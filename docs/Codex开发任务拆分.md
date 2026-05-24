# 智学工坊 Codex 开发任务拆分
文档版本：V1.0  
适用位置：`docs/Codex开发任务拆分.md`  
项目名称：智学工坊——基于自进化学习智能体与 LLM Wiki 的个性化资源生成学习空间
---
# 0. 使用说明
本任务清单用于把项目交给 Codex 分阶段实现。每个任务都尽量控制在可独立完成、可验收、可回滚的粒度。执行原则如下：
1. 按阶段顺序执行，除非任务明确标为 P2 或无依赖；
2. P0 是主链路必须完成，P1 是比赛展示增强，P2 是冲奖增强或预留；
3. 每次只给 Codex 一个任务，不要一次性塞入多个阶段；
4. Codex 执行时必须严格限制修改范围，避免无关重构；
5. 每个任务完成后先运行本阶段可用的测试或启动检查，再进入下一任务；
6. 教师端按轻量课程内容维护端预留，不做完整班级、作业、成绩管理。
---
# 1. 阶段总览
| 阶段 | 目标 | 主要优先级 |
|---|---|---|
| 第1阶段：项目初始化 | 完成本阶段可验收功能 | P0:2 / P1:1 / P2:0 |
| 第2阶段：前端基础框架 | 完成本阶段可验收功能 | P0:4 / P1:1 / P2:0 |
| 第3阶段：后端基础框架 | 完成本阶段可验收功能 | P0:3 / P1:1 / P2:0 |
| 第4阶段：数据库与认证 | 完成本阶段可验收功能 | P0:4 / P1:0 / P2:0 |
| 第5阶段：课程与资料管理 | 完成本阶段可验收功能 | P0:3 / P1:2 / P2:0 |
| 第6阶段：RAG 知识库 | 完成本阶段可验收功能 | P0:3 / P1:2 / P2:0 |
| 第7阶段：LLM Wiki 学习空间 | 完成本阶段可验收功能 | P0:4 / P1:1 / P2:1 |
| 第8阶段：大模型接口封装 | 完成本阶段可验收功能 | P0:2 / P1:2 / P2:0 |
| 第9阶段：多智能体基础框架 | 完成本阶段可验收功能 | P0:4 / P1:0 / P2:0 |
| 第10阶段：学生画像与长期记忆 | 完成本阶段可验收功能 | P0:3 / P1:1 / P2:0 |
| 第11阶段：自进化策略系统 | 完成本阶段可验收功能 | P0:3 / P1:1 / P2:0 |
| 第12阶段：学习路径生成 | 完成本阶段可验收功能 | P0:0 / P1:3 / P2:0 |
| 第13阶段：学习资源生成 | 完成本阶段可验收功能 | P0:3 / P1:1 / P2:0 |
| 第14阶段：AI 答疑 | 完成本阶段可验收功能 | P0:2 / P1:2 / P2:0 |
| 第15阶段：练习题与错题本 | 完成本阶段可验收功能 | P0:3 / P1:1 / P2:0 |
| 第16阶段：学习诊断与推荐 | 完成本阶段可验收功能 | P0:3 / P1:1 / P2:0 |
| 第17阶段：教师端 | 完成本阶段可验收功能 | P0:0 / P1:0 / P2:3 |
| 第18阶段：管理员端 | 完成本阶段可验收功能 | P0:0 / P1:4 / P2:1 |
| 第19阶段：前端美化 | 完成本阶段可验收功能 | P0:0 / P1:3 / P2:1 |
| 第20阶段：测试 | 完成本阶段可验收功能 | P0:0 / P1:3 / P2:1 |
| 第21阶段：Docker 部署 | 完成本阶段可验收功能 | P0:3 / P1:1 / P2:0 |
| 第22阶段：演示数据 | 完成本阶段可验收功能 | P0:2 / P1:2 / P2:0 |
| 第23阶段：比赛材料 | 完成本阶段可验收功能 | P0:1 / P1:3 / P2:1 |

## 1.1 关键依赖修正

为避免后续实现顺序偏离主链路，以下依赖优先级高于阶段编号：

1. `T08-01` 统一 LLM Provider 基类和 Mock Provider 必须早于所有真实生成类任务，至少早于 `T07-03`、`T13-01`、`T14-01`、`T15-01`、`T16-01`、`T11-02`。
2. `T08-03` Prompt 版本读取和渲染应早于需要 Prompt 的 Agent 任务，至少早于 Wiki 生成、资源生成、Tutor、诊断和自进化分析。
3. `T09-01` 到 `T09-03` 的 Agent 基础框架应在具体 Agent 深度实现前完成；业务接口可以先直连 Service，但最终必须能写入 `agent_runs`。
4. 数据库表名以 `docs/10_数据库设计/数据库设计.md` 为准：资料表使用 `course_materials`，Wiki 关系使用 `wiki_links`，自进化策略使用 `evolution_strategies`。

## 1.2 前端实现路线修正：保留 Stitch 静态页并接入后端

当前前端已经完成 Stitch 视觉原型，后续所有前端任务必须默认采用：

```text
保留 Stitch 静态页面视觉与导航
  → 通过 StitchFrame 继续承载 frontend/public/stitch-pages/*.html
  → 在静态页内追加或维护少量页面脚本
  → 统一通过 frontend/public/stitch-pages/zhixue-static-api.js 调用 /api/v1 后端
  → 将原静态占位内容替换为真实 API 数据、真实空状态和真实错误提示
```

除非任务明确写明“将某个页面 React 组件化”并得到人工确认，否则禁止：

1. 用新的 React 页面重做 `/courses`、`/knowledge`、`/assistant`、`/practice`、`/dashboard`、`/path-profile` 的视觉结构；
2. 删除或重排既有 Stitch 导航栏、侧边栏、顶部栏和主要布局；
3. 新增一套与 Stitch 原型不一致的学生端 UI；
4. 让后端能力只停留在接口层而没有接入对应静态页面。

任务文档中历史提到的 `/student/wiki`、`/student/tutor`、`/student/resources`、`/student/quizzes`、`/student/diagnosis`、`/student/evolution` 等 React 页面路径，后续应优先作为功能清单参考，不作为默认新建页面要求。当前学生端功能应聚合到 7 个 Stitch 主入口中：

| 功能阶段 | 默认接入页面 | 接入方式 |
|---|---|---|
| 认证、用户信息 | `/`、`/login`、`/register` 对应 Stitch/首页脚本 | 保留品牌页登录注册弹窗，写入 token 和用户信息 |
| 课程 CRUD | `/courses` | 用课程卡片和创建弹窗调用 `/api/v1/courses` |
| 资料上传、解析、切片、向量化、知识点抽取、Wiki 生成 | `/knowledge` | 在原资料库面板追加按钮和真实状态，不改布局 |
| Wiki 页面、来源、版本、图谱 | `/knowledge` | 用原“课程 Wiki / 图谱视图”区域或局部面板展示 |
| Tutor 问答、引用、Agent 状态 | `/assistant` | 用原聊天区调用 Tutor API 并追加回答 |
| 资源生成 | `/assistant` 或 `/practice` 的资源面板 | 用原资源生成卡片调用 `/resources/generate` |
| 练习、答题、错题、诊断 | `/practice` | 用原练习/诊断 Tab 调用 Quiz 和 Diagnosis API |
| 画像、长期记忆、自进化策略、学习路径 | `/path-profile` | 用原画像、记忆、策略、路径卡片接入 API |
| 学习总览、推荐、最近动态 | `/dashboard` | 用原统计卡、任务、提醒、推荐卡接入 API |
| Agent 日志 | `/path-profile`、`/dashboard`，管理员端另行扩展 | 调用 `/api/v1/agents/runs` 展示调用链摘要 |

每个后端阶段完成后，必须同步检查对应 Stitch 页面是否已经接入真实 API。若未接入，不得宣称“阶段已完成”，只能说明“后端实现完成，前端 Stitch 联动未完成”。

---
# 第1阶段：项目初始化

## T01-01 创建 Monorepo 项目骨架

- **任务编号**：T01-01
- **任务名称**：创建 Monorepo 项目骨架
- **优先级**：P0
- **任务目标**：建立前后端、文档、数据、脚本、部署目录，形成统一项目结构。
- **涉及目录**：`项目根目录`
- **涉及文件**：`README.md, .gitignore, .env.example, frontend/, backend/, docs/, data/, scripts/, docker-compose.yml`
- **前置依赖**：无
- **具体实现要求**：输入：无。输出：完整项目目录骨架。创建根目录结构，补充 README 初版，写清楚项目名称、技术栈、启动方式占位；创建 .env.example，包含 DATABASE_URL、REDIS_URL、JWT_SECRET、LLM_PROVIDER、LLM_API_KEY、LLM_BASE_URL 等占位变量。
- **验收标准**：本地目录结构完整；README 可读；.env.example 字段齐全；前后端目录分离；不生成业务代码。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请在当前仓库创建智学工坊项目基础目录结构。只完成项目骨架，不实现业务功能。需要创建 frontend、backend、docs、data、scripts 等目录，补充 README.md、.gitignore、.env.example 和 docker-compose.yml 占位文件。README 写明项目名称、技术栈和后续启动方式占位。不要修改未提到的文件。
```

## T01-02 整理 docs 文档入口

- **任务编号**：T01-02
- **任务名称**：整理 docs 文档入口
- **优先级**：P0
- **任务目标**：让已有设计文档能被团队和 Codex 快速定位。
- **涉及目录**：`docs/`
- **涉及文件**：`docs/README.md, docs/index.md`
- **前置依赖**：T01-01
- **具体实现要求**：输入：已有 docs 文档。输出：docs 文档索引。创建 docs/README.md，按 PRD、系统架构、数据库、API、前端、UI、自进化、LLM Wiki、多智能体、部署、测试、比赛材料分类列出文档用途。
- **验收标准**：打开 docs/README.md 能快速找到各设计文档；文档路径与实际目录一致。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请为 docs 目录创建文档索引。新增 docs/README.md 和 docs/index.md，按模块列出本项目设计文档用途，包括 PRD、系统架构、数据库、API、前端页面、UI 规范、自进化、LLM Wiki、多智能体、测试、部署和比赛材料。不要写业务代码。
```

## T01-03 制定代码规范与提交规范

- **任务编号**：T01-03
- **任务名称**：制定代码规范与提交规范
- **优先级**：P1
- **任务目标**：统一团队和 Codex 后续代码风格。
- **涉及目录**：`项目根目录, docs/`
- **涉及文件**：`.editorconfig, docs/开发规范.md`
- **前置依赖**：T01-01
- **具体实现要求**：输入：项目技术栈。输出：基础开发规范。添加 .editorconfig；编写 docs/开发规范.md，规定前端组件命名、后端分层、API 响应格式、异常处理、数据库命名、Prompt 存放规则。
- **验收标准**：规范覆盖前端、后端、数据库、接口、Agent、Prompt；命名规则明确。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请新增项目开发规范。创建 .editorconfig 和 docs/开发规范.md，明确 Next.js、FastAPI、SQLAlchemy、API 响应、数据库命名、Agent 类、Prompt 文件的代码风格。只写规范，不实现业务。
```

---

# 第2阶段：前端基础框架

## T02-01 初始化 Next.js 前端工程

- **任务编号**：T02-01
- **任务名称**：初始化 Next.js 前端工程
- **优先级**：P0
- **任务目标**：搭建可运行的前端基础项目。
- **涉及目录**：`frontend/`
- **涉及文件**：`frontend/package.json, app/, tsconfig.json, next.config.js`
- **前置依赖**：T01-01
- **具体实现要求**：输入：技术栈要求。输出：可启动 Next.js App Router 项目。使用 TypeScript，创建 app/page.tsx、app/login/page.tsx、app/register/page.tsx。
- **验收标准**：npm install 后可运行；访问 /、/login、/register 不报错。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请在 frontend 目录初始化 Next.js App Router + TypeScript 项目结构。创建基础页面 /、/login、/register，确保 npm install 和 npm run dev 可运行。不要实现复杂业务，只放基础页面占位。
```

## T02-02 配置 Tailwind CSS 与 shadcn/ui

- **任务编号**：T02-02
- **任务名称**：配置 Tailwind CSS 与 shadcn/ui
- **优先级**：P0
- **任务目标**：建立统一 UI 基础能力。
- **涉及目录**：`frontend/`
- **涉及文件**：`tailwind.config.ts, app/globals.css, components/ui/*`
- **前置依赖**：T02-01
- **具体实现要求**：输入：UI 设计规范。输出：Tailwind 主题和 shadcn/ui 基础组件。配置品牌色、圆角、阴影、背景渐变；安装 Button、Card、Input、Dialog、Tabs、Badge、Dropdown、Textarea、Toast。
- **验收标准**：页面能使用 Tailwind；shadcn/ui 组件可正常导入；主题 token 与 UI 规范一致。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请为 frontend 配置 Tailwind CSS 和 shadcn/ui。按照 docs/UI设计规范.md 中的品牌色、圆角、阴影和渐变配置 tailwind.config.ts，并安装 Button、Card、Input、Dialog、Tabs、Badge、Textarea、Toast 等基础组件。不要写业务页面。
```

## T02-03 实现学生端与管理员端 Layout

- **任务编号**：T02-03
- **任务名称**：实现学生端与管理员端 Layout
- **优先级**：P0
- **任务目标**：建立学生端和管理员端统一布局。
- **涉及目录**：`frontend/app, frontend/components/layout`
- **涉及文件**：`app/student/layout.tsx, app/admin/layout.tsx, components/layout/StudentSidebar.tsx, StudentTopbar.tsx, AdminSidebar.tsx, AdminTopbar.tsx`
- **前置依赖**：T02-02
- **具体实现要求**：输入：前端页面设计。输出：可复用 Layout。学生端侧边栏包含 Dashboard、Wiki、Tutor、Resources、Quizzes、Diagnosis、Evolution 等入口；管理员端包含 Dashboard、Users、Agents、LLM Logs、Evolution、System。
- **验收标准**：访问 /student/dashboard 和 /admin/dashboard 可看到对应布局；侧边栏跳转正常。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现学生端和管理员端 Layout。创建 app/student/layout.tsx、app/admin/layout.tsx 和对应 Sidebar/Topbar 组件。侧边栏按 docs/前端页面设计.md 配置导航。先使用静态路由，不接 API。
```

## T02-04 实现前端请求封装与 Auth Store

- **任务编号**：T02-04
- **任务名称**：实现前端请求封装与 Auth Store
- **优先级**：P0
- **任务目标**：为后续页面调用 API 和鉴权做准备。
- **涉及目录**：`frontend/lib, frontend/stores, frontend/types`
- **涉及文件**：`lib/request.ts, lib/api.ts, lib/auth.ts, stores/authStore.ts, types/api.ts`
- **前置依赖**：T02-01
- **具体实现要求**：输入：API 接口设计。输出：统一 request 函数、ApiResponse 类型、Token 读写、authStore。处理 401、错误 toast、Authorization Bearer Header。
- **验收标准**：前端任意服务可复用 request；Token 可保存和清除；类型定义清晰。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现前端 API 请求封装和认证状态管理。新增 lib/request.ts、lib/auth.ts、stores/authStore.ts、types/api.ts，统一处理 JWT、ApiResponse、错误码和 401 跳转。不要写具体业务页面。
```

## T02-05 实现前端路由权限守卫

- **任务编号**：T02-05
- **任务名称**：实现前端路由权限守卫
- **优先级**：P1
- **任务目标**：根据用户角色限制访问 student/admin 路由。
- **涉及目录**：`frontend/`
- **涉及文件**：`middleware.ts, components/auth/RequireRole.tsx, lib/auth.ts`
- **前置依赖**：T02-04
- **具体实现要求**：输入：JWT 和用户角色。输出：路由保护。未登录访问 /student 或 /admin 跳转 /login；学生不能访问 /admin；管理员不能误入学生端时跳转 admin dashboard。
- **验收标准**：权限跳转符合预期；无 Token 不能进入受保护页面。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 Next.js 路由权限守卫。新增 middleware.ts 和 RequireRole 组件，根据 JWT 和 role 控制 /student/* 与 /admin/* 访问。未登录跳转 /login，角色不匹配跳转对应首页或 403 占位页。
```

---

# 第3阶段：后端基础框架

## T03-01 初始化 FastAPI 后端工程

- **任务编号**：T03-01
- **任务名称**：初始化 FastAPI 后端工程
- **优先级**：P0
- **任务目标**：建立可运行的后端基础服务。
- **涉及目录**：`backend/`
- **涉及文件**：`app/main.py, app/core/config.py, requirements.txt, Dockerfile`
- **前置依赖**：T01-01
- **具体实现要求**：输入：后端技术栈。输出：FastAPI 项目骨架。实现 /health 接口、CORS 配置、settings 配置读取。
- **验收标准**：uvicorn 可启动；GET /health 返回 success；CORS 支持前端本地地址。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请在 backend 目录初始化 FastAPI 项目。创建 app/main.py、app/core/config.py、requirements.txt，提供 /health 接口和 CORS 配置。使用 pydantic settings 读取环境变量。不要实现业务接口。
```

## T03-02 实现统一响应与异常处理

- **任务编号**：T03-02
- **任务名称**：实现统一响应与异常处理
- **优先级**：P0
- **任务目标**：统一 API 返回格式和错误码。
- **涉及目录**：`backend/app/core`
- **涉及文件**：`response.py, exceptions.py, error_codes.py`
- **前置依赖**：T03-01
- **具体实现要求**：输入：API 设计文档。输出：ApiResponse、分页响应、业务异常类、全局异常处理。统一返回 code、message、data、request_id。
- **验收标准**：正常和异常接口返回格式一致；错误码与 docs/API接口设计.md 对齐。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现后端统一响应和异常处理。新增 core/response.py、exceptions.py、error_codes.py，封装 success_response、page_response、BusinessException，并在 main.py 注册全局异常处理器。
```

## T03-03 建立模块化 Router 结构

- **任务编号**：T03-03
- **任务名称**：建立模块化 Router 结构
- **优先级**：P0
- **任务目标**：为后续接口开发提供清晰路由分层。
- **涉及目录**：`backend/app/api/v1`
- **涉及文件**：`router.py, auth.py, users.py, courses.py, materials.py, wiki.py, tutor.py, resources.py, quizzes.py, diagnosis.py, evolution.py, agents.py, admin.py`
- **前置依赖**：T03-01
- **具体实现要求**：输入：API 模块列表。输出：路由占位。每个模块有 APIRouter，占位 ping 接口或空 router，在 app/main.py 统一挂载 /api/v1。
- **验收标准**：OpenAPI 中可见模块路径；项目启动不报错。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请建立 FastAPI v1 路由模块结构。创建 app/api/v1/router.py 和各业务模块 router 文件，在 main.py 统一挂载 /api/v1。每个 router 先放一个简单占位接口，后续任务再实现业务。
```

## T03-04 建立 Service/Repository/Schema 目录

- **任务编号**：T03-04
- **任务名称**：建立 Service/Repository/Schema 目录
- **优先级**：P1
- **任务目标**：规定后端分层，避免业务写在路由里。
- **涉及目录**：`backend/app`
- **涉及文件**：`models/, schemas/, services/, repositories/, utils/`
- **前置依赖**：T03-03
- **具体实现要求**：输入：系统架构设计。输出：后端分层目录和基础 README。说明路由只做参数和响应，Service 写业务，Repository 写数据访问，Schema 写 Pydantic DTO。
- **验收标准**：目录清晰；后续任务有固定落点。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请创建后端分层目录 models、schemas、services、repositories、utils，并为每层添加简短 README 或 __init__.py 注释，明确职责。不要实现具体业务逻辑。
```

---

# 第4阶段：数据库与认证

## T04-01 配置 SQLAlchemy 与 Alembic

- **任务编号**：T04-01
- **任务名称**：配置 SQLAlchemy 与 Alembic
- **优先级**：P0
- **任务目标**：让后端能够连接 PostgreSQL 并管理迁移。
- **涉及目录**：`backend/app/db, backend/alembic`
- **涉及文件**：`app/db/session.py, app/db/base.py, alembic.ini, alembic/env.py`
- **前置依赖**：T03-01
- **具体实现要求**：输入：DATABASE_URL。输出：数据库会话、Base、Alembic 配置。支持 async 或 sync 二选一，建议 Async SQLAlchemy。
- **验收标准**：可执行 alembic revision/autogenerate；应用可创建数据库连接。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请为后端配置 SQLAlchemy 和 Alembic。创建 app/db/session.py、base.py，配置 DATABASE_URL，初始化 alembic。优先使用 SQLAlchemy 2.x 风格。不要创建业务表。
```

## T04-02 实现核心数据库模型首批

- **任务编号**：T04-02
- **任务名称**：实现核心数据库模型首批
- **优先级**：P0
- **任务目标**：落地认证和课程基础数据表。
- **涉及目录**：`backend/app/models, backend/alembic/versions`
- **涉及文件**：`models/user.py, course.py, profile.py, prompt.py, migration`
- **前置依赖**：T04-01
- **具体实现要求**：输入：数据库设计。输出：users、courses、student_profiles、learning_preferences、prompt_versions 模型和迁移。字段与 docs/数据库设计.md 对齐。
- **验收标准**：迁移能成功执行；数据库中生成对应表；外键和索引正确。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请根据 docs/数据库设计.md 实现首批 SQLAlchemy 模型：users、courses、student_profiles、learning_preferences、prompt_versions，并生成 Alembic 迁移。字段、索引、外键尽量与文档一致。不要实现 API。
```

## T04-03 实现 JWT 注册登录接口

- **任务编号**：T04-03
- **任务名称**：实现 JWT 注册登录接口
- **优先级**：P0
- **任务目标**：完成最小可用认证系统。
- **涉及目录**：`backend/app/api/v1, backend/app/services, backend/app/schemas, backend/app/core`
- **涉及文件**：`api/v1/auth.py, services/auth_service.py, schemas/auth.py, core/security.py`
- **前置依赖**：T04-02
- **具体实现要求**：输入：用户名、密码。输出：access_token、refresh_token、用户信息。实现密码哈希、JWT 生成、注册时创建 student_profile。
- **验收标准**：POST /auth/register、/auth/login 可用；密码不明文存储；登录后返回 token。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 JWT 注册登录。按 docs/API接口设计.md 实现 POST /api/v1/auth/register 和 POST /api/v1/auth/login，使用密码哈希，登录返回 access_token、refresh_token 和用户信息。注册学生时自动创建 student_profiles。
```

## T04-04 实现当前用户与权限依赖

- **任务编号**：T04-04
- **任务名称**：实现当前用户与权限依赖
- **优先级**：P0
- **任务目标**：让后续接口能获取当前用户和角色。
- **涉及目录**：`backend/app/core, backend/app/api/v1`
- **涉及文件**：`core/deps.py, api/v1/users.py, schemas/user.py`
- **前置依赖**：T04-03
- **具体实现要求**：输入：JWT。输出：current_user。实现 get_current_user、require_admin、GET /users/me。
- **验收标准**：无 Token 请求受保护接口返回 401；管理员权限校验生效；/users/me 返回当前用户。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 FastAPI 鉴权依赖。新增 get_current_user、require_admin、require_student，并实现 GET /api/v1/users/me。所有返回格式使用统一 ApiResponse。
```

---

# 第5阶段：课程与资料管理

## T05-01 实现课程 CRUD 后端

- **任务编号**：T05-01
- **任务名称**：实现课程 CRUD 后端
- **优先级**：P0
- **任务目标**：学生能创建和管理课程学习空间。
- **涉及目录**：`backend/app/api/v1, backend/app/services, backend/app/repositories, backend/app/schemas`
- **涉及文件**：`courses.py, course_service.py, course_repository.py, schemas/course.py`
- **前置依赖**：T04-04
- **具体实现要求**：输入：课程标题、描述。输出：课程对象。实现创建、列表、详情、更新、归档；学生只能访问自己的课程，管理员可访问全部。
- **验收标准**：课程 CRUD 接口可用；权限隔离正确；返回字段符合 API 文档。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现课程 CRUD 后端接口。按 docs/API接口设计.md 实现 /api/v1/courses 的创建、列表、详情、更新、删除/归档。学生只能操作自己的课程，管理员可查看全部。
```

## T05-02 实现课程页面前端

- **任务编号**：T05-02
- **任务名称**：实现课程页面前端
- **优先级**：P1
- **任务目标**：学生端能够查看和创建课程。
- **涉及目录**：`frontend/app/student, frontend/components/course, frontend/services`
- **涉及文件**：`services/courseService.ts, components/course/*, app/student/dashboard/page.tsx`
- **前置依赖**：T05-01, T02-04
- **具体实现要求**：输入：课程 API。输出：课程卡片和创建课程弹窗。Dashboard 显示课程列表，支持创建课程。
- **验收标准**：前端可创建课程并刷新列表；错误有提示。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现学生端课程展示与创建功能。在 dashboard 页面展示课程卡片，新增创建课程弹窗，调用 /api/v1/courses。遵守 docs/UI设计规范.md，不要做普通后台表格。
```

## T05-03 实现资料上传与本地存储

- **任务编号**：T05-03
- **任务名称**：实现资料上传与本地存储
- **优先级**：P0
- **任务目标**：学生能上传课程资料。
- **涉及目录**：`backend/app/api/v1, backend/app/services, backend/app/storage, backend/app/models`
- **涉及文件**：`models/material.py, api/v1/materials.py, services/material_service.py, storage/local_storage.py`
- **前置依赖**：T05-01
- **具体实现要求**：输入：course_id、文件。输出：course_materials 记录和文件路径。支持 pdf、docx、md、txt；限制大小；本地存储到 storage/materials。
- **验收标准**：上传接口可用；数据库记录 parse_status=pending；非法格式被拒绝。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现课程资料上传接口。支持 multipart/form-data 的 POST /api/v1/materials/upload，保存文件到本地 storage/materials，并写入 course_materials 表。校验文件类型和大小，返回资料 ID 和解析状态。
```

## T05-04 实现资料列表与上传前端

- **任务编号**：T05-04
- **任务名称**：实现资料列表与上传前端
- **优先级**：P1
- **任务目标**：学生能在前端上传和查看资料。
- **涉及目录**：`frontend/components/material, frontend/services, frontend/app/student/wiki`
- **涉及文件**：`materialService.ts, FileUploader.tsx, MaterialList.tsx`
- **前置依赖**：T05-03
- **具体实现要求**：输入：资料上传 API。输出：上传组件、资料列表。Wiki 页面或 Dashboard 提供上传资料入口。
- **验收标准**：选择文件后可上传；上传成功显示资料；解析状态可见。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现前端资料上传组件和资料列表。调用 /api/v1/materials/upload 和 /api/v1/materials，支持选择课程、上传文件、显示 parse_status。组件风格遵守 UI 规范。
```

## T05-05 实现文档文本解析

- **任务编号**：T05-05
- **任务名称**：实现文档文本解析
- **优先级**：P0
- **任务目标**：把上传资料解析为纯文本，为切片做准备。
- **涉及目录**：`backend/app/services, backend/app/utils`
- **涉及文件**：`services/material_parse_service.py, utils/document_parser.py`
- **前置依赖**：T05-03
- **具体实现要求**：输入：course_materials 文件路径。输出：解析文本和状态。支持 txt、md 直接读取，docx 使用 python-docx，pdf 可先用 pypdf；失败写 parse_error。
- **验收标准**：解析接口可用；成功 parse_status=success；失败有错误信息。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现资料解析服务和 POST /api/v1/materials/{id}/parse。支持 txt、md、docx、pdf 文本提取，解析失败要写入 parse_error，成功后更新 parse_status。暂不做 OCR。
```

---

# 第6阶段：RAG 知识库

## T06-01 实现知识点和文档切片模型

- **任务编号**：T06-01
- **任务名称**：实现知识点和文档切片模型
- **优先级**：P0
- **任务目标**：建立 RAG 所需知识点和切片数据结构。
- **涉及目录**：`backend/app/models, backend/alembic/versions`
- **涉及文件**：`models/knowledge.py, models/chunk.py, migration`
- **前置依赖**：T04-02
- **具体实现要求**：输入：数据库设计。输出：knowledge_points、document_chunks 表。包含 pgvector embedding 字段，向量维度按配置或默认 1024。
- **验收标准**：迁移成功；表、索引和外键正确；pgvector 扩展启用。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 knowledge_points 和 document_chunks 的 SQLAlchemy 模型和 Alembic 迁移。document_chunks 需要包含 content、chunk_index、course_id、material_id、knowledge_id、embedding vector 字段。确保 pgvector 扩展可用。
```

## T06-02 实现文本切片服务

- **任务编号**：T06-02
- **任务名称**：实现文本切片服务
- **优先级**：P0
- **任务目标**：把解析后的文本切成可检索片段。
- **涉及目录**：`backend/app/rag, backend/app/services`
- **涉及文件**：`rag/chunking.py, services/chunk_service.py`
- **前置依赖**：T05-05, T06-01
- **具体实现要求**：输入：资料解析文本。输出：document_chunks。按段落和长度切片，保存 chunk_index、content、token_count、source_title。
- **验收标准**：资料解析后可生成 chunks；chunk 内容非空；顺序正确。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现文本切片服务。新增 rag/chunking.py 和 chunk_service.py，将资料解析文本按段落和最大长度切成 chunks，并写入 document_chunks。实现 POST /api/v1/materials/{id}/chunk 或在 parse 后自动调用。
```

## T06-03 实现 Embedding 生成与入库

- **任务编号**：T06-03
- **任务名称**：实现 Embedding 生成与入库
- **优先级**：P1
- **任务目标**：为文档切片生成向量。
- **涉及目录**：`backend/app/llm, backend/app/rag, backend/app/services`
- **涉及文件**：`llm/embedding.py, services/embedding_service.py`
- **前置依赖**：T06-02, T08-01
- **具体实现要求**：输入：document_chunks content。输出：embedding 字段。先支持 mock embedding 或配置的真实 embedding；为后续检索打通。
- **验收标准**：每个 chunk 有 embedding；失败有日志；可重复生成。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 Embedding 生成服务。为 document_chunks 生成向量并写入 embedding 字段。先允许 mock embedding fallback，后续可接真实 LLM Provider。提供批量生成函数和接口。
```

## T06-04 实现向量检索接口

- **任务编号**：T06-04
- **任务名称**：实现向量检索接口
- **优先级**：P0
- **任务目标**：前端和 Tutor 能按问题检索课程资料。
- **涉及目录**：`backend/app/rag, backend/app/api/v1`
- **涉及文件**：`rag/retriever.py, api/v1/knowledge.py`
- **前置依赖**：T06-03
- **具体实现要求**：输入：course_id、query、top_k。输出：相关 chunks。使用 pgvector cosine 检索；支持 course_id、knowledge_id 过滤。
- **验收标准**：POST /knowledge/search 可返回相似 chunks；无 embedding 时有明确提示。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 RAG 向量检索接口 POST /api/v1/knowledge/search。输入 course_id、query、top_k、knowledge_id，可返回 chunk_id、content、score、source_title、page_no。使用 pgvector 相似度查询。
```

## T06-05 实现知识点抽取基础接口

- **任务编号**：T06-05
- **任务名称**：实现知识点抽取基础接口
- **优先级**：P1
- **任务目标**：从资料中初步生成知识点列表。
- **涉及目录**：`backend/app/api/v1, backend/app/services`
- **涉及文件**：`api/v1/knowledge.py, services/knowledge_service.py`
- **前置依赖**：T06-02, T08-01
- **具体实现要求**：输入：material_id。输出：knowledge_points。MVP 可用规则 + LLM 抽取标题和关键概念。
- **验收标准**：可从数据结构资料中抽取若干知识点；重复知识点不重复入库。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 POST /api/v1/knowledge/extract-from-material。读取资料 chunks，调用 LLM 或规则抽取章节和知识点，写入 knowledge_points。需要去重，返回新增知识点列表。
```

---

# 第7阶段：LLM Wiki 学习空间

## T07-01 实现 Wiki 数据模型和迁移

- **任务编号**：T07-01
- **任务名称**：实现 Wiki 数据模型和迁移
- **优先级**：P0
- **任务目标**：落地 LLM Wiki 页面、版本、关系、来源表。
- **涉及目录**：`backend/app/models, backend/alembic/versions`
- **涉及文件**：`models/wiki.py, migration`
- **前置依赖**：T06-01
- **具体实现要求**：输入：数据库设计。输出：wiki_pages、wiki_page_versions、wiki_links、wiki_sources 表。
- **验收标准**：迁移成功；外键和唯一索引正确。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请根据 docs/数据库设计.md 实现 Wiki 相关模型：wiki_pages、wiki_page_versions、wiki_links、wiki_sources，并生成 Alembic 迁移。字段、外键、索引保持与文档一致。
```

## T07-02 实现 Wiki 页面 CRUD 和版本

- **任务编号**：T07-02
- **任务名称**：实现 Wiki 页面 CRUD 和版本
- **优先级**：P0
- **任务目标**：学生能创建、查看、编辑 Wiki 页面并保留版本。
- **涉及目录**：`backend/app/api/v1, backend/app/services, backend/app/schemas`
- **涉及文件**：`api/v1/wiki.py, services/wiki_service.py, schemas/wiki.py`
- **前置依赖**：T07-01
- **具体实现要求**：输入：页面内容。输出：wiki_pages 和 wiki_page_versions。每次更新创建新版本；学生只能访问自己的 Wiki。
- **验收标准**：GET/POST/PUT/DELETE Wiki 页面可用；版本列表可查询；权限正确。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 Wiki 页面基础接口：列表、详情、创建、更新、归档、版本列表、回滚。每次创建或更新都写 wiki_page_versions。学生只能操作自己的页面。
```

## T07-03 实现从资料生成 Wiki 页面

- **任务编号**：T07-03
- **任务名称**：实现从资料生成 Wiki 页面
- **优先级**：P0
- **任务目标**：打通资料到 Wiki 的核心创新链路。
- **涉及目录**：`backend/app/api/v1, backend/app/services, backend/app/agents`
- **涉及文件**：`api/v1/wiki.py, services/wiki_generate_service.py, agents/wiki_agent.py`
- **前置依赖**：T06-05, T07-02, T08-01
- **具体实现要求**：输入：course_id、material_id。输出：Wiki 页面、来源和关系。读取 knowledge_points 和 chunks，生成知识点页面；绑定 wiki_sources；可先生成固定模板。
- **验收标准**：POST /wiki/pages/generate-from-material 可生成数据结构 Wiki 页面；页面有来源；重复生成不乱覆盖。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现重点接口 POST /api/v1/wiki/pages/generate-from-material。根据 material_id 的 chunks 和抽取出的 knowledge_points 生成 Wiki 页面，写入 wiki_pages、wiki_page_versions、wiki_sources，必要时创建 wiki_links。MVP 允许模板化生成，但必须可运行。
```

## T07-04 实现从笔记更新 Wiki 与页面总结

- **任务编号**：T07-04
- **任务名称**：实现从笔记更新 Wiki 与页面总结
- **优先级**：P1
- **任务目标**：支持学生笔记沉淀到 Wiki。
- **涉及目录**：`backend/app/api/v1, backend/app/services`
- **涉及文件**：`api/v1/wiki.py, services/wiki_update_service.py`
- **前置依赖**：T07-02, T08-01
- **具体实现要求**：输入：note_content 或 page_id。输出：新版本 Wiki 页面。实现 update-from-note 和 summarize，更新对应小节或 summary。
- **验收标准**：两个重点接口可用；写入版本；AI 失败时返回明确错误。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 POST /api/v1/wiki/pages/update-from-note 和 POST /api/v1/wiki/pages/{id}/summarize。调用 LLM 将学生笔记整理进 Wiki，或总结页面内容。更新页面时必须生成新版本。
```

## T07-05 实现 Wiki 前端列表和详情页

- **任务编号**：T07-05
- **任务名称**：实现 Wiki 前端列表和详情页
- **优先级**：P0
- **任务目标**：前端可浏览和编辑 Wiki。
- **涉及目录**：`frontend/app/student/wiki, frontend/components/wiki, frontend/services`
- **涉及文件**：`wikiService.ts, WikiPageGrid.tsx, WikiContentRenderer.tsx, WikiEditor.tsx, WikiSourcePanel.tsx`
- **前置依赖**：T07-02, T02-03
- **具体实现要求**：输入：Wiki API。输出：/student/wiki 和 /student/wiki/[id]。支持页面列表、详情、编辑、来源、版本。
- **验收标准**：页面可查看 Wiki；编辑保存后版本增加；来源展示清楚。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现学生端 Wiki 列表页和详情页。调用 Wiki API 展示页面列表、详情、来源、版本，支持编辑保存。UI 遵守 docs/UI设计规范.md 的 Wiki 页面视觉规范。
```

## T07-06 实现 Wiki 知识图谱基础页

- **任务编号**：T07-06
- **任务名称**：实现 Wiki 知识图谱基础页
- **优先级**：P2
- **任务目标**：用图或关系列表展示知识点关系。
- **涉及目录**：`frontend/app/student/wiki/graph, frontend/components/wiki`
- **涉及文件**：`KnowledgeGraphCanvas.tsx, GraphFilterPanel.tsx`
- **前置依赖**：T07-05
- **具体实现要求**：输入：wiki_links、wiki_pages。输出：知识图谱页面。MVP 可先用关系卡片，增强版再做力导向图。
- **验收标准**：能看到页面关系；点击节点进入 Wiki 详情。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 /student/wiki/graph。读取 wiki pages 和 links，先用简洁关系网络或关系列表展示知识点关系，支持点击跳转 Wiki 页面。不要过度复杂。
```

---

# 第8阶段：大模型接口封装

## T08-01 实现统一 LLM Provider 基类

- **任务编号**：T08-01
- **任务名称**：实现统一 LLM Provider 基类
- **优先级**：P0
- **任务目标**：为所有 Agent 和 AI 功能提供统一调用入口。
- **涉及目录**：`backend/app/llm`
- **涉及文件**：`provider.py, schemas.py, adapters/base.py`
- **前置依赖**：T03-01
- **具体实现要求**：输入：messages、model_config。输出：统一 LLM 响应。定义 chat、stream_chat、embedding 接口；支持 mock provider。
- **验收标准**：业务代码不直接调用厂商 SDK；mock provider 可正常返回。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现统一 LLM Provider 基础架构。新增 app/llm/provider.py、schemas.py、adapters/base.py，定义 chat、stream_chat、embedding 统一接口，并实现 MockProvider 用于本地开发。
```

## T08-02 实现 OpenAI Compatible 适配器

- **任务编号**：T08-02
- **任务名称**：实现 OpenAI Compatible 适配器
- **优先级**：P0
- **任务目标**：支持 OpenAI、通义、智谱等兼容接口。
- **涉及目录**：`backend/app/llm/adapters`
- **涉及文件**：`openai_compatible.py`
- **前置依赖**：T08-01
- **具体实现要求**：输入：LLM_BASE_URL、LLM_API_KEY、MODEL。输出：chat/stream_chat 结果。使用 httpx 调用 OpenAI-compatible API；错误统一抛出。
- **验收标准**：配置 key 后可调用；无 key 时可 fallback mock；错误日志清楚。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 OpenAI-compatible LLM 适配器。读取环境变量 LLM_BASE_URL、LLM_API_KEY、LLM_MODEL，支持普通 chat 和 stream_chat。调用失败时抛出业务异常并记录错误。
```

## T08-03 实现 Prompt 版本读取和渲染

- **任务编号**：T08-03
- **任务名称**：实现 Prompt 版本读取和渲染
- **优先级**：P1
- **任务目标**：让 Agent 使用可管理的 Prompt 模板。
- **涉及目录**：`backend/app/services, backend/app/llm`
- **涉及文件**：`services/prompt_service.py, llm/prompt_renderer.py`
- **前置依赖**：T04-02, T08-01
- **具体实现要求**：输入：agent_name、scene、参数。输出：渲染后的 Prompt。读取 active prompt_versions；无配置则使用默认模板。
- **验收标准**：Agent 可通过 PromptService 获取模板；变量渲染正确。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 PromptService 和 PromptRenderer。根据 agent_name、scene 读取 active prompt_versions，使用参数渲染模板；没有数据库模板时使用代码默认模板。
```

## T08-04 实现 LLM 调用日志

- **任务编号**：T08-04
- **任务名称**：实现 LLM 调用日志
- **优先级**：P1
- **任务目标**：记录模型调用，便于管理员和答辩展示。
- **涉及目录**：`backend/app/models, backend/app/services, backend/alembic`
- **涉及文件**：`models/llm_log.py, services/llm_log_service.py`
- **前置依赖**：T08-02
- **具体实现要求**：输入：provider、model、tokens、请求摘要。输出：llm_call_logs。注意请求和响应脱敏。
- **验收标准**：调用 LLM 后产生日志；失败也记录。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 llm_call_logs 模型和日志写入服务。LLM Provider 每次调用后记录 provider、model_name、token 数、latency、status、错误信息，请求响应需脱敏摘要。
```

---

# 第9阶段：多智能体基础框架

## T09-01 实现 BaseAgent 和 AgentResult

- **任务编号**：T09-01
- **任务名称**：实现 BaseAgent 和 AgentResult
- **优先级**：P0
- **任务目标**：建立可编码的 Agent 基类。
- **涉及目录**：`backend/app/agents`
- **涉及文件**：`base_agent.py, context.py`
- **前置依赖**：T08-01
- **具体实现要求**：输入：AgentContext。输出：AgentResult。定义 name、description、run 方法和统一返回结构。
- **验收标准**：后续 Agent 能继承 BaseAgent；类型清晰。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现多智能体基础类。新增 BaseAgent、AgentContext、AgentResult，统一 Agent 输入输出结构，支持 success、data、message、evidence、next_actions 字段。
```

## T09-02 实现 AgentRegistry 与 Orchestrator

- **任务编号**：T09-02
- **任务名称**：实现 AgentRegistry 与 Orchestrator
- **优先级**：P0
- **任务目标**：实现任务路由和 Agent 调度。
- **涉及目录**：`backend/app/agents, backend/app/services`
- **涉及文件**：`agents/registry.py, agents/orchestrator_agent.py, services/agent_service.py`
- **前置依赖**：T09-01
- **具体实现要求**：输入：task_type、上下文。输出：Agent 执行结果。MVP 用规则路由 TASK_AGENT_PLAN；按顺序调用 Agent。
- **验收标准**：可执行 document_to_wiki、course_qa 等任务；失败可返回明确错误。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 AgentRegistry 和 OrchestratorAgent。MVP 使用固定 TASK_AGENT_PLAN 规则路由，根据 task_type 顺序调用注册的 Agent，并聚合结果。不要做复杂自治规划。
```

## T09-03 实现 Agent 运行日志

- **任务编号**：T09-03
- **任务名称**：实现 Agent 运行日志
- **优先级**：P0
- **任务目标**：记录 Agent 执行过程，支撑前端展示。
- **涉及目录**：`backend/app/models, backend/app/services, backend/app/api/v1`
- **涉及文件**：`models/agent.py, services/agent_log_service.py, api/v1/agents.py`
- **前置依赖**：T09-02
- **具体实现要求**：输入：Agent 输入输出。输出：agent_runs 记录。实现运行列表和详情接口。
- **验收标准**：每次 Agent 执行有日志；前端可查询 /agents/runs。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 agent_runs 模型、AgentLogService 和 /api/v1/agents/runs 接口。记录 task_type、agent_name、input_payload、output_payload、status、duration_ms、error_message。
```

## T09-04 实现 MVP Agent 类占位

- **任务编号**：T09-04
- **任务名称**：实现 MVP Agent 类占位
- **优先级**：P0
- **任务目标**：创建所有 Agent 类文件，先打通调用。
- **涉及目录**：`backend/app/agents`
- **涉及文件**：`profile_agent.py, memory_agent.py, wiki_agent.py, knowledge_agent.py, planner_agent.py, resource_agent.py, quiz_agent.py, tutor_agent.py, diagnosis_agent.py, recommend_agent.py, evolution_agent.py, review_agent.py`
- **前置依赖**：T09-01
- **具体实现要求**：输入：AgentContext。输出：占位结果或简单调用。先保证所有类可注册，不一定完成完整业务。
- **验收标准**：Registry 能列出所有 Agent；Orchestrator 调用不报 ImportError。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请创建多智能体架构中的所有 Agent 类文件，全部继承 BaseAgent。MVP 阶段每个 Agent 先返回结构化占位结果或调用已有 Service，不要写复杂逻辑。
```

---

# 第10阶段：学生画像与长期记忆

## T10-01 实现学生画像服务与 API

- **任务编号**：T10-01
- **任务名称**：实现学生画像服务与 API
- **优先级**：P0
- **任务目标**：后端可读取和更新学生画像。
- **涉及目录**：`backend/app/api/v1, backend/app/services, backend/app/schemas`
- **涉及文件**：`api/v1/student_profile.py, services/profile_service.py, schemas/profile.py`
- **前置依赖**：T04-04
- **具体实现要求**：输入：user_id、course_id。输出：profile_summary、mastery、weak_points。实现 GET/PUT/rebuild。
- **验收标准**：画像查询可用；手动更新学习目标可用；rebuild 可返回结果。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现学生画像 API：GET /api/v1/student/profile、PUT /api/v1/student/profile、GET /summary、POST /rebuild。先使用 student_profiles 表和 learning_preferences 表，rebuild 可调用 ProfileAgent 或规则生成。
```

## T10-02 实现学习行为记录服务

- **任务编号**：T10-02
- **任务名称**：实现学习行为记录服务
- **优先级**：P0
- **任务目标**：建立自进化的数据基础。
- **涉及目录**：`backend/app/models, backend/app/services, backend/app/api/v1`
- **涉及文件**：`models/learning_record.py, services/learning_record_service.py`
- **前置依赖**：T04-02
- **具体实现要求**：输入：event_type、event_payload。输出：learning_records。提供内部方法和可选调试 API。
- **验收标准**：问答、练习、推荐反馈能写 learning_records。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 learning_records 模型和 LearningRecordService。提供 record_event 方法，支持 user_id、course_id、knowledge_id、event_type、event_source、event_payload。后续各模块可调用。
```

## T10-03 实现学习记忆 API

- **任务编号**：T10-03
- **任务名称**：实现学习记忆 API
- **优先级**：P0
- **任务目标**：学生可查看和反思长期记忆。
- **涉及目录**：`backend/app/models, backend/app/api/v1, backend/app/services`
- **涉及文件**：`models/memory.py, api/v1/student_memory.py, services/memory_service.py`
- **前置依赖**：T10-02, T09-04
- **具体实现要求**：输入：学习记录。输出：student_memories。实现 GET /student/memory、POST /reflect、DELETE/PATCH。
- **验收标准**：重点接口 GET /student/memory 和 POST /student/memory/reflect 可用；reflect 能生成或模拟记忆。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现学生长期记忆模块。新增 student_memories 模型和 API：GET /api/v1/student/memory、POST /api/v1/student/memory/reflect、DELETE/PATCH。reflect 调用 MemoryAgent 或规则，从 learning_records 中生成长期记忆。
```

## T10-04 实现画像与记忆前端页面

- **任务编号**：T10-04
- **任务名称**：实现画像与记忆前端页面
- **优先级**：P1
- **任务目标**：学生端展示系统如何理解自己。
- **涉及目录**：`frontend/app/student/profile, frontend/app/student/memory, frontend/components/profile, frontend/components/memory`
- **涉及文件**：`profile/page.tsx, memory/page.tsx, ProfileSummaryCard.tsx, MemoryList.tsx`
- **前置依赖**：T10-01, T10-03
- **具体实现要求**：输入：画像和记忆 API。输出：/student/profile、/student/memory 页面。
- **验收标准**：页面显示画像摘要、薄弱点、学习偏好、记忆列表；可触发 reflect。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现学生画像页和学习记忆页。调用 profile 和 memory API，展示画像摘要、薄弱知识点、错误模式、学习偏好、长期记忆和证据。提供“反思生成记忆”按钮。
```

---

# 第11阶段：自进化策略系统

## T11-01 实现自进化数据模型

- **任务编号**：T11-01
- **任务名称**：实现自进化数据模型
- **优先级**：P0
- **任务目标**：落地策略版本和自进化事件表。
- **涉及目录**：`backend/app/models, backend/alembic/versions`
- **涉及文件**：`models/evolution.py, migration`
- **前置依赖**：T04-02
- **具体实现要求**：输入：数据库设计。输出：evolution_strategies、evolution_events 表。
- **验收标准**：迁移成功；策略版本支持 previous_strategy_id、status、risk_level。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现自进化相关 SQLAlchemy 模型：evolution_strategies 和 evolution_events，并生成 Alembic 迁移。字段与 docs/数据库设计.md 对齐。
```

## T11-02 实现 Evolution Analyze 接口

- **任务编号**：T11-02
- **任务名称**：实现 Evolution Analyze 接口
- **优先级**：P0
- **任务目标**：根据学生行为生成策略更新建议。
- **涉及目录**：`backend/app/api/v1, backend/app/services, backend/app/agents`
- **涉及文件**：`api/v1/evolution.py, services/evolution_service.py, agents/evolution_agent.py, agents/review_agent.py`
- **前置依赖**：T11-01, T10-03, T09-04
- **具体实现要求**：输入：course_id、trigger_type、focus。输出：evolution_event 和 strategy draft。读取画像、记忆、诊断、行为，生成策略建议。
- **验收标准**：POST /evolution/analyze 可生成策略；策略有证据、风险等级、状态。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现重点接口 POST /api/v1/evolution/analyze。读取学生画像、长期记忆、学习行为和诊断报告，调用 EvolutionAgent 生成策略建议，再调用 ReviewAgent 审核，写入 evolution_events 和 evolution_strategies。
```

## T11-03 实现策略应用与回滚

- **任务编号**：T11-03
- **任务名称**：实现策略应用与回滚
- **优先级**：P0
- **任务目标**：让策略可生效、可回退。
- **涉及目录**：`backend/app/api/v1, backend/app/services`
- **涉及文件**：`api/v1/evolution.py, services/strategy_service.py`
- **前置依赖**：T11-02
- **具体实现要求**：输入：strategy_id。输出：active 策略。实现 strategies 列表、详情、apply、rollback；同类型同用户同课程只允许一个 active。
- **验收标准**：apply 后策略状态 active；旧策略失效；rollback 可恢复上一版本。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现自进化策略管理接口：GET /evolution/strategies、GET /{id}、POST /strategies/apply、POST /strategies/{id}/rollback。同一用户同课程同策略类型只允许一个 active。
```

## T11-04 实现自进化前端页面

- **任务编号**：T11-04
- **任务名称**：实现自进化前端页面
- **优先级**：P1
- **任务目标**：前端展示策略演化过程。
- **涉及目录**：`frontend/app/student/evolution, frontend/components/evolution, frontend/services`
- **涉及文件**：`evolution/page.tsx, EvolutionEventTimeline.tsx, StrategyVersionList.tsx, StrategyDiffViewer.tsx`
- **前置依赖**：T11-03
- **具体实现要求**：输入：Evolution API。输出：自进化中心页面。展示事件时间线、策略版本、证据、应用、回滚。
- **验收标准**：页面可触发 analyze；可应用策略；可查看更新前后对比。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 /student/evolution 自进化中心页面。调用 evolution API 展示事件、策略版本、证据、风险等级、更新前后对比，并支持手动分析、应用策略和回滚。
```

---

# 第12阶段：学习路径生成

## T12-01 实现学习路径模型和 API

- **任务编号**：T12-01
- **任务名称**：实现学习路径模型和 API
- **优先级**：P1
- **任务目标**：学生可生成和查看学习路径。
- **涉及目录**：`backend/app/models, backend/app/api/v1, backend/app/services`
- **涉及文件**：`models/learning_path.py, api/v1/learning_paths.py, services/learning_path_service.py`
- **前置依赖**：T07-01, T10-01
- **具体实现要求**：输入：goal、course_id、target_knowledge_ids。输出：learning_paths 和 items。MVP 用知识点关系 + 薄弱点规则生成。
- **验收标准**：生成路径接口可用；路径节点顺序合理；可标记完成。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现学习路径后端。新增 learning_paths、learning_path_items 模型和 API：列表、详情、generate、更新节点状态。MVP 用规则基于薄弱点和 wiki_links 生成路径。
```

## T12-02 实现 Planner Agent

- **任务编号**：T12-02
- **任务名称**：实现 Planner Agent
- **优先级**：P1
- **任务目标**：封装路径规划逻辑为 Agent。
- **涉及目录**：`backend/app/agents, backend/app/services`
- **涉及文件**：`agents/planner_agent.py, services/planner_service.py`
- **前置依赖**：T12-01, T09-04
- **具体实现要求**：输入：画像、掌握度、知识关系、目标。输出：路径计划。支持 LLM 生成理由，规则生成路径。
- **验收标准**：PlannerAgent 可被 Orchestrator 调用；输出结构稳定。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 PlannerAgent。读取 student_profile、knowledge_points、wiki_links 和 mastery_snapshot，生成 learning path 的节点、理由和预计时间。MVP 先规则排序，LLM 只生成自然语言理由。
```

## T12-03 实现学习路径前端

- **任务编号**：T12-03
- **任务名称**：实现学习路径前端
- **优先级**：P1
- **任务目标**：学生可查看和执行路径。
- **涉及目录**：`frontend/app/student/learning-paths, frontend/components/path`
- **涉及文件**：`learning-paths/page.tsx, learning-paths/[id]/page.tsx, LearningPathTimeline.tsx`
- **前置依赖**：T12-01
- **具体实现要求**：输入：Learning Path API。输出：路径列表和详情页。
- **验收标准**：可生成路径；节点可标记完成；点击节点跳转 Wiki 或练习。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现学生学习路径页面。/student/learning-paths 展示路径列表和生成入口，/student/learning-paths/[id] 展示路径时间线、节点任务、推荐理由和完成状态。
```

---

# 第13阶段：学习资源生成

## T13-01 实现资源数据模型和 API

- **任务编号**：T13-01
- **任务名称**：实现资源数据模型和 API
- **优先级**：P0
- **任务目标**：保存 AI 生成学习资源。
- **涉及目录**：`backend/app/models, backend/app/api/v1, backend/app/services`
- **涉及文件**：`models/resource.py, api/v1/resources.py, services/resource_service.py`
- **前置依赖**：T07-01, T08-01
- **具体实现要求**：输入：resource_type、knowledge_id、wiki_page_id。输出：generated_resources。实现列表、详情、删除。
- **验收标准**：资源可保存、查询、归档。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 generated_resources 模型和资源基础 API：列表、详情、删除。字段包括 user_id、course_id、knowledge_id、wiki_page_id、resource_type、title、content、citations、personalized_reason、status。
```

## T13-02 实现资源生成 Agent 和接口

- **任务编号**：T13-02
- **任务名称**：实现资源生成 Agent 和接口
- **优先级**：P0
- **任务目标**：根据 Wiki、RAG、画像生成个性化资源。
- **涉及目录**：`backend/app/api/v1, backend/app/agents, backend/app/services`
- **涉及文件**：`api/v1/resources.py, agents/resource_agent.py, services/resource_generate_service.py`
- **前置依赖**：T13-01, T08-02, T10-01
- **具体实现要求**：输入：course_id、knowledge_id、resource_type、requirement。输出：资源内容、引用、个性化原因。调用 RAG、Wiki、Profile、Memory。
- **验收标准**：POST /resources/generate 可生成资源；结果有 personalized_reason 和 citations。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现重点接口 POST /api/v1/resources/generate。ResourceAgent 需要读取 Wiki 页面、RAG chunks、学生画像和记忆，生成个性化讲解/总结/例题/卡片，保存到 generated_resources，并返回引用和个性化原因。
```

## T13-03 实现保存资源到 Wiki

- **任务编号**：T13-03
- **任务名称**：实现保存资源到 Wiki
- **优先级**：P1
- **任务目标**：让 AI 生成资源沉淀回 Wiki。
- **涉及目录**：`backend/app/api/v1, backend/app/services`
- **涉及文件**：`api/v1/resources.py, services/resource_service.py, services/wiki_service.py`
- **前置依赖**：T13-02, T07-02
- **具体实现要求**：输入：resource_id、target wiki。输出：Wiki 新版本。资源状态变 saved_to_wiki。
- **验收标准**：保存后 Wiki 页面版本增加；资源状态更新。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 POST /api/v1/resources/{id}/save-to-wiki。将资源内容追加到目标 Wiki 页面指定小节，生成 wiki_page_versions，并将资源状态更新为 saved_to_wiki。
```

## T13-04 实现资源生成前端

- **任务编号**：T13-04
- **任务名称**：实现资源生成前端
- **优先级**：P0
- **任务目标**：学生能在页面生成学习资源。
- **涉及目录**：`frontend/app/student/resources, frontend/components/resources, frontend/services`
- **涉及文件**：`resources/generate/page.tsx, resources/page.tsx, ResourceGenerateForm.tsx, GeneratedResourceViewer.tsx`
- **前置依赖**：T13-02
- **具体实现要求**：输入：资源 API。输出：资源生成页和资源列表。支持选择课程、知识点、资源类型、保存到 Wiki。
- **验收标准**：前端可生成资源、显示引用、保存到 Wiki。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现资源生成页面和资源列表。/student/resources/generate 调用 /resources/generate，显示生成内容、个性化原因和引用；支持保存到 Wiki。/student/resources 展示历史资源。
```

---

# 第14阶段：AI 答疑

## T14-01 实现 Tutor Chat 后端

- **任务编号**：T14-01
- **任务名称**：实现 Tutor Chat 后端
- **优先级**：P0
- **任务目标**：打通 RAG + Wiki + 画像的智能问答。
- **涉及目录**：`backend/app/api/v1, backend/app/agents, backend/app/services`
- **涉及文件**：`api/v1/tutor.py, agents/tutor_agent.py, services/tutor_service.py`
- **前置依赖**：T06-04, T07-02, T10-01, T08-02
- **具体实现要求**：输入：course_id、question。输出：answer、citations、related_knowledge_points。记录 learning_records 和 agent_runs。
- **验收标准**：POST /tutor/chat 可回答问题；带引用；依据不足时说明。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现重点接口 POST /api/v1/tutor/chat。TutorAgent 需要检索 RAG chunks、相关 Wiki 页面，读取学生画像和记忆，调用 LLM 生成回答，返回 citations、related_knowledge_points、follow_up_questions，并记录学习行为和 Agent 日志。
```

## T14-02 实现流式输出支持

- **任务编号**：T14-02
- **任务名称**：实现流式输出支持
- **优先级**：P1
- **任务目标**：提升 AI 答疑体验。
- **涉及目录**：`backend/app/api/v1, backend/app/llm, frontend/lib`
- **涉及文件**：`api/v1/tutor.py, llm/provider.py, frontend/lib/stream.ts`
- **前置依赖**：T14-01
- **具体实现要求**：输入：stream=true。输出：SSE delta。后端支持 text/event-stream，前端可逐步显示。
- **验收标准**：stream=true 时可看到流式文本；结束返回 citations。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请为 Tutor Chat 增加 SSE 流式输出。后端在 stream=true 时返回 text/event-stream，逐步发送 delta，结束时发送 done 和 citations。前端新增 stream.ts 处理 EventSource/fetch stream。
```

## T14-03 实现答疑前端页面

- **任务编号**：T14-03
- **任务名称**：实现答疑前端页面
- **优先级**：P0
- **任务目标**：学生可进行 AI 答疑。
- **涉及目录**：`frontend/app/student/tutor, frontend/components/tutor, frontend/services`
- **涉及文件**：`tutor/page.tsx, ChatWindow.tsx, ChatInputBox.tsx, CitationPanel.tsx, AgentTracePanel.tsx`
- **前置依赖**：T14-01
- **具体实现要求**：输入：Tutor API。输出：聊天页。显示回答、引用、相关知识点、保存到 Wiki、反馈。
- **验收标准**：可提问并看到回答；引用可展开；可保存回答到 Wiki。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 /student/tutor 页面。调用 POST /tutor/chat，展示聊天消息、引用来源、相关知识点、Agent 调用摘要和保存到 Wiki 按钮。UI 要专业可信，不做普通聊天玩具风格。
```

## T14-04 实现答疑保存到 Wiki 与反馈

- **任务编号**：T14-04
- **任务名称**：实现答疑保存到 Wiki 与反馈
- **优先级**：P1
- **任务目标**：让问答进入学习闭环。
- **涉及目录**：`backend/app/api/v1, frontend/components/tutor`
- **涉及文件**：`api/v1/tutor.py, SaveAnswerToWikiButton.tsx, MessageFeedbackButtons.tsx`
- **前置依赖**：T14-03, T07-04
- **具体实现要求**：输入：message 或 answer 内容。输出：Wiki 新版本、user_feedback。实现保存到 Wiki 和点赞点踩。
- **验收标准**：保存后 Wiki 页面更新；反馈写入 user_feedback 和 learning_records。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 AI 答疑结果保存到 Wiki 和反馈。后端提供保存接口或复用 wiki update-from-note，前端提供“保存到 Wiki”“有用/无用”按钮，反馈写入 user_feedback 和 learning_records。
```

---

# 第15阶段：练习题与错题本

## T15-01 实现 Quiz 和 Question 模型/API

- **任务编号**：T15-01
- **任务名称**：实现 Quiz 和 Question 模型/API
- **优先级**：P0
- **任务目标**：支持生成和存储练习题。
- **涉及目录**：`backend/app/models, backend/app/api/v1, backend/app/services`
- **涉及文件**：`models/quiz.py, api/v1/quizzes.py, services/quiz_service.py`
- **前置依赖**：T06-01
- **具体实现要求**：输入：course_id、knowledge_id。输出：quizzes、questions。实现列表、详情。
- **验收标准**：可创建 quiz；题目可查询。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 quizzes 和 questions 模型及基础 API：创建/生成入口占位、列表、详情。字段与 docs/数据库设计.md 对齐。
```

## T15-02 实现 Quiz Agent 生成题目

- **任务编号**：T15-02
- **任务名称**：实现 Quiz Agent 生成题目
- **优先级**：P0
- **任务目标**：根据知识点生成练习题。
- **涉及目录**：`backend/app/agents, backend/app/services`
- **涉及文件**：`agents/quiz_agent.py, services/quiz_generate_service.py`
- **前置依赖**：T15-01, T08-02, T07-02
- **具体实现要求**：输入：知识点、题型、难度、数量。输出：题目、答案、解析、错因标签。结合 Wiki 页面生成。
- **验收标准**：POST /quizzes/generate 可生成题目；题目结构完整。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 POST /api/v1/quizzes/generate。QuizAgent 根据 knowledge_id、question_types、difficulty、count 和 Wiki 页面生成题目，保存 quizzes 和 questions，返回题目列表。
```

## T15-03 实现答题提交与错题本

- **任务编号**：T15-03
- **任务名称**：实现答题提交与错题本
- **优先级**：P0
- **任务目标**：学生答题后产生记录和错题。
- **涉及目录**：`backend/app/models, backend/app/api/v1, backend/app/services`
- **涉及文件**：`models/answer.py, models/mistake.py, services/answer_service.py`
- **前置依赖**：T15-02, T10-02
- **具体实现要求**：输入：quiz_id、answers。输出：answer_records、mistake_books。客观题规则批改，主观题可调用 LLM 或暂时人工/标准答案比对。
- **验收标准**：提交答案可得分；错误题进入错题本；写 learning_records。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 POST /api/v1/quizzes/{id}/submit 和 GET /api/v1/quizzes/mistakes。客观题自动批改，错误题写入 mistake_books，记录 answer_records 和 learning_records。
```

## T15-04 实现练习与错题前端

- **任务编号**：T15-04
- **任务名称**：实现练习与错题前端
- **优先级**：P1
- **任务目标**：学生可生成练习、答题、查看错题。
- **涉及目录**：`frontend/app/student/quizzes, frontend/app/student/mistakes, frontend/components/quiz`
- **涉及文件**：`quizzes/page.tsx, mistakes/page.tsx, QuestionCard.tsx, QuizResultPanel.tsx`
- **前置依赖**：T15-03
- **具体实现要求**：输入：Quiz API。输出：练习页和错题页。
- **验收标准**：可生成题目、提交答案、查看解析、错题列表。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 /student/quizzes 和 /student/mistakes 页面。练习页支持选择知识点生成题目、答题提交、查看解析；错题页支持按知识点和错因筛选。
```

---

# 第16阶段：学习诊断与推荐

## T16-01 实现诊断报告模型/API

- **任务编号**：T16-01
- **任务名称**：实现诊断报告模型/API
- **优先级**：P0
- **任务目标**：根据答题和行为生成学习诊断。
- **涉及目录**：`backend/app/models, backend/app/api/v1, backend/app/services`
- **涉及文件**：`models/diagnosis.py, api/v1/diagnosis.py, services/diagnosis_service.py`
- **前置依赖**：T15-03, T10-01
- **具体实现要求**：输入：course_id、answer_records、mistake_books。输出：diagnosis_reports。规则计算掌握度和薄弱点。
- **验收标准**：POST /diagnosis/generate 可生成报告；报告列表可查询。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现诊断报告后端。新增 diagnosis_reports 模型和 API：POST /api/v1/diagnosis/generate、GET /reports、GET /reports/{id}、GET /mastery。MVP 用规则计算掌握度、薄弱点和错因。
```

## T16-02 实现 Diagnosis Agent

- **任务编号**：T16-02
- **任务名称**：实现 Diagnosis Agent
- **优先级**：P0
- **任务目标**：用 Agent 生成可解释诊断文本和建议。
- **涉及目录**：`backend/app/agents, backend/app/services`
- **涉及文件**：`agents/diagnosis_agent.py, services/diagnosis_generate_service.py`
- **前置依赖**：T16-01, T08-02
- **具体实现要求**：输入：错题、掌握度、行为记录。输出：诊断摘要、推荐动作、是否触发自进化。
- **验收标准**：诊断报告有自然语言摘要和建议；可触发 evolution。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 DiagnosisAgent。读取答题记录、错题本、学习行为和 Wiki 关系，生成诊断摘要、薄弱点、错因模式、推荐动作，并可在 trigger_evolution=true 时调用 evolution analyze。
```

## T16-03 实现推荐模型/API

- **任务编号**：T16-03
- **任务名称**：实现推荐模型/API
- **优先级**：P0
- **任务目标**：为学生推荐下一步学习内容。
- **涉及目录**：`backend/app/models, backend/app/api/v1, backend/app/services`
- **涉及文件**：`models/recommendation.py, api/v1/recommendations.py, services/recommendation_service.py`
- **前置依赖**：T16-01, T12-01, T13-01
- **具体实现要求**：输入：profile、diagnosis、path、resources。输出：recommendations。MVP 规则：薄弱知识点优先、前置知识优先、错题相关优先。
- **验收标准**：推荐列表可查询；refresh 可生成新推荐；状态可更新。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 recommendations 后端。提供 GET /recommendations、POST /refresh、PATCH /{id}、POST /{id}/feedback。MVP 根据薄弱知识点、学习路径和资源生成推荐。
```

## T16-04 实现诊断与推荐前端

- **任务编号**：T16-04
- **任务名称**：实现诊断与推荐前端
- **优先级**：P1
- **任务目标**：学生可看到诊断和下一步建议。
- **涉及目录**：`frontend/app/student/diagnosis, frontend/app/student/recommendations, frontend/components/diagnosis`
- **涉及文件**：`diagnosis/page.tsx, recommendations/page.tsx, DiagnosisSummaryCard.tsx, WeakPointRankList.tsx`
- **前置依赖**：T16-03
- **具体实现要求**：输入：Diagnosis 和 Recommendation API。输出：诊断页和推荐页。
- **验收标准**：能生成诊断；显示薄弱点、错因、推荐动作；推荐可标记完成/忽略。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 /student/diagnosis 和 /student/recommendations 页面。诊断页展示摘要、掌握度、薄弱点、错因和推荐动作；推荐页展示不同类型推荐并支持反馈。
```

---

# 第17阶段：教师端

## T17-01 实现教师端预留路由与说明页

- **任务编号**：T17-01
- **任务名称**：实现教师端预留路由与说明页
- **优先级**：P2
- **任务目标**：满足角色预留，但不建设完整教师端。
- **涉及目录**：`frontend/app/teacher`
- **涉及文件**：`teacher/layout.tsx, teacher/dashboard/page.tsx`
- **前置依赖**：T02-03
- **具体实现要求**：输入：教师角色。输出：教师端占位。说明当前版本教师能力并入管理员/课程内容维护，不提供班级作业管理。
- **验收标准**：访问 /teacher/dashboard 可见说明；不影响学生端。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请新增轻量教师端预留页面 /teacher/dashboard，说明当前版本教师端仅预留课程内容维护能力，完整教师端不在 MVP 范围。不要实现班级管理、作业发布、教师批改。
```

## T17-02 实现课程内容维护页面

- **任务编号**：T17-02
- **任务名称**：实现课程内容维护页面
- **优先级**：P2
- **任务目标**：教师或内容维护者可上传课程资料模板。
- **涉及目录**：`frontend/app/teacher/materials, backend/app/api/v1`
- **涉及文件**：`teacher/materials/page.tsx, api/v1/teacher.py`
- **前置依赖**：T05-03
- **具体实现要求**：输入：课程资料。输出：公共课程模板资料。可复用 materials API 或 admin demo seed。
- **验收标准**：能上传课程资料模板；权限可用；不涉及学生个人数据。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现一个轻量课程内容维护页面，允许 teacher/admin 上传公共课程资料模板。复用 materials 上传逻辑，不实现班级、作业、成绩等教师端功能。
```

## T17-03 教师端范围文档补充

- **任务编号**：T17-03
- **任务名称**：教师端范围文档补充
- **优先级**：P2
- **任务目标**：避免评审认为教师端缺失是漏洞。
- **涉及目录**：`docs/`
- **涉及文件**：`docs/教师端范围说明.md`
- **前置依赖**：T17-01
- **具体实现要求**：输入：产品定位。输出：说明文档。解释为什么不做完整教师端，教师相关能力如何由管理员和课程模板维护支撑。
- **验收标准**：文档清楚说明范围，和 PRD 一致。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请新增 docs/教师端范围说明.md，说明本项目核心是学生个性化学习端，教师端仅作为课程内容维护能力预留，不做班级管理、作业发布、教师批改。
```

---

# 第18阶段：管理员端

## T18-01 实现管理员用户管理

- **任务编号**：T18-01
- **任务名称**：实现管理员用户管理
- **优先级**：P1
- **任务目标**：管理员可查看和管理用户。
- **涉及目录**：`backend/app/api/v1, frontend/app/admin/users`
- **涉及文件**：`api/v1/admin.py, admin/users/page.tsx, UserTable.tsx`
- **前置依赖**：T04-04, T02-03
- **具体实现要求**：输入：admin token。输出：用户列表和启停状态。实现 GET /admin/users、PATCH status。
- **验收标准**：管理员能查看用户；可禁用/启用；学生无权限。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现管理员用户管理。后端提供 /api/v1/admin/users 和 /api/v1/admin/users/{id}/status，前端 /admin/users 显示用户表格并支持启用禁用。
```

## T18-02 实现 Agent 日志管理页

- **任务编号**：T18-02
- **任务名称**：实现 Agent 日志管理页
- **优先级**：P1
- **任务目标**：管理员可查看多智能体运行情况。
- **涉及目录**：`frontend/app/admin/agents, frontend/components/agent`
- **涉及文件**：`admin/agents/page.tsx, AgentRunTable.tsx, AgentRunDetailDrawer.tsx`
- **前置依赖**：T09-03
- **具体实现要求**：输入：agent_runs API。输出：Agent 日志表、详情抽屉。
- **验收标准**：可筛选 Agent、状态、任务类型；可查看输入输出摘要。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 /admin/agents 页面。调用 /api/v1/agents/runs 和详情接口，展示 Agent 名称、任务类型、状态、耗时、创建时间，支持详情抽屉查看输入输出。
```

## T18-03 实现 LLM 日志管理页

- **任务编号**：T18-03
- **任务名称**：实现 LLM 日志管理页
- **优先级**：P1
- **任务目标**：管理员可查看大模型调用情况。
- **涉及目录**：`backend/app/api/v1, frontend/app/admin/llm-logs`
- **涉及文件**：`api/v1/admin.py, admin/llm-logs/page.tsx`
- **前置依赖**：T08-04
- **具体实现要求**：输入：llm_call_logs。输出：日志列表和统计。
- **验收标准**：可按 provider、model、status 筛选；显示 latency 和 token。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 LLM 调用日志管理。后端提供 /api/v1/admin/llm-logs，前端 /admin/llm-logs 展示 provider、model、status、token、latency、错误信息。
```

## T18-04 实现系统配置与 Prompt 管理

- **任务编号**：T18-04
- **任务名称**：实现系统配置与 Prompt 管理
- **优先级**：P1
- **任务目标**：管理员可管理模型和 Prompt 版本。
- **涉及目录**：`backend/app/api/v1, frontend/app/admin/system`
- **涉及文件**：`api/v1/admin.py, admin/system/page.tsx, PromptVersionTable.tsx, ModelConfigForm.tsx`
- **前置依赖**：T08-03
- **具体实现要求**：输入：模型配置、Prompt 模板。输出：prompt_versions 和配置。MVP 模型配置可读写 .env 展示或数据库配置占位。
- **验收标准**：可查看和新增 Prompt 版本；可激活版本；模型配置表单可保存。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现管理员系统配置页面。支持 Prompt 版本列表、新建、激活；模型配置可先保存到 system config 占位或环境变量说明。前端页面遵守 UI 规范。
```

## T18-05 实现管理员首页

- **任务编号**：T18-05
- **任务名称**：实现管理员首页
- **优先级**：P2
- **任务目标**：管理员看到系统概览。
- **涉及目录**：`frontend/app/admin/dashboard, frontend/components/admin`
- **涉及文件**：`admin/dashboard/page.tsx, AdminMetricCards.tsx, SystemHealthCard.tsx`
- **前置依赖**：T18-01, T18-02, T18-03
- **具体实现要求**：输入：用户、Agent、LLM、课程统计。输出：管理员 dashboard。
- **验收标准**：显示关键指标和最近日志；不做复杂报表。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 /admin/dashboard。展示用户数、课程数、Agent 最近运行、LLM 调用概览和系统健康状态，数据可来自已有 API 或临时统计接口。
```

---

# 第19阶段：前端美化

## T19-01 应用 UI Design Token

- **任务编号**：T19-01
- **任务名称**：应用 UI Design Token
- **优先级**：P1
- **任务目标**：统一前端视觉语言。
- **涉及目录**：`frontend/`
- **涉及文件**：`tailwind.config.ts, app/globals.css, components/common/*`
- **前置依赖**：T02-02
- **具体实现要求**：输入：UI 设计规范。输出：统一颜色、阴影、圆角、背景、公共卡片组件。
- **验收标准**：主要页面风格一致；没有明显默认样式。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请根据 docs/UI设计规范.md 统一 Tailwind token 和公共组件。新增 AppCard、GradientCard、SectionHeader、EmptyState、LoadingState 等组件，并替换关键页面中的杂乱样式。
```

## T19-02 美化五个重点页面

- **任务编号**：T19-02
- **任务名称**：美化五个重点页面
- **优先级**：P1
- **任务目标**：提升比赛演示效果。
- **涉及目录**：`frontend/app/student, frontend/components`
- **涉及文件**：`dashboard, wiki/[id], tutor, diagnosis, evolution 相关文件`
- **前置依赖**：T19-01
- **具体实现要求**：输入：现有页面。输出：高级教育科技风 UI。重点优化学生首页、Wiki 页面、自进化页面、AI 答疑页面、学习诊断页面。
- **验收标准**：页面具备柔和渐变、卡片、大圆角、轻微动效；不再像普通后台。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请重点美化五个页面：/student/dashboard、/student/wiki/[id]、/student/tutor、/student/diagnosis、/student/evolution。严格遵守 docs/UI设计规范.md，使用卡片式布局、柔和渐变、大圆角、轻微动效和清晰信息层级。
```

## T19-03 添加 Framer Motion 轻量动效

- **任务编号**：T19-03
- **任务名称**：添加 Framer Motion 轻量动效
- **优先级**：P2
- **任务目标**：提升交互质感。
- **涉及目录**：`frontend/components`
- **涉及文件**：`common/motion.ts, 关键页面组件`
- **前置依赖**：T19-02
- **具体实现要求**：输入：现有 UI 组件。输出：页面进入、卡片 hover、Agent 状态高亮动效。
- **验收标准**：动效轻微；不影响性能；无夸张闪烁。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请为关键前端组件添加 Framer Motion 轻量动效。包括页面进入、卡片 hover、Agent 调用链节点高亮、AI 生成状态。动效要克制，不要炫技。
```

## T19-04 响应式适配

- **任务编号**：T19-04
- **任务名称**：响应式适配
- **优先级**：P1
- **任务目标**：保证常见屏幕可用。
- **涉及目录**：`frontend/app, frontend/components/layout`
- **涉及文件**：`StudentSidebar.tsx, StudentTopbar.tsx, 各页面布局`
- **前置依赖**：T19-02
- **具体实现要求**：输入：现有页面。输出：移动端和平板适配。侧边栏折叠，表格转卡片，Wiki 三栏变单栏。
- **验收标准**：Chrome 1024px、768px、390px 下可正常使用。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请进行响应式适配。学生端侧边栏在小屏折叠，Wiki 详情三栏在移动端变为单列，表格改为卡片或横向滚动。确保主要页面在 390px 宽度下可用。
```

---

# 第20阶段：测试

## T20-01 后端单元测试基础

- **任务编号**：T20-01
- **任务名称**：后端单元测试基础
- **优先级**：P1
- **任务目标**：保障核心 API 稳定。
- **涉及目录**：`backend/tests`
- **涉及文件**：`tests/conftest.py, tests/test_auth.py, test_courses.py, test_wiki.py`
- **前置依赖**：T04-04, T07-02
- **具体实现要求**：输入：后端 API。输出：pytest 测试。覆盖 auth、courses、wiki 基础接口。
- **验收标准**：pytest 通过；测试数据库隔离。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请为后端添加 pytest 测试基础。配置测试数据库或 sqlite 替代方案，编写 auth、courses、wiki 基础接口测试，验证登录、鉴权、创建课程、创建 Wiki 页面。
```

## T20-02 AI 核心链路集成测试

- **任务编号**：T20-02
- **任务名称**：AI 核心链路集成测试
- **优先级**：P1
- **任务目标**：验证主链路不崩。
- **涉及目录**：`backend/tests`
- **涉及文件**：`test_rag_wiki_tutor.py, test_resource_diagnosis.py`
- **前置依赖**：T14-01, T16-01
- **具体实现要求**：输入：mock LLM。输出：集成测试。覆盖资料切片、Wiki 生成、Tutor Chat、资源生成、诊断。
- **验收标准**：使用 mock LLM 时测试稳定通过。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请编写 AI 主链路集成测试，使用 MockProvider，不依赖真实模型。覆盖资料解析/切片、Wiki 生成、Tutor Chat、资源生成、Quiz 提交、Diagnosis 生成。
```

## T20-03 前端基础测试和构建检查

- **任务编号**：T20-03
- **任务名称**：前端基础测试和构建检查
- **优先级**：P1
- **任务目标**：确保前端可构建。
- **涉及目录**：`frontend/`
- **涉及文件**：`package.json, tests or __tests__, playwright.config.ts 可选`
- **前置依赖**：T19-02
- **具体实现要求**：输入：前端项目。输出：lint、typecheck、build 脚本和基础测试。
- **验收标准**：npm run build 通过；TypeScript 无严重错误。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请补充前端质量检查脚本。配置 npm run lint、typecheck、build，修复阻塞构建的问题。可添加少量组件测试或页面 smoke test。
```

## T20-04 端到端演示链路测试

- **任务编号**：T20-04
- **任务名称**：端到端演示链路测试
- **优先级**：P2
- **任务目标**：保证比赛演示流程稳定。
- **涉及目录**：`tests/e2e 或 frontend/e2e`
- **涉及文件**：`demo.spec.ts`
- **前置依赖**：T22-02
- **具体实现要求**：输入：演示数据。输出：E2E 测试脚本。模拟登录、进入 Wiki、提问、生成资源、诊断、自进化。
- **验收标准**：一键运行能走完演示主链路。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请使用 Playwright 编写端到端演示测试。流程：登录演示学生账号，进入 dashboard，打开 Wiki，进行 AI 答疑，生成资源，提交练习，生成诊断，触发自进化。
```

---

# 第21阶段：Docker 部署

## T21-01 编写后端 Dockerfile

- **任务编号**：T21-01
- **任务名称**：编写后端 Dockerfile
- **优先级**：P0
- **任务目标**：后端可容器化运行。
- **涉及目录**：`backend/`
- **涉及文件**：`Dockerfile, .dockerignore`
- **前置依赖**：T03-01
- **具体实现要求**：输入：backend 项目。输出：后端镜像。安装依赖，启动 uvicorn。
- **验收标准**：docker build 成功；容器启动 /health 正常。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请为 backend 编写 Dockerfile 和 .dockerignore。镜像启动 FastAPI 服务，暴露 8000 端口，使用环境变量配置数据库和 Redis。
```

## T21-02 编写前端 Dockerfile

- **任务编号**：T21-02
- **任务名称**：编写前端 Dockerfile
- **优先级**：P0
- **任务目标**：前端可容器化运行。
- **涉及目录**：`frontend/`
- **涉及文件**：`Dockerfile, .dockerignore`
- **前置依赖**：T02-01
- **具体实现要求**：输入：frontend 项目。输出：前端镜像。构建 Next.js 并运行。
- **验收标准**：docker build 成功；容器启动可访问前端。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请为 frontend 编写 Dockerfile 和 .dockerignore。使用 Node 镜像构建 Next.js 项目，运行 npm run build 和 npm start。支持 NEXT_PUBLIC_API_BASE_URL 环境变量。
```

## T21-03 完善 docker-compose

- **任务编号**：T21-03
- **任务名称**：完善 docker-compose
- **优先级**：P0
- **任务目标**：一键启动前端、后端、PostgreSQL、Redis。
- **涉及目录**：`项目根目录`
- **涉及文件**：`docker-compose.yml, .env.example`
- **前置依赖**：T21-01, T21-02, T04-01
- **具体实现要求**：输入：服务配置。输出：完整 compose。包括 postgres + pgvector、redis、backend、frontend、volume。
- **验收标准**：docker compose up 后服务全部启动；前端可访问后端。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请完善根目录 docker-compose.yml，包含 postgres(pgvector)、redis、backend、frontend 服务，配置网络、volume、环境变量。确保 docker compose up 能启动完整开发环境。
```

## T21-04 编写部署文档

- **任务编号**：T21-04
- **任务名称**：编写部署文档
- **优先级**：P1
- **任务目标**：团队和评委可复现运行。
- **涉及目录**：`docs/`
- **涉及文件**：`docs/部署方案.md`
- **前置依赖**：T21-03
- **具体实现要求**：输入：Docker Compose 配置。输出：部署步骤。包含本地运行、环境变量、数据库迁移、演示数据初始化、常见问题。
- **验收标准**：按文档可完成启动；命令准确。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请编写 docs/部署方案.md。说明如何配置 .env、启动 docker compose、执行数据库迁移、初始化演示数据、访问前端和后端接口，并列出常见错误排查。
```

---

# 第22阶段：演示数据

## T22-01 构造《数据结构》初始知识库文件

- **任务编号**：T22-01
- **任务名称**：构造《数据结构》初始知识库文件
- **优先级**：P0
- **任务目标**：准备比赛要求的完整高校专业课程输入。
- **涉及目录**：`data/seed_knowledge/data_structure`
- **涉及文件**：`课程大纲.md, 各章节讲义.md, 知识点列表.csv, 知识点关系.csv, 题库.json`
- **前置依赖**：T01-01
- **具体实现要求**：输入：数据结构课程设计。输出：结构化初始资料。至少包含绪论、线性表、栈和队列、树、图、排序等章节。
- **验收标准**：目录完整；资料可被解析；知识点关系清晰。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请在 data/seed_knowledge/data_structure 构造《数据结构》初始课程知识库。包含课程大纲、章节讲义、知识点列表.csv、知识点关系.csv、练习题 JSON、常见错误总结。内容简洁但要完整可演示。
```

## T22-02 实现演示数据初始化脚本

- **任务编号**：T22-02
- **任务名称**：实现演示数据初始化脚本
- **优先级**：P0
- **任务目标**：一键导入演示课程、学生、Wiki、题目、策略。
- **涉及目录**：`backend/app/scripts 或 scripts/`
- **涉及文件**：`scripts/seed_demo.py, backend/app/services/demo_seed_service.py`
- **前置依赖**：T22-01, T07-02, T15-01, T11-01
- **具体实现要求**：输入：seed_knowledge 文件。输出：数据库演示数据。创建 admin_demo、student_demo、数据结构课程、知识点、Wiki、题目、画像、策略。
- **验收标准**：运行脚本后前端可直接演示主链路。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现演示数据初始化脚本 scripts/seed_demo.py。导入《数据结构》课程、知识点、Wiki 页面、题目、演示学生画像、学习记忆、自进化策略和推荐数据。脚本可重复运行，避免重复插入。
```

## T22-03 实现管理员一键初始化演示数据

- **任务编号**：T22-03
- **任务名称**：实现管理员一键初始化演示数据
- **优先级**：P1
- **任务目标**：管理员端可初始化演示环境。
- **涉及目录**：`backend/app/api/v1, frontend/app/admin/system`
- **涉及文件**：`api/v1/admin.py, SeedDemoDataButton.tsx`
- **前置依赖**：T22-02, T18-04
- **具体实现要求**：输入：admin 请求。输出：seed 结果。调用 demo seed service，返回创建数量。
- **验收标准**：管理员页面点击后可初始化数据；有成功/失败提示。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请实现 POST /api/v1/admin/demo/seed，并在 /admin/system 增加一键初始化演示数据按钮。返回创建的用户、课程、Wiki、题目、策略数量。
```

## T22-04 准备演示脚本数据状态

- **任务编号**：T22-04
- **任务名称**：准备演示脚本数据状态
- **优先级**：P1
- **任务目标**：保证答辩演示有明确流程。
- **涉及目录**：`docs/`
- **涉及文件**：`docs/演示数据说明.md`
- **前置依赖**：T22-02
- **具体实现要求**：输入：演示数据。输出：账号、课程、演示路径说明。列出登录账号、演示问题、演示错题、自进化触发步骤。
- **验收标准**：文档能指导队员完整演示。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请编写 docs/演示数据说明.md，说明演示账号、课程、初始 Wiki、推荐问题、练习题、自进化触发条件和完整演示流程。
```

---

# 第23阶段：比赛材料

## T23-01 整理项目 README 完整版

- **任务编号**：T23-01
- **任务名称**：整理项目 README 完整版
- **优先级**：P0
- **任务目标**：让项目仓库具备完整说明。
- **涉及目录**：`项目根目录`
- **涉及文件**：`README.md`
- **前置依赖**：T21-04, T22-02
- **具体实现要求**：输入：项目功能和启动方式。输出：完整 README。包含项目简介、创新点、架构、技术栈、启动、演示账号、目录结构。
- **验收标准**：README 可用于评委快速理解和运行项目。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请完善根目录 README.md。包含项目简介、核心创新、技术栈、系统架构、目录结构、启动方式、演示账号、核心演示流程和注意事项。
```

## T23-02 编写答辩稿

- **任务编号**：T23-02
- **任务名称**：编写答辩稿
- **优先级**：P1
- **任务目标**：准备答辩陈述材料。
- **涉及目录**：`docs/`
- **涉及文件**：`docs/答辩稿.md`
- **前置依赖**：T23-01
- **具体实现要求**：输入：项目文档。输出：5-8 分钟答辩稿。突出赛题契合、创新点、系统闭环、可控自进化、LLM Wiki。
- **验收标准**：语言自然；逻辑清楚；不过度夸大。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请编写 docs/答辩稿.md，面向中国软件杯 A3 赛题，控制在 5-8 分钟讲述。重点说明项目背景、核心功能、技术架构、LLM Wiki、自进化、多智能体、演示流程和创新价值。
```

## T23-03 编写演示视频脚本

- **任务编号**：T23-03
- **任务名称**：编写演示视频脚本
- **优先级**：P1
- **任务目标**：准备录屏视频流程。
- **涉及目录**：`docs/`
- **涉及文件**：`docs/演示视频脚本.md`
- **前置依赖**：T22-04
- **具体实现要求**：输入：演示数据说明。输出：分镜脚本。按登录、上传资料、生成 Wiki、答疑、资源、练习、诊断、自进化、管理员日志排序。
- **验收标准**：每个镜头有操作、旁白、预期画面。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请编写 docs/演示视频脚本.md。按 3-5 分钟视频设计分镜，包含操作步骤、旁白和展示重点，覆盖登录、Wiki、AI 答疑、资源生成、练习诊断、自进化和 Agent 日志。
```

## T23-04 整理支撑材料说明

- **任务编号**：T23-04
- **任务名称**：整理支撑材料说明
- **优先级**：P1
- **任务目标**：解释提交材料和系统支撑点。
- **涉及目录**：`docs/`
- **涉及文件**：`docs/支撑材料说明.md`
- **前置依赖**：T23-01
- **具体实现要求**：输入：项目文档和代码结构。输出：支撑材料说明。列出源码、文档、演示数据、部署方案、测试材料、视频脚本。
- **验收标准**：可直接放入比赛提交材料。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请编写 docs/支撑材料说明.md，说明本项目提交材料包含哪些内容：源码、设计文档、数据库设计、API 文档、演示数据、部署脚本、测试说明、演示视频脚本和答辩稿。
```

## T23-05 编写评委可能质疑问题 FAQ

- **任务编号**：T23-05
- **任务名称**：编写评委可能质疑问题 FAQ
- **优先级**：P2
- **任务目标**：提前准备答辩追问。
- **涉及目录**：`docs/`
- **涉及文件**：`docs/答辩FAQ.md`
- **前置依赖**：T23-02
- **具体实现要求**：输入：项目创新点和风险点。输出：FAQ。覆盖自进化是否安全、和普通 RAG 区别、为什么不做完整教师端、如何避免概念堆砌、数据来源。
- **验收标准**：FAQ 回答具体、克制、可信。
- **Stitch 前端联动规范**：本任务如涉及前端或用户可见能力，必须优先保留现有 Stitch 静态页视觉与导航，在 `frontend/public/stitch-pages/*.html` 和 `zhixue-static-api.js` 中接入真实 `/api/v1` 后端；不得默认重做 React 页面。若本任务只涉及后端/数据库/文档，也必须在完成说明中明确对应 Stitch 页面是否需要同步联动；后端能力完成但页面未接入时，不得宣称阶段完成。
- **给 Codex 的提示词**：

```text
请编写 docs/答辩FAQ.md，整理评委可能追问的问题和回答，包括自进化边界、LLM Wiki 与 RAG 区别、多智能体是否概念堆砌、教师端范围、数据隐私、系统可落地性、演示数据真实性。
```

---

# 24. 推荐执行顺序

## 24.1 MVP 主线

优先完成以下 P0 任务，确保项目能形成可演示闭环：

1. `T01-01` 创建 Monorepo 项目骨架
1. `T01-02` 整理 docs 文档入口
1. `T02-01` 初始化 Next.js 前端工程
1. `T02-02` 配置 Tailwind CSS 与 shadcn/ui
1. `T02-03` 实现学生端与管理员端 Layout
1. `T02-04` 实现前端请求封装与 Auth Store
1. `T03-01` 初始化 FastAPI 后端工程
1. `T03-02` 实现统一响应与异常处理
1. `T03-03` 建立模块化 Router 结构
1. `T04-01` 配置 SQLAlchemy 与 Alembic
1. `T04-02` 实现核心数据库模型首批
1. `T04-03` 实现 JWT 注册登录接口
1. `T04-04` 实现当前用户与权限依赖
1. `T08-01` 实现统一 LLM Provider 基类
1. `T08-03` 实现 Prompt 版本读取和渲染
1. `T09-01` 实现 BaseAgent 和 AgentResult
1. `T09-02` 实现 AgentRegistry 与 Orchestrator
1. `T09-03` 实现 Agent 运行日志
1. `T09-04` 实现 MVP Agent 类占位
1. `T05-01` 实现课程 CRUD 后端
1. `T05-03` 实现资料上传与本地存储
1. `T05-05` 实现文档文本解析
1. `T06-01` 实现知识点和文档切片模型
1. `T06-02` 实现文本切片服务
1. `T06-03` 实现 Embedding 生成与入库
1. `T06-04` 实现向量检索接口
1. `T07-01` 实现 Wiki 数据模型和迁移
1. `T07-02` 实现 Wiki 页面 CRUD 和版本
1. `T07-03` 实现从资料生成 Wiki 页面
1. `T07-05` 实现 Wiki 前端列表和详情页
1. `T08-02` 实现 OpenAI Compatible 适配器
1. `T10-01` 实现学生画像服务与 API
1. `T10-02` 实现学习行为记录服务
1. `T10-03` 实现学习记忆 API
1. `T11-01` 实现自进化数据模型
1. `T11-02` 实现 Evolution Analyze 接口
1. `T11-03` 实现策略应用与回滚
1. `T13-01` 实现资源数据模型和 API
1. `T13-02` 实现资源生成 Agent 和接口
1. `T13-04` 实现资源生成前端
1. `T14-01` 实现 Tutor Chat 后端
1. `T14-03` 实现答疑前端页面
1. `T15-01` 实现 Quiz 和 Question 模型/API
1. `T15-02` 实现 Quiz Agent 生成题目
1. `T15-03` 实现答题提交与错题本
1. `T16-01` 实现诊断报告模型/API
1. `T16-02` 实现 Diagnosis Agent
1. `T16-03` 实现推荐模型/API
1. `T21-01` 编写后端 Dockerfile
1. `T21-02` 编写前端 Dockerfile
1. `T21-03` 完善 docker-compose
1. `T22-01` 构造《数据结构》初始知识库文件
1. `T22-02` 实现演示数据初始化脚本
1. `T23-01` 整理项目 README 完整版

## 24.2 比赛增强

P0 完成后，优先补齐 P1 中与展示直接相关的任务：前端美化、自进化页面、学习路径、管理员日志、演示数据、答辩稿。

## 24.3 可延后内容

P2 任务包括完整教师端预留、知识图谱高级展示、复杂动效、E2E 测试、答辩 FAQ 等，可在主链路稳定后完成。

---
# 25. 最小可演示闭环

项目至少需要跑通以下链路：

```text
注册/登录
  → 创建《数据结构》课程
  → 上传课程资料
  → 解析、切片、向量检索
  → 生成 LLM Wiki 页面
  → 学生 AI 答疑
  → 保存回答到 Wiki
  → 生成个性化学习资源
  → 生成练习并提交答案
  → 生成学习诊断
  → 更新学生画像与记忆
  → 触发自进化策略分析
  → 展示推荐与 Agent 日志
```

只要这条链路稳定，项目就具备软件杯 A3 赛题的核心展示能力。
