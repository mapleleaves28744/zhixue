from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import Any

import bleach


@dataclass
class CoursewareRenderResult:
    title: str
    html: str
    spec: dict[str, Any]
    safety_result: dict[str, Any]


class CoursewareService:
    """模板化互动课件生成：LLM 只产 JSON spec，服务端模板渲染。"""

    def build_spec(self, *, topic: str, interaction_type: str, brief: dict[str, Any]) -> dict[str, Any]:
        citations = brief.get("citations") or []
        steps = []
        for idx, citation in enumerate(citations[:5], start=1):
            quote = str(citation.get("quote") or "")[:160]
            steps.append({
                "title": f"步骤 {idx}",
                "body": quote or f"围绕 {topic} 的关键步骤 {idx}",
                "hint": "结合课程资料理解此步骤，并尝试解释原因。",
            })
        if not steps:
            steps = [
                {"title": "概念引入", "body": f"理解 {topic} 的定义和适用场景。", "hint": "先用一句话解释概念。"},
                {"title": "过程拆解", "body": f"把 {topic} 拆成输入、处理、输出。", "hint": "关注每一步状态变化。"},
                {"title": "自测", "body": "完成一道小题验证理解。", "hint": "说出容易出错的边界条件。"},
            ]
        return {
            "version": "1.0",
            "topic": topic,
            "interaction_type": interaction_type,
            "title": f"{topic} 互动课件",
            "steps": steps,
            "citations": citations,
        }

    def render(self, spec: dict[str, Any]) -> CoursewareRenderResult:
        safety = self.validate_spec(spec)
        if not safety["passed"]:
            raise RuntimeError("课件 spec 未通过安全校验：" + ";".join(safety["issues"]))
        title = str(spec.get("title") or "互动课件")[:120]
        steps = list(spec.get("steps") or [])[:10]
        step_items = []
        for i, step in enumerate(steps):
            step_items.append(
                f"""
                <section class="step-card" data-step="{i}">
                  <h2>{html.escape(str(step.get('title') or f'步骤{i+1}'))}</h2>
                  <p>{html.escape(str(step.get('body') or ''))}</p>
                  <button type="button" onclick="toggleHint({i})">显示/隐藏提示</button>
                  <p id="hint-{i}" class="hint" hidden>{html.escape(str(step.get('hint') or ''))}</p>
                </section>
                """
            )
        html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; media-src data:;" />
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin:0; font-family: system-ui, sans-serif; background:#fff8f0; color:#2b2118; }}
    main {{ max-width: 960px; margin: 0 auto; padding: 32px; }}
    .hero {{ border-radius: 28px; padding: 28px; background: linear-gradient(135deg, #fff, #ffe8c7); box-shadow: 0 18px 50px rgba(90,65,30,.12); }}
    .step-card {{ margin-top: 18px; padding: 22px; border-radius: 22px; background: #fff; border: 1px solid #f5d7aa; }}
    button {{ border:0; border-radius: 999px; padding: 10px 16px; background:#8a5a00; color:white; cursor:pointer; }}
    .hint {{ color:#7b4b00; background:#fff2d9; padding:12px; border-radius:14px; }}
  </style>
</head>
<body>
  <main>
    <div class="hero">
      <h1>{html.escape(title)}</h1>
      <p>由智学工坊基于课程资料生成的安全模板化互动课件。</p>
    </div>
    {''.join(step_items)}
  </main>
  <script>
    function toggleHint(i) {{
      const el = document.getElementById('hint-' + i);
      if (el) el.hidden = !el.hidden;
    }}
  </script>
</body>
</html>"""
        cleaned = bleach.clean(
            html_doc,
            tags=["html", "head", "body", "meta", "title", "style", "main", "div", "h1", "h2", "p", "section", "button", "script"],
            attributes={"*": ["class", "id", "data-step", "hidden", "type", "onclick", "lang", "charset", "name", "content", "http-equiv"]},
            strip=False,
        )
        return CoursewareRenderResult(title=title, html=cleaned, spec=spec, safety_result=safety)

    def validate_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        issues = []
        raw = json.dumps(spec, ensure_ascii=False).lower()
        banned = ["fetch(", "xmlhttprequest", "websocket", "localstorage", "document.cookie", "<script", "http://", "https://"]
        for item in banned:
            if item in raw:
                issues.append(f"包含禁止内容: {item}")
        if len(raw) > 50000:
            issues.append("课件 spec 过大")
        return {"passed": not issues, "issues": issues, "risk_level": "low" if not issues else "high"}
