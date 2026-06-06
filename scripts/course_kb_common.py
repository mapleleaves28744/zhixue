from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPO_ROOT / "data" / "seed_knowledge" / "data_structure"
SELF_CURATED_ROOT = REPO_ROOT / "data" / "数据结构知识库"

REQUIRED_IMPORT_STATUSES = {
    "candidate",
    "approved_link_only",
    "approved_importable",
    "rejected",
}
REQUIRED_REVIEW_STATUSES = {
    "unreviewed",
    "approved",
    "needs_revision",
    "rejected",
}


def read_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_phase1_dirs(source_root: Path = DEFAULT_SOURCE_ROOT) -> None:
    for name in (
        "raw",
        "normalized",
        "normalized/self_curated",
        "normalized/authoritative",
        "graph",
        "wiki_seed",
        "eval",
        "artifacts",
    ):
        (source_root / name).mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    return value.strip("-") or "untitled"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", value).strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer"}:
            self._skip_depth += 1
            return
        if tag in {"h1", "h2", "h3", "h4"}:
            self.parts.append("\n\n# ")
        elif tag in {"p", "li", "tr", "pre", "div", "section", "article"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in {"h1", "h2", "h3", "h4", "p", "li", "pre"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.parts.append(text + " ")


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return normalize_whitespace("".join(parser.parts))


def frontmatter(metadata: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            text = str(value).replace("\n", " ").strip()
            lines.append(f"{key}: {text}")
    lines.append("---")
    return "\n".join(lines)


def read_sources(source_root: Path = DEFAULT_SOURCE_ROOT) -> list[dict[str, Any]]:
    manifest = read_yaml(source_root / "sources_manifest.yml")
    sources = manifest.get("sources", []) if isinstance(manifest, dict) else []
    return [source for source in sources if isinstance(source, dict)]
