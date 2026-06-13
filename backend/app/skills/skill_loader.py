from __future__ import annotations

from functools import lru_cache
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent / "html-ppt-skill"


class HtmlPptSkillLoader:
    """加载 lewislulu/html-ppt-skill 的 SKILL 与模板资产（MIT）。"""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or SKILL_ROOT

    def read(self, relative_path: str) -> str:
        path = self.root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"html-ppt skill asset missing: {relative_path}")
        return path.read_text(encoding="utf-8")

    @lru_cache(maxsize=1)
    def skill_md(self) -> str:
        return self.read("SKILL.md")

    @lru_cache(maxsize=1)
    def authoring_guide(self) -> str:
        return self.read("references/authoring-guide.md")

    @lru_cache(maxsize=1)
    def layouts_catalog(self) -> str:
        return self.read("references/layouts.md")

    @lru_cache(maxsize=1)
    def course_module_template(self) -> str:
        return self.read("templates/full-decks/course-module/index.html")

    @lru_cache(maxsize=1)
    def bundled_styles(self) -> str:
        parts = [
            self.read("assets/base.css"),
            self.read("templates/full-decks/course-module/style.css"),
            self.read("assets/animations/animations.css"),
            "/* iframe-safe fonts */ html,body{font-family:'Noto Sans SC',system-ui,-apple-system,sans-serif;}",
        ]
        return "\n".join(parts)

    @lru_cache(maxsize=1)
    def bundled_runtime(self) -> str:
        return self.read("assets/runtime.js")

    def outline_system_prompt(self) -> str:
        return (
            "你必须严格遵循以下 Agent Skill 工作流，不得偏离。\n\n"
            "=== html-ppt SKILL.md ===\n"
            f"{self.skill_md()}\n\n"
            "=== authoring-guide（大纲阶段）===\n"
            f"{self.authoring_guide()}\n\n"
            "当前任务：仅完成 authoring-guide 第 1-3 步——理解受众、选定主题、输出课件大纲。\n"
            "高校课程互动课件默认：\n"
            "- 受众：大学生\n"
            "- 主题/模板：`course-module`（学术友好课件风）\n"
            "- 页数：6-8 页\n"
            "- 语言：简体中文\n"
            "- 结构：cover → objectives → concept ×2 → example → exercise → quiz → summary\n"
            "禁止把原始 markdown（如 ### 标题）直接塞进 bullets；知识点需改写为短句。\n"
        )

    def deck_system_prompt(self) -> str:
        return (
            "你必须严格遵循 html-ppt skill 的 course-module 全 deck 模板结构与 class 命名。\n\n"
            "=== layouts 参考 ===\n"
            f"{self.layouts_catalog()}\n\n"
            "=== course-module 示例（结构与 class 必须一致）===\n"
            f"{self.course_module_template()}\n\n"
            "输出要求：仅输出完整 HTML 文档（<!doctype html> 开头），不要 markdown 围栏。\n"
            "CSS/JS 用内联 <style> 与 <script>，禁止外链 http(s)。\n"
            "每页必须是 <section class=\"slide\">，首屏加 is-active。\n"
        )
