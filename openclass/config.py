"""
OpenClass 配置管理模块
支持环境变量、YAML配置文件、运行时动态配置
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class TingwuConfig(BaseSettings):
    """通义听悟配置"""
    model_config = ConfigDict(populate_by_name=True)
    access_key_id: str = Field(default="", alias="ALIBABA_CLOUD_ACCESS_KEY_ID")
    access_key_secret: str = Field(default="", alias="ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    app_key: str = Field(default="", alias="TINGWU_APP_KEY")
    region: str = "cn-beijing"
    api_version: str = "2023-09-30"
    domain: str = "tingwu.cn-beijing.aliyuncs.com"
    sample_rate: int = 16000
    audio_format: str = "pcm"
    source_language: str = "cn"
    enable_diarization: bool = True
    speaker_count: int = 0  # 0=自动检测人数
    enable_translation: bool = False
    translation_target_languages: list[str] = Field(default_factory=lambda: ["en"])
    output_level: int = 2  # 2=返回中间结果和完整句子


class LLMConfig(BaseSettings):
    """大模型配置"""
    model_config = ConfigDict(populate_by_name=True)

    provider: str = Field(default="qwen", alias="LLM_PROVIDER")
    # 通义千问
    dashscope_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    qwen_model: str = "qwen-plus"
    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = "gpt-4o"
    # 自定义
    custom_api_key: str = Field(default="", alias="CUSTOM_LLM_API_KEY")
    custom_base_url: str = Field(default="", alias="CUSTOM_LLM_BASE_URL")
    custom_model: str = Field(default="", alias="CUSTOM_LLM_MODEL")
    # 通用
    temperature: float = 0.7
    max_tokens: int = 4096


class AudioConfig(BaseSettings):
    """音频采集配置"""
    device_index: Optional[int] = None  # None=系统默认
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 3200  # 每次读取的帧数 (100ms @ 16kHz)
    format_bits: int = 16


class ClassroomConfig(BaseSettings):
    """课堂配置"""
    model_config = ConfigDict(populate_by_name=True)

    data_dir: str = Field(default="./classroom_data", alias="CLASSROOM_DATA_DIR")
    output_language: str = Field(default="cn", alias="OUTPUT_LANGUAGE")
    summary_interval_minutes: int = Field(default=10, alias="SUMMARY_INTERVAL_MINUTES")
    auto_detect_language: bool = True
    enable_question_detection: bool = True
    enable_auto_answer: bool = True
    enable_suggest_questions: bool = True
    enable_periodic_summary: bool = True
    enable_creative_ideas: bool = True


class MessagingConfig(BaseSettings):
    """消息平台配置"""
    enabled_platforms: list[str] = Field(default_factory=lambda: ["console"])
    # 预留社交媒体平台配置
    whatsapp_token: str = ""
    qq_bot_token: str = ""
    x_api_key: str = ""


class AppConfig(BaseSettings):
    """应用总配置"""
    tingwu: TingwuConfig = Field(default_factory=TingwuConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    classroom: ClassroomConfig = Field(default_factory=ClassroomConfig)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    debug: bool = False
    log_level: str = "INFO"

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "AppConfig":
        """
        加载配置，优先级：环境变量 > YAML配置文件 > 默认值
        """
        yaml_data = {}
        if config_path and Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}
        else:
            # 尝试从默认路径加载
            for p in ["openclass.yaml", "openclass.yml", "config.yaml"]:
                if Path(p).exists():
                    with open(p, "r", encoding="utf-8") as f:
                        yaml_data = yaml.safe_load(f) or {}
                    break

        # 从 .env 文件加载环境变量（如果存在）
        env_file = Path(".env")
        if env_file.exists():
            _load_dotenv(env_file)

        # 兼容环境变量别名：支持 ALI_ACCESS_KEY_ID / ALI_ACCESS_KEY_SECRET
        # 以及历史遗留的 ALIBABA_CLOUD_ACCESS_KEY_ID / ALIBABA_CLOUD_ACCESS_KEY_SECRET
        # 优先使用 ALI_*，但保证两个名称都能被识别
        # 优先使用简短变量名 ALI_*（如果同时存在，AL I_* 将覆盖 ALIBABA_*）
        if os.environ.get("ALI_ACCESS_KEY_ID"):
            os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"] = os.environ["ALI_ACCESS_KEY_ID"]
        if os.environ.get("ALI_ACCESS_KEY_SECRET"):
            os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"] = os.environ["ALI_ACCESS_KEY_SECRET"]
        # 反向兼容：若仅设置了老名称，则同步到新的 ALI_* 名称
        if os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID") and not os.environ.get("ALI_ACCESS_KEY_ID"):
            os.environ["ALI_ACCESS_KEY_ID"] = os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"]
        if os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET") and not os.environ.get("ALI_ACCESS_KEY_SECRET"):
            os.environ["ALI_ACCESS_KEY_SECRET"] = os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"]

        config = cls()

        # 覆盖 YAML 配置
        if "tingwu" in yaml_data:
            config.tingwu = TingwuConfig(**{**config.tingwu.model_dump(), **yaml_data["tingwu"]})
        if "llm" in yaml_data:
            config.llm = LLMConfig(**{**config.llm.model_dump(), **yaml_data["llm"]})
        if "audio" in yaml_data:
            config.audio = AudioConfig(**{**config.audio.model_dump(), **yaml_data["audio"]})
        if "classroom" in yaml_data:
            config.classroom = ClassroomConfig(**{**config.classroom.model_dump(), **yaml_data["classroom"]})
        if "messaging" in yaml_data:
            config.messaging = MessagingConfig(**{**config.messaging.model_dump(), **yaml_data["messaging"]})
        if "debug" in yaml_data:
            config.debug = yaml_data["debug"]
        if "log_level" in yaml_data:
            config.log_level = yaml_data["log_level"]

        return config


def _load_dotenv(env_path: Path) -> None:
    """简单的 .env 文件加载器"""
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and value and key not in os.environ:
                    os.environ[key] = value
