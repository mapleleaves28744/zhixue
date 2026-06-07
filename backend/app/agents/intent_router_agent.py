from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry


ARTIFACT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("learning_path", ("学习计划", "学习路径", "复习计划")),
    ("doc", ("讲解资料", "讲解", "学习资料", "文档")),
    ("quiz", ("练习题", "练习", "题目", "测验")),
    ("html_classroom", ("课堂讲解", "课堂", "交互课堂", "html")),
]
KNOWLEDGE_KEYWORDS = [
    "复杂度",
    "线性表",
    "栈",
    "队列",
    "字符串",
    "数组",
    "链表",
    "树",
    "二叉树",
    "堆",
    "图",
    "排序",
    "查找",
    "哈希",
]
HIGH_RISK_KEYWORDS = ("删除", "覆盖", "发布", "批量重建", "对外导出", "应用自进化")
MEDIUM_RISK_KEYWORDS = ("更新画像", "修改画像", "应用策略")


@AgentRegistry.register
class IntentRouterAgent(BaseAgent):
    name = "IntentRouterAgent"
    description = "将自然语言学习请求解析为受控 AgentTask 意图"

    async def run(self, context: AgentContext) -> AgentResult:
        user_input = str(context.params.get("user_input") or "").strip()
        if not user_input:
            return self.error_result(message="缺少 user_input 参数")

        artifacts = [
            artifact
            for artifact, keywords in ARTIFACT_KEYWORDS
            if any(keyword.lower() in user_input.lower() for keyword in keywords)
        ]
        knowledge = [
            keyword
            for keyword in KNOWLEDGE_KEYWORDS
            if keyword in user_input and not self._is_shadowed(keyword, user_input)
        ]
        risk_level, requires_confirmation = self._risk(user_input)
        task_type = self._task_type(user_input, artifacts)
        if not artifacts:
            artifacts = ["doc"] if task_type == "personalized_learning_package" else []

        return self.success_result(
            data={
                "task_type": task_type,
                "goal": self._goal(user_input, knowledge),
                "target_knowledge": knowledge,
                "requested_artifacts": artifacts,
                "constraints": {"original_request": user_input},
                "risk_level": risk_level,
                "requires_confirmation": requires_confirmation,
            },
            message="任务意图解析完成",
            evidence=["IntentRouterAgent 确定性规则解析"],
        )

    def _task_type(self, user_input: str, artifacts: list[str]) -> str:
        if any(keyword in user_input for keyword in ("了解我的学习情况", "画像访谈", "学习画像")):
            return "profile_interview_plan"
        if artifacts == ["html_classroom"]:
            return "html_classroom_request"
        return "personalized_learning_package"

    def _risk(self, user_input: str) -> tuple[str, bool]:
        if any(keyword in user_input for keyword in HIGH_RISK_KEYWORDS):
            return "high", True
        if any(keyword in user_input for keyword in MEDIUM_RISK_KEYWORDS):
            return "medium", True
        return "low", False

    def _goal(self, user_input: str, knowledge: list[str]) -> str:
        if knowledge:
            return f"补强{'和'.join(knowledge)}"
        return user_input[:200]

    def _is_shadowed(self, keyword: str, user_input: str) -> bool:
        if keyword == "树" and "二叉树" in user_input:
            return True
        return False

