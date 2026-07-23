from __future__ import annotations

import html
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.llm.adapters.base import BaseLLMProvider
from app.llm.schemas import ChatMessage
from app.skills.skill_loader import HtmlPptSkillLoader


@dataclass
class HtmlPptRenderResult:
    title: str
    html: str
    spec: dict[str, Any]
    safety_result: dict[str, Any]


class HtmlPptCoursewareService:
    """基于 lewislulu/html-ppt-skill 的多页 HTML 互动课件（course-module 模板）。"""

    def __init__(self, skill_loader: HtmlPptSkillLoader | None = None) -> None:
        self.skill = skill_loader or HtmlPptSkillLoader()

    async def build_spec_with_llm(
        self,
        *,
        topic: str,
        brief: dict[str, Any],
        requirement: str | None,
        llm: BaseLLMProvider,
    ) -> dict[str, Any]:
        outline = await self._build_outline_with_skill(
            topic=topic,
            brief=brief,
            requirement=requirement,
            llm=llm,
        )
        return outline

    async def _build_outline_with_skill(
        self,
        *,
        topic: str,
        brief: dict[str, Any],
        requirement: str | None,
        llm: BaseLLMProvider,
    ) -> dict[str, Any]:
        citations = brief.get("citations") or []
        context_lines = [
            f"- {self._clean_text(str(item.get('title') or '课程资料'))}: "
            f"{self._clean_text(str(item.get('quote') or ''))[:160]}"
            for item in citations[:8]
        ]
        user_prompt = (
            f"主题：{topic}\n"
            f"学生要求：{requirement or '适合初学者，分步骤讲解'}\n"
            f"画像提示：{brief.get('style_hint') or '循序渐进'}\n"
            "课程依据：\n"
            + ("\n".join(context_lines) or "- 数据结构基础概念")
            + "\n\n请输出 JSON（不要 markdown 围栏），结构：\n"
            '{"title":"...", "module_label":"...", "duration_hint":"...", "prereq":"...", '
            '"objectives":["..."], "slides":[{"type":"cover|objectives|concept|example|exercise|quiz|summary", '
            '"title":"...", "kicker":"...", "subtitle":"...", "lede":"...", "pills":["..."], '
            '"boxes":[{"title":"...","body":"..."}], "callout":"...", "code":"...", '
            '"tasks":["..."], "options":[{"label":"A","text":"...","correct":true,"explain":"..."}], '
            '"takeaways":[{"title":"...","body":"..."}], "next_hint":"..."}]}\n'
            "要求：严格输出 7 页，顺序固定为 cover、objectives、concept、example、exercise、quiz、summary，"
            "不得重复或跳过页型。每页只讲一个教学动作：概念页只保留 2 个要点；例子页只演示一个最小过程；"
            "练习页最多 3 个任务；自测页 3 个选项且仅 1 个 correct。不要输出“课程无关”“忽略定义”等凑数内容。"
            "封面 title 不超过 18 个中文字符，subtitle 不超过 52 个中文字符；标题必须是课程概念，"
            "不能把整段学生要求、生成指令或题目原样塞进标题。"
        )
        response = await llm.chat(
            [
                ChatMessage(role="system", content=self.skill.outline_system_prompt()),
                ChatMessage(role="user", content=user_prompt),
            ],
            temperature=0.5,
            max_tokens=4096,
        )
        parsed = self._parse_outline(response.content, topic=topic, brief=brief)
        parsed["skill"] = "html-ppt-skill"
        parsed["template"] = "course-module"
        parsed["citations"] = citations
        return parsed

    def render(self, spec: dict[str, Any]) -> HtmlPptRenderResult:
        normalized_spec = self._normalize_spec(spec)
        safety = self.validate_spec(normalized_spec)
        if not safety["passed"]:
            raise RuntimeError("课件 spec 未通过安全校验：" + ";".join(safety["issues"]))
        title = str(normalized_spec.get("title") or "互动课件")[:48]
        html_doc = self._render_course_module_deck(normalized_spec)
        html_safety = self.validate_html(html_doc)
        if not html_safety["passed"]:
            raise RuntimeError("课件 HTML 未通过安全校验：" + ";".join(html_safety["issues"]))
        return HtmlPptRenderResult(
            title=title,
            html=html_doc,
            spec=normalized_spec,
            safety_result={**safety, "html": html_safety},
        )

    def _render_course_module_deck(self, spec: dict[str, Any]) -> str:
        slides_spec = list(spec.get("slides") or [])
        if not slides_spec:
            slides_spec = self._fallback_spec(str(spec.get("topic") or "课程"), spec).get("slides") or []

        objectives = [self._clean_text(str(x)) for x in (spec.get("objectives") or [])[:6]]
        module_label = self._clean_text(str(spec.get("module_label") or "智学工坊 · 互动课件"))
        total = len(slides_spec)
        slide_html: list[str] = []

        for index, slide in enumerate(slides_spec):
            slide_type = str(slide.get("type") or "concept")
            active = " is-active" if index == 0 else ""
            sidebar = self._sidebar_html(
                module_label=module_label,
                objectives=objectives,
                current_index=self._objective_index(slide_type, index, total),
                page_no=index + 1,
                total=total,
                slide=slide,
            )
            body = self._slide_body_html(slide_type, slide, index + 1, total)
            if slide_type == "cover" or slide_type == "summary":
                slide_html.append(
                    f'<section class="slide full{active}" data-title="{html.escape(str(slide.get("title") or slide_type))}">{body}</section>'
                )
            else:
                slide_html.append(
                    f'<section class="slide{active}" data-title="{html.escape(str(slide.get("title") or slide_type))}">'
                    f"{sidebar}<div class=\"main\">{body}</div></section>"
                )

        styles = self.skill.bundled_styles()
        runtime = self.skill.bundled_runtime()
        deck_title = html.escape(str(spec.get("title") or "互动课件"))
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:;" />
  <title>{deck_title}</title>
  <style>{styles}
  .slide .h1,.slide .h2,.slide .lede,.slide .concept-box,.slide .callout{{overflow-wrap:anywhere;word-break:break-word;}}
  .slide .h1{{font-size:clamp(2.25rem,5.2vw,5rem);line-height:1.12;max-width:18ch;}}
  .slide .h2{{font-size:clamp(1.7rem,3vw,3rem);line-height:1.22;max-width:24ch;}}
  .slide .lede{{max-width:58ch;line-height:1.65;}}
  .slide.full{{overflow:hidden;}}
  </style>
</head>
<body class="tpl-course-module">
<div class="deck">
{''.join(slide_html)}
</div>
<script>{runtime}</script>
</body>
</html>"""

    def _sidebar_html(
        self,
        *,
        module_label: str,
        objectives: list[str],
        current_index: int,
        page_no: int,
        total: int,
        slide: dict[str, Any],
    ) -> str:
        obj_items: list[str] = []
        for idx, item in enumerate(objectives):
            state = "current" if idx == current_index else ("done" if idx < current_index else "")
            cls = f' class="{state}"' if state else ""
            obj_items.append(f"<li{cls}>{html.escape(item)}</li>")
        sidebar_hint = self._clean_text(str(slide.get("sidebar_hint") or ""))
        hint_block = (
            f'<h5>学习提示</h5><p class="dim" style="font-size:13px">{html.escape(sidebar_hint)}</p>'
            if sidebar_hint
            else ""
        )
        return (
            '<aside class="sidebar">'
            f'<div class="brand">{html.escape(module_label)}</div>'
            "<h5>学习目标</h5>"
            f'<ul class="obj-list">{"".join(obj_items)}</ul>'
            f"{hint_block}"
            "<h5>进度</h5>"
            f'<p class="dim" style="font-size:13px">第 {page_no} 页 / 共 {total} 页</p>'
            "</aside>"
        )

    def _slide_body_html(self, slide_type: str, slide: dict[str, Any], page_no: int, total: int) -> str:
        kicker = html.escape(self._clean_text(str(slide.get("kicker") or self._default_kicker(slide_type))))
        title = html.escape(self._clean_text(str(slide.get("title") or "")))
        if slide_type == "cover":
            subtitle = html.escape(self._clean_text(str(slide.get("subtitle") or slide.get("lede") or "")))
            pills = "".join(
                f'<span class="pill-academic">{html.escape(self._clean_text(str(p)))}</span>'
                for p in (slide.get("pills") or [])[:4]
            )
            return (
                f'<p class="kicker">{kicker}</p>'
                f'<h1 class="h1 mt-s">{title}</h1>'
                f'<p class="lede mt-l" style="max-width:62ch">{subtitle}</p>'
                f'<div class="row mt-l" style="gap:16px">{pills}</div>'
                f'<div class="deck-footer"><span>智学工坊 · html-ppt-skill</span>'
                f'<span class="slide-number" data-current="{page_no}" data-total="{total}"></span></div>'
            )
        if slide_type == "objectives":
            boxes = "".join(
                self._concept_box(str(box.get("title") or ""), str(box.get("body") or ""))
                for box in (slide.get("boxes") or [])[:4]
            ) or "".join(
                f'<div class="concept-box"><h4>{html.escape(obj)}</h4></div>'
                for obj in (slide.get("objectives") or [])[:4]
            )
            lede = html.escape(self._clean_text(str(slide.get("lede") or "完成本模块后，你将能够：")))
            return (
                f'<p class="kicker">{kicker}</p><h2 class="h2 mt-s">{title or "学习目标"}</h2>'
                f'<p class="lede mt-m">{lede}</p><div class="stack mt-l">{boxes}</div>'
            )
        if slide_type == "example":
            code_raw = self._clean_text(str(slide.get("code") or ""))
            code_block = (
                f'<div class="code mt-m"><pre style="margin:0">{html.escape(code_raw)}</pre></div>'
                if code_raw
                else ""
            )
            callout = self._callout_html(slide.get("callout"))
            lede = html.escape(self._clean_text(str(slide.get("lede") or "")))
            lede_block = f'<p class="lede mt-m">{lede}</p>' if lede else ""
            return (
                f'<p class="kicker">{kicker}</p><h2 class="h2 mt-s">{title}</h2>{lede_block}'
                f"{code_block}{callout}"
            )
        if slide_type == "exercise":
            tasks = slide.get("tasks") or []
            task_items = "".join(f"<li>{html.escape(self._clean_text(str(t)))}</li>" for t in tasks[:6])
            lede = html.escape(self._clean_text(str(slide.get("lede") or "")))
            return (
                f'<p class="kicker">{kicker}</p><h2 class="h2 mt-s">{title}</h2>'
                f'<p class="lede mt-m">{lede}</p>'
                f'<div class="exercise mt-l"><ol style="line-height:1.8;margin:10px 0 0">{task_items}</ol></div>'
            )
        if slide_type == "quiz":
            options_html: list[str] = []
            for opt in (slide.get("options") or [])[:4]:
                label = html.escape(str(opt.get("label") or "?"))
                text = html.escape(self._clean_text(str(opt.get("text") or "")))
                explain = html.escape(self._clean_text(str(opt.get("explain") or "")))
                correct = " correct" if opt.get("correct") else ""
                explain_block = (
                    f'<p class="dim" style="font-size:13px;margin:4px 0 0">{explain}</p>' if explain else ""
                )
                options_html.append(
                    f'<div class="mcq{correct}"><div class="letter">{label}</div>'
                    f"<div><b>{text}</b>{explain_block}</div></div>"
                )
            return (
                f'<p class="kicker">{kicker}</p><h2 class="h2 mt-s">{title or "自测"}</h2>'
                f'<div class="mt-l">{"".join(options_html)}</div>'
            )
        if slide_type == "summary":
            takeaways = "".join(
                self._concept_box(str(t.get("title") or ""), str(t.get("body") or ""))
                for t in (slide.get("takeaways") or [])[:4]
            )
            next_hint = self._callout_html(slide.get("next_hint"))
            return (
                f'<p class="kicker">{kicker}</p><h1 class="h1 mt-s">{title or "模块小结"}</h1>'
                f'<div class="grid g2 mt-l">{takeaways}</div>{next_hint}'
            )
        boxes = "".join(
            self._concept_box(str(box.get("title") or ""), str(box.get("body") or ""))
            for box in (slide.get("boxes") or [])[:4]
        )
        lede = html.escape(self._clean_text(str(slide.get("lede") or "")))
        callout = self._callout_html(slide.get("callout"))
        return (
            f'<p class="kicker">{kicker}</p><h2 class="h2 mt-s">{title}</h2>'
            f'<p class="lede mt-m">{lede}</p>{callout}<div class="grid g2 mt-l">{boxes}</div>'
        )

    @staticmethod
    def _concept_box(title: str, body: str) -> str:
        title_clean = html.escape(HtmlPptCoursewareService._clean_text(title))
        body_clean = html.escape(HtmlPptCoursewareService._clean_text(body))
        body_block = f'<p class="dim">{body_clean}</p>' if body_clean else ""
        return f'<div class="concept-box"><h4>{title_clean}</h4>{body_block}</div>'

    @staticmethod
    def _callout_html(text: Any) -> str:
        cleaned = HtmlPptCoursewareService._clean_text(str(text or ""))
        if not cleaned:
            return ""
        return f'<div class="callout mt-l"><b>要点</b> {html.escape(cleaned)}</div>'

    @staticmethod
    def _default_kicker(slide_type: str) -> str:
        mapping = {
            "cover": "智学工坊 · 互动课件",
            "objectives": "学习目标",
            "concept": "核心概念",
            "example": "例题讲解",
            "exercise": "练习",
            "quiz": "自测",
            "summary": "小结",
        }
        return mapping.get(slide_type, "课程模块")

    @staticmethod
    def _objective_index(slide_type: str, page_index: int, total: int) -> int:
        progress_map = {
            "cover": 0,
            "objectives": 0,
            "concept": 1,
            "example": 2,
            "exercise": 3,
            "quiz": 4,
            "summary": 5,
        }
        return min(progress_map.get(slide_type, page_index), max(total - 1, 0))

    def _parse_outline(self, raw: str, *, topic: str, brief: dict[str, Any]) -> dict[str, Any]:
        text = str(raw or "").strip()
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.I)
        if fenced:
            text = fenced.group(1).strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict) and data.get("slides"):
                data.setdefault("title", f"{topic} 互动课件")
                data.setdefault("module_label", f"智学工坊 · {topic}")
                data.setdefault("topic", topic)
                data["objectives"] = [
                    self._clean_text(str(x)) for x in (data.get("objectives") or [])[:6]
                ]
                return self._normalize_spec(data)
        except json.JSONDecodeError:
            pass
        return self._fallback_spec(topic, brief)

    def _normalize_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(spec)
        topic = self._limit(self._clean_text(str(normalized.get("topic") or "课程")), 24) or "课程"
        normalized["topic"] = topic
        normalized["title"] = self._compact_title(normalized.get("title"), topic, limit=24)
        normalized["module_label"] = self._limit(
            self._clean_text(str(normalized.get("module_label") or f"智学工坊 · {topic}")),
            30,
        )
        normalized["duration_hint"] = self._limit(self._clean_text(str(normalized.get("duration_hint") or "")), 16)
        normalized["prereq"] = self._limit(self._clean_text(str(normalized.get("prereq") or "")), 40)
        normalized["objectives"] = [
            self._limit(self._clean_text(str(value)), 40)
            for value in list(normalized.get("objectives") or [])[:5]
            if self._clean_text(str(value))
        ]
        fallback_spec = self._fallback_spec(topic, normalized)
        raw_slides = [slide for slide in list(normalized.get("slides") or []) if isinstance(slide, dict)]
        fallback_by_type = {str(slide.get("type")): slide for slide in fallback_spec["slides"]}
        supplied_by_type: dict[str, dict[str, Any]] = {}
        for slide in raw_slides:
            slide_type = str(slide.get("type") or "concept")
            supplied_by_type.setdefault(slide_type, slide)
        teaching_flow = ("cover", "objectives", "concept", "example", "exercise", "quiz", "summary")
        normalized["slides"] = [
            self._normalize_slide(supplied_by_type.get(slide_type) or fallback_by_type[slide_type], topic)
            for slide_type in teaching_flow
        ]
        return normalized

    def _normalize_slide(self, slide: dict[str, Any], topic: str) -> dict[str, Any]:
        item = deepcopy(slide)
        slide_type = str(item.get("type") or "concept")
        item["type"] = slide_type
        item["kicker"] = self._limit(self._clean_text(str(item.get("kicker") or self._default_kicker(slide_type))), 24)
        item["title"] = self._compact_title(item.get("title"), topic, limit=24 if slide_type in {"cover", "summary"} else 30)
        for field, limit in (("subtitle", 58), ("lede", 90), ("callout", 72), ("next_hint", 64), ("sidebar_hint", 50)):
            item[field] = self._limit(self._clean_text(str(item.get(field) or "")), limit)
        item["pills"] = [self._limit(self._clean_text(str(value)), 16) for value in list(item.get("pills") or [])[:3]]
        item["tasks"] = [self._limit(self._clean_text(str(value)), 46) for value in list(item.get("tasks") or [])[:3]]
        item["code"] = self._limit(self._clean_text(str(item.get("code") or "")), 420)
        box_limit = 3 if slide_type == "objectives" else 2
        item["boxes"] = [
            {"title": self._limit(self._clean_text(str(box.get("title") or "")), 20), "body": self._limit(self._clean_text(str(box.get("body") or "")), 56)}
            for box in list(item.get("boxes") or [])[:box_limit]
            if isinstance(box, dict)
        ]
        item["takeaways"] = [
            {"title": self._limit(self._clean_text(str(box.get("title") or "")), 24), "body": self._limit(self._clean_text(str(box.get("body") or "")), 60)}
            for box in list(item.get("takeaways") or [])[:4]
            if isinstance(box, dict)
        ]
        item["options"] = [
            {
                "label": self._limit(self._clean_text(str(option.get("label") or "?")), 3),
                "text": self._limit(self._clean_text(str(option.get("text") or "")), 48),
                "correct": bool(option.get("correct")),
                "explain": self._limit(self._clean_text(str(option.get("explain") or "")), 48),
            }
            for option in list(item.get("options") or [])[:4]
            if isinstance(option, dict)
        ]
        return item

    def _compact_title(self, value: Any, topic: str, *, limit: int) -> str:
        title = self._clean_text(str(value or ""))
        instruction_markers = ("：", ":", "；", ";", "，", ",", "请", "先", "最后", "面向")
        if not title or len(title) > limit or any(marker in title for marker in instruction_markers):
            title = topic
        return self._limit(title, limit)

    @staticmethod
    def _limit(value: str, limit: int) -> str:
        return value[:limit].rstrip("，。；：、 ")

    def _fallback_spec(self, topic: str, brief: dict[str, Any]) -> dict[str, Any]:
        citations = brief.get("citations") or []
        points = [
            self._clean_text(str(item.get("quote") or item.get("title") or f"{topic} 关键点"))[:100]
            for item in citations[:6]
        ] or [
            f"理解 {topic} 的定义与术语",
            f"掌握 {topic} 的基本性质",
            f"能举例说明 {topic} 的应用",
            "完成自测并核对理解",
        ]
        return {
            "title": f"{topic} 互动课件",
            "topic": topic,
            "module_label": f"智学工坊 · {topic}",
            "duration_hint": "~15 min",
            "prereq": "课程前置章节",
            "objectives": points[:4],
            "slides": [
                {
                    "type": "cover",
                    "kicker": "智学工坊 · 互动课件",
                    "title": topic,
                    "subtitle": f"围绕「{topic}」的分步互动学习模块，基于课程资料整理。",
                    "pills": ["~15 min", "html-ppt-skill", "course-module"],
                },
                {
                    "type": "objectives",
                    "title": "本模块结束后，你将能够…",
                    "boxes": [{"title": f"① {p}", "body": ""} for p in points[:3]],
                },
                {
                    "type": "concept",
                    "title": "核心概念",
                    "lede": points[0] if points else f"{topic} 的基本定义与直观理解。",
                    "boxes": [
                        {"title": "定义", "body": points[0] if points else ""},
                        {"title": "关键性质", "body": points[1] if len(points) > 1 else ""},
                    ],
                    "callout": "结合课程资料理解，不要只背名词。",
                },
                {
                    "type": "example",
                    "title": "例题 / 直观例子",
                    "lede": "用一个小例子把概念和操作对应起来。",
                    "callout": points[2] if len(points) > 2 else f"尝试用一句话解释 {topic}。",
                },
                {
                    "type": "exercise",
                    "title": "动手练习",
                    "lede": "按步骤完成以下任务：",
                    "tasks": [
                        f"用一句话解释 {topic}",
                        "举一个课程中的具体例子",
                        "指出一个常见易错点",
                    ],
                },
                {
                    "type": "quiz",
                    "title": "哪一项描述最准确？",
                    "options": [
                        {"label": "A", "text": points[0][:60], "correct": True, "explain": "与课程资料一致。"},
                        {"label": "B", "text": "可以忽略定义直接做题", "correct": False, "explain": "定义是后续推导的基础。"},
                        {"label": "C", "text": f"{topic} 与课程无关", "correct": False, "explain": "本题围绕当前章节。"},
                    ],
                },
                {
                    "type": "summary",
                    "title": "你已经掌握…",
                    "takeaways": [{"title": f"✓ {p[:24]}", "body": ""} for p in points[:3]],
                    "next_hint": "建议回到 Wiki 或练习页继续巩固。",
                },
            ],
        }

    @staticmethod
    def _clean_text(value: str) -> str:
        text = re.sub(r"^#{1,6}\s*", "", value.strip())
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def validate_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        issues: list[str] = []
        raw = json.dumps(spec, ensure_ascii=False).lower()
        banned = ["fetch(", "xmlhttprequest", "websocket", "document.cookie"]
        for item in banned:
            if item in raw:
                issues.append(f"包含禁止内容: {item}")
        if "http://" in raw or "https://" in raw:
            issues.append("spec 中包含外链")
        if len(raw) > 120000:
            issues.append("课件 spec 过大")
        if not spec.get("slides"):
            issues.append("缺少 slides")
        return {"passed": not issues, "issues": issues, "risk_level": "low" if not issues else "high"}

    def validate_html(self, html_doc: str) -> dict[str, Any]:
        issues: list[str] = []
        lower = html_doc.lower()
        banned = ["fetch(", "xmlhttprequest", "websocket", "document.cookie"]
        for item in banned:
            if item in lower:
                issues.append(f"HTML 包含禁止内容: {item}")
        if re.search(r"""<(script|link)[^>]+(?:src|href)\s*=\s*['"]https?://""", lower):
            issues.append("HTML 包含外链脚本或样式")
        if len(html_doc) > 600000:
            issues.append("课件 HTML 过大")
        if "<section class=\"slide" not in html_doc and "<section class='slide" not in html_doc:
            issues.append("未找到 html-ppt slide 结构")
        return {"passed": not issues, "issues": issues, "risk_level": "low" if not issues else "high"}
