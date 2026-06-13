"""Supervisor 意图识别：避免纯子串关键词误路由工具。"""

from __future__ import annotations


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
    return any(k in goal for k in ("互动课件", "交互课件", "可交互", "拖拽", "仿真", "演示页面"))


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
    if speech_intent(goal) or video_intent(goal):
        return False
    if knowledge_card_intent(goal) or image_intent(goal) or mindmap_intent(goal) or diagram_intent(goal):
        return False
    if any(k in goal for k in ("讲解资料", "配套讲解", "生成讲解", "个性化讲解")):
        return True
    return "生成一份" in goal and any(k in goal for k in ("讲解", "说明", "资源"))


def qa_intent(goal: str) -> bool:
    if any(k in goal for k in ("生成", "制作", "出一张", "画一", "资源", "语音", "视频", "练习", "计划")):
        return False
    return any(
        k in goal
        for k in ("什么是", "是什么", "讲解一下", "解释一下", "帮我理解", "什么意思", "为什么", "如何")
    )


def search_explicit_intent(goal: str) -> bool:
    return any(k in goal for k in ("检索", "课程资料", "课程知识库", "基于资料", "基于课程", "引用", "来源"))


def should_prepare_speech_script(goal: str) -> bool:
    return any(k in goal for k in ("讲解", "解释", "说明", "队列", "栈", "树", "图", "算法", "结构"))


def plan_required_tools(goal: str, *, is_profile_update_only: bool) -> list[str]:
    if is_profile_update_only:
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
    if search_explicit_intent(goal) and "search_course_knowledge" not in tools:
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
