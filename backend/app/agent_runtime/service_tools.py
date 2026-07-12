from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools import ToolRegistry
from app.agent_runtime.toolsets import (
    register_knowledge_tools,
    register_learning_tools,
    register_media_tools,
    register_profile_tools,
    register_review_tools,
)
from app.models.user import User


def _register_toolsets(
    registry: ToolRegistry,
    db: AsyncSession,
    current_user: User,
) -> None:
    # Preserve the registry's established public tool order.
    register_knowledge_tools(registry, db, current_user, tool_names=("search_course_knowledge", "search_web"))
    register_learning_tools(registry, db, current_user, tool_names=("answer_course_question", "generate_learning_path", "generate_explanation", "generate_quiz"))
    register_knowledge_tools(registry, db, current_user, tool_names=("parse_uploaded_document", "generate_mindmap", "generate_diagram"))
    register_media_tools(registry, db, current_user, tool_names=("transcribe_audio", "synthesize_speech"))
    register_learning_tools(registry, db, current_user, tool_names=("analyze_learning_diagnosis", "refresh_recommendations"))
    register_profile_tools(registry, db, current_user, tool_names=("update_profile_from_dialogue", "rebuild_profile", "reflect_learning_memory"))
    register_review_tools(registry, db, current_user)
    register_profile_tools(registry, db, current_user, tool_names=("apply_evolution_strategy",))
    register_media_tools(registry, db, current_user, tool_names=("generate_educational_image", "generate_immersive_classroom", "generate_lesson_video", "generate_storyboard_html", "generate_interactive_courseware"))


def build_learning_tool_registry(
    db: AsyncSession,
    current_user: User,
    *,
    result_loader=None,
    result_saver=None,
) -> ToolRegistry:
    registry = ToolRegistry(result_loader=result_loader, result_saver=result_saver)

    _register_toolsets(registry, db, current_user)
    return registry
