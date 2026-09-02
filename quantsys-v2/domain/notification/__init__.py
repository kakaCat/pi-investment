"""
通知领域模型

Domain-Driven Design 架构的通知系统：
- 统一的通知抽象（Notification 聚合根）
- 多渠道支持（Feishu, Agent, Email, SMS）
- 清晰的职责分离（领域层、应用层、基础设施层）
- 可扩展的格式化器体系

作者: System
日期: 2026-09-02
"""

from .models.notification import (
    Notification,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
    NotificationRecipient,
)

from .models.channel import (
    NotificationChannel,
    ChannelResult,
)

from .models.formatter import (
    NotificationFormatter,
)

from .services.notification_service import (
    NotificationService,
)

from .policies.notification_policy import (
    NotificationPolicy,
)

__all__ = [
    # Models
    'Notification',
    'NotificationPriority',
    'NotificationStatus',
    'NotificationType',
    'NotificationRecipient',

    # Interfaces
    'NotificationChannel',
    'ChannelResult',
    'NotificationFormatter',

    # Services
    'NotificationService',

    # Policies
    'NotificationPolicy',
]
