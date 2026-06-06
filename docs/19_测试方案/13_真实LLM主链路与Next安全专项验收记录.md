# 13_真实 LLM 主链路与 Next 安全专项验收记录

> 验收日期：2026-06-06  
> 验收环境：本机 PostgreSQL、Redis、FastAPI、Next.js；Docker 未参与本专项。  
> 目标：验证真实 LLM 主链路稳定性，并完成 Next.js 14 安全升级专项。

## 验收结论

- 真实 LLM 后端主链路通过。
- 实际 Provider：`xiaomi_mimo`。
- 实际模型：`mimo-v2.5`。
- `fallback_used=false`，未使用 Mock 代替真实 LLM 结论。
- 后端测试：`91 passed`。
- 前端升级：Next.js `14.2.35` → `16.2.7`。
- 前端依赖审计：`0 vulnerabilities`。

## 执行方式

后端启动并配置真实 LLM Provider 后执行：

```powershell
python scripts/main_chain_check.py

# 或
scripts/local_check.ps1 -MainChain
```

验收脚本每次创建隔离测试账号和课程，避免读取其他学生数据。若 Tutor 返回 Mock Provider 或发生 fallback，脚本直接失败。

## 主链路结果

| 链路节点 | 实际结果 |
|---|---|
| 注册、登录、课程创建 | 通过 |
| 资料上传、解析 | 通过；解析文本长度 239 |
| 文档切片、向量化 | 通过；4 个 chunk，4 条 embedding |
| 知识点抽取、RAG 检索 | 通过；5 个知识点，检索返回 3 条资料片段 |
| Wiki 生成、详情、版本 | 通过；生成 5 个页面，详情有正文、来源和版本 |
| Tutor 答疑 | 通过；有真实模型回答和引用，未回退 |
| 个性化资源生成 | 通过；内容与个性化理由非空 |
| 练习生成、提交、错题 | 通过；生成 3 道题，故意错答后写入错题本 |
| 学习诊断 | 通过；报告、摘要、建议动作已落库 |
| 学生画像重建 | 通过 |
| 长期记忆反思 | 调用通过；本轮因证据阈值未生成长期记忆，返回 0 条 |
| 自进化分析 | 通过；生成 1 条带证据策略 |
| 推荐刷新、Agent 日志 | 通过；可查询到 6 条 Agent 运行记录 |

完整 23 步执行总耗时约 `224.1s`。真实模型调用耗时最高的节点为 Wiki、Tutor、资源、练习、诊断与自进化，符合外部模型调用特征。

## Next 安全升级

升级前：

- Next.js `14.2.35`。
- `npm audit`：1 个 high、1 个 moderate。
- 命中 DoS、SSRF、权限绕过、缓存投毒等 Next.js 安全公告。

升级后：

- Next.js 固定为 `16.2.7`。
- 保留 React `18.3.1`，减少升级范围。
- 使用 npm override 将 Next 内部 PostCSS 从 `8.4.31` 统一到已修复的 `8.5.15`。
- `npm run typecheck` 通过。
- `npm run build` 通过，11 个 App Router 页面完成静态生成。
- `npm audit --audit-level=moderate`：`0 vulnerabilities`。
- Next 16 开发服务启动后，品牌首页及 `knowledge`、`assistant`、`practice`、`path-profile`、`dashboard`、`courses` Stitch 页面浏览器烟测通过，逐页导航未新增控制台错误。

## 基础回归

```text
python -m alembic upgrade head       通过
python -m pytest -q                  91 passed
npm run typecheck                    通过
npm run build                        通过
npm audit --audit-level=moderate     0 vulnerabilities
```

## 已知限制

1. 本次真实验收确认聊天生成类能力使用真实 LLM；Embedding 按当前环境中的 Embedding Provider 配置执行。
2. 长期记忆反思本轮返回 0 条，表示证据未达到写入阈值，不代表接口失败。
3. 真实 LLM 主链路会产生测试账号、课程和学习记录，并消耗 API 配额，因此不纳入 `scripts/local_check.ps1 -All`。
4. 本专项不包含 Docker 验收；Docker 仍按第21阶段单独验收。
