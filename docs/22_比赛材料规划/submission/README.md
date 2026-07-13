# 比赛提交包

> 对外配套文档目标：**1 份** Word（由主文档导出）。当前仓库保留 Markdown 副本；只有安装 pandoc 并执行导出后才会生成 `.docx`。

| 文件 | 说明 |
|---|---|
| `智学工坊系统说明书.docx` | 由 [`../智学工坊比赛材料合集.md`](../智学工坊比赛材料合集.md) 导出 |
| `智学工坊系统说明书.md` | 无 pandoc 时的 Markdown 副本 |

## 生成命令

```bash
# 1. 刷新事实源（改 API/Model 后）
python3 scripts/export_implementation_docs.py

# 2. 全量测试（2026-07-13：466 passed）
cd backend && .venv/bin/python -m pytest tests -q

# 3. 校验文档数字
python3 scripts/validate_competition_doc.py

# 4. 导出 Word（需 pandoc）
python3 scripts/export_competition_docx.py

# 5. 可选：渲染架构图 PNG（需 mmdc）
bash scripts/render_diagrams.sh
```

> **环境提示**：若 Cursor/CI shell 设置了 `DEBUG=release` 等非布尔值，会覆盖 `.env` 导致 pytest 无法启动；本地请 `unset DEBUG`。仓库内 `.env` / `backend/.env` 的 `DEBUG=true/false` 是正确的。

维护入口：只编辑 [`../智学工坊比赛材料合集.md`](../智学工坊比赛材料合集.md)，不要恢复 6 份分散说明书。
