"""
测试 AI 引擎的 JSON 解析功能
"""

from openclass.ai_engine import AIEngine


def test_parse_json_response_normal():
    """测试正常JSON解析"""
    text = '{"is_question": true, "question_text": "什么是极限?"}'
    result = AIEngine._parse_json_response(text)
    assert result is not None
    assert result["is_question"] is True


def test_parse_json_response_with_markdown():
    """测试带 markdown 代码块的 JSON"""
    text = '```json\n{"key": "value"}\n```'
    result = AIEngine._parse_json_response(text)
    assert result is not None
    assert result["key"] == "value"


def test_parse_json_response_with_extra_text():
    """测试含有额外文字的 JSON"""
    text = 'Here is the analysis:\n{"result": "ok"}\nDone.'
    result = AIEngine._parse_json_response(text)
    assert result is not None
    assert result["result"] == "ok"


def test_parse_json_response_invalid():
    """测试无效 JSON"""
    text = 'This is not JSON at all'
    result = AIEngine._parse_json_response(text)
    assert result is None
