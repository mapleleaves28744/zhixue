### Task 2: 拆分领域 ToolSet，保持 Registry 契约

**Files:**
- Create: `backend/app/agent_runtime/toolsets/__init__.py`
- Create: `backend/app/agent_runtime/toolsets/common.py`
- Create: `backend/app/agent_runtime/toolsets/knowledge_tools.py`
- Create: `backend/app/agent_runtime/toolsets/learning_tools.py`
- Create: `backend/app/agent_runtime/toolsets/profile_tools.py`
- Create: `backend/app/agent_runtime/toolsets/review_tools.py`
- Create: `backend/app/agent_runtime/toolsets/media_tools.py`
- Modify: `backend/app/agent_runtime/service_tools.py`
- Modify: `backend/tests/test_agent_runtime.py`

**Interfaces:**
- Produces: `register_knowledge_tools`, `register_learning_tools`, `register_profile_tools`, `register_review_tools`, `register_media_tools`.
- Preserves: `build_learning_tool_registry(db, current_user, *, result_loader=None, result_saver=None)`.

- [ ] **Step 1: Write failing Registry-equivalence test**

```python
def test_learning_registry_keeps_public_tool_contracts() -> None:
    registry = build_learning_tool_registry(SimpleNamespace(), SimpleNamespace(id=uuid4()))
    schemas = {item["function"]["name"]: item["function"]["parameters"] for item in registry.tool_schemas()}
    assert set(schemas) == EXPECTED_TOOL_NAMES
    assert schemas["generate_interactive_courseware"]["required"] == ["topic"]
    assert registry.risk_level("apply_evolution_strategy") == "high"
    assert registry.requires_confirmation("apply_evolution_strategy") is True
```

Set `EXPECTED_TOOL_NAMES` to the current 24 tool names plus an assertion that each ToolSet module exports its registration function. This fails until ToolSet modules exist.

- [ ] **Step 2: Verify RED**

Run: `cd backend && python -m pytest tests/test_agent_runtime.py::test_learning_registry_keeps_public_tool_contracts -v`

Expected: import failure for `app.agent_runtime.toolsets`.

- [ ] **Step 3: Move handlers without altering registration**

```python
async def register_knowledge_tools(registry: ToolRegistry, db: AsyncSession, current_user: User) -> None:
    register_tool(registry, "search_course_knowledge", "使用向量、关键词、metadata 和 rerank 混合检索课程资料，返回可引用片段。", "KnowledgeAgent", {"query": {"type": "string"}, "top_k": {"type": "integer", "minimum": 1, "maximum": 20}}, ["query"], search_knowledge)
    register_tool(registry, "search_web", "通过 AnySearch 联网搜索互联网实时信息，返回可引用的网页标题、URL 与摘要。", "KnowledgeAgent", WEB_SEARCH_PROPERTIES, ["query"], search_web, timeout_seconds=45)
    register_tool(registry, "parse_uploaded_document", "解析已上传的课程资料（PDF/DOCX/TXT/MD），自动切片和向量化，供 RAG 检索使用。", "KnowledgeAgent", {"material_id": {"type": "string"}}, ["material_id"], parse_document, writes_db=True)
    register_tool(registry, "generate_mindmap", "围绕课程知识点生成 Mermaid 思维导图，可视化知识结构关系。", "KnowledgeAgent", MINDMAP_PROPERTIES, ["topic"], generate_mindmap_handler, writes_db=True)
    register_tool(registry, "generate_diagram", "围绕知识概念生成流程图、架构图或示意图的 Mermaid 代码。", "KnowledgeAgent", DIAGRAM_PROPERTIES, ["concept"], generate_diagram_handler, writes_db=True)
```

Move current nested handlers and `_register` calls verbatim: knowledge/search to `knowledge_tools`; path/explanation/quiz/diagnosis/recommendations to `learning_tools`; profile/memory/evolution to `profile_tools`; review handlers to `review_tools`; audio/image/video/courseware handlers to `media_tools`. Keep a shared `register_tool(...)` helper in `common.py`. `service_tools.py` constructs the Registry and invokes ToolSets in current registration order.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd backend && python -m pytest tests/test_agent_runtime.py tests/test_tool_registry_jsonschema.py -v`

Commit: `git add backend/app/agent_runtime/service_tools.py backend/app/agent_runtime/toolsets backend/tests/test_agent_runtime.py && git commit -m "refactor: split agent service toolsets"`

