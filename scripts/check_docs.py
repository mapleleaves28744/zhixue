"""Validate consolidated documentation structure and local Markdown references."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
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
        if not directory.is_dir() or not re.match(r"^\d\d_", directory.name):
            continue
        guide = directory / f"{directory.name}.md"
        if not guide.exists():
            errors.append(f"missing folder guide: {guide.relative_to(ROOT)}")
            continue
        if "## 目录导读" not in guide.read_text(encoding="utf-8")[:2000]:
            errors.append(f"missing directory guide section: {guide.relative_to(ROOT)}")

    markdown_link = re.compile(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")
    backtick_doc = re.compile(r"`(docs/[^`\n]+\.md)`")

    for path in markdown_files:
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

    numbered = sum(
        1 for path in DOCS.iterdir() if path.is_dir() and re.match(r"^\d\d_", path.name)
    )
    print(
        f"documentation check passed: {numbered} numbered folders, "
        f"{len(markdown_files)} markdown files, no placeholders or broken local references"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
