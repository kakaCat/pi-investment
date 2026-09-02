"""
通知领域模型单元测试

测试 Notification 聚合根的状态转换逻辑

Author: System
Date: 2026-09-02
"""

import pytest
from datetime import datetime

from domain.notification.models.notification import (
    Notification,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
    NotificationRecipient,
)


class TestNotification:
    """Notification 聚合根测试"""

    def test_notification_creation(self):
        """测试通知创建"""
        notification = Notification(
            notification_type=NotificationType.STOP_LOSS,
            title="止损触发",
            content="测试内容",
            priority=NotificationPriority.CRITICAL
        )

        assert notification.notification_type == NotificationType.STOP_LOSS
        assert notification.title == "止损触发"
        assert notification.content == "测试内容"
        assert notification.priority == NotificationPriority.CRITICAL
        assert notification.status == NotificationStatus.PENDING
        assert notification.retry_count == 0

    def test_notification_id_generation(self):
        """测试通知 ID 自动生成"""
        notif1 = Notification()
        notif2 = Notification()

        assert notif1.notification_id != notif2.notification_id
        assert notif1.notification_id.startswith("notif_")
        assert notif2.notification_id.startswith("notif_")

    def test_mark_sending(self):
        """测试标记为发送中"""
        notification = Notification()
        assert notification.status == NotificationStatus.PENDING

        notification.mark_sending()
        assert notification.status == NotificationStatus.SENDING

    def test_mark_sending_from_wrong_status(self):
        """测试从错误状态标记发送中（应该失败）"""
        notification = Notification()
        notification.mark_sending()
        notification.mark_sent()

        # 从 SENT 状态无法再次标记为 SENDING
        with pytest.raises(ValueError):
            notification.mark_sending()

    def test_mark_sent(self):
        """测试标记为已发送"""
        notification = Notification()
        notification.mark_sending()

        assert notification.sent_at is None

        notification.mark_sent()

        assert notification.status == NotificationStatus.SENT
        assert notification.sent_at is not None
        assert isinstance(notification.sent_at, datetime)

    def test_mark_failed(self):
        """测试标记为失败"""
        notification = Notification()
        notification.mark_sending()

        assert notification.failed_at is None
        assert notification.retry_count == 0

        notification.mark_failed("连接失败")

        assert notification.status == NotificationStatus.FAILED
        assert notification.failed_at is not None
        assert notification.error_message == "连接失败"
        assert notification.retry_count == 1

    def test_mark_fallback(self):
        """测试标记为降级发送"""
        notification = Notification()
        notification.mark_sending()

        assert notification.sent_at is None

        notification.mark_fallback()

        assert notification.status == NotificationStatus.FALLBACK
        assert notification.sent_at is not None

    def test_can_retry(self):
        """测试重试判断"""
        notification = Notification(max_retries=3)

        assert notification.can_retry() is True

        notification.mark_sending()
        notification.mark_failed("错误1")
        assert notification.can_retry() is True

        notification.mark_failed("错误2")
        assert notification.can_retry() is True

        notification.mark_failed("错误3")
        assert notification.can_retry() is False

    def test_should_fallback(self):
        """测试降级判断"""
        notification = Notification(
            max_retries=2,
            fallback_enabled=True
        )

        # 未达到重试上限，不应降级
        assert notification.should_fallback() is False

        notification.retry_count = 1
        assert notification.should_fallback() is False

        notification.retry_count = 2
        assert notification.should_fallback() is True

    def test_should_fallback_disabled(self):
        """测试禁用降级"""
        notification = Notification(
            max_retries=2,
            fallback_enabled=False
        )

        notification.retry_count = 2
        assert notification.should_fallback() is False

    def test_is_critical(self):
        """测试紧急通知判断"""
        notif_critical = Notification(priority=NotificationPriority.CRITICAL)
        notif_normal = Notification(priority=NotificationPriority.NORMAL)

        assert notif_critical.is_critical() is True
        assert notif_normal.is_critical() is False

    def test_to_dict(self):
        """测试序列化为字典"""
        notification = Notification(
            notification_type=NotificationType.STOP_LOSS,
            title="止损触发",
            content="测试内容",
            variables={'symbol': '000001', 'price': 10.5},
            priority=NotificationPriority.CRITICAL
        )

        data = notification.to_dict()

        assert data['notification_type'] == 'stop_loss'
        assert data['title'] == "止损触发"
        assert data['content'] == "测试内容"
        assert data['variables'] == {'symbol': '000001', 'price': 10.5}
        assert data['priority'] == 'critical'
        assert data['status'] == 'pending'

    def test_from_dict(self):
        """测试从字典反序列化"""
        data = {
            'notification_id': 'notif_test123',
            'notification_type': 'stop_loss',
            'title': '止损触发',
            'content': '测试内容',
            'variables': {'symbol': '000001'},
            'recipients': [],
            'priority': 'critical',
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'sent_at': None,
            'failed_at': None,
            'retry_count': 0,
            'max_retries': 3,
            'preferred_channels': ['feishu'],
            'fallback_enabled': True,
            'metadata': {},
            'error_message': None,
        }

        notification = Notification.from_dict(data)

        assert notification.notification_id == 'notif_test123'
        assert notification.notification_type == NotificationType.STOP_LOSS
        assert notification.title == '止损触发'
        assert notification.priority == NotificationPriority.CRITICAL
        assert notification.status == NotificationStatus.PENDING

    def test_notification_with_recipients(self):
        """测试带接收者的通知"""
        recipients = [
            NotificationRecipient(
                recipient_type='user',
                recipient_id='user123',
                mention=True
            ),
            NotificationRecipient(
                recipient_type='all',
                mention=True
            )
        ]

        notification = Notification(recipients=recipients)

        assert len(notification.recipients) == 2
        assert notification.recipients[0].recipient_type == 'user'
        assert notification.recipients[0].recipient_id == 'user123'
        assert notification.recipients[0].mention is True

    def test_notification_repr(self):
        """测试字符串表示"""
        notification = Notification(
            notification_type=NotificationType.STOP_LOSS,
            priority=NotificationPriority.CRITICAL
        )

        repr_str = repr(notification)

        assert 'Notification' in repr_str
        assert 'stop_loss' in repr_str
        assert 'critical' in repr_str
        assert 'pending' in repr_str


class TestNotificationRecipient:
    """NotificationRecipient 值对象测试"""

    def test_recipient_creation(self):
        """测试接收者创建"""
        recipient = NotificationRecipient(
            recipient_type='user',
            recipient_id='user123',
            mention=True
        )

        assert recipient.recipient_type == 'user'
        assert recipient.recipient_id == 'user123'
        assert recipient.mention is True

    def test_recipient_defaults(self):
        """测试接收者默认值"""
        recipient = NotificationRecipient(recipient_type='group')

        assert recipient.recipient_type == 'group'
        assert recipient.recipient_id is None
        assert recipient.mention is False
