# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""
通知领域模型包
"""

from .notification import (
    Notification,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
    NotificationRecipient,
)

from .channel import (
    NotificationChannel,
    ChannelResult,
)

from .formatter import (
    NotificationFormatter,
)

__all__ = [
    'Notification',
    'NotificationPriority',
    'NotificationStatus',
    'NotificationType',
    'NotificationRecipient',
    'NotificationChannel',
    'ChannelResult',
    'NotificationFormatter',
]
