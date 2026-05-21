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

## 本地启动

1. 复制环境变量：

```bash
cp .env.example .env
```

2. 启动基础依赖和应用：

```bash
docker compose up --build
```

3. 访问服务：

- 前端：http://localhost:3000
- 后端健康检查：http://localhost:8000/health
- 后端 OpenAPI：http://localhost:8000/docs

也可以分别本地启动：

```bash
cd frontend
npm install
npm run dev
```

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

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
