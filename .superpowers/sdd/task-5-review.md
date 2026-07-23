# Review package: fd62eb283552b63c9d76723e76c0c0f54b9fcc20..HEAD

## Commits
76b64e1 docs: record agent runtime convergence

## Files changed
 ...5\223\345\211\215\345\256\236\347\216\260\345\237\272\347\272\277.md" | 1 +
 1 file changed, 1 insertion(+)

## Diff
diff --git "a/docs/\345\275\223\345\211\215\345\256\236\347\216\260\345\237\272\347\272\277.md" "b/docs/\345\275\223\345\211\215\345\256\236\347\216\260\345\237\272\347\272\277.md"
index 3545130..1eeaa45 100644
--- "a/docs/\345\275\223\345\211\215\345\256\236\347\216\260\345\237\272\347\272\277.md"
+++ "b/docs/\345\275\223\345\211\215\345\256\236\347\216\260\345\237\272\347\272\277.md"
@@ -58,20 +58,21 @@
 - Phase 2/3 固定任务执行器保留为 `legacy_workflow` 回滚链路；Phase 3.1 已新增 LangGraph 1.x 动态学习智能体，使用 MiMo Supervisor 根据目标和观察动态选择工具、继续执行或重新规划。正式验收见 `docs/19_测试方案/16_Phase3.1LangGraph真正智能体阶段验收记录.md`。
 - **Supervisor 决策模型（2026-06-08）**：LLM 主导 native function calling；规则层 `_apply_safety_net` 仅在必交付物缺失（语音/视频/练习等）、显式「基于资料/引用」约束、用户 `tool_hints` 或 Mock 空转 fallback 时介入；待交付物列表在工具约束过滤之后计算，避免安全网与 deliverable 对齐顺序不一致。Mock Provider 在有 tools 时会模拟 native `tool_calls`。
 - Phase 3.1 真实 MiMo 20 条场景评测已通过：场景通过率 100%、任务完成率 95%、工具选择准确率 100%、重规划成功率 100%、高风险拦截率 100%。
 - Phase 3.1 已补稳定演示脚本：`scripts/start_phase31_demo.ps1` 启动 backend / arq Worker / frontend，`scripts/agent_demo_check.py` 通过真实 HTTP API 验证统一 Agent 入口、工具事件、对话消息和画像证据。
 - `/assistant` 会按课程恢复已有 Agent 会话，回放用户消息、规划/工具/观察/Review/多模态进度等可展开流式步骤、完整事件日志和 Assistant 最终回答；切换或新建会话时会停止当前页面 SSE 监听，后台 Agent 任务可继续运行，用户可手动恢复查看或取消任务。
 - `/assistant` 的简单寒暄使用轻量直答路径：快速模式不构建 RAG/画像上下文，智能体模式不进入 Review、长期记忆反思和对话知识抽取；普通快速问答关闭模型 thinking 并在流式结束后使用规则校验，避免第二次同步 Review LLM 阻塞完成状态。
 - `/assistant` 的资料问答已统一到 `GroundedQAPipeline`：文档与 Wiki 证据保留真实来源 ID，以 `[S1]` 形式生成和校验引用；主回答只调用一次 LLM，反馈所需学习记录同步落库，画像/记忆等非关键处理异步执行。Agent 的纯资料问答直接复用同一结果，避免再次检索和再次生成；需要多模态产物时先检索课程依据再生成产物。
 - Tutor SSE 前端只在首个回答增量前允许一次非流式降级，支持 AbortSignal、无 `done` 结束检测和请求所有权隔离，避免重复回答、幽灵停止状态与旧请求覆盖新会话。课程切换会停止活动流并清理课程相关状态。
 - 登录后的学生端页面已挂载全站“知知”桌宠：支持拖拽吸附、跨 Stitch iframe 常驻、任务完成气泡、提醒收件箱、刷题/路径催学及提醒偏好设置；公开首页与认证页面不显示。
 - Agent 运行时将长期记忆反思视为非关键后置步骤：反思失败会记录降级事件但不阻断最终回答；arq Worker 启动时会把长时间无进展的 `running` LangGraph 任务标记为失败，避免历史任务永久卡住。
+- **Agent Runtime 收敛（2026-07-12）**：Supervisor 对可识别意图仅提供对应的候选工具（无候选时保留全量回退）；事件与动态步骤继续记录既有的执行时序和耗时；Worker 以条件更新原子认领 `queued` 任务。此次收敛未新增数据库表或 API。
 - Phase 4 对话式画像 v1 已接入：Supervisor 可将“专业、年级、学习目标、学习偏好、薄弱点、错误模式”等自然语言信息路由到 `update_profile_from_dialogue` 工具，由 `ProfileService` 写入 `student_profiles.strategy_summary.dialogue_profile` 和 `learning_preferences.prompt_params`，并在 `/path-profile` 展示证据。
 - 个性化学习闭环已完成第一版工程化修复：长期记忆使用稳定 `memory_key` 合并强化、反思水位仅处理新行为；`MemoryAgent` 按 `params.course_id` 解析课程作用域（不再误用 `context.course_id`）；课程作用域最多保留 20 条活跃记忆、全局最多 10 条，超限与历史重复记录只归档不删除；Tutor、Resource 与个性化上下文只加载当前课程最相关的 5 条活跃记忆。
 - 学生画像已拆分为全局 `student_profiles` 与课程级 `student_course_profiles`。非寒暄问答完成后通过 EventBus 后置提取画像信号，使用消息 ID 幂等；掌握度写入课程画像，不再覆盖其他课程快照。
 - 自进化策略应用已从“仅修改 active 状态”升级为物化执行：`qa_style` / `resource_strategy` 写入学习偏好与 Prompt 参数，`difficulty` / `recommendation` / `learning_path` 写入课程策略上下文；推荐与路径绑定策略版本，回滚恢复上一版实际参数，低风险策略审核后自动生效。
 - 首页学习分析已接入真实 `learning_sessions` 与汇总 API；`/assistant`、`/knowledge`、`/practice` 仅在页面可见且最近有交互时发送心跳，服务端单次最多累计 60 秒。首页本周/本月时长、掌握度和每日柱状图不再使用 `18.5 小时 / 82%` 静态值。
 - RAG 检索已从单纯向量检索增强为向量检索 + 关键词检索 + metadata 过滤 + 轻量 rerank/source diversity 的 HybridRetriever。
 - 资料知识点抽取已升级为“规则候选召回 → LLM 结构化归一化 → 确定性校验 / 规则降级”：单份资料最多保留 30 个有来源的细粒度知识点，整理元数据记录 aliases、source chunk/material、置信度与降级原因；Wiki 生成仅处理当前资料绑定的知识点，避免跨资料页面混入，`/knowledge` 展示候选、合并、拒绝、保留和整理方式统计。
 - Redis 已用于 arq 持久后台任务队列和实时 Agent 事件通知；当前本机 Redis 3.0 不支持 Stream，运行时自动兼容为 PostgreSQL 追加事件 + Redis Pub/Sub。
 - Agent 画像上下文使用 Redis 30 分钟智能缓存；画像编辑、对话画像更新、画像重建和掌握度快照同步后立即失效，Redis 不可用时回退数据库。
 - 上传文件使用本地存储 `backend/storage`；当前无 MinIO Adapter。
