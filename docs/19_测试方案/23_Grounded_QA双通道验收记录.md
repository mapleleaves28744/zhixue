# Grounded QA 双通道验收记录

> 验收日期：2026-07-11
>
> 验收范围：Tutor 快速通道、LangGraph Agent 资料问答通道、引用证据、助手交互和响应式布局
>
> 运行环境：本地 PostgreSQL/Redis，后端 `127.0.0.1:8010`，Next.js `localhost:3000`

## 结论

快速问答与 Agent 纯资料问答已共用 `GroundedQAPipeline`。回答只进行一次主 LLM 调用，证据来自当前课程的文档 chunk 或 Wiki 页面并保留真实 ID；模型引用经确定性校验后才返回。Agent 不再重复执行已完成的资料问答，非关键画像/记忆处理移至异步后置任务。

本次工程验收通过，但质量结论受 Mock 环境限制：检索与引用协议可回归，不能据此宣称真实模型回答正确率已达标。

## 自动化结果

| 检查 | 结果 |
|---|---|
| `cd backend; python -m pytest tests -q` | 402 passed，6 个 FastAPI `on_event` 弃用警告 |
| `cd backend; python -m compileall -q app tests` | 通过 |
| 三个 Assistant Node 契约脚本 | 通过：工具选项、发送/停止、响应式布局 |
| `cd frontend; npm run typecheck` | 通过 |
| `cd frontend; npx next build --webpack` | 通过，13 个页面生成步骤完成；`/login` 按需服务端渲染 |
| `python scripts/check_docs.py` | 通过：114 个 Markdown 文件，无占位和本地断链 |
| `python scripts/export_implementation_docs.py` | 通过：143 个 API 操作、44 个数据库表 |

默认 Turbopack 构建在该 worktree 的外部 `node_modules` junction 环境中失败；改用 webpack 后生产构建通过。这是本地依赖布局限制，不作为代码通过 Turbopack 的证据。

## 公有知识库评测

执行 `python scripts/evaluate_public_kb.py --run-llm-sample 33`，题集为 30 道可回答题和 3 道不可回答干扰题。严格引用校验要求来源正确，且同一引用覆盖该题定义的全部必需证据词组；嵌套词组表示可接受的同义表达。

| 指标 | 结果 |
|---|---:|
| Recall@5 | 1.0000 |
| MRR | 0.9467 |
| 严格引用精度 | 0.2833 |
| 引用覆盖率 | 0.4000 |
| 不可回答拒答率 | 1.0000 |
| 回答正确率 | 未评分（`null`） |
| LLM 评测回答数 | 33 |
| 人工评分数 | 0 |

聊天 Provider 为 Mock，embedding 报告同样标记为 Mock（模型名配置为 `text-embedding-3-small`、1024 维）。严格指标显示当前引用质量仍未达理想目标：部分答案虽找到正确资料，但单条引用没有覆盖问题要求的全部关键依据。报告不得用于宣称真实模型质量；后续必须改善证据切片/引用选择，并在比赛环境中用真实 Provider 和人工评分补齐 `answer_correctness`。

## 浏览器验收

使用登录用户 `stu_01` 和公有课程《数据结构》，提问“栈为什么适合括号匹配？请基于课程资料回答并给出引用。”：

1. 回答完成后显示“基于 2 条课程资料”和 Mock 标识；引用可展开并显示真实资料标题与 chunk。
2. “有用”反馈提交成功；选择 Wiki“栈”后保存成功。
3. 刷新页面后，问题、完整回答、依据状态和操作按钮由历史记录恢复。
4. 1440×900 显示桌面资源侧栏；960×768 显示右侧资源 Dialog；390×844 显示底部资源 Dialog。三种尺寸下输入框与主要操作均可见。
5. 应用控制台未发现相关运行时错误，仅有 Next.js 平滑滚动提示；浏览器工具自身的 Statsig 网络错误与应用无关。

截图在本次交互式验收中生成查看，但未作为仓库文件提交。

## 实测性能与边界

上述一次 Mock 回答的学习记录指标：

| 指标 | 数值 |
|---|---:|
| retrieval_ms | 2033 |
| first_token_ms | 2234 |
| generation_ms | 74 |
| total_ms | 2307 |
| llm_call_count | 1 |
| 候选 / 接受 / 有效引用 | 10 / 3 / 2 |

该结果验证了单次主 LLM 调用和完整引用链，但首字延迟仍主要受本地检索影响，尚未达到亚秒级。下一阶段应对真实 embedding/数据库检索做剖析和缓存，并分别统计 P50/P95；不能只以 Mock 生成速度代表用户实际体验。

端口 `8001` 在本机被系统进程占用，本次后端改在 `8010` 验收；不影响 API 语义。无数据库结构变更，无 Alembic migration。
