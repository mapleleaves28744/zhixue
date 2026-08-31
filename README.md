# 智学工坊 Zhixue Workshop

> 从课程资料出发，构建可追溯、会适应学习者的 AI 学习空间。

[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs)](frontend/package.json)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](backend/requirements.txt)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.x-1C3C3C)](backend/requirements.txt)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql)](docs/当前实现数据库清单.md)
[![Tests](https://img.shields.io/badge/pytest-503%20passed-2E8B57?logo=pytest)](docs/当前实现基线.md)

智学工坊是一套面向高校课程的个性化学习系统。它将学生上传的 PDF、Word、Markdown 等课程资料处理为可检索的知识库与 LLM Wiki，再把答疑、资源生成、练习、诊断、学习路径和长期画像连接成一个持续反馈的学习闭环。

项目关注的不是“再做一个聊天框”，而是解决三个更具体的工程问题：

- **回答如何可信**：Tutor 的关键结论绑定真实资料切片与 Wiki 来源，以 `[S1]` 等引用标记返回，并对无依据回答进行校验。
- **个性化如何持续**：系统从问答、练习和诊断中沉淀有证据的课程画像与长期记忆，让后续解释风格、难度和推荐随学习过程变化。
- **智能体如何可控**：LangGraph 运行时只允许调用集中注册的业务工具，完整记录计划、工具调用、观察、重规划和 Review；策略更新可版本化、可审核、可回滚。

## 产品界面

| AI Tutor 与 Agent 过程 | 课程知识库与资料处理 |
|---|---|
| ![AI Tutor](frontend/public/stitch-screenshots/assistant.png) | ![课程知识库](frontend/public/stitch-screenshots/knowledge.png) |

![学习仪表盘](frontend/public/stitch-screenshots/dashboard.png)

## 核心学习闭环

```text
上传课程资料
  → 解析、切片与向量化
  → 知识点抽取、知识图谱与 LLM Wiki
  → 基于来源的 AI Tutor / 个性化资源
  → 练习、批改、错题与学习诊断
  → 学生画像、长期记忆与掌握度更新
  → 学习路径、推荐与自进化策略
```

### 1. 可追溯的课程知识空间

- 支持 PDF、DOCX、TXT、Markdown 资料上传、解析、切片和 Embedding。
- 使用 pgvector 实现课程范围内的向量检索，并结合关键词、元数据过滤、轻量重排和来源多样性组成 Hybrid RAG。
- 从资料中抽取细粒度知识点，组织为知识图谱和 LLM Wiki。
- Wiki 页面保留来源、版本和关系；编辑、AI 补全与回滚不会覆盖历史内容。

### 2. Grounded AI Tutor

- 快速模式通过 SSE 流式返回基于课程资料的回答、引用、相关知识点和追问建议。
- 资料与 Wiki 证据保留真实来源 ID，回答中的引用会经过规则校验。
- 支持反馈、保存回答到 Wiki、会话恢复、停止生成和多会话切换。
- 可从自然语言中提取专业、年级、学习目标、薄弱点和解释偏好，并以证据形式更新画像。

### 3. 动态多智能体运行时

- 基于 LangGraph 构建 `load_context → supervisor → execute_tool → observe → replan/review → memory_reflect → finalize` 状态图。
- Supervisor 根据用户目标动态选择候选工具；Tool Registry 统一控制工具权限、参数和调用边界。
- Agent 任务、步骤、事件、对话与 checkpoint 持久化，支持后台执行、SSE 进度、取消、确认和恢复。
- 15 个领域 Agent 覆盖知识、Wiki、Tutor、资源、练习、诊断、推荐、画像、记忆和策略演化等职责。

### 4. 有证据的个性化与受控自进化

- 全局画像与课程画像分离，避免不同课程的掌握度和薄弱点互相覆盖。
- 练习结果驱动知识点掌握度更新；无有效证据时使用中性先验并明确标记“待验证”。
- 长期记忆带来源、置信度、显著性和强化次数，可查看、归档、恢复或删除。
- 自进化只调整问答风格、资源、难度、推荐和学习路径策略，不修改代码、权限或数据库结构。
- 每次策略变更记录前后快照、证据、风险等级和版本链；低风险变更可受控生效，中高风险需要确认，已应用策略可回滚。

### 5. 从文字回答到学习产物

- 可生成总结、例题、闪卡、思维导图、播客脚本和交互式 HTML 课件。
- 支持语音合成、语音识别、知识卡片和带字幕的讲解视频。
- 可基于课程 RAG、画像与薄弱点生成个性化沉浸课堂，并异步导出 MP4。
- 无真实模型 Key 时，普通 Wiki、Tutor、资源、练习和诊断链路可使用结构化 Mock Provider，便于本地开发与自动化测试。

## 系统架构

```mermaid
flowchart LR
    UI[Next.js 学生端] --> API[FastAPI /api/v1]
    API --> SVC[Service 业务层]
    SVC --> RAG[解析 / Embedding / Hybrid RAG]
    SVC --> RT[LangGraph Agent Runtime]
    RT --> REG[Tool Registry]
    REG --> DOMAIN[Wiki / Tutor / Quiz / Diagnosis / Profile]
    RT --> QUEUE[arq Worker]
    QUEUE <--> REDIS[(Redis)]
    SVC --> PG[(PostgreSQL + pgvector)]
    DOMAIN --> PG
    RAG --> PG
    SVC --> LLM[统一 LLM Provider]
    LLM --> MOCK[Mock Provider]
    LLM --> COMPAT[OpenAI-compatible Provider]
    DOMAIN --> MEDIA[OpenMAIC / 本地媒体渲染]
```

后端采用模块化单体，主调用链保持为：

```text
Router → Service → Repository → SQLAlchemy Model → PostgreSQL
Router → Service → Agent Runtime → Tool / Service → Repository
```

这种结构让鉴权、事务、模型调用和智能体决策保持在明确边界内，也便于为每层编写独立测试。

## 技术栈

| 层级 | 主要技术 |
|---|---|
| Web | Next.js 16、React 18、TypeScript、Tailwind CSS、Framer Motion |
| API | FastAPI、Pydantic、SQLAlchemy 2、Alembic |
| Agent | LangGraph 1.x、集中式 Tool Registry、arq 后台任务 |
| Data | PostgreSQL、pgvector、Redis、PostgreSQL Checkpoint |
| AI | 统一 LLM Provider、OpenAI-compatible Adapter、Mock Provider、Sentence Transformers |
| Content | 文档解析、Hybrid RAG、LLM Wiki、知识图谱、OpenMAIC |
| Quality | pytest、类型检查、Next.js Build、自动生成 OpenAPI/ORM 事实清单 |

## 工程规模与验证

以下数字来自当前实现清单与最近一次完整回归基线：

| 指标 | 当前记录 |
|---|---:|
| FastAPI HTTP 操作 | 147 |
| SQLAlchemy ORM 表 | 44 |
| Alembic migrations | 25 |
| Agent 类 / 注册工具 | 15 / 24 |
| 后端测试 | 503 passed |
| 真实 LLM 主链路 | 23 步通过 |
| 真实 MiMo Agent 场景 | 20 个场景，工具选择准确率 100%，任务完成率 95% |

完整口径、日期与限制以[当前实现基线](docs/当前实现基线.md)和[测试记录](docs/19_测试方案/13_真实LLM主链路与Next安全专项验收记录.md)为准。仓库同时维护由 OpenAPI 和 SQLAlchemy metadata 自动导出的 [API 清单](docs/当前实现API清单.md)与[数据库清单](docs/当前实现数据库清单.md)，避免设计文档与代码事实漂移。

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- PostgreSQL 14+（需启用 pgvector）
- Redis 5+（旧版本可降级为 Pub/Sub 兼容模式）

推荐先在本机运行 PostgreSQL 和 Redis。复制配置模板并按本机环境修改：

```bash
cp .env.example .env
```

默认连接配置：

```env
DATABASE_URL=postgresql+asyncpg://zhixue:zhixue_password@localhost:5432/zhixue
REDIS_URL=redis://localhost:6379/0
LLM_PROVIDER=mock
EMBEDDING_PROVIDER=mock
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

打开 [http://127.0.0.1:3000](http://127.0.0.1:3000)，从注册、创建课程和上传资料开始体验。API 文档位于 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

更完整的 Windows 环境配置、数据同步和演示启动方式见[队友本地开发指南](docs/20_部署方案/05_队友本地开发README.md)。

## 典型体验路径

1. 注册账号并创建课程。
2. 上传一份课程资料，依次完成解析、切片、向量化和知识点抽取。
3. 生成带来源和版本记录的课程 Wiki，使用 RAG 检索验证资料召回。
4. 在 AI Tutor 中围绕资料提问，查看引用、相关知识点与 Agent 执行过程。
5. 生成个性化资源或练习，提交答案后查看批改、错题与诊断。
6. 查看课程画像、长期记忆、掌握度、学习路径和下一步推荐。
7. 触发自进化分析，检查策略证据、风险等级、物化结果和回滚链。

## 项目结构

```text
zhixue/
├── frontend/                 # Next.js 学生端与 Stitch 页面
├── backend/
│   ├── app/api/v1/          # FastAPI 路由
│   ├── app/agent_runtime/    # LangGraph 状态图与运行时
│   ├── app/agents/           # 领域 Agent
│   ├── app/services/         # 业务流程
│   ├── app/repositories/     # 数据访问
│   ├── app/rag/              # 文档处理与检索
│   ├── app/llm/              # LLM Provider 抽象
│   ├── alembic/              # 数据库迁移
│   └── tests/                # 后端测试
├── third_party/openmaic/     # 二次开发的沉浸课堂引擎
├── data/                     # 数据结构课程知识库与示例资料
├── docs/                     # 设计、事实源、测试与运行文档
├── scripts/                  # 检查、验收和数据维护脚本
└── .env.example
```

## 实现边界

为了让仓库描述与代码保持一致，以下能力仍处于待完善状态：

- 当前聚焦学生端，未建设教师端和管理员后台。
- LangGraph 智能体模式要求真实 LLM Provider；普通生成链路可以使用 Mock。
- Docker 全栈、全站浏览器 E2E 和真实 Provider 全模态矩阵仍需继续补齐正式验收。
- Grounded QA 的检索召回表现稳定，但严格引用精度与覆盖率仍有提升空间。
- 部分学生端页面仍由 Next.js `StitchFrame` 承载静态视觉页，并非全站 React 组件化。

更多已知风险与未完成项见[当前实现基线](docs/当前实现基线.md#当前明确未实现或未完成)。

## 文档导航

- [当前实现基线](docs/当前实现基线.md)：项目实际能力、规模、验收证据和已知限制
- [系统架构设计](docs/_archive/设计文档/06_系统架构设计/06_系统架构设计.md)：模块边界与数据流（历史设计参考）
- [多智能体架构](docs/_archive/设计文档/07_多智能体架构设计/07_多智能体架构设计.md)：Agent、工具和运行时设计（历史设计参考）
- [自进化学习智能体](docs/_archive/设计文档/08_自进化学习智能体设计/08_自进化学习智能体设计.md)：证据、风险、版本与回滚机制（历史设计参考）
- [LLM Wiki 学习空间](docs/_archive/设计文档/09_LLM_Wiki学习空间设计/09_LLM_Wiki学习空间设计.md)：页面、来源、版本和关系模型（历史设计参考）
- [测试方案](docs/19_测试方案/19_测试方案.md)：测试策略与验收记录入口
- [完整文档索引](docs/README.md)

## 开源组件说明

沉浸课堂能力基于开源项目 OpenMAIC 进行二次开发。`third_party/openmaic` 保留了 AGPL-3.0 许可证、上游仓库、基线 commit 和本项目改动说明。智学工坊负责用户与课程权限、RAG 引用、学生画像、任务编排、产物管理和媒体导出；OpenMAIC 负责课堂场景生成与播放。

## 项目背景

项目最初源于中国软件杯 A3 赛题，后续按可运行的 AI 学习产品持续工程化：从单次生成扩展为带知识库、持久状态、可观测 Agent 过程和个性化反馈闭环的完整系统。
