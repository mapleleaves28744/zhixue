# 智学工坊

智学工坊是面向中国软件杯 A3 赛题的个性化学习空间项目，围绕高校课程资料构建完整学生端学习闭环：

```text
注册登录
  → 创建课程
  → 上传资料
  → 解析、切片、向量化
  → 知识点抽取与 LLM Wiki 生成
  → RAG 检索与 AI Tutor 答疑
  → 个性化学习资源生成
  → 练习生成、答题与批改
  → 学习诊断与推荐
  → 学习路径、长期记忆与自进化策略
```

当前版本聚焦**学生端可演示主链路**。教师端、管理员端和 AI 重新美化前端阶段已冻结/跳过；前端保留 Stitch 静态视觉原型，并通过真实后端 API 接入数据。

判断当前项目实际能力时，优先阅读：

- `docs/当前实现基线.md`
- `docs/11_API接口设计/16_当前实现API清单.md`
- `docs/10_数据库设计/15_当前实现数据库清单.md`

早期 PRD 和设计方案用于表达目标与约束，不代表其中所有接口、页面或增强能力均已实现。

## 当前状态

- 学生端主链路已用真实本地数据库、后端、前端跑通过。
- 前端构建路由只保留：`/`、`/home`、`/courses`、`/knowledge`、`/assistant`、`/practice`、`/dashboard`、`/path-profile`、`/evolution`、`/login`、`/register`。
- 不再建设 `/teacher/*`、`/admin/*` 或旧 React `/student/*` 页面。
- 无真实 LLM Key 时可用 Mock Provider；配置 OpenAI-compatible Provider 后可调用真实模型。
- 2026-06-06 已使用真实 `xiaomi_mimo / mimo-v2.5` 完成资料上传到 Agent 日志的 23 步主链路验收，未回退 Mock。
- `/assistant` 已 React 化（快速 Tutor SSE + LangGraph 智能体）；Supervisor 采用 LLM 主导、规则安全网决策模型。
- `/assistant` 支持一句话生成基于课程 RAG、画像和薄弱点的 OpenMAIC 个性化沉浸课堂，并异步导出带配音、烧录字幕的 MP4 知识点讲解视频。
- 前端已从存在高危公告的 Next.js 14.2.35 升级至 Next.js 16.2.7，`npm audit` 为 0 vulnerabilities。

最近一次本地验收：

```powershell
cd backend
python -m pytest -q --maxfail=1
# 323 passed；DEF-012～015 修复后全量回归

python -m alembic upgrade head
# OK

cd ..\frontend
npm run typecheck
# OK

npm run build
# OK

npm audit --audit-level=moderate
# 0 vulnerabilities

cd ..
python scripts/export_implementation_docs.py
# 同步当前 API 与数据库文档
```

真实 LLM 主链路专项记录见 `docs/19_测试方案/13_真实LLM主链路与Next安全专项验收记录.md`。
本轮全量扫描、浏览器验收和缺陷闭环见 `docs/19_测试方案/20_全量功能扫描与浏览器验收报告.md` 与 `21_缺陷清单与修复闭环记录.md`。

## 比赛材料

队友准备 PPT、视频、Word 文档请从以下入口开始：

- [**智学工坊比赛材料合集**](docs/22_比赛材料规划/智学工坊比赛材料合集.md) — 需求/架构/功能/测试/用户/AI Coding 全文（**AI 一键阅读**）
- [比赛提交总览](docs/22_比赛材料规划/00_比赛提交总览.md) — 赛题映射、分工、检查清单
- [文档索引](docs/README.md) — 比赛 / 事实源 / 设计参考分区

Markdown 为源文件，转 Word 时从合集按章复制；维护源材料见 `docs/_archive/competition_sources/`。

## 技术栈

- Frontend：Next.js App Router、TypeScript、Tailwind CSS、Stitch 静态页面承载
- Backend：FastAPI、SQLAlchemy、Alembic、Pydantic
- Database：PostgreSQL、pgvector
- Cache：Redis
- AI：统一 LLM Provider、OpenAI-compatible Adapter、Mock Provider、Embedding Provider
- Deployment：Docker Compose 预留，当前开发和演示优先本地运行

## 本地环境

推荐使用本机 PostgreSQL / Redis，不要在日常开发中依赖 Docker 内的数据库。

**队友首次上手**请直接阅读：[队友本地开发 README](docs/20_部署方案/05_队友本地开发README.md)（含从演示服务器同步数据库的一键步骤）。

`.env` 关键配置：

```env
DATABASE_URL=postgresql+asyncpg://zhixue:zhixue_password@localhost:5432/zhixue
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=change-me

# 无 Key 可用 mock；有 OpenAI-compatible 服务时可改成 openai-compatible
LLM_PROVIDER=mock
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL_NAME=
```

前端 `.env.local` 默认可指向：

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

如果本机 `8000` 被旧进程占用，可以把后端开在 `8010`，并通过页面 URL 的 `api_base` 参数覆盖：

```text
http://127.0.0.1:3000/register?api_base=http%3A%2F%2F127.0.0.1%3A8010%2Fapi%2Fv1
```

登录/注册页会把该 API 地址写入浏览器本地存储，后续 Stitch 页面会沿用同一个后端地址。

## 启动步骤

### 0. Phase 3.1 Agent 稳定演示快速启动

推荐比赛演示前使用脚本统一启动后端、Agent Worker 和前端，避免页面连到旧后端或旧 Worker：

```powershell
scripts/start_phase31_demo.ps1
```

脚本默认使用：

```text
Backend:  http://127.0.0.1:8000
Frontend: http://127.0.0.1:3000
OpenMAIC: http://127.0.0.1:3001
Agent:    arq Worker
```

如果端口被占用，脚本会提示 PID，不会自动杀进程。可以改端口：

```powershell
scripts/start_phase31_demo.ps1 -BackendPort 8002 -FrontendPort 3002 -OpenMAICPort 3001
```

如果检测到已有 `arq app.workers.agent_worker.WorkerSettings` 进程，脚本默认会拒绝继续启动。原因是新旧 Worker 会共享同一个 Redis 队列，旧代码 Worker 可能抢走新任务，导致 `/assistant` 页面或 `agent_demo_check.py` 长时间等待。确认已有 Worker 就是当前分支版本时，才使用：

```powershell
scripts/start_phase31_demo.ps1 -AllowExistingWorker
```

稳定性冒烟验收：

```powershell
python scripts/agent_demo_check.py --base-url http://127.0.0.1:8000/api/v1
```

启动脚本会在本次进程内生成 OpenMAIC 内部令牌和播放签名密钥，并把根 `.env` 的 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_NAME` 映射到 Xiaomi MiMo、TTS 和 ASR 配置；不会写回或打印密钥。服务器部署应显式配置稳定的 `OPENMAIC_INTERNAL_TOKEN` 与 `OPENMAIC_SIGNING_SECRET`。

### 1. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Phase 3.1 的 `/assistant` 统一 Agent 入口还需要单独启动后台 worker：

```powershell
cd backend
python -m arq app.workers.agent_worker.WorkerSettings
```

若 `8000` 被占用：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

检查：

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

或把端口替换为 `8010`。

### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

访问：

```text
http://127.0.0.1:3000
```

## 学生端演示流程

推荐从注册页开始：

```text
http://127.0.0.1:3000/register
```

如果后端使用 `8010`：

```text
http://127.0.0.1:3000/register?api_base=http%3A%2F%2F127.0.0.1%3A8010%2Fapi%2Fv1
```

完整演示路径：

1. `/register`：注册学生账号，进入课程空间。
2. `/courses`：创建课程，例如“数据结构演示课”。
3. `/knowledge`：上传 `.txt` / `.md` / `.pdf` / `.docx` 资料。
4. `/knowledge`：依次执行解析、切片、向量化、抽取知识点、生成 Wiki。
5. `/knowledge`：使用“检索资料”验证 RAG 检索结果。
6. `/assistant`：围绕课程资料提问，例如“请解释栈和队列的区别，并引用课程资料。”
7. `/assistant`：用自然语言更新画像，例如“我是软件工程大二学生，递归薄弱，喜欢 Python 代码示例和分步骤讲解，请记住我的学习偏好。”
8. `/path-profile`：查看对话式画像证据。
9. `/assistant`：生成学习资源，例如例题、总结或复习卡。
10. `/assistant`：输入“为广度优先搜索一键生成个性化沉浸课堂和讲解视频”，观察 Agent 进度，进入 OpenMAIC 课堂并等待配音字幕 MP4 产物。
11. `/practice`：生成练习题，选择答案并提交，查看自动批改。
12. `/practice`：打开诊断报告，生成学习诊断并刷新推荐。
13. `/dashboard`：查看课程数、Wiki 数、Agent 运行数、今日任务和推荐。
14. `/path-profile`：生成学习路径，触发长期记忆反思，触发自进化策略分析。

演示建议资料内容可用一份简单的《数据结构》文本，例如：

```text
第一章 线性表
线性表是由零个或多个数据元素组成的有限序列。顺序表适合随机访问，链表适合频繁插入删除。

第二章 栈与队列
栈是只允许在一端进行插入和删除的线性表，遵循后进先出。队列在队尾插入、队头删除，遵循先进先出。

第三章 树与二叉树
二叉树每个结点最多有两个孩子。遍历方式包括前序、中序、后序和层序。

第四章 图
图由顶点和边组成，常见遍历方法有深度优先搜索和广度优先搜索。Dijkstra 算法用于求单源最短路径。
```

## 本地验收命令

可以单独运行：

```powershell
cd backend
python -m pytest -q --maxfail=1
python -m alembic upgrade head

cd ..\frontend
npm run typecheck
npm run build
```

也可以使用项目脚本：

```powershell
scripts/local_check.ps1 -Database
scripts/local_check.ps1 -Backend
scripts/local_check.ps1 -Frontend
scripts/local_check.ps1 -OpenMAIC
scripts/local_check.ps1 -MainChain
scripts/local_check.ps1 -AgentDemo
```

说明：

- `-Backend` 会运行后端 pytest 和 FastAPI import check。
- `-Database` 会运行 Alembic migration。
- `-Frontend` 会运行 TypeScript 检查和 Next.js build。
- `-OpenMAIC` 会运行内部鉴权测试和 OpenMAIC 生产构建。
- `-MainChain` 要求后端已启动且配置真实 LLM Provider；会创建隔离测试账号并执行完整真实生成链路，回退 Mock 时直接失败。
- `-AgentDemo` 要求后端和 arq Worker 已启动；会验证 `/assistant` 统一 Agent 入口、工具事件、对话式画像和学习路径生成。
- `-All` 不包含真实 LLM 主链路，避免日常检查意外消耗 API 配额。
- Docker 只作为第21阶段或部署专项验收，不作为当前学生端功能开发的前置条件。

## 常见问题

### 1. 前端连到了错误后端

如果 `.env.local` 指向 `8000`，但当前真实后端在 `8010`，请用：

```text
http://127.0.0.1:3000/register?api_base=http%3A%2F%2F127.0.0.1%3A8010%2Fapi%2Fv1
```

或者在浏览器控制台清理旧地址：

```js
localStorage.removeItem("zhixue_api_base")
```

### 2. 端口被旧进程占用

PowerShell 查看端口：

```powershell
Get-NetTCPConnection -LocalPort 3000,8000,8010 -ErrorAction SilentlyContinue |
  Select-Object LocalPort,State,OwningProcess
```

停止指定进程：

```powershell
Stop-Process -Id <PID> -Force
```

### 3. 没有真实 LLM Key

把 `LLM_PROVIDER=mock`，系统仍应能演示 Wiki、Tutor、资源、练习、诊断、自进化等主流程。Mock 输出不是最终效果，但用于保证主链路不因 Key 缺失中断。

### 4. 资料页切片或向量数为 0

确认已经按顺序执行：

```text
上传资料 → 解析资料 → 切片 → 向量化 → 抽取知识点 → 生成 Wiki
```

刷新 `/knowledge` 后，资料详情应显示真实 `Chunks` 和 `Embeddings` 计数。

## Docker 说明

Docker Compose 仍保留为后续部署目标。进入部署专项时，容器内环境应使用：

```env
DATABASE_URL=postgresql+asyncpg://zhixue:zhixue_password@postgres:5432/zhixue
REDIS_URL=redis://redis:6379/0
OPENMAIC_ENABLED=true
OPENMAIC_BASE_URL=http://openmaic:3000
OPENMAIC_PUBLIC_BASE_URL=https://your-domain.example:3001
OPENMAIC_INTERNAL_TOKEN=replace-with-a-long-random-service-token
OPENMAIC_SIGNING_SECRET=replace-with-a-different-long-random-signing-secret
XIAOMI_API_KEY=...
XIAOMI_BASE_URL=...
XIAOMI_MODELS=mimo-v2.5
DEFAULT_MODEL=xiaomi:mimo-v2.5
TTS_XIAOMI_MIMO_API_KEY=...
TTS_XIAOMI_MIMO_BASE_URL=...
ASR_XIAOMI_MIMO_API_KEY=...
ASR_XIAOMI_MIMO_BASE_URL=...
```

启动：

```powershell
docker compose -f docker-compose.prod.yml up -d --build
```

当前 `docker-compose.prod.yml` 会同时启动 `postgres`、`redis`、`openmaic`、`backend`、`worker`、`frontend` 和 `nginx`。其中 OpenMAIC 默认映射宿主机 `3001`，便于像本地一样直接访问：

```text
http://server-ip:3001/api/health
```

当前阶段若 Docker 与本地运行结果冲突，优先保证本地学生端主链路可用。更完整的服务器变量与启动说明见 [20_部署方案.md](docs/20_部署方案/20_部署方案.md) 和 [06_OpenMAIC沉浸课堂本地运行指南.md](docs/20_部署方案/06_OpenMAIC沉浸课堂本地运行指南.md)。

## 目录结构

```text
zhixue/
├── backend/                          # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/                   # 学生端业务 API
│   │   ├── agents/                   # 多智能体编排
│   │   ├── core/                     # 配置、异常、响应、鉴权依赖
│   │   ├── db/                       # 数据库会话
│   │   ├── llm/                      # LLM Provider 与日志
│   │   ├── models/                   # SQLAlchemy Model
│   │   ├── repositories/             # Repository 层
│   │   ├── schemas/                  # Pydantic Schema
│   │   ├── services/                 # Service 层
│   │   └── rag/                      # 切片、Embedding、检索
│   ├── alembic/                      # 数据库迁移
│   └── tests/                        # 后端测试
├── frontend/                         # Next.js 前端
│   ├── app/                          # StitchFrame 页面入口
│   ├── components/                   # 通用组件
│   ├── lib/                          # API URL、鉴权、请求工具
│   ├── public/stitch-pages/          # 当前学生端主界面
│   ├── services/                     # 当前保留的 React 登录/课程等服务
│   └── types/                        # TypeScript 类型
├── data/                             # 演示资料和种子知识库预留
├── docs/                             # 设计、测试、演示与答辩文档
├── scripts/                          # 本地检查与后续数据脚本
├── docker-compose.yml
├── .env.example
└── README.md
```

## 当前展示重点

- LLM Wiki：资料生成知识点页面，保留来源、版本和关系。
- AI Tutor：基于课程资料与 Wiki 回答，展示引用和相关知识点。
- 资源生成：Resource Agent 生成讲解、总结、例题、复习卡，并经过 Review Agent 校验。
- 练习诊断：生成题目、提交答案、自动批改、形成诊断报告。
- 推荐与学习路径：基于诊断、路径、Wiki 和行为日志生成下一步任务。
- 长期记忆与自进化：Memory Agent 生成学习记忆，Evolution Agent 生成可确认、可追溯的策略建议。
- 个性化沉浸课堂：智学工坊负责 RAG/画像/权限/任务编排，仓库内二次开发的 OpenMAIC 负责场景与播放，完成后继续生成带配音字幕的 MP4。

## OpenMAIC 来源与比赛表述

本项目没有把 OpenMAIC 描述为自研原始项目。仓库在 `third_party/openmaic` 保留其 AGPL-3.0 许可证、上游仓库、基线 commit 和本项目改动说明。推荐答辩表述：

> 智学工坊参考并二次开发了开源 OpenMAIC 的沉浸课堂生成能力，将其封装为受控课堂引擎；我们的核心工作是把课程 RAG 引用、学生画像与薄弱点、多智能体任务编排、用户权限隔离、课堂产物管理，以及 MiMo 配音字幕 MP4 导出整合成可追溯的个性化学习闭环。
