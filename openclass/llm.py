"""
OpenClass LLM 大模型模块
支持多种大模型后端：通义千问(QWen)、OpenAI、自定义API
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from openclass.config import LLMConfig

logger = logging.getLogger(__name__)


class BaseLLM(ABC):
    """大模型基类"""

    @abstractmethod
    async def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """发送对话请求，返回回复文本"""
        ...

    @abstractmethod
    async def chat_stream(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> AsyncIterator[str]:
        """流式对话"""
        ...


class QWenLLM(BaseLLM):
    """阿里通义千问 (DashScope) 大模型"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = config.dashscope_api_key
        self.model = config.qwen_model

    async def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> str:
        try:
            import dashscope
            from dashscope import Generation

            dashscope.api_key = self.api_key

            response = await self._call_sync(messages, temperature, max_tokens)
            return response
        except ImportError:
            # 回退到 OpenAI 兼容接口
            return await self._chat_via_openai_compat(messages, temperature, max_tokens)

    async def _call_sync(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_dashscope, messages, temperature, max_tokens)

    def _call_dashscope(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        from dashscope import Generation

        response = Generation.call(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format="message",
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            raise RuntimeError(f"QWen API error: {response.code} - {response.message}")

    async def _chat_via_openai_compat(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        """通过 OpenAI 兼容接口调用通义千问"""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def chat_stream(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> AsyncIterator[str]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class OpenAILLM(BaseLLM):
    """OpenAI 大模型"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = config.openai_api_key
        self.base_url = config.openai_base_url
        self.model = config.openai_model

    async def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def chat_stream(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> AsyncIterator[str]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class CustomLLM(BaseLLM):
    """自定义 OpenAI 兼容 API 大模型"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = config.custom_api_key
        self.base_url = config.custom_base_url
        self.model = config.custom_model

    async def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def chat_stream(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> AsyncIterator[str]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


def create_llm(config: LLMConfig) -> BaseLLM:
    """根据配置创建对应的大模型实例"""
    providers = {
        "qwen": QWenLLM,
        "openai": OpenAILLM,
        "custom": CustomLLM,
    }
    provider_cls = providers.get(config.provider.lower())
    if not provider_cls:
        raise ValueError(f"不支持的 LLM 提供商: {config.provider}，可选: {list(providers.keys())}")
    return provider_cls(config)
