"""Conservative identity and ambiguity checks; similarity never authorizes a merge."""
from __future__ import annotations

import re
from difflib import SequenceMatcher


def learning_memory_source_allowed(text: str) -> bool:
    from app.services.conversation_constraints import parse_session_changes

    if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)|身份证(?:号|号码)|家庭住址|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
        return False
    if re.search(r"不要(?:长期)?(?:记住|保存)|别(?:记住|保存)|不(?:代表|作为).{0,8}(?:长期偏好|我的偏好|记忆)", text):
        return False
    explicitly_long_term = bool(re.search(r"(?:长期|跨会话).{0,6}(?:记住|保存)|记住.{0,10}(?:长期|学习偏好)", text))
    if explicitly_long_term:
        return True
    return not parse_session_changes(text) and not bool(re.search(r"这次|这一次|本轮|本次对话|仅本次", text))


def normalize_fact_text(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def canonical_preference(content: str) -> str | None:
    categories = (
        ("examples", r"用例子|举例子|举例|先看例子|先给例子|实例|示例|具体案例"),
        ("diagrams", r"用图|画图|示意图|图解|图示|图片|图形|可视化|视觉化"),
        ("steps", r"分步骤|一步一步|逐步|拆成步骤|按步骤"),
        ("code", r"用代码|代码示例"),
        ("concise", r"简短|简洁|精简|言简意赅|少说一些"),
        ("detailed", r"详细|深入|展开|讲得细|细致讲"),
    )
    matches = [name for name, pattern in categories if re.search(pattern, content)]
    # Multiple dimensions and negated statements need a verified correction.
    if len(matches) != 1 or re.search(r"不要|不喜欢|不用|不再|别", content):
        return None
    return "preference:explanation:" + matches[0]


def likely_same_fact(left: str, right: str) -> bool:
    left, right = normalize_fact_text(left), normalize_fact_text(right)
    if not left or not right:
        return False
    return left == right or (min(len(left), len(right)) >= 8 and SequenceMatcher(None, left, right).ratio() >= 0.72)
