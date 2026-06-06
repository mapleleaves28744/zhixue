# 16_当前实现 API 清单

> 文档状态：**自动生成的当前实现事实源**
>
> HTTP 操作数：**90**
> 生成命令：`python scripts/export_implementation_docs.py`

| 方法 | 路径 | 权限 | Path / Query 参数 | 请求体 |
|---|---|---|---|---|
| `GET` | `/` | Public | - | - |
| `GET` | `/api/v1/agents/ping` | JWT | - | - |
| `POST` | `/api/v1/agents/run` | JWT | - | application/json: `AgentRunRequest` |
| `GET` | `/api/v1/agents/runs` | JWT | task_type, status, page, page_size | - |
| `GET` | `/api/v1/agents/runs/{run_id}` | JWT | run_id* | - |
| `POST` | `/api/v1/auth/change-password` | JWT | - | application/json: `ChangePasswordRequest` |
| `GET` | `/api/v1/auth/check-username` | Public | username* | - |
| `POST` | `/api/v1/auth/login` | Public | - | application/json: `LoginRequest` |
| `GET` | `/api/v1/auth/ping` | Public | - | - |
| `POST` | `/api/v1/auth/register` | Public | - | application/json: `RegisterRequest` |
| `POST` | `/api/v1/auth/reset-password` | Public | - | - |
| `POST` | `/api/v1/courses` | JWT | - | application/json: `CourseCreate` |
| `GET` | `/api/v1/courses` | JWT | page, page_size, status | - |
| `GET` | `/api/v1/courses/ping` | JWT | - | - |
| `GET` | `/api/v1/courses/{course_id}` | JWT | course_id* | - |
| `PUT` | `/api/v1/courses/{course_id}` | JWT | course_id* | application/json: `CourseUpdate` |
| `DELETE` | `/api/v1/courses/{course_id}` | JWT | course_id* | - |
| `POST` | `/api/v1/diagnosis/analyze` | JWT | course_id*, trigger_evolution | - |
| `POST` | `/api/v1/diagnosis/generate` | JWT | course_id*, trigger_evolution | - |
| `GET` | `/api/v1/diagnosis/mastery` | JWT | course_id | - |
| `GET` | `/api/v1/diagnosis/reports` | JWT | course_id, page, page_size | - |
| `GET` | `/api/v1/diagnosis/reports/{report_id}` | JWT | report_id* | - |
| `POST` | `/api/v1/evolution/analyze` | JWT | - | application/json: `AnalyzeRequest` |
| `GET` | `/api/v1/evolution/events` | JWT | course_id, page, page_size | - |
| `GET` | `/api/v1/evolution/strategies` | JWT | course_id, strategy_type, status, page, page_size | - |
| `POST` | `/api/v1/evolution/strategies/apply` | JWT | - | application/json: `StrategyApplyRequest` |
| `GET` | `/api/v1/evolution/strategies/{strategy_id}` | JWT | strategy_id* | - |
| `POST` | `/api/v1/evolution/strategies/{strategy_id}/rollback` | JWT | strategy_id* | - |
| `POST` | `/api/v1/knowledge/extract-from-material` | JWT | - | application/json: `ExtractKnowledgeRequest` |
| `POST` | `/api/v1/knowledge/search` | JWT | - | application/json: `KnowledgeSearchRequest` |
| `GET` | `/api/v1/knowledge/seed-quality-report` | JWT | - | - |
| `GET` | `/api/v1/learning-paths` | JWT | course_id, status, page, page_size | - |
| `POST` | `/api/v1/learning-paths/generate` | JWT | - | application/json: `LearningPathGenerateRequest` |
| `PATCH` | `/api/v1/learning-paths/items/{item_id}` | JWT | item_id* | application/json: `LearningPathItemUpdate` |
| `GET` | `/api/v1/learning-paths/{path_id}` | JWT | path_id* | - |
| `DELETE` | `/api/v1/learning-paths/{path_id}` | JWT | path_id* | - |
| `GET` | `/api/v1/learning-records` | JWT | course_id, event_type, limit | - |
| `GET` | `/api/v1/materials` | JWT | course_id*, page, page_size | - |
| `GET` | `/api/v1/materials/ping` | JWT | - | - |
| `POST` | `/api/v1/materials/upload` | JWT | - | multipart/form-data: `Body_upload_material_api_v1_materials_upload_post` |
| `GET` | `/api/v1/materials/{material_id}` | JWT | material_id* | - |
| `POST` | `/api/v1/materials/{material_id}/chunk` | JWT | material_id* | - |
| `POST` | `/api/v1/materials/{material_id}/embed` | JWT | material_id* | - |
| `POST` | `/api/v1/materials/{material_id}/parse` | JWT | material_id* | - |
| `GET` | `/api/v1/materials/{material_id}/parse-status` | JWT | material_id* | - |
| `GET` | `/api/v1/ping` | Public | - | - |
| `GET` | `/api/v1/quizzes` | JWT | course_id, page, page_size | - |
| `POST` | `/api/v1/quizzes/generate` | JWT | - | application/json: `QuizGenerateRequest` |
| `GET` | `/api/v1/quizzes/mistakes` | JWT | course_id, knowledge_id, status, page, page_size | - |
| `GET` | `/api/v1/quizzes/{quiz_id}` | JWT | quiz_id* | - |
| `POST` | `/api/v1/quizzes/{quiz_id}/submit` | JWT | quiz_id* | application/json: `QuizSubmitRequest` |
| `GET` | `/api/v1/recommendations` | JWT | course_id, status, page, page_size | - |
| `POST` | `/api/v1/recommendations/refresh` | JWT | course_id* | - |
| `PATCH` | `/api/v1/recommendations/{item_id}` | JWT | item_id*, status | - |
| `POST` | `/api/v1/recommendations/{item_id}/feedback` | JWT | item_id*, helpful | - |
| `GET` | `/api/v1/resources` | JWT | course_id, resource_type, status, page, page_size | - |
| `POST` | `/api/v1/resources/generate` | JWT | - | application/json: `ResourceGenerateRequest` |
| `GET` | `/api/v1/resources/ping` | JWT | - | - |
| `GET` | `/api/v1/resources/{resource_id}` | JWT | resource_id* | - |
| `DELETE` | `/api/v1/resources/{resource_id}` | JWT | resource_id* | - |
| `POST` | `/api/v1/resources/{resource_id}/save-to-wiki` | JWT | resource_id* | application/json: `ResourceSaveToWikiRequest` |
| `GET` | `/api/v1/student/memory` | JWT | - | - |
| `POST` | `/api/v1/student/memory/reflect` | JWT | - | - |
| `DELETE` | `/api/v1/student/memory/{memory_id}` | JWT | memory_id* | - |
| `PATCH` | `/api/v1/student/memory/{memory_id}` | JWT | memory_id* | application/json: `MemoryUpdate` |
| `GET` | `/api/v1/student/profile` | JWT | - | - |
| `PUT` | `/api/v1/student/profile` | JWT | - | application/json: `ProfileUpdate` |
| `GET` | `/api/v1/student/profile/preferences` | JWT | - | - |
| `POST` | `/api/v1/student/profile/rebuild` | JWT | - | - |
| `GET` | `/api/v1/student/profile/summary` | JWT | - | - |
| `POST` | `/api/v1/tutor/ask` | JWT | - | application/json: `TutorChatRequest` |
| `POST` | `/api/v1/tutor/chat` | JWT | - | application/json: `TutorChatRequest` |
| `POST` | `/api/v1/tutor/messages/{message_id}/feedback` | JWT | message_id* | application/json: `TutorFeedbackRequest` |
| `POST` | `/api/v1/tutor/messages/{message_id}/save-to-wiki` | JWT | message_id* | application/json: `TutorSaveToWikiRequest` |
| `GET` | `/api/v1/tutor/ping` | JWT | - | - |
| `GET` | `/api/v1/users/me` | JWT | - | - |
| `GET` | `/api/v1/users/ping` | JWT | - | - |
| `GET` | `/api/v1/wiki/graph` | JWT | course_id* | - |
| `GET` | `/api/v1/wiki/pages` | JWT | course_id*, status, page, page_size | - |
| `POST` | `/api/v1/wiki/pages` | JWT | - | application/json: `WikiPageCreate` |
| `POST` | `/api/v1/wiki/pages/generate-from-material` | JWT | - | application/json: `GenerateFromMaterialRequest` |
| `POST` | `/api/v1/wiki/pages/update-from-note` | JWT | - | application/json: `UpdateFromNoteRequest` |
| `GET` | `/api/v1/wiki/pages/{page_id}` | JWT | page_id* | - |
| `PUT` | `/api/v1/wiki/pages/{page_id}` | JWT | page_id* | application/json: `WikiPageUpdate` |
| `DELETE` | `/api/v1/wiki/pages/{page_id}` | JWT | page_id* | - |
| `POST` | `/api/v1/wiki/pages/{page_id}/rollback/{version_number}` | JWT | page_id*, version_number* | - |
| `POST` | `/api/v1/wiki/pages/{page_id}/summarize` | JWT | page_id* | - |
| `GET` | `/api/v1/wiki/pages/{page_id}/versions` | JWT | page_id* | - |
| `GET` | `/api/v1/wiki/pages/{page_id}/versions/{version_number}` | JWT | page_id*, version_number* | - |
| `GET` | `/health` | Public | - | - |
