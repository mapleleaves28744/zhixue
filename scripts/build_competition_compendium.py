"""Build docs/22_比赛材料规划/智学工坊比赛材料合集.md from source materials."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ARCHIVE_DESIGN = DOCS / "_archive" / "设计文档"
COMP = DOCS / "22_比赛材料规划"
SRC = DOCS / "_archive" / "competition_sources"
OUT = COMP / "智学工坊比赛材料合集.md"

SOURCE_FILES = [
    "软件需求规格说明书.md",
    "软件系统开发说明书.md",
    "软件系统测试说明书.md",
    "功能说明书.md",
    "用户使用说明书.md",
    "AI_Coding工具使用说明.md",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_doc_header(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    while lines and (lines[0].strip().startswith(">") or lines[0].strip() == ""):
        lines = lines[1:]
    if lines and lines[0].startswith("## 目录导读"):
        for i, line in enumerate(lines):
            if line.startswith("## ") and not line.startswith("## 目录导读"):
                return "\n".join(lines[i:]).strip()
    return "\n".join(lines).strip()


def src(name: str) -> str:
    return strip_doc_header(read(SRC / name))


def main() -> None:
    for name in SOURCE_FILES:
        if not (SRC / name).is_file():
            raise FileNotFoundError(f"Missing source: {SRC / name}")

    baseline = read(DOCS / "当前实现基线.md")
    pos = read(ARCHIVE_DESIGN / "02_项目定位与创新设计" / "02_项目定位与创新设计.md")
    dev = read(SRC / "软件系统开发说明书.md")
    user = read(SRC / "用户使用说明书.md")

    ai = dev.split("## 4. AI 融合方式", 1)[1].split("## 5. 开发流程", 1)[0].strip()
    ai = ai.replace("## 4.", "## 5.").replace("### 4.", "### 5.")
    deploy = dev.split("## 7. 部署流程", 1)[1].split("## 8. 冻结边界", 1)[0].strip()

    sections: list[str] = [
        """# 智学工坊比赛材料合集

> **2026-06-13 代码对齐版** — 约 2150 行，与当前实现基线、143 API、44 表、322 pytest 一致。维护：改 `_archive/competition_sources/` 后运行 `python scripts/build_competition_compendium.py`。
>
> 本文档合并需求、功能、架构、设计、测试、部署、使用说明与 AI Coding 全部比赛口径。
> 判断实现事实以本文 + 代码为准；精确 API/表字段见 `当前实现API清单.md`。
>
> **给 AI 的阅读提示**：按章顺序阅读；数字见「附录 A」；未实现项见「附录 B」。

---

## 文档目录

1. [项目概述](#1-项目概述与赛题定位) · 2. [需求分析](#2-需求分析) · 3. [创新设计](#3-创新点与设计理念)
4. [系统架构](#4-系统架构与技术栈) · 5. [多智能体](#5-多智能体与-ai-融合) · 6. [功能模块](#6-功能模块详解)
7. [前端体验](#7-前端页面与用户体验) · 8. [数据与API](#8-数据与-api-概要) · 9. [安全边界](#9-安全隐私与系统边界)
10. [测试验收](#10-测试与验收) · 11. [部署运行](#11-部署与本地运行) · 12. [用户手册](#12-用户使用说明)
13. [AI Coding](#13-ai-coding-工具说明) · 14. [演示答辩](#14-演示答辩与提交)
A. [数字证据](#附录-a可引用数字与证据) · B. [已知缺口](#附录-b已知缺口与诚实口径)

---""",
        "# 1. 项目概述与赛题定位",
        "## 1.1 一句话结论\n\n"
        + baseline.split("## 一句话结论", 1)[1].split("## 当前规模", 1)[0].strip(),
        "## 1.2 项目定位与创新\n\n"
        + pos.split("## 项目定位", 1)[1].split("## 核心创新", 1)[0].strip(),
        "## 1.3 当前规模\n\n"
        + baseline.split("## 当前规模", 1)[1].split("## 当前前端形态", 1)[0].strip(),
        "## 1.4 已验收主链路\n\n"
        + baseline.split("## 当前已验收主链路", 1)[1].split("## 当前明确未实现", 1)[0].strip(),
        "---",
        f"# 2. 需求分析\n\n{src('软件需求规格说明书.md')}",
        "---",
        "# 3. 创新点与设计理念\n\n"
        + pos.split("## 核心创新", 1)[1].split("## MVP", 1)[0].strip(),
        "---",
        f"# 4. 系统架构与技术栈\n\n{src('软件系统开发说明书.md')}",
        "---",
        "# 5. 多智能体与 AI 融合",
        f"## 5.1 AI 融合\n\n{ai}",
        "## 5.2 后端 AI 能力\n\n"
        + baseline.split("## 当前后端形态", 1)[1].split("## 当前 Agent", 1)[0].strip(),
        "## 5.3 Agent 运行时\n\n"
        + baseline.split("## 当前 Agent", 1)[1].split("## 当前已验收主链路", 1)[0].strip(),
        "---",
        f"# 6. 功能模块详解\n\n{src('功能说明书.md')}",
        "---",
        "# 7. 前端页面与用户体验",
        "## 7.1 路由形态\n\n"
        + baseline.split("## 当前前端形态", 1)[1].split("## 当前后端形态", 1)[0].strip(),
        "## 7.2 页面作用\n\n"
        + user.split("## 5. 各页面分别做什么", 1)[1].split("## 6.", 1)[0].strip(),
        "## 7.3 桌宠\n\n"
        + user.split("### 4.10 桌宠", 1)[1].split("## 5.", 1)[0].strip(),
        "---",
        """# 8. 数据与 API 概要

## 8.1 数据层

PostgreSQL + pgvector（44 表）、Redis、本地 `backend/storage`。清单：`docs/当前实现数据库清单.md`

## 8.2 API 层

`/api/v1`，143 操作，统一 `{ code, message, data, request_id }`。清单：`docs/当前实现API清单.md`

## 8.3 分组

认证、课程、资料、知识库、Wiki、Tutor、资源、练习、诊断、画像、记忆、自进化、Agent、学习分析、推荐。""",
        "---",
        """# 9. 安全、隐私与系统边界

JWT 用户隔离；课程归属校验；AI 有来源与 Review；自进化不改代码/DB/权限；Agent 工具白名单；OpenMAIC HMAC 签名。""",
        "---",
        f"# 10. 测试与验收\n\n{src('软件系统测试说明书.md')}",
        "---",
        f"# 11. 部署与本地运行\n\n{deploy}",
        "---",
        f"# 12. 用户使用说明\n\n{src('用户使用说明书.md')}",
        "---",
        f"# 13. AI Coding 工具说明\n\n{src('AI_Coding工具使用说明.md')}",
        "---",
        """# 14. 演示、答辩与提交

7 分钟路径：`/` → 建课资料 → Wiki → `/assistant` → OpenMAIC → `/practice` → 画像自进化 → `/home`

创新：LLM Wiki | 受控自进化 | 可观察 Agent

PPT：`演示PPT大纲.md` · 数字：`证据与截图索引.md`""",
        "---",
        """# 附录 A：可引用数字与证据

| 指标 | 数值 |
|---|---:|
| API | 143 |
| ORM 表 | 44 |
| Agent | 14 |
| pytest | 322 passed |
| 真实 LLM | 23 步 (mimo-v2.5) |
| Agent 场景 | 20/20, 95% |
| 知识库 | 32 资料 / 1608 chunks |""",
        "---",
        """# 附录 B：已知缺口与诚实口径

教师/管理员端（冻结）、一键演示数据、全站 E2E、Docker 全栈、GraphRAG/MinIO（规划增强）

---

*生成：`python scripts/build_competition_compendium.py` · 源文件：`docs/_archive/competition_sources/`*""",
    ]

    body = "\n\n".join(sections)
    body = body.replace(
        "[软件系统开发说明书.md](软件系统开发说明书.md)",
        "[智学工坊比赛材料合集.md §4](智学工坊比赛材料合集.md#4-系统架构与技术栈)",
    )
    for old, new in (
        ("docs/11_API接口设计/16_当前实现API清单.md", "docs/当前实现API清单.md"),
        ("docs/10_数据库设计/15_当前实现数据库清单.md", "docs/当前实现数据库清单.md"),
        ("../11_API接口设计/16_当前实现API清单.md", "../当前实现API清单.md"),
        ("../10_数据库设计/15_当前实现数据库清单.md", "../当前实现数据库清单.md"),
        ("../../当前实现API清单.md", "../当前实现API清单.md"),
        ("../../当前实现数据库清单.md", "../当前实现数据库清单.md"),
        ("../../19_测试方案/", "../19_测试方案/"),
        ("../../22_比赛材料规划/", "./"),
        ("16_当前实现API清单.md](../11_API接口设计/16_当前实现API清单.md", "当前实现API清单.md](../当前实现API清单.md"),
        ("15_当前实现数据库清单.md](../10_数据库设计/15_当前实现数据库清单.md", "当前实现数据库清单.md](../当前实现数据库清单.md"),
    ):
        body = body.replace(old, new)
    OUT.write_text(body, encoding="utf-8")
    line_count = len(OUT.read_text(encoding="utf-8").splitlines())
    print(f"Wrote {OUT.relative_to(ROOT)} ({line_count} lines)")


if __name__ == "__main__":
    main()
