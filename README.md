# 智学工坊

智学工坊是面向中国软件杯 A3 赛题的个性化学习空间项目，目标是围绕高校课程资料构建从资料上传、知识库构建、LLM Wiki、AI Tutor、资源生成、练习诊断到自进化学习策略的完整闭环。

当前仓库处于项目初始化阶段，只包含可启动的前后端基础骨架、Docker Compose 编排和环境变量模板，尚未实现具体业务功能。

## 核心创新

- 自进化学习智能体：受控更新学生画像、学习偏好、薄弱知识点、推荐策略和 Prompt 参数，不自动修改源代码或部署配置。
- LLM Wiki 学习空间：把课程资料、问答、错题、资源和诊断沉淀为可追溯、可版本化、有关联关系的个人知识空间。
- 轻量多智能体协作：通过明确职责边界的 Agent 编排 Wiki、问答、资源、诊断、推荐和策略演化流程。

## 技术栈

- Frontend：Next.js App Router、TypeScript、Tailwind CSS
- Backend：FastAPI、Pydantic Settings
- Database：PostgreSQL / pgvector
- Cache：Redis
- AI：统一 LLM Provider 抽象，默认支持 Mock Provider 占位
- Deployment：Docker Compose

## 本地优先启动

当前阶段建议先使用本地开发环境把主链路跑通，Docker Compose 暂作为后续部署与演示目标。除非正在处理 Docker/部署任务，日常开发优先验证：

- 后端：本地 Python 虚拟环境 + FastAPI
- 前端：本地 Node.js + Next.js dev server
- 数据库：本机 PostgreSQL / Redis 服务
- LLM：`.env` 配置 OpenAI-compatible Provider；无 Key 时使用 Mock Provider

1. 复制环境变量：

```bash
cp .env.example .env
```

2. 确认本机数据库和缓存可用：

```env
DATABASE_URL=postgresql+asyncpg://zhixue:zhixue_password@localhost:5432/zhixue
REDIS_URL=redis://localhost:6379/0
```

Docker Compose 内部使用的 `postgres`、`redis` 主机名只用于 Docker 部署环境，日常本地开发不要写进本地 `.env`。

3. 启动后端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload
```

4. 启动前端：

```bash
cd frontend
npm install
npm run dev
```

5. 访问服务：

- 前端：http://localhost:3000
- 后端健康检查：http://localhost:8000/health
- 后端 OpenAPI：http://localhost:8000/docs

## Docker 启动

Docker Compose 用于后续部署、演示环境和第21阶段专项验收。如果本地链路尚未打通，不优先处理 Docker 问题。

进入 Docker 部署阶段时，再把容器内环境切换为：

```env
DATABASE_URL=postgresql+asyncpg://zhixue:zhixue_password@postgres:5432/zhixue
REDIS_URL=redis://redis:6379/0
```

```bash
docker compose up --build
```

- 前端：http://localhost:3000
- 后端健康检查：http://localhost:8000/health
- 后端 OpenAPI：http://localhost:8000/docs

## 本地验收

每个阶段完成后都要对照 `docs/19_测试方案/12_阶段运行验收清单.md` 做本地验收。基础检查脚本：

```powershell
scripts/local_check.ps1 -Database
scripts/local_check.ps1 -Backend
scripts/local_check.ps1 -Frontend
```

只有第21阶段 Docker 部署任务才强制 Docker 验收。

## 目录结构

```text
zhixue/
├── frontend/                         # Next.js 前端
│   ├── app/                          # App Router 页面入口
│   ├── components/                   # 可复用组件
│   ├── hooks/                        # React hooks
│   ├── lib/                          # 请求、工具函数等基础库
│   ├── public/                       # 静态资源
│   ├── stores/                       # 前端状态管理预留
│   ├── styles/                       # 全局样式
│   └── types/                        # TypeScript 类型定义
├── backend/                          # FastAPI 后端
│   ├── app/
│   │   ├── api/                      # API Router 预留
│   │   ├── agents/                   # 多智能体模块预留
│   │   ├── core/                     # 配置、异常、响应等基础能力
│   │   ├── db/                       # 数据库连接与迁移入口预留
│   │   ├── evolution/                # 自进化模块预留
│   │   ├── models/                   # SQLAlchemy Model 预留
│   │   ├── schemas/                  # Pydantic Schema 预留
│   │   ├── services/                 # 业务 Service 预留
│   │   └── wiki/                     # LLM Wiki 模块预留
│   └── tests/                        # 后端测试预留
├── data/
│   └── seed_knowledge/
│       └── data_structure/           # 《数据结构》初始课程资料预留
├── docs/                             # 项目设计文档
├── scripts/                          # 初始化、部署、数据导入脚本预留
├── docker-compose.yml
└── .env.example
```

## 当前状态

- 已创建基础目录结构。
- 前端可运行最小 Next.js 页面。
- 后端可运行 FastAPI 健康检查接口。
- Docker Compose 已预留 PostgreSQL、Redis、backend、frontend。
- 未创建业务模型、业务接口、Agent、Wiki、RAG 或自进化实现。
