"""
通知应用层包
"""

from .agent_task_dispatch import (
    REPORT_BLOCK_TEMPLATE,
    build_instruction,
    dispatch_agent_task,
)
from .notification_facade import NotificationFacade
from .notification_factory import NotificationFactory, get_notification_facade

__all__ = [
    'NotificationFacade',
    'NotificationFactory',
    'REPORT_BLOCK_TEMPLATE',
    'build_instruction',
    'dispatch_agent_task',
    'get_notification_facade',
]
