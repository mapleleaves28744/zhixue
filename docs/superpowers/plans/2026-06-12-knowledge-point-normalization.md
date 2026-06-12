# Knowledge Point Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将每份资料的粗抽取候选整理为 15-30 个有来源、可分组的细粒度知识点，并确保 Wiki 仅从当前资料知识点生成。

**Architecture:** 在现有 `KnowledgeService` 与 Repository 之间新增独立 `KnowledgeNormalizationService`。规则抽取负责召回带 chunk 来源的候选，归一化服务通过统一 LLM Provider 或规则降级输出结构化结果，Service 校验后写入现有 `knowledge_points.extra_meta` 并回绑 chunks；`WikiGenerateService` 按当前资料来源过滤知识点。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy Async、统一 LLM Provider、pytest、Stitch 静态页面 JavaScript

---

### Task 1: 建立归一化结构与确定性质量规则

**Files:**
- Create: `backend/app/services/knowledge_normalization_service.py`
- Create: `backend/tests/test_knowledge_normalization.py`

- [ ] **Step 1: 编写名称清洗与拒绝规则失败测试**

在 `backend/tests/test_knowledge_normalization.py` 覆盖：

```python
from app.services.knowledge_normalization_service import KnowledgeNormalizationService


def test_clean_candidate_name_rejects_markdown_and_sentence_noise() -> None:
    service = KnowledgeNormalizationService(db=None)

    assert service.clean_candidate_name("**知识图谱建议关系**") == "知识图谱建议关系"
    assert service.is_valid_name("知识图谱建议关系")
    assert not service.is_valid_name("按位访问 O(n)，插入删除后继 O(1)")
    assert not service.is_valid_name("**")
    assert not service.is_valid_name("1")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend; python -m pytest tests/test_knowledge_normalization.py -v`

Expected: FAIL，原因是 `KnowledgeNormalizationService` 尚不存在。

- [ ] **Step 3: 实现归一化数据结构与清洗规则**

在 `knowledge_normalization_service.py` 定义：

```python
class KnowledgeCandidate(BaseModel):
    raw_name: str
    description: str = ""
    chapter: str | None = None
    source_chunk_ids: list[UUID] = Field(default_factory=list)
    source_order: int = 0


class NormalizedKnowledgeItem(BaseModel):
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    chapter: str | None = None
    parent_name: str | None = None
    description: str = ""
    difficulty: str | None = None
    importance: str | None = None
    sort_order: int = 0
    source_chunk_ids: list[UUID] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    decision_reason: str = ""


class KnowledgeNormalizationResult(BaseModel):
    candidate_count: int
    merged_count: int
    rejected_count: int
    kept_count: int
    used_llm: bool
    fallback_reason: str | None = None
    items: list[NormalizedKnowledgeItem] = Field(default_factory=list)
    rejected: list[dict[str, str]] = Field(default_factory=list)
```

实现 `clean_candidate_name()`、`is_valid_name()` 和 Markdown、编号、完整句噪声过滤。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend; python -m pytest tests/test_knowledge_normalization.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backend/app/services/knowledge_normalization_service.py backend/tests/test_knowledge_normalization.py
git commit -m "feat: add knowledge normalization quality rules"
```

### Task 2: 实现 LLM 归一化与规则降级

**Files:**
- Modify: `backend/app/services/knowledge_normalization_service.py`
- Modify: `backend/app/services/prompt_service.py`
- Modify: `backend/tests/test_knowledge_normalization.py`

- [ ] **Step 1: 编写重复合并、数量上限与降级测试**

新增测试，传入包含重复项、噪声项和 35 个有效项的候选，断言：

```python
assert result.used_llm is False
assert result.kept_count <= 30
assert result.candidate_count == len(candidates)
assert len({item.canonical_name for item in result.items}) == result.kept_count
assert all(item.source_chunk_ids for item in result.items)
assert result.rejected_count > 0
```

另用 `AsyncMock` 模拟结构化 LLM 返回“链式栈 + aliases=[链栈]”，断言两个候选合并为一个规范知识点。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend; python -m pytest tests/test_knowledge_normalization.py -v`

Expected: FAIL，原因是 `normalize()` 尚未实现。

- [ ] **Step 3: 实现 `normalize()`**

实现以下签名：

```python
async def normalize(
    self,
    *,
    candidates: list[KnowledgeCandidate],
    course_id: UUID,
    owner_id: UUID,
    min_items: int = 15,
    max_items: int = 30,
) -> KnowledgeNormalizationResult:
    ...
```

行为要求：

1. 先清洗并拒绝确定性噪声。
2. 通过统一 Provider 的 `structured_chat()` 请求规范名称、别名、章节、父知识点、来源候选索引和理由。
3. 校验 LLM 输出只能引用已有候选来源。
4. LLM 异常或无有效结果时调用 `_normalize_by_rules()`。
5. 最终按来源覆盖度、重要程度、置信度和出现顺序排序，最多保留 30 个。

在 `PromptService.DEFAULT_PROMPTS` 增加 `knowledge.normalize`，明确禁止无来源新增概念并要求 15-30 个细粒度知识点。

- [ ] **Step 4: 运行专项测试**

Run: `cd backend; python -m pytest tests/test_knowledge_normalization.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backend/app/services/knowledge_normalization_service.py backend/app/services/prompt_service.py backend/tests/test_knowledge_normalization.py
git commit -m "feat: normalize extracted knowledge with llm fallback"
```

### Task 3: 将资料抽取改为带来源候选并持久化整理元数据

**Files:**
- Modify: `backend/app/services/knowledge_service.py`
- Modify: `backend/app/repositories/knowledge_repository.py`
- Modify: `backend/app/repositories/chunk_repository.py`
- Modify: `backend/tests/test_knowledge_normalization.py`

- [ ] **Step 1: 编写资料范围与来源绑定失败测试**

构造两个 chunks，调用候选抽取与持久化辅助方法，断言：

```python
assert all(item.source_chunk_ids for item in result.items)
assert all(str(material_id) in point.extra_meta["normalization"]["source_material_ids"] for point in points)
assert all(chunk.knowledge_id is not None for chunk in material_chunks)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend; python -m pytest tests/test_knowledge_normalization.py -v`

Expected: FAIL，原因是现有抽取结果不带 chunk 来源，也不会回绑 chunk。

- [ ] **Step 3: 修改抽取与 Repository**

将 `KnowledgeService._extract_by_rules()` 改为按 chunk 生成 `KnowledgeCandidate`，保留最多 80 个候选。`extract_from_material()` 调用归一化器后再持久化。

在 `KnowledgeRepository` 增加受控更新方法：

```python
async def apply_normalization(
    self,
    point: KnowledgePoint,
    *,
    chapter: str | None,
    parent_id: UUID | None,
    description: str | None,
    difficulty: str | None,
    importance: str | None,
    sort_order: int,
    normalization_meta: dict[str, object],
) -> KnowledgePoint:
    ...
```

在 `ChunkRepository` 增加：

```python
async def bind_knowledge(self, *, chunk_ids: list[UUID], knowledge_id: UUID) -> int:
    ...
```

写入 `extra_meta.normalization` 时合并 `aliases`、`source_chunk_ids` 和 `source_material_ids`，不得覆盖其他 `extra_meta`。

- [ ] **Step 4: 运行专项测试**

Run: `cd backend; python -m pytest tests/test_knowledge_normalization.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backend/app/services/knowledge_service.py backend/app/repositories/knowledge_repository.py backend/app/repositories/chunk_repository.py backend/tests/test_knowledge_normalization.py
git commit -m "feat: persist normalized material knowledge sources"
```

### Task 4: 扩展抽取 API 的整理统计

**Files:**
- Modify: `backend/app/schemas/knowledge.py`
- Modify: `backend/app/api/v1/knowledge.py`
- Modify: `backend/app/agents/knowledge_agent.py`
- Modify: `backend/tests/test_knowledge_normalization.py`

- [ ] **Step 1: 编写响应兼容测试**

断言抽取响应仍包含旧字段，并新增：

```python
assert payload["extracted_count"] == payload["normalization"]["kept_count"]
assert "relations_created" in payload
assert "points" in payload
assert payload["normalization"]["candidate_count"] >= payload["normalization"]["kept_count"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend; python -m pytest tests/test_knowledge_normalization.py -v`

Expected: FAIL，原因是响应无 `normalization`。

- [ ] **Step 3: 修改 Service 返回值与 API**

让 `KnowledgeService.extract_from_material()` 返回包含 `points`、`relations_created` 和 `normalization` 的明确结果对象。Router 只负责调用 Service 并序列化响应；`KnowledgeAgent` 使用新的结果对象生成日志摘要：

```text
粗抽取 {candidate_count} 个候选，合并 {merged_count} 个，拒绝 {rejected_count} 个，保留 {kept_count} 个知识点
```

- [ ] **Step 4: 运行专项测试**

Run: `cd backend; python -m pytest tests/test_knowledge_normalization.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backend/app/schemas/knowledge.py backend/app/api/v1/knowledge.py backend/app/agents/knowledge_agent.py backend/tests/test_knowledge_normalization.py
git commit -m "feat: expose knowledge normalization statistics"
```

### Task 5: 限制 Wiki 仅生成当前资料知识点

**Files:**
- Modify: `backend/app/services/wiki_generate_service.py`
- Create: `backend/tests/test_wiki_generate_material_scope.py`

- [ ] **Step 1: 编写跨资料隔离失败测试**

创建资料 A 与资料 B 的知识点，并在 `extra_meta.normalization.source_material_ids` 中分别记录来源。调用资料 A 的 Wiki 生成，断言：

```python
assert {page.knowledge_id for page in pages} == {material_a_point.id}
assert material_b_point.id not in {page.knowledge_id for page in pages}
```

另覆盖当前资料无整理知识点时返回明确业务错误。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend; python -m pytest tests/test_wiki_generate_material_scope.py -v`

Expected: FAIL，因为当前实现读取课程下全部 owner 知识点。

- [ ] **Step 3: 修改 Wiki 生成筛选**

在 `WikiGenerateService.generate_from_material()` 中仅保留：

```python
material_knowledge_points = [
    point
    for point in knowledge_points
    if str(material_id)
    in ((point.extra_meta or {}).get("normalization") or {}).get("source_material_ids", [])
]
```

后续 pending、页面生成、来源创建和父子链接均使用 `material_knowledge_points`。没有匹配知识点时抛出“当前资料尚无已整理知识点，请先执行知识点抽取”。

- [ ] **Step 4: 运行 Wiki 与知识专项测试**

Run: `cd backend; python -m pytest tests/test_wiki_generate_material_scope.py tests/test_knowledge_normalization.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backend/app/services/wiki_generate_service.py backend/tests/test_wiki_generate_material_scope.py
git commit -m "fix: scope wiki generation to source material"
```

### Task 6: 在现有 Stitch 页面展示整理统计

**Files:**
- Modify: `frontend/public/stitch-pages/knowledge.html`

- [ ] **Step 1: 增加前端状态与渲染验收检查**

在浏览器测试前记录验收目标：

```text
单独抽取后显示候选、合并、拒绝、保留数量
完整流水线完成文案包含整理统计
used_llm=false 时显示“规则整理”
原导航、侧栏、顶部栏和主布局不变
```

- [ ] **Step 2: 修改局部状态与文案**

新增 `lastNormalization` 状态。抽取成功后保存 `result.normalization`，在现有 Knowledge / Wiki 卡片中增加一行简洁统计：

```text
粗抽取 58 · 合并 17 · 拒绝 14 · 保留 27 · LLM 整理
```

完整流水线结束文案使用真实统计；`used_llm=false` 时显示“规则整理”。不新增平行页面或裸 `fetch`。

- [ ] **Step 3: 运行前端检查**

Run: `cd frontend; npm run typecheck`

Expected: PASS。

Run: `cd frontend; npm run build`

Expected: PASS。

- [ ] **Step 4: 使用 in-app Browser 验证**

打开 `/knowledge?course_id=<可写课程ID>`，执行一次知识点抽取，确认统计文案、错误提示和现有布局正常。

- [ ] **Step 5: 提交**

```powershell
git add frontend/public/stitch-pages/knowledge.html
git commit -m "feat: show knowledge normalization progress"
```

### Task 7: 同步实现事实文档并完成阶段验收

**Files:**
- Modify: `docs/当前实现基线.md`
- Auto-update: `docs/11_API接口设计/16_当前实现API清单.md`
- Auto-update: `docs/10_数据库设计/15_当前实现数据库清单.md`

- [ ] **Step 1: 更新当前实现基线**

记录以下事实：

```text
资料知识点抽取已采用规则候选 + LLM 归一化 + 规则降级
单份资料最多保留 30 个有来源知识点
Wiki 生成已限制为当前资料知识点
/knowledge 已展示整理统计
```

- [ ] **Step 2: 导出实现文档**

Run: `python scripts/export_implementation_docs.py`

Expected: 命令成功，API 与数据库当前实现清单同步。

- [ ] **Step 3: 运行后端回归**

Run: `cd backend; python -m pytest tests/test_knowledge_normalization.py tests/test_wiki_generate_material_scope.py tests/test_knowledge_graph_relations.py -v`

Expected: PASS。

- [ ] **Step 4: 运行阶段验收**

Run: `powershell -ExecutionPolicy Bypass -File scripts/local_check.ps1 -Backend`

Expected: PASS。

Run: `powershell -ExecutionPolicy Bypass -File scripts/local_check.ps1 -Frontend`

Expected: PASS。

- [ ] **Step 5: 检查文档**

Run: `python scripts/check_docs.py`

Expected: PASS，无占位模板和本地断链。

- [ ] **Step 6: 提交**

```powershell
git add docs/当前实现基线.md docs/11_API接口设计/16_当前实现API清单.md docs/10_数据库设计/15_当前实现数据库清单.md
git commit -m "docs: record normalized knowledge wiki pipeline"
```

