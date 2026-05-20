# AGENTS.md

项目名称：智学工坊——基于自进化学习智能体与 LLM Wiki 的个性化资源生成学习空间  
项目类型：中国软件杯 A3 赛题作品  
适用对象：Codex、AI 编程助手、团队开发者  
文档目的：规定本项目中 AI 编程助手的工作边界、代码规范、实现顺序和禁止事项。

---

# 1. 项目目标

本项目面向高校学生，构建一个基于大模型的个性化学习空间。系统应能够围绕学生学习过程完成以下闭环：

```text
课程资料上传
  → 文档解析与切片
  → 向量检索知识库构建
  → LLM Wiki 学习空间生成
  → AI Tutor 个性化答疑
  → 个性化学习资源生成
  → 练习题生成与答题
  → 错题分析与学习诊断
  → 学生画像与长期记忆更新
  → 自进化策略生成
  → 学习路径与推荐更新
```

本项目不是简单聊天机器人，也不是普通资料管理系统，而是一个能够持续理解学生、沉淀知识、生成资源、诊断学习状态并受控优化策略的学习智能体系统。

---

# 2. 赛题背景

本项目对应中国软件杯 A3 赛题：

> 基于大模型的个性化资源生成与学习多智能体系统开发。

系统必须体现以下能力：

1. 面向高校专业课程；
2. 能构造至少一门完整课程的初始知识库；
3. 支持个性化学习资源生成；
4. 支持学习过程中的多智能体协作；
5. 支持学习状态分析与个性化推荐；
6. 支持学生端完整学习闭环；
7. 具备可演示、可部署、可解释的工程实现。

本项目默认使用《数据结构》作为初始演示课程。

---

# 3. 核心创新点

## 3.1 自进化学习智能体

自进化不是自动修改代码，而是受控更新以下对象：

1. 学生长期画像；
2. 学生学习偏好；
3. 学生薄弱知识点；
4. 学生常见错误模式；
5. 学生适合的解释风格；
6. 个性化提示词参数；
7. 学习策略版本；
8. 推荐策略记录；
9. Wiki 知识组织结构建议。

所有自进化更新必须满足：

```text
可解释
可记录
可版本化
可回滚
有证据
有风险等级
```

严禁让 Agent 自动修改源代码、数据库结构、权限规则或部署配置。

## 3.2 LLM Wiki 学习空间

LLM Wiki 不是普通笔记，也不是简单 RAG 文档库。它是学生个人学习知识空间。

LLM Wiki 必须支持：

1. 知识点页面；
2. 页面来源追溯；
3. 页面版本管理；
4. 页面关系链接；
5. AI 整理与学生编辑；
6. 错题、答疑、诊断、资源与知识点关联；
7. 个人学习知识图谱。

## 3.3 多智能体学习闭环

系统采用自研轻量多智能体编排，不使用过度复杂的自治 Agent。每个 Agent 必须有明确职责、输入、输出、工具边界和日志记录。

核心 Agent 包括：

1. Orchestrator Agent；
2. Profile Agent；
3. Memory Agent；
4. Wiki Agent；
5. Knowledge Agent；
6. Planner Agent；
7. Resource Agent；
8. Quiz Agent；
9. Tutor Agent；
10. Diagnosis Agent；
11. Recommend Agent；
12. Evolution Agent；
13. Review Agent。

---

# 4. 技术栈

## 4.1 Frontend

```text
Next.js App Router
TypeScript
Tailwind CSS
shadcn/ui
Framer Motion
Recharts
```

## 4.2 Backend

```text
FastAPI
Python
SQLAlchemy
Alembic
Pydantic
```

## 4.3 Database

```text
PostgreSQL
pgvector
Redis
```

## 4.4 AI

```text
统一 LLM Provider 抽象层
OpenAI-compatible Adapter
Mock Provider
Embedding Provider
Prompt 版本管理
```

## 4.5 Deployment

```text
Docker Compose
```

---

# 5. 目录结构

Codex 必须遵守以下目录结构。不要随意新增平行架构。

```text
zhixue-workshop/
├── frontend/                         # Next.js 前端
│   ├── app/
│   ├── components/
│   ├── services/
│   ├── stores/
│   ├── hooks/
│   ├── lib/
│   ├── types/
│   └── public/
│
├── backend/                          # FastAPI 后端
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── v1/
│   │   ├── agents/
│   │   ├── agent_tools/
│   │   ├── core/
│   │   ├── db/
│   │   ├── llm/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── rag/
│   │   ├── storage/
│   │   ├── workers/
│   │   └── utils/
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── data/
│   └── seed_knowledge/
│       └── data_structure/
│
├── docs/
├── scripts/
├── docker-compose.yml
├── .env.example
├── README.md
└── AGENTS.md
```

---

# 6. 代码风格

## 6.1 通用原则

1. 每次只完成当前任务，不要扩大修改范围。
2. 不要一次性重写整个项目。
3. 不要破坏已有功能。
4. 不要删除已有文档、接口、模型和页面，除非任务明确要求。
5. 不要引入与技术栈不一致的新框架。
6. 不要把业务逻辑写死在页面组件或 API Router 中。
7. 不要为了快速完成任务牺牲数据结构、权限和可维护性。
8. 代码必须可读、可测试、可扩展。
9. 所有业务功能必须和 `docs/` 中的设计文档保持一致。
10. 实现和文档冲突时，优先遵守文档；确需调整时，必须说明原因。

## 6.2 TypeScript 规范

1. 尽量避免 `any`。
2. API 响应必须定义类型。
3. 组件 Props 必须定义 interface 或 type。
4. 服务层函数必须定义返回类型。
5. 不要在页面中直接拼接复杂请求逻辑，应放入 `services/`。

## 6.3 Python 规范

1. 使用类型注解。
2. Service 层写业务逻辑。
3. Repository 层写数据库访问。
4. API Router 只做参数接收、权限校验和响应返回。
5. Agent 类只负责智能体任务，不直接绕过 Service 写数据库。
6. 大模型调用必须通过 LLM Provider。
7. 异常必须使用统一异常体系，不直接抛裸字符串异常。

---

# 7. 命名规范

## 7.1 前端命名

| 对象 | 规范 | 示例 |
|---|---|---|
| React 组件 | PascalCase | `WikiPageCard.tsx` |
| hooks | camelCase，use 开头 | `useCurrentCourse.ts` |
| service 文件 | camelCase + Service | `wikiService.ts` |
| 类型文件 | camelCase | `wiki.ts` |
| 页面目录 | kebab-case 或 Next.js 约定 | `learning-paths` |
| store | camelCase + Store | `authStore.ts` |

## 7.2 后端命名

| 对象 | 规范 | 示例 |
|---|---|---|
| Python 文件 | snake_case | `wiki_service.py` |
| 类名 | PascalCase | `WikiService` |
| 函数名 | snake_case | `generate_from_material` |
| Pydantic Schema | PascalCase | `WikiPageCreate` |
| SQLAlchemy Model | PascalCase | `WikiPage` |
| 数据库表 | snake_case 复数 | `wiki_pages` |
| API Router 文件 | snake_case | `learning_paths.py` |

## 7.3 Agent 命名

Agent 类必须使用 PascalCase，并以 `Agent` 结尾。

示例：

```python
class TutorAgent(BaseAgent):
    name = "TutorAgent"
```

---

# 8. 前端开发规范

## 8.1 页面开发

1. 页面文件只负责组合组件和处理页面级状态。
2. 可复用 UI 必须放入 `components/`。
3. API 请求必须放入 `services/`。
4. 类型定义必须放入 `types/`。
5. 全局状态放入 `stores/`。
6. 页面应遵守 `docs/UI设计规范.md`。
7. 不要做普通后台模板风格。
8. 核心页面必须展示“依据、来源、推荐理由或 Agent 状态”。

## 8.2 必须使用的 UI 风格

1. 柔和渐变背景；
2. 卡片式布局；
3. 大圆角；
4. 轻微阴影；
5. 清晰信息层级；
6. 教育科技感；
7. Wiki 知识空间感；
8. Agent 协作过程可视化。

## 8.3 禁止的 UI 风格

1. 普通后台表格模板；
2. 廉价 AI 机器人插画；
3. 霓虹强发光；
4. 彩虹渐变；
5. 过度动画；
6. 大面积纯黑；
7. 颜色随机；
8. 无来源、无解释的 AI 输出。

## 8.4 前端 API 调用

前端不得直接使用裸 `fetch` 散落在页面中。必须通过：

```text
frontend/lib/request.ts
frontend/services/*
```

所有 API 响应统一使用：

```ts
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  request_id: string
}
```

---

# 9. 后端开发规范

## 9.1 分层规范

后端必须遵守：

```text
API Router
  → Service
  → Repository
  → Model
  → Database
```

Agent 相关流程：

```text
API Router
  → Service
  → Orchestrator / Agent
  → Tools / Service
  → Repository
  → Database
```

## 9.2 API Router 规则

API Router 只允许做：

1. 接收参数；
2. 调用依赖获取当前用户；
3. 调用 Service；
4. 返回统一响应；
5. 抛出业务异常。

不要在 Router 中写复杂业务逻辑、数据库查询、大模型调用或 Agent 编排。

## 9.3 Service 规则

Service 负责：

1. 业务流程；
2. 权限上下文处理；
3. 调用 Repository；
4. 调用 Agent；
5. 调用 LLM Provider；
6. 事务控制；
7. 结果整理。

## 9.4 Repository 规则

Repository 负责：

1. 数据库查询；
2. 创建、更新、删除；
3. 分页；
4. 条件过滤；
5. 不写业务决策。

---

# 10. 数据库迁移规范

## 10.1 必须使用 Migration

所有数据库结构变化必须通过 Alembic migration 完成。

禁止：

1. 直接手写临时 SQL 改线上表；
2. 在代码中自动创建业务表；
3. 修改模型但不生成 migration；
4. 删除字段但不处理历史数据；
5. 随意重命名表或字段。

## 10.2 Migration 要求

每次修改数据库结构后必须：

1. 更新 SQLAlchemy Model；
2. 生成 Alembic migration；
3. 检查 migration 内容；
4. 确保 upgrade 可执行；
5. 确保 downgrade 不为空或有明确说明；
6. 更新相关 Schema；
7. 更新相关 API；
8. 必要时更新 docs。

## 10.3 pgvector 规范

使用 pgvector 时：

1. 必须启用 `vector` 扩展；
2. 向量维度必须与 Embedding 模型一致；
3. 检索必须带 `course_id` 过滤；
4. 不要跨学生泄露私有资料；
5. 无真实 Embedding 时必须使用 Mock Embedding 保证流程可演示。

---

# 11. API 设计规范

## 11.1 基础路径

所有业务 API 使用：

```text
/api/v1
```

## 11.2 统一响应

必须返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "request_id": "req_xxx"
}
```

错误响应：

```json
{
  "code": 40001,
  "message": "参数错误",
  "detail": "course_id 不能为空",
  "request_id": "req_xxx"
}
```

## 11.3 权限要求

1. 学生只能访问自己的数据。
2. 管理员可以访问管理端数据。
3. 教师端只作为课程内容维护预留，不实现学生个人学习数据访问。
4. 所有涉及 `user_id` 的查询必须校验当前用户。
5. 所有涉及 `course_id` 的查询必须校验课程归属。

## 11.4 API 文档一致性

接口必须与以下文档保持一致：

```text
docs/API接口设计.md
docs/数据库设计.md
docs/前端页面设计.md
```

实现接口前必须先检查对应文档。

---

# 12. LLM Wiki 开发规范

## 12.1 Wiki 页面原则

LLM Wiki 页面不是普通文本。每个页面应尽量具备：

1. 页面类型；
2. 标题；
3. 摘要；
4. 结构化内容；
5. Markdown 内容；
6. 来源引用；
7. 页面版本；
8. 关联知识点；
9. 页面关系；
10. 创建者和更新时间。

## 12.2 来源追溯要求

所有由 AI 生成或整理的重要 Wiki 内容必须尽量绑定来源。

来源类型包括：

```text
document
chat
resource
exercise
diagnosis
manual
```

没有可靠来源时，必须标记为：

```text
AI 推断内容，建议核对资料。
```

## 12.3 版本管理要求

所有 Wiki 页面创建、编辑、AI 补全、问答保存、资源保存、回滚操作都必须写入：

```text
wiki_page_versions
```

更新页面时不要覆盖历史版本。

## 12.4 Wiki 关系要求

Wiki 页面关系使用：

```text
wiki_links
```

关系类型包括：

```text
prerequisite
contains
belongs_to
similar
confused_with
supports
applied_to
next
example_of
mistake_of
resource_for
```

不要用自由文本随意表示关系类型。

---

# 13. 自进化 Agent 开发规范

## 13.1 自进化边界

自进化允许更新：

1. 学生画像；
2. 学习偏好；
3. 长期记忆；
4. 答疑风格策略；
5. 资源生成策略；
6. 推荐策略；
7. 复习策略；
8. Prompt 参数；
9. Wiki 结构建议。

自进化禁止更新：

1. 源代码；
2. 数据库结构；
3. 权限规则；
4. 安全配置；
5. API Key；
6. 部署配置；
7. 用户原始资料；
8. 历史答题记录；
9. 历史行为日志。

## 13.2 策略版本要求

每次自进化策略生成必须写入：

```text
evolution_strategies
```

必须包含：

1. strategy_type；
2. version_no；
3. before_snapshot；
4. after_snapshot；
5. change_summary；
6. evidence；
7. risk_level；
8. status；
9. previous_strategy_id；
10. created_at。

## 13.3 风险等级

| 风险等级 | 处理方式 |
|---|---|
| low | 可自动生效 |
| medium | 需要用户确认 |
| high | 需要管理员确认 |

## 13.4 回滚要求

所有已生效策略必须支持回滚。

回滚时：

1. 不删除历史策略；
2. 将目标策略设为 active；
3. 将当前策略设为 rollbacked；
4. 记录回滚原因；
5. 保留完整版本链。

---

# 14. 多智能体开发规范

## 14.1 Agent 类规范

每个 Agent 必须继承：

```python
BaseAgent
```

并实现：

```python
async def run(self, context: AgentContext) -> AgentResult:
    ...
```

## 14.2 Agent 输入输出

Agent 输入必须使用：

```python
AgentContext
```

Agent 输出必须使用：

```python
AgentResult
```

不要让 Agent 返回随意结构。

## 14.3 Agent 不得越权

Agent 不允许：

1. 直接绕过 Service 修改数据库；
2. 直接读取其他学生数据；
3. 直接修改系统配置；
4. 自动修改代码；
5. 自动执行 migration；
6. 自动删除用户数据。

## 14.4 Agent 日志

每次 Agent 执行必须尽量记录：

1. agent_name；
2. task_type；
3. input_payload；
4. output_payload；
5. status；
6. error_message；
7. duration_ms；
8. created_at；
9. finished_at。

对应表：

```text
agent_runs
```

## 14.5 Review Agent

关键生成内容必须经过 Review Agent 或规则校验：

1. Wiki 自动生成；
2. 资源生成；
3. Tutor 回答；
4. 自进化策略；
5. 诊断建议；
6. 推荐理由。

Review Agent 负责检查：

1. 是否有来源；
2. 是否偏离知识点；
3. 是否存在明显幻觉；
4. 是否需要人工确认；
5. 风险等级是否合理。

---

# 15. 大模型调用规范

## 15.1 必须通过 LLM Provider

所有大模型调用必须经过：

```text
backend/app/llm/provider.py
```

禁止在业务代码中直接调用具体厂商 SDK。

## 15.2 Provider 结构

至少支持：

1. Mock Provider；
2. OpenAI-compatible Provider；
3. Embedding Provider；
4. stream_chat；
5. chat；
6. embedding。

## 15.3 无 API Key 时的行为

当没有真实大模型 API Key 时，必须使用 Mock Provider，保证以下流程仍可演示：

1. Wiki 生成；
2. AI 答疑；
3. 资源生成；
4. 练习题生成；
5. 学习诊断；
6. 自进化策略分析；
7. 学习记忆反思。

不得因为没有真实 API Key 导致系统主链路无法演示。

## 15.4 Prompt 规范

Prompt 不得散落在业务代码中。应优先放入：

```text
backend/app/prompts/
```

或数据库表：

```text
prompt_versions
```

Prompt 必须按 Agent 和场景区分：

```text
tutor.qa
wiki.generate
resource.generate
diagnosis.generate
evolution.analyze
review.check
```

## 15.5 LLM 日志

每次大模型调用必须尽量写入：

```text
llm_call_logs
```

记录：

1. provider；
2. model_name；
3. agent_run_id；
4. prompt_version_id；
5. token 统计；
6. latency_ms；
7. status；
8. error_message。

请求和响应内容必须脱敏，不要保存 API Key。

---

# 16. 测试规范

## 16.1 后端测试

后端测试使用 pytest。

至少覆盖：

1. Auth 注册登录；
2. JWT 鉴权；
3. Course CRUD；
4. Material 上传；
5. Wiki 页面 CRUD；
6. Tutor Chat Mock 流程；
7. Resource Generate Mock 流程；
8. Quiz Submit；
9. Diagnosis Generate；
10. Evolution Analyze。

## 16.2 前端测试

前端至少保证：

1. TypeScript 检查通过；
2. `npm run build` 通过；
3. 关键页面不报运行时错误；
4. 登录后路由跳转正确；
5. 核心表单能提交；
6. API 错误能显示提示。

## 16.3 Mock 测试

涉及大模型的测试必须使用 Mock Provider，不依赖真实网络和真实 API Key。

## 16.4 每次完成任务后必须运行

根据任务类型选择：

```text
后端任务：
pytest 或至少启动 FastAPI 检查

前端任务：
npm run typecheck
npm run build

数据库任务：
alembic upgrade head

Docker 任务：
docker compose config
```

如果无法运行，必须在输出中说明原因。

---

# 17. 安全与隐私规范

## 17.1 用户数据隔离

1. 学生只能访问自己的画像、记忆、Wiki、资源、诊断、推荐。
2. 查询必须带当前用户过滤。
3. 不允许通过 URL 参数访问他人数据。
4. 管理员接口必须使用 admin 权限依赖。

## 17.2 密钥安全

禁止提交：

1. API Key；
2. 数据库密码；
3. JWT Secret；
4. 真实用户隐私数据；
5. `.env` 文件。

只能提交：

```text
.env.example
```

## 17.3 学习记忆安全

学生长期记忆必须允许：

1. 查看；
2. 删除；
3. 归档；
4. 说明来源证据。

不要保存无意义闲聊，不要保存敏感个人信息，除非用户明确要求且与学习个性化强相关。

## 17.4 AI 输出安全

AI 输出必须：

1. 尽量基于课程资料和 Wiki；
2. 无依据时明确说明；
3. 不编造来源；
4. 不生成违法、危险或侵犯隐私内容；
5. 不冒充教师或官方评价；
6. 不给出不可验证的学习结论。

---

# 18. 禁止事项

Codex 或任何 AI 编程助手禁止执行以下行为：

1. 不要一次性重写整个项目。
2. 不要在未要求时重构大范围代码。
3. 不要删除已有功能。
4. 不要改变技术栈。
5. 不要引入大型新框架替代现有设计。
6. 不要绕过 docs 文档自行设计另一套架构。
7. 不要直接修改数据库结构而不生成 migration。
8. 不要让 Agent 自动修改代码。
9. 不要让 Agent 自动修改权限规则。
10. 不要让 Agent 自动修改部署配置。
11. 不要在业务代码中硬编码 API Key。
12. 不要让前端直接访问数据库。
13. 不要让前端绕过后端调用大模型。
14. 不要让学生访问其他学生数据。
15. 不要生成没有来源的 Wiki 内容而不标注。
16. 不要覆盖 Wiki 历史版本。
17. 不要生成无法回滚的自进化策略。
18. 不要用假数据冒充真实模型效果。
19. 不要写“暂时随便实现”却不标记 TODO。
20. 不要为了演示牺牲安全边界。

---

# 19. 每次 Codex 执行任务前必须做什么

Codex 在开始任何任务前必须完成以下检查：

## 19.1 阅读任务

确认当前任务的：

1. 任务编号；
2. 任务名称；
3. 优先级；
4. 前置依赖；
5. 涉及目录；
6. 涉及文件；
7. 验收标准。

任务来源通常在：

```text
docs/Codex开发任务拆分.md
```

## 19.2 阅读相关文档

根据任务类型阅读对应文档：

| 任务类型 | 必读文档 |
|---|---|
| PRD / 需求 | `docs/PRD.md` |
| 系统架构 | `docs/06_系统架构设计.md` |
| API | `docs/API接口设计.md` |
| 数据库 | `docs/数据库设计.md` |
| 前端 | `docs/前端页面设计.md`、`docs/UI设计规范.md` |
| Wiki | `docs/LLM Wiki学习空间设计.md` |
| Agent | `docs/多智能体架构设计.md` |
| 自进化 | `docs/自进化学习智能体设计.md` |
| 部署 | `docs/部署方案.md` |

## 19.3 检查已有代码

必须先查看相关已有文件，确认：

1. 是否已有实现；
2. 是否已有类似组件或 Service；
3. 是否已有类型定义；
4. 是否已有接口路径；
5. 是否已有数据库模型；
6. 是否存在迁移文件；
7. 是否可能影响其他模块。

## 19.4 明确修改范围

执行前必须明确：

```text
本次只修改哪些文件
不修改哪些文件
是否需要 migration
是否需要更新文档
是否需要新增测试
```

不要扩大任务范围。

---

# 20. 每次 Codex 完成任务后必须输出什么

每次完成任务后，Codex 必须输出以下内容：

## 20.1 修改摘要

格式：

```text
本次完成：
1. ...
2. ...
3. ...
```

## 20.2 修改文件列表

格式：

```text
修改文件：
- backend/app/api/v1/wiki.py
- backend/app/services/wiki_service.py
- frontend/app/student/wiki/page.tsx
```

## 20.3 数据库变更说明

如有数据库变化，必须说明：

```text
数据库变更：
- 新增表：xxx
- 新增字段：xxx
- Migration 文件：alembic/versions/xxxx.py
```

如无数据库变化，写：

```text
数据库变更：无
```

## 20.4 API 变更说明

如有 API 变化，必须说明：

```text
API 变更：
- POST /api/v1/wiki/pages/generate-from-material
- GET /api/v1/wiki/pages
```

如无 API 变化，写：

```text
API 变更：无
```

## 20.5 测试结果

必须说明执行了什么检查。

示例：

```text
已执行：
- pytest backend/tests/test_wiki.py
- npm run typecheck
- npm run build
```

如果没有执行，必须说明原因：

```text
未执行测试：
- 当前环境未安装依赖
- 缺少数据库连接
```

不要谎称测试通过。

## 20.6 风险与后续建议

必须说明：

1. 当前实现是否为 Mock；
2. 是否依赖真实 LLM API Key；
3. 是否还有 TODO；
4. 是否影响其他模块；
5. 下一步建议做哪个任务。

---

# 21. 当前项目主链路优先级

Codex 应优先保证以下主链路可运行：

```text
Auth 登录注册
  → Course 创建课程
  → Material 上传资料
  → Document Chunk 文档切片
  → RAG Search 检索
  → Wiki Generate 生成 Wiki
  → Tutor Chat AI 答疑
  → Resource Generate 资源生成
  → Quiz Generate 生成练习
  → Answer Submit 提交答案
  → Diagnosis Generate 学习诊断
  → Profile / Memory 更新
  → Evolution Analyze 自进化策略
  → Recommendation 推荐下一步
  → Agent Logs 展示调用链
```

未打通该主链路前，不要优先投入复杂装饰性功能。

---

# 22. Mock Provider 要求

本项目必须能在没有真实大模型 API Key 的情况下完整演示。

Mock Provider 必须返回结构化、可解释、与课程学习场景相关的内容。

Mock 内容要求：

1. 不能只返回 `mock response`。
2. 必须根据输入问题生成合理占位回答。
3. 对数据结构课程演示要有基本可读内容。
4. Tutor Mock 应返回 answer、citations、related_knowledge_points。
5. Wiki Mock 应返回页面结构。
6. Resource Mock 应返回 Markdown 资源。
7. Diagnosis Mock 应返回薄弱点和建议。
8. Evolution Mock 应返回策略更新建议和证据。

---

# 23. 项目验收核心标准

任何实现都应服务于以下验收标准：

## 23.1 功能闭环

必须能演示：

1. 资料上传；
2. Wiki 生成；
3. AI 答疑；
4. 资源生成；
5. 练习与错题；
6. 学习诊断；
7. 学生画像；
8. 学习记忆；
9. 自进化策略；
10. 推荐下一步；
11. Agent 日志。

## 23.2 创新可见

必须在前端明确展示：

1. LLM Wiki 与普通笔记不同；
2. 自进化不是自动改代码，而是策略版本更新；
3. 多智能体不是概念堆砌，而是有调用链；
4. 推荐不是随机推荐，而是基于画像、诊断和 Wiki；
5. AI 输出有来源和依据。

## 23.3 工程可落地

必须满足：

1. Docker Compose 可启动；
2. 数据库 migration 可运行；
3. 无真实 API Key 时可用 Mock；
4. 前后端接口一致；
5. 权限隔离正确；
6. README 和 docs 完整。

---

# 24. 最终执行原则

Codex 在本项目中的最高优先级规则：

```text
只完成当前任务。
保持文档一致。
不破坏已有功能。
数据库变化走 migration。
AI 调用走 LLM Provider。
无 Key 使用 Mock Provider。
Wiki 保留来源和版本。
自进化保留证据、版本和回滚。
Agent 保留输入、输出和日志。
```

任何与以上规则冲突的实现，都应停止并说明原因。
