"""
测试配置管理
"""

import os
import pytest
from openclass.config import AppConfig, LLMConfig, TingwuConfig


def test_default_config():
    """测试默认配置"""
    config = AppConfig()
    assert config.llm.provider == "qwen"
    assert config.tingwu.sample_rate == 16000
    assert config.classroom.summary_interval_minutes == 10
    assert config.classroom.output_language == "cn"
    assert config.audio.channels == 1


def test_llm_config_from_env():
    """测试从环境变量加载 LLM 配置"""
    os.environ["LLM_PROVIDER"] = "openai"
    os.environ["OPENAI_API_KEY"] = "test-key-123"

    config = LLMConfig()
    assert config.provider == "openai"
    assert config.openai_api_key == "test-key-123"

    # 清理
    del os.environ["LLM_PROVIDER"]
    del os.environ["OPENAI_API_KEY"]


def test_tingwu_config():
    """测试听悟配置"""
    config = TingwuConfig()
    assert config.audio_format == "pcm"
    assert config.domain == "tingwu.cn-beijing.aliyuncs.com"
    assert config.source_language == "cn"


def test_config_load():
    """测试配置加载"""
    config = AppConfig.load()
    assert config is not None
    assert isinstance(config.llm, LLMConfig)
    assert isinstance(config.tingwu, TingwuConfig)


def test_tingwu_env_aliases(monkeypatch):
    """确保 ALI_ACCESS_KEY_ID / ALI_ACCESS_KEY_SECRET 能被识别并映射"""
    monkeypatch.setenv("ALI_ACCESS_KEY_ID", "id-ali-123")
    monkeypatch.setenv("ALI_ACCESS_KEY_SECRET", "sk-ali-456")

    config = AppConfig.load()
    assert config.tingwu.access_key_id == "id-ali-123"
    assert config.tingwu.access_key_secret == "sk-ali-456"
