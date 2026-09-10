"""
Agent OS 通知渠道实现

通过 Agent OS 通知网关投递通知（HTTP POST /api/v1/notifications/send），支持：
1. 统一消息网关路由（v2 通知优先走 Agent OS，由 OS 负责最终外发与留痕）
2. 超时区分（连接超时 vs 响应超时，超时标记为"可能已送达"避免重复发送）
3. 可选 Token 认证

Author: System
Date: 2026-09-02

2026-09-11 契约修复（w-23c70356）：
    原实现 POST {agent_url}/wake 是旧版 wake-channel 网关（默认 :3002）的契约，该服务早已不存在；
    实测 AgentChannel.send() 恒失败（"无法连接到 Agent: http://localhost:3002"），
    导致 NotificationPolicy 里写好的「agent 优先、feishu 降级」从未生效（每次都静默降级飞书）。
    Agent OS 现运行于 :8080，通知入口为 POST /api/v1/notifications/send，
    请求体 {channel,title,content,urgency,color?,metadata?}，响应 {"log_id","success","error"?,"message_id"?}
    （渠道码见 public.notification_channels：alerts / reports / trading）。
"""

import requests
import structlog
from typing import Any, Dict, Optional

from domain.notification.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
)
from domain.notification.models.channel import NotificationChannel, ChannelResult

logger = structlog.get_logger(__name__)


# 通知类型 → Agent OS 渠道码映射（未覆盖的类型按优先级兜底）
TRADING_NOTIFICATION_TYPES = {
    NotificationType.TRADE_SIGNAL,
    NotificationType.REBALANCE,
    NotificationType.STOP_LOSS,
    NotificationType.TAKE_PROFIT,
    NotificationType.VERIFICATION,
}
ALERT_NOTIFICATION_TYPES = {
    NotificationType.RISK_ALERT,
    NotificationType.SYSTEM_ALERT,
}
OS_TRADING_CHANNEL = "trading"
OS_ALERT_CHANNEL = "alerts"
OS_REPORT_CHANNEL = "reports"


class AgentChannel(NotificationChannel):
    """Agent OS 通知渠道

    职责：
    1. 把通知投递给 Agent OS 网关（由 OS 决定最终外发渠道与格式）
    2. 处理超时场景（区分连接超时和响应超时）
    3. 提供可选 Token 认证

    配置：
    - agent_url: Agent OS 基地址（如 http://localhost:8080）
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
            agent_url: Agent OS 基地址（如 http://localhost:8080）
            timeout: 响应超时时间（秒）
            token: 认证 Token（可选）
        """
        self.agent_url = agent_url.rstrip("/")
        self.timeout = timeout
        self.token = token

        logger.info(
            "AgentChannel initialized",
            agent_os_url=agent_url,
            timeout=timeout,
            token_configured=bool(token)
        )

    # ------------------------------------------------------------------ 内部
    def resolve_channel_code(self, notification: Notification) -> str:
        """决定投递到 Agent OS 的哪个渠道码

        规则（自上而下）：
        1. notification.variables["os_channel"] 显式指定（调用方可覆盖）
        2. 交易类通知 → trading
        3. 风险/系统告警，或优先级 high/critical → alerts
        4. 其余 → reports
        """
        override = (notification.variables or {}).get("os_channel")
        if isinstance(override, str) and override.strip():
            return override.strip()

        if notification.notification_type in TRADING_NOTIFICATION_TYPES:
            return OS_TRADING_CHANNEL

        if (
            notification.notification_type in ALERT_NOTIFICATION_TYPES
            or notification.priority in (NotificationPriority.HIGH, NotificationPriority.CRITICAL)
        ):
            return OS_ALERT_CHANNEL

        return OS_REPORT_CHANNEL

    def _build_metadata(self, notification: Notification) -> Dict[str, Any]:
        """构建 OS metadata（只保留可 JSON 序列化的值，避免序列化失败）"""
        allowed = (str, int, float, bool, list, dict, type(None))
        metadata: Dict[str, Any] = {
            "source": "quantsys-v2",
            "notification_id": notification.notification_id,
            "notification_type": notification.notification_type.value,
        }
        for key, value in (notification.variables or {}).items():
            if key == "os_channel":
                continue
            if isinstance(value, allowed):
                metadata[key] = value
        return metadata

    # ------------------------------------------------------------------ 发送
    def send(self, notification: Notification) -> ChannelResult:
        """投递通知到 Agent OS

        Args:
            notification: 通知对象

        Returns:
            ChannelResult: 投递结果（success=False 时由 NotificationService 降级下一渠道）
        """
        channel_code = None
        try:
            channel_code = self.resolve_channel_code(notification)
            payload = {
                "channel": channel_code,
                "title": notification.title or notification.notification_type.value,
                "content": notification.content or "",
                "urgency": notification.priority.value,
                "metadata": self._build_metadata(notification),
            }

            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["X-Wake-Token"] = self.token

            logger.debug(
                "投递 Agent OS",
                notification_id=notification.notification_id,
                notification_type=notification.notification_type.value,
                os_channel=channel_code
            )

            # 区分连接超时和响应超时: (connect_timeout, read_timeout)
            response = requests.post(
                f"{self.agent_url}/api/v1/notifications/send",
                json=payload,
                headers=headers,
                timeout=(3, self.timeout)
            )

            if response.status_code == 200:
                try:
                    result = response.json()
                except ValueError:
                    result = {}

                if result.get("success"):
                    logger.info(
                        "Agent OS 投递成功",
                        notification_id=notification.notification_id,
                        os_channel=channel_code,
                        log_id=result.get("log_id")
                    )
                    return ChannelResult.ok(
                        message="Agent OS 投递成功",
                        metadata={
                            "os_channel": channel_code,
                            "log_id": result.get("log_id"),
                            "message_id": result.get("message_id"),
                        }
                    )

                error_msg = f"Agent OS 处理失败: {result.get('error') or response.text[:200]}"
                logger.error(
                    error_msg,
                    notification_id=notification.notification_id,
                    response=result
                )
                return ChannelResult.error(error_msg)

            error_msg = f"Agent OS API 错误 {response.status_code}: {response.text[:200]}"
            logger.error(
                error_msg,
                notification_id=notification.notification_id,
                status_code=response.status_code
            )
            return ChannelResult.error(error_msg)

        except requests.exceptions.ConnectTimeout:
            error_msg = "Agent OS 连接超时（未送达）"
            logger.error(
                error_msg,
                notification_id=notification.notification_id,
                agent_os_url=self.agent_url
            )
            return ChannelResult.error(error_msg)

        except requests.exceptions.ReadTimeout:
            # 2026-09-11（w-23c70356）语义修正：原返回 ChannelResult.timeout()（success=True）
            # 会让 NotificationService 认为已送达并**跳过飞书降级**——对告警类通知而言漏发比重复
            # 更严重（OS 网关实测 <1s，>timeout 属病态），故如实报 error，交由策略降级下一渠道。
            error_msg = "Agent OS 响应超时（未能确认送达，降级下一渠道）"
            logger.warning(
                error_msg,
                notification_id=notification.notification_id,
                timeout=self.timeout
            )
            return ChannelResult.error(error_msg)

        except requests.exceptions.ConnectionError as e:
            error_msg = f"无法连接到 Agent OS: {self.agent_url}"
            logger.error(
                error_msg,
                notification_id=notification.notification_id,
                error=str(e)
            )
            return ChannelResult.error(error_msg)

        except Exception as e:
            error_msg = f"Agent OS 投递异常: {str(e)}"
            logger.error(
                error_msg,
                notification_id=notification.notification_id,
                error=str(e),
                exc_info=True
            )
            return ChannelResult.error(error_msg)

    # ------------------------------------------------------------------ 元信息
    def supports(self, notification_type: NotificationType) -> bool:
        """Agent OS 支持所有类型（由 OS 自行决定如何处理）

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
        """健康检查：探测 Agent OS /health

        Returns:
            bool: Agent OS 是否可用
        """
        try:
            response = requests.get(
                f"{self.agent_url}/health",
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
