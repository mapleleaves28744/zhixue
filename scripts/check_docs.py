"""Validate consolidated documentation structure and local Markdown references."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SKIP_DIRS = (
    DOCS / "_archive",
)
ACTIVE_NUMBERED = frozenset(
    {
        "00_文档规范",
        "19_测试方案",
        "20_部署方案",
        "22_比赛材料规划",
    }
)
PLACEHOLDER_PATTERNS = (
    "- [ ] 待补充",
    "请根据项目当前实现情况补充本文件内容",
)


def normalized_target(source: Path, raw: str) -> Path | None:
    target = raw.split("#", 1)[0].strip()
    if not target or "://" in target or target.startswith(("mailto:", "#")):
        return None
    if any(token in target for token in ("*", "{", "}", "<", ">")):
        return None
    candidate = Path(target)
    if target.startswith("docs/"):
        return ROOT / candidate
    return source.parent / candidate


def main() -> int:
    errors: list[str] = []
    markdown_files = sorted(DOCS.rglob("*.md"))

    for directory in sorted(DOCS.iterdir()):
        if not directory.is_dir() or directory.name not in ACTIVE_NUMBERED:
            continue
        guide = directory / f"{directory.name}.md"
        if directory.name == "22_比赛材料规划":
            guide = directory / "22_比赛材料规划.md"
        if not guide.exists():
            errors.append(f"missing folder guide: {guide.relative_to(ROOT)}")
            continue
        if "## 目录导读" not in guide.read_text(encoding="utf-8")[:2000]:
            errors.append(f"missing directory guide section: {guide.relative_to(ROOT)}")

    markdown_link = re.compile(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")
    backtick_doc = re.compile(r"`(docs/[^`\n]+\.md)`")

    for path in markdown_files:
        if any(path.is_relative_to(skip) for skip in SKIP_DIRS):
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern in text:
                errors.append(f"placeholder remains: {path.relative_to(ROOT)}")
        for raw in markdown_link.findall(text) + backtick_doc.findall(text):
            target = normalized_target(path, raw)
            if target is not None and not target.resolve().exists():
                errors.append(
                    f"broken reference: {path.relative_to(ROOT)} -> {raw}"
                )

    if errors:
        print("\n".join(errors))
        print(f"documentation check failed: {len(errors)} issue(s)")
        return 1

    print(
        f"documentation check passed: {len(ACTIVE_NUMBERED)} active folders, "
        f"{len(markdown_files)} markdown files, no placeholders or broken local references"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
