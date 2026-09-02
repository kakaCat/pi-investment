"""
Agent 唤醒渠道实现

通过 HTTP POST 唤醒 Agent 处理通知事件，支持：
1. 事件唤醒（/wake 接口）
2. 超时区分（连接超时 vs 响应超时）
3. Token 认证

Author: System
Date: 2026-09-02
"""

import requests
import structlog
from typing import Optional

from domain.notification.models.notification import Notification, NotificationType
from domain.notification.models.channel import NotificationChannel, ChannelResult

logger = structlog.get_logger(__name__)


class AgentChannel(NotificationChannel):
    """Agent 唤醒渠道

    职责：
    1. 唤醒 Agent 处理事件
    2. 处理超时场景（区分连接超时和响应超时）
    3. 提供 Token 认证

    配置：
    - agent_url: Agent API 地址
    - timeout: 响应超时时间（秒）
    - token: 认证 Token（可选）
    """

    def __init__(
        self,
        agent_url: str,
        timeout: int = 30,
        token: Optional[str] = None
    ):
        """初始化 Agent 渠道

        Args:
            agent_url: Agent API 地址（如 http://127.0.0.1:3002）
            timeout: 响应超时时间（秒）
            token: 认证 Token（可选）
        """
        self.agent_url = agent_url.rstrip('/')
        self.timeout = timeout
        self.token = token

        logger.info(
            "AgentChannel initialized",
            agent_url=agent_url,
            timeout=timeout,
            token_configured=bool(token)
        )

    def send(self, notification: Notification) -> ChannelResult:
        """唤醒 Agent

        Args:
            notification: 通知对象

        Returns:
            ChannelResult: 发送结果
        """
        try:
            # 构建 Agent 事件载荷
            payload = {
                'event': notification.notification_type.value,
                'data': {
                    'notification_id': notification.notification_id,
                    'title': notification.title,
                    'content': notification.content,
                    **notification.variables
                },
                'timestamp': notification.created_at.isoformat()
            }

            headers = {'Content-Type': 'application/json'}
            if self.token:
                headers['X-Wake-Token'] = self.token

            logger.debug(
                "唤醒 Agent",
                notification_id=notification.notification_id,
                event=notification.notification_type.value
            )

            # 区分连接超时和响应超时
            # (connect_timeout, read_timeout)
            response = requests.post(
                f'{self.agent_url}/wake',
                json=payload,
                headers=headers,
                timeout=(3, self.timeout)
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(
                        "Agent 唤醒成功",
                        notification_id=notification.notification_id
                    )
                    return ChannelResult.ok(
                        message="Agent 唤醒成功",
                        metadata={'response': result}
                    )
                else:
                    error_msg = f"Agent 处理失败: {result.get('error')}"
                    logger.error(
                        error_msg,
                        notification_id=notification.notification_id,
                        response=result
                    )
                    return ChannelResult.error(error_msg)
            else:
                error_msg = f"Agent API 错误 {response.status_code}: {response.text}"
                logger.error(
                    error_msg,
                    notification_id=notification.notification_id,
                    status_code=response.status_code
                )
                return ChannelResult.error(error_msg)

        except requests.exceptions.ConnectTimeout:
            error_msg = "Agent 连接超时（未送达）"
            logger.error(
                error_msg,
                notification_id=notification.notification_id,
                agent_url=self.agent_url
            )
            return ChannelResult.error(error_msg)

        except requests.exceptions.ReadTimeout:
            # 响应超时：请求可能已送达，Agent 正在处理
            logger.warning(
                "Agent 响应超时（可能已送达）",
                notification_id=notification.notification_id,
                timeout=self.timeout
            )
            return ChannelResult.timeout("Agent 响应超时（可能已送达）")

        except requests.exceptions.ConnectionError as e:
            error_msg = f"无法连接到 Agent: {self.agent_url}"
            logger.error(
                error_msg,
                notification_id=notification.notification_id,
                error=str(e)
            )
            return ChannelResult.error(error_msg)

        except Exception as e:
            error_msg = f"Agent 唤醒异常: {str(e)}"
            logger.error(
                error_msg,
                notification_id=notification.notification_id,
                error=str(e),
                exc_info=True
            )
            return ChannelResult.error(error_msg)

    def supports(self, notification_type: NotificationType) -> bool:
        """Agent 支持所有类型（由 Agent 自行决定如何处理）

        Args:
            notification_type: 通知类型

        Returns:
            bool: 始终返回 True
        """
        return True

    def get_name(self) -> str:
        """获取渠道名称

        Returns:
            str: 'agent'
        """
        return "agent"

    def healthcheck(self) -> bool:
        """健康检查：尝试连接 Agent

        Returns:
            bool: Agent 是否可用
        """
        try:
            response = requests.get(
                f'{self.agent_url}/health',
                timeout=3
            )
            is_healthy = response.status_code == 200
            logger.debug(
                "AgentChannel healthcheck",
                is_healthy=is_healthy,
                status_code=response.status_code
            )
            return is_healthy
        except Exception as e:
            logger.debug(
                "AgentChannel healthcheck failed",
                error=str(e)
            )
            return False
