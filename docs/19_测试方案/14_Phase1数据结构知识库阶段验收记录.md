# Phase 1《数据结构》知识库阶段验收记录

> 验收日期：2026-06-07  
> 验收分支：`change_2`  
> 验收环境：本机 PostgreSQL、FastAPI、Next.js、本地真实 Embedding、真实 LLM；Docker 不属于 Phase 1 验收范围。  
> 验收结论：**Phase 1《数据结构》GraphRAG-ready 课程知识库工程化通过验收，状态为 completed。**

## 验收范围

本次验收覆盖资料治理、文档解析与清洗、层级切片、真实 Embedding、索引、混合检索、轻量 rerank、真实 LLM RAG 回答、引用来源、标准问题评测和 `/knowledge` Stitch 页面联动。

完整 Microsoft GraphRAG community summaries、Global/Local/DRIFT 查询和 cross-encoder/LLM rerank 属于后续 Phase 5，不作为 Phase 1 阻塞项。

## 公有知识库实际状态

| 指标 | 实际结果 |
|---|---:|
| 公有课程 | `DS-PUBLIC` / `public_template` |
| course_id | `0b41dca8-3e7d-420b-9769-b4fe623e482f` |
| 章节覆盖 | 19 / 19，100% |
| normalized 文档 | 32 |
| 实际入库资料 | 32 |
| document chunks | 1608 |
| 已向量化 chunks | 1608 |
| 知识点 | 125 |
| 来源可追溯率 | 100% |
| GraphRAG-ready v0 | 10 个实体、8 条关系、6 条 claims |

真实 Embedding 配置：

```text
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DIMENSION=1024
EMBEDDING_ALLOW_MOCK_FALLBACK=false
```

## 知识库流水线验收

| 流水线阶段 | 结果 | 验收证据 |
|---|---|---|
| 原始资料与许可证治理 | 通过 | `sources_manifest.yml`、`LICENSES.md`、21 份 raw、32 份 normalized |
| 文档解析与清洗 | 通过 | HTML、Markdown、RST、PDF 可规范化；来源可追溯率 100% |
| 层级切片 | 通过 | 标题层级、token-aware、overlap、metadata、代码块保护 |
| 真实 Embedding | 通过 | 1608 / 1608 chunks 使用 BGE 1024 维真实向量，禁止 Mock fallback |
| 索引 | 通过 | pgvector HNSW、内容 pg_trgm、extra_meta GIN、metadata expression indexes |
| 混合检索 | 通过 | `HybridRetriever` 组合向量、关键词和 metadata 检索 |
| Rerank | 通过 | 已执行向量分数、关键词分数、metadata 和来源多样性轻量 rerank |
| LLM 回答与引用 | 通过 | 真实 `xiaomi_mimo` RAG 样例，`fallback_used=false`，引用率 100% |
| 反馈评测 | 通过 | 标准问题逐题保存来源命中、回答 grounded 状态和引用状态 |

## 标准问题评测

执行：

```powershell
python scripts/evaluate_public_kb.py --course-id 0b41dca8-3e7d-420b-9769-b4fe623e482f --top-k 8 --run-llm-sample 3
python scripts/evaluate_course_kb.py --source-root data/seed_knowledge/data_structure
```

结果：

| 指标 | 结果 |
|---|---:|
| 标准问题数 | 30 |
| 检索召回率 | 96.67% |
| 回答准确率 | 96.67% |
| 幻觉率 | 3.33% |
| 引用率 | 100% |
| 真实 LLM 样例 | 3 个，均 `fallback_used=false` |

详细报告：

- [GraphRAG-ready 质量报告](../../data/seed_knowledge/data_structure/eval/quality_report.md)
- [公有知识库评测报告](../../data/seed_knowledge/data_structure/eval/public_kb_eval_report.md)

## 浏览器验收

使用普通学生验收账号访问：

```text
http://127.0.0.1:3000/knowledge?course_id=0b41dca8-3e7d-420b-9769-b4fe623e482f
```

实际结果：

1. `/knowledge` 页面成功展示 32 份公有课程资料，资料卡标记为“公共资料”。
2. “质量报告”页签成功展示《数据结构》GraphRAG-ready v0、真实 BGE 向量化证据和资料源许可证风险。
3. 页面可见 Open Data Structures、MIT OCW 6.006 和自有草稿等资料源卡片。
4. 输入“什么是抽象数据类型 ADT？”并点击“检索资料”，页面返回 RAG Search 结果；空结果提示消失，可见 `01_绪论与复杂度分析.md` 和 ADT 相关命中内容。
5. 首次验收发现运行中的旧后端进程未加载新增质量报告路由，接口返回 404；重启当前分支 FastAPI 后，接口返回 `code=0`，最终浏览器验收通过。

## 工程检查

```text
python -m alembic upgrade head                          通过
python -m pytest                                       109 passed
python scripts/check_docs.py                           通过
npm run typecheck                                      通过
npm run build                                          通过
GET /api/v1/knowledge/seed-quality-report              code=0
浏览器 /knowledge 质量报告、资料源、实际检索             通过
```

## Phase 1 结论

Phase 1 已满足推进方案中的 `A3-01-01` 至 `A3-01-07` 验收标准，并完成用户追加要求的真实公有知识库入库、关键词索引、metadata GIN、混合检索、轻量 rerank、真实 RAG 回答和效果评测。

正式状态：

```text
Phase 1：completed
下一阶段：Phase 2 对话式 Agent 任务入口
```
