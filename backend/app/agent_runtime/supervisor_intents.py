"""Supervisor 意图识别：避免纯子串关键词误路由工具。"""

from __future__ import annotations

import re
from dataclasses import dataclass


def _has_non_negated_marker(goal: str, markers: tuple[str, ...]) -> bool:
    """Match an intent marker unless the user explicitly excludes that output."""
    lowered = goal.lower()
    negations = ("不要", "不生成", "不用", "无需", "不需要", "别")
    for marker in markers:
        start = 0
        normalized_marker = marker.lower()
        while (index := lowered.find(normalized_marker, start)) >= 0:
            prefix = goal[max(0, index - 24):index].replace(" ", "")
            if not any(negation in prefix for negation in negations):
                return True
            start = index + len(normalized_marker)
    return False


def transcribe_intent(goal: str) -> bool:
    if any(k in goal for k in ("语音识别", "识别语音", "音频转文字", "语音转文字")):
        return True
    return "识别" in goal and "语音" in goal and any(k in goal for k in ("转文字", "转文本", "转成文字", "听写"))


def speech_intent(goal: str) -> bool:
    if transcribe_intent(goal):
        return False
    speech_keys = (
        "文字转语音",
        "合成语音",
        "语音讲解",
        "生成语音",
        "讲解语音",
        "TTS",
        "朗读",
        "播讲",
        "听讲解",
        "读出来",
        "念出来",
    )
    if any(k in goal for k in speech_keys):
        return True
    return "语音" in goal and "视频" not in goal


def video_intent(goal: str) -> bool:
    if presentation_intent(goal):
        return False
    video_keys = (
        "讲解视频",
        "短视频",
        "动画讲解",
        "生成动画",
        "可视化讲一遍",
        "视频讲解",
        "生成视频",
    )
    if any(k in goal for k in video_keys):
        return True
    return "视频" in goal and not speech_intent(goal)


def immersive_classroom_intent(goal: str) -> bool:
    return ("一键" in goal and "课程" in goal) or any(
        key in goal
        for key in (
            "沉浸课堂",
            "沉浸式课堂",
            "一键课程",
            "一键生成课程",
            "互动课堂",
            "交互式课堂",
        )
    )


def storyboard_intent(goal: str) -> bool:
    return any(k in goal for k in ("分镜", "分镜页", "storyboard", "视频分镜"))


def courseware_intent(goal: str) -> bool:
    lowered = goal.lower()
    explicit_keys = (
        "互动课件",
        "交互课件",
        "可交互",
        "拖拽",
        "仿真",
        "演示页面",
        "幻灯片",
        "网页ppt",
        "网页幻灯片",
        "html ppt",
        "html-ppt",
        "翻页课件",
        "html课件",
        "演示文稿",
        "课件",
    )
    if _has_non_negated_marker(goal, explicit_keys):
        return True
    latin_keys = ("ppt", "slides", "slide", "deck", "keynote")
    return _has_non_negated_marker(lowered, latin_keys)


def presentation_intent(goal: str) -> bool:
    """PPT/幻灯片/课件类演示（非视频、非纯 Markdown 讲解）。"""
    return courseware_intent(goal)


def knowledge_card_intent(goal: str) -> bool:
    return "知识卡片" in goal


def image_intent(goal: str) -> bool:
    if knowledge_card_intent(goal):
        return True
    return any(
        k in goal
        for k in (
            "插图",
            "配图",
            "概念图",
            "封面图",
            "教学图片",
            "教学插图",
            "画一张图片",
            "生成一张",
            "出一张图",
        )
    )


def diagram_intent(goal: str) -> bool:
    return any(k in goal for k in ("图解", "流程图", "架构图", "示意图", "画一张", "画一个"))


def mindmap_intent(goal: str) -> bool:
    return any(k in goal for k in ("思维导图", "知识图谱", "知识结构", "梳理一下脉络", "整体框架"))


def quiz_intent(goal: str) -> bool:
    return any(k in goal for k in ("练习题", "生成练习", "生成一组练习", "配套练习", "出题", "测试题", "几道"))


def learning_path_intent(goal: str) -> bool:
    return any(k in goal for k in ("学习计划", "学习路径", "复习计划", "安排一周", "安排三天", "制定一个"))


def explanation_resource_intent(goal: str) -> bool:
    if speech_intent(goal) or video_intent(goal) or presentation_intent(goal):
        return False
    if knowledge_card_intent(goal) or image_intent(goal) or mindmap_intent(goal) or diagram_intent(goal):
        return False
    if any(k in goal for k in ("讲解资料", "配套讲解", "生成讲解", "个性化讲解")):
        return True
    return "生成一份" in goal and any(k in goal for k in ("讲解", "说明", "资源"))


def qa_intent(goal: str) -> bool:
    if presentation_intent(goal):
        return False
    if any(
        k in goal
        for k in ("生成", "制作", "出一张", "画一", "资源", "语音", "视频", "练习", "计划", "课件", "幻灯片")
    ):
        return False
    return any(
        k in goal
        for k in ("什么是", "是什么", "讲解一下", "解释一下", "帮我理解", "什么意思", "为什么", "如何")
    )


def search_explicit_intent(goal: str) -> bool:
    return any(k in goal for k in ("检索", "课程资料", "课程知识库", "基于资料", "基于课程", "引用", "来源"))


def web_search_intent(goal: str) -> bool:
    if search_explicit_intent(goal):
        return False
    if any(k in goal for k in ("课程资料", "课程知识库", "wiki", "Wiki", "基于资料")):
        return False
    markers = (
        "联网搜索",
        "网上搜索",
        "互联网搜索",
        "实时搜索",
        "搜索引擎",
        "查一下网上",
        "联网查",
        "网上查",
        "在线搜索",
        "搜索网络",
        "web search",
        "最新新闻",
        "最新消息",
        "最新动态",
        "帮我搜",
        "帮我查一下",
        "百度",
        "谷歌",
        "google",
        "bing",
    )
    if any(k in goal for k in markers):
        return True
    if "搜索" in goal and any(k in goal for k in ("网上", "互联网", "联网", "在线", "实时")):
        return True
    if any(k in goal for k in ("有哪些新特性", "有什么新功能", "新特性", "最新版本", "更新了什么")):
        return True
    return False


def search_only_intent(goal: str) -> bool:
    has_search_action = any(k in goal for k in ("检索", "搜索", "查找", "找出"))
    has_answer_action = any(
        k in goal
        for k in (
            "解释",
            "讲解",
            "回答",
            "什么是",
            "是什么",
            "为什么",
            "如何",
            "怎么",
            "帮我理解",
            "给出引用",
            "引用回答",
        )
    )
    return has_search_action and not has_answer_action


def should_prepare_speech_script(goal: str) -> bool:
    return any(k in goal for k in ("讲解", "解释", "说明", "队列", "栈", "树", "图", "算法", "结构"))


def is_profile_update_only_goal(goal: str) -> bool:
    profile_requests = (
        "请记住",
        "记住我的学习偏好",
        "更新我的画像",
        "记录我的学习偏好",
        "保存我的学习偏好",
    )
    explicit_other_tasks = (
        "学习计划",
        "学习路径",
        "复习计划",
        "安排三天",
        "安排一周",
        "生成练习",
        "练习题",
        "生成讲解",
        "讲解一下",
        "解释一下",
        "检索资料",
        "课程资料",
        "给出引用",
        "推荐下一步",
        "学习诊断",
        "ppt",
        "幻灯片",
        "课件",
        "视频",
    )
    return any(item in goal for item in profile_requests) and not any(
        item in goal for item in explicit_other_tasks
    )


def should_intent_first_route(goal: str) -> bool:
    """意图足够明确时，首轮规划不交给 LLM 自由发挥。"""
    if is_profile_update_only_goal(goal):
        return False
    if len(required_deliverables(goal)) >= 2:
        return True
    return any(
        (
            presentation_intent(goal),
            immersive_classroom_intent(goal),
            video_intent(goal),
            speech_intent(goal),
            transcribe_intent(goal),
            quiz_intent(goal),
            learning_path_intent(goal),
            knowledge_card_intent(goal),
            mindmap_intent(goal),
            diagram_intent(goal) and not image_intent(goal),
            image_intent(goal) and not diagram_intent(goal),
            explanation_resource_intent(goal),
            web_search_intent(goal),
        )
    )


_GOAL_CONNECTORS = (
    "以及",
    "还有",
    "同时",
    "并且",
    "然后再",
    "再帮",
    "再给我",
    "接着",
    "然后",
)
_GOAL_SEPARATORS = ("，", ",", "、", ";", "；")
_MULTI_INTENT_AND = re.compile(
    r"和(?=[^和]*(?:ppt|slides|slide|deck|思维导图|流程图|图解|视频|课件|幻灯片|插图|练习|导图|图谱|沉浸|分镜|语音|讲解资料|学习路径|学习计划))",
    re.IGNORECASE,
)
_TOPIC_NOISE_TERMS = (
    "生成",
    "制作",
    "创建",
    "帮我",
    "请",
    "给",
    "做",
    "画",
    "再画",
    "再生成",
    "再做",
    "一份",
    "一个",
    "一张",
    "一幅",
    "一套",
    "关于",
    "的",
    "讲解",
    "互动课件",
    "交互课件",
    "网页幻灯片",
    "网页ppt",
    "html ppt",
    "html-ppt",
    "幻灯片",
    "演示文稿",
    "翻页课件",
    "思维导图",
    "知识图谱",
    "知识结构",
    "流程图",
    "架构图",
    "示意图",
    "图解",
    "插图",
    "配图",
    "概念图",
    "教学图片",
    "教学插图",
    "知识卡片",
    "讲解视频",
    "短视频",
    "动画讲解",
    "视频讲解",
    "沉浸课堂",
    "互动课堂",
    "练习题",
    "配套练习",
    "学习计划",
    "学习路径",
    "个性化讲解",
    "讲解资料",
    "ppt",
    "slides",
    "slide",
    "deck",
    "keynote",
    "storyboard",
    "分镜",
)


@dataclass(frozen=True)
class GoalIntent:
    segment: str
    topic: str
    tools: tuple[str, ...]


def split_goal_segments(goal: str) -> list[str]:
    text = str(goal or "").strip()
    if not text:
        return []
    for connector in _GOAL_CONNECTORS:
        text = text.replace(connector, "|")
    text = _MULTI_INTENT_AND.sub("|", text)
    for separator in _GOAL_SEPARATORS:
        text = text.replace(separator, "|")
    parts = [part.strip() for part in text.split("|") if part.strip()]
    return parts if len(parts) > 1 else [text]


def extract_topic_from_segment(segment: str) -> str:
    cleaned = str(segment or "").strip()
    lowered = cleaned.lower()
    for _ in range(3):
        for term in _TOPIC_NOISE_TERMS:
            cleaned = cleaned.replace(term, " ")
            if term.isascii():
                lowered = lowered.replace(term.lower(), " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        lowered = re.sub(r"\s+", " ", lowered).strip()
    cleaned = cleaned.strip("，。、；： ")
    # 资源主题通常位于首句，后续句子是展示方式、受众或练习要求，不能作为主题传给生成器。
    cleaned = re.split(r"[。；;]", cleaned, maxsplit=1)[0].strip("，、： ")
    # 去掉残留前缀助词
    cleaned = re.sub(r"^(再|又|还|先|帮|给|做|画|来)\s*", "", cleaned).strip()
    if cleaned:
        return cleaned
    fallback = re.sub(r"(生成|制作|创建|帮我|请|给|一份|一个|一张|关于|的)", " ", segment)
    fallback = re.sub(r"\s+", " ", fallback).strip("，。、；： ")
    return fallback or str(segment).strip()


def parse_goal_intents(goal: str, *, is_profile_update_only: bool = False) -> list[GoalIntent]:
    if is_profile_update_only or is_profile_update_only_goal(goal):
        return []
    segments = split_goal_segments(goal)
    intents: list[GoalIntent] = []
    for segment in segments:
        tools = tuple(
            name
            for name in required_deliverables(segment)
            if name in _DELIVERABLE_TOOL_NAMES
        )
        if not tools:
            planned = plan_required_tools(segment, is_profile_update_only=False)
            tools = tuple(name for name in planned if name in _DELIVERABLE_TOOL_NAMES)
        if not tools:
            continue
        intents.append(
            GoalIntent(
                segment=segment,
                topic=extract_topic_from_segment(segment),
                tools=tools,
            )
        )
    if intents:
        return intents
    deliverables = required_deliverables(goal)
    if not deliverables:
        return []
    topic = extract_topic_from_segment(goal)
    return [GoalIntent(segment=goal, topic=topic, tools=tuple(deliverables))]


def parse_tool_topics(goal: str, *, is_profile_update_only: bool = False) -> dict[str, str]:
    """多意图场景下，为每个交付物工具提取独立子主题。"""
    intents = parse_goal_intents(goal, is_profile_update_only=is_profile_update_only)
    mapping: dict[str, str] = {}
    for intent in intents:
        for tool in intent.tools:
            if tool not in mapping:
                mapping[tool] = intent.topic
    for tool in required_deliverables(goal):
        mapping.setdefault(tool, extract_topic_from_segment(goal))
    return mapping


_DELIVERABLE_TOOL_NAMES = frozenset(
    {
        "transcribe_audio",
        "synthesize_speech",
        "generate_immersive_classroom",
        "generate_lesson_video",
        "generate_interactive_courseware",
        "generate_educational_image",
        "generate_diagram",
        "generate_mindmap",
        "generate_quiz",
        "generate_learning_path",
        "generate_explanation",
        "apply_evolution_strategy",
    }
)


def plan_required_tools(goal: str, *, is_profile_update_only: bool) -> list[str]:
    if is_profile_update_only or is_profile_update_only_goal(goal):
        return ["update_profile_from_dialogue"]

    tools: list[str] = []

    if transcribe_intent(goal):
        tools.append("transcribe_audio")
    if speech_intent(goal):
        if should_prepare_speech_script(goal):
            tools.append("generate_explanation")
        tools.append("synthesize_speech")
    if immersive_classroom_intent(goal):
        tools.append("generate_immersive_classroom")
    elif video_intent(goal):
        tools.append("generate_lesson_video")
    if storyboard_intent(goal):
        tools.append("generate_storyboard_html")
    if courseware_intent(goal):
        tools.append("generate_interactive_courseware")
        # PPT/课件与视频/分镜互斥，避免「讲解 ppt」误走视频链路
        tools = [
            name
            for name in tools
            if name
            not in (
                "generate_lesson_video",
                "generate_immersive_classroom",
                "generate_storyboard_html",
                "generate_explanation",
            )
        ]
    if diagram_intent(goal) and not image_intent(goal):
        tools.append("generate_diagram")
    elif image_intent(goal):
        tools.append("generate_educational_image")
    if mindmap_intent(goal):
        tools.append("generate_mindmap")
    if learning_path_intent(goal):
        tools.append("generate_learning_path")
    if quiz_intent(goal):
        tools.append("generate_quiz")
    if any(k in goal for k in ("薄弱点", "错误模式", "学习诊断")):
        tools.append("analyze_learning_diagnosis")
    if any(
        k in goal
        for k in (
            "推荐下一步",
            "推荐学习内容",
            "刷新推荐",
            "根据画像推送",
            "主动推荐",
            "诊断后推荐",
            "推荐资源",
        )
    ):
        tools.append("refresh_recommendations")
    if any(k in goal for k in ("解析资料", "解析文档", "处理上传", "解析这份")):
        tools.append("parse_uploaded_document")
    if any(k in goal for k in ("来源、幻觉和风险审查", "审查学习产物", "审核学习产物")):
        tools.append("review_artifacts")
    if any(k in goal for k in ("审核多模态", "审查插图", "审查视频", "审查课件", "审查产物安全", "multimodal review")):
        tools.append("review_multimodal_asset")
    if any(k in goal for k in ("应用最新的一条自进化策略", "应用自进化策略")):
        tools.append("apply_evolution_strategy")
    if any(k in goal for k in ("重建画像", "重新整理我的学习画像", "根据学习记录重建画像")):
        tools.append("rebuild_profile")
    if any(k in goal for k in ("长期学习记忆", "反思最近学习", "沉淀有价值")):
        tools.append("reflect_learning_memory")
    if explanation_resource_intent(goal) and "generate_explanation" not in tools:
        tools.append("generate_explanation")
    if knowledge_card_intent(goal) and "generate_educational_image" not in tools:
        tools = [name for name in tools if name != "generate_explanation"]
        tools.append("generate_educational_image")
    if any(
        k in goal
        for k in (
            "记住我的学习偏好",
            "更新我的画像",
            "我的学习偏好",
            "我更喜欢",
            "我喜欢",
            "我的专业",
            "我的目标",
            "我是",
            "我目前",
            "比较薄弱",
        )
    ) and not tools:
        tools.append("update_profile_from_dialogue")
    if web_search_intent(goal) and "search_web" not in tools:
        tools.insert(0, "search_web")
    elif (search_explicit_intent(goal) or search_only_intent(goal)) and not tools:
        tools.append("search_course_knowledge" if search_only_intent(goal) else "answer_course_question")
    elif not web_search_intent(goal) and search_explicit_intent(goal) and "search_course_knowledge" not in tools:
        # 生成资源、诊断或推荐等多意图任务仍需先取得课程证据；纯问答则由
        # answer_course_question 内部完成检索与一次生成，避免重复工具调用。
        tools.insert(0, "search_course_knowledge")
    if not tools and qa_intent(goal):
        tools.append("answer_course_question")

    return _dedupe(tools)


def required_deliverables(goal: str) -> list[str]:
    deliverables: list[str] = []
    if transcribe_intent(goal):
        deliverables.append("transcribe_audio")
    if speech_intent(goal):
        deliverables.append("synthesize_speech")
    if immersive_classroom_intent(goal):
        deliverables.append("generate_immersive_classroom")
    elif video_intent(goal):
        deliverables.append("generate_lesson_video")
    if courseware_intent(goal):
        deliverables.append("generate_interactive_courseware")
    if knowledge_card_intent(goal):
        deliverables.append("generate_educational_image")
    elif image_intent(goal) and not diagram_intent(goal):
        deliverables.append("generate_educational_image")
    elif diagram_intent(goal):
        deliverables.append("generate_diagram")
    if mindmap_intent(goal):
        deliverables.append("generate_mindmap")
    if quiz_intent(goal):
        deliverables.append("generate_quiz")
    if learning_path_intent(goal):
        deliverables.append("generate_learning_path")
    if explanation_resource_intent(goal):
        deliverables.append("generate_explanation")
    if any(k in goal for k in ("应用最新的一条自进化策略", "应用自进化策略")):
        deliverables.append("apply_evolution_strategy")
    return _dedupe(deliverables)


def deliverable_label(tool_name: str) -> str:
    labels = {
        "synthesize_speech": "语音合成",
        "generate_lesson_video": "讲解视频",
        "generate_immersive_classroom": "沉浸课堂与配音字幕讲解视频",
        "generate_educational_image": "教学插图",
        "generate_diagram": "图解/流程图",
        "generate_interactive_courseware": "互动课件",
        "generate_mindmap": "思维导图",
        "generate_quiz": "练习题",
        "generate_learning_path": "学习路径",
        "generate_explanation": "讲解资源",
        "transcribe_audio": "语音识别",
        "apply_evolution_strategy": "自进化策略应用",
    }
    return labels.get(tool_name, tool_name)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
