"""基础设施层 - 事件系统"""

from .event_bus import EventBus, event_bus
from .handlers import register_handlers

__all__ = ['EventBus', 'event_bus', 'register_handlers']
