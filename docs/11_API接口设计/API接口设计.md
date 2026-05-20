# 智学工坊 API 接口设计文档

文档版本：V1.0  
适用位置：`docs/API接口设计.md`  
后端技术栈：FastAPI + Python  
前端技术栈：Next.js + TypeScript  
数据格式：JSON  
认证方式：JWT Bearer Token  
项目名称：智学工坊——基于自进化学习智能体与 LLM Wiki 的个性化资源生成学习空间

---

# 1. API 总体规范

## 1.1 基础路径

```http
/api/v1
```

## 1.2 认证方式

除登录、注册接口外，其余接口默认需要 JWT。

请求头：

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

文件上传接口使用：

```http
Content-Type: multipart/form-data
Authorization: Bearer <access_token>
```

## 1.3 统一响应格式

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "request_id": "req_20260520_000001"
}
```

分页响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 100
  },
  "request_id": "req_20260520_000001"
}
```

错误响应：

```json
{
  "code": 40001,
  "message": "参数错误",
  "detail": "course_id 不能为空",
  "request_id": "req_20260520_000002"
}
```

## 1.4 通用错误码

| 错误码 | 含义 | HTTP 状态码 |
|---:|---|---:|
| 0 | 成功 | 200 |
| 40001 | 参数错误 | 400 |
| 40002 | 请求体格式错误 | 400 |
| 40101 | 未登录或 Token 无效 | 401 |
| 40102 | Token 已过期 | 401 |
| 40301 | 权限不足 | 403 |
| 40401 | 资源不存在 | 404 |
| 40901 | 资源冲突 | 409 |
| 42201 | 业务校验失败 | 422 |
| 42901 | 请求过于频繁 | 429 |
| 50001 | 服务器内部错误 | 500 |
| 50002 | 大模型调用失败 | 500 |
| 50003 | Agent 执行失败 | 500 |
| 50004 | 文件解析失败 | 500 |
| 50005 | 向量检索失败 | 500 |

## 1.5 权限标识

| 权限 | 说明 |
|---|---|
| Public | 无需登录 |
| Student | 学生登录后访问，只能访问自己的数据 |
| Admin | 管理员访问 |
| Owner | 资源所有者访问 |
| System | 系统内部调用 |

## 1.6 通用分页参数

```http
?page=1&page_size=20
```

## 1.7 通用列表响应字段

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

---

# 2. 模块 API 总览

| 模块 | 路径前缀 | 说明 |
|---|---|---|
| Auth | `/api/v1/auth` | 登录、注册、刷新 Token |
| User | `/api/v1/users` | 用户信息 |
| Student Profile | `/api/v1/student/profile` | 学生画像 |
| Student Memory | `/api/v1/student/memory` | 学习记忆 |
| Course | `/api/v1/courses` | 课程空间 |
| Material | `/api/v1/materials` | 学习资料上传与解析 |
| Knowledge | `/api/v1/knowledge` | 知识点与知识库 |
| Wiki | `/api/v1/wiki` | LLM Wiki 页面 |
| Wiki Link | `/api/v1/wiki/links` | Wiki 知识关系 |
| Learning Path | `/api/v1/learning-paths` | 学习路径 |
| Resource | `/api/v1/resources` | 个性化资源生成 |
| Quiz | `/api/v1/quizzes` | 练习题 |
| Tutor | `/api/v1/tutor` | AI 答疑 |
| Diagnosis | `/api/v1/diagnosis` | 学习诊断 |
| Recommendation | `/api/v1/recommendations` | 推荐 |
| Evolution | `/api/v1/evolution` | 自进化策略 |
| Agent | `/api/v1/agents` | 多智能体 |
| Admin | `/api/v1/admin` | 管理端 |

---

# 3. Auth 用户认证 API

## 3.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 用户注册 | POST | `/api/v1/auth/register` | 创建学生账号 | Public | users, student_profiles | 否 | 否 | 否 | 否 |
| 用户登录 | POST | `/api/v1/auth/login` | 登录并返回 JWT | Public | users | 否 | 否 | 否 | 否 |
| 刷新 Token | POST | `/api/v1/auth/refresh` | 刷新访问令牌 | Public | users | 否 | 否 | 否 | 否 |
| 退出登录 | POST | `/api/v1/auth/logout` | 前端清理 Token，后端可记录日志 | Student/Admin | users | 否 | 否 | 否 | 否 |

## 3.2 用户注册

```http
POST /api/v1/auth/register
```

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| username | string | 是 | 用户名 |
| email | string | 否 | 邮箱 |
| password | string | 是 | 密码 |
| role | string | 否 | 默认 student |

请求示例：

```json
{
  "username": "student_demo",
  "email": "student@example.com",
  "password": "123456",
  "role": "student"
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | 用户 ID |
| username | string | 用户名 |
| role | string | 角色 |
| status | string | 状态 |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "u_001",
    "username": "student_demo",
    "role": "student",
    "status": "active"
  },
  "request_id": "req_001"
}
```

错误码：`40001`、`40901`、`50001`

## 3.3 用户登录

```http
POST /api/v1/auth/login
```

请求示例：

```json
{
  "username": "student_demo",
  "password": "123456"
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "jwt_access_token",
    "refresh_token": "jwt_refresh_token",
    "token_type": "bearer",
    "expires_in": 7200,
    "user": {
      "id": "u_001",
      "username": "student_demo",
      "role": "student"
    }
  },
  "request_id": "req_002"
}
```

错误码：`40001`、`40101`、`40301`

---

# 4. User 用户信息 API

## 4.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 获取当前用户 | GET | `/api/v1/users/me` | 获取当前登录用户信息 | Student/Admin | users | 否 | 否 | 否 | 否 |
| 更新当前用户 | PUT | `/api/v1/users/me` | 更新昵称、头像等基础信息 | Student/Admin | users | 否 | 否 | 否 | 否 |
| 修改密码 | PUT | `/api/v1/users/me/password` | 修改当前用户密码 | Student/Admin | users | 否 | 否 | 否 | 否 |

## 4.2 获取当前用户

```http
GET /api/v1/users/me
```

请求参数：无

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "u_001",
    "username": "student_demo",
    "email": "student@example.com",
    "role": "student",
    "status": "active",
    "avatar_url": null,
    "last_login_at": "2026-05-20T10:00:00Z"
  },
  "request_id": "req_003"
}
```

错误码：`40101`、`40401`

---

# 5. Student Profile 学生画像 API

## 5.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 获取学生画像 | GET | `/api/v1/student/profile` | 获取当前学生画像 | Student | student_profiles, learning_preferences | 否 | 否 | 否 | 否 |
| 更新基础画像 | PUT | `/api/v1/student/profile` | 学生手动更新学习目标、专业等 | Student | student_profiles | 否 | 否 | 否 | 否 |
| 获取画像摘要 | GET | `/api/v1/student/profile/summary` | 获取答疑/推荐用画像摘要 | Student | student_profiles, student_memories | 否 | 否 | 否 | 否 |
| 重新计算画像 | POST | `/api/v1/student/profile/rebuild` | 基于学习记录重算画像 | Student | student_profiles, learning_records | 是 | Profile Agent | 否 | 是 |

## 5.2 获取学生画像

```http
GET /api/v1/student/profile?course_id=c_001
```

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| course_id | string | 否 | 指定课程画像上下文 |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "u_001",
    "major": "计算机科学与技术",
    "grade": "大二",
    "learning_goal": "补强数据结构基础",
    "profile_summary": "学生在递归调用栈和循环队列上存在薄弱点。",
    "mastery_snapshot": {
      "栈": 76,
      "递归调用栈": 45
    },
    "weak_points": [
      {
        "knowledge_id": "k_009",
        "name": "递归调用栈",
        "severity": "high",
        "reason": "连续错题和多次追问"
      }
    ],
    "error_patterns": [
      "调用顺序和返回顺序混淆"
    ],
    "version_no": 3
  },
  "request_id": "req_004"
}
```

错误码：`40101`、`40401`

---

# 6. Student Memory 学习记忆 API

## 6.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 获取学习记忆 | GET | `/api/v1/student/memory` | 获取长期学习记忆 | Student | student_memories | 否 | 否 | 否 | 否 |
| 反思并生成记忆 | POST | `/api/v1/student/memory/reflect` | 从近期学习记录提炼长期记忆 | Student | student_memories, learning_records | 是 | Memory Agent | 否 | 是 |
| 删除学习记忆 | DELETE | `/api/v1/student/memory/{id}` | 删除或归档某条记忆 | Student | student_memories | 否 | 否 | 否 | 是 |
| 更新记忆状态 | PATCH | `/api/v1/student/memory/{id}` | 归档、恢复、修改置信度 | Student | student_memories | 否 | 否 | 否 | 是 |

## 6.2 重点接口：GET /api/v1/student/memory

```http
GET /api/v1/student/memory?course_id=c_001&memory_type=weak_point
```

功能说明：  
获取当前学生的长期学习记忆，可按课程和记忆类型过滤。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| course_id | string | 否 | 课程 ID |
| memory_type | string | 否 | weak_point / preference / error_pattern / goal |
| status | string | 否 | active / archived |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

请求示例：

```http
GET /api/v1/student/memory?course_id=c_001&status=active&page=1&page_size=20
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | 记忆 ID |
| memory_type | string | 记忆类型 |
| content | string | 记忆内容 |
| evidence | array | 证据 |
| confidence | number | 置信度 |
| status | string | 状态 |
| created_at | string | 创建时间 |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "mem_001",
        "memory_type": "weak_point",
        "content": "学生在递归调用栈相关题目中经常混淆调用顺序和返回顺序。",
        "evidence": [
          {
            "type": "mistake",
            "id": "mb_001"
          },
          {
            "type": "chat",
            "id": "msg_002"
          }
        ],
        "confidence": 0.86,
        "status": "active",
        "created_at": "2026-05-20T10:00:00Z"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  },
  "request_id": "req_005"
}
```

错误码：`40101`、`40301`

权限要求：Student，只能查询自己的记忆。  
对应数据库表：`student_memories`  
是否调用大模型：否  
是否触发 Agent：否  
是否更新 Wiki：否  
是否更新学生记忆：否

## 6.3 重点接口：POST /api/v1/student/memory/reflect

```http
POST /api/v1/student/memory/reflect
```

功能说明：  
根据近期学习行为、问答记录、错题记录和反馈，让 Memory Agent 提炼长期学习记忆。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| course_id | string | 否 | 课程 ID |
| time_range_days | int | 否 | 分析最近多少天，默认 7 |
| memory_types | array | 否 | 指定提炼的记忆类型 |
| force | boolean | 否 | 是否强制重新分析 |

请求示例：

```json
{
  "course_id": "c_001",
  "time_range_days": 7,
  "memory_types": ["weak_point", "preference", "error_pattern"],
  "force": false
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| new_memories | array | 新增记忆 |
| updated_memories | array | 更新记忆 |
| archived_memories | array | 归档记忆 |
| agent_run_id | string | Agent 运行 ID |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "new_memories": [
      {
        "id": "mem_002",
        "memory_type": "preference",
        "content": "学生更偏好分步骤解释和代码示例。",
        "confidence": 0.78
      }
    ],
    "updated_memories": [],
    "archived_memories": [],
    "agent_run_id": "ar_001"
  },
  "request_id": "req_006"
}
```

错误码：`40101`、`50002`、`50003`

权限要求：Student  
对应数据库表：`student_memories`、`learning_records`、`agent_runs`、`llm_call_logs`  
是否调用大模型：是  
是否触发 Agent：是，Memory Agent  
是否更新 Wiki：否  
是否更新学生记忆：是

---

# 7. Course 课程 API

## 7.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 创建课程 | POST | `/api/v1/courses` | 创建个人课程空间 | Student/Admin | courses | 否 | 否 | 否 | 否 |
| 课程列表 | GET | `/api/v1/courses` | 获取课程列表 | Student/Admin | courses | 否 | 否 | 否 | 否 |
| 课程详情 | GET | `/api/v1/courses/{id}` | 获取课程详情 | Owner/Admin | courses | 否 | 否 | 否 | 否 |
| 更新课程 | PUT | `/api/v1/courses/{id}` | 更新课程信息 | Owner/Admin | courses | 否 | 否 | 否 | 否 |
| 删除课程 | DELETE | `/api/v1/courses/{id}` | 归档或删除课程 | Owner/Admin | courses | 否 | 否 | 否 | 否 |
| 初始化演示课程 | POST | `/api/v1/courses/seed-demo` | 初始化《数据结构》演示课程 | Admin | courses, knowledge_points, wiki_pages | 否 | 可选 | 是 | 否 |

## 7.2 创建课程

```http
POST /api/v1/courses
```

请求示例：

```json
{
  "title": "数据结构",
  "course_code": "CS-DS-001",
  "description": "计算机专业核心课程",
  "subject": "计算机科学与技术",
  "visibility": "private"
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "c_001",
    "title": "数据结构",
    "course_code": "CS-DS-001",
    "status": "active"
  },
  "request_id": "req_007"
}
```

错误码：`40101`、`40001`

---

# 8. Material 学习资料 API

## 8.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 上传资料 | POST | `/api/v1/materials/upload` | 上传 PDF/DOCX/MD/TXT | Student/Admin | course_materials | 否 | 可选 | 否 | 否 |
| 资料列表 | GET | `/api/v1/materials` | 查询课程资料 | Student/Admin | course_materials | 否 | 否 | 否 | 否 |
| 资料详情 | GET | `/api/v1/materials/{id}` | 查询资料详情 | Owner/Admin | course_materials | 否 | 否 | 否 | 否 |
| 删除资料 | DELETE | `/api/v1/materials/{id}` | 删除资料和切片 | Owner/Admin | course_materials, document_chunks | 否 | 否 | 可选 | 否 |
| 解析资料 | POST | `/api/v1/materials/{id}/parse` | 解析资料为文本切片 | Owner/Admin | course_materials, document_chunks | 否 | Knowledge Agent 可选 | 否 | 否 |
| 查询解析状态 | GET | `/api/v1/materials/{id}/parse-status` | 查询解析进度 | Owner/Admin | course_materials | 否 | 否 | 否 | 否 |

## 8.2 上传资料

```http
POST /api/v1/materials/upload
Content-Type: multipart/form-data
```

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| course_id | string | 是 | 课程 ID |
| file | file | 是 | 上传文件 |
| auto_parse | boolean | 否 | 是否上传后自动解析 |
| auto_generate_wiki | boolean | 否 | 是否解析后自动生成 Wiki |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "mat_001",
    "course_id": "c_001",
    "file_name": "栈和队列讲义.pdf",
    "file_type": "pdf",
    "parse_status": "pending"
  },
  "request_id": "req_008"
}
```

错误码：`40001`、`40101`、`50004`

---

# 9. Knowledge 知识库 API

## 9.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 知识点列表 | GET | `/api/v1/knowledge/points` | 查询课程知识点 | Student/Admin | knowledge_points | 否 | 否 | 否 | 否 |
| 创建知识点 | POST | `/api/v1/knowledge/points` | 手动创建知识点 | Student/Admin | knowledge_points | 否 | 否 | 可选 | 否 |
| 更新知识点 | PUT | `/api/v1/knowledge/points/{id}` | 更新知识点信息 | Owner/Admin | knowledge_points | 否 | 否 | 可选 | 否 |
| 删除知识点 | DELETE | `/api/v1/knowledge/points/{id}` | 删除知识点 | Owner/Admin | knowledge_points | 否 | 否 | 可选 | 否 |
| 从资料抽取知识点 | POST | `/api/v1/knowledge/extract-from-material` | 从资料抽取知识点和关系 | Owner/Admin | knowledge_points, wiki_links | 是 | Knowledge Agent | 可选 | 否 |
| 文档切片检索 | POST | `/api/v1/knowledge/search` | 基于 pgvector 检索资料片段 | Student/Admin | document_chunks | 否 | 否 | 否 | 否 |

## 9.2 文档切片检索

```http
POST /api/v1/knowledge/search
```

请求示例：

```json
{
  "course_id": "c_001",
  "query": "递归为什么和栈有关？",
  "top_k": 5,
  "knowledge_id": null
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "chunk_id": "chunk_001",
        "content": "栈是一种后进先出的线性结构，递归调用过程会使用函数调用栈保存现场。",
        "score": 0.87,
        "source_title": "栈和队列讲义",
        "page_no": 12
      }
    ]
  },
  "request_id": "req_009"
}
```

错误码：`40101`、`50005`

---

# 10. Wiki LLM Wiki API

## 10.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| Wiki 页面列表 | GET | `/api/v1/wiki/pages` | 查询课程 Wiki 页面 | Student/Admin | wiki_pages | 否 | 否 | 否 | 否 |
| Wiki 页面详情 | GET | `/api/v1/wiki/pages/{id}` | 查询页面详情 | Owner/Admin | wiki_pages, wiki_sources, wiki_links | 否 | 否 | 否 | 否 |
| 创建 Wiki 页面 | POST | `/api/v1/wiki/pages` | 手动创建页面 | Student/Admin | wiki_pages, wiki_page_versions | 否 | 否 | 是 | 否 |
| 更新 Wiki 页面 | PUT | `/api/v1/wiki/pages/{id}` | 手动编辑页面 | Owner/Admin | wiki_pages, wiki_page_versions | 否 | 否 | 是 | 否 |
| 删除 Wiki 页面 | DELETE | `/api/v1/wiki/pages/{id}` | 归档页面 | Owner/Admin | wiki_pages | 否 | 否 | 是 | 否 |
| 从资料生成 Wiki | POST | `/api/v1/wiki/pages/generate-from-material` | 从课程资料生成 Wiki 页面 | Owner/Admin | wiki_pages, wiki_sources, wiki_links | 是 | Knowledge + Wiki + Review Agent | 是 | 否 |
| 从笔记更新 Wiki | POST | `/api/v1/wiki/pages/update-from-note` | 将学生笔记整理进 Wiki | Student | wiki_pages, wiki_page_versions, wiki_sources | 是 | Wiki Agent | 是 | 可选 |
| 总结 Wiki 页面 | POST | `/api/v1/wiki/pages/{id}/summarize` | 总结页面并生成摘要 | Owner/Admin | wiki_pages, wiki_page_versions | 是 | Wiki Agent | 是 | 否 |
| 页面版本列表 | GET | `/api/v1/wiki/pages/{id}/versions` | 查询页面历史版本 | Owner/Admin | wiki_page_versions | 否 | 否 | 否 | 否 |
| 页面回滚 | POST | `/api/v1/wiki/pages/{id}/rollback` | 回滚页面版本 | Owner/Admin | wiki_pages, wiki_page_versions | 否 | 否 | 是 | 否 |
| 来源列表 | GET | `/api/v1/wiki/pages/{id}/sources` | 查询页面来源 | Owner/Admin | wiki_sources | 否 | 否 | 否 | 否 |

---

## 10.2 重点接口：POST /api/v1/wiki/pages/generate-from-material

```http
POST /api/v1/wiki/pages/generate-from-material
```

功能说明：  
从某个课程资料中抽取知识点，生成 LLM Wiki 页面、页面来源和页面关系。适合资料上传后自动构建 Wiki。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| course_id | string | 是 | 课程 ID |
| material_id | string | 是 | 资料 ID |
| page_types | array | 否 | 生成页面类型，默认 knowledge |
| overwrite_existing | boolean | 否 | 是否覆盖已有页面，默认 false |
| generate_links | boolean | 否 | 是否生成页面关系，默认 true |
| review_required | boolean | 否 | 是否调用 Review Agent 审核，默认 true |

请求示例：

```json
{
  "course_id": "c_001",
  "material_id": "mat_001",
  "page_types": ["knowledge"],
  "overwrite_existing": false,
  "generate_links": true,
  "review_required": true
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| generated_pages | array | 生成的 Wiki 页面 |
| updated_pages | array | 更新的 Wiki 页面 |
| skipped_pages | array | 跳过页面 |
| links | array | 生成的知识关系 |
| sources | array | 来源记录 |
| agent_run_id | string | Agent 运行 ID |
| review_result | object | 审核结果 |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "generated_pages": [
      {
        "id": "wp_001",
        "title": "栈",
        "page_type": "knowledge",
        "knowledge_id": "k_001",
        "version_no": 1
      },
      {
        "id": "wp_002",
        "title": "递归调用栈",
        "page_type": "knowledge",
        "knowledge_id": "k_002",
        "version_no": 1
      }
    ],
    "updated_pages": [],
    "skipped_pages": [],
    "links": [
      {
        "source_page_id": "wp_001",
        "target_page_id": "wp_002",
        "relation_type": "supports"
      }
    ],
    "sources": [
      {
        "page_id": "wp_001",
        "chunk_id": "chunk_001",
        "source_type": "document"
      }
    ],
    "agent_run_id": "ar_101",
    "review_result": {
      "status": "pass",
      "issues": []
    }
  },
  "request_id": "req_010"
}
```

错误码：`40001`、`40101`、`40301`、`40401`、`50002`、`50003`

权限要求：Owner/Admin  
对应数据库表：`course_materials`、`document_chunks`、`knowledge_points`、`wiki_pages`、`wiki_page_versions`、`wiki_sources`、`wiki_links`、`agent_runs`、`llm_call_logs`  
是否调用大模型：是  
是否触发 Agent：是，Knowledge Agent、Wiki Agent、Review Agent  
是否更新 Wiki：是  
是否更新学生记忆：否

---

## 10.3 重点接口：POST /api/v1/wiki/pages/update-from-note

```http
POST /api/v1/wiki/pages/update-from-note
```

功能说明：  
学生输入一段笔记，系统自动识别关联知识点，并整理到已有 Wiki 页面或创建新页面。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| course_id | string | 是 | 课程 ID |
| note_content | string | 是 | 学生笔记 |
| target_page_id | string | 否 | 指定更新的页面 ID |
| auto_detect_knowledge | boolean | 否 | 是否自动识别知识点 |
| update_mode | string | 否 | append / merge / create_if_missing |

请求示例：

```json
{
  "course_id": "c_001",
  "note_content": "递归函数每次调用时会把当前函数的局部变量和返回地址压入调用栈。",
  "target_page_id": "wp_002",
  "auto_detect_knowledge": true,
  "update_mode": "merge"
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| page_id | string | 更新的页面 ID |
| version_no | int | 新版本号 |
| updated_sections | array | 更新的小节 |
| detected_knowledge | array | 识别到的知识点 |
| agent_run_id | string | Agent 运行 ID |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "page_id": "wp_002",
    "version_no": 3,
    "updated_sections": ["personal_notes", "core_concepts"],
    "detected_knowledge": [
      {
        "knowledge_id": "k_002",
        "name": "递归调用栈"
      }
    ],
    "agent_run_id": "ar_102"
  },
  "request_id": "req_011"
}
```

错误码：`40001`、`40101`、`40401`、`50002`、`50003`

权限要求：Student，只能更新自己的 Wiki。  
对应数据库表：`wiki_pages`、`wiki_page_versions`、`wiki_sources`、`learning_records`、`agent_runs`、`llm_call_logs`  
是否调用大模型：是  
是否触发 Agent：是，Wiki Agent  
是否更新 Wiki：是  
是否更新学生记忆：可选。若笔记体现长期偏好或薄弱点，可触发 Memory Agent。

---

## 10.4 重点接口：POST /api/v1/wiki/pages/{id}/summarize

```http
POST /api/v1/wiki/pages/{id}/summarize
```

功能说明：  
对指定 Wiki 页面进行 AI 总结，可更新页面摘要，也可生成“复习摘要”小节。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| summary_type | string | 否 | brief / review / exam |
| update_page | boolean | 否 | 是否写回页面 |
| include_mistakes | boolean | 否 | 是否结合错题总结 |
| include_profile | boolean | 否 | 是否结合学生画像 |

请求示例：

```json
{
  "summary_type": "review",
  "update_page": true,
  "include_mistakes": true,
  "include_profile": true
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| page_id | string | 页面 ID |
| summary | string | 生成摘要 |
| version_no | int | 更新后的版本号 |
| agent_run_id | string | Agent 运行 ID |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "page_id": "wp_002",
    "summary": "递归调用栈用于保存每次递归调用的现场信息，理解它需要先掌握栈的后进先出特性。",
    "version_no": 4,
    "agent_run_id": "ar_103"
  },
  "request_id": "req_012"
}
```

错误码：`40101`、`40301`、`40401`、`50002`、`50003`

权限要求：Owner/Admin  
对应数据库表：`wiki_pages`、`wiki_page_versions`、`mistake_books`、`student_profiles`、`agent_runs`、`llm_call_logs`  
是否调用大模型：是  
是否触发 Agent：是，Wiki Agent  
是否更新 Wiki：取决于 `update_page`  
是否更新学生记忆：否

---

# 11. Wiki Link 知识关系 API

## 11.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 获取页面关系 | GET | `/api/v1/wiki/links` | 查询课程或页面关系 | Student/Admin | wiki_links | 否 | 否 | 否 | 否 |
| 创建页面关系 | POST | `/api/v1/wiki/links` | 创建知识关系 | Student/Admin | wiki_links | 否 | 否 | 是 | 否 |
| 更新页面关系 | PUT | `/api/v1/wiki/links/{id}` | 更新关系类型或说明 | Owner/Admin | wiki_links | 否 | 否 | 是 | 否 |
| 删除页面关系 | DELETE | `/api/v1/wiki/links/{id}` | 删除或拒绝关系 | Owner/Admin | wiki_links | 否 | 否 | 是 | 否 |
| 自动生成关系 | POST | `/api/v1/wiki/links/generate` | 基于 Wiki 页面自动生成关系 | Owner/Admin | wiki_links, wiki_pages | 是 | Wiki Agent/Knowledge Agent | 是 | 否 |

## 11.2 创建关系

```http
POST /api/v1/wiki/links
```

请求示例：

```json
{
  "course_id": "c_001",
  "source_page_id": "wp_001",
  "target_page_id": "wp_002",
  "relation_type": "supports",
  "description": "理解栈有助于理解递归调用栈"
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "wl_001",
    "relation_type": "supports",
    "status": "active"
  },
  "request_id": "req_013"
}
```

错误码：`40001`、`40101`、`40401`

---

# 12. Learning Path 学习路径 API

## 12.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 学习路径列表 | GET | `/api/v1/learning-paths` | 查询路径列表 | Student | learning_paths | 否 | 否 | 否 | 否 |
| 学习路径详情 | GET | `/api/v1/learning-paths/{id}` | 查询路径详情 | Owner | learning_paths, learning_path_items | 否 | 否 | 否 | 否 |
| 生成学习路径 | POST | `/api/v1/learning-paths/generate` | 基于画像和知识图谱生成路径 | Student | learning_paths, learning_path_items | 是 | Planner Agent | 可选 | 否 |
| 更新路径节点状态 | PATCH | `/api/v1/learning-paths/items/{id}` | 标记完成、跳过 | Student | learning_path_items, learning_records | 否 | 可选 | 否 | 是 |
| 删除学习路径 | DELETE | `/api/v1/learning-paths/{id}` | 归档路径 | Owner | learning_paths | 否 | 否 | 否 | 否 |

## 12.2 生成学习路径

```http
POST /api/v1/learning-paths/generate
```

请求示例：

```json
{
  "course_id": "c_001",
  "goal": "补强递归和树遍历",
  "target_knowledge_ids": ["k_002", "k_010"],
  "path_type": "weakness_repair"
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "lp_001",
    "title": "递归与树遍历补弱路径",
    "reason": "你在递归调用栈和二叉树递归遍历上存在薄弱点。",
    "items": [
      {
        "id": "lpi_001",
        "title": "复习栈的后进先出特性",
        "item_type": "review",
        "order_index": 1
      },
      {
        "id": "lpi_002",
        "title": "学习递归调用栈",
        "item_type": "learn",
        "order_index": 2
      }
    ]
  },
  "request_id": "req_014"
}
```

错误码：`40101`、`50002`、`50003`

---

# 13. Resource 资源生成 API

## 13.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 生成资源 | POST | `/api/v1/resources/generate` | 个性化生成讲解/总结/例题/卡片 | Student | generated_resources | 是 | Resource Agent + Review Agent | 可选 | 可选 |
| 资源列表 | GET | `/api/v1/resources` | 查询生成资源 | Student | generated_resources | 否 | 否 | 否 | 否 |
| 资源详情 | GET | `/api/v1/resources/{id}` | 查询资源详情 | Owner | generated_resources | 否 | 否 | 否 | 否 |
| 保存资源到 Wiki | POST | `/api/v1/resources/{id}/save-to-wiki` | 将资源沉淀到 Wiki | Owner | generated_resources, wiki_pages, wiki_page_versions | 可选 | Wiki Agent | 是 | 否 |
| 删除资源 | DELETE | `/api/v1/resources/{id}` | 归档资源 | Owner | generated_resources | 否 | 否 | 否 | 否 |

## 13.2 重点接口：POST /api/v1/resources/generate

```http
POST /api/v1/resources/generate
```

功能说明：  
根据知识点、学生画像、Wiki 页面、RAG 检索结果和当前策略，生成个性化学习资源。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| course_id | string | 是 | 课程 ID |
| knowledge_id | string | 否 | 知识点 ID |
| wiki_page_id | string | 否 | Wiki 页面 ID |
| resource_type | string | 是 | explanation / summary / example / flashcard / review |
| requirement | string | 否 | 学生附加要求 |
| use_profile | boolean | 否 | 是否结合画像，默认 true |
| save_to_wiki | boolean | 否 | 是否生成后自动保存到 Wiki，默认 false |

请求示例：

```json
{
  "course_id": "c_001",
  "knowledge_id": "k_002",
  "wiki_page_id": "wp_002",
  "resource_type": "explanation",
  "requirement": "用适合初学者的方式解释递归调用栈",
  "use_profile": true,
  "save_to_wiki": false
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| resource_id | string | 资源 ID |
| title | string | 标题 |
| content | string | Markdown 内容 |
| citations | array | 来源 |
| personalized_reason | string | 个性化原因 |
| agent_run_id | string | Agent 运行 ID |
| review_result | object | 审核结果 |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "resource_id": "res_001",
    "title": "递归调用栈入门讲解",
    "content": "## 一句话理解\\n递归调用栈就是用栈保存每一次函数调用现场...",
    "citations": [
      {
        "source_type": "wiki",
        "page_id": "wp_002",
        "title": "递归调用栈"
      }
    ],
    "personalized_reason": "你最近在递归调用顺序相关题目中多次出错，因此本讲解采用分步骤方式说明。",
    "agent_run_id": "ar_201",
    "review_result": {
      "status": "pass"
    }
  },
  "request_id": "req_015"
}
```

错误码：`40001`、`40101`、`40401`、`50002`、`50003`

权限要求：Student  
对应数据库表：`generated_resources`、`wiki_pages`、`document_chunks`、`student_profiles`、`student_memories`、`prompt_versions`、`agent_runs`、`llm_call_logs`  
是否调用大模型：是  
是否触发 Agent：是，Resource Agent、Review Agent  
是否更新 Wiki：取决于 `save_to_wiki`  
是否更新学生记忆：可选，资源反馈后更新

---

# 14. Quiz 练习题 API

## 14.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 生成练习 | POST | `/api/v1/quizzes/generate` | 根据知识点生成练习 | Student | quizzes, questions | 是 | Quiz Agent | 否 | 否 |
| 测验列表 | GET | `/api/v1/quizzes` | 查询练习列表 | Student | quizzes | 否 | 否 | 否 | 否 |
| 测验详情 | GET | `/api/v1/quizzes/{id}` | 查询题目 | Student | quizzes, questions | 否 | 否 | 否 | 否 |
| 提交答案 | POST | `/api/v1/quizzes/{id}/submit` | 提交测验答案 | Student | answer_records, mistake_books, learning_records | 可选 | Diagnosis Agent | 可选 | 是 |
| 获取错题 | GET | `/api/v1/quizzes/mistakes` | 查询错题本 | Student | mistake_books | 否 | 否 | 否 | 否 |

## 14.2 生成练习

```http
POST /api/v1/quizzes/generate
```

请求示例：

```json
{
  "course_id": "c_001",
  "knowledge_id": "k_002",
  "quiz_type": "practice",
  "question_types": ["single_choice", "short_answer"],
  "difficulty": "medium",
  "count": 5
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "quiz_id": "quiz_001",
    "title": "递归调用栈练习",
    "questions": [
      {
        "id": "q_001",
        "question_type": "single_choice",
        "question_text": "递归调用过程中，函数现场通常保存在哪里？",
        "options": ["队列", "调用栈", "堆", "数组"]
      }
    ]
  },
  "request_id": "req_016"
}
```

错误码：`40101`、`50002`、`50003`

---

# 15. Tutor AI 答疑 API

## 15.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| AI 答疑 | POST | `/api/v1/tutor/chat` | 基于 RAG、Wiki、画像答疑 | Student | learning_records, agent_runs, llm_call_logs | 是 | Tutor Agent + Review Agent | 可选 | 可选 |
| 会话列表 | GET | `/api/v1/tutor/sessions` | 查询会话列表 | Student | 可扩展 chat_sessions | 否 | 否 | 否 | 否 |
| 会话详情 | GET | `/api/v1/tutor/sessions/{id}` | 查询会话消息 | Student | 可扩展 chat_messages | 否 | 否 | 否 | 否 |
| 保存回答到 Wiki | POST | `/api/v1/tutor/messages/{id}/save-to-wiki` | 将回答保存到 Wiki | Student | wiki_pages, wiki_page_versions, wiki_sources | 可选 | Wiki Agent | 是 | 否 |

说明：当前数据库设计未单独列 `chat_sessions`、`chat_messages`。MVP 可将聊天记录先写入 `learning_records.event_payload`；增强版建议新增独立聊天表。

## 15.2 重点接口：POST /api/v1/tutor/chat

```http
POST /api/v1/tutor/chat
```

功能说明：  
学生发起课程答疑。系统检索 RAG 文档切片、Wiki 页面、学生画像和学习记忆，由 Tutor Agent 生成个性化回答。支持普通 JSON 返回；如需流式输出，可增加 `stream=true`，后端使用 SSE。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| course_id | string | 是 | 课程 ID |
| question | string | 是 | 学生问题 |
| session_id | string | 否 | 会话 ID |
| knowledge_id | string | 否 | 指定知识点 |
| use_rag | boolean | 否 | 是否使用 RAG，默认 true |
| use_wiki | boolean | 否 | 是否使用 Wiki，默认 true |
| use_profile | boolean | 否 | 是否使用画像，默认 true |
| stream | boolean | 否 | 是否流式输出 |

请求示例：

```json
{
  "course_id": "c_001",
  "question": "递归为什么和栈有关？",
  "session_id": null,
  "knowledge_id": "k_002",
  "use_rag": true,
  "use_wiki": true,
  "use_profile": true,
  "stream": false
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| answer | string | 回答内容 |
| citations | array | 引用来源 |
| related_knowledge_points | array | 相关知识点 |
| follow_up_questions | array | 建议追问 |
| save_to_wiki_candidate | string | 可保存到 Wiki 的内容 |
| agent_run_id | string | Agent 运行 ID |
| memory_update_suggestion | object | 记忆更新建议 |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "answer": "递归和栈有关，是因为每一次函数调用都需要保存当前执行现场，后调用的函数会先返回，这正好符合栈的后进先出特性。",
    "citations": [
      {
        "source_type": "document",
        "chunk_id": "chunk_001",
        "source_title": "栈和队列讲义",
        "page_no": 12
      },
      {
        "source_type": "wiki",
        "page_id": "wp_002",
        "title": "递归调用栈"
      }
    ],
    "related_knowledge_points": [
      {
        "knowledge_id": "k_001",
        "name": "栈"
      },
      {
        "knowledge_id": "k_002",
        "name": "递归调用栈"
      }
    ],
    "follow_up_questions": [
      "递归调用栈中每一层保存了什么？",
      "递归函数什么时候开始返回？"
    ],
    "save_to_wiki_candidate": "递归调用栈可以理解为保存递归调用现场的栈结构。",
    "agent_run_id": "ar_301",
    "memory_update_suggestion": {
      "should_reflect": true,
      "reason": "学生正在学习递归调用栈，可能需要记录为关注知识点。"
    }
  },
  "request_id": "req_017"
}
```

错误码：`40001`、`40101`、`40401`、`50002`、`50003`、`50005`

权限要求：Student  
对应数据库表：`document_chunks`、`wiki_pages`、`wiki_sources`、`student_profiles`、`student_memories`、`learning_records`、`agent_runs`、`llm_call_logs`  
是否调用大模型：是  
是否触发 Agent：是，Tutor Agent、Review Agent，可选 Memory Agent  
是否更新 Wiki：默认否；用户保存回答时更新  
是否更新学生记忆：可选；可异步触发 Memory Agent

### 流式响应说明

当 `stream=true` 时：

```http
POST /api/v1/tutor/chat
Accept: text/event-stream
```

SSE 事件格式：

```text
event: delta
data: {"content": "递归"}

event: delta
data: {"content": "和栈有关"}

event: done
data: {"agent_run_id": "ar_301", "citations": []}
```

---

# 16. Diagnosis 学习诊断 API

## 16.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 生成诊断 | POST | `/api/v1/diagnosis/generate` | 基于学习记录生成诊断 | Student | diagnosis_reports, learning_records, mistake_books | 是 | Diagnosis Agent | 可选 | 是 |
| 诊断列表 | GET | `/api/v1/diagnosis/reports` | 查询诊断报告 | Student | diagnosis_reports | 否 | 否 | 否 | 否 |
| 诊断详情 | GET | `/api/v1/diagnosis/reports/{id}` | 查询诊断详情 | Student | diagnosis_reports | 否 | 否 | 否 | 否 |
| 查询掌握度 | GET | `/api/v1/diagnosis/mastery` | 查询知识点掌握情况 | Student | student_profiles, diagnosis_reports | 否 | 否 | 否 | 否 |

## 16.2 重点接口：POST /api/v1/diagnosis/generate

```http
POST /api/v1/diagnosis/generate
```

功能说明：  
基于答题记录、错题本、学习行为和 Wiki 关系生成学习诊断报告，并可触发画像更新、推荐和自进化分析。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| course_id | string | 是 | 课程 ID |
| report_type | string | 否 | manual / quiz / daily / weekly |
| knowledge_ids | array | 否 | 指定诊断知识点 |
| include_recommendation | boolean | 否 | 是否生成推荐 |
| trigger_evolution | boolean | 否 | 是否触发自进化分析 |

请求示例：

```json
{
  "course_id": "c_001",
  "report_type": "manual",
  "knowledge_ids": ["k_002"],
  "include_recommendation": true,
  "trigger_evolution": true
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| report_id | string | 诊断报告 ID |
| summary | string | 诊断摘要 |
| mastery_result | object | 掌握度结果 |
| weak_points | array | 薄弱点 |
| error_patterns | array | 错误模式 |
| recommended_actions | array | 建议动作 |
| recommendations | array | 推荐结果 |
| evolution_event_id | string | 自进化事件 ID |
| agent_run_id | string | Agent 运行 ID |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "report_id": "dr_001",
    "summary": "学生在递归调用栈上存在明显薄弱，主要问题是调用顺序和返回顺序混淆。",
    "mastery_result": {
      "k_002": {
        "name": "递归调用栈",
        "score": 45,
        "confidence": 0.82
      }
    },
    "weak_points": [
      {
        "knowledge_id": "k_002",
        "name": "递归调用栈",
        "severity": "high",
        "reason": "最近 5 次练习错误率超过 60%"
      }
    ],
    "error_patterns": [
      {
        "pattern": "调用顺序和返回顺序混淆",
        "evidence": ["mb_001", "ans_003"]
      }
    ],
    "recommended_actions": [
      "先复习栈的后进先出特性",
      "完成递归调用栈基础练习"
    ],
    "recommendations": [
      {
        "id": "rec_001",
        "title": "复习栈的基本操作"
      }
    ],
    "evolution_event_id": "ee_001",
    "agent_run_id": "ar_401"
  },
  "request_id": "req_018"
}
```

错误码：`40001`、`40101`、`50002`、`50003`

权限要求：Student  
对应数据库表：`diagnosis_reports`、`answer_records`、`mistake_books`、`learning_records`、`student_profiles`、`recommendations`、`evolution_events`、`agent_runs`、`llm_call_logs`  
是否调用大模型：是  
是否触发 Agent：是，Diagnosis Agent，可选 Recommend Agent、Evolution Agent  
是否更新 Wiki：可选；可将错因写入 Wiki  
是否更新学生记忆：是；可触发 Profile Agent / Memory Agent

---

# 17. Recommendation 推荐 API

## 17.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 推荐列表 | GET | `/api/v1/recommendations` | 查询推荐内容 | Student | recommendations | 否 | 否 | 否 | 否 |
| 刷新推荐 | POST | `/api/v1/recommendations/refresh` | 重新生成推荐 | Student | recommendations | 是 | Recommend Agent | 否 | 否 |
| 更新推荐状态 | PATCH | `/api/v1/recommendations/{id}` | 标记点击、完成、忽略 | Student | recommendations, learning_records | 否 | 可选 | 否 | 是 |
| 推荐反馈 | POST | `/api/v1/recommendations/{id}/feedback` | 对推荐进行反馈 | Student | user_feedback, learning_records | 否 | 可选 | 否 | 是 |

## 17.2 刷新推荐

```http
POST /api/v1/recommendations/refresh
```

请求示例：

```json
{
  "course_id": "c_001",
  "recommendation_types": ["knowledge", "resource", "quiz", "review"],
  "use_strategy": true
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "rec_001",
        "recommendation_type": "knowledge",
        "title": "复习栈的后进先出特性",
        "reason": "该知识点是理解递归调用栈的前置知识。",
        "priority": 1
      }
    ]
  },
  "request_id": "req_019"
}
```

---

# 18. Evolution 自进化策略 API

## 18.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 自进化分析 | POST | `/api/v1/evolution/analyze` | 分析是否需要更新策略 | Student/Admin | evolution_events, evolution_strategies | 是 | Evolution Agent + Review Agent | 可选 | 可选 |
| 策略列表 | GET | `/api/v1/evolution/strategies` | 查询策略版本 | Student/Admin | evolution_strategies | 否 | 否 | 否 | 否 |
| 策略详情 | GET | `/api/v1/evolution/strategies/{id}` | 查询策略详情 | Student/Admin | evolution_strategies | 否 | 否 | 否 | 否 |
| 应用策略 | POST | `/api/v1/evolution/strategies/apply` | 应用策略版本 | Student/Admin | evolution_strategies, learning_preferences | 否 | 可选 | 可选 | 可选 |
| 回滚策略 | POST | `/api/v1/evolution/strategies/{id}/rollback` | 回滚策略版本 | Student/Admin | evolution_strategies | 否 | 否 | 可选 | 可选 |
| 自进化事件列表 | GET | `/api/v1/evolution/events` | 查询自进化事件 | Student/Admin | evolution_events | 否 | 否 | 否 | 否 |

## 18.2 重点接口：POST /api/v1/evolution/analyze

```http
POST /api/v1/evolution/analyze
```

功能说明：  
根据学习行为、诊断报告、学生画像、长期记忆、反馈记录，判断是否需要生成新的学习策略版本。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| course_id | string | 否 | 课程 ID |
| trigger_type | string | 否 | manual / rule / scheduled |
| scope | string | 否 | course / global |
| focus | array | 否 | qa_style / resource_generation / recommendation / review |
| dry_run | boolean | 否 | true 时只分析不写入策略 |

请求示例：

```json
{
  "course_id": "c_001",
  "trigger_type": "manual",
  "scope": "course",
  "focus": ["qa_style", "resource_generation", "recommendation"],
  "dry_run": false
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| event_id | string | 自进化事件 ID |
| should_update | boolean | 是否建议更新 |
| strategies | array | 生成的策略 |
| wiki_suggestions | array | Wiki 优化建议 |
| review_result | object | 审核结果 |
| agent_run_id | string | Agent 运行 ID |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "event_id": "ee_001",
    "should_update": true,
    "strategies": [
      {
        "id": "es_001",
        "strategy_type": "qa_style",
        "version_no": 2,
        "change_summary": "递归相关答疑改为优先使用分步骤和代码示例。",
        "risk_level": "low",
        "status": "draft"
      }
    ],
    "wiki_suggestions": [
      {
        "page_id": "wp_002",
        "suggestion": "为递归调用栈页面补充调用顺序示意。"
      }
    ],
    "review_result": {
      "status": "pass",
      "need_human_confirm": false
    },
    "agent_run_id": "ar_501"
  },
  "request_id": "req_020"
}
```

错误码：`40101`、`50002`、`50003`

权限要求：Student/Admin。学生只能分析自己的策略；管理员可分析演示账号。  
对应数据库表：`evolution_events`、`evolution_strategies`、`student_profiles`、`student_memories`、`learning_records`、`diagnosis_reports`、`user_feedback`、`agent_runs`、`llm_call_logs`  
是否调用大模型：是  
是否触发 Agent：是，Evolution Agent、Review Agent  
是否更新 Wiki：可选，生成 Wiki 建议但不直接修改  
是否更新学生记忆：可选，可能产生策略性记忆

---

## 18.3 重点接口：POST /api/v1/evolution/strategies/apply

```http
POST /api/v1/evolution/strategies/apply
```

功能说明：  
应用某个自进化策略版本，使其成为当前生效策略。低风险策略可由系统自动应用，中高风险策略需要用户或管理员确认。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| strategy_id | string | 是 | 策略 ID |
| apply_scope | string | 否 | user_course / user_global |
| confirm | boolean | 是 | 是否确认应用 |
| note | string | 否 | 应用说明 |

请求示例：

```json
{
  "strategy_id": "es_001",
  "apply_scope": "user_course",
  "confirm": true,
  "note": "应用递归答疑风格优化策略"
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| strategy_id | string | 策略 ID |
| status | string | active |
| applied_effect | object | 应用影响 |
| previous_active_strategy_id | string | 之前生效策略 |

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "strategy_id": "es_001",
    "status": "active",
    "previous_active_strategy_id": "es_000",
    "applied_effect": {
      "qa_style": {
        "include_step_by_step": true,
        "include_code_example": true,
        "answer_length": "medium"
      }
    }
  },
  "request_id": "req_021"
}
```

错误码：`40001`、`40101`、`40301`、`40401`、`42201`

权限要求：Student/Admin  
对应数据库表：`evolution_strategies`、`learning_preferences`、`student_profiles`  
是否调用大模型：否  
是否触发 Agent：可选，Review Agent 用于应用前风险检查  
是否更新 Wiki：可选，若策略包含 Wiki 建议则后续触发 Wiki Agent  
是否更新学生记忆：可选，记录策略变化

---

# 19. Agent 多智能体 API

## 19.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| Agent 列表 | GET | `/api/v1/agents` | 查询可用 Agent | Admin | 可配置 | 否 | 否 | 否 | 否 |
| Agent 运行列表 | GET | `/api/v1/agents/runs` | 查询运行日志 | Student/Admin | agent_runs | 否 | 否 | 否 | 否 |
| Agent 运行详情 | GET | `/api/v1/agents/runs/{id}` | 查询运行详情 | Student/Admin | agent_runs, llm_call_logs | 否 | 否 | 否 | 否 |
| 手动执行 Agent | POST | `/api/v1/agents/run` | 调试或演示用 | Admin | agent_runs | 可选 | 指定 Agent | 可选 | 可选 |
| Agent 调用链 | GET | `/api/v1/agents/runs/{id}/trace` | 查询调用链 | Student/Admin | agent_runs, llm_call_logs | 否 | 否 | 否 | 否 |

## 19.2 Agent 运行详情

```http
GET /api/v1/agents/runs/ar_001
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "ar_001",
    "task_type": "course_qa",
    "agent_name": "TutorAgent",
    "status": "success",
    "duration_ms": 3200,
    "input_payload": {
      "question": "递归为什么和栈有关？"
    },
    "output_payload": {
      "answer_summary": "解释递归调用栈"
    },
    "llm_calls": [
      {
        "provider": "qwen",
        "model_name": "qwen-plus",
        "status": "success",
        "latency_ms": 2800
      }
    ]
  },
  "request_id": "req_022"
}
```

---

# 20. Admin 管理端 API

## 20.1 接口清单

| 接口名称 | 方法 | URL | 功能说明 | 权限 | 数据库表 | 调用大模型 | 触发 Agent | 更新 Wiki | 更新记忆 |
|---|---|---|---|---|---|---|---|---|---|
| 用户列表 | GET | `/api/v1/admin/users` | 管理用户 | Admin | users | 否 | 否 | 否 | 否 |
| 禁用用户 | PATCH | `/api/v1/admin/users/{id}/status` | 禁用或启用用户 | Admin | users | 否 | 否 | 否 | 否 |
| 模型配置列表 | GET | `/api/v1/admin/models` | 查询模型配置 | Admin | system_configs 可扩展 | 否 | 否 | 否 | 否 |
| 更新模型配置 | PUT | `/api/v1/admin/models/{id}` | 更新模型配置 | Admin | system_configs 可扩展 | 否 | 否 | 否 | 否 |
| Prompt 版本列表 | GET | `/api/v1/admin/prompts` | 查询 Prompt | Admin | prompt_versions | 否 | 否 | 否 | 否 |
| 创建 Prompt 版本 | POST | `/api/v1/admin/prompts` | 创建 Prompt 版本 | Admin | prompt_versions | 否 | 否 | 否 | 否 |
| 激活 Prompt 版本 | PATCH | `/api/v1/admin/prompts/{id}/activate` | 设置 Prompt 生效 | Admin | prompt_versions | 否 | 否 | 否 | 否 |
| 查看 LLM 日志 | GET | `/api/v1/admin/llm-logs` | 查看模型调用日志 | Admin | llm_call_logs | 否 | 否 | 否 | 否 |
| 初始化演示数据 | POST | `/api/v1/admin/demo/seed` | 初始化演示课程和学生数据 | Admin | 多表 | 否 | 可选 | 是 | 是 |

## 20.2 初始化演示数据

```http
POST /api/v1/admin/demo/seed
```

请求示例：

```json
{
  "dataset": "data_structure",
  "reset_existing": false,
  "include_student_history": true,
  "include_evolution_demo": true
}
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "course_id": "c_demo_ds",
    "student_user_id": "u_demo_student",
    "created": {
      "knowledge_points": 15,
      "wiki_pages": 8,
      "questions": 20,
      "learning_records": 30,
      "evolution_strategies": 1
    }
  },
  "request_id": "req_023"
}
```

错误码：`40101`、`40301`、`50001`

---

# 21. 前端开发接口使用建议

## 21.1 学生端首页需要调用

1. `GET /api/v1/users/me`
2. `GET /api/v1/courses`
3. `GET /api/v1/student/profile/summary`
4. `GET /api/v1/recommendations`
5. `GET /api/v1/learning-paths`

## 21.2 课程详情页需要调用

1. `GET /api/v1/courses/{id}`
2. `GET /api/v1/materials?course_id=...`
3. `GET /api/v1/wiki/pages?course_id=...`
4. `GET /api/v1/knowledge/points?course_id=...`
5. `GET /api/v1/diagnosis/mastery?course_id=...`

## 21.3 智能问答页需要调用

1. `POST /api/v1/tutor/chat`
2. `POST /api/v1/tutor/messages/{id}/save-to-wiki`
3. `POST /api/v1/student/memory/reflect`
4. `POST /api/v1/recommendations/refresh`

## 21.4 LLM Wiki 页面需要调用

1. `GET /api/v1/wiki/pages`
2. `GET /api/v1/wiki/pages/{id}`
3. `PUT /api/v1/wiki/pages/{id}`
4. `GET /api/v1/wiki/pages/{id}/versions`
5. `GET /api/v1/wiki/pages/{id}/sources`
6. `GET /api/v1/wiki/links`

## 21.5 学习诊断页需要调用

1. `POST /api/v1/diagnosis/generate`
2. `GET /api/v1/diagnosis/reports`
3. `GET /api/v1/student/profile`
4. `GET /api/v1/recommendations`

## 21.6 自进化展示页需要调用

1. `POST /api/v1/evolution/analyze`
2. `GET /api/v1/evolution/strategies`
3. `GET /api/v1/evolution/events`
4. `POST /api/v1/evolution/strategies/apply`
5. `POST /api/v1/evolution/strategies/{id}/rollback`

---

# 22. MVP 必须实现接口

MVP 阶段优先实现以下接口：

## 22.1 用户与课程

1. `POST /api/v1/auth/register`
2. `POST /api/v1/auth/login`
3. `GET /api/v1/users/me`
4. `POST /api/v1/courses`
5. `GET /api/v1/courses`
6. `GET /api/v1/courses/{id}`

## 22.2 资料与知识库

1. `POST /api/v1/materials/upload`
2. `POST /api/v1/materials/{id}/parse`
3. `GET /api/v1/materials`
4. `POST /api/v1/knowledge/search`
5. `GET /api/v1/knowledge/points`

## 22.3 Wiki

1. `POST /api/v1/wiki/pages/generate-from-material`
2. `GET /api/v1/wiki/pages`
3. `GET /api/v1/wiki/pages/{id}`
4. `PUT /api/v1/wiki/pages/{id}`
5. `GET /api/v1/wiki/pages/{id}/sources`
6. `GET /api/v1/wiki/links`

## 22.4 AI 学习闭环

1. `POST /api/v1/tutor/chat`
2. `POST /api/v1/resources/generate`
3. `POST /api/v1/quizzes/generate`
4. `POST /api/v1/quizzes/{id}/submit`
5. `POST /api/v1/diagnosis/generate`
6. `GET /api/v1/recommendations`

## 22.5 自进化与 Agent 展示

1. `GET /api/v1/student/profile`
2. `GET /api/v1/student/memory`
3. `POST /api/v1/student/memory/reflect`
4. `POST /api/v1/evolution/analyze`
5. `GET /api/v1/evolution/strategies`
6. `POST /api/v1/evolution/strategies/apply`
7. `GET /api/v1/agents/runs`

---

# 23. 增强版接口

增强版可以继续实现：

1. Wiki 矛盾检测；
2. Wiki 健康度检查；
3. Agent 调用链详细步骤；
4. Prompt 在线编辑和版本管理；
5. 推荐效果反馈分析；
6. 策略效果评估；
7. Wiki 自动结构优化建议；
8. 多模型配置管理；
9. 学习路径动态重规划；
10. 资源生成 AB 策略对比。

---

# 24. Codex 实现建议

## 24.1 接口实现顺序

建议 Codex 按以下顺序实现：

```text
1. Auth / User
2. Course
3. Material
4. Knowledge Search
5. Wiki Pages
6. Tutor Chat
7. Resources Generate
8. Quiz / Answer
9. Diagnosis
10. Student Profile / Memory
11. Recommendation
12. Evolution
13. Agent Logs
14. Admin
```

## 24.2 FastAPI 路由目录建议

```text
backend/app/api/v1/
├── auth.py
├── users.py
├── student_profile.py
├── student_memory.py
├── courses.py
├── materials.py
├── knowledge.py
├── wiki.py
├── wiki_links.py
├── learning_paths.py
├── resources.py
├── quizzes.py
├── tutor.py
├── diagnosis.py
├── recommendations.py
├── evolution.py
├── agents.py
└── admin.py
```

## 24.3 前端 TypeScript 类型生成建议

建议后端使用 FastAPI 自动生成 OpenAPI：

```http
GET /openapi.json
```

前端可以基于 OpenAPI 生成类型，也可以手写 `types/api.ts`：

```ts
export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
  request_id: string;
}
```

---

# 25. 最终说明

本 API 设计覆盖智学工坊的核心闭环：

```text
用户登录
  → 创建课程
  → 上传资料
  → 生成知识库和 Wiki
  → AI 答疑
  → 个性化资源生成
  → 练习与错题
  → 学习诊断
  → 推荐学习路径
  → 学生记忆更新
  → 自进化策略更新
  → Agent 日志展示
```

MVP 阶段应优先保证：

```text
资料上传 → Wiki 生成 → AI 答疑 → 资源生成 → 练习诊断 → 画像记忆 → 自进化策略
```

增强版再补充：

```text
复杂 Wiki 质量检查 → Agent 调用链可视化 → Prompt 版本管理 → 策略效果评估 → 多模型管理
```
