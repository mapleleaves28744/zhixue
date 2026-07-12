# Agent Runtime 收敛优化设计

> 状态：已批准，待实现计划复核
>
> 日期：2026-07-12

## 目标

在不改变现有 API、数据库结构、学生端界面或 Agent 工具契约的前提下，收敛 LangGraph Agent Runtime：按意图限制 LLM 可见工具、拆分 Supervisor 与 Service Tools 的职责、补齐运行可观测性，并消除后台 Worker 与 inline fallback 可能重复接管同一任务的竞态。

## 范围与非目标

本次包含：

- 将 `supervisor.py` 拆为门面、策略、Prompt/消息构造、完成态整理等职责明确的模块；
- 将 `service_tools.py` 拆为按领域注册的 ToolSet，保留统一 Registry 入口；
- 在每次 Supervisor 决策前按目标、意图、交付物、提示和执行进度筛选候选工具；
- 用现有 Agent 任务、步骤、事件和 LLM 日志记录候选工具数、耗时、失败和 fallback；
- 将任务执行改为原子接管，避免 ARQ Worker、重新入队和 inline fallback 重复执行；
- 缩短 Agent Runtime 的数据库事务边界，避免在等待 LLM 时持有隐式事务。

本次不包含：

- 演示数据初始化或 `seed_demo.py`；
- 修改 FastAPI 路径、Schema、SQLAlchemy Model 或 Alembic migration；
- 重做 `/assistant` 页面或其它学生端 Stitch 页面；
- 开放 Shell、代码、migration、权限或系统配置类 Agent 工具；
- 改动工作区已有的 `structured_outputs.py`、`prompt_service.py`、真实 Provider 验收脚本和相关未提交测试。

## 模块边界

```text
agent_runtime/
├── supervisor.py              # MiMoSupervisor 公共门面和 decide 协调
├── supervisor_intents.py      # 已有目标/意图解析
├── supervisor_policy.py       # 交付物、安全网、fallback 与参数兜底
├── supervisor_prompt.py       # 系统 Prompt 与 ChatMessage 构造
├── supervisor_completion.py   # 观察结果到最终回答的规范化
├── tool_selector.py           # 选择当前轮可传给 LLM 的工具 schema
├── service_tools.py           # build_learning_tool_registry 统一组装入口
└── toolsets/
    ├── knowledge_tools.py
    ├── learning_tools.py
    ├── profile_tools.py
    ├── review_tools.py
    └── media_tools.py
```

`MiMoSupervisor` 和 `build_learning_tool_registry()` 是兼容入口。现有工具名称、JSON Schema、风险等级、确认要求和 handler 语义保持不变；调用方不需要感知 ToolSet 的文件拆分。

## 执行数据流

1. `AgentRuntimeService.execute()` 通过条件更新原子把任务从允许执行的状态置为 `running`。未成功接管的执行器立即退出，不写失败状态。
2. Runtime 加载短生命周期的上下文，然后在 LLM 调用前结束隐式读事务。
3. `ToolSelector` 结合已解析意图、`tool_hints`、必需交付物、已完成/跳过工具和前置检索，选出少量候选工具。
4. `MiMoSupervisor` 用候选 schema 调用 Provider；Policy 模块检查工具调用、补齐必要交付物并限制参数；Completion 模块在完成态生成稳定的最终回答。
5. Graph 执行经 Registry 验证的工具。写库异常先 rollback；成功或失败结果写入既有步骤和事件。
6. 任务结束后保留既有对话消息、事件回放、Review 和记忆反思行为。

## 候选工具规则

- 普通课程问答只提供课程问答、课程检索以及必须的 Review/准备工具；
- 图、练习、学习路径、画像和媒体目标只提供对应领域工具及必要前置检索；
- 多交付物请求使用各子意图的工具并保留已有顺序；
- 显式 `tool_hints` 可加入合法工具，但不能绕过高风险确认或加入未知工具；
- 已完成和显式跳过的工具不会再次暴露；
- Policy 层仍是执行前最后一道校验，Registry 仍能执行全量已注册工具，确保恢复任务与直接测试兼容。

## 可观测性与事务

不新增表或字段：

- `agent_task_events.payload` 记录规划耗时、候选/总工具数量、fallback 原因和失败原因；
- `agent_task_steps.duration_ms` 记录工具端到端耗时；
- `llm_call_logs` 继续作为 Provider、模型、Token 和 LLM latency 的事实源；
- `agent_tasks` 继续保存累计 iteration/tool/replan 计数。

每个状态更新、事件持久化和工具结果持久化使用短事务。LLM 等待期间不持有同一个隐式数据库事务。工具执行出错后回滚当前会话，再以干净会话状态记录失败；Redis 事件投递失败不覆盖 PostgreSQL 事件事实源。

## 错误处理

- 原子接管失败代表任务已被其他执行器处理，不得覆盖其状态；
- 参数校验错误不可重试；执行期异常遵守各工具已有重试上限；
- 目标外、未知或不在候选集中的 LLM 工具调用由策略层拒绝并触发安全重新决策；
- 取消任务仍由事件写入时的状态检查及时中断；
- 拆分不会扩大 Agent 工具权限边界。

## 测试与验收

先写失败测试，再最小实现。新增或扩展测试应覆盖：

1. 问答、练习、画像、PPT、视频和多交付物的候选工具集合；
2. 所有现有工具的名称、schema、风险等级和确认要求保持不变；
3. Supervisor 的意图、交付物、安全网、fallback 和 completion 回归；
4. 两个执行器竞争同一任务时只有一个接管；
5. 工具异常后的 rollback 和失败事件持久化；
6. 规划/工具事件中的耗时、候选工具数和 fallback/失败信息。

验收命令至少包括 Agent Runtime 专项测试与完整 `pytest`。无前端源文件改动时不把 UI 重构纳入本阶段；最终结果如未执行前端构建，必须如实说明原因。
