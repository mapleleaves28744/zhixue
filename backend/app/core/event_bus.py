"""轻量级事件总线，基于 asyncio.Queue 实现发布-订阅模式。

用于 Agent 间异步解耦通信。事件在进程内分发，不持久化。

用法：
    bus = get_event_bus()
    bus.subscribe("diagnosis_complete", my_handler)
    await bus.publish("diagnosis_complete", {"user_id": ..., "course_id": ...})
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from uuid import uuid4

logger = logging.getLogger(__name__)

# 事件处理器类型：接收事件数据，返回 None
EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


@dataclass
class Event:
    """事件消息载体。"""
    event_type: str
    data: dict[str, Any]
    event_id: str = field(default_factory=lambda: uuid4().hex)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    source: str = ""


class EventBus:
    """进程内发布-订阅事件总线。

    - 每个事件类型可以有多个订阅者
    - 发布后异步并发通知所有订阅者
    - 单个订阅者异常不影响其他订阅者
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task[None] | None = None

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """注册事件处理器。"""
        self._handlers[event_type].append(handler)
        logger.debug("EventBus: subscribed %s to '%s'", handler.__name__, event_type)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """取消注册事件处理器。"""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event_type: str, data: dict[str, Any], *, source: str = "") -> Event:
        """发布事件到队列。"""
        event = Event(event_type=event_type, data=data, source=source)
        await self._queue.put(event)
        logger.debug("EventBus: published '%s' (id=%s)", event_type, event.event_id)
        return event

    async def emit(self, event: Event) -> None:
        """直接向所有订阅者分发事件（同步等待完成）。"""
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return
        tasks = [self._safe_call(handler, event) for handler in handlers]
        await asyncio.gather(*tasks)

    async def start(self) -> None:
        """启动后台消费 worker。"""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._consume_loop())
        logger.info("EventBus: started background consumer")

    async def stop(self) -> None:
        """停止后台消费 worker。"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("EventBus: stopped background consumer")

    async def _consume_loop(self) -> None:
        """后台循环消费队列中的事件。"""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            await self.emit(event)

    @staticmethod
    async def _safe_call(handler: EventHandler, event: Event) -> None:
        """安全调用处理器，捕获异常不影响其他处理器。"""
        try:
            await handler(event)
        except Exception:
            logger.exception(
                "EventBus: handler %s failed for event '%s' (id=%s)",
                handler.__name__, event.event_type, event.event_id,
            )


# ── 全局单例 ──
_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例。"""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
