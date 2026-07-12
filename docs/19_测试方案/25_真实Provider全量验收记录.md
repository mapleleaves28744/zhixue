# 25_真实 Provider 全量验收记录

> 记录状态：**验收基线尚未建立；本文件仅记录当前可核验的 Runner 准备度和复验边界。**
>
> 建立日期：2026-07-12
> 适用范围：文本 LLM 与外部媒体 Provider 的全量、真实 Provider 验收，不替代 Mock 测试或既有真实 LLM 主链路专项。

## 结论

当前工作区没有可核验的真实 Provider 全量验收 JSON、逐场景通过矩阵、延迟或产物 ID。因此本记录中不存在任何全量通过结论，也没有将 Mock、fallback 或未配置能力计为通过。

`scripts/real_provider_acceptance.py` 当前提供并已测试 Provider 分类、真实响应拒绝和错误脱敏辅助函数；它**尚未**提供计划中的命令行入口、Provider 预检、认证 API 场景执行、轮询、JSON 输出或逐场景结果汇总。故当前不能以该文件执行真实 Provider 全量基线，也不能从其进程退出码推导出验收结果。

现有的 [真实 LLM 主链路与 Next 安全专项验收记录](13_真实LLM主链路与Next安全专项验收记录.md) 是 2026-06-06 的独立主链路证据：其中记录了 `xiaomi_mimo / mimo-v2.5`、`fallback_used=false` 和 23 步主链路结果。该专项未覆盖本记录要求的所有 Provider、媒体能力、逐场景延迟和持久化产物，因此不作为本全量矩阵的结果。

## 当前可核验的准备度

| 项目 | 状态 | 可核验证据 | 结论边界 |
|---|---|---|---|
| Provider 分类和 fallback 拒绝辅助函数 | 已实现并通过单元测试 | `backend/tests/test_real_provider_acceptance_helpers.py`：3 passed | 仅证明纯函数规则；不调用 Provider 或业务 API。 |
| 辅助模块语法 | 可编译 | `backend/.venv/bin/python -m py_compile scripts/real_provider_acceptance.py` | 不证明 CLI、网络、认证或场景执行存在。 |
| 全量验收 CLI | 未实现 | 文件没有 `argparse`、主入口或场景执行代码 | `--preflight`、`--scenario`、`--timeout`、`--json-output` 目前均不能形成验收语义。 |
| 真实 Provider 预检 | 未执行且当前不可由该模块执行 | 无预检输出文件或结构化记录 | 未确认文本、图像、音频、视频或沉浸课堂 Provider 配置。 |
| 真实 Provider 全量基线 | 未执行 | 未发现 `*real*provider*.json` 或 `*provider*baseline*.json` 基线文件 | 无通过数量、失败数量、延迟、Provider/模型或产物 ID 可报告。 |

## 全量状态矩阵

下表列出计划中需要逐项验收的范围。所有“未执行”均表示没有可核验证据，并不表示 Provider 不可用或接口失败。

| 场景 | Provider / 模型 | 状态 | API / 首次输出 / 完成耗时 | 证据 ID | 结果或失败边界 |
|---|---|---|---|---|---|
| Wiki 生成 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无认证场景调用、真实响应校验和持久化页面证据。 |
| Tutor 对话 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无 `fallback_used=false`、引用和完成事件的全量基线。 |
| 个性化资源生成 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无真实响应、资源持久化和归属访问证据。 |
| 练习生成与提交 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无题目、提交和错题持久化基线。 |
| 学习诊断 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无诊断报告与建议动作的真实 Provider 证据。 |
| 学习路径生成 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无路径持久化和真实 Provider 证据。 |
| 自进化分析 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无策略、证据和风险字段的全量基线。 |
| Agent 对话任务 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无任务成功、`completed` 事件、助手消息和工具事件证据。 |
| 教学图片 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚未预检图像 Provider，也无归属可访问产物。 |
| 语音合成 / 转写 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚未预检音频 Provider，也无媒体资产证据。 |
| 互动课件 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无任务轮询和资源产物证据。 |
| 课程视频 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚未预检视频 Provider，也无可访问媒体产物。 |
| 沉浸课堂 | 未采集 | 未执行（全量 Runner 不可用） | 未采集 | 无 | 尚无任务轮询、签名访问和导出产物证据。 |

## 执行前置条件

在建立真实 Provider 全量基线前，执行环境必须满足以下条件：

1. 实现全量 Runner 的 CLI，并让它实际处理 `--preflight`、`--base-url`、`--timeout`、`--scenario` 和 `--json-output` 参数；未知参数或空输出不能视为成功。
2. 使用独立测试账号和私有《数据结构》课程；测试过程不得读取其他学生数据。
3. 后端、PostgreSQL、Redis、Worker 及需要的媒体服务均已启动，且 `base-url` 指向可认证的 `/api/v1` 服务。
4. 每个被调用的 Provider 配置为真实 Provider；响应必须记录 Provider / 模型，并在存在该字段时要求 `fallback_used=false`。
5. 每个媒体能力先记录“已配置”或“未配置”；未配置能力应写为 `not_configured`，不得调用其接口或记为通过。
6. Runner 必须对每个场景保留脱敏后的请求失败边界、首个输出和完成耗时、任务/作业/产物 ID，以及归属令牌下的可访问性校验。

## 复验步骤与产物位置

当前已执行的准备度检查：

```bash
backend/.venv/bin/python -m pytest backend/tests/test_real_provider_acceptance_helpers.py -q
backend/.venv/bin/python -m py_compile scripts/real_provider_acceptance.py
```

2026-07-12 的结果分别为 `3 passed` 和退出码 `0`。它们不产生 Provider 基线 JSON。

在 CLI 和场景 Runner 完整实现后，才可使用以下命令建立新的基线；这些命令在本记录建立时**没有执行**：

```bash
backend/.venv/bin/python scripts/real_provider_acceptance.py \
  --preflight \
  --base-url http://127.0.0.1:8000/api/v1

backend/.venv/bin/python scripts/real_provider_acceptance.py \
  --base-url http://127.0.0.1:8000/api/v1 \
  --timeout 900 \
  --json-output /tmp/real-provider-baseline.json
```

预期产物位置为显式传入的 JSON 路径，例如 `/tmp/real-provider-baseline.json`；产物应至少包含 `provider_preflight`、逐场景结果和汇总计数。将脱敏 JSON 的路径、生成时间和每行矩阵的证据 ID 追加到本记录后，才能更新对应状态。不得用旧 JSON 代表变更后的代码状态。

## 已知限制与真实性边界

1. 当前辅助模块只拒绝 `mock`、`fallback`、`mock_multimodal` 和 `mock_audio` 等非真实 Provider 标识；它没有发起网络调用或检查实际配置。
2. 当前没有真实媒体 Provider 的配置预检、延迟、作业 ID、媒体资产 ID 或可访问产物可供记录。
3. 真实 Provider 验收会消耗外部配额并创建测试数据，必须在获得所需账号和服务权限后执行；没有这些条件时，状态应保持“未执行”或明确标为 `not_configured`。
4. 本记录不改变现有 API、数据库、业务逻辑或测试计划；它只提供诚实的全量验收状态入口和复验规则。
