from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from app.core.config import PROJECT_ROOT


DEFAULT_DATA_STRUCTURE_ROOT = PROJECT_ROOT / "data" / "seed_knowledge" / "data_structure"


def load_seed_quality_report(source_root: Path = DEFAULT_DATA_STRUCTURE_ROOT) -> dict[str, Any]:
    report_path = source_root / "eval" / "quality_report.json"
    manifest_path = source_root / "sources_manifest.yml"
    report = _read_json(report_path)
    manifest = _read_yaml(manifest_path)
    sources = manifest.get("sources", []) if isinstance(manifest, dict) else []
    return {
        "source_root": str(source_root),
        "report": report,
        "sources": [
            {
                "source_id": source.get("source_id"),
                "name": source.get("name"),
                "license": source.get("license"),
                "import_status": source.get("import_status"),
                "review_status": source.get("review_status"),
                "risk_level": source.get("risk_level"),
                "quality_score": source.get("quality_score"),
            }
            for source in sources
            if isinstance(source, dict)
        ],
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "graphrag_ready": False,
            "message": "quality_report.json 尚未生成，请先运行 scripts/evaluate_course_kb.py",
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}
