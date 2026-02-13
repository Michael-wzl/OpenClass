"""
测试大模型模块
"""

import pytest
from openclass.config import LLMConfig
from openclass.llm import QWenLLM, OpenAILLM, CustomLLM, create_llm


def test_create_qwen_llm():
    """测试创建通义千问实例"""
    config = LLMConfig(provider="qwen")
    llm = create_llm(config)
    assert isinstance(llm, QWenLLM)


def test_create_openai_llm():
    """测试创建 OpenAI 实例"""
    config = LLMConfig(provider="openai")
    llm = create_llm(config)
    assert isinstance(llm, OpenAILLM)


def test_create_custom_llm():
    """测试创建自定义实例"""
    config = LLMConfig(provider="custom")
    llm = create_llm(config)
    assert isinstance(llm, CustomLLM)


def test_invalid_provider():
    """测试无效的提供商"""
    config = LLMConfig(provider="invalid")
    with pytest.raises(ValueError, match="不支持的 LLM 提供商"):
        create_llm(config)
