"""
OpenClass 消息平台模块
可扩展的消息通信框架，支持多种社交媒体平台
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

from openclass.events import Event, EventBus, EventType

logger = logging.getLogger(__name__)


class MessagePlatform(ABC):
    """消息平台基类"""

    platform_name: str = "base"

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """启动平台连接"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """停止平台连接"""
        ...

    @abstractmethod
    async def send_message(self, message: str, **kwargs) -> None:
        """发送消息"""
        ...

    @abstractmethod
    async def send_alert(self, title: str, content: str, level: str = "info", **kwargs) -> None:
        """发送提醒/告警"""
        ...

    async def _on_command(self, command: str, args: dict) -> None:
        """处理收到的命令"""
        await self.event_bus.publish(Event(
            type=EventType.COMMAND_RECEIVED,
            data={"command": command, "args": args, "platform": self.platform_name},
            source=f"platform.{self.platform_name}",
        ))


class ConsolePlatform(MessagePlatform):
    """
    控制台输出平台（默认）
    将所有消息输出到终端
    """

    platform_name = "console"

    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)

    async def start(self) -> None:
        self._running = True
        logger.info("控制台消息平台已启动")

    async def stop(self) -> None:
        self._running = False

    async def send_message(self, message: str, **kwargs) -> None:
        """输出消息到控制台"""
        # 这里在 TUI 模式下会被覆盖
        print(message)

    async def send_alert(self, title: str, content: str, level: str = "info", **kwargs) -> None:
        """输出告警到控制台"""
        icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "question": "❓", "answer": "✅", "idea": "💡", "summary": "📝"}
        icon = icons.get(level, "📌")
        print(f"\n{icon} [{title}]\n{content}\n")


class WhatsAppPlatform(MessagePlatform):
    """
    WhatsApp 消息平台（预留接口）
    未来实现与 WhatsApp Business API 的集成
    """

    platform_name = "whatsapp"

    def __init__(self, event_bus: EventBus, token: str = ""):
        super().__init__(event_bus)
        self.token = token

    async def start(self) -> None:
        logger.info("WhatsApp 平台接口已预留（待实现）")
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send_message(self, message: str, **kwargs) -> None:
        # TODO: 实现 WhatsApp Business API 消息发送
        logger.debug(f"[WhatsApp] {message}")

    async def send_alert(self, title: str, content: str, level: str = "info", **kwargs) -> None:
        await self.send_message(f"[{title}] {content}")


class QQPlatform(MessagePlatform):
    """
    QQ 消息平台（预留接口）
    未来实现与 QQ 机器人 API 的集成
    """

    platform_name = "qq"

    def __init__(self, event_bus: EventBus, token: str = ""):
        super().__init__(event_bus)
        self.token = token

    async def start(self) -> None:
        logger.info("QQ 平台接口已预留（待实现）")
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send_message(self, message: str, **kwargs) -> None:
        # TODO: 实现 QQ Bot API 消息发送
        logger.debug(f"[QQ] {message}")

    async def send_alert(self, title: str, content: str, level: str = "info", **kwargs) -> None:
        await self.send_message(f"[{title}] {content}")


class XPlatform(MessagePlatform):
    """
    X (Twitter) 消息平台（预留接口）
    """

    platform_name = "x"

    def __init__(self, event_bus: EventBus, api_key: str = ""):
        super().__init__(event_bus)
        self.api_key = api_key

    async def start(self) -> None:
        logger.info("X 平台接口已预留（待实现）")
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send_message(self, message: str, **kwargs) -> None:
        # TODO: 实现 X API 消息发送
        logger.debug(f"[X] {message}")

    async def send_alert(self, title: str, content: str, level: str = "info", **kwargs) -> None:
        await self.send_message(f"[{title}] {content}")


class PlatformManager:
    """
    平台管理器
    管理多个消息平台，统一分发消息
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._platforms: dict[str, MessagePlatform] = {}

    def register(self, platform: MessagePlatform) -> None:
        """注册消息平台"""
        self._platforms[platform.platform_name] = platform
        logger.info(f"已注册消息平台: {platform.platform_name}")

    async def start_all(self) -> None:
        """启动所有平台"""
        for p in self._platforms.values():
            await p.start()

    async def stop_all(self) -> None:
        """停止所有平台"""
        for p in self._platforms.values():
            await p.stop()

    async def broadcast_message(self, message: str, **kwargs) -> None:
        """向所有平台广播消息"""
        for p in self._platforms.values():
            try:
                await p.send_message(message, **kwargs)
            except Exception as e:
                logger.error(f"发送消息到 {p.platform_name} 失败: {e}")

    async def broadcast_alert(self, title: str, content: str, level: str = "info", **kwargs) -> None:
        """向所有平台广播提醒"""
        for p in self._platforms.values():
            try:
                await p.send_alert(title, content, level, **kwargs)
            except Exception as e:
                logger.error(f"发送提醒到 {p.platform_name} 失败: {e}")

    def get_platform(self, name: str) -> Optional[MessagePlatform]:
        """获取指定平台"""
        return self._platforms.get(name)
