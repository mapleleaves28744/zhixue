# Grounded QA 双通道智能问答重构设计

> 文档状态：已确认设计，待实施计划
>
> 日期：2026-07-10
>
> 范围：LLM/RAG、多智能体课程问答、`/assistant` 问答体验

## 1. 背景与事实依据

本设计以当前分支代码、自动生成实现清单和真实验收记录为事实源。当前智能问答已经具备 Tutor SSE、Hybrid/Graph Retriever、LangGraph Agent Runtime、引用结构、反馈和保存到 Wiki 接口，但用户体验仍存在响应慢、回答与引用不可靠的问题。

已确认的根因如下：

1. `frontend/components/assistant/AssistantPageClient.tsx` 收到 Tutor 的引用、相关知识点、建议追问和 `message_id` 后，只保留回答正文与引用数组，实际回复组件没有展示引用、反馈或保存入口。
2. 页面外层在窄屏使用固定视口高度和纵向 flex，`ResourceSidePanel` 同时声明 `h-full`，导致约 960px 和移动端下资源面板占满可用高度，问答区被压缩到不可见。
3. `TutorAgent._load_wiki_pages()` 在没有匹配 Wiki 时退回任意前三页，可能把无关 Wiki 注入 Prompt。
4. `TutorAgent._related_knowledge_points()` 使用 `wiki_page.id` 充当 `knowledge_id`，相关知识点标识不真实。
5. `GraphRetriever._candidates_from_knowledge()` 为图谱扩展节点生成随机 chunk/material UUID；这些值随后可能进入引用结构，不满足来源可追溯要求。
6. Agent 的 `answer_course_question` 工具调用 `TutorService.chat()`；外层 Supervisor 可能已调用知识检索，而 Tutor 内部再次检索，并继续执行 Tutor LLM、Review、知识抽取、外层 Review 和记忆反思，形成重复检索与多次模型调用。
7. `frontend/services/tutorService.ts` 对 SSE 异常无差别回退完整同步请求；部分输出后发生错误时可能重复调用模型和副作用。
8. 现有知识库评测把“命中任意宽泛 source_id”同时当作检索命中和回答正确，无法真实衡量答案准确性与引用精确率。
9. 既有 Agent 冒烟记录中两轮任务总耗时为 76 秒，说明当前多轮编排不适合作为普通问答默认路径。

## 2. 目标

### 2.1 用户目标

1. 普通课程问答在 0.5 秒内显示可理解的处理状态。
2. 在比赛环境的真实 Provider 下，普通问答目标首 token 不超过 3 秒，总完成时间不超过 15 秒。
3. 普通问答固定为一次课程检索和一次聊天模型调用。
4. 回答只展示真实、可追溯且达到可信阈值的资料引用。
5. 没有可靠依据时明确说明依据不足，不使用低相关结果装饰回答。
6. 快速问答刷新后可恢复，支持反馈、保存到 Wiki 和建议追问。
7. 390px、约 960px 和 1440px 宽度下，问答区均可见且可操作。

### 2.2 工程目标

1. Tutor API 与 Agent `answer_course_question` 工具复用同一 Grounded QA 内核。
2. 普通问答不进入 Supervisor、同步 Review Agent 或同步 Memory Agent。
3. 复杂资源、练习、路径和多模态任务继续由 LangGraph Agent Runtime 编排。
4. 画像、记忆、知识抽取和深度 Review 在回答完成后异步执行。
5. 记录检索耗时、首 token、生成耗时、总耗时、LLM 调用次数和 fallback 状态。

## 3. 非目标

1. 不替换 FastAPI、Next.js、LangGraph、PostgreSQL、pgvector 或现有 LLM Provider。
2. 不实现完整 Microsoft GraphRAG、cross-encoder 或 LLM rerank。
3. 不新增开放式 Agent 工具，不扩大 Agent 的权限边界。
4. 不新增数据库表或修改权限模型。
5. 不重做其他学生端页面。

## 4. 总体架构

```text
学生问题
  → 任务类型选择
    → 普通问答：GroundedQaPipeline
    → 复杂任务：Supervisor / Agent Runtime → 专业工具 → GroundedQaPipeline（需要答疑时）

GroundedQaPipeline
  → 一次混合检索
  → 证据可信度过滤
  → 一次 LLM 流式生成
  → 确定性引用校验
  → 保存问答与会话
  → 返回完成事件
  → EventBus 异步 Review / 画像 / 记忆 / 知识抽取
```

### 4.1 核心组件

#### GroundedQaPipeline

唯一课程问答内核，负责：

1. 课程权限校验后的问答上下文准备；
2. 课程资料、明确匹配 Wiki 和图谱关系上下文检索；
3. 证据筛选、编号和 Prompt 组装；
4. 单次 LLM 普通或流式生成；
5. 引用解析与校验；
6. 问答记录与会话消息持久化；
7. 性能指标与 Provider 元数据整理。

#### EvidenceRetrievalService

在现有 `HybridRetriever` 与 `GraphRetriever` 基础上形成统一证据结果。文档和 Wiki 证据必须拥有真实数据库 ID；图谱扩展节点只作为知识关系上下文，除非其关系具有可追溯的文档或 Wiki 来源，否则不能作为文档引用展示。

#### CitationValidator

不调用 LLM。负责从最终回答提取 `[S1]`、`[S2]` 等引用标记，只保留当前证据包中存在的编号，并将编号映射为真实来源结构。未知编号、失效 ID 和未在回答中使用的来源不会进入最终引用列表。

#### TutorPostprocessService

订阅 `chat_completed` 事件，使用独立数据库会话执行：

1. 深度 Review；
2. 画像信号提取；
3. 长期记忆反思；
4. 对话知识抽取和图谱沉淀；
5. 学习掌握度轻量更新。

这些任务失败时只记录日志和后处理状态，不修改已经返回的回答。当前进程内 EventBus 的 `publish()` 只负责入队，因此快速问答在记录提交后发布事件，不同步执行处理器。

## 5. 领域契约

### 5.1 问答请求

`TutorChatRequest` 增加可选 `conversation_id`，保留现有 `session_id` 以兼容旧调用方。核心字段为：

```text
course_id
question
conversation_id（可选）
knowledge_id（可选）
wiki_page_id（可选）
top_k
use_rag
use_wiki
use_profile
stream
```

### 5.2 证据项

内部 `EvidenceItem` 包含：

```text
citation_key          例如 S1
source_type           document | wiki
source_id             真实 material_id 或 wiki_page_id
chunk_id              文档来源时必须为真实 chunk ID
page_id               Wiki 来源时必须为真实 page ID
knowledge_id          可为空，但存在时必须为真实知识点 ID
title
page_no
quote
retrieval_mode
vector_score
keyword_score
rerank_score
confidence            strong | acceptable
```

图谱关系使用独立 `GraphContext` 返回真实知识点 ID、关系类型和证据文本，不制造 material/chunk UUID。

### 5.3 问答结果

`TutorChatResponse` 在现有字段基础上增加：

```text
conversation_id
grounding_status       grounded | partial | insufficient
grounding_message
performance            retrieval_ms | first_token_ms | generation_ms | total_ms | llm_call_count
postprocess_status      queued | skipped
```

`message_id` 继续表示 `learning_records.id`，用于反馈与保存到 Wiki。快速问答写入 `agent_messages` 时，在消息 payload 中保存 `learning_record_id`，避免把 AgentMessage ID 误用于 Tutor 接口。

### 5.4 SSE 事件

事件顺序固定为：

```text
progress  stage=retrieve_context
evidence  grounding_status + 可信证据摘要
progress  stage=llm_generation
delta     content
progress  stage=validate_citations
done      TutorChatResponse
```

简单寒暄可以跳过 `evidence`，但仍返回结构完整的 `done`。

## 6. 检索与可信度策略

### 6.1 候选生成

1. 向量检索和关键词检索各召回不少于 `max(top_k * 8, 30)` 个候选。
2. 关键词切分继续覆盖数据结构领域词，并从课程知识点名称、标题路径和问题中的连续中文片段生成动态词项，不再只依赖硬编码领域词表。
3. 明确传入的 `wiki_page_id` 在权限校验通过后作为强证据；未明确选择 Wiki 时，只返回标题、摘要、正文或绑定知识点与问题匹配的页面。
4. `knowledge_id` 必须从 API 一直传递到 Retriever 过滤条件，不能在 Service 层丢失。

### 6.2 初始可信规则

文档候选满足下列任一条件才可进入证据包：

1. `keyword_score >= 1.0`；
2. `vector_score >= 0.55`；
3. 标题路径命中问题核心词，且 `vector_score >= 0.45`。

显式选择且可读的 Wiki 页面直接接受；自动匹配 Wiki 必须至少命中一个长度不小于 2 的问题核心词或真实绑定知识点。阈值通过配置暴露，初始默认值按上述规则固定，并用 30 个标准问题、无答案问题和干扰资料集校准。

### 6.3 排序与去重

1. 保留现有向量、关键词、metadata 和来源质量轻量 rerank。
2. 同一 chunk 只出现一次。
3. 同一资料默认最多 2 条证据。
4. 最终 Prompt 最多使用 5 条证据。
5. 图谱关系不参与文档引用数量，只单独影响相关知识点和补充上下文。

### 6.4 依据不足

没有可信文档或 Wiki 证据时：

1. `grounding_status=insufficient`；
2. Prompt 要求把课程资料无法验证的内容放入“通用知识补充”段落；
3. 回答显示“课程资料未找到可靠依据”；
4. `citations=[]`，不得生成 inference 类型的伪引用卡片。

有可信证据但回答未包含任何有效 `[S#]` 标记时，返回 `grounding_status=partial` 并显示“回答未完整绑定来源”。

## 7. Prompt 与生成规则

证据以编号块写入 Prompt：

```text
[S1] 标题：...
页码：...
原文：...

[S2] 标题：...
页码：...
原文：...
```

回答规则：

1. 先直接回答问题，再给必要解释；
2. 由课程资料支持的关键结论必须附 `[S#]`；
3. 只能引用提供的编号；
4. 不重复输出完整引用列表；
5. 依据不足时明确区分课程依据与通用知识；
6. 默认使用较低温度，保证术语和事实稳定；
7. 学生画像和长期记忆使用不同上下文，不再把同一画像文本重复填入两个 Prompt 槽位。

## 8. 普通问答执行流

1. Router 完成鉴权、参数接收并返回 `StreamingResponse`。
2. Pipeline 校验课程和可选 Wiki 权限。
3. 立即发送检索进度事件。
4. 执行一次 EvidenceRetrievalService 检索。
5. 发送可信证据摘要事件。
6. 执行一次 LLM 流式生成并记录首 token 时间。
7. CitationValidator 校验最终回答和引用。
8. 保存 `learning_records`、AgentConversation 用户消息与助手消息。
9. 提交事务后发送 `done`。
10. 发布 `chat_completed`，异步执行后处理。

普通问答不调用 Supervisor、同步 Review Agent 或同步 Memory Agent。

## 9. Agent 集成

### 9.1 路由边界

普通知识解释、概念比较和课程事实问答使用快速路径。资源、练习、学习路径、画像更新、语音、视频、沉浸课堂以及明确选择智能体模式的请求进入 Agent Runtime。

### 9.2 answer_course_question

Agent 工具直接调用 GroundedQaPipeline 的非 SSE 接口。Supervisor 策略中，`answer_course_question` 已保证内部检索，因此不能再自动前置 `search_course_knowledge`。

### 9.3 确定性完成

`ToolExecutionResult` 增加可选 `final_answer`。当 `answer_course_question` 成功、没有未完成交付物且没有待执行工具时，Graph 直接使用该答案进入 finalize，不再调用 Supervisor 对 Tutor 答案二次总结。复杂任务仍按交付物规则继续规划。

### 9.4 Review 与记忆

普通问答和纯 Agent 答疑仅同步执行 CitationValidator。深度 Review 与记忆反思进入后处理。高风险写操作、多模态安全检查和需要用户确认的工具继续保留同步 Review/interrupt 门禁。

## 10. 失败与降级

1. 向量检索不可用时降级关键词检索。
2. 两种检索均无可信结果时返回依据不足，不伪造来源。
3. LLM 在首 token 前失败时最多执行一次已配置 Provider fallback。
4. 已输出至少一个 token 后失败时保留部分回答，发送中断错误，不自动发起第二次完整请求。
5. 问答记录保存失败时保留已生成答案，但 `message_id=null`、`postprocess_status=skipped`，前端禁用反馈和保存到 Wiki，并说明记录未保存。
6. EventBus 发布或后处理失败不改变已返回答案；错误写入日志。
7. Mock fallback 必须通过 `fallback_used`、`failed_provider` 和 `fallback_reason` 明确展示。
8. 所有检索继续在已授权 `course_id` 范围内执行。

## 11. 前端设计

### 11.1 响应式布局

1. `>= 1280px`：问答区为主列，资源栏固定约 320–360px。
2. `768–1279px`：问答区占满主体，资源栏改为可打开抽屉。
3. `< 768px`：资源栏使用底部抽屉；问答区和输入框始终可见。
4. 移除纵向布局下资源面板的 `h-full` 竞争，避免问答区被压缩。

### 11.2 Tutor 状态管理

`AssistantPageClient` 使用唯一的 `useTutorStream` 管理：

```text
idle → retrieving → generating → validating → completed
                               ↘ interrupted / failed
```

页面不再直接维护另一套重复的 Tutor SSE 控制器和 fallback 逻辑。停止生成保留已接收正文；重试显式创建新请求。

### 11.3 回答展示

完成回答展示：

1. Markdown 正文；
2. “基于 N 条课程资料”“部分绑定来源”或“课程依据不足”状态；
3. 可展开的资料标题、页码、原文片段和检索方式；
4. 真实相关知识点；
5. 建议追问 chip；
6. 有用/无用反馈；
7. 保存到 Wiki；
8. Provider fallback、回答中断或记录保存失败提示。

### 11.4 会话恢复

快速问答开始前确保存在 AgentConversation。用户消息和完成后的 Tutor 消息写入现有 `agent_messages`，消息 payload 保存引用、相关知识点、建议追问、grounding 状态和 `learning_record_id`。历史恢复后反馈与保存按钮使用 `learning_record_id`。

### 11.5 服务不可用

课程加载失败、401 或后端不可达时，页面显示明确错误卡和重试按钮。课程选择为空时禁用发送，并解释是“未登录”“没有课程”还是“后端不可达”，不只显示 toast。

## 12. 性能与可观测性

每次问答记录：

```text
retrieval_ms
first_token_ms
generation_ms
total_ms
llm_call_count
evidence_candidate_count
evidence_accepted_count
grounding_status
provider
model
fallback_used
```

这些数据写入现有 Agent/LLM 日志的 payload，不新增表字段。普通问答验收要求 `llm_call_count=1`；Provider fallback 场景允许为 2，并必须明确标记。

## 13. 测试设计

### 13.1 后端单元测试

1. 低相关文档不会进入证据包。
2. 显式 Wiki 页面可作为强证据，任意前三页 fallback 被删除。
3. 图谱扩展不产生随机 material/chunk ID。
4. CitationValidator 只映射有效 `[S#]`。
5. 相关知识点返回真实 `page.knowledge_id`。
6. `knowledge_id` 从 Service 传递到 Retriever。
7. 普通问答只调用一次聊天模型。
8. EventBus 后处理不阻塞 `done`。
9. 保存失败仍保留答案并禁用后处理。

### 13.2 Agent 测试

1. `answer_course_question` 前不重复调用搜索工具。
2. Tutor 工具结果可以确定性成为最终回答。
3. 有其他未完成交付物时不能提前 finalize。
4. 普通问答不触发同步双重 Review。

### 13.3 SSE 与前端测试

1. 首 token 前失败只回退一次。
2. 部分输出后失败不重复请求。
3. evidence、delta、done 事件按顺序更新页面。
4. 引用、反馈、保存、建议追问和历史恢复可用。
5. 后端不可达、401、无课程和记录保存失败显示不同状态。

### 13.4 浏览器验收

在 390×844、约 960×768、1440×900 三档视口验证：

1. 问答主区域和输入框可见；
2. 资源抽屉可打开和关闭；
3. 普通问题能流式返回；
4. 引用可展开；
5. 反馈和保存可操作；
6. 控制台没有相关应用错误。

### 13.5 RAG 评测

标准集增加具体预期资料或 chunk、无答案问题和干扰资料。分别统计：

1. Recall@5；
2. MRR；
3. 引用精确率；
4. 无依据拒答率；
5. 回答正确性。

回答正确性不再由“检索到任意来源”推导。自动指标与人工抽查结果分开报告。

## 14. 验收标准

1. 普通问答首个进度事件不超过 0.5 秒。
2. 真实 Provider 目标首 token 不超过 3 秒，总完成时间不超过 15 秒，并记录实际网络环境和结果。
3. 普通问答无 fallback 时只有一条聊天模型调用日志。
4. 所有展示引用都能映射真实 material/chunk 或 Wiki page。
5. 无可靠证据时不展示低相关引用。
6. 快速问答刷新后可恢复，反馈和保存使用正确 `learning_record_id`。
7. Agent 纯答疑不重复检索、不二次总结 Tutor 答案。
8. 三档视口下问答区均可见。
9. Mock Provider 下核心测试不依赖网络。
10. 相关后端测试、前端 typecheck/build、浏览器验收和文档检查通过。

## 15. 数据库、API 与文档影响

### 数据库

无表结构变化，无 Alembic migration。复用现有 `learning_records`、`agent_conversations`、`agent_messages`、`agent_runs` 和 `llm_call_logs`。

### API

1. `TutorChatRequest` 增加 `conversation_id`。
2. `TutorChatResponse` 增加 grounding、performance、conversation 和后处理状态字段。
3. Tutor SSE 增加 `evidence` 事件。
4. 现有 `/api/v1/tutor/chat`、反馈和保存路径保持不变。

### 文档

修改 Router/Schema 后执行：

```powershell
python scripts/export_implementation_docs.py
python scripts/check_docs.py
```

同时更新当前实现基线、API 清单、功能完成度和阶段验收记录，不把本设计文档当成已实现事实。

## 16. 实施范围边界

本轮只修改课程问答、相关 RAG/Agent 集成、助手页 Tutor 展示和对应测试文档。资源、练习、路径、多模态工具的业务逻辑保持不变；只允许为消除重复检索和正确完成 Agent 问答而调整公共 ToolResult/Graph 路由。
