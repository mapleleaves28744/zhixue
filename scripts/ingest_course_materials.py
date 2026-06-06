from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.course_kb_common import (
    DEFAULT_SOURCE_ROOT,
    SELF_CURATED_ROOT,
    ensure_phase1_dirs,
    frontmatter,
    html_to_text,
    normalize_whitespace,
    read_sources,
    sha256_text,
    slugify,
)
from scripts.discover_course_sources import write_manifest


def select_importable_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        source
        for source in sources
        if source.get("import_status") == "approved_importable"
        and source.get("review_status") == "approved"
    ]


def download_approved_sources(
    source_root: Path = DEFAULT_SOURCE_ROOT,
    *,
    dry_run: bool = False,
    timeout_seconds: float = 30.0,
) -> list[Path]:
    sources = read_sources(source_root)
    if not sources:
        write_manifest(source_root)
        sources = read_sources(source_root)

    downloaded: list[Path] = []
    failure_log: list[dict[str, str]] = []
    headers = {
        "User-Agent": "zhixue-workshop-phase1-kb/1.0 (+https://localhost)"
    }
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True, headers=headers) as client:
        for source in select_importable_sources(sources):
            for item in source.get("download_urls") or []:
                url = item["url"] if isinstance(item, dict) else str(item)
                parsed = urlparse(url)
                suffix = Path(parsed.path).suffix or ".html"
                raw_dir = source_root / (source.get("local_path") or f"raw/{source['source_id']}")
                file_name = f"{slugify(item.get('title') or parsed.path or source['source_id'])}{suffix}"
                target = raw_dir / file_name
                if dry_run:
                    print(f"DRY download {url} -> {target}")
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    target.write_bytes(response.content)
                    downloaded.append(target)
                except Exception as exc:
                    failure_log.append(
                        {
                            "source_id": source["source_id"],
                            "url": url,
                            "error": str(exc),
                        }
                    )
                    print(f"WARN download failed: {source['source_id']} {url} ({exc})")
    if not dry_run:
        record_download_failures(source_root, failure_log)
    return downloaded


def record_download_failures(source_root: Path, failure_log: list[dict[str, str]]) -> Path:
    from scripts.course_kb_common import write_json

    path = source_root / "artifacts" / "download_failures.json"
    write_json(path, failure_log)
    return path


def normalize_authoritative_sources(source_root: Path = DEFAULT_SOURCE_ROOT) -> list[Path]:
    sources = read_sources(source_root)
    normalized: list[Path] = []
    for source in select_importable_sources(sources):
        if source["source_id"] == "self-curated-draft":
            continue
        raw_dir = source_root / (source.get("local_path") or f"raw/{source['source_id']}")
        if not raw_dir.exists():
            continue
        for raw_path in sorted(raw_dir.glob("*")):
            if raw_path.is_dir():
                continue
            raw_text = _read_raw_text(raw_path)
            if not raw_text:
                continue
            title = raw_path.stem.replace("-", " ").strip()
            chapter_id = _chapter_id_for_raw(source, raw_path)
            metadata = {
                "source_id": source["source_id"],
                "source_type": source["source_type"],
                "chapter_id": chapter_id,
                "license": source["license"],
                "source_url": source["url"],
                "attribution": source["name"],
                "imported_at": datetime.now(UTC).isoformat(),
                "text_hash": sha256_text(raw_text),
            }
            normalized_path = (
                source_root
                / "normalized"
                / "authoritative"
                / source["source_id"]
                / f"{slugify(chapter_id)}-{slugify(title)}.md"
            )
            normalized_path.parent.mkdir(parents=True, exist_ok=True)
            normalized_path.write_text(
                f"{frontmatter(metadata)}\n\n# {title}\n\n{raw_text}\n",
                encoding="utf-8",
            )
            normalized.append(normalized_path)
    return normalized


def normalize_self_curated(source_root: Path = DEFAULT_SOURCE_ROOT) -> list[Path]:
    if not SELF_CURATED_ROOT.exists():
        return []
    source_dir = SELF_CURATED_ROOT / "02_LLMWiki知识页"
    if not source_dir.exists():
        return []

    created: list[Path] = []
    for index, path in enumerate(sorted(source_dir.glob("*.md")), start=1):
        content = normalize_whitespace(path.read_text(encoding="utf-8"))
        chapter_id = f"self-{index:02d}"
        metadata = {
            "source_id": "self-curated-draft",
            "source_type": "self_curated_draft",
            "chapter_id": chapter_id,
            "license": "self-curated",
            "source_url": "data/数据结构知识库",
            "attribution": "智学工坊自有 AI 整理草稿",
            "imported_at": datetime.now(UTC).isoformat(),
            "text_hash": sha256_text(content),
        }
        target = source_root / "normalized" / "self_curated" / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"{frontmatter(metadata)}\n\n{content}\n",
            encoding="utf-8",
        )
        created.append(target)

    for source_file in (
        "03_知识库切片_jsonl/ds_kb_chunks.jsonl",
        "04_知识图谱_csv/entities.csv",
        "04_知识图谱_csv/relations.csv",
        "04_知识图谱_csv/triples.csv",
        "05_题库与测评/question_bank.jsonl",
        "06_代码示例",
        "07_学习路径与先修关系/prerequisite_edges.csv",
    ):
        _copy_self_curated_artifact(source_file, source_root)
    return created


def ingest(
    source_root: Path = DEFAULT_SOURCE_ROOT,
    *,
    download_approved: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    ensure_phase1_dirs(source_root)
    if not (source_root / "sources_manifest.yml").exists():
        write_manifest(source_root)

    if dry_run:
        sources = read_sources(source_root)
        importable = select_importable_sources(sources)
        return {
            "source_root": str(source_root),
            "importable_source_count": len(importable),
            "will_download": sum(len(source.get("download_urls") or []) for source in importable)
            if download_approved
            else 0,
            "self_curated_available": (SELF_CURATED_ROOT / "02_LLMWiki知识页").exists(),
        }

    downloaded = download_approved_sources(source_root) if download_approved else []
    self_curated = normalize_self_curated(source_root)
    authoritative = normalize_authoritative_sources(source_root)
    return {
        "downloaded_count": len(downloaded),
        "self_curated_count": len(self_curated),
        "authoritative_count": len(authoritative),
    }


def _read_raw_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return html_to_text(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix in {".md", ".txt", ".rst"}:
        return normalize_whitespace(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return normalize_whitespace("\n\n".join(page.extract_text() or "" for page in reader.pages))
        except Exception:
            return ""
    return ""


def _chapter_id_for_raw(source: dict[str, Any], raw_path: Path) -> str:
    raw_name = raw_path.stem.lower()
    for item in source.get("download_urls") or []:
        title = slugify(item.get("title") or "").lower()
        if title and title in raw_name:
            return item.get("chapter_id") or "unknown"
    return "unknown"


def _copy_self_curated_artifact(relative_path: str, source_root: Path) -> None:
    source = SELF_CURATED_ROOT / relative_path
    if not source.exists():
        return
    target_root = source_root / "artifacts" / "self_curated"
    if source.is_dir():
        target = target_root / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    else:
        target = target_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest approved data-structure course materials.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--download-approved", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = ingest(args.source_root, download_approved=args.download_approved, dry_run=args.dry_run)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
