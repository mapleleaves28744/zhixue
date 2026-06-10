from app.agent_runtime.answer_text import extract_final_answer_text


def test_extract_final_answer_from_json_envelope() -> None:
    raw = (
        '{"status":"complete","summary":"已成功生成","final_answer":"# 队列\\n\\n**先进先出**"}'
    )
    assert extract_final_answer_text(raw) == "# 队列\n\n**先进先出**"


def test_extract_final_answer_keeps_plain_markdown() -> None:
    raw = "# 标题\n\n正文"
    assert extract_final_answer_text(raw) == raw
