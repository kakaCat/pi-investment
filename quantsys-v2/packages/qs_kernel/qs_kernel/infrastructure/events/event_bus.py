"""
事件总线 - 事件驱动架构核心
使用 Queue 实现非阻塞发布，后台线程异步处理
"""
from typing import Callable, Dict, List, Any
import asyncio
import logging
import threading
import queue
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


class EventBus:
    """事件总线 - 非阻塞发布，后台线程处理"""

    def __init__(self, max_history: int = 1000, max_queue_size: int = 10000):
        """
        初始化事件总线

        Args:
            max_history: 保留的最大事件历史数量
            max_queue_size: 事件队列最大容量（0=无限）
        """
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history: deque = deque(maxlen=max_history)
        self._lock = threading.Lock()
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._running = True
        self._worker = threading.Thread(target=self._process_loop, daemon=True)
        self._worker.start()

    def _process_loop(self):
        """后台工作线程：持续从队列取出事件并处理"""
        while self._running:
            try:
                event_type, data = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            event = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            self.event_history.append(event)

            logger.debug(f"处理事件: {event_type}")

            with self._lock:
                handlers = list(self.subscribers.get(event_type, []))

            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        logger.warning(f"跳过异步处理器(同步模式): {handler.__name__}")
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"事件处理器错误: {handler.__name__}, {e}", exc_info=True)

    def subscribe(self, event_type: str, handler: Callable):
        """
        订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理函数（同步）
        """
        with self._lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            self.subscribers[event_type].append(handler)
            logger.info(f"订阅事件: {event_type}, 处理器: {handler.__name__}")

    def unsubscribe(self, event_type: str, handler: Callable):
        """
        取消订阅

        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        with self._lock:
            if event_type in self.subscribers:
                try:
                    self.subscribers[event_type].remove(handler)
                    logger.info(f"取消订阅: {event_type}, 处理器: {handler.__name__}")
                except ValueError:
                    logger.warning(f"处理器未找到: {event_type}, {handler.__name__}")

    def publish(self, event_type: str, data: Dict[str, Any]):
        """
        发布事件（非阻塞，立即返回）

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        try:
            self._queue.put_nowait((event_type, data))
        except queue.Full:
            logger.error(f"事件队列已满，丢弃事件: {event_type}")

    def publish_sync(self, event_type: str, data: Dict[str, Any]):
        """publish 的别名，保持向后兼容"""
        self.publish(event_type, data)

    async def publish_async(self, event_type: str, data: Dict[str, Any]):
        """异步发布事件（非阻塞）"""
        self.publish(event_type, data)

    def get_history(self, event_type: str = None, limit: int = 100) -> List[Dict]:
        """
        获取事件历史

        Args:
            event_type: 事件类型过滤（可选）
            limit: 返回的最大事件数量

        Returns:
            事件列表
        """
        history = list(self.event_history)
        if event_type:
            history = [e for e in history if e["type"] == event_type]
        return history[-limit:]

    def get_subscriber_count(self, event_type: str = None) -> int:
        """
        获取订阅者数量

        Args:
            event_type: 事件类型（可选）

        Returns:
            订阅者数量
        """
        with self._lock:
            if event_type:
                return len(self.subscribers.get(event_type, []))
            return sum(len(handlers) for handlers in self.subscribers.values())

    def get_queue_size(self) -> int:
        """获取当前队列中待处理的事件数量"""
        return self._queue.qsize()

    def clear_history(self):
        """清空事件历史"""
        self.event_history.clear()
        logger.info("事件历史已清空")

    def shutdown(self):
        """关闭事件总线，等待队列处理完成"""
        self._running = False
        self._worker.join(timeout=5.0)
        logger.info("事件总线已关闭")


# 全局事件总线实例
event_bus = EventBus()
