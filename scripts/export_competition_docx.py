"""Export competition master markdown to a single Word document."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "docs" / "22_比赛材料规划" / "智学工坊比赛材料合集.md"
OUT_DIR = ROOT / "docs" / "22_比赛材料规划" / "submission"
OUT_DOCX = OUT_DIR / "智学工坊系统说明书.docx"


def main() -> int:
    if not MASTER.is_file():
        print(f"Missing master doc: {MASTER}", file=sys.stderr)
        return 1

    pandoc = shutil.which("pandoc")
    if not pandoc:
        print("pandoc not found. Install: sudo apt install pandoc")
        print(f"Fallback: copy {MASTER} to submission/ and convert manually in Word.")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        fallback = OUT_DIR / "智学工坊系统说明书.md"
        fallback.write_text(MASTER.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Wrote fallback markdown: {fallback}")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        pandoc,
        str(MASTER),
        "-o",
        str(OUT_DOCX),
        "--from",
        "markdown",
        "--to",
        "docx",
        "--toc",
        "--toc-depth=3",
        "--resource-path",
        str(ROOT / "docs"),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    print(f"Exported: {OUT_DOCX}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
