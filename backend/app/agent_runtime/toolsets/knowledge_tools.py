from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools import ToolContext, ToolExecutionResult, ToolRegistry
from app.agent_runtime.toolsets.common import register_tool
from app.models.user import User


def register_knowledge_tools(
    registry: ToolRegistry,
    db: AsyncSession,
    current_user: User,
    *,
    tool_names: Iterable[str] | None = None,
) -> None:
    selected = set(tool_names or ())

    def include(name: str) -> bool:
        return not selected or name in selected

    async def search_knowledge(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.knowledge_search_service import KnowledgeSearchService

        payload = await KnowledgeSearchService(db).search(
            current_user=current_user,
            course_id=context.course_id,
            query=str(arguments["query"]),
            top_k=int(arguments.get("top_k") or 5),
        )
        items = payload.get("items") or []
        graph_context = payload.get("graph_context") or {}
        citations = [
            {
                "source_type": "document",
                "title": item.get("source_title") or "课程资料",
                "source_id": item.get("material_id"),
                "chunk_id": item.get("chunk_id"),
                "page_no": item.get("page_no"),
                "score": item.get("score"),
                "quote": str(item.get("content") or "")[:300],
            }
            for item in items
        ]
        return ToolExecutionResult(
            output={"items": items, "graph_context": graph_context},
            evidence=citations,
            citations=citations,
        )

    async def search_web(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.web_search_service import WebSearchService

        payload = await WebSearchService().search(
            query=str(arguments["query"]),
            max_results=int(arguments.get("max_results") or 5),
            domain=str(arguments.get("domain") or "") or None,
        )
        citations = payload.get("citations") or []
        return ToolExecutionResult(output=payload, evidence=citations, citations=citations)

    async def parse_document(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.embedding_service import EmbeddingService
        from app.services.material_service import MaterialService

        material_id = UUID(str(arguments["material_id"]))
        parse_result = await MaterialService(db).parse_material(
            material_id=material_id,
            current_user=current_user,
        )
        embedded_count = await EmbeddingService(db).generate_embeddings(material_id)
        return ToolExecutionResult(
            output={
                "material_id": str(material_id),
                "file_name": parse_result.file_name,
                "text_length": parse_result.text_length,
                "parse_status": parse_result.parse_status,
                "embedded_count": embedded_count,
            },
            evidence=[
                f"已解析 {parse_result.file_name}，提取 {parse_result.text_length} 字符",
                f"已生成 {embedded_count} 个向量切片",
            ],
            artifact_refs=[{"type": "material", "id": str(material_id), "title": parse_result.file_name}],
        )

    async def generate_mindmap_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.mindmap_service import MindmapService

        topic = str(arguments.get("topic") or "").strip() or "数据结构知识结构"
        result = await MindmapService(db).generate(
            current_user=current_user,
            course_id=context.course_id,
            topic=topic,
            scope=str(arguments.get("scope") or "course"),
            depth=int(arguments.get("depth") or 3),
        )
        return ToolExecutionResult(
            output=result,
            evidence=result.get("citations") or [],
            citations=result.get("citations") or [],
            artifact_refs=[
                {"type": "resource", "subtype": "mindmap", "id": result["resource_id"], "title": result["title"]}
            ],
        )

    async def generate_diagram_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
        from app.services.diagram_service import DiagramService

        concept = str(arguments.get("concept") or "").strip() or "数据结构概念"
        result = await DiagramService(db).generate(
            current_user=current_user,
            course_id=context.course_id,
            concept=concept,
            diagram_type=str(arguments.get("diagram_type") or "flowchart"),
        )
        return ToolExecutionResult(
            output=result,
            evidence=result.get("citations") or [],
            citations=result.get("citations") or [],
            artifact_refs=[
                {"type": "resource", "subtype": "diagram", "id": result["resource_id"], "title": result["title"]}
            ],
        )

    if include("search_course_knowledge"):
        register_tool(registry, "search_course_knowledge", "使用向量、关键词、metadata 和 rerank 混合检索课程资料，返回可引用片段。", "KnowledgeAgent", {"query": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}}, ["query"], search_knowledge)
    if include("search_web"):
        register_tool(registry, "search_web", "通过 AnySearch 联网搜索互联网实时信息，返回可引用的网页标题、URL 与摘要。适用于最新资讯、公开资料、技术文档等课程库未覆盖的问题。", "KnowledgeAgent", {"query": {"type": "string", "description": "搜索关键词或完整问题"}, "max_results": {"type": "integer", "minimum": 1, "maximum": 10}, "domain": {"type": "string", "description": "可选垂直领域，如 general/academic/code/finance"}}, ["query"], search_web, timeout_seconds=45)
    if include("parse_uploaded_document"):
        register_tool(registry, "parse_uploaded_document", "解析已上传的课程资料（PDF/DOCX/TXT/MD），自动切片和向量化，供 RAG 检索使用。", "KnowledgeAgent", {"material_id": {"type": "string", "description": "课程资料 UUID"}}, ["material_id"], parse_document, writes_db=True)
    if include("generate_mindmap"):
        register_tool(registry, "generate_mindmap", "围绕课程知识点生成 Mermaid 思维导图，可视化知识结构关系。", "KnowledgeAgent", {"topic": {"type": "string", "description": "知识主题"}, "scope": {"type": "string", "enum": ["course", "chapter", "custom"]}, "depth": {"type": "integer", "minimum": 2, "maximum": 5}}, ["topic"], generate_mindmap_handler, writes_db=True)
    if include("generate_diagram"):
        register_tool(registry, "generate_diagram", "围绕知识概念生成流程图、架构图或示意图的 Mermaid 代码。", "KnowledgeAgent", {"concept": {"type": "string", "description": "需要图解的概念"}, "diagram_type": {"type": "string", "enum": ["flowchart", "sequence", "class", "er"]}}, ["concept"], generate_diagram_handler, writes_db=True)
