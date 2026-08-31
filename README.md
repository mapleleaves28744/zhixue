# 智学工坊 Zhixue Workshop

> 面向高校课程的个性化 AI 学习空间：让课程资料成为可检索、可引用、可持续演化的个人知识系统。

[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs)](frontend/package.json)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](backend/requirements.txt)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.x-1C3C3C)](backend/requirements.txt)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql)](docs/当前实现数据库清单.md)
[![Tests](https://img.shields.io/badge/pytest-503%20passed-2E8B57?logo=pytest)](docs/当前实现基线.md)

![智学工坊项目视觉横幅](docs/assets/readme/zhixue-hero-v2.png)

智学工坊是一套围绕高校课程学习过程构建的 AI 原生学习系统。学生可以为不同课程建立独立空间，上传 PDF、Word、Markdown 等资料；系统会将原始文档转化为课程知识库、知识图谱与 LLM Wiki，并在此基础上提供可信答疑、个性化资源、练习诊断、学习路径和长期画像。

它不是把大模型接到一个聊天框里，而是尝试回答四个更接近真实学习场景的问题：

| 学习问题 | 产品设计 | 工程实现 |
|---|---|---|
| 资料散落在讲义、教材和笔记中，难以组织 | 为每门课程建立动态知识空间 | 文档解析、切片、Embedding、Hybrid RAG、知识点抽取、LLM Wiki |
| 通用模型回答看似流畅，却缺少课程依据 | 让回答和资源能够回到原始资料 | 真实 chunk/source ID、`[S1]` 引用、Grounded QA、引用规则校验 |
| 一次性问答无法理解学生长期变化 | 让系统持续积累有证据的学习状态 | 全局画像、课程画像、长期记忆、掌握度、错题与诊断联动 |
| 智能体会调用什么工具、做了什么难以控制 | 把智能体约束在可观测的业务边界内 | LangGraph、Tool Registry、任务事件、checkpoint、风险确认与策略回滚 |

## 从资料到个性化学习闭环

```text
创建课程与上传资料
  → 文档解析、语义切片、向量化与知识点抽取
  → Hybrid RAG、知识图谱与版本化 LLM Wiki
  → Grounded Tutor、个性化资源与多模态学习产物
  → 练习、自动批改、错题归因与学习诊断
  → 全局画像、课程画像、长期记忆与掌握度更新
  → 学习路径、下一步推荐与可回滚策略演化
  └──────────────────── 新的学习行为继续反馈到下一轮 ────────────────────┘
```

系统以 `course_id` 作为课程级数据边界。资料、切片、知识点、Wiki、练习、诊断、资源和课程画像都与当前课程关联；稳定的学习偏好可以跨课程复用，而掌握度、薄弱点和错误模式不会在不同课程之间互相覆盖。

## 核心能力

### 1. 把原始课程资料加工成可用知识

课程资料不是简单上传后交给模型，而是经过一条可检查的知识加工流水线：

1. 根据文件类型解析 PDF、DOCX、TXT 和 Markdown 正文。
2. 清理无效内容，记录解析状态与失败原因。
3. 结合标题层级、文本长度和重叠窗口进行语义切片，并保护代码块。
4. 为每个切片保留课程、资料、标题、页码和来源 metadata。
5. 通过独立 Embedding Provider 生成向量并写入 pgvector。
6. 抽取有来源的细粒度知识点，继续生成 Wiki、图谱和可引用知识片段。

![RAG 资料预处理流水线](docs/assets/readme/rag-pipeline.png)

当前公有《数据结构》模板知识库已完成规模化入库验证：

- 32 份课程资料；
- 1,608 个文档切片；
- 1,608 条真实 BGE 1024 维向量；
- 125 个知识点；
- 课程资料覆盖 19 个章节，并保留来源与许可清单。

开发环境可以使用 Mock Embedding 验证流程；效果评测和真实知识库构建使用 `BAAI/bge-large-zh-v1.5`，不会把 Mock 结果当作真实检索效果。

### 2. Hybrid RAG 与可信问答

单纯向量相似度容易漏掉课程术语，也容易返回来自同一文档的重复片段。项目实现 `HybridRetriever`，综合：

- 向量语义相似度；
- 关键词命中；
- `course_id` 与 metadata 过滤；
- 轻量重排序；
- 来源多样性控制。

检索结果会保留资料标题、原始片段、相似度和来源标识，可直接供 Tutor、Resource Agent 和 Wiki 生成链路使用。`GroundedQAPipeline` 将资料与 Wiki 证据转换为 `[S1]`、`[S2]` 等引用上下文，主回答只进行一次 LLM 生成，再通过规则检查引用标记和来源状态。

用户明确要求“基于资料”或“请给出引用”时，Agent 安全网会优先确保课程检索进入任务链；没有可靠证据时，系统应标明属于 AI 推断，而不是伪造来源。

### 3. LLM Wiki：会生长的课程知识空间

LLM Wiki 不是普通的笔记列表，也不是 RAG 文档库的换皮展示。每个 Wiki 页面可以包含：

- 结构化正文、摘要和知识点归属；
- 来自资料、对话、资源、练习或诊断的来源；
- `prerequisite`、`contains`、`confused_with`、`applied_to` 等知识关系；
- 创建、人工编辑、AI 补全和回滚产生的版本记录；
- 内容质量状态，用于区分“已核验”“待补充”和“待补强”。

知识点抽取采用“规则候选召回 → LLM 结构化归一化 → 确定性校验 → 规则降级”流程。单份资料最多保留 30 个有来源的细粒度知识点，并记录别名、来源 chunk、置信度和降级原因。Wiki 生成只处理当前资料绑定的知识点，减少跨资料内容混入。

Tutor 回答和生成资源可以继续保存到 Wiki，让一次性对话沉淀为长期课程资产；页面更新不会直接覆盖旧内容，而是写入 `wiki_page_versions`，学生可以比较历史版本并回滚。

### 4. 两种 AI 学习助手模式

系统为不同复杂度的学习目标提供两种入口：

**快速 Tutor**

- 通过 SSE 流式输出 Markdown、代码和引用；
- 返回相关知识点、追问建议与来源状态；
- 支持停止接收、反馈和保存回答到 Wiki；
- 普通问答优先减少重复检索和重复模型调用。

**LangGraph 智能体模式**

- 适合“检索资料后生成练习并给出复习计划”等复合目标；
- 根据当前观察继续执行、重新规划、审查或结束；
- 展示简洁的计划、工具、观察摘要和产物，不暴露模型原始思维链；
- 浏览器断开后后台任务仍可继续，用户能够恢复历史会话、查看事件或取消任务。

### 5. 可控、可恢复的多智能体运行时

项目基于 LangGraph 1.x 实现动态状态图：

```text
load_context
  → supervisor
  → execute_tool
  → observe
  → replan / review
  → memory_reflect
  → finalize
```

![LangGraph 智能体运行状态图](docs/assets/readme/langgraph-runtime.png)

当前实现包含 15 个领域 Agent，覆盖意图路由、编排、知识检索、Wiki、Tutor、资源、练习、诊断、推荐、画像、记忆、学习路径、知识图谱、自进化和 Review；Tool Registry 集中注册 24 个业务工具。

智能体运行时的重点不是 Agent 数量，而是执行边界：

- Supervisor 只能从当前意图对应的候选工具中选择操作；
- 工具通过业务 Service 工作，不直接绕过权限访问数据库；
- Agent 不具备 Shell、源码修改、Migration、权限或系统配置工具；
- 任务、步骤、事件、对话和 PostgreSQL checkpoint 持久化；
- `task_id`、`tool_call_id` 和事件序号用于任务恢复、追踪与幂等控制；
- 高风险策略应用通过 LangGraph interrupt 等待确认；
- Redis 负责队列和实时通知，PostgreSQL 事件记录作为持久事实源。

### 6. 从对话中持续建立学习画像

传统学习画像往往依赖一次性问卷，填写后很快失效。智学工坊把画像拆分为三层：

| 层级 | 记录内容 | 作用范围 |
|---|---|---|
| 全局画像 | 专业、年级、长期目标、稳定偏好 | 跨课程复用 |
| 课程画像 | 当前课程掌握度、薄弱点、错误模式 | 仅作用于对应课程 |
| 长期记忆 | 有来源的偏好、困难与学习事实 | 按课程或全局作用域管理 |

![对话式学习画像构建过程](docs/assets/readme/dialogue-profile.png)

画像信号可以来自对话、答题、错题、诊断、学习时长和反馈。自然语言中的“喜欢分步骤讲解”“希望优先给 Python 示例”“递归比较薄弱”等信息会经过提取与校验，并保存来源消息、摘录、时间和置信度。

学生可以查看画像证据，归档、恢复或删除长期记忆。生成回答和资源时只加载当前课程相关度最高的活跃记忆，避免无关历史不断堆进 Prompt。

### 7. 练习、诊断、推荐与受控自进化

学生可以按知识点、题型、难度和数量生成练习。提交答案后，系统完成批改、解析、错误标签和错题记录，并将有效学习证据用于更新掌握度。

掌握度并非随意生成的百分比：

- 没有有效学习证据时使用 50% 中性先验，并标记为“待验证”；
- 答题证据按次数和置信度加权；
- 单纯提问不会被当成掌握度下降证据；
- 遗忘模型设置首日宽限和中性下限，避免出现没有依据的极低分。

诊断报告整理薄弱点、错误模式和下一步动作，并进一步影响自适应难度、学习路径和推荐。Planner Agent 会生成“薄弱优先、覆盖优先、难度梯度”等候选路径，再结合学生目标选出更合适的方案。

本项目所说的“自进化”不是让 Agent 修改代码，而是受控调整：

- 问答解释风格与 Prompt 参数；
- 资源生成策略；
- 练习难度；
- 推荐与复习策略；
- 学习路径上下文。

每次策略变更保存变更前后快照、证据、风险等级、版本号、上一版本和物化结果。低风险策略可以受控生效，中高风险策略需要确认；已经应用的策略可以回滚，历史记录不会被删除。

### 8. 多模态学习产物

除了文本问答，系统还可以根据课程来源和画像生成：

- 讲解、总结、例题、错题解析和拓展阅读包；
- 闪卡、思维导图和播客脚本；
- 教学图解与知识卡片；
- 多页 HTML 互动课件；
- TTS 语音与 ASR 转写；
- 带中文画面、配音和烧录字幕的讲解视频；
- 基于课程 RAG、薄弱点和解释偏好的 OpenMAIC 沉浸课堂。

媒体生成通过后台任务执行，统一记录进度、Provider、产物类型、错误和降级状态。无真实文生图能力时，教学图片请求会降级为 Mermaid 知识卡片；无真实模型 Key 时，普通 Wiki、Tutor、资源、练习和诊断可使用结构化 Mock Provider，且不会把降级结果描述为真实模型效果。

## 系统架构

```mermaid
flowchart TB
    Browser[学生端浏览器] --> Web[Next.js 16 / React / StitchFrame]
    Web -->|REST API| API[FastAPI /api/v1]
    Web -->|Tutor SSE / Agent Events| API

    API --> Auth[认证与课程权限]
    API --> Services[业务 Service 层]
    Services --> Repo[Repository / SQLAlchemy]
    Repo --> PG[(PostgreSQL + pgvector)]

    Services --> RAG[文档解析 / Embedding / Hybrid RAG]
    RAG --> PG

    Services --> Runtime[LangGraph Agent Runtime]
    Runtime --> Registry[Tool Registry]
    Registry --> Domains[Wiki / Tutor / Resource / Quiz / Profile / Evolution]
    Domains --> Repo

    Runtime --> Queue[arq Worker]
    Queue <--> Redis[(Redis Queue / PubSub / Cache)]
    Queue --> PG

    Services --> Provider[统一 LLM Provider]
    Provider --> Mock[Mock Provider]
    Provider --> Compatible[OpenAI-compatible Provider]
    Domains --> Media[本地媒体渲染 / OpenMAIC]
```

后端采用模块化单体，主调用链保持为：

```text
Router → Service → Repository → SQLAlchemy Model → PostgreSQL
Router → Service → Agent Runtime → Tool / Service → Repository
```

这种结构让接口校验、权限上下文、事务、模型调用和智能体决策保持在明确边界内。复杂能力仍在一个可部署单元中协作，避免项目早期为了“微服务化”引入额外网络和运维复杂度。

## 关键工程设计

### 数据与状态

- PostgreSQL 保存用户、课程、资料、Wiki、练习、画像、任务和资源等业务事实。
- pgvector 的 `VECTOR(1024)` 保存文档切片向量，并支持按课程过滤的相似度检索。
- Redis 用于 arq 队列、实时通知和画像缓存；Redis 不可用时，持久任务事件仍以数据库为准。
- Alembic 管理所有数据库结构变化，当前包含 25 个 migration。
- 44 张 ORM 表将核心实体与版本、事件、日志、映射和学习过程记录分离。

### 异步任务与流式体验

- 快速 Tutor 使用 SSE 返回文本增量，支持 AbortSignal 与结束状态检测。
- Agent 和多模态长任务由 arq Worker 执行，前端订阅结构化事件。
- 会话、消息、任务、步骤和 checkpoint 持久化，页面关闭不会直接丢失任务。
- 非关键后置任务失败会记录降级事件，但不阻断当前回答。

### Provider 抽象与可降级开发

- 聊天、Embedding、语音和多模态 Provider 分开配置。
- 业务代码不直接依赖具体厂商 SDK，通过统一 Adapter 接入 OpenAI-compatible 服务。
- 结构化任务使用 Pydantic Schema 校验，解析失败可以重试或返回明确错误。
- Mock Provider 返回课程场景相关的结构化结果，使无 Key 环境仍可开发和回归普通主链路。

### 可观测性与事实源

- 每个 HTTP 请求生成 `request_id`，便于关联页面错误与服务日志。
- LLM 调用记录 Provider、模型、Token、延迟、状态和脱敏后的请求/响应摘要。
- Agent 运行记录输入、输出、步骤、工具、耗时、错误和产物引用。
- API 与数据库清单由 FastAPI OpenAPI 和 SQLAlchemy metadata 自动导出，避免文档长期脱离代码。

## 技术栈

| 层级 | 主要技术 |
|---|---|
| Web | Next.js 16、React 18、TypeScript、Tailwind CSS、Framer Motion、Radix UI |
| API | FastAPI、Pydantic、SQLAlchemy 2、Alembic、JWT |
| Agent | LangGraph 1.x、Supervisor、Tool Registry、PostgreSQL Checkpoint |
| Async | Redis、arq、SSE、EventBus |
| Data | PostgreSQL、pgvector、本地文件存储 |
| AI | OpenAI-compatible Adapter、Mock Provider、Sentence Transformers、MiMo |
| Knowledge | 文档解析、Hybrid RAG、LLM Wiki、知识图谱、HNSW |
| Media | MoviePy、TTS/ASR、HTML 课件、OpenMAIC |
| Quality | pytest、TypeScript、Next.js Build、OpenAPI/ORM 自动事实清单 |

## 工程规模与验证结果

以下数字来自当前实现清单与最近一次完整回归基线，而不是早期设计稿：

| 指标 | 当前记录 |
|---|---:|
| FastAPI HTTP 操作 | 147 |
| SQLAlchemy ORM 表 | 44 |
| Alembic migrations | 25 |
| Agent 类 / 注册工具 | 15 / 24 |
| Service 文件 | 69 |
| 后端测试文件 | 68 |
| 后端全量回归 | 503 passed |
| 真实 LLM 主链路 | 23 步通过，未回退 Mock |
| 真实 MiMo Agent 场景 | 20/20 场景通过 |
| Agent 任务完成率 | 95% |
| 工具选择 / 重规划 / 高风险拦截 | 100% / 100% / 100% |

完整统计日期、测试条件和限制以[当前实现基线](docs/当前实现基线.md)和[真实 LLM 验收记录](docs/19_测试方案/13_真实LLM主链路与Next安全专项验收记录.md)为准。

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- PostgreSQL 14+ 与 pgvector
- Redis 5+

项目采用本地优先的开发方式。先启动 PostgreSQL 和 Redis，再复制环境变量模板：

```bash
cp .env.example .env
```

默认开发配置：

```env
DATABASE_URL=postgresql+asyncpg://zhixue:zhixue_password@localhost:5432/zhixue
REDIS_URL=redis://localhost:6379/0
LLM_PROVIDER=mock
EMBEDDING_PROVIDER=mock
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

### 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

在另一个终端启动 Agent Worker：

```bash
cd backend
source .venv/bin/activate
python -m arq app.workers.agent_worker.WorkerSettings
```

Windows PowerShell 可将激活命令替换为 `.\.venv\Scripts\Activate.ps1`。

### 启动前端

```bash
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

打开 [http://127.0.0.1:3000](http://127.0.0.1:3000)。API 文档位于 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

更完整的 Windows 环境配置、数据同步和演示启动方式见[本地开发指南](docs/20_部署方案/05_队友本地开发README.md)。

## 建议体验路径

1. 注册账号并创建一门课程。
2. 上传课程资料，依次执行解析、切片、向量化和知识点抽取。
3. 生成带来源和版本记录的课程 Wiki，通过检索验证知识召回。
4. 在快速 Tutor 中围绕资料提问，查看引用、相关知识点和追问建议。
5. 在智能体模式下提出复合目标，观察工具选择、任务事件和最终产物。
6. 生成练习并提交答案，查看批改、错题、掌握度和诊断。
7. 查看课程画像、长期记忆、学习路径与下一步推荐。
8. 触发自进化分析，检查策略证据、风险等级、实际变更和回滚链。

## 本地验证

```bash
cd backend
python -m pytest -q --maxfail=1
python -m alembic upgrade head

cd ../frontend
npm run typecheck
npm run build
```

Windows 环境也可以使用：

```powershell
scripts/local_check.ps1 -Database
scripts/local_check.ps1 -Backend
scripts/local_check.ps1 -Frontend
scripts/local_check.ps1 -MainChain
scripts/local_check.ps1 -AgentDemo
```

真实 LLM 主链路和 Agent Demo 会产生外部调用或要求后台服务，不包含在普通日常检查中。

## 项目结构

```text
zhixue/
├── frontend/                     # Next.js 学生端
│   ├── app/                      # 路由入口
│   ├── components/               # React 组件
│   ├── services/                 # API 服务
│   └── public/stitch-pages/      # 已接入真实 API 的视觉页面
├── backend/
│   ├── app/api/v1/               # FastAPI 路由
│   ├── app/agent_runtime/        # LangGraph 状态图与运行时
│   ├── app/agents/               # 领域 Agent
│   ├── app/services/             # 业务流程
│   ├── app/repositories/         # 数据访问
│   ├── app/rag/                  # 文档处理与检索
│   ├── app/llm/                  # LLM Provider 抽象
│   ├── alembic/                  # 数据库迁移
│   └── tests/                    # 后端测试
├── third_party/openmaic/         # 二次开发的沉浸课堂引擎
├── data/                         # 课程知识库与示例资料
├── docs/                         # 设计、事实源、测试与运行文档
├── scripts/                      # 检查、验收和数据维护脚本
└── .env.example
```

## 当前实现边界

README 只描述当前代码和已有验收证据。以下事项仍需要继续完善：

- 当前聚焦学生端，未建设教师端和管理员后台。
- LangGraph 智能体模式要求真实 LLM Provider；普通生成链路可以使用 Mock。
- Docker 全栈、全站浏览器 E2E 和真实 Provider 全模态矩阵仍需补齐正式验收。
- Grounded QA 的检索召回较稳定，但严格引用精度与引用覆盖率仍有提升空间。
- Agent Review 结果目前尚未形成完整的阻断路由分支。
- 写库工具仍存在“业务已写入、结果未保存”窗口下的重试副作用风险。
- 公有课程资料写权限、媒体 URL Token、SSE 订阅窗口等安全与一致性问题仍在修复计划中。
- 部分学生端页面仍通过 `StitchFrame` 承载，并非全站 React 组件化。

更多风险、测试口径与未完成项见[当前实现基线](docs/当前实现基线.md#当前明确未实现或未完成)和[全面代码评估问题修复计划](docs/19_测试方案/26_全面代码评估问题修复计划.md)。

## 文档导航

- [当前实现基线](docs/当前实现基线.md)：实际能力、规模、验收证据与已知限制
- [当前 API 清单](docs/当前实现API清单.md)：从 FastAPI 自动导出的 147 个 HTTP 操作
- [当前数据库清单](docs/当前实现数据库清单.md)：从 SQLAlchemy metadata 自动导出的 44 张表
- [测试方案与验收入口](docs/19_测试方案/19_测试方案.md)
- [本地与部署说明](docs/20_部署方案/20_部署方案.md)
- [系统架构设计](docs/_archive/设计文档/06_系统架构设计/06_系统架构设计.md)：历史设计参考
- [多智能体架构](docs/_archive/设计文档/07_多智能体架构设计/07_多智能体架构设计.md)：历史设计参考
- [自进化学习智能体](docs/_archive/设计文档/08_自进化学习智能体设计/08_自进化学习智能体设计.md)：历史设计参考
- [LLM Wiki 学习空间](docs/_archive/设计文档/09_LLM_Wiki学习空间设计/09_LLM_Wiki学习空间设计.md)：历史设计参考
- [完整文档索引](docs/README.md)

## 开源组件说明

沉浸课堂能力基于开源项目 OpenMAIC 进行二次开发。`third_party/openmaic` 保留了 AGPL-3.0 许可证、上游仓库、基线 commit 和本项目改动说明。智学工坊负责用户与课程上下文、RAG 引用、学生画像、任务编排、产物管理和媒体导出；OpenMAIC 负责课堂场景生成与播放。

## 项目背景

项目最初源于中国软件杯 A3 赛题，后续按照可运行的 AI 学习产品持续工程化：从一次性内容生成扩展为带课程知识库、持久状态、可观测 Agent 过程、个性化反馈和明确风险边界的完整学习系统。
