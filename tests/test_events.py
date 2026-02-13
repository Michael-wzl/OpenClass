"""
测试事件总线
"""

import asyncio
import pytest
from openclass.events import Event, EventBus, EventType


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_subscribe_and_publish(bus):
    """测试基本的发布-订阅"""
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.TRANSCRIPTION_SENTENCE_END, handler)
    await bus.publish(Event(
        type=EventType.TRANSCRIPTION_SENTENCE_END,
        data={"text": "Hello world"},
        source="test",
    ))

    assert len(received) == 1
    assert received[0].data["text"] == "Hello world"


@pytest.mark.asyncio
async def test_subscribe_all(bus):
    """测试全局订阅"""
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe_all(handler)

    await bus.publish(Event(type=EventType.CLASS_STARTED, source="test"))
    await bus.publish(Event(type=EventType.CLASS_ENDED, source="test"))

    assert len(received) == 2


@pytest.mark.asyncio
async def test_unsubscribe(bus):
    """测试取消订阅"""
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.QUESTION_DETECTED, handler)
    bus.unsubscribe(EventType.QUESTION_DETECTED, handler)

    await bus.publish(Event(type=EventType.QUESTION_DETECTED, source="test"))
    assert len(received) == 0


@pytest.mark.asyncio
async def test_event_history(bus):
    """测试事件历史"""
    for i in range(5):
        await bus.publish(Event(
            type=EventType.TRANSCRIPTION_SENTENCE_END,
            data={"index": i},
            source="test",
        ))

    history = bus.get_history(EventType.TRANSCRIPTION_SENTENCE_END)
    assert len(history) == 5

    history = bus.get_history(limit=3)
    assert len(history) == 3


@pytest.mark.asyncio
async def test_handler_error_isolation(bus):
    """测试处理器错误隔离"""
    received = []

    async def bad_handler(event: Event):
        raise ValueError("test error")

    async def good_handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.SYSTEM_INFO, bad_handler)
    bus.subscribe(EventType.SYSTEM_INFO, good_handler)

    await bus.publish(Event(type=EventType.SYSTEM_INFO, source="test"))
    assert len(received) == 1  # good_handler 应该正常执行
