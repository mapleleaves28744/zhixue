from __future__ import annotations

import re


_SIMPLE_GREETINGS = {
    "hi",
    "hello",
    "hey",
    "你好",
    "您好",
    "嗨",
    "哈喽",
    "在吗",
    "早",
    "早上好",
    "上午好",
    "中午好",
    "下午好",
    "晚上好",
}


def is_simple_greeting(text: str) -> bool:
    normalized = re.sub(r"[\s,，。.!！?？~～]+", "", str(text).strip().lower())
    return normalized in _SIMPLE_GREETINGS


def simple_greeting_answer() -> str:
    return "你好！我是智学工坊学习助手。你可以直接提问课程知识，也可以让我生成练习、讲解或学习资源。"
