"""
事件总线 - 事件驱动架构核心
"""
from typing import Callable, Dict, List, Any
import asyncio
import logging
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


class EventBus:
    """事件总线 - 支持同步和异步事件处理"""

    def __init__(self, max_history: int = 1000):
        """
        初始化事件总线

        Args:
            max_history: 保留的最大事件历史数量
        """
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history: deque = deque(maxlen=max_history)
        self._lock = asyncio.Lock() if self._is_async_available() else None

    def _is_async_available(self) -> bool:
        """检查是否在异步环境中"""
        try:
            asyncio.get_event_loop()
            return True
        except RuntimeError:
            return False

    def subscribe(self, event_type: str, handler: Callable):
        """
        订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理函数（可以是同步或异步）
        """
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
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(handler)
                logger.info(f"取消订阅: {event_type}, 处理器: {handler.__name__}")
            except ValueError:
                logger.warning(f"处理器未找到: {event_type}, {handler.__name__}")

    async def publish_async(self, event_type: str, data: Dict[str, Any]):
        """
        异步发布事件

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self.event_history.append(event)

        logger.debug(f"发布事件: {event_type}, 数据: {data}")

        if event_type in self.subscribers:
            tasks = []
            for handler in self.subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        tasks.append(handler(data))
                    else:
                        # 同步函数在线程池中执行
                        loop = asyncio.get_event_loop()
                        tasks.append(loop.run_in_executor(None, handler, data))
                except Exception as e:
                    logger.error(f"事件处理器错误: {handler.__name__}, {e}", exc_info=True)

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"处理器执行失败: {self.subscribers[event_type][i].__name__}, {result}")

    def publish_sync(self, event_type: str, data: Dict[str, Any]):
        """
        同步发布事件（用于非异步环境）

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self.event_history.append(event)

        logger.debug(f"发布事件(同步): {event_type}, 数据: {data}")

        if event_type in self.subscribers:
            for handler in self.subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        logger.warning(f"跳过异步处理器(同步模式): {handler.__name__}")
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"事件处理器错误: {handler.__name__}, {e}", exc_info=True)

    def publish(self, event_type: str, data: Dict[str, Any]):
        """
        发布事件（自动选择同步或异步）

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在运行的事件循环中，创建任务
                asyncio.create_task(self.publish_async(event_type, data))
            else:
                # 没有运行的循环，使用同步模式
                self.publish_sync(event_type, data)
        except RuntimeError:
            # 没有事件循环，使用同步模式
            self.publish_sync(event_type, data)

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
        if event_type:
            return len(self.subscribers.get(event_type, []))
        return sum(len(handlers) for handlers in self.subscribers.values())

    def clear_history(self):
        """清空事件历史"""
        self.event_history.clear()
        logger.info("事件历史已清空")


# 全局事件总线实例
event_bus = EventBus()
