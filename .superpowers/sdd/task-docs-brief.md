# 文档断链修复任务

## 目标

创建 `docs/19_测试方案/25_真实Provider全量验收记录.md`，修复已跟踪真实 Provider 验收计划对该文件的本地引用，并让 `scripts/check_docs.py` 通过。

## 事实与约束

- `scripts/real_provider_acceptance.py` 和 `backend/tests/test_real_provider_acceptance_helpers.py` 已存在，但当前工作区没有已执行的真实 Provider 全量基线 JSON 或可核验通过矩阵。
- 不得伪造真实 Provider、媒体 Provider、延迟、产物 ID、通过数量或 fallback=false 的执行结果。
- 记录必须清楚区分“验收 Runner 已实现并可执行”与“真实 Provider 全量基线尚未在本环境执行”。
- 将真实主链路的既有证据链接到 `13_真实LLM主链路与Next安全专项验收记录.md`，但不要将其表述为本记录的全量 Provider 结果。
- 不修改业务代码、API、Schema、Model、migration、前端、演示数据或已有实现计划；仅创建此验收记录。
- 文档遵守目录规范：标题、运行命令、状态矩阵、执行前置条件、产物/日志位置、已知限制与复验步骤必须具体，无“待补充”占位文本。

## TDD/验证

先运行 `backend/.venv/bin/python scripts/check_docs.py` 并记录缺失文件导致的失败；创建记录后重跑相同命令并观察通过。运行 `git diff --check`。提交仅包含新记录。

## 报告

将完整报告写入 `.superpowers/sdd/task-docs-report.md`，包括 RED/GREEN 命令与输出、修改文件、真实性边界和 commit。
