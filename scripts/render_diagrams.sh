#!/usr/bin/env bash
# Render docs/assets/diagrams/*.mmd to PNG via @mermaid-js/mermaid-cli (mmdc).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIAG="$ROOT/docs/assets/diagrams"
cd "$DIAG"

if ! command -v mmdc >/dev/null 2>&1; then
  echo "mmdc not found. Install: npm install -g @mermaid-js/mermaid-cli"
  echo "Skipping PNG render; .mmd sources remain usable in Markdown."
  exit 0
fi

for f in *.mmd; do
  out="${f%.mmd}.png"
  echo "Rendering $f -> $out"
  mmdc -i "$f" -o "$out" -b transparent -w 1200
done
echo "Done: $(ls -1 *.png 2>/dev/null | wc -l) PNG files"
