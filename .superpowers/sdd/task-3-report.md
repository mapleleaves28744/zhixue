# Task 3 Report: Single-call GroundedQaPipeline and grounded prompt

## Status

GREEN. Task 3 的非流式 grounded QA 内核、Prompt 不变量、响应契约和 `TutorAgent` 兼容适配器已实现。Router、数据库表和 migration 均未变更。

## RED / GREEN evidence

### RED 1: pipeline 不存在

命令（在 `backend` 目录）：

```powershell
python -m pytest tests/test_grounded_qa_pipeline.py -q
```

结果：collection error，`ModuleNotFoundError: No module named 'app.services.grounded_qa_pipeline'`。失败原因与预期一致，证明新测试覆盖的是尚未存在的 Task 3 内核。

### GREEN 1: 最小单次调用与寒暄短路

同一命令结果：`2 passed`。

### RED / GREEN 2: 关联知识点不应依赖模型是否标注该条引用

新增断言后结果：`1 failed, 5 passed`，失败为 `related_knowledge_points` 空列表；最小修改为从已接受证据集合生成关联知识点，同时引用列表仍只采用验证后、实际在回答中使用的标记。复跑结果：`6 passed`。

### 聚焦兼容集合

命令：

```powershell
python -m pytest tests/test_citation_validator.py tests/test_evidence_retrieval_service.py tests/test_graph_retriever.py tests/test_hybrid_retriever.py tests/test_grounded_qa_pipeline.py tests/test_prompt_service.py tests/test_tutor.py -q
```

结果：`54 passed`。

额外的 pipeline + Tutor 复跑（加入适配器委托测试后）：`17 passed`。

### 静态与文档检查

```powershell
python -m compileall -q app tests/test_grounded_qa_pipeline.py
git diff --check
python scripts/check_docs.py
```

结果：均为退出码 0；文档检查输出 `documentation check passed: 4 active folders, 113 markdown files, no placeholders or broken local references`。

按 AGENTS 要求执行了：

```powershell
python scripts/export_implementation_docs.py
```

结果：失败，项目基线缺少 `backend/app/storage`，导入 `app.services.material_parse_service` 时抛出 `ModuleNotFoundError: No module named 'app.storage'`。未伪造模块、未临时修改无关业务代码，也未生成不可信事实文档；该基线阻塞留待统一处理。

## Implemented behavior

- `GroundedQaPipeline.answer()` 对普通问题只调用一次 `EvidenceRetrievalService.retrieve()` 和一次 `provider.chat()`。
- 简单寒暄在授权后本地返回，检索和 LLM 调用数均为 0。
- 普通问题在检索前创建一个 `TutorAgent` run，并将 run ID 传给 LLM provider 日志上下文；完成日志包含 performance、候选数、接受数和 grounding 状态。
- 使用 Task 1 的 `CitationValidator`，只向客户端返回回答实际引用且存在的 `[S#]` 证据。
- 默认 Tutor Prompt 使用编号证据规则；即使数据库启用旧模板，也强制追加 `GROUNDED_TUTOR_RULES`。
- 学生画像和长期记忆使用独立 formatter，避免把同一合并文本复制进两个 Prompt 槽位。
- `_persist()` 按 Task 3 保持兼容 stub，只返回 `(None, payload.conversation_id)`。
- `TutorAgent.run()` 委托新 pipeline；原有格式化 helper 保留并通过既有测试。

## Files

- `backend/app/services/grounded_qa_pipeline.py`（新增）
- `backend/app/services/prompt_service.py`
- `backend/app/services/personalization_context_service.py`
- `backend/app/schemas/tutor.py`
- `backend/app/agents/tutor_agent.py`
- `backend/tests/test_grounded_qa_pipeline.py`（新增）
- `backend/tests/test_tutor.py`
- `.superpowers/sdd/task-3-report.md`（新增）

## Self-review

- 未调用 `AgentService`、Review Agent、Memory Agent 或同步知识抽取；pipeline 只读取个性化上下文。
- `provider.chat` 参数固定为 `temperature=0.2`、`max_tokens=1200`、禁用 thinking，并传递 prompt version。
- Prompt 中的证据编号由 Task 2 `EvidenceItem.citation_key` 唯一提供，不生成自由来源编号。
- Fallback、模型、provider、图谱上下文、grounding 和 performance 元数据均写入响应。
- 未修改 Router、SQLAlchemy Model、migration、数据库结构或既有两个无关工作区改动。
- 新增 Schema 保持向后兼容：扩展字段均有默认值，既有响应构造测试继续通过。

## Concerns / Task 4 handoff

1. Task 3 的 `_persist()` 有意不写消息、学习记录或事务；因此直接调用 pipeline 时 `message_id` 为空、`postprocess_status=skipped`。Task 4 必须在同一内核上补齐事务、事件和流式路径。
2. 当前旧 `TutorService.chat()` 仍包裹 `AgentService`、旧持久化和同步后处理。API 路由迁移到 pipeline 的单一持久化事务属于 Task 4；在此之前兼容路径可能同时存在外层 Orchestrator run 与 pipeline run。
3. `export_implementation_docs.py` 被基线缺失 `app.storage` 阻塞，Task 3 未生成或提交事实清单变化。
