from __future__ import annotations

import base64
import re
import zlib


def extract_mermaid_code(content: str, *, fallback_root: str = "知识结构") -> str:
    match = re.search(r"```mermaid\s*\n(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    trimmed = content.strip()
    for prefix in ("mindmap", "flowchart TD", "flowchart LR", "sequenceDiagram", "classDiagram", "erDiagram"):
        if prefix in trimmed:
            return trimmed[trimmed.index(prefix) :].strip()
    if trimmed.startswith("mindmap"):
        return trimmed
    return f"mindmap\n  root(({fallback_root[:40]}))\n    AI推断内容\n      建议核对资料"


def is_mermaid_code(content: str) -> bool:
    trimmed = str(content or "").strip()
    return bool(
        re.match(
            r"^(mindmap|flowchart\s+(TD|LR|BT|RL)|sequenceDiagram|classDiagram|erDiagram)\b",
            trimmed,
        )
    )


def kroki_encode(graph: str) -> str:
    compressed = zlib.compress(graph.encode("utf-8"), 9)
    return base64.urlsafe_b64encode(compressed).decode("ascii")


def repair_mermaid_content(content: str, *, root_label: str = "知识结构") -> str:
    """将 LLM 混合格式修复为可渲染的 Mermaid。"""
    text = re.sub(r"<br\s*/?>", " ", str(content or ""), flags=re.I).strip()
    if not text:
        return f"mindmap\n  root(({root_label[:40]}))"

    fenced = re.search(r"```mermaid\s*\n(.*?)```", text, re.DOTALL | re.I)
    if fenced:
        text = fenced.group(1).strip()

    if is_mermaid_code(text) and "\n" in text:
        first = text.split("\n", 1)[0].strip()
        if first in {"mindmap"} or first.startswith("flowchart"):
            return _sanitize_mermaid_labels(text)

    single_root = re.match(r"^mindmap\s+root\(\((.+)\)\)\s*$", text, re.I)
    if single_root:
        root = single_root.group(1).strip()[:40]
        return f"mindmap\n  root(({root}))"

    lines = text.split("\n")
    if lines and "mindmap" in lines[0].lower():
        root_match = re.search(r"root\(\((.+?)\)\)", lines[0], re.I)
        root = (root_match.group(1) if root_match else root_label).strip()[:40]
        branches: list[str] = []
        current_section: str | None = None
        for raw in lines[1:]:
            line = raw.strip()
            if not line:
                continue
            section = re.match(r"^\*\*(.+?)\*\*$", line)
            if section:
                current_section = section.group(1).strip()[:20]
                branches.append(f"    {current_section}")
                continue
            cleaned = re.sub(r"[*#:`\"“”]", "", line).strip()[:32]
            if not cleaned:
                continue
            branches.append(f"      {cleaned}" if current_section else f"    {cleaned}")
        if branches:
            return f"mindmap\n  root(({root}))\n" + "\n".join(branches[:14])
        return f"mindmap\n  root(({root}))\n    核心概念"

    return extract_mermaid_code(text, fallback_root=root_label[:40])


def _sanitize_mermaid_labels(code: str) -> str:
    return "\n".join(
        line.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
        for line in code.split("\n")
    ).strip()
