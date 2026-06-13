"""Legacy compendium builder — DEPRECATED.

The single master document is now edited directly at:
  docs/22_比赛材料规划/智学工坊比赛材料合集.md

This script only validates that the master exists and runs validate_competition_doc.
Do NOT re-run the old 6-file merge; it would overwrite the detailed master.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "docs" / "22_比赛材料规划" / "智学工坊比赛材料合集.md"


def main() -> int:
    if not MASTER.is_file():
        print(f"ERROR: missing master doc {MASTER}", file=sys.stderr)
        return 1
    lines = len(MASTER.read_text(encoding="utf-8").splitlines())
    print(f"Master doc OK: {MASTER.relative_to(ROOT)} ({lines} lines)")
    print("NOTE: edit the master directly; old competition_sources merge is disabled.")
    validate = ROOT / "scripts" / "validate_competition_doc.py"
    if validate.is_file():
        return subprocess.call([sys.executable, str(validate)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
