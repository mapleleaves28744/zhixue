# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

智学工坊——基于自进化学习智能体与 LLM Wiki 的个性化资源生成学习空间（中国软件杯 A3 赛题）。核心链路：课程资料上传 → 文档解析切片 → 向量知识库 → LLM Wiki → AI Tutor → 资源生成 → 练习诊断 → 学生画像 → 自进化策略。

## 常用命令

### 前端 (frontend/)
```bash
cd frontend
npm install
npm run dev          # 启动开发服务器 http://localhost:3000
npm run build        # 生产构建
npm run typecheck    # TypeScript 类型检查 (tsc --noEmit)
```

### 后端 (backend/)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload   # 启动开发服务器 http://localhost:8000
pytest                          # 运行测试
```

### Docker 全栈
```bash
cp .env.example .env
docker compose up --build
# 前端: http://localhost:3000
# 后端: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### 数据库迁移
```bash
cd backend
alembic upgrade head           # 执行迁移
alembic revision --autogenerate -m "描述"  # 生成迁移
```

## 架构要点

### 前端 (Next.js App Router)
- **路由**: `frontend/app/` 下按页面目录组织（student/, admin/, login/ 等）
- **组件**: `frontend/components/` 可复用 UI 组件（shadcn/ui 风格）
- **API 调用**: 统一通过 `frontend/lib/request.ts`，禁止页面内直接 fetch
- **服务层**: `frontend/services/` 封装业务 API 调用
- **类型定义**: `frontend/types/` TypeScript 类型
- **状态管理**: `frontend/stores/` 前端状态

### Stitch 页面转 Next.js（核心开发方式）

**重要：前端页面开发必须基于 Stitch 设计稿转换，禁止重新设计页面。**

当前状态：`frontend/app/*/page.tsx` 通过 `StitchFrame` 组件以 iframe 方式嵌入 `frontend/public/stitch-pages/*.html` 静态页面。

开发流程：

1. 查看 `frontend/public/stitch-pages/` 对应的 HTML 文件了解页面结构和样式
2. 参考 `docs/DESIGN.md` 中的 "Luminous Warmth" 设计系统（Glassmorphism 风格）
3. 将静态 HTML 转换为 Next.js 组件：提取结构、样式、交互逻辑
4. 替换 `StitchFrame` iframe 为真正的 React 组件
5. 接入 API 服务层实现数据动态化

Stitch 页面清单：

- `home.html` → 首页
- `dashboard.html` → 学习仪表盘
- `courses.html` → 课程列表
- `knowledge.html` → LLM Wiki 知识空间
- `assistant.html` → AI Tutor 答疑
- `practice.html` → 练习与错题
- `path-profile.html` → 学习路径/画像
- `brand-home.html` → 品牌介绍页

无论是转换现有 Stitch 页面还是新增页面，都必须严格遵循 `docs/DESIGN.md` 中的 Luminous Warmth 设计系统，确保全站风格统一。

### 后端 (FastAPI)
- **分层**: API Router → Service → Repository → Model → Database
- **API 路由**: `backend/app/api/v1/` 所有业务接口，统一前缀 `/api/v1`
- **核心配置**: `backend/app/core/config.py` Pydantic Settings，从 `.env` 读取
- **统一响应格式**: `{ code: 0, message: "success", data: {}, request_id: "req_xxx" }`
- **异常处理**: `backend/app/core/exceptions.py` 统一异常体系
- **LLM 调用**: 必须通过 `backend/app/llm/provider.py`，无 API Key 时用 Mock Provider
- **Agent**: `backend/app/agents/` 多智能体模块，继承 BaseAgent，使用 AgentContext/AgentResult
- **数据库**: PostgreSQL + pgvector，迁移用 Alembic

### 关键设计约束
- Agent 不得直接修改数据库，必须通过 Service 层
- Wiki 页面必须保留来源追溯和版本管理（wiki_page_versions 表）
- 自进化策略必须可回滚、有证据、有风险等级
- 前端 UI 风格：柔和渐变、卡片式、大圆角、教育科技感，禁止普通后台模板风格
- 所有 AI 生成内容必须有来源标注，无依据时明确说明

### 数据库表名约定
- 资料表: `course_materials`
- Wiki 关系: `wiki_links`
- 自进化策略: `evolution_strategies`
- Agent 运行日志: `agent_runs`
- LLM 调用日志: `llm_call_logs`

## 开发任务

任务拆分在 `docs/Codex开发任务拆分.md`，按阶段执行。当前进度在第5阶段（课程与资料管理）。执行任务前必须阅读对应设计文档（docs/ 目录下）。

## stitch-pages

`frontend/public/stitch-pages/` 包含 Stitch 设计工具导出的静态 HTML 原型页面，用于 UI 参考，非运行时代码。

## 编码原则

1. **先想后写** — 有歧义就问，不要默默假设。列出多个方案的利弊再动手。
2. **简单优先** — 能 100 行写完就别写 1000 行。不加未要求的抽象、配置、容错。
3. **精准改动** — 只改任务要求的部分。不顺手重构、不优化无关代码、不删除已有死代码。
4. **目标驱动** — 先明确验收标准，写完代码后验证通过再提交。
