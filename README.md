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

## 当前状态

- 学生端主链路已用真实本地数据库、后端、前端跑通过。
- 前端构建路由只保留：`/`、`/home`、`/courses`、`/knowledge`、`/assistant`、`/practice`、`/dashboard`、`/path-profile`、`/login`、`/register`。
- 不再建设 `/teacher/*`、`/admin/*` 或旧 React `/student/*` 页面。
- 无真实 LLM Key 时可用 Mock Provider；配置 OpenAI-compatible Provider 后可调用真实模型。

最近一次本地验收：

```powershell
cd backend
python -m pytest -q --maxfail=1
# 73 passed

python -m alembic upgrade head
# OK

cd ..\frontend
npm run typecheck
# OK

npm run build
# OK
```

`npm run build` 可能出现 Google Fonts 下载优化警告，不影响构建成功。

## 技术栈

- Frontend：Next.js App Router、TypeScript、Tailwind CSS、Stitch 静态页面承载
- Backend：FastAPI、SQLAlchemy、Alembic、Pydantic
- Database：PostgreSQL、pgvector
- Cache：Redis
- AI：统一 LLM Provider、OpenAI-compatible Adapter、Mock Provider、Embedding Provider
- Deployment：Docker Compose 预留，当前开发和演示优先本地运行

## 本地环境

推荐使用本机 PostgreSQL / Redis，不要在日常开发中依赖 Docker 内的数据库。

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

### 1. 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
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
7. `/assistant`：生成学习资源，例如例题、总结或复习卡。
8. `/practice`：生成练习题，选择答案并提交，查看自动批改。
9. `/practice`：打开诊断报告，生成学习诊断并刷新推荐。
10. `/dashboard`：查看课程数、Wiki 数、Agent 运行数、今日任务和推荐。
11. `/path-profile`：生成学习路径，触发长期记忆反思，触发自进化策略分析。

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
```

说明：

- `-Backend` 会运行后端 pytest 和 FastAPI import check。
- `-Database` 会运行 Alembic migration。
- `-Frontend` 会运行 TypeScript 检查和 Next.js build。
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
```

启动：

```powershell
docker compose up --build
```

当前阶段若 Docker 与本地运行结果冲突，优先保证本地学生端主链路可用。

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
