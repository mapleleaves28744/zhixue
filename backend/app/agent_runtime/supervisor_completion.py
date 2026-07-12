from __future__ import annotations

from typing import Any

from app.agent_runtime.answer_text import extract_final_answer_text
from app.agent_runtime import supervisor_intents


def format_search_output_answer(tool_name: str, output: dict[str, Any], goal: str) -> str:
    query = str(output.get("query") or goal).strip()
    items = output.get("items") or []
    lines: list[str] = []
    if tool_name == "search_web":
        lines.append(f"## 联网搜索：{query}\n")
        message = str(output.get("message") or "").strip()
        if message and output.get("provider") == "mock":
            lines.append(f"_{message}_\n")
    else:
        lines.append(f"## 课程资料检索：{query}\n")

    if not items:
        lines.append("未找到相关结果，请尝试换关键词或补充更具体的描述。")
        return "\n".join(lines).strip()

    lines.append("为你找到以下参考来源：\n")
    for index, item in enumerate(items[:5], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or f"结果 {index}")
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("snippet") or item.get("content") or "").strip()
        if len(snippet) > 400:
            snippet = snippet[:400].rstrip() + "…"
        lines.append(f"{index}. **{title}**")
        if snippet:
            lines.append(f"   {snippet}")
        if url:
            lines.append(f"   来源：{url}")
        lines.append("")

    if tool_name == "search_web":
        lines.append("> 以上信息来自互联网公开资料，建议结合官方文档进一步核实。")
    else:
        lines.append("> 以上内容来自你的课程资料检索结果。")
    return "\n".join(lines).strip()


def build_search_results_answer(state: dict[str, Any], goal: str) -> str | None:
    observations = list(state.get("observations") or [])
    for obs in reversed(observations):
        if obs.get("success") is not True or str(obs.get("tool_name") or "") != "answer_course_question":
            continue
        output = obs.get("output")
        if not isinstance(output, dict):
            continue
        for key in ("answer", "content", "summary"):
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    for obs in reversed(observations):
        if obs.get("success") is not True:
            continue
        tool_name = str(obs.get("tool_name") or "")
        if tool_name not in {"search_web", "search_course_knowledge"}:
            continue
        output = obs.get("output")
        if isinstance(output, dict):
            return format_search_output_answer(tool_name, output, goal)
    return None


def build_completion_answer(state: dict[str, Any]) -> str:
    search_answer = build_search_results_answer(state, str(state.get("goal") or ""))
    if search_answer:
        return search_answer

    lines = ["所需学习内容已生成，请查看下方产物卡片或资源侧栏。"]
    for artifact in state.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        title = str(artifact.get("title") or artifact.get("name") or "学习产物")
        subtype = str(artifact.get("subtype") or artifact.get("asset_type") or artifact.get("type") or "")
        if subtype == "image" or str(artifact.get("mime_type") or "").startswith("image/"):
            lines.append(f"- 教学插图：{title}")
        elif subtype in {"mindmap", "diagram"} or artifact.get("type") == "resource":
            lines.append(f"- 知识卡片/资源：{title}")
        elif artifact.get("type") == "quiz":
            lines.append(f"- 练习题：{title}")
        elif artifact.get("type") == "learning_path":
            lines.append(f"- 学习路径：{title}")
        elif artifact.get("type") == "media_asset":
            lines.append(f"- 多模态产物：{title}")
    if len(lines) == 1 and state.get("observations"):
        lines.append("- 相关工具已执行完成，可在执行详情中查看输出。")
    return "\n".join(lines)


def normalize_completion_answer(state: dict[str, Any], goal: str, answer: str) -> str:
    for obs in reversed(state.get("observations") or []):
        if obs.get("success") is not True:
            continue
        tool_name = str(obs.get("tool_name") or "")
        output = obs.get("output") if isinstance(obs.get("output"), dict) else {}
        if tool_name == "generate_interactive_courseware":
            title = str(output.get("title") or "互动课件")
            asset_id = output.get("asset_id") or output.get("media_asset_id")
            return (
                f"互动课件已生成：{title}\n- 请在下方产物卡片或资源侧栏打开 HTML 课件预览"
                + (f"\n- asset_id={asset_id}" if asset_id else "")
            )
        if tool_name == "generate_lesson_video":
            job_id = output.get("media_job_id") or output.get("job_id")
            return (
                "讲解视频任务已提交后台队列，尚未完成渲染。\n"
                f"- job_id={job_id}\n"
                "- 请在执行轨迹查看进度；若出现 failed 步骤，说明后台渲染失败，需要重试或改选互动课件。"
            )
        if tool_name == "generate_immersive_classroom":
            job_id = output.get("media_job_id") or output.get("job_id")
            return f"沉浸课堂任务已提交后台队列。\n- job_id={job_id}\n- 请在执行轨迹查看 OpenMAIC 生成进度。"
        if tool_name in {"search_web", "search_course_knowledge"}:
            return format_search_output_answer(tool_name, output, goal)
    search_answer = build_search_results_answer(state, goal)
    if search_answer:
        return search_answer
    if supervisor_intents.presentation_intent(goal) and answer and "视频" in answer and "课件" not in answer:
        return build_completion_answer(state)
    return extract_final_answer_text(answer) or build_completion_answer(state)
