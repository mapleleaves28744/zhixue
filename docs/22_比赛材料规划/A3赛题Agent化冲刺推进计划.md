# A3 赛题 Agent 化冲刺推进计划

> 文档状态：**规划参考 / 后续实施依据**
>
> 适用范围：把当前“AI 助手感较强”的学生端系统，中度重构为更符合中国软件杯 A3 赛题要求的个性化学习多智能体系统。
>
> 当前实现事实仍以 `docs/当前实现基线.md`、当前代码、OpenAPI、SQLAlchemy Model 与真实验收记录为准。本文不代表所有能力已经实现。

## 1. 核心结论

当前项目已经具备课程、资料、RAG、Wiki、Tutor、资源、练习、诊断、画像、记忆、自进化、推荐和 Agent 日志等主链路雏形，但整体体验仍偏向：

```text
用户点击功能按钮
  → 后端调用某个 Agent
  → 返回单次结果
```

更接近赛题要求的学习 Agent 系统应升级为：

```text
用户通过自然语言说明学习需求或任务
  → Agent 理解目标
  → 自动拆解计划
  → 选择公共知识库、个人 LLM Wiki、Skill 和子 Agent
  → 分步骤执行
  → 展示进度、证据、引用和风险
  → 产出多模态资源
  → 更新画像、Wiki、学习路径、诊断、自进化策略和推荐
```

因此，本轮改造不只是继续增加接口，而是新增：

```text
AgentTask
IntentRouterAgent
PlannerExecutor / LearningTaskGraph
SkillRegistry
Artifact 系统
课程知识库工程流水线
Karpathy LLM Wiki 个人知识库
AgentTimeline 前端面板
```

## 2. 参考项目与资料

所有参考项目和协议必须在比赛文档显著位置标注。AGPL/GPL 类项目只参考架构、流程和交互，不直接复制代码，除非项目明确接受对应协议约束。

| 方向 | 参考 | 用途 |
|---|---|---|
| 个人 LLM Wiki | <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f> | 第一参考，raw sources、ingest、index、log、lint、query 方法论 |
| Agent 工作流 | <https://github.com/langchain-ai/langgraph> | 有状态、多步骤、可恢复学习 Agent 工作流 |
| Supervisor 多 Agent | <https://github.com/langchain-ai/langgraph-supervisor-py> | 多 Agent handoff、memory、supervisor 参考 |
| GraphRAG | <https://github.com/microsoft/graphrag> | 公共课程知识库实体、关系、社区摘要与检索 |
| GraphRAG 文档 | <https://microsoft.github.io/graphrag/> | 索引、查询、评估流程参考 |
| 轻量图谱 RAG | <https://github.com/HKUDS/LightRAG> | 轻量 GraphRAG 与增量更新参考 |
| 资料摄取 | <https://github.com/run-llama/llama_index> | 文档加载、ingestion pipeline、metadata、chunk 参考 |
| LlamaIndex ingestion | <https://docs.llamaindex.ai/en/v0.12.15/understanding/loading/loading/> | 资料解析、转换、索引工程流程参考 |
| HTML 课堂 | <https://github.com/THU-MAIC/OpenMAIC> | 只参考多模态课堂/讲解视频 Skill，不整站迁移 |
| MAIC UI | <https://github.com/THU-MAIC/MAIC-UI> | 课堂交互形态和 UI 参考 |
| LLM Wiki 工程参考 | <https://github.com/swarmclawai/swarmvault> | 个人知识库工程化参考 |
| LLM Wiki 工程参考 | <https://github.com/nashsu/llm_wiki> | Wiki 检索和页面组织参考 |
| 数据结构课程 | <https://github.com/Berkeley-CS61B> | 公开课程、代码、项目材料参考 |
| CS61B 课程站点 | <https://fa25.datastructur.es/> | 数据结构课程章节、slides、项目组织参考 |
| MIT 6.006 | <https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/> | 数据结构与算法讲义、视频、习题参考 |
| 开放教材 | <https://opendatastructures.org/> | 数据结构开放教材参考 |
| 前端图表 | <https://github.com/apache/echarts> | 知识图谱、掌握度、学习趋势可视化 |
| Markdown 渲染 | <https://github.com/remarkjs/react-markdown> | 现代 AI 输出渲染参考 |
| 流式交互 | <https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events> | SSE 流式输出、生成进度和阶段事件参考 |

## 3. 总体推进顺序

严格按以下顺序推进，避免同时开太多战线：

```text
Phase 0  范围冻结与参考确认
Phase 1  《数据结构》课程知识库工程化
Phase 2  对话式 Agent 任务入口
Phase 3  Agent 规划执行器
Phase 4  对话式学习画像
Phase 5  公共 GraphRAG + 个人 Karpathy LLM Wiki
Phase 6  Skill 多资源生成
Phase 7  HTML 课堂/动画讲解
Phase 8  学习路径、效果评估、自进化
Phase 9  现代 AI 产品交互与前端底层重构
Phase 10 演示、测试、比赛文档
```

关键约束：

1. 中度重构当前项目，不整站重写。
2. 前端展示样子保持当前 Stitch 风格，底层可以逐步 React 化。
3. `/assistant` 升级为对话式 Agent 任务入口。
4. `/knowledge` 升级为课程知识库建设、GraphRAG、LLM Wiki 和质量报告入口。
5. 公共 GraphRAG 是课程知识底座，个人 LLM Wiki 是学生知识沉淀。
6. OpenMAIC 只参考 HTML 课堂 Skill，不迁移整站。
7. 所有生成能力必须支持 Mock Provider，保证无真实 Key 也可演示。
8. 现代 AI 产品交互是硬性验收项：流式输出、Markdown 渲染、多模态内容卡片、生成进度、错误/空状态必须显性可见。

## 4. Phase 0：范围冻结与参考确认

### 目标

防止推进中失控，先把不做什么、参考什么、怎样判定完成写清楚。

### 不做

```text
不重建整套 UI
不整站迁移 OpenMAIC
不先追求真实 MP4
不建设教师端/管理员端
不绕过人工审核导入网上资料
不让 Agent 自动修改代码、数据库结构、权限规则或部署配置
```

### 要做

1. 在比赛材料中建立开源参考和协议说明。
2. 明确知识库、Agent、Skill、Wiki、前端体验的分工。
3. 明确每个阶段完成后的 gate。
4. 明确现有事实源仍以 `docs/当前实现基线.md` 和当前代码为准。

### Gate

```text
docs 中有改造路线、参考项目、协议说明、阶段顺序。
```

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-00-01` | 开源参考与协议矩阵 | `docs/22_比赛材料规划` | 形成参考项目、许可证、可用方式、风险等级表；AGPL/GPL 项明确只参考不复制 |
| `A3-00-02` | 冲刺范围冻结说明 | 本文档、比赛材料总文档 | 明确不建设教师端/管理员端、不整站重写、不让 Agent 自动改代码/数据库/权限 |
| `A3-00-03` | Milestone Gate 统一模板 | 本文档 | 每个后续阶段都有代码、前端、功能、文档验收项 |

## 5. Phase 1：《数据结构》课程知识库工程化

### 目标

先补赛题硬门槛：自行构造至少一门完整高校专业课程的初始知识库/文档集。当前 `data/seed_knowledge/data_structure` 只有 `.gitkeep`，必须优先补真实资料、结构、图谱和评测。

### 5.1 标准目录

创建并维护：

```text
data/seed_knowledge/data_structure/
├── README.md
├── sources_manifest.yml
├── LICENSES.md
├── course_outline.yml
├── raw/
├── normalized/
├── graph/
├── wiki_seed/
├── eval/
└── artifacts/
```

### 5.2 资料发现脚本

新增：

```text
scripts/discover_course_sources.py
```

功能：

```text
搜索《数据结构》高质量资料
  → 生成候选源
  → AI 评分
  → 标注许可证、使用建议和风险
  → 写入 sources_manifest.yml
```

候选源字段：

```yaml
name:
url:
institution:
source_type:
license:
coverage:
quality_score:
risk_level:
import_status: candidate|approved|rejected
notes:
```

规则：

1. AI 只发现、总结和评分。
2. 开发者手动 approve。
3. 未授权资料不导入 `raw/`，只保留链接和说明。
4. 用户自行上传资料时，默认用户确认拥有使用授权，但系统仍记录来源和风险。

### 5.2.1 资料导入分级

为避免资料版权和范围失控，资料处理分为三类：

| 等级 | 含义 | 是否进入 `raw/` | 使用方式 |
|---|---|---|---|
| `candidate` | AI 或人工发现的候选源，未审核 | 否 | 只保存链接、摘要、许可证判断和风险 |
| `approved_link_only` | 可引用但不适合复制全文 | 否 | 在 manifest 中保留链接，用于人工说明和演示引用 |
| `approved_importable` | 许可证允许或自有资料 | 是 | 可进入 `raw/`，参与 normalized、chunk、embedding 和 Wiki seed |

任何脚本不得把 `candidate` 或 `approved_link_only` 自动下载为本地全文资料。

### 5.3 课程大纲

`course_outline.yml` 必须覆盖：

```text
导论
复杂度
线性表
链表
栈
队列
递归
树
二叉树
堆
哈希表
图
BFS
DFS
最短路径
并查集
排序
查找
综合项目
```

每章结构：

```yaml
chapter_id:
title:
learning_goals:
knowledge_points:
prerequisites:
resource_types:
expected_exercises:
```

### 5.4 一键构建脚本

新增：

```text
scripts/build_data_structure_kb.py
scripts/ingest_course_materials.py
scripts/evaluate_course_kb.py
```

构建流程：

```text
读取 approved sources
  → 解析 raw 文件
  → 清洗文本
  → 识别章节
  → 生成 normalized/chapter_x.md
  → 按“标题层级 + 语义块 + token-aware + overlap + metadata”生成 chunk
  → 写入 document_chunks
  → 使用 text-embedding-3-small 生成 1024 维 embedding
  → 抽取 knowledge_points
  → 抽取 knowledge_edges
  → 生成题库/代码案例草稿
  → 生成 wiki_seed
  → 生成质量报告
```

### 5.4.1 最小可运行版本

第一版不要一次性追求完整 GraphRAG 和自动题库。建议 MVP 流程为：

```text
读取 approved_importable sources
  → 解析本地 markdown/txt/pdf
  → 生成 normalized/chapter_x.md
  → 复用现有课程、资料、切片、embedding、知识点抽取 Service
  → 生成 wiki_seed markdown
  → 输出 eval/quality_report.json
```

MVP 不新增复杂后台任务系统，不依赖 Docker，不要求真实 LLM Key。Mock Provider 下必须可运行。

### 5.5 改造 chunking

Phase 1 的切片策略必须写死为：

```text
标题层级 + 语义块 + token-aware + overlap + metadata
```

不得退化为单纯按字符长度、固定行数或固定段落粗暴切分。

推荐参数：

| 类型 | 建议 chunk 大小 | overlap | 说明 |
|---|---:|---:|---|
| 普通知识解释 | 500-700 tokens | 80-120 tokens | 保留上下文连续性 |
| 定义/定理/复杂度结论 | 尽量整体保留 | 0-80 tokens | 不从关键结论中间切断 |
| Python 代码示例 | 整个代码块优先保留 | 0-80 tokens | 不切断函数、类、缩进块 |
| 表格/公式 | 整体保留或以占位符绑定原文 | 0-80 tokens | 避免破坏结构 |
| 超长章节 | 先按标题/小节拆，再 token-aware | 80-120 tokens | 不直接硬切全文 |

必须保留的切片信息：

```text
heading_path
chapter_id
source_id
source_url
license
attribution
page_no 或 url_fragment（有则必须写）
chunk_type: definition|concept|example|code|table|formula|complexity|misconception|exercise
text_hash
chunk_index
```

切片质量要求：

1. 同一 chunk 应尽量表达一个完整概念、操作、复杂度结论或例子。
2. 标题路径必须进入 `document_chunks.extra_meta.heading_path`。
3. 代码块不能从中间截断，Python 缩进不能被破坏。
4. 表格和公式不能被无意义拆散；无法结构化解析时保留 Markdown 原文或占位符。
5. 每个 chunk 必须可追溯到资料源，不允许无 `source_id` 的正式 chunk 进入课程知识库。
6. 后续真实入库前，应把当前字符近似切片升级为真正 token-aware 切片。

### 5.5.1 Embedding 模型与维度约束

Phase 1 真实向量化默认使用：

```text
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1024
```

必须注意：当前数据库 `document_chunks.embedding` 维度为 `Vector(1024)`。`text-embedding-3-small` 默认输出不是 1024 维，因此真实调用 OpenAI-compatible embedding 接口时必须显式传：

```json
{
  "model": "text-embedding-3-small",
  "input": ["..."],
  "dimensions": 1024
}
```

禁止事项：

1. 禁止在未修改数据库 migration 的情况下把 embedding 维度改成 1536 或 3072。
2. 禁止用真实 embedding 默认维度直接写入 `Vector(1024)`。
3. 禁止用 Mock Embedding 的效果冒充真实检索质量。
4. 若要改用 `text-embedding-3-large` 或其他模型，必须同步修改 `EMBEDDING_DIMENSION`、pgvector 维度、migration、检索评测记录和文档。
5. 真实构建前必须先 dry-run，再执行非 dry-run 入库。

Mock 模式仅用于无 API Key 演示：

```powershell
python scripts/build_data_structure_kb.py --dry-run --use-mock-embedding
```

真实入库示例：

```powershell
python scripts/build_data_structure_kb.py --course-id <course_id> --user-id <owner_user_id>
```

### 5.6 质量评估

`scripts/evaluate_course_kb.py` 输出：

```text
章节覆盖率
知识点数量
关系数量
chunk 数
题目数量
代码案例数量
来源可追溯率
标准问题命中率
无来源回答比例
图谱覆盖率
```

### Gate

```text
能在 /knowledge 看到数据结构资料源、章节、知识图谱、质量报告。
```

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-01-01` | 数据结构知识库目录与 manifest | `data/seed_knowledge/data_structure` | 目录、`README.md`、`sources_manifest.yml`、`LICENSES.md` 存在；没有只有标题的占位文档 |
| `A3-01-02` | 课程大纲初版 | `course_outline.yml` | 覆盖导论、复杂度、线性表、链表、栈、队列、递归、树、二叉树、堆、哈希表、图、BFS、DFS、最短路径、并查集、排序、查找、综合项目 |
| `A3-01-03` | 资料发现脚本 | `scripts/discover_course_sources.py` | 只生成候选源，不下载未授权全文；输出字段包含许可证和风险 |
| `A3-01-04` | 本地资料规范化脚本 | `scripts/ingest_course_materials.py` | approved_importable 资料可生成 `normalized/chapter_x.md` |
| `A3-01-05` | 种子知识库构建脚本 MVP | `scripts/build_data_structure_kb.py` | 能复用现有 Service 创建演示课程、资料、chunks、embeddings、knowledge_points |
| `A3-01-06` | 知识库质量评估 | `scripts/evaluate_course_kb.py`、`eval/` | 输出章节覆盖率、知识点数、chunk 数、来源可追溯率、标准问题命中率 |
| `A3-01-07` | `/knowledge` 质量报告接入 | `frontend/public/stitch-pages/knowledge.html`、静态 API 脚本 | 页面能看到资料源、章节覆盖和质量报告；保持 Stitch 视觉结构 |

## 6. Phase 2：对话式 Agent 任务入口

### 目标

让用户可以在对话窗口直接说明任务，而不是只能点按钮。

用户示例：

```text
我最近图和排序不太会，帮我生成一套学习计划、讲解资料、练习题和一个课堂讲解。
```

### 6.1 新增 Agent Task 数据模型

新增表：

```text
agent_tasks
agent_task_steps
```

`agent_tasks` 关键字段：

```text
id
user_id
course_id
task_goal
task_type
status
plan_json
risk_level
requires_confirmation
created_at
updated_at
```

建议补充字段：

```text
plan_schema_version
input_payload
intent_payload
confirmed_at
started_at
finished_at
cancelled_at
error_message
```

`agent_task_steps` 关键字段：

```text
id
task_id
step_index
agent_name
skill_name
status
input_payload
output_payload
evidence
error_message
started_at
finished_at
```

建议补充字段：

```text
action
expected_output
related_agent_run_id
artifact_refs
retry_count
duration_ms
```

### 6.1.1 状态机

`agent_tasks.status` 固定为：

```text
draft
planned
waiting_confirmation
running
succeeded
failed
cancelled
```

`agent_task_steps.status` 固定为：

```text
pending
running
succeeded
failed
skipped
```

状态流转规则：

```text
draft → planned → running → succeeded
draft → planned → waiting_confirmation → running → succeeded
running → failed
running → cancelled
waiting_confirmation → cancelled
```

所有查询必须按当前 `user_id` 过滤；涉及 `course_id` 时必须校验课程归属。

### 6.2 新增任务 API

新增：

```text
POST /api/v1/agent-tasks/create
POST /api/v1/agent-tasks/{task_id}/confirm
POST /api/v1/agent-tasks/{task_id}/run
GET  /api/v1/agent-tasks/{task_id}
GET  /api/v1/agent-tasks/{task_id}/steps
```

### 6.3 新增 IntentRouterAgent

职责：

```text
理解用户自然语言任务
识别任务类型
抽取课程、知识点、资源需求、约束
判断风险等级
判断是否需要确认
```

输出示例：

```json
{
  "task_type": "personalized_learning_package",
  "goal": "补强图和排序",
  "target_knowledge": ["图", "排序"],
  "requested_artifacts": ["learning_path", "doc", "quiz", "html_classroom"],
  "risk_level": "low",
  "requires_confirmation": false
}
```

### Gate

```text
用户在 /assistant 输入复杂任务，系统能生成结构化任务，而不是只回答一段话。
```

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-02-01` | AgentTask ORM 与 migration | `backend/app/models`、`backend/alembic` | 新增 `agent_tasks`、`agent_task_steps`；`alembic upgrade head` 通过 |
| `A3-02-02` | AgentTask Schema/Repository/Service | `backend/app/schemas`、`repositories`、`services` | 支持创建、查询、确认、取消；用户隔离正确 |
| `A3-02-03` | AgentTask API | `backend/app/api/v1` | API 返回统一响应；执行 `python scripts/export_implementation_docs.py` 更新 API 清单 |
| `A3-02-04` | IntentRouterAgent MVP | `backend/app/agents`、Prompt/Mock | Mock 下能将自然语言任务解析成 task_type、目标知识点、artifact 需求、风险等级 |
| `A3-02-05` | `/assistant` 任务入口 | `frontend/public/stitch-pages/assistant.html`、静态 API 脚本 | 输入复杂任务后出现 AgentTask 卡片，而不是只追加普通聊天回答 |
| `A3-02-06` | AgentTask 后端测试 | `backend/tests` | 覆盖创建、确认、查询、用户隔离、IntentRouter Mock 输出 |

## 7. Phase 3：Agent 规划执行器

### 目标

让 Agent 能自己拆计划、选工具、分步骤执行，并展示进度。

### 7.1 新增 LearningTaskGraph

新增：

```text
backend/app/agent_graphs/learning_task_graph.py
```

流程：

```text
IntentRouterAgent
  → PlannerAgent 生成计划
  → 用户确认高风险计划
  → Executor 按步骤执行
  → 每步调用 Agent 或 Skill
  → ReviewAgent 审核
  → 保存 artifact
  → 更新 Wiki/Profile/Recommendation
```

### 7.2 固定计划格式

```json
{
  "goal": "",
  "steps": [
    {
      "step": 1,
      "agent": "KnowledgeAgent",
      "action": "retrieve_context",
      "input": {},
      "expected_output": "citations"
    },
    {
      "step": 2,
      "agent": "ResourceAgent",
      "skill": "knowledge_card_skill",
      "expected_output": "artifact"
    }
  ]
}
```

计划 JSON 建议补充：

```json
{
  "plan_schema_version": "1.0",
  "goal": "",
  "risk_level": "low",
  "requires_confirmation": false,
  "steps": [
    {
      "step": 1,
      "agent": "KnowledgeAgent",
      "action": "retrieve_context",
      "skill": null,
      "input": {},
      "expected_output": "citations",
      "writes": [],
      "risk_level": "low",
      "requires_confirmation": false
    }
  ]
}
```

第一版执行器只允许调用白名单动作，不执行任意字符串命令或动态导入。

### 7.3 风险规则

自动执行：

```text
检索
生成讲解
生成题目
生成卡片
生成课堂草稿
生成学习路径草稿
```

需要确认：

```text
应用自进化策略
覆盖 Wiki 页面
删除记忆
批量重建知识库
对外导出或发布内容
```

### Gate

```text
用户提出学习任务后，系统能生成计划、执行步骤、展示进度、产出多个 artifact。
```

### 7.4 PlannerExecutor MVP

第一版只实现 3 条可演示路径：

| task_type | 固定步骤 | 产物 |
|---|---|---|
| `personalized_learning_package` | 检索上下文 → 生成学习路径草稿 → 生成讲解资源 → 生成练习 → Review | learning_path、resource、quiz、review |
| `profile_interview_plan` | 画像访谈 → 更新画像草稿 → 生成推荐 | profile_update、recommendations |
| `html_classroom_request` | 检索上下文 → 生成课堂分镜草稿 → Review → 保存 artifact | html_classroom |

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-03-01` | 计划格式与校验 | `backend/app/schemas`、`backend/app/services` | 非白名单 agent/action 被拒绝；高风险步骤进入 waiting_confirmation |
| `A3-03-02` | PlannerExecutor MVP | `backend/app/agent_graphs/learning_task_graph.py` | 能执行固定 2-4 步计划，并写入 `agent_task_steps` |
| `A3-03-03` | 复用现有 Agent/Service | `backend/app/services` | 通过 Service 调用资源、练习、路径等能力，不绕过业务层写库 |
| `A3-03-04` | ReviewAgent 接入 | `backend/app/agent_graphs`、`backend/app/agents` | 关键产物保存前有 review_result 或风险说明 |
| `A3-03-05` | AgentTimeline MVP | `/assistant` Stitch 页面 | 用轮询展示 pending/running/succeeded/failed；失败保留已完成步骤 |
| `A3-03-06` | 执行器测试 | `backend/tests` | Mock 下完整执行 `personalized_learning_package`，至少生成 2 类产物和 step 日志 |

## 8. Phase 4：对话式学习画像

### 目标

满足赛题第一条：摒弃传统繁琐表单，通过自然语言对话构建不少于 6 个维度的动态学生画像。

### 8.1 新增 ProfileInterviewAgent

画像维度至少包括：

```text
专业背景
学习目标
知识基础
认知风格
学习偏好
易错点
时间节奏
资源偏好
代码能力
掌握度
```

### 8.2 接入 Agent Task

用户可以说：

```text
帮我先了解一下我的学习情况，然后给我制定数据结构学习计划。
```

系统执行：

```text
ProfileInterviewAgent
  → ProfileAgent
  → PlannerAgent
  → RecommendAgent
```

### 8.3 画像证据

每个画像字段都保存 evidence：

```text
来自哪轮对话
来自哪次答题
来自哪份诊断
来自哪条记忆
```

### Gate

```text
用户不填表，通过对话生成 6+ 维画像，并能看到画像证据。
```

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-04-01` | ProfileInterviewAgent | `backend/app/agents` | 能生成 6+ 维画像问题和结构化画像草稿 |
| `A3-04-02` | 画像证据结构 | `student_profiles`、`learning_preferences` 相关 Service 或 JSON 字段 | 每个画像字段记录来源类型、来源 ID、置信度和更新时间 |
| `A3-04-03` | 对话式画像接入 AgentTask | AgentTask Service/Executor | 用户一句话可触发画像访谈和后续计划 |
| `A3-04-04` | `/path-profile` 证据展示 | Stitch 页面 | 画像字段旁能看到证据摘要，不只显示结论 |

## 9. Phase 5：公共 GraphRAG + 个人 Karpathy LLM Wiki

### 9.1 公共 GraphRAG

用途：

```text
课程资料检索
资源生成 grounding
学习路径规划
知识图谱展示
```

实现：

```text
knowledge_graph_entities
knowledge_graph_edges
community summaries
hybrid search
```

### 9.2 个人 Karpathy LLM Wiki

第一参考为 Karpathy LLM Wiki。落地模式：

```text
raw_sources
  → ingest
  → wiki_pages
  → wiki_links
  → wiki_sources
  → wiki_page_versions
  → index
  → log
  → lint
  → query
```

新增：

```text
wiki_raw_sources
wiki_lint_reports
```

来源类型：

```text
document
chat
quiz
mistake
diagnosis
resource
classroom
manual
```

### 9.3 查询顺序

```text
先查个人 LLM Wiki
  → 再查公共 GraphRAG
  → 再查原始 chunks
  → 生成回答
  → ReviewAgent 审核
```

### Gate

```text
回答里能同时显示“个人 Wiki 来源”和“课程资料来源”。
```

### 9.4 分档实现

不要一次性上完整 GraphRAG。建议分为：

| 档位 | 实现范围 | 是否阻塞比赛主链路 |
|---|---|---|
| `v0` | 复用 `knowledge_points`、`wiki_links`、`document_chunks`，做轻量图谱和混合检索展示 | 是 |
| `v1` | 新增 `knowledge_graph_entities`、`knowledge_graph_edges`，支持实体/关系查询 | 可作为 P1 |
| `v2` | community summaries、GraphRAG 评估、复杂图谱增强检索 | 不阻塞主链路，作为冲奖增强 |

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-05-01` | GraphRAG v0 查询协议 | RAG/Knowledge Service | 查询结果区分个人 Wiki、课程资料 chunk、知识点图谱 |
| `A3-05-02` | Wiki raw source 与 lint 设计 | Model/Schema/Docs | 明确是否新增 `wiki_raw_sources`、`wiki_lint_reports`，若新增必须走 migration |
| `A3-05-03` | Wiki 查询顺序落地 | Tutor/Knowledge Service | 回答 citation 中能标明个人 Wiki 来源和课程资料来源 |
| `A3-05-04` | `/knowledge` 图谱增强 | Stitch 页面 | 展示知识点、Wiki 页面、来源三类节点或筛选 |

## 10. Phase 6：Skill 多资源生成

### 目标

满足至少 5 类资源生成，实际规划 9 类资源。

### 10.1 新增 SkillRegistry

新增：

```text
backend/app/skills/
```

Skill 列表：

```text
doc_explain_skill
knowledge_card_skill
mindmap_skill
quiz_skill
reading_skill
html_classroom_skill
code_case_skill
ppt_skill
project_material_skill
```

每个 Skill 必须有：

```text
input_schema
output_schema
required_context
citations
review_result
artifact_type
```

### 10.2 统一 artifact

```json
{
  "artifact_type": "",
  "title": "",
  "markdown": "",
  "content": {},
  "citations": [],
  "review_result": {},
  "agent_run_id": ""
}
```

### 10.3 Artifact 落库策略

当前已有 `generated_resources` 表。统一 artifact 有三种落地方式：

| 方案 | 做法 | 优点 | 风险 |
|---|---|---|---|
| A | 扩展 `generated_resources`，增加 `artifact_type`、`content_json`、`review_result` | 改动较小，前端可复用现有资源列表 | 表语义会逐渐变宽 |
| B | 新增 `learning_artifacts` 表，所有 Skill 产物统一落库 | 结构清晰，适合长期演进 | migration、API、前端改动较多 |
| C | 短期把 artifact 放入现有 JSON/extra_meta 字段 | 最快可演示 | 后续迁移成本较高 |

建议比赛冲刺采用 A；如果后续要系统化建设多模态产物，再升级到 B。

### Gate

```text
同一个知识点能生成 5+ 类资源，且每类都有引用和审核结果。
```

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-06-01` | Artifact Schema | `backend/app/schemas`、前端类型/静态脚本 | 前后端 artifact 字段一致 |
| `A3-06-02` | SkillRegistry MVP | `backend/app/skills` | 注册 doc、card、quiz、code_case、html_classroom 5 类 Skill |
| `A3-06-03` | ResourceAgent 接入 Skill | `backend/app/agents/resource_agent.py`、Service | 资源生成可按 artifact_type 分流 |
| `A3-06-04` | Review 结果入 artifact | ReviewAgent/Service | 每个 artifact 有引用检查和风险说明 |
| `A3-06-05` | ArtifactCard MVP | `/assistant` 或 `/practice` Stitch 页面 | 展示标题、类型、来源、Review 状态、保存到 Wiki |

## 11. Phase 7：HTML 课堂/动画讲解

### 目标

满足赛题“多模态教学视频/动画”要求。比赛版先交付可播放 HTML 互动课堂，不先追求 MP4。

### 用户输入示例

```text
帮我生成一个栈和递归的讲解视频。
```

### Agent 执行

```text
IntentRouterAgent
  → PlannerAgent
  → KnowledgeAgent
  → html_classroom_skill
  → ReviewAgent
  → 保存 artifact
```

### HTML 课堂内容

```text
分镜
讲解稿
字幕
图解卡片
动画描述
随堂测验
总结
下一步推荐
```

### Gate

```text
前端能播放一个 HTML 课堂，而不是只展示 Markdown。
```

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-07-01` | HTML 课堂 artifact schema | Skill/Artifact Schema | 包含 scenes、script、subtitle、quiz、summary |
| `A3-07-02` | html_classroom_skill Mock | `backend/app/skills` | 无真实 Key 时能生成可播放课堂结构 |
| `A3-07-03` | ClassroomPlayer MVP | `/assistant` Stitch 页面或 React island | 能播放分镜、字幕和简单动画，不直接注入不可信 HTML |
| `A3-07-04` | 保存到 Wiki/学习路径 | Resource/Wiki/Path Service | 课堂可关联知识点和推荐下一步 |

## 12. Phase 8：学习路径、评估、自进化

### 12.1 学习路径

用户可以说：

```text
根据我的错题和目标，给我安排这周的数据结构学习计划。
```

系统执行：

```text
ProfileAgent
  → DiagnosisAgent
  → PlannerAgent
  → RecommendAgent
```

### 12.2 学习效果评估

指标：

```text
学习频次
答题正确率
知识点掌握度
错误类型
资源反馈
推荐采纳率
策略前后变化
```

### 12.3 自进化

触发条件：

```text
完成诊断
连续答错某类题
资源反馈较差
学习目标变化
定时每日/每周分析
```

风险规则：

```text
low 自动推荐
medium 用户确认
high 管理员/人工确认
```

### Gate

```text
答题后能触发诊断、画像更新、自进化策略和学习路径调整。
```

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-08-01` | 学习效果指标汇总 | Diagnosis/Profile/Recommendation Service | 输出答题正确率、薄弱点、资源反馈、推荐采纳率 |
| `A3-08-02` | 自进化触发规则 | Evolution Service | 诊断后、连续错题、反馈较差可生成策略；medium/high 不自动应用 |
| `A3-08-03` | 策略 diff 展示 | `/path-profile` Stitch 页面 | 显示 before/after、证据、风险、应用/回滚 |
| `A3-08-04` | 学习路径自动调整 | LearningPath Service | 策略应用后能生成或更新路径，并记录理由 |

## 13. Phase 9：现代 AI 产品交互与前端底层重构

### 目标

补齐赛题非功能性要求中的现代 AI 产品交互规范。当前视觉不变，底层更现代；前端展示仍保持当前 Stitch 风格，但必须具备流式输出、Markdown 渲染、多模态内容卡片化展示、生成进度追踪和稳定错误状态。

当前项目已有部分“等待进度”和静态卡片样式，但还没有形成统一的现代 AI 交互层。因此这一阶段不是单纯美化，而是补一套可复用的 AI 输出协议和渲染体系。

### 13.1 流式输出

适用场景：

```text
Tutor 问答
AgentTask 执行进度
资源生成
HTML 课堂生成
知识库构建进度
ReviewAgent 审核结果
```

后端建议：

```text
优先使用 SSE
事件类型固定为 token、step、artifact、citation、review、done、error
Mock Provider 也要模拟流式 token 和 step 事件
长任务先返回 task_id，再通过 stream/status 查询进度
```

前端行为：

```text
用户提交后立即出现 AI 正在执行状态
文本 token 逐步出现
Agent step 实时变更状态
引用和 artifact 可以后到达
失败时保留已生成内容并显示重试按钮
```

### 13.2 Markdown 渲染

所有 AI 文本输出不再以纯文本展示，统一走 Markdown 渲染。

必须支持：

```text
标题
列表
表格
代码块
行内代码
引用块
数学公式占位或降级显示
来源脚注
安全转义，禁止直接注入不可信 HTML
```

接入页面：

```text
/assistant：Tutor 回答、Agent 任务总结
/knowledge：Wiki 内容、知识库质量报告
/practice：题目解析、诊断报告
/path-profile：画像解释、策略 diff
/dashboard：推荐理由
```

### 13.3 多模态内容卡片化

Skill 输出必须统一渲染为 ArtifactCard，而不是把所有内容塞成 Markdown。

卡片类型：

```text
doc：课程讲解文档
card：知识卡片
mindmap：思维导图
quiz：练习题
reading：拓展阅读
html_classroom：HTML 课堂/动画讲解
code_case：代码实操案例
ppt：课件/PPT 大纲
project：实践项目材料
citation：引用来源
review：审核结果
recommendation：推荐下一步
```

统一展示规则：

```text
每张卡片有标题、类型、来源、生成 Agent、Review 状态
卡片支持展开详情
卡片支持保存到 Wiki
卡片支持反馈 helpful/unhelpful
重要卡片支持加入学习路径
无来源卡片必须显示 AI 推断风险
```

### 13.4 多模态 Artifact Schema

前后端统一使用 artifact 结构，避免每个 Skill 自己定义一套展示方式：

```json
{
  "artifact_type": "doc|card|mindmap|quiz|reading|html_classroom|code_case|ppt|project",
  "title": "",
  "summary": "",
  "markdown": "",
  "content": {},
  "citations": [],
  "related_knowledge_points": [],
  "actions": ["save_to_wiki", "add_to_path", "practice_now"],
  "review_result": {
    "has_citation": true,
    "hallucination_risk": "low",
    "safety_risk": "low",
    "reason": ""
  },
  "agent_run_id": ""
}
```

### 13.5 生成进度追踪

所有长任务必须展示阶段进度，避免白屏等待。

通用阶段：

```text
理解任务
读取画像
检索个人 Wiki
检索公共 GraphRAG
规划步骤
调用 Skill
生成草稿
Review 审核
保存产物
更新推荐
完成
```

页面上至少展示：

```text
当前阶段
已完成阶段
失败阶段
耗时
可重试入口
相关 Agent 名称
```

### 13.6 错误、空状态和降级

现代 AI 产品不能只在成功路径好看。必须补齐：

```text
无课程：引导创建或导入演示课程
无知识库：引导构建《数据结构》知识库
无画像：引导开始画像访谈
无引用：标记 AI 推断并建议核对资料
生成超时：显示部分结果和重试
Review 高风险：阻止直接保存或应用
Mock 模式：明确显示 Mock，但内容仍结构化可演示
```

### 13.7 React islands

优先接入：

```text
AgentTaskPanel
AgentTimeline
KnowledgeGraph
ProfileMetrics
StrategyDiff
ArtifactCard
MarkdownRenderer
ClassroomPlayer
QualityReportPanel
```

### 13.8 页面接入

```text
/assistant：对话式 Agent 任务入口、流式输出、Artifact 卡片
/knowledge：知识库构建、GraphRAG、Wiki、质量报告、知识图谱
/path-profile：画像、策略 diff、记忆、路径、证据卡片
/dashboard：学习总览、推荐、Agent 状态、ECharts 趋势
/practice：练习、诊断、错题、解析 Markdown 和推荐卡片
```

### Gate

```text
页面仍是当前样子，但用户能通过对话驱动 Agent 执行任务，并能看到流式输出、Markdown 渲染、多模态 Artifact 卡片、生成进度、引用来源和 Review 状态。
```

### 13.9 前移与后置边界

AgentTask 的最小进度展示不应等到 Phase 9。Phase 2/3 先通过轮询展示 steps；Phase 9 再升级为统一 SSE 和更完整的 Markdown/Artifact 渲染。

Phase 9 不做整站 React 重写，只做必要 React islands 或静态脚本增强。若某页面需要 React 组件化，必须单独确认范围。

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-09-01` | AI Event 协议 | Backend Schema/Docs | 固定 token、step、artifact、citation、review、done、error |
| `A3-09-02` | SSE MVP | Tutor/AgentTask Service/API | Mock Provider 也能模拟 token 和 step 事件 |
| `A3-09-03` | MarkdownRenderer | 前端静态页或 React island | 支持标题、列表、表格、代码块、安全转义 |
| `A3-09-04` | ArtifactCard 统一渲染 | `/assistant`、`/practice` | 多资源不再塞成纯 Markdown |
| `A3-09-05` | 错误/空状态统一 | 关键 Stitch 页面 | 无课程、无知识库、无画像、无引用、超时、高风险、Mock 模式均有明确状态 |

## 14. Phase 10：演示、测试、比赛文档

### 必须交付

```text
数据结构知识库
一键初始化脚本
演示账号
30-50 个标准问题
Agent 任务样例
知识库质量报告
开源项目与协议说明
答辩稿
演示视频脚本
README
```

### 测试

```text
pytest
alembic upgrade head
python scripts/export_implementation_docs.py
python scripts/check_docs.py
npm run typecheck
npm run build
Playwright/E2E
```

### 最终演示链路

```text
登录
  → 用户对话构建画像
  → 用户通过对话提出学习任务
  → Agent 自动拆计划
  → Agent 构建/检索知识库
  → 生成讲解文档、卡片、思维导图、题库、代码案例、PPT、HTML课堂
  → 学生做题
  → 系统诊断
  → 画像更新
  → 自进化策略
  → 学习路径更新
  → 展示 Agent 调用链和防幻觉审核
```

### 建议拆分任务

| 任务编号 | 任务名称 | 修改范围 | 验收标准 |
|---|---|---|---|
| `A3-10-01` | 一键初始化演示数据 | `scripts/`、`data/seed_knowledge` | 初始化后可直接演示数据结构课程主链路 |
| `A3-10-02` | 30-50 个标准问题 | `data/seed_knowledge/data_structure/eval` | 覆盖课程章节、Tutor、资源、练习、诊断、AgentTask |
| `A3-10-03` | E2E 演示脚本 | `scripts/` 或测试目录 | 覆盖登录、AgentTask、资源、练习、诊断、自进化、推荐 |
| `A3-10-04` | 比赛答辩材料 | `docs/24_答辩稿`、`docs/22_比赛材料规划` | 功能表述与当前实现一致，不宣称未完成能力 |
| `A3-10-05` | 最终验收记录 | `docs/19_测试方案` | 记录 pytest、alembic、docs check、前端 build、E2E、真实/Mock LLM 结果 |

## 15. 当前项目能力差距

当前能做到：

```text
有 Agent 类
有 Agent 日志
有 Tutor 问答
有资源生成
有练习诊断
有画像/记忆/自进化/推荐接口
```

当前不能完整做到：

```text
用户通过自然语言下达复杂任务
Agent 自动拆计划
Agent 自动选择多个 Skill
Agent 分步骤执行
前端展示任务进度
统一流式输出
统一 Markdown 渲染
统一多模态 Artifact 卡片
长任务生成进度追踪
现代 AI 产品级错误/空状态
遇到风险请求确认
任务完成后自动更新 Wiki/画像/路径/推荐
完整数据结构课程知识库工程化构建
```

所以本计划的核心不是再堆单点功能，而是把系统升级为：

```text
对话驱动任务
  → Agent 规划执行
  → 知识库 grounding
  → 多 Skill 产物
  → Review 防幻觉
  → 学习状态自更新
```

## 16. Milestone Gates

```text
Gate 1：数据结构知识库真实存在
Gate 2：用户能通过对话创建 AgentTask
Gate 3：Agent 能自动生成计划并执行多步骤
Gate 4：画像能通过对话生成 6+ 维度
Gate 5：GraphRAG 和 Karpathy LLM Wiki 分工清楚
Gate 6：5+ 类资源生成都有 artifact、引用、审核
Gate 7：HTML 课堂可播放
Gate 8：答题后触发诊断、画像、自进化、推荐
Gate 9：流式输出、Markdown、多模态卡片和生成进度可见
Gate 10：防幻觉机制可见
Gate 11：演示和文档完整
```

## 17. 后续实施建议

第一批实施不要从前端炫技开始，应先做：

```text
1. 数据结构知识库目录和资料源 manifest
2. course_outline.yml
3. 资料发现与人工审核脚本
4. AgentTask + IntentRouterAgent
5. PlannerExecutor 最小可运行版本
```

这五项完成后，项目才真正具备继续 Agent 化和比赛冲刺的稳定地基。

## 18. 统一 Gate 模板

后续每个 `A3-*` 任务完成后，必须按以下模板验收，不得只写“已完成”。

```text
代码验收：
- 后端变更：执行相关 pytest；涉及 DB 时执行 alembic upgrade head
- 前端变更：执行 npm run typecheck 和 npm run build
- Router/Schema/Model 变更：执行 python scripts/export_implementation_docs.py
- 文档变更：执行 python scripts/check_docs.py

功能验收：
- 输入样例：
- 预期 API：
- 预期数据库记录：
- 预期页面展示：
- Mock Provider 下结果：
- 真实 LLM 结果（如本任务要求）：

边界验收：
- 是否保持 Stitch 页面视觉和导航：
- 是否校验 user_id/course_id 权限：
- 是否有引用、证据或 AI 推断风险提示：
- 是否未引入教师端/管理员端新范围：
- 是否未让 Agent 自动修改代码、数据库结构、权限或部署配置：

未完成项：
- 后端完成但前端未接入：
- Mock 完成但真实 LLM 未验收：
- 本地通过但 Docker 未验收：
```

## 19. 第一批 Codex 任务建议

第一批不要并行展开全部阶段。建议按下面顺序逐个执行：

| 顺序 | 任务编号 | 为什么先做 |
|---|---|---|
| 1 | `A3-01-01` | 先建立数据结构知识库目录、manifest 和许可证边界 |
| 2 | `A3-01-02` | 课程大纲是知识点、资源、题库和质量评估的共同骨架 |
| 3 | `A3-01-03` | 资料发现先只做候选，不触碰版权风险 |
| 4 | `A3-02-01` | AgentTask 表是对话任务、进度和执行器的持久化基础 |
| 5 | `A3-02-04` | IntentRouterAgent 让 `/assistant` 从普通问答升级为任务入口 |
| 6 | `A3-03-01` | 先固定计划格式和白名单，避免执行器失控 |
| 7 | `A3-03-02` | PlannerExecutor MVP 打通 Agent 化最短链路 |

这 7 个任务完成后，项目可以形成新的比赛叙事：

```text
完整课程知识库底座
  → 对话创建学习任务
  → Agent 解析意图
  → 白名单计划执行
  → 多步骤进度展示
  → 有来源、有审核、有风险边界的学习产物
```
