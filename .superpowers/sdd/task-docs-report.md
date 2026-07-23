# 文档断链修复执行报告

## 任务范围

仅创建 `docs/19_测试方案/25_真实Provider全量验收记录.md`，用于修复已跟踪真实 Provider 验收计划对该记录的本地引用。未修改计划、业务代码、API、Schema、模型、迁移、前端、演示数据或既有实现文档。

## RED：修改前文档检查

执行命令：

```bash
backend/.venv/bin/python scripts/check_docs.py
```

输出摘要：

```text
broken reference: docs/superpowers/plans/2026-07-11-real-provider-full-acceptance.md -> docs/19_测试方案/25_真实Provider全量验收记录.md
broken reference: docs/superpowers/plans/2026-07-11-real-provider-full-acceptance.md -> docs/19_测试方案/25_真实Provider全量验收记录.md
broken reference: docs/superpowers/plans/2026-07-11-real-provider-full-acceptance.md -> docs/19_测试方案/25_真实Provider全量验收记录.md
broken reference: docs/superpowers/plans/2026-07-11-real-provider-full-acceptance.md -> docs/19_测试方案/25_真实Provider全量验收记录.md
documentation check failed: 4 issue(s)
```

## 事实核验

执行的辅助模块检查：

```bash
backend/.venv/bin/python -m pytest backend/tests/test_real_provider_acceptance_helpers.py -q
backend/.venv/bin/python -m py_compile scripts/real_provider_acceptance.py
```

结果：辅助测试 `3 passed in 0.03s`，语法编译退出码 `0`。

核验发现 `scripts/real_provider_acceptance.py` 当前仅包含 Provider 分类、真实响应拒绝和 Bearer token 脱敏辅助函数；没有 CLI 主入口、`argparse` 参数处理、Provider 预检、认证 API 场景、轮询或 JSON 输出。文件作为 Python 脚本传入计划中的 `--preflight` 等参数时会静默退出，不能据此认定预检或全量验收成功。

工作区中未发现 `*real*provider*.json` 或 `*provider*baseline*.json` 的真实 Provider 全量基线文件。

## 修改

新增 `docs/19_测试方案/25_真实Provider全量验收记录.md`，其中包含：

- 明确的“全量基线尚未建立”结论；
- 已实现辅助函数与未实现全量 Runner 的区分；
- 文本与媒体范围的逐场景“未执行”矩阵；
- 执行前置条件、预计 JSON 产物位置和未来复验命令；
- 对 `13_真实LLM主链路与Next安全专项验收记录.md` 的独立证据链接及非全量边界；
- 不将 Mock、fallback、未配置能力、延迟或产物 ID 虚构为通过结果的真实性约束。

## GREEN：修改后验证

执行命令：

```bash
backend/.venv/bin/python scripts/check_docs.py
git diff --check
git diff --check --cached
```

输出摘要：

```text
documentation check passed: 4 active folders, 124 markdown files, no placeholders or broken local references
```

`git diff --check` 与暂存后的 `git diff --check --cached` 均退出码 `0`，没有空白错误。

## 真实性边界与风险

- 本次没有执行真实 Provider、媒体 Provider、延迟测量、产物访问或全量基线；没有报告通过数量、失败数量、Provider/模型、延迟或产物 ID。
- 13 号记录仍可作为其自身真实 LLM 主链路专项的历史证据，但不能用于填充本记录的全量矩阵。
- 要建立全量基线，须先实现真正处理 `--preflight`、`--base-url`、`--timeout`、`--scenario` 和 `--json-output` 的 Runner，并在配置真实 Provider 的受控环境中执行。

## 提交

提交 `e6c94d0`（`docs: add real provider acceptance status record`）仅包含新增验收记录。
