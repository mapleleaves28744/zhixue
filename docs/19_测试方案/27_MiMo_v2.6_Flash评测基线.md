# MiMo v2.6 Flash 评测基线（2026-09-27）

## 环境与范围

- 本地 PostgreSQL、Redis；真实 `xiaomi_mimo / mimo-v2.6-flash`。本次 33 条 Tutor 回答的 `fallback_used` 全为 `false`。
- 检索 Embedding：`sentence_transformers / BAAI/bge-large-zh-v1.5`，1024 维，禁用 Mock fallback。
- 公有《数据结构》课程：32 份资料、1608 个切片（全部有向量）、131 个知识点。
- 题集：30 道可回答题、3 道不可回答题。学习视频不纳入后续评测与优化范围。
- 本次在独立评测学生账号上运行 Agent 场景，避免改动普通学生的画像和记忆。
- 本轮 Tutor 脚本沿用公有课程所有者运行；脚本现支持 `--user-id`，下次复验应指定独立评测账号，以隔离问答记录。

## 公有知识库与 Tutor 基线

执行命令：

```powershell
python scripts/evaluate_public_kb.py --run-llm-sample 33 --require-real-provider --expected-model mimo-v2.6-flash --output-prefix data/seed_knowledge/data_structure/eval/baselines/2026-09-27-mimo-v2.6-flash-public-kb
```

报告：[JSON](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-mimo-v2.6-flash-public-kb.json)、[Markdown](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-mimo-v2.6-flash-public-kb.md)。

| 指标 | 基线 |
|---|---:|
| Recall@5（30 道可回答题） | 0.9667 |
| MRR@5 | 0.9400 |
| 引用精确率 | 0.6957 |
| 引用覆盖率 | 0.5000 |
| 不可回答题人工复核拒答率 | 0.6667（2/3） |
| 不可回答题依据不足率 | 1.0000（3/3） |
| 回答正确率 | 未独立评分（`null`） |

引用精确率的分子为“引用了预期来源的检索切片，且引用片段包含至少一个预期证据词组”的引用数，分母为全部引用数；未知切片 ID 保留在分母中。引用覆盖率要求一题的有效引用**合起来**覆盖全部必需证据词组。此口径与 2026-07-11 Mock 报告的“单条引用覆盖全部词组”不同，不能直接比较数值。

不可回答题逐条复核：第 31 题虽提示课程无依据，却继续给出贝尔不等式的实质性证明，记为**未拒答**；第 32、33 题没有给出请求的具体日期或股价，记为拒答。`grounding_status=insufficient` 仅表示课程依据不足，不能代替拒答判定。

本轮未人工核对 30 道可回答题的事实正确性，因此 `answer_correctness=null`。引用指标只核验来源切片 ID 与证据词，不证明整段回答事实正确。

## 评测口径修正

- Agent 工具评分区分计划、尝试和成功执行。多步骤场景要求每个必需工具组都有实际成功执行；等待确认的高风险场景检查计划工具，同时要求未尝试执行。
- 超时场景纳入工具选择分母。脚本在超时后尝试取消评测任务。
- 重复写入和跨用户泄露未设置可验证探针，报告值为 `null`，不能当作 0 次问题。
- 真实 Tutor 评测检查 Provider、模型和 Mock 回退；若不匹配，停止生成真实模型基线。

## Agent Runtime 基线

使用独立评测学生账号和公有《数据结构》课程执行 20 个场景，单场景上限 600 秒、并发 2。命令如下（`--user-id` 为本地评测账号 ID）：

```powershell
python scripts/evaluate_agent_runtime.py --user-id ce48214f-107c-4904-afb5-40b7ab8cff2f --course-id 0b41dca8-3e7d-420b-9769-b4fe623e482f --concurrency 2 --timeout-seconds 600 --expected-model mimo-v2.6-flash --output data/seed_knowledge/data_structure/eval/baselines/2026-09-27-mimo-v2.6-flash-agent-runtime.json
```

报告：[JSON](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-mimo-v2.6-flash-agent-runtime.json)。原进程对超时场景未保留步骤；报告完成后已从评测任务的持久化步骤补回尝试和成功执行的工具，并重算汇总（`scoring_version=2026-09-27-v2`）。5 个超时任务已在评测账号下取消。

| 指标 | 基线 |
|---|---:|
| 场景通过 | 13/20（0.6500） |
| 任务成功结束 | 14/20（0.7000） |
| 工具选择准确率 | 0.7368（14/19） |
| 高风险拦截 | 1/1 |
| 重新规划成功率 | 未测到重新规划样本（`null`） |
| 重复写入、跨用户泄露 | 无探针，均为 `null` |

未通过的 7 个场景：

| 场景 | 实测原因 |
|---|---|
| `agent-003` | 问答任务结束，但没有引用，不满足有依据回答。 |
| `agent-007`、`agent-008` | 检索成功，`generate_explanation` 失败，超过 600 秒。 |
| `agent-015` | 检索与出题成功，`generate_explanation` 失败，超过 600 秒。 |
| `agent-016` | 检索成功，学习路径步骤未成功，后续讲解未完成，超过 600 秒。 |
| `agent-017` | 检索和推荐成功，漏执行必需的解释步骤，任务却标记为成功。 |
| `agent-018` | 审查工具已成功，随后又发起检索并超时；检索顺序与审查的取证依赖不符。 |

本轮评测连接本机 PostgreSQL/Redis；Docker 数据库或 volume 的状态不是这些失败的证据。旧的 2026-06-07 Agent 报告将计划工具算入执行，并将未测量的安全指标记为 0；与本轮新口径不可直接比较。

评测 Worker 在资源场景运行期间还输出过 SQLAlchemy `MissingGreenlet` 异常；当前任务记录未保留足够的原始异常链，不能单凭该日志断定所有超时的根因。下一轮应优先检查 `agent_runtime_service.py` 在异常回滚后读取 ORM 对象和记录失败状态的路径，并把原始工具异常持久化。

## 多步骤 Agent 下一轮优化

1. **先收紧失败耗时**：写入型工具按错误类型决定是否重试；总任务设绝对截止时间。当前通用工具默认每次 120 秒、最多重试 2 次，资源生成失败可占用数百秒。
2. **显式计划依赖**：把检索、讲解、出题、推荐等表示为带前置条件的步骤；先取证再审查。完成状态按所有必需交付物判定，防止 `agent-017` 式漏步骤。
3. **按交付物持久化进度**：步骤保留输入、输出、证据、产物 ID、失败类型和可恢复点；失败时返回已完成内容与下一步，不让用户只看到整题超时。
4. **写操作幂等**：当前缓存键包含 `tool_call_id`，重规划生成新调用 ID 时无法天然去重；写入服务需要按“任务 + 交付物”级别的幂等约束，并加入重复写入探针。
5. **精简意图与工具集合**：保留现有意图规则和交付物约束，将明确的多步骤请求映射为少量固定流程；学习视频不进入默认工具候选、评测集或近期开发范围。

## 基线后的定向修复与复验

基线数字保持不变。随后针对失败场景做了以下小范围修复：

- 课程问答增加“二叉搜索树”到“二叉排序树”的检索别名；原问题不改写，引用仍只能来自实际检索到的课程内容。
- 混合任务把课程解释、推荐和产物审查列为必需步骤；已有解释答案不能让未完成的推荐提前结束，纯审查不会因“来源”一词追加检索，也不再重复执行 Review Agent。
- 写入型工具不隐式重试；讲解资源、学习路径和练习生成的单次上限从 120 秒调整为 240 秒；超时会记录明确错误。Agent 事件与收尾通过任务 ID 重新查询，避免回滚后读取已过期 ORM 对象触发 `MissingGreenlet`。
- 学习路径读取画像薄弱点时兼容字符串与对象两种已有数据形态；原 `agent-016` 定向复验在 `PlannerAgent` 立即报 `str` 无 `get` 属性，已据此补回归用例。
- Review Agent 的结构化输出不再重复向模型发起多次修复请求；兜底审查如果仍无法解析，会标记未通过并提示人工复核。
- Quiz Agent 的结构化输出也收紧为单次尝试，失败后走现有普通回答解析，避免重复模型请求耗尽工具时限。

真实 `mimo-v2.6-flash` 定向复验（同一独立评测账号）：

| 场景 | 结果 | 证据 |
|---|---|---|
| `agent-003` | 通过 | 课程问答成功，保留 3 条引用；[报告](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-optimized-smoke-agent-003.json)。 |
| `agent-018` | 通过 | 仅执行 `review_artifacts`，任务成功结束；[报告](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-optimized-smoke-agent-018.json)。 |
| `agent-017` | 通过 | 依次完成课程检索、课程问答、推荐，保留 13 条引用；[报告](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-optimized-smoke-agent-017.json)。 |
| `agent-007` | 通过 | 检索与讲解资源均成功；讲解工具实际耗时约 184 秒、单次执行；[报告](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-optimized-smoke-agent-007-final.json)。 |
| `agent-016` | 通过 | 检索、学习路径和配套讲解都成功；[报告](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-optimized-smoke-agent-016-final.json)。 |
| `agent-015` | 通过 | 检索、出题和讲解均有成功步骤；[报告](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-optimized-smoke-agent-015-final.json)。 |
| `agent-008` | 通过 | 单独运行时完成检索与哈希冲突讲解；[报告](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-optimized-smoke-agent-008-final.json)。 |

`agent-007` 的中间复验先确认了 120 秒超时与 `MissingGreenlet` 二次异常；[修复事件记录后的失败报告](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-optimized-smoke-agent-007-recheck.json)中，工具失败已能持久化为明确超时且无重复尝试。`agent-008` 与 `agent-015` 的首次并发复验分别触发讲解和出题工具时限，后续改为串行复验。原基线的 7 个失败场景均已有单独真实模型复验通过记录；这不能代替完整 20 场景重新测评，也不能据此把原 13/20 分数改写。重复写入、跨用户隔离探针仍待测。

按当前产品取舍，讲解视频、动画与 OpenMAIC 沉浸课堂不再作为新学习资源生成能力。Agent 不再提供对应工具；直接生成服务默认返回 410。已有视频与课堂产物仍可查看，HTML 互动课件和文字讲解继续可用。代码通过 `LEARNING_VIDEO_ENABLED=false` 默认关闭新建入口，保留历史服务实现与数据读取。

## 优化后的完整 20 场景重跑与探针

2026-09-27 使用同一独立评测账号、公有《数据结构》课程和真实 `mimo-v2.6-flash`，按原 600 秒单场景上限串行重跑全部 20 场景。串行运行用于减少生成任务相互竞争；与原基线并发 2 的耗时不可直接比较。原 13/20 基线报告保持不变。

```powershell
python scripts/evaluate_agent_runtime.py --user-id ce48214f-107c-4904-afb5-40b7ab8cff2f --course-id 0b41dca8-3e7d-420b-9769-b4fe623e482f --concurrency 1 --timeout-seconds 600 --expected-model mimo-v2.6-flash --output data/seed_knowledge/data_structure/eval/baselines/2026-09-27-mimo-v2.6-flash-agent-runtime-rerun-20.json
python scripts/probe_agent_runtime.py --report data/seed_knowledge/data_structure/eval/baselines/2026-09-27-mimo-v2.6-flash-agent-runtime-rerun-20.json --user-id ce48214f-107c-4904-afb5-40b7ab8cff2f
```

完整结果见[重跑与探针报告](../../data/seed_knowledge/data_structure/eval/baselines/2026-09-27-mimo-v2.6-flash-agent-runtime-rerun-20.json)。

| 指标 | 本次结果 |
|---|---:|
| 场景通过 | 20/20（1.0000） |
| 任务成功结束 | 19/20（0.9500）；另 1 个按预期等待用户确认 |
| 工具选择准确率 | 19/19（1.0000） |
| 高风险拦截 | 1/1（1.0000） |
| 重新规划成功率 | 无重新规划样本（`null`） |
| 重复写入 | 已测 0 次 |
| 跨用户泄露 | 已测 0 次 |

重复写入探针针对本轮 20 个任务逐一重复投递相同任务 ID，均返回 `already_claimed`；资源、练习、学习路径、长期记忆、Wiki、Agent 步骤、事件及消息的新增行数均为 0。另对 29 个已成功的工具步骤，用相同 `task_id:tool_call_id` 从数据库复用持久化结果，缓存未命中和意外执行处理器均为 0。探针使用禁止真实写入的处理器，因此不会在缓存失效时制造额外产物。此结果**只覆盖相同任务 ID 与相同工具调用 ID 的重放**；重规划产生新调用 ID 时，同一交付物的语义去重仍需独立约束和测试。

跨用户探针创建未提交的临时学生身份，对本轮 20 个任务分别请求他人的会话消息、任务详情和事件历史，并检查会话列表及已有资源的详情和列表，共 63 个检查点，均被拒绝或过滤；临时身份随后回滚。探针覆盖 Agent 与资源 Service 层的用户过滤，尚未覆盖所有业务模块、HTTP 鉴权链和并发竞态。

本轮 20 个场景均未使用讲解视频或 OpenMAIC。执行期间曾记录 MiMo 音频接口返回缺少 `audio.data` 并回退到 Mock 音频；该日志没有导致本轮场景失败，但不应被解读为真实 TTS 能力验收通过。
