"""Validate competition doc numbers against auto-generated fact sources."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
API_LIST = DOCS / "当前实现API清单.md"
DB_LIST = DOCS / "当前实现数据库清单.md"
BASELINE = DOCS / "当前实现基线.md"
COMP = DOCS / "22_比赛材料规划" / "智学工坊比赛材料合集.md"
EVIDENCE = DOCS / "22_比赛材料规划" / "证据与截图索引.md"
SUBMIT_OVERVIEW = DOCS / "22_比赛材料规划" / "00_比赛提交总览.md"
PPT = DOCS / "22_比赛材料规划" / "演示PPT大纲.md"
DEFENSE = DOCS / "22_比赛材料规划" / "答辩稿.md"

STALE_PATTERNS = [
    (re.compile(r"\b143\b\s*API"), "143 API (stale; expected 147)"),
    (re.compile(r"323\s*passed"), "323 passed (stale; check baseline for current pytest)"),
    (re.compile(r"\b466(?:/466)?\b"), "466 pytest count (stale; check baseline)"),
    (
        re.compile(r"\b24\b\s*(?:个数据库\s*|个\s*)?migration", re.IGNORECASE),
        "24 migration count (stale; check baseline)",
    ),
    (
        re.compile(r"(?:\b61\b\s*(?:个\s*)?(?:后端\s*)?测试文件|\|\s*测试文件\s*\|\s*61\s*\|)"),
        "61 test files (stale; check baseline)",
    ),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_api_count(text: str) -> int:
    m = re.search(r"HTTP 操作数：\*\*(\d+)\*\*", text)
    if not m:
        m = re.search(r"HTTP 操作数：(\d+)", text)
    if not m:
        raise ValueError("Cannot parse API count from 当前实现API清单.md")
    return int(m.group(1))


def extract_db_count(text: str) -> int:
    m = re.search(r"ORM 表数量：\*\*(\d+)\*\*", text)
    if not m:
        m = re.search(r"ORM 表数量：(\d+)", text)
    if not m:
        raise ValueError("Cannot parse DB count from 当前实现数据库清单.md")
    return int(m.group(1))


def check_stale(content: str, label: str, allow_drift_table: bool = False) -> list[str]:
    errors: list[str] = []
    for line_no, line in enumerate(content.splitlines(), 1):
        if allow_drift_table:
            if any(k in line for k in ("漂移", "旧文档", "旧比赛", "旧口径", "→", "「143", "323 pytest")):
                continue
            if re.search(r"\|\s*143\s*\|", line) and "147" in line:
                continue
            if "323 passed" in line and ("352" in line or "361" in line or "9 failed" in line):
                continue
        for pat, msg in STALE_PATTERNS:
            if pat.search(line):
                errors.append(f"{label}:{line_no}: {msg} -> {line.strip()[:80]}")
    return errors


def main() -> int:
    errors: list[str] = []
    api_count = extract_api_count(read(API_LIST))
    db_count = extract_db_count(read(DB_LIST))

    comp = read(COMP)
    if f"**{api_count}** API" not in comp and f"{api_count} API" not in comp:
        errors.append(f"Compendium missing current API count {api_count}")
    if f"**{db_count}** 表" not in comp and f"{db_count} 表" not in comp:
        errors.append(f"Compendium missing current DB table count {db_count}")

    for path, allow in [
        (BASELINE, False),
        (EVIDENCE, False),
        (SUBMIT_OVERVIEW, False),
        (PPT, True),
        (DEFENSE, True),
        (COMP, True),
    ]:
        if path.is_file():
            errors.extend(check_stale(read(path), path.name, allow_drift_table=allow))

    if errors:
        print("validate_competition_doc: FAILED")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(
        f"validate_competition_doc: OK (API={api_count}, DB={db_count}, checked {len(STALE_PATTERNS)} stale patterns)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
