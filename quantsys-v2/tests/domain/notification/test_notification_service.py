"""
通知服务单元测试

测试 NotificationService 的发送流程、重试、降级逻辑

Author: System
Date: 2026-09-02
"""

import pytest
from unittest.mock import Mock, MagicMock

from domain.notification.models.notification import (
    Notification,
    NotificationType,
    NotificationPriority,
    NotificationStatus,
)
from domain.notification.models.channel import (
    NotificationChannel,
    ChannelResult,
)
from domain.notification.services.notification_service import NotificationService
from domain.notification.policies.notification_policy import NotificationPolicy


class TestNotificationService:
    """NotificationService 测试"""

    def test_send_success(self):
        """测试发送成功"""
        # Mock 渠道
        mock_channel = Mock(spec=NotificationChannel)
        mock_channel.get_name.return_value = "feishu"
        mock_channel.send.return_value = ChannelResult.ok("发送成功")
        mock_channel.supports.return_value = True

        # 创建服务
        policy = NotificationPolicy()
        service = NotificationService(
            channels=[mock_channel],
            policy=policy
        )

        # 创建通知
        notification = Notification(
            notification_type=NotificationType.STOP_LOSS,
            title="止损触发",
            content="测试内容",
            preferred_channels=['feishu']
        )

        # 发送
        result = service.send(notification)

        # 断言
        assert result.success is True
        assert notification.status == NotificationStatus.SENT
        assert notification.sent_at is not None
        mock_channel.send.assert_called_once()

    def test_send_channel_not_available(self):
        """测试渠道不可用"""
        policy = NotificationPolicy()
        service = NotificationService(
            channels=[],  # 没有渠道
            policy=policy
        )

        notification = Notification(
            notification_type=NotificationType.STOP_LOSS,
            title="止损触发"
        )

        result = service.send(notification)

        assert result.success is False
        assert "没有可用的通知渠道" in result.message
        assert notification.status == NotificationStatus.FAILED

    def test_send_with_fallback_success(self):
        """测试降级发送成功"""
        # Mock Agent 失败
        mock_agent = Mock(spec=NotificationChannel)
        mock_agent.get_name.return_value = "agent"
        mock_agent.send.return_value = ChannelResult.error("连接失败")

        # Mock 飞书成功
        mock_feishu = Mock(spec=NotificationChannel)
        mock_feishu.get_name.return_value = "feishu"
        mock_feishu.send.return_value = ChannelResult.ok("发送成功")

        # 创建服务
        policy = NotificationPolicy()
        service = NotificationService(
            channels=[mock_agent, mock_feishu],
            policy=policy
        )

        notification = Notification(
            notification_type=NotificationType.WATCH_TRIGGERED,
            title="盯盘触发"
        )

        # 带降级发送
        result = service.send_with_fallback(notification, 'agent', 'feishu')

        # 断言
        assert result.success is True
        assert notification.status == NotificationStatus.FALLBACK
        mock_agent.send.assert_called_once()
        mock_feishu.send.assert_called_once()

    def test_send_with_fallback_both_failed(self):
        """测试主渠道和降级渠道都失败"""
        # Mock Agent 失败
        mock_agent = Mock(spec=NotificationChannel)
        mock_agent.get_name.return_value = "agent"
        mock_agent.send.return_value = ChannelResult.error("Agent 连接失败")

        # Mock 飞书失败
        mock_feishu = Mock(spec=NotificationChannel)
        mock_feishu.get_name.return_value = "feishu"
        mock_feishu.send.return_value = ChannelResult.error("飞书连接失败")

        policy = NotificationPolicy()
        service = NotificationService(
            channels=[mock_agent, mock_feishu],
            policy=policy
        )

        notification = Notification(
            notification_type=NotificationType.WATCH_TRIGGERED
        )

        result = service.send_with_fallback(notification, 'agent', 'feishu')

        assert result.success is False
        assert notification.status == NotificationStatus.FALLBACK

    def test_send_multiple_channels_fallback(self):
        """测试多渠道按优先级尝试"""
        # Mock 第一个渠道失败
        mock_channel1 = Mock(spec=NotificationChannel)
        mock_channel1.get_name.return_value = "channel1"
        mock_channel1.send.return_value = ChannelResult.error("失败1")
        mock_channel1.supports.return_value = True

        # Mock 第二个渠道成功
        mock_channel2 = Mock(spec=NotificationChannel)
        mock_channel2.get_name.return_value = "channel2"
        mock_channel2.send.return_value = ChannelResult.ok("成功")
        mock_channel2.supports.return_value = True

        policy = NotificationPolicy()
        service = NotificationService(
            channels=[mock_channel1, mock_channel2],
            policy=policy
        )

        notification = Notification(
            notification_type=NotificationType.STOP_LOSS,
            preferred_channels=['channel1', 'channel2']
        )

        result = service.send(notification)

        assert result.success is True
        assert notification.status == NotificationStatus.SENT
        mock_channel1.send.assert_called_once()
        mock_channel2.send.assert_called_once()

    def test_send_with_repository(self):
        """测试发送时保存到仓储"""
        mock_channel = Mock(spec=NotificationChannel)
        mock_channel.get_name.return_value = "feishu"
        mock_channel.send.return_value = ChannelResult.ok()
        mock_channel.supports.return_value = True

        mock_repository = Mock()

        policy = NotificationPolicy()
        service = NotificationService(
            channels=[mock_channel],
            policy=policy,
            repository=mock_repository
        )

        notification = Notification(
            notification_type=NotificationType.STOP_LOSS,
            preferred_channels=['feishu']
        )

        service.send(notification)

        # 仓储应该被调用两次：mark_sending 后和 mark_sent 后
        assert mock_repository.save.call_count == 2

    def test_get_available_channels(self):
        """测试获取可用渠道列表"""
        mock_channel1 = Mock(spec=NotificationChannel)
        mock_channel1.get_name.return_value = "feishu"

        mock_channel2 = Mock(spec=NotificationChannel)
        mock_channel2.get_name.return_value = "agent"

        policy = NotificationPolicy()
        service = NotificationService(
            channels=[mock_channel1, mock_channel2],
            policy=policy
        )

        channels = service.get_available_channels()

        assert len(channels) == 2
        assert 'feishu' in channels
        assert 'agent' in channels

    def test_healthcheck_all(self):
        """测试健康检查所有渠道"""
        mock_channel1 = Mock(spec=NotificationChannel)
        mock_channel1.get_name.return_value = "feishu"
        mock_channel1.healthcheck.return_value = True

        mock_channel2 = Mock(spec=NotificationChannel)
        mock_channel2.get_name.return_value = "agent"
        mock_channel2.healthcheck.return_value = False

        policy = NotificationPolicy()
        service = NotificationService(
            channels=[mock_channel1, mock_channel2],
            policy=policy
        )

        health = service.healthcheck_all()

        assert health['feishu'] is True
        assert health['agent'] is False

    def test_send_with_exception_handling(self):
        """测试发送异常处理"""
        mock_channel = Mock(spec=NotificationChannel)
        mock_channel.get_name.return_value = "feishu"
        mock_channel.send.side_effect = Exception("未知异常")
        mock_channel.supports.return_value = True

        policy = NotificationPolicy()
        service = NotificationService(
            channels=[mock_channel],
            policy=policy
        )

        notification = Notification(
            notification_type=NotificationType.STOP_LOSS,
            preferred_channels=['feishu']
        )

        result = service.send(notification)

        # 异常应该被捕获并返回错误结果
        assert result.success is False
        assert "渠道异常" in result.message


class TestChannelResult:
    """ChannelResult 测试"""

    def test_ok_result(self):
        """测试成功结果"""
        result = ChannelResult.ok("发送成功")

        assert result.success is True
        assert result.delivered is True
        assert result.message == "发送成功"
        assert bool(result) is True

    def test_timeout_result(self):
        """测试超时结果"""
        result = ChannelResult.timeout("请求超时")

        assert result.success is True  # 超时标记为成功（避免重试）
        assert result.delivered is False  # 但无法确认送达
        assert "超时" in result.message

    def test_error_result(self):
        """测试失败结果"""
        result = ChannelResult.error("连接失败")

        assert result.success is False
        assert result.delivered is False
        assert result.message == "连接失败"
        assert bool(result) is False

    def test_result_with_metadata(self):
        """测试带元数据的结果"""
        result = ChannelResult.ok(
            message="发送成功",
            metadata={'message_id': 'msg123', 'trace_id': 'trace456'}
        )

        assert result.metadata['message_id'] == 'msg123'
        assert result.metadata['trace_id'] == 'trace456'

    def test_result_repr(self):
        """测试字符串表示"""
        result = ChannelResult.ok("发送成功")
        repr_str = repr(result)

        assert 'SUCCESS' in repr_str
        assert '发送成功' in repr_str
