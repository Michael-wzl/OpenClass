"""
OpenClass 事件系统
基于发布-订阅模式的事件总线，连接各模块之间的通信
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """事件类型枚举"""
    # 语音识别事件
    TRANSCRIPTION_STARTED = "transcription.started"
    TRANSCRIPTION_PARTIAL = "transcription.partial"            # 中间结果
    TRANSCRIPTION_SENTENCE_BEGIN = "transcription.sentence_begin"
    TRANSCRIPTION_SENTENCE_END = "transcription.sentence_end"  # 完整句子
    TRANSCRIPTION_COMPLETED = "transcription.completed"
    TRANSCRIPTION_ERROR = "transcription.error"
    TRANSCRIPTION_TRANSLATED = "transcription.translated"

    # AI 分析事件
    QUESTION_DETECTED = "ai.question_detected"         # 检测到老师提问
    ANSWER_GENERATED = "ai.answer_generated"           # 答案生成完毕
    SUGGEST_QUESTION = "ai.suggest_question"           # 建议提问
    PERIODIC_SUMMARY = "ai.periodic_summary"           # 定时总结
    CREATIVE_IDEAS = "ai.creative_ideas"               # 创意想法
    CONTENT_ANALYSIS = "ai.content_analysis"           # 内容分析

    # 课堂管理事件
    CLASS_STARTED = "class.started"
    CLASS_PAUSED = "class.paused"
    CLASS_RESUMED = "class.resumed"
    CLASS_ENDED = "class.ended"
    MATERIAL_LOADED = "class.material_loaded"

    # 系统事件
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"
    SYSTEM_INFO = "system.info"

    # 消息平台事件
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    COMMAND_RECEIVED = "command.received"


@dataclass
class Event:
    """事件对象"""
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""

    def __str__(self) -> str:
        return f"Event({self.type.value}, source={self.source}, data_keys={list(self.data.keys())})"


# 事件处理器类型
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    异步事件总线
    支持发布-订阅模式，所有模块通过事件总线通信
    """

    def __init__(self):
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._event_history: list[Event] = []
        self._max_history: int = 1000

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅特定类型的事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to {event_type.value}")

    def subscribe_all(self, handler: EventHandler) -> None:
        """订阅所有事件"""
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """取消订阅"""
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]

    async def publish(self, event: Event) -> None:
        """发布事件，异步通知所有订阅者"""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        handlers = self._handlers.get(event.type, []) + self._global_handlers

        if not handlers:
            logger.debug(f"No handlers for event: {event}")
            return

        tasks = []
        for handler in handlers:
            tasks.append(self._safe_call(handler, event))

        await asyncio.gather(*tasks)

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """安全调用事件处理器"""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Error in event handler for {event.type.value}: {e}", exc_info=True)

    def get_history(self, event_type: EventType | None = None, limit: int = 50) -> list[Event]:
        """获取事件历史"""
        if event_type:
            history = [e for e in self._event_history if e.type == event_type]
        else:
            history = self._event_history
        return history[-limit:]


# 全局事件总线实例
event_bus = EventBus()
