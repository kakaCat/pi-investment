"""
测试 AgentNotificationService 双模式通知
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from application.services.agent_notification_service import AgentNotificationService


class TestAgentNotificationService:
    """测试 Agent 通知服务"""

    def setup_method(self):
        """每个测试前初始化"""
        self.service = AgentNotificationService(
            agent_url='http://127.0.0.1:3002',
            timeout=5
        )

    def test_send_notification_success(self):
        """测试直接发送通知成功"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = self.service.send_notification(
                title='测试通知',
                content='测试内容',
                channel='feishu',
                priority='normal'
            )

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == 'http://127.0.0.1:8080/api/v1/notifications/send'
            assert call_args[1]['json'] == {
                'channel': 'feishu',
                'title': '测试通知',
                'content': '测试内容',
                'priority': 'normal',
            }

    def test_send_notification_failure(self):
        """测试直接发送通知失败"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_post.return_value = mock_response

            result = self.service.send_notification(
                title='测试通知',
                content='测试内容'
            )

            assert result is False

    def test_send_notification_timeout(self):
        """测试直接发送通知超时"""
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("Timeout")

            result = self.service.send_notification(
                title='测试通知',
                content='测试内容'
            )

            assert result is False

    def test_send_notification_disabled(self):
        """测试通知服务被禁用"""
        self.service.enabled = False

        with patch('requests.post') as mock_post:
            result = self.service.send_notification(
                title='测试通知',
                content='测试内容'
            )

            # 禁用时不应该调用 API
            mock_post.assert_not_called()
            assert result is False

    def test_notify_agent_still_works(self):
        """测试旧的 notify_agent 方法仍然可用"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = self.service.notify_agent('test_event', {'key': 'value'})

            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert '/wake' in call_args[0][0]

    def test_send_notification_custom_channel(self):
        """测试自定义通知渠道"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = self.service.send_notification(
                title='测试通知',
                content='测试内容',
                channel='email',
                priority='high'
            )

            assert result is True
            call_args = mock_post.call_args
            assert call_args[1]['json']['channel'] == 'email'
            assert call_args[1]['json']['priority'] == 'high'
