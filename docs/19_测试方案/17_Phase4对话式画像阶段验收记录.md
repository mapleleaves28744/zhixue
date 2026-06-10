# Phase 4 对话式画像与证据化学生模型阶段验收记录

> 验收日期：2026-06-07  
> 验收分支：`change_2`  
> 验收结论：**Phase 4 v1 已接入代码与页面，支持通过 `/assistant` 自然对话更新画像，并在 `/path-profile` 展示证据。**

## 验收范围

本阶段不是新增开放自治 Agent，而是在 Phase 3.1 LangGraph 运行时上补齐“学生可以通过对话让系统理解自己”的画像能力：

```text
学生自然语言描述背景/目标/偏好/薄弱点
→ MiMo Supervisor 识别画像更新意图
→ Tool Registry 调用 update_profile_from_dialogue
→ ProfileService 提取结构化画像信号
→ 写入 student_profiles 与 learning_preferences
→ /path-profile 展示画像摘要和对话证据
```

## 实际实现

- 新增 `ProfileService.ingest_dialogue_profile()`：从自然语言中提取专业、年级、学习目标、回答长度偏好、解释风格、资源偏好、薄弱知识点和错误模式。
- 画像证据写入 `student_profiles.strategy_summary.dialogue_profile`，包含 `source_type`、`source_message_id`、`quote`、`observed_at`、`method` 和置信度。
- 偏好写入 `learning_preferences`：`answer_length`、`explanation_style`、`resource_preferences`、`prompt_params.last_dialogue_evidence`。
- 新增 API：

```text
POST /api/v1/student/profile/dialogue-ingest
```

- 新增 Agent 工具：

```text
update_profile_from_dialogue
```

- MiMo Supervisor 在用户表达“我是…… / 我喜欢…… / 我的目标…… / 请记住我的学习偏好 / 比较薄弱”等画像类意图时，强制优先调用该工具。
- `/path-profile` 画像卡片新增“对话证据”区域，展示画像维度、置信度和来源摘录。

## 示例输入

```text
我是软件工程大二学生，学习目标是期末数据结构拿到 85 分以上。
我递归和二叉树遍历比较薄弱，经常漏掉边界条件。
我喜欢 Python 代码示例、分步骤讲解和短一点的总结，请记住我的学习偏好。
```

预期沉淀：

| 维度 | 结果 |
|---|---|
| 专业 | 软件工程 |
| 年级 | 大二 |
| 学习目标 | 期末数据结构拿到 85 分以上 |
| 薄弱点 | 递归、二叉树遍历 |
| 错误模式 | 边界条件遗漏 |
| 偏好 | `short`、`code_first`、`python_code`、`step_by_step` |

## 验收命令

已新增并通过的目标测试：

```powershell
cd backend
python -m pytest tests/test_profile_dialogue.py `
  tests/test_agent_runtime.py::test_mimo_supervisor_routes_dialogue_profile_updates_to_profile_tool `
  tests/test_agent_runtime.py::test_default_learning_tool_registry_exposes_specialized_agents_and_risk_boundaries -q
```

结果：

```text
5 passed
```

阶段收尾还需执行全量检查：

```powershell
python -m alembic upgrade head
python -m pytest -q
python scripts/export_implementation_docs.py
python scripts/check_docs.py
npm run typecheck
npm run build
```

真实 Agent 演示检查：

```powershell
scripts/start_phase31_demo.ps1
python scripts/agent_demo_check.py --base-url http://127.0.0.1:8000/api/v1
```

最终真实登录浏览器复验结果：

- `/assistant` 能恢复画像更新会话，显示 `update_profile_from_dialogue` 单工具任务、完整事件时间线与最终回答。
- `/path-profile` 显示“大二、软件工程、递归、二叉树遍历”、学习偏好和对话证据原文。
- 纯画像请求不会扩张为资源、练习或学习路径任务。

## 边界

- 本阶段不新增数据库表，复用 `student_profiles.strategy_summary` 与 `learning_preferences.prompt_params` 承载证据。
- 本阶段不保存无意义闲聊，只抽取与学习个性化相关的明确背景、目标、偏好、薄弱点和错误模式。
- 本阶段不允许 Agent 修改代码、权限、数据库结构或部署配置。
- 当前抽取策略是可测试规则 v1；后续可以在同一 Provider 边界内扩展为 MiMo 结构化抽取，但必须保留证据字段和测试覆盖。
