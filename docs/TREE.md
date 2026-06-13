# 文档目录结构

> 日常只关心 [README.md](README.md) 里的 6 个入口即可。

```text
docs/
├── README.md
├── 当前实现基线.md
├── 当前实现API清单.md
├── 当前实现数据库清单.md
├── 功能完成度与待完善清单.md
├── DESIGN.md
├── 00_文档规范/
├── 19_测试方案/
├── 20_部署方案/
├── 22_比赛材料规划/
├── assets/
└── _archive/
    ├── 设计文档/          ← 01–18、21 及 API/DB 设计详情
    ├── competition_sources/
    └── …
```

维护命令：`python scripts/export_implementation_docs.py` · `python scripts/check_docs.py`
