# Grounded QA 双通道智能问答 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将普通课程问答收敛为一次可信检索和一次流式 LLM 调用，同时让 Tutor 与 Agent 共享同一问答内核，并修复引用展示、会话恢复和窄屏不可用问题。

**Architecture:** 新增 `EvidenceRetrievalService`、`CitationValidator` 与 `GroundedQaPipeline`，把可信证据、编号引用、生成、持久化和性能指标组成唯一课程问答内核。Tutor API 直接调用该内核；复杂任务仍由 LangGraph 编排，`answer_course_question` 工具复用内核并把结果确定性传给 `finalize`，深度 Review、画像、记忆和知识抽取在事务提交后通过现有 EventBus 异步执行。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy AsyncSession、Pydantic v2、PostgreSQL/pgvector、现有 LLM Provider、LangGraph、Next.js 16、React 18、TypeScript 5.6、Tailwind CSS、Radix Dialog、pytest、Node source-contract tests。

## Global Constraints

- 普通问答无 Provider fallback 时只允许一次 `chat` 或 `stream_chat` 调用；fallback 场景最多两次并显式标记。
- 普通问答不进入 Supervisor、同步 Review Agent 或同步 Memory Agent。
- 所有展示引用必须映射到真实 `material_id + chunk_id` 或真实 `wiki_page_id`；图谱关系不得伪造 chunk/material UUID。
- 无可信证据时返回 `grounding_status="insufficient"` 与空引用，不生成 inference 类型引用。
- 响应目标：首个进度事件不超过 0.5 秒、比赛真实 Provider 首 token 不超过 3 秒、总完成时间不超过 15 秒。
- SSE 固定顺序为 `progress(retrieve_context) → evidence → progress(llm_generation) → delta → progress(validate_citations) → done`；简单寒暄可省略 `evidence`。
- 已输出 token 后发生错误时保留部分回答，不自动发送第二个完整请求。
- 快速问答复用现有 `agent_conversations`、`agent_messages`、`learning_records`、`agent_runs` 与 `llm_call_logs`；不新增表、不修改字段、不生成 Alembic migration。
- API 仍使用 `/api/v1/tutor/chat`、`/api/v1/tutor/messages/{message_id}/feedback` 与 `/api/v1/tutor/messages/{message_id}/save-to-wiki`。
- 390×844、960×768、1440×900 三档视口都必须保持问答区和输入框可见。
- 所有 LLM 调用必须经过 `backend/app/llm/provider.py` 的现有 Provider 抽象；无真实 Key 时继续支持明确标识的 Mock Provider。
- 每个任务先写失败测试、确认失败、写最小实现、确认通过，再提交；不得改动 `deploy/ssh-cursor-proxy.config.example`。
- 修改 Router 或 Schema 后执行 `python scripts/export_implementation_docs.py`；所有文档修改后执行 `python scripts/check_docs.py`。

## File Responsibility Map

- `backend/app/rag/evidence.py`：问答证据、图谱上下文、证据包和确定性引用校验结果的内部类型。
- `backend/app/services/citation_validator.py`：解析回答中的 `[S#]` 并映射真实证据，不调用 LLM。
- `backend/app/services/evidence_retrieval_service.py`：调用现有 Hybrid/Graph Retriever、匹配 Wiki、执行可信阈值、去重和编号。
- `backend/app/services/grounded_qa_pipeline.py`：唯一课程问答内核，负责普通/流式生成、持久化、性能指标和 EventBus 发布。
- `backend/app/services/tutor_service.py`：保留反馈和保存 Wiki 能力；聊天入口改为薄委托。
- `backend/app/agents/tutor_agent.py`：保留 Agent 注册身份，改为 `GroundedQaPipeline` 的兼容适配器。
- `backend/app/agent_runtime/tools.py`、`service_tools.py`、`graph.py`、`supervisor_intents.py`：共享问答工具结果并消除重复检索与二次总结。
- `frontend/services/tutorService.ts`、`frontend/hooks/useTutorStream.ts`：唯一 Tutor SSE 状态机和安全回退策略。
- `frontend/components/assistant/TutorEvidencePanel.tsx`：依据状态、引用、相关知识点、追问、反馈和保存操作。
- `frontend/components/assistant/ResourcePanelDialog.tsx`：中屏侧抽屉与移动端底部抽屉。
- `frontend/components/assistant/AssistantPageClient.tsx`：组合聊天、会话恢复、服务状态和资源抽屉，不再直接实现 SSE 协议。
- `scripts/evaluate_public_kb.py`：把检索、引用、拒答和答案正确性拆成独立指标。

---

### Task 1: Evidence contracts and deterministic citation validation

**Files:**
- Create: `backend/app/rag/evidence.py`
- Create: `backend/app/services/citation_validator.py`
- Create: `backend/tests/test_citation_validator.py`

**Interfaces:**
- Consumes: `UUID`, document/Wiki database identifiers, final answer text containing optional `[S1]` markers.
- Produces: `EvidenceItem`, `GraphContext`, `EvidenceBundle`, `CitationValidationResult`, and `CitationValidator.validate(answer: str, evidence: list[EvidenceItem]) -> CitationValidationResult`.

- [ ] **Step 1: Write the failing validator tests**

```python
from uuid import uuid4

from app.rag.evidence import EvidenceItem
from app.services.citation_validator import CitationValidator


def _document(key: str) -> EvidenceItem:
    return EvidenceItem(
        citation_key=key,
        source_type="document",
        source_id=uuid4(),
        chunk_id=uuid4(),
        title="数据结构讲义",
        quote="栈遵循后进先出原则。",
        retrieval_mode="hybrid",
        confidence="strong",
    )


def test_validator_keeps_only_used_known_citations_in_answer_order() -> None:
    s1, s2 = _document("S1"), _document("S2")
    result = CitationValidator().validate("结论一 [S2]，结论二 [S9]，再次引用 [S2]。", [s1, s2])

    assert [item.citation_key for item in result.citations] == ["S2"]
    assert result.unknown_keys == ["S9"]
    assert result.grounding_status == "grounded"


def test_validator_marks_supported_answer_without_marker_as_partial() -> None:
    result = CitationValidator().validate("栈遵循后进先出原则。", [_document("S1")])

    assert result.citations == []
    assert result.grounding_status == "partial"


def test_validator_marks_no_evidence_as_insufficient() -> None:
    result = CitationValidator().validate("课程资料中没有可验证依据。", [])

    assert result.citations == []
    assert result.grounding_status == "insufficient"
```

- [ ] **Step 2: Run the tests and confirm the missing-module failure**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_citation_validator.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'app.rag.evidence'`.

- [ ] **Step 3: Add the internal evidence types**

```python
# backend/app/rag/evidence.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID


GroundingStatus = Literal["grounded", "partial", "insufficient"]


@dataclass(frozen=True)
class EvidenceItem:
    citation_key: str
    source_type: Literal["document", "wiki"]
    source_id: UUID
    title: str
    quote: str
    chunk_id: UUID | None = None
    page_id: UUID | None = None
    knowledge_id: UUID | None = None
    page_no: int | None = None
    retrieval_mode: str = "hybrid"
    vector_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: float = 0.0
    confidence: Literal["strong", "acceptable"] = "acceptable"

    def as_citation(self) -> dict[str, object]:
        return {
            "citation_key": self.citation_key,
            "source_type": self.source_type,
            "title": self.title,
            "source_id": str(self.source_id),
            "chunk_id": str(self.chunk_id) if self.chunk_id else None,
            "page_id": str(self.page_id) if self.page_id else None,
            "knowledge_id": str(self.knowledge_id) if self.knowledge_id else None,
            "page_no": self.page_no,
            "score": round(self.rerank_score, 6),
            "quote": self.quote,
            "retrieval_mode": self.retrieval_mode,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class GraphContext:
    seed_knowledge_ids: list[UUID] = field(default_factory=list)
    expanded_knowledge_ids: list[UUID] = field(default_factory=list)
    relation_paths: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceBundle:
    evidence: list[EvidenceItem]
    graph_context: GraphContext
    candidate_count: int


@dataclass(frozen=True)
class CitationValidationResult:
    citations: list[EvidenceItem]
    unknown_keys: list[str]
    grounding_status: GroundingStatus
    grounding_message: str
```

- [ ] **Step 4: Implement marker parsing and deterministic mapping**

```python
# backend/app/services/citation_validator.py
from __future__ import annotations

import re

from app.rag.evidence import CitationValidationResult, EvidenceItem


class CitationValidator:
    _marker = re.compile(r"\[(S\d+)\]")

    def validate(self, answer: str, evidence: list[EvidenceItem]) -> CitationValidationResult:
        by_key = {item.citation_key: item for item in evidence}
        seen: set[str] = set()
        used: list[EvidenceItem] = []
        unknown: list[str] = []
        for key in self._marker.findall(answer):
            if key in seen:
                continue
            seen.add(key)
            item = by_key.get(key)
            if item is None:
                unknown.append(key)
            else:
                used.append(item)
        if not evidence:
            status = "insufficient"
            message = "课程资料未找到可靠依据。"
        elif used:
            status = "grounded"
            message = f"回答已绑定 {len(used)} 条课程依据。"
        else:
            status = "partial"
            message = "已检索到课程依据，但回答未完整绑定来源。"
        return CitationValidationResult(used, unknown, status, message)
```

- [ ] **Step 5: Run the validator tests**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_citation_validator.py -q`

Expected: `3 passed`.

- [ ] **Step 6: Commit the evidence boundary**

```powershell
git add backend/app/rag/evidence.py backend/app/services/citation_validator.py backend/tests/test_citation_validator.py
git commit -m "feat: add grounded qa evidence validation"
```

### Task 2: Trusted retrieval, real identifiers, and Wiki matching

**Files:**
- Create: `backend/app/services/evidence_retrieval_service.py`
- Create: `backend/tests/test_evidence_retrieval_service.py`
- Create: `backend/tests/test_hybrid_retriever.py`
- Modify: `backend/app/rag/hybrid_retriever.py`
- Modify: `backend/app/rag/graph_expansion.py`
- Modify: `backend/app/rag/graph_retriever.py`
- Modify: `backend/app/agents/tutor_agent.py`
- Modify: `backend/tests/test_graph_retriever.py`
- Modify: `backend/tests/test_tutor.py`

**Interfaces:**
- Consumes: `GraphRetriever.search(course_id, query, user_id, top_k, expand_hops, knowledge_id)` and readable `WikiPage` objects.
- Produces: `EvidenceRetrievalService.retrieve(course_id, user_id, question, top_k, knowledge_id, wiki_page_id, use_rag, use_wiki) -> EvidenceBundle`; graph-expanded knowledge is returned only in `GraphContext`; `TutorAgent._related_knowledge_points()` uses `WikiPage.knowledge_id`.

- [ ] **Step 1: Add failing confidence and identifier tests**

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.evidence_retrieval_service import EvidenceRetrievalService


@pytest.mark.asyncio
async def test_retrieval_filters_low_confidence_and_limits_two_chunks_per_material() -> None:
    material_id = uuid4()
    service = EvidenceRetrievalService(db=None)  # type: ignore[arg-type]
    service.graph.search = AsyncMock(return_value={
        "items": [
            {"chunk_id": str(uuid4()), "material_id": str(material_id), "content": "栈是 LIFO", "source_title": "讲义", "vector_score": 0.61, "keyword_score": 0.0, "score": 0.61, "retrieval_mode": "vector", "extra_meta": {}},
            {"chunk_id": str(uuid4()), "material_id": str(material_id), "content": "入栈操作", "source_title": "讲义", "vector_score": 0.58, "keyword_score": 0.0, "score": 0.58, "retrieval_mode": "vector", "extra_meta": {}},
            {"chunk_id": str(uuid4()), "material_id": str(material_id), "content": "出栈操作", "source_title": "讲义", "vector_score": 0.57, "keyword_score": 0.0, "score": 0.57, "retrieval_mode": "vector", "extra_meta": {}},
            {"chunk_id": str(uuid4()), "material_id": str(uuid4()), "content": "无关内容", "source_title": "干扰资料", "vector_score": 0.12, "keyword_score": 0.0, "score": 0.12, "retrieval_mode": "vector", "extra_meta": {}},
        ],
        "graph_context": {"seed_knowledge_ids": [], "expanded_knowledge_ids": [], "relation_paths": []},
    })
    service._load_wiki_pages = AsyncMock(return_value=[])

    bundle = await service.retrieve(
        course_id=uuid4(), user_id=uuid4(), question="什么是栈？", top_k=5,
        knowledge_id=None, wiki_page_id=None, use_rag=True, use_wiki=True,
    )

    assert len(bundle.evidence) == 2
    assert {item.source_id for item in bundle.evidence} == {material_id}
    assert [item.citation_key for item in bundle.evidence] == ["S1", "S2"]


def test_wiki_related_point_uses_real_knowledge_id() -> None:
    from app.agents.tutor_agent import TutorAgent

    knowledge_id = uuid4()
    page = SimpleNamespace(id=uuid4(), knowledge_id=knowledge_id, title="递归调用栈")
    related = TutorAgent(db=None)._related_knowledge_points("递归", [page])  # type: ignore[arg-type]
    assert related[0]["knowledge_id"] == str(knowledge_id)
```

Add this graph assertion to `backend/tests/test_graph_retriever.py`:

```python
@pytest.mark.asyncio
async def test_graph_expansion_does_not_create_synthetic_document_candidates() -> None:
    retriever = GraphRetriever.__new__(GraphRetriever)
    rows = [MagicMock(id=uuid4(), name="BFS", description="广度优先搜索")]
    assert await retriever._candidates_from_knowledge(rows, []) == []
```

Create `backend/tests/test_hybrid_retriever.py`:

```python
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.rag.hybrid_retriever import HybridRetriever, RetrievalCandidate


@pytest.mark.asyncio
async def test_vector_failure_falls_back_to_keyword_candidates() -> None:
    retriever = HybridRetriever(db=None)  # type: ignore[arg-type]
    keyword = RetrievalCandidate(
        chunk_id=uuid4(), material_id=uuid4(), content="栈是 LIFO 结构",
        source_title="数据结构讲义", page_no=3, keyword_score=2.0,
        keyword_rank=1, retrieval_mode="keyword",
    )
    retriever._vector_search = AsyncMock(side_effect=RuntimeError("vector unavailable"))
    retriever._keyword_search = AsyncMock(return_value=[keyword])

    result = await retriever.search(uuid4(), "什么是栈？", uuid4(), top_k=5)

    assert [item.chunk_id for item in result] == [keyword.chunk_id]
    retriever._keyword_search.assert_awaited_once()
```

- [ ] **Step 2: Run the focused tests and confirm failures**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_evidence_retrieval_service.py backend/tests/test_hybrid_retriever.py backend/tests/test_graph_retriever.py backend/tests/test_tutor.py -q`

Expected: FAIL because `EvidenceRetrievalService` does not exist, graph expansion still returns random IDs, and the Tutor related point uses `page.id`.

- [ ] **Step 3: Remove synthetic graph candidates and pass `knowledge_id` through**

Replace `GraphRetriever._candidates_from_knowledge` with:

```python
async def _candidates_from_knowledge(
    self,
    rows: list[KnowledgePoint],
    seed_ids: list[UUID],
) -> list[RetrievalCandidate]:
    return []
```

Extend the public search signature and Hybrid call:

```python
async def search(
    self,
    *,
    course_id: UUID,
    query: str,
    user_id: UUID | None,
    top_k: int = 8,
    expand_hops: int = 1,
    knowledge_id: UUID | None = None,
) -> dict[str, Any]:
    seeds = await self.hybrid.search(
        course_id=course_id,
        query=query,
        user_id=user_id,
        top_k=max(top_k * 2, 10),
        knowledge_id=knowledge_id,
    )
```

Keep real knowledge IDs in `graph_context` and remove the call that appends `_candidates_from_knowledge` results to document candidates.

Extend `GraphExpansionContext` with `seed_knowledge_ids` and `expanded_knowledge_ids`, return both lists from `to_dict()`, and populate them from `seed_kp_ids` and expanded `kp_ids`. Remove `_map_candidates_to_knowledge_ids()`'s fallback that chooses the first three visible knowledge points when no retrieved chunk maps to a knowledge point. Extend `_serialize()` with:

```python
"vector_score": round(item.vector_score, 6),
"keyword_score": round(item.keyword_score, 6),
"rerank_score": round(item.rerank_score, 6),
```

In `HybridRetriever.search()`, isolate vector failure while preserving keyword retrieval:

```python
try:
    vector_candidates = await self._vector_search(
        course_id=course_id, query=query, user_id=user_id,
        top_k=candidate_k, knowledge_id=knowledge_id,
    )
except Exception:
    vector_candidates = []
keyword_candidates = await self._keyword_search(
    course_id=course_id, query=query, user_id=user_id,
    top_k=candidate_k, knowledge_id=knowledge_id,
)
```

Extend `_query_terms()` with unique Chinese 2–4 character windows from each unsplit question segment, capped at 24 generated terms, while retaining matched domain terms. This gives keyword retrieval dynamic terms without adding a tokenizer dependency.

- [ ] **Step 4: Implement trusted evidence selection and exact Wiki matching**

Create `EvidenceRetrievalService` with these public rules:

```python
class EvidenceRetrievalService:
    VECTOR_STRONG = 0.55
    VECTOR_WITH_TITLE = 0.45
    KEYWORD_STRONG = 1.0
    MAX_EVIDENCE = 5
    MAX_PER_SOURCE = 2

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.graph = GraphRetriever(db)

    def _accept_document(self, item: dict[str, Any], terms: list[str]) -> bool:
        vector = float(item.get("vector_score") or 0.0)
        keyword = float(item.get("keyword_score") or 0.0)
        title = str(item.get("source_title") or "").lower()
        title_hit = any(term.lower() in title for term in terms)
        return keyword >= self.KEYWORD_STRONG or vector >= self.VECTOR_STRONG or (
            title_hit and vector >= self.VECTOR_WITH_TITLE
        )

    def _confidence(self, item: dict[str, Any]) -> Literal["strong", "acceptable"]:
        if float(item.get("keyword_score") or 0.0) >= self.KEYWORD_STRONG:
            return "strong"
        if float(item.get("vector_score") or 0.0) >= self.VECTOR_STRONG:
            return "strong"
        return "acceptable"
```

`retrieve()` must call `GraphRetriever.search(course_id=course_id, query=question, user_id=user_id, top_k=max(top_k * 2, 10), expand_hops=1, knowledge_id=knowledge_id)`, reject document items missing parseable `material_id` or `chunk_id`, cap each material at two items, append explicit/readable Wiki evidence before auto-matched Wiki, cap the total at five, and assign `S1` through `S5` only after final ordering. `_load_wiki_pages()` must return `[]` when no question term of length at least two matches title/summary/content or `page.knowledge_id != knowledge_id`; it must never return arbitrary pages.

- [ ] **Step 5: Correct Tutor compatibility helpers**

Replace the fallback tail in `TutorAgent._load_wiki_pages()`:

```python
if scored:
    return [page for _, page in sorted(scored, key=lambda item: item[0], reverse=True)[:3]]
return []
```

Replace the first line of `_related_knowledge_points()`:

```python
related = [
    {"knowledge_id": str(page.knowledge_id) if page.knowledge_id else None, "name": page.title}
    for page in wiki_pages[:3]
]
```

- [ ] **Step 6: Run trusted retrieval tests**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_evidence_retrieval_service.py backend/tests/test_hybrid_retriever.py backend/tests/test_graph_retriever.py backend/tests/test_tutor.py -q`

Expected: all selected tests PASS and no graph-expanded item has a synthetic document identifier.

- [ ] **Step 7: Commit trusted retrieval**

```powershell
git add backend/app/services/evidence_retrieval_service.py backend/app/rag/hybrid_retriever.py backend/app/rag/graph_expansion.py backend/app/rag/graph_retriever.py backend/app/agents/tutor_agent.py backend/tests/test_evidence_retrieval_service.py backend/tests/test_hybrid_retriever.py backend/tests/test_graph_retriever.py backend/tests/test_tutor.py
git commit -m "fix: keep grounded qa evidence traceable"
```

### Task 3: Single-call GroundedQaPipeline and grounded prompt

**Files:**
- Create: `backend/app/services/grounded_qa_pipeline.py`
- Create: `backend/tests/test_grounded_qa_pipeline.py`
- Modify: `backend/app/services/prompt_service.py`
- Modify: `backend/app/services/personalization_context_service.py`
- Modify: `backend/app/agents/tutor_agent.py`

**Interfaces:**
- Consumes: `TutorChatRequest`, `User`, `EvidenceRetrievalService.retrieve()`, `CitationValidator.validate()`, and existing `get_llm_provider()`.
- Produces: `GroundedQaPipeline.answer(payload: TutorChatRequest, current_user: User, persist_conversation_messages: bool = True) -> TutorChatResponse`; one normal LLM call; `TutorAgent.run()` delegates to it.

- [ ] **Step 1: Write failing one-call and insufficient-evidence tests**

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.rag.evidence import EvidenceBundle, GraphContext
from app.schemas.tutor import TutorChatRequest
from app.services.grounded_qa_pipeline import GroundedQaPipeline


@pytest.mark.asyncio
async def test_answer_uses_one_llm_call_and_no_sync_review() -> None:
    provider = SimpleNamespace(chat=AsyncMock(return_value=SimpleNamespace(
        content="栈遵循后进先出 [S1]。", model="mock", provider="mock", raw={}
    )))
    pipeline = GroundedQaPipeline(db=None)  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    pipeline._retrieve = AsyncMock(return_value=EvidenceBundle([], GraphContext(), 0))
    pipeline._build_generation = AsyncMock(return_value=(provider, "grounded prompt", None))
    pipeline._persist = AsyncMock(return_value=(None, None))
    pipeline.logs.start_run = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    pipeline.logs.finish_run = AsyncMock()

    result = await pipeline.answer(
        TutorChatRequest(course_id=uuid4(), question="什么是栈？"),
        SimpleNamespace(id=uuid4(), role="student"),
    )

    assert provider.chat.await_count == 1
    assert result.grounding_status == "insufficient"
    assert result.citations == []
    assert result.performance.llm_call_count == 1


@pytest.mark.asyncio
async def test_simple_greeting_skips_retrieval_and_llm() -> None:
    pipeline = GroundedQaPipeline(db=None)  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    pipeline._retrieve = AsyncMock()
    pipeline._persist = AsyncMock(return_value=(None, None))

    result = await pipeline.answer(
        TutorChatRequest(course_id=uuid4(), question="你好"),
        SimpleNamespace(id=uuid4(), role="student"),
    )

    pipeline._retrieve.assert_not_awaited()
    assert result.provider == "local_intent_router"
    assert result.performance.llm_call_count == 0
```

- [ ] **Step 2: Run the focused test and confirm the missing pipeline failure**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_grounded_qa_pipeline.py -q`

Expected: FAIL during collection because `grounded_qa_pipeline.py` does not exist.

- [ ] **Step 3: Extend the Tutor response contract**

Add to `backend/app/schemas/tutor.py`:

```python
class TutorPerformance(BaseModel):
    retrieval_ms: int = 0
    first_token_ms: int | None = None
    generation_ms: int = 0
    total_ms: int = 0
    llm_call_count: int = 0
    evidence_candidate_count: int = 0
    evidence_accepted_count: int = 0


class TutorChatRequest(BaseModel):
    course_id: UUID
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    session_id: UUID | None = None
    knowledge_id: UUID | None = None
    wiki_page_id: UUID | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    use_rag: bool = True
    use_wiki: bool = True
    use_profile: bool = True
    stream: bool = False
```

Extend `TutorCitation` with `citation_key`, `knowledge_id`, `retrieval_mode`, and `confidence`. Extend `TutorChatResponse` with:

```python
conversation_id: UUID | None = None
grounding_status: Literal["grounded", "partial", "insufficient"] = "insufficient"
grounding_message: str = "课程资料未找到可靠依据。"
performance: TutorPerformance = Field(default_factory=TutorPerformance)
postprocess_status: Literal["queued", "skipped"] = "skipped"
```

- [ ] **Step 4: Replace the default Tutor prompt with numbered evidence rules**

Use this exact `DEFAULT_PROMPTS[("TutorAgent", "tutor.qa")]` value:

```python
(
    "你是课程 AI Tutor。先直接回答，再给必要解释。\n"
    "课程资料支持的关键结论必须在句末标注 [S1]、[S2]；只能使用输入中存在的编号。\n"
    "没有可信课程依据时，明确写出‘课程资料未找到可靠依据’，并把通用知识放在‘通用知识补充’段落。\n"
    "不要编造来源，不要输出独立引用清单。\n\n"
    "问题：{question}\n\n"
    "编号课程证据：\n{retrieved_context}\n\n"
    "知识关系：\n{graph_context}\n\n"
    "学生画像：\n{student_profile}\n\n"
    "长期记忆：\n{memory_context}"
)
```

Add `PromptService.render_grounded_tutor_prompt(params)` that first calls `render_prompt(agent_name="TutorAgent", scene="tutor.qa", params=params)` and then appends this invariant suffix even when an older database prompt is active:

```python
GROUNDED_TUTOR_RULES = (
    "\n\n强制引用规则：课程依据必须使用当前输入中的 [S#]；"
    "不得引用不存在的编号；没有可信证据时必须明确说明课程依据不足。"
)

async def render_grounded_tutor_prompt(self, params: dict[str, Any]) -> RenderedPrompt:
    rendered = await self.render_prompt(
        agent_name="TutorAgent", scene="tutor.qa", params=params
    )
    return RenderedPrompt(
        content=f"{rendered.content}{GROUNDED_TUTOR_RULES}",
        prompt_version_id=rendered.prompt_version_id,
        source=rendered.source,
    )
```

Add separate personalization formatters and use them in `_build_generation()`:

```python
@staticmethod
def format_profile_for_prompt(context: dict[str, Any]) -> str:
    profile_only = {**context, "memories": []}
    return PersonalizationContextService.format_for_prompt(profile_only)

@staticmethod
def format_memories_for_prompt(context: dict[str, Any]) -> str:
    memories = context.get("memories") or []
    return "；".join(item.content for item in memories) or "暂无可用长期学习记忆。"
```

- [ ] **Step 5: Implement the non-streaming pipeline**

The new class must initialize `EvidenceRetrievalService`, `CitationValidator`, `LearningRecordService`, `AgentConversationRepository`, and `AgentLogService`; authorize with `CourseService.get_readable_course`; return `simple_greeting_answer()` before retrieval/model work for a local greeting; format each evidence block as `[S#] 标题/页码/原文`; call `PromptService.render_grounded_tutor_prompt`; call `provider.chat` once with `temperature=0.2`, `max_tokens=1200`, and disabled thinking; validate markers; and build `TutorChatResponse` with exact provider/fallback/performance metadata. Split personalization formatting so profile fields and active memories are formatted separately rather than copying one combined string into both prompt slots. Start one `TutorAgent` run before retrieval, pass its ID to `get_llm_provider(agent_run_id=run.id)`, and finish it with the response plus `performance`, candidate counts and grounding status in `output_payload`.

Use this public control flow; private helpers named below are implemented in the same file:

```python
class GroundedQaPipeline:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.retrieval = EvidenceRetrievalService(db)
        self.validator = CitationValidator()
        self.records = LearningRecordService(db)
        self.conversations = AgentConversationRepository(db)
        self.logs = AgentLogService(db)

    async def answer(
        self,
        payload: TutorChatRequest,
        current_user: User,
        *,
        persist_conversation_messages: bool = True,
    ) -> TutorChatResponse:
        started = perf_counter()
        course = await self._authorize(payload, current_user)
        retrieval_started = perf_counter()
        bundle = await self._retrieve(payload, current_user)
        retrieval_ms = int((perf_counter() - retrieval_started) * 1000)
        provider, prompt, prompt_version_id = await self._build_generation(
            bundle, payload, current_user
        )
        generation_started = perf_counter()
        llm_response = await provider.chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=0.2,
            max_tokens=1200,
            thinking={"type": "disabled"},
            prompt_version_id=prompt_version_id,
        )
        answer = llm_response.content.strip()
        validated = self.validator.validate(answer, bundle.evidence)
        performance = TutorPerformance(
            retrieval_ms=retrieval_ms,
            first_token_ms=None,
            generation_ms=int((perf_counter() - generation_started) * 1000),
            total_ms=int((perf_counter() - started) * 1000),
            llm_call_count=1,
            evidence_candidate_count=bundle.candidate_count,
            evidence_accepted_count=len(bundle.evidence),
        )
        response = self._build_response(
            answer=answer,
            validation=validated,
            bundle=bundle,
            payload=payload,
            llm_response=llm_response,
            performance=performance,
        )
        message_id, conversation_id = await self._persist(
            response=response,
            payload=payload,
            current_user=current_user,
            course=course,
            persist_conversation_messages=persist_conversation_messages,
        )
        return response.model_copy(update={
            "message_id": message_id,
            "conversation_id": conversation_id,
            "postprocess_status": "queued" if message_id else "skipped",
        })
```

Implement `_authorize(payload, current_user) -> Course` with `CourseService.get_readable_course`; `_retrieve(payload, current_user) -> EvidenceBundle` as the single call to Task 2; `_build_generation(bundle, payload, current_user) -> tuple[object, str, UUID | None]` with numbered evidence and separated profile/memory text; `_build_response(answer, validation, bundle, payload, llm_response, performance) -> TutorChatResponse` with validated citations, related points, follow-ups, fallback metadata and graph context. Until Task 4, `_persist(response, payload, current_user, course, persist_conversation_messages) -> tuple[UUID | None, UUID | None]` returns `(None, payload.conversation_id)` without writing.

- [ ] **Step 6: Convert TutorAgent into a compatibility adapter**

Replace `TutorAgent.run()` with:

```python
async def run(self, context: AgentContext) -> AgentResult:
    question = str(context.params.get("question") or "").strip()
    if not question:
        return self.error_result(message="缺少 question 参数")
    from app.models.user import User
    from sqlalchemy import select
    from app.schemas.tutor import TutorChatRequest
    from app.services.grounded_qa_pipeline import GroundedQaPipeline

    user = (await self.db.execute(select(User).where(User.id == context.user_id))).scalar_one()
    response = await GroundedQaPipeline(self.db).answer(
        TutorChatRequest.model_validate({"course_id": context.course_id, **context.params}),
        user,
    )
    return self.success_result(
        data=response.model_dump(mode="json"),
        message="问答完成",
        evidence=response.citations,
    )
```

Keep the compatibility formatting helpers covered by existing tests until all callers are migrated.

- [ ] **Step 7: Run pipeline and Tutor tests**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_grounded_qa_pipeline.py backend/tests/test_tutor.py -q`

Expected: PASS; the fake provider records exactly one `chat` call.

- [ ] **Step 8: Commit the shared non-streaming core**

```powershell
git add backend/app/services/grounded_qa_pipeline.py backend/app/services/prompt_service.py backend/app/services/personalization_context_service.py backend/app/schemas/tutor.py backend/app/agents/tutor_agent.py backend/tests/test_grounded_qa_pipeline.py backend/tests/test_tutor.py
git commit -m "feat: add single-call grounded qa pipeline"
```

### Task 4: Streaming, conversation persistence, and asynchronous postprocessing

**Files:**
- Modify: `backend/app/services/grounded_qa_pipeline.py`
- Modify: `backend/app/services/tutor_service.py`
- Modify: `backend/app/services/chat_knowledge_pipeline.py`
- Create: `backend/app/services/tutor_postprocess_service.py`
- Modify: `backend/app/core/event_handlers.py`
- Modify: `backend/tests/test_grounded_qa_pipeline.py`
- Modify: `backend/tests/test_tutor.py`

**Interfaces:**
- Consumes: `GroundedQaPipeline.answer()`, `AgentConversationRepository.add_message()`, `LearningRecordService.record_event(commit=False)`, and `publish_chat_completed()`.
- Produces: `GroundedQaPipeline.stream(payload, current_user, persist_conversation_messages=True) -> AsyncIterator[dict[str, Any]]`; persisted user/assistant messages; assistant payload key `learning_record_id`; non-blocking `postprocess_status`.

- [ ] **Step 1: Add failing SSE order and persistence-failure tests**

```python
@pytest.mark.asyncio
async def test_stream_orders_evidence_before_delta_and_done(monkeypatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.rag.evidence import EvidenceBundle, EvidenceItem, GraphContext
    from app.schemas.tutor import TutorChatRequest, TutorChatResponse, TutorPerformance
    from app.services.grounded_qa_pipeline import GroundedQaPipeline

    class FakeStreamProvider:
        provider_name = "mock"
        async def stream_chat(self, messages, **kwargs):
            yield "栈遵循"
            yield "后进先出 [S1]。"

    evidence = EvidenceItem(
        citation_key="S1", source_type="document", source_id=uuid4(), chunk_id=uuid4(),
        title="数据结构讲义", quote="栈遵循后进先出原则。", confidence="strong",
    )
    bundle = EvidenceBundle([evidence], GraphContext(), 1)
    request = TutorChatRequest(course_id=uuid4(), question="什么是栈？")
    user = SimpleNamespace(id=uuid4(), role="student")
    db = SimpleNamespace(rollback=AsyncMock())
    pipeline = GroundedQaPipeline(db=db)  # type: ignore[arg-type]
    pipeline._authorize = AsyncMock(return_value=SimpleNamespace(id=request.course_id))
    pipeline._retrieve = AsyncMock(return_value=bundle)
    pipeline._build_generation = AsyncMock(return_value=(FakeStreamProvider(), "prompt", None))
    pipeline._complete_and_persist = AsyncMock(return_value=TutorChatResponse(
        answer="栈遵循后进先出 [S1]。",
        citations=[evidence.as_citation()],
        grounding_status="grounded",
        grounding_message="回答已绑定 1 条课程依据。",
        performance=TutorPerformance(llm_call_count=1),
    ))

    events = [event async for event in pipeline.stream(request, user)]
    names = [event["event"] for event in events]
    assert names.index("evidence") < names.index("delta") < names.index("done")
    assert events[-1]["data"]["performance"]["llm_call_count"] == 1


@pytest.mark.asyncio
async def test_persistence_failure_keeps_answer_and_skips_postprocess() -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.schemas.tutor import TutorChatRequest, TutorChatResponse
    from app.services.grounded_qa_pipeline import GroundedQaPipeline

    request = TutorChatRequest(course_id=uuid4(), question="什么是栈？")
    user = SimpleNamespace(id=uuid4(), role="student")
    expected = TutorChatResponse(answer="栈遵循后进先出原则。")
    pipeline = GroundedQaPipeline(db=None)  # type: ignore[arg-type]
    pipeline._persist = AsyncMock(side_effect=RuntimeError("database unavailable"))
    pipeline._publish_postprocess = AsyncMock()
    pipeline._answer_without_persistence = AsyncMock(return_value=(
        expected, SimpleNamespace(id=request.course_id)
    ))

    result = await pipeline.answer(request, user)

    assert result.answer
    assert result.message_id is None
    assert result.postprocess_status == "skipped"
    pipeline._publish_postprocess.assert_not_awaited()
```

`answer()` must call `_answer_without_persistence()` for generation and `_safe_persist()` for storage, so the second test exercises the public behavior without a database.

- [ ] **Step 2: Run the tests and confirm stream/persistence failures**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_grounded_qa_pipeline.py backend/tests/test_tutor.py -q`

Expected: FAIL because `stream()` and completed persistence are not implemented.

- [ ] **Step 3: Implement streaming with performance timestamps**

Add:

```python
async def stream(
    self,
    payload: TutorChatRequest,
    current_user: User,
    *,
    persist_conversation_messages: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    started = perf_counter()
    yield {"event": "progress", "data": {"stage": "retrieve_context", "message": "正在检索课程依据"}}
    course = await self._authorize(payload, current_user)
    retrieval_started = perf_counter()
    bundle = await self._retrieve(payload, current_user)
    retrieval_ms = int((perf_counter() - retrieval_started) * 1000)
    yield {"event": "evidence", "data": self._evidence_event(bundle)}
    yield {"event": "progress", "data": {"stage": "llm_generation", "message": "正在基于课程依据生成回答"}}
    provider, prompt, prompt_version_id = await self._build_generation(bundle, payload, current_user)
    chunks: list[str] = []
    first_token_ms: int | None = None
    generation_started = perf_counter()
    async for chunk in provider.stream_chat(
        [ChatMessage(role="user", content=prompt)], temperature=0.2, max_tokens=1200,
        thinking={"type": "disabled"}, prompt_version_id=prompt_version_id,
    ):
        if not chunk:
            continue
        if first_token_ms is None:
            first_token_ms = int((perf_counter() - started) * 1000)
        chunks.append(chunk)
        yield {"event": "delta", "data": {"content": chunk}}
    yield {"event": "progress", "data": {"stage": "validate_citations", "message": "正在核验引用"}}
    response = await self._complete_and_persist(
        answer="".join(chunks), bundle=bundle, payload=payload, current_user=current_user,
        course=course, provider=provider, retrieval_ms=retrieval_ms,
        first_token_ms=first_token_ms,
        generation_ms=int((perf_counter() - generation_started) * 1000),
        total_ms=int((perf_counter() - started) * 1000),
        persist_conversation_messages=persist_conversation_messages,
    )
    yield {"event": "done", "data": response.model_dump(mode="json")}
```

Use the same `_complete_and_persist()` from non-streaming `answer()` so validation and persistence behavior cannot diverge.

Refactor `answer()` to call `_answer_without_persistence(payload, current_user) -> tuple[TutorChatResponse, Course]`, then `_safe_persist()`. Implement the failure boundary exactly as:

```python
async def _safe_persist(
    self,
    *,
    response: TutorChatResponse,
    payload: TutorChatRequest,
    current_user: User,
    course: Course,
    persist_conversation_messages: bool,
) -> tuple[UUID | None, UUID | None]:
    try:
        return await self._persist(
            response=response,
            payload=payload,
            current_user=current_user,
            course=course,
            persist_conversation_messages=persist_conversation_messages,
        )
    except Exception:
        await self.db.rollback()
        return None, payload.conversation_id
```

The completed response is returned even when this method returns `(None, payload.conversation_id)`; in that branch set `postprocess_status="skipped"` and do not publish an event.

- [ ] **Step 4: Persist learning record and conversation atomically**

`_persist()` must:

1. Resolve `payload.conversation_id` with `AgentConversationRepository.get_for_user`; create a conversation when absent and `persist_conversation_messages=True`.
2. Add the user message and assistant message only when `persist_conversation_messages=True`; Agent mode already owns both conversation messages.
3. Create the `learning_records` chat event with `commit=False`.
4. When conversation persistence is enabled, add an assistant `agent_message` with `message_type="tutor"` and payload containing `learning_record_id`, `citations`, `related_knowledge_points`, `follow_up_questions`, `grounding_status`, `grounding_message`, `performance`, and provider fallback fields.
5. Commit once, refresh the record and conversation, then return `(record.id, conversation.id)`.
6. On any persistence exception, call `await self.db.rollback()` and return `(None, payload.conversation_id)`.

After a successful commit, call:

```python
await publish_chat_completed(
    user_id=current_user.id,
    course_id=course.id,
    question=payload.question,
    answer=response.answer,
    citations=[item.model_dump(mode="json") for item in response.citations],
    knowledge_id=payload.knowledge_id,
    message_id=str(response.message_id) if response.message_id else None,
    extract_result=None,
    source="grounded_qa_pipeline",
)
```

Set `postprocess_status="queued"` only when persistence succeeded. Remove synchronous `extract_knowledge_from_dialogue()` calls from Tutor chat paths; EventBus handlers continue using their own `AsyncSessionLocal` session.

- [ ] **Step 5: Add asynchronous deep Review and memory processing**

Create `TutorPostprocessService` with:

```python
class TutorPostprocessService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run(self, event: Event) -> None:
        user_id = UUID(str(event.data["user_id"]))
        course_id = UUID(str(event.data["course_id"]))
        answer = str(event.data.get("answer") or "")
        citations = list(event.data.get("citations") or [])
        review = await AgentService(self.db).run_task(
            task_type="review_content",
            user_id=user_id,
            course_id=course_id,
            params={"content": str({"answer": answer, "citations": citations})[:4000]},
        )
        await MemoryService(self.db).reflect(user_id, course_id)
        await self.db.commit()
```

Include validated citations in `publish_chat_completed()` event data. In `on_chat_completed`, run `TutorPostprocessService` in its own `AsyncSessionLocal` block after the existing mastery/profile work and before graph extraction. Each existing handler boundary already catches and logs exceptions, so Review or memory failure cannot alter the returned Tutor answer.

Extend `publish_chat_completed()` with `citations: list[dict[str, Any]] | None = None` and store `"citations": citations or []` in the event payload.

- [ ] **Step 6: Make TutorService a thin chat delegate**

Replace only `chat()` and `stream_chat()` bodies:

```python
async def chat(self, *, payload: TutorChatRequest, current_user: User) -> TutorChatResponse:
    return await GroundedQaPipeline(self.db).answer(payload, current_user)

async def stream_chat(
    self, *, payload: TutorChatRequest, current_user: User
) -> AsyncIterator[dict[str, Any]]:
    async for event in GroundedQaPipeline(self.db).stream(payload, current_user):
        yield event
```

Retain `save_answer_to_wiki()`, `submit_feedback()`, authorization helpers, and citation formatting. Remove now-unused synchronous Review/knowledge-extraction imports from this service.

- [ ] **Step 7: Run backend streaming tests**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_grounded_qa_pipeline.py backend/tests/test_tutor.py -q`

Expected: PASS; event order is fixed, database failure preserves answer, and EventBus publication is not awaited before the persistence commit.

- [ ] **Step 8: Commit stream and persistence**

```powershell
git add backend/app/services/grounded_qa_pipeline.py backend/app/services/tutor_service.py backend/app/services/chat_knowledge_pipeline.py backend/app/services/tutor_postprocess_service.py backend/app/core/event_handlers.py backend/tests/test_grounded_qa_pipeline.py backend/tests/test_tutor.py
git commit -m "feat: stream and persist grounded tutor answers"
```

### Task 5: Agent reuse and deterministic pass-through completion

**Files:**
- Modify: `backend/app/agent_runtime/tools.py`
- Modify: `backend/app/agent_runtime/service_tools.py`
- Modify: `backend/app/agent_runtime/graph.py`
- Modify: `backend/app/agent_runtime/supervisor_intents.py`
- Modify: `backend/app/services/agent_runtime_service.py`
- Modify: `backend/tests/test_agent_runtime.py`

**Interfaces:**
- Consumes: `GroundedQaPipeline.answer(payload, current_user, persist_conversation_messages=False)` and `ToolContext.conversation_id`.
- Produces: `ToolExecutionResult.final_answer: str | None`; successful `answer_course_question` can route directly from observation to finalize when no tool remains.

- [ ] **Step 1: Add failing no-duplicate-search and pass-through tests**

```python
def test_explicit_course_source_qa_plans_only_grounded_answer() -> None:
    from app.agent_runtime.supervisor_intents import plan_required_tools

    assert plan_required_tools("基于课程资料解释栈并给出引用", is_profile_update_only=False) == [
        "answer_course_question"
    ]


@pytest.mark.asyncio
async def test_answer_tool_final_answer_bypasses_second_supervisor_call() -> None:
    async def async_result(value):
        return value

    class OneDecisionSupervisor:
        def __init__(self) -> None:
            self.calls = 0

        async def decide(self, state, tool_schemas):
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("grounded answer must not be summarized again")
            return AgentDecision(
                status="continue",
                summary="调用共享问答内核",
                plan=["回答课程问题"],
                tool_calls=[PlannedToolCall(
                    id="qa-1", name="answer_course_question", arguments={"question": "解释栈"}
                )],
            )

    supervisor = OneDecisionSupervisor()
    registry = ToolRegistry()
    registry.register(AgentTool(
        name="answer_course_question", description="答疑", agent_name="TutorAgent",
        input_schema={"type": "object", "properties": {}},
        handler=lambda context, arguments: async_result(ToolExecutionResult(
            output={"answer": "栈是 LIFO [S1]。"}, final_answer="栈是 LIFO [S1]。",
            citations=[{"citation_key": "S1"}],
        )),
    ))
    result = await LearningAgentGraph(registry=registry, supervisor=supervisor).run(
        task_id=uuid4(), conversation_id=uuid4(), user_id=uuid4(), course_id=uuid4(),
        goal="解释栈", thread_id="grounded-pass-through",
    )
    assert result["final_answer"] == "栈是 LIFO [S1]。"
    assert supervisor.calls == 1


def test_agent_runtime_no_longer_extracts_dialogue_synchronously() -> None:
    source = Path("backend/app/services/agent_runtime_service.py").read_text(encoding="utf-8")
    assert "extract_knowledge_from_dialogue(" not in source
```

- [ ] **Step 2: Run Agent tests and confirm failures**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_agent_runtime.py -q`

Expected: FAIL because the intent planner inserts `search_course_knowledge`, `ToolExecutionResult` lacks `final_answer`, and the graph calls Supervisor again.

- [ ] **Step 3: Add the pass-through field and use the shared pipeline**

Add to `ToolExecutionResult`:

```python
final_answer: str | None = None
```

Replace the `answer_question` handler with:

```python
async def answer_question(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
    from app.schemas.tutor import TutorChatRequest
    from app.services.grounded_qa_pipeline import GroundedQaPipeline

    result = await GroundedQaPipeline(db).answer(
        TutorChatRequest(
            course_id=context.course_id,
            conversation_id=context.conversation_id,
            question=str(arguments["question"]),
            top_k=int(arguments.get("top_k") or 5),
        ),
        current_user,
        persist_conversation_messages=False,
    )
    data = result.model_dump(mode="json")
    return ToolExecutionResult(
        output=data,
        evidence=data.get("citations") or [],
        citations=data.get("citations") or [],
        final_answer=result.answer,
        artifact_refs=[{"type": "tutor_answer", "id": str(result.message_id)}] if result.message_id else [],
    )
```

- [ ] **Step 4: Route successful terminal Tutor results directly to finalize**

Include `final_answer` in `last_tool_result`. In `_observe()`, copy it into state only when successful. Extend the observation routing map with `"finalize": "finalize"` and replace `_route_observation()` with:

```python
def _route_observation(self, state: AgentState) -> str:
    result = state.get("last_tool_result", {})
    if state.get("pending_tool_calls") and result.get("success"):
        return "execute_tool"
    if result.get("success") and result.get("final_answer"):
        return "finalize"
    return "supervisor"
```

This cannot finalize a multi-deliverable plan early because the first branch keeps executing every pending tool before considering `final_answer`.

- [ ] **Step 5: Make explicit-source QA use the self-retrieving answer tool**

In `supervisor_intents.plan_required_tools()`, replace the explicit search insertion with:

```python
if search_explicit_intent(goal) and not tools:
    tools.append("answer_course_question")
elif search_explicit_intent(goal) and tools == ["search_course_knowledge"]:
    tools = ["answer_course_question"]
```

In `MiMoSupervisor._requires_explicit_retrieval()`, treat a completed `answer_course_question` as satisfying the retrieval requirement. Keep standalone `search_course_knowledge` available for explicit search-only Agent tasks.

- [ ] **Step 6: Preserve pass-through results across retries and remove synchronous Agent extraction**

In `AgentRuntimeService._save_tool_result()`, store `result.final_answer` under `_final_answer`; in `_load_tool_result()`, pop that key and pass it to `ToolExecutionResult(final_answer=final_answer)`. In `_record_event()`, remove the call to `_attach_knowledge_extract()` for completed events and delete that synchronous helper.

After `_finish_task()` commits, call `publish_chat_completed()` only when the completed result has no successful `answer_course_question` observation, because Grounded QA already queued its event. For the successful Tutor observation, copy `output.message_id`, grounding fields, follow-ups and related knowledge into the outer Agent assistant-message payload so the learning record remains traceable without creating a duplicate assistant message.

Use this extractor:

```python
def _grounded_qa_output(self, result: dict[str, Any]) -> dict[str, Any]:
    for observation in reversed(result.get("observations") or []):
        if observation.get("success") and observation.get("tool_name") == "answer_course_question":
            return dict(observation.get("output") or {})
    return {}
```

When this returns data, `_finish_task()` adds `learning_record_id=qa_output.get("message_id")`, `grounding_status`, `grounding_message`, `follow_up_questions`, and `related_knowledge_points` to its existing payload. It does not add another conversation message inside Grounded QA because `persist_conversation_messages=False` was passed by the tool.

- [ ] **Step 7: Run Agent runtime tests**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_agent_runtime.py backend/tests/test_agent_answer_text.py -q`

Expected: PASS; pure Agent QA uses one Supervisor decision, one Grounded QA model call, and no second summary call.

- [ ] **Step 8: Commit Agent reuse**

```powershell
git add backend/app/agent_runtime/tools.py backend/app/agent_runtime/service_tools.py backend/app/agent_runtime/graph.py backend/app/agent_runtime/supervisor_intents.py backend/app/services/agent_runtime_service.py backend/tests/test_agent_runtime.py
git commit -m "perf: reuse grounded qa in agent answers"
```

### Task 6: Safe Tutor SSE client and the single stream hook

**Files:**
- Modify: `frontend/types/tutor.ts`
- Modify: `frontend/services/tutorService.ts`
- Rewrite: `frontend/hooks/useTutorStream.ts`
- Create: `frontend/scripts/tutor-stream-policy.test.mjs`
- Modify: `scripts/check-assistant-ui.mjs`

**Interfaces:**
- Consumes: Tutor `progress`, `evidence`, `delta`, `done`, `error` SSE events.
- Produces: `TutorStreamSnapshot`, multi-request `useTutorStream({ onSnapshot })`, `start(requestId, payload)`, `stop(requestId)`, `stopAll()`; synchronous fallback only before the first delta.

- [ ] **Step 1: Add failing source-contract tests for the fallback boundary**

```javascript
import assert from "node:assert/strict"
import fs from "node:fs"

const service = fs.readFileSync(new URL("../services/tutorService.ts", import.meta.url), "utf8")
const hook = fs.readFileSync(new URL("../hooks/useTutorStream.ts", import.meta.url), "utf8")
const page = fs.readFileSync(new URL("../components/assistant/AssistantPageClient.tsx", import.meta.url), "utf8")

assert.match(service, /let receivedDelta = false/)
assert.match(service, /if \(!receivedDelta\)/)
assert.match(service, /onInterrupted/)
assert.match(service, /eventName === "evidence"/)
assert.match(hook, /Record<string, TutorStreamSnapshot>/)
assert.match(hook, /const stopAll = useCallback/)
assert.doesNotMatch(page, /import \{ streamTutorChat \}/)
assert.match(page, /useTutorStream/)

console.log("tutor stream policy assertions passed")
```

- [ ] **Step 2: Run the contract test and confirm failure**

Run: `node frontend/scripts/tutor-stream-policy.test.mjs`

Expected: FAIL on the missing `receivedDelta`, `evidence`, and hook-owned controller assertions.

- [ ] **Step 3: Mirror the backend Tutor types**

Add `citation_key`, `knowledge_id`, `retrieval_mode`, and `confidence` to `TutorCitation`; add `TutorPerformance`; add `conversation_id`, `grounding_status`, `grounding_message`, `performance`, `postprocess_status`, provider fallback fields, and `knowledge_extract`/`graph_context` to `TutorChatResponse`. Add optional `conversation_id` to `TutorChatRequest`.

- [ ] **Step 4: Enforce fallback-before-first-token in the service**

Extend handlers:

```typescript
export type TutorStreamHandlers = {
  onOpen?: () => void
  onClose?: () => void
  onProgress?: (data: { stage?: string; message?: string }) => void
  onEvidence?: (data: Pick<TutorChatResponse, "grounding_status" | "grounding_message" | "citations">) => void
  onDelta?: (content: string) => void
  onDone?: (data: TutorChatResponse) => void
  onInterrupted?: (error: Error) => void
  signal?: AbortSignal
}
```

Inside `streamTutorChat`, initialize `let receivedDelta = false`; set it before invoking `onDelta`; handle `evidence`; in `catch`, return partial/null after `handlers.onInterrupted(error)` when `receivedDelta` is true; call `chatWithTutor()` only when `receivedDelta` is false and the request was not aborted. Do not append the fallback answer as a delta before `onDone`, because `onDone` owns final replacement.

- [ ] **Step 5: Make `useTutorStream` own every Tutor request**

Use these exact public types:

```typescript
export type TutorStreamStatus = "retrieving" | "generating" | "validating" | "completed" | "interrupted" | "failed"

export interface TutorStreamSnapshot {
  requestId: string
  status: TutorStreamStatus
  progress: string
  answer: string
  result: TutorChatResponse | null
  error: string | null
}

export function useTutorStream({
  onSnapshot,
}: {
  onSnapshot: (snapshot: TutorStreamSnapshot) => void
}) {
  const controllersRef = useRef(new Map<string, AbortController>())
  const [streams, setStreams] = useState<Record<string, TutorStreamSnapshot>>({})
  // start() registers one controller, translates every handler into a snapshot,
  // and removes the controller in finally.
  // stop() aborts one controller while retaining its accumulated answer.
  // stopAll() aborts every controller and clears the map.
  return { streams, start, stop, stopAll }
}
```

Implement the three described callbacks in the same file with `useCallback`; the comment lines above are implementation invariants, not deferred work.

- [ ] **Step 6: Replace direct page-level SSE calls**

`AssistantPageClient` must import `useTutorStream`, create it once, map snapshots to the matching Tutor `ChatItem`, call `start(tutorId, payload)`, and route the stop button to `stopAll()`. Remove the page-owned Tutor controller map, `activeTutorId`, and direct `streamTutorChat` import.

- [ ] **Step 7: Run client contract and type checks**

Run: `node frontend/scripts/tutor-stream-policy.test.mjs`

Run: `node scripts/check-assistant-ui.mjs`

Run: `& 'C:\Users\28744\Desktop\zhixue\frontend\node_modules\.bin\tsc.cmd' --noEmit -p frontend/tsconfig.json`

Expected: both Node scripts PASS and TypeScript exits 0.

- [ ] **Step 8: Commit the stream state machine**

```powershell
git add frontend/types/tutor.ts frontend/services/tutorService.ts frontend/hooks/useTutorStream.ts frontend/components/assistant/AssistantPageClient.tsx frontend/scripts/tutor-stream-policy.test.mjs scripts/check-assistant-ui.mjs
git commit -m "fix: prevent duplicate tutor stream fallback"
```

### Task 7: Grounding UI, feedback, Wiki save, follow-ups, and history restoration

**Files:**
- Create: `frontend/components/assistant/TutorEvidencePanel.tsx`
- Modify: `frontend/components/assistant/ReplyBlocks.tsx`
- Modify: `frontend/components/assistant/AssistantPageClient.tsx`
- Create: `frontend/scripts/tutor-evidence-ui.test.mjs`

**Interfaces:**
- Consumes: completed `TutorChatResponse`, `learning_record_id` in historical `AgentMessage.payload`, selected `wikiPageId`.
- Produces: visible grounding badge, expandable citations, related knowledge points, follow-up chips, feedback and save actions using the real learning-record ID.

- [ ] **Step 1: Add failing UI contract tests**

```javascript
import assert from "node:assert/strict"
import fs from "node:fs"

const panel = fs.readFileSync(new URL("../components/assistant/TutorEvidencePanel.tsx", import.meta.url), "utf8")
const page = fs.readFileSync(new URL("../components/assistant/AssistantPageClient.tsx", import.meta.url), "utf8")

for (const token of ["grounding_status", "课程依据不足", "citation.quote", "follow_up_questions", "submitTutorFeedback", "saveTutorAnswerToWiki"]) {
  assert.match(panel, new RegExp(token))
}
assert.match(page, /learning_record_id/)
assert.match(page, /related_knowledge_points/)
assert.match(page, /follow_up_questions/)

console.log("tutor evidence UI assertions passed")
```

- [ ] **Step 2: Run the UI contract test and confirm failure**

Run: `node frontend/scripts/tutor-evidence-ui.test.mjs`

Expected: FAIL because `TutorEvidencePanel.tsx` does not exist.

- [ ] **Step 3: Build the evidence/action panel**

Define:

```typescript
interface TutorEvidencePanelProps {
  response: TutorChatResponse
  wikiPageId: string | null
  onFollowUp: (question: string) => void
}
```

The component must render:

- `grounded`: “基于 N 条课程资料”；`partial`: “部分绑定来源”；`insufficient`: “课程依据不足”。
- A native `<details>` list containing title, page number, quote, retrieval mode, and confidence for each citation.
- Related knowledge point chips and follow-up question buttons.
- “有用”“无用” buttons calling `submitTutorFeedback(response.message_id, { feedback_type: "useful", rating: 5 })` or `submitTutorFeedback(response.message_id, { feedback_type: "useless", rating: 1 })`.
- “保存到 Wiki” calling `saveTutorAnswerToWiki(response.message_id, { wiki_page_id: wikiPageId })`.
- Disabled action copy when `message_id` is null, and explicit provider fallback/record-save warnings.
- “演示模式（Mock Provider）” when `response.provider` or `response.model` contains `mock`, so demo data is never presented as a real-model result.

Use local `actionPending`/`actionMessage` state to prevent duplicate feedback/save submissions; errors must render inline and may also use `toast.error`.

- [ ] **Step 4: Pass complete result data through TutorReplyBlock**

Extend props:

```typescript
interface TutorReplyBlockProps {
  content: string
  progress?: string
  streaming: boolean
  error?: string | null
  result?: TutorChatResponse | null
  wikiPageId?: string | null
  onFollowUp?: (question: string) => void
  onOpenDetail?: () => void
}
```

Render `TutorEvidencePanel` under the Markdown body only when `!streaming && result`; retain partial content and an inline interruption message when `error` is present.

- [ ] **Step 5: Restore complete Tutor payload from conversation history**

Extend Tutor `ChatItem` with `result?: TutorChatResponse | null`. In `messagesFromHistory`, build `result` from `m.payload`, use `m.payload.learning_record_id` as `message_id`, and never use `AgentMessage.id` for feedback/save. On `done`, store the complete response in the item. Follow-up chips must set the input and immediately call the same fast-path sender with that question.

- [ ] **Step 6: Run UI contracts and TypeScript**

Run: `node frontend/scripts/tutor-evidence-ui.test.mjs`

Run: `node frontend/scripts/assistant-send-stop-button.test.mjs`

Run: `& 'C:\Users\28744\Desktop\zhixue\frontend\node_modules\.bin\tsc.cmd' --noEmit -p frontend/tsconfig.json`

Expected: both Node tests PASS and TypeScript exits 0.

- [ ] **Step 7: Commit grounded answer UI**

```powershell
git add frontend/components/assistant/TutorEvidencePanel.tsx frontend/components/assistant/ReplyBlocks.tsx frontend/components/assistant/AssistantPageClient.tsx frontend/scripts/tutor-evidence-ui.test.mjs
git commit -m "feat: show tutor evidence and answer actions"
```

### Task 8: Responsive resource drawer and explicit service states

**Files:**
- Create: `frontend/components/assistant/ResourcePanelDialog.tsx`
- Modify: `frontend/components/assistant/ResourceSidePanel.tsx`
- Modify: `frontend/components/assistant/AssistantPageClient.tsx`
- Create: `frontend/scripts/assistant-responsive-layout.test.mjs`

**Interfaces:**
- Consumes: existing `ResourceSidePanel` props and course-loading state.
- Produces: desktop panel at `xl`, side/bottom dialog below `xl`, persistent chat height, and visible states for unauthenticated/backend-unavailable/no-course conditions.

- [ ] **Step 1: Add failing responsive source-contract tests**

```javascript
import assert from "node:assert/strict"
import fs from "node:fs"

const page = fs.readFileSync(new URL("../components/assistant/AssistantPageClient.tsx", import.meta.url), "utf8")
const panel = fs.readFileSync(new URL("../components/assistant/ResourceSidePanel.tsx", import.meta.url), "utf8")
const dialog = fs.readFileSync(new URL("../components/assistant/ResourcePanelDialog.tsx", import.meta.url), "utf8")

assert.match(page, /hidden xl:block/)
assert.match(page, /xl:hidden/)
assert.match(page, /ResourcePanelDialog/)
assert.match(page, /课程加载失败/)
assert.doesNotMatch(panel, /h-full w-full lg:w-\[360px\]/)
assert.match(dialog, /max-xl:bottom-0/)
assert.match(dialog, /md:right-0/)

console.log("assistant responsive layout assertions passed")
```

- [ ] **Step 2: Run the layout contract and confirm failure**

Run: `node frontend/scripts/assistant-responsive-layout.test.mjs`

Expected: FAIL because the dialog does not exist and the old `h-full` panel contract remains.

- [ ] **Step 3: Make ResourceSidePanel embeddable**

Add `className?: string` to its props and use:

```tsx
<aside className={cn(
  "glass-card flex min-h-0 w-full flex-col overflow-hidden rounded-3xl",
  className,
)}>
```

Import `cn` from `@/lib/utils`. Desktop sizing becomes a caller concern.

- [ ] **Step 4: Add a Radix-backed responsive resource dialog**

`ResourcePanelDialog` must accept `open`, `onOpenChange`, and the existing resource props. Render `DialogContent` with `max-xl:bottom-0 max-xl:left-0 max-xl:top-auto max-xl:w-full max-xl:max-w-none max-xl:translate-x-0 max-xl:translate-y-0 max-xl:rounded-b-none md:bottom-4 md:left-auto md:right-4 md:top-4 md:w-[420px] md:translate-x-0 md:translate-y-0`, and render `ResourceSidePanel className="h-[min(76dvh,720px)] md:h-full"`.

- [ ] **Step 5: Keep chat primary at all breakpoints**

In `AssistantPageClient`:

```tsx
<div className="mx-auto flex h-[calc(100dvh-7rem)] max-w-[1540px] gap-4">
  <section className="glass-card flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-3xl">
    {/* existing chat controls, messages, and composer */}
  </section>
  <div className="hidden h-full w-[360px] shrink-0 xl:block">
    <ResourceSidePanel
      className="h-full"
      courseId={courseId}
      wikiPageId={wikiPageId || null}
      refreshSignal={resourceRefreshSignal}
      highlightResourceType={resourceRevealType}
    />
  </div>
</div>
```

Add an `xl:hidden` resource button in the chat header and mount `ResourcePanelDialog`. Track course load as `"loading" | "ready" | "unauthenticated" | "unavailable" | "empty"`; render an inline card with retry for failure states and disable the composer unless state is `ready`.

- [ ] **Step 6: Run layout, UI, and type checks**

Run: `node frontend/scripts/assistant-responsive-layout.test.mjs`

Run: `node scripts/check-assistant-ui.mjs`

Run: `& 'C:\Users\28744\Desktop\zhixue\frontend\node_modules\.bin\tsc.cmd' --noEmit -p frontend/tsconfig.json`

Expected: Node scripts PASS and TypeScript exits 0.

- [ ] **Step 7: Commit responsive layout**

```powershell
git add frontend/components/assistant/ResourcePanelDialog.tsx frontend/components/assistant/ResourceSidePanel.tsx frontend/components/assistant/AssistantPageClient.tsx frontend/scripts/assistant-responsive-layout.test.mjs
git commit -m "fix: keep assistant chat visible on narrow screens"
```

### Task 9: Honest RAG evaluation metrics and acceptance documentation

**Files:**
- Create: `backend/tests/test_public_kb_evaluation.py`
- Modify: `scripts/evaluate_public_kb.py`
- Modify: `data/seed_knowledge/data_structure/eval/standard_questions.yml`
- Modify: `docs/当前实现基线.md`
- Modify: `docs/当前实现API清单.md`
- Modify: `docs/功能完成度与待完善清单.md`
- Create in `docs/19_测试方案`: `23_Grounded_QA双通道验收记录.md`

**Interfaces:**
- Consumes: evaluation rows with ranked source IDs, answer citations, `answerable`, optional manual correctness label, and refusal status.
- Produces: `recall_at_5`, `mrr`, `citation_precision`, `unanswerable_refusal_rate`, and nullable `answer_correctness`; generated implementation docs and a factual acceptance record.

- [ ] **Step 1: Add failing metric-separation tests**

```python
from scripts.evaluate_public_kb import calculate_metrics


def test_metrics_do_not_infer_answer_correctness_from_retrieval_hit() -> None:
    metrics = calculate_metrics([
        {
            "answerable": True,
            "expected_sources": ["source-a"],
            "retrieved_source_ids": ["source-a", "source-b"],
            "cited_source_ids": ["source-b"],
            "answer_correct": None,
            "refused": False,
            "llm_evaluated": True,
        },
        {
            "answerable": False,
            "expected_sources": [],
            "retrieved_source_ids": [],
            "cited_source_ids": [],
            "answer_correct": True,
            "refused": True,
            "llm_evaluated": True,
        },
    ])

    assert metrics["recall_at_5"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["citation_precision"] == 0.0
    assert metrics["unanswerable_refusal_rate"] == 1.0
    assert metrics["answer_correctness"] == 1.0
    assert metrics["manually_scored_answers"] == 1
```

- [ ] **Step 2: Run the evaluator test and confirm key mismatch failure**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_public_kb_evaluation.py -q`

Expected: FAIL because current metrics expose `retrieval_recall` and derive `answer_accuracy` from `answer_grounded`.

- [ ] **Step 3: Implement independent metrics**

`calculate_metrics()` must:

- Compute Recall@5 only over `answerable=True` rows from expected sources found in the first five retrieved source IDs.
- Compute reciprocal rank only over `answerable=True` rows from the first expected source in the first five retrieved source IDs.
- Compute citation precision only across `llm_evaluated=True` rows as valid cited expected sources divided by all cited sources; when evaluated answers exist but none cites a source, return `0.0`.
- Compute refusal rate only across `llm_evaluated=True` and `answerable=False` rows.
- Compute answer correctness only across rows whose `answer_correct` is a boolean; return `None` and count zero when no manual/independent label exists.

Return exactly:

```python
{
    "question_count": question_count,
    "answerable_questions": answerable_count,
    "recall_at_5": round(recall_hits / answerable_count, 4) if answerable_count else None,
    "mrr": round(reciprocal_rank_sum / answerable_count, 4) if answerable_count else None,
    "citation_precision": (
        round(valid_citations / cited_count, 4)
        if cited_count else (0.0 if llm_evaluated_count else None)
    ),
    "unanswerable_refusal_rate": round(refusals / unanswerable_count, 4) if unanswerable_count else None,
    "answer_correctness": round(correct / scored_count, 4) if scored_count else None,
    "llm_evaluated_answers": llm_evaluated_count,
    "manually_scored_answers": scored_count,
}
```

- [ ] **Step 4: Tighten the evaluation cases**

Add `answerable: true` and `expected_evidence_terms` to every existing question. Use this exact question-to-term mapping so a broad source ID alone cannot make an evidence citation valid:

```python
{
    "数据结构和算法之间是什么关系？": ["数据结构", "算法"],
    "什么是抽象数据类型 ADT？": ["抽象数据类型", "ADT"],
    "如何区分逻辑结构和存储结构？": ["逻辑结构", "存储结构"],
    "时间复杂度 O(n) 和 O(log n) 的直观差异是什么？": ["O(n)", "O(log n)"],
    "递归算法的复杂度如何分析？": ["递归", "复杂度"],
    "顺序表为什么支持随机访问？": ["顺序表", "随机访问"],
    "链表插入删除为什么通常不需要移动大量元素？": ["链表", "插入", "删除"],
    "单链表删除结点时最容易出错的边界条件有哪些？": ["单链表", "删除", "边界"],
    "栈为什么适合括号匹配？": ["栈", "括号匹配"],
    "递归和调用栈之间有什么关系？": ["递归", "调用栈"],
    "循环队列如何判断队空和队满？": ["循环队列", "队空", "队满"],
    "BFS 为什么通常使用队列？": ["BFS", "队列"],
    "DFS 为什么可以用递归实现？": ["DFS", "递归"],
    "二叉树的前序、中序、后序遍历有什么区别？": ["前序", "中序", "后序"],
    "完全二叉树为什么适合数组存储？": ["完全二叉树", "数组"],
    "堆和二叉排序树有什么区别？": ["堆", "二叉排序树"],
    "哈希表平均 O(1) 查找依赖哪些前提？": ["哈希表", "O(1)"],
    "装填因子过高会带来什么问题？": ["装填因子", "冲突"],
    "邻接矩阵和邻接表各自适合什么图？": ["邻接矩阵", "邻接表"],
    "BFS 可以解决哪类最短路径问题？": ["BFS", "最短路径"],
    "Dijkstra 算法为什么要求边权非负？": ["Dijkstra", "非负"],
    "Floyd 算法适合解决什么问题？": ["Floyd", "最短路径"],
    "并查集的路径压缩在优化什么？": ["并查集", "路径压缩"],
    "快速排序最坏情况如何出现？": ["快速排序", "最坏"],
    "排序稳定性是什么意思？": ["排序", "稳定性"],
    "归并排序为什么需要额外空间？": ["归并排序", "额外空间"],
    "折半查找为什么要求数据有序？": ["折半查找", "有序"],
    "二叉排序树退化后复杂度会怎样？": ["二叉排序树", "退化", "复杂度"],
    "B 树和 B+ 树为什么适合外存索引？": ["B 树", "B+ 树", "外存"],
    "如何为 LRU 缓存选择合适的数据结构？": ["LRU", "哈希", "链表"],
}
```

Append these exact unanswerable/interference cases:

```yaml
  - question: 数据结构课程资料里如何证明量子纠缠违反贝尔不等式？
    answerable: false
    expected_sources: []
  - question: 当前课程讲义规定 2030 年考试的具体日期是哪一天？
    answerable: false
    expected_sources: []
  - question: 课程资料是否给出了某家公司的实时股票价格？
    answerable: false
    expected_sources: []
```

For LLM samples, store `llm_evaluated=True`, `cited_source_ids`, cited quotes, `refused`, and `answer_correct=None`; a citation is valid only when its source is expected and its quote contains at least one expected evidence term. Unsampled rows store `llm_evaluated=False`. Do not label answer correctness from retrieval. The Markdown report must show “未独立评分” when correctness is `None` and “未运行回答评测” when no LLM rows were sampled.

- [ ] **Step 5: Run all focused backend and frontend checks**

Run: `C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_citation_validator.py backend/tests/test_evidence_retrieval_service.py backend/tests/test_grounded_qa_pipeline.py backend/tests/test_graph_retriever.py backend/tests/test_tutor.py backend/tests/test_agent_runtime.py backend/tests/test_public_kb_evaluation.py -q`

Run: `node frontend/scripts/tutor-stream-policy.test.mjs`

Run: `node frontend/scripts/tutor-evidence-ui.test.mjs`

Run: `node frontend/scripts/assistant-responsive-layout.test.mjs`

Run: `node scripts/check-assistant-ui.mjs`

Expected: all commands PASS.

- [ ] **Step 6: Regenerate implementation facts and write the acceptance record**

Run from repository root:

```powershell
& 'C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe' scripts/export_implementation_docs.py
& 'C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe' scripts/check_docs.py
```

Update current-state documents only after tests pass. The `23_Grounded_QA双通道验收记录.md` acceptance record must state actual commands and measured values for `retrieval_ms`, `first_token_ms`, `generation_ms`, `total_ms`, `llm_call_count`, three viewport checks, Provider/Mock status, and any unmet target; it must not convert the design goals into claimed results.

- [ ] **Step 7: Run full proportional verification**

Run:

```powershell
& 'C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe' -m pytest backend/tests -q
& 'C:\Users\28744\Desktop\zhixue\frontend\node_modules\.bin\tsc.cmd' --noEmit -p frontend/tsconfig.json
$env:NODE_PATH='C:\Users\28744\Desktop\zhixue\frontend\node_modules'; & 'C:\Users\28744\Desktop\zhixue\frontend\node_modules\.bin\next.cmd' build frontend
& 'C:\Users\28744\Desktop\zhixue\backend\.venv\Scripts\python.exe' scripts/check_docs.py
git diff --check
```

Expected: backend tests PASS, TypeScript exits 0, Next build succeeds, docs check succeeds, and `git diff --check` emits no errors. If an environment service is unavailable, record the exact failing command and output in the acceptance record instead of claiming completion.

- [ ] **Step 8: Perform three-viewport browser acceptance**

Use `build-web-apps:frontend-testing-debugging` with the in-app Browser against a locally running frontend and backend. At 390×844, 960×768, and 1440×900 verify chat visibility, composer visibility, resource dialog open/close, one streamed grounded answer, expandable citation, feedback/save availability, history restoration, and no relevant console error. Add the observed results and screenshots/paths, when retained, to `23_Grounded_QA双通道验收记录.md`.

- [ ] **Step 9: Commit evaluator and factual documentation**

```powershell
git add scripts/evaluate_public_kb.py data/seed_knowledge/data_structure/eval/standard_questions.yml backend/tests/test_public_kb_evaluation.py docs/当前实现基线.md docs/当前实现API清单.md docs/功能完成度与待完善清单.md docs/19_测试方案
git commit -m "test: verify grounded qa quality and responsiveness"
```

## Final Acceptance Gate

- [ ] `CitationValidator` never returns unknown or unused citations.
- [ ] Every displayed document citation resolves to a real material and chunk; every Wiki citation resolves to a real page.
- [ ] No reliable evidence yields `insufficient` and `citations=[]`.
- [ ] Fast Tutor path performs one retrieval and one model call without fallback.
- [ ] Agent pure QA does not pre-search or re-summarize the Grounded QA result.
- [ ] Partial stream failure does not trigger a duplicate synchronous request.
- [ ] Fast Tutor history restores the real `learning_record_id` and complete evidence payload.
- [ ] 390px, 960px, and 1440px layouts keep chat and composer usable.
- [ ] Evaluation report separates retrieval, citations, refusal, and independently scored correctness.
- [ ] API facts, implementation baseline, functional completeness, and acceptance record match executable code.
