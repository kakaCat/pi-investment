# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""
通知应用层包
"""

from .notification_facade import NotificationFacade
from .notification_factory import NotificationFactory, get_notification_facade

__all__ = [
    'NotificationFacade',
    'NotificationFactory',
    'get_notification_facade',
]
