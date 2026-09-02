"""
Agent 通知服务
V2 任务完成后调用此服务通知 Agent
"""
import os
import structlog
import requests
from typing import Dict, Any, Optional
from datetime import datetime

logger = structlog.get_logger(__name__)


class AgentNotificationService:
    """Agent 通知服务 - 双模式架构

    支持两种通知模式：
    1. Wake 模式 (notify_agent): 唤醒 Agent 进行智能分析和决策 - 高 token 消耗
    2. Direct Send 模式 (send_notification): 直接发送通知不唤醒 Agent - 零 token 消耗

    选择原则：
    - 需要 Agent 决策的场景（如 agent 自己账户交易）使用 Wake 模式
    - 不需要决策的通知（盯盘触发、风险告警、日报等）使用 Direct Send 模式
    """

    def __init__(self, agent_url: Optional[str] = None, timeout: Optional[int] = None):
        # Agent 唤醒端点（旧模式，/wake）
        self.agent_url = agent_url or os.getenv('AGENT_API_URL', 'http://127.0.0.1:3002')
        # Agent OS 通知端点（新模式，/api/v1/notifications/send）
        self.agent_os_url = os.getenv('AGENT_OS_URL', 'http://127.0.0.1:8080')
        # timeout 显式传入优先（如盯盘路径需要更短超时），否则读环境变量
        self.timeout = timeout if timeout is not None else int(os.getenv('AGENT_TIMEOUT', '30'))
        self.enabled = os.getenv('AGENT_NOTIFY_ENABLED', 'true').lower() == 'true'
        self.token = os.getenv('AGENT_API_TOKEN')

    def notify_agent(self, event: str, data: Dict[str, Any]) -> bool:
        """通知 Agent 处理事件

        Args:
            event: 事件类型 (daily_report, market_alert, position_alert 等)
            data: 事件数据

        Returns:
            是否成功通知
        """
        return self.notify_agent_detailed(event, data) == 'ok'

    def notify_agent_detailed(self, event: str, data: Dict[str, Any]) -> str:
        """通知 Agent 并返回详细结果

        Returns:
            'ok'      - 成功送达并确认
            'timeout' - 请求超时（事件大概率已送达，Agent 正在处理，不应重试）
            'error'   - 连接失败/其他错误（事件未送达，可重试）
            'disabled'- 通知被禁用
        """
        if not self.enabled:
            logger.debug(f"Agent notify disabled, skipping: {event}")
            return 'disabled'

        try:
            payload = {
                'event': event,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Notifying Agent: {event}")

            headers = {'Content-Type': 'application/json'}
            if self.token:
                headers['X-Wake-Token'] = self.token
            response = requests.post(
                f'{self.agent_url}/wake',
                json=payload,
                timeout=self.timeout,
                headers=headers
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"Agent notified successfully: {event}")
                    return 'ok'
                else:
                    logger.warning(f"Agent notification failed: {result.get('error')}")
                    return 'error'
            else:
                logger.error(f"Agent API error {response.status_code}: {response.text}")
                return 'error'

        except requests.exceptions.Timeout:
            logger.error(f"Agent notification timeout: {event}")
            return 'timeout'
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Agent at {self.agent_url}")
            return 'error'
        except Exception as e:
            logger.error(f"Failed to notify Agent: {e}")
            return 'error'

    def send_notification(self, title: str, content: str,
                         channel: str = 'feishu',
                         priority: str = 'normal') -> bool:
        """直接发送通知（不唤醒 Agent）- Direct Send 模式

        调用 agent-os 的 /api/v1/notifications/send 端点，agent-os 负责：
        1. 记录通知到数据库（notification_logs 表）
        2. 直接发送到飞书（或其他渠道）

        这种模式下 Agent 不参与，零 token 消耗。适用于大部分不需要智能分析的通知场景。

        Args:
            title: 通知标题
            content: 通知内容（支持 Markdown 格式）
            channel: 通知渠道代码（默认 'feishu'）
            priority: 优先级 (low/normal/high/urgent)

        Returns:
            是否成功发送
        """
        if not self.enabled:
            logger.debug(f"Agent notify disabled, skipping direct send: {title}")
            return False

        try:
            payload = {
                'channel': channel,
                'title': title,
                'content': content,
                'priority': priority,
            }

            logger.info(f"Sending notification directly via agent-os: {title}")

            response = requests.post(
                f'{self.agent_os_url}/api/v1/notifications/send',
                json=payload,
                timeout=10,  # 直接发送用较短超时
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Notification sent successfully: {title}")
                return True
            else:
                logger.error(f"Agent OS notification API error {response.status_code}: {response.text}")
                return False

        except requests.exceptions.Timeout:
            logger.error(f"Agent OS notification timeout: {title}")
            return False
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Agent OS at {self.agent_os_url}")
            return False
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def send_reminder(self, agent_id: str, message: str,
                      remind_at: Optional[str] = None) -> bool:
        """发送提醒事件给 Agent（调度任务 agent_reminder 使用）

        Args:
            agent_id: Agent ID
            message: 提醒消息
            remind_at: 提醒时间（可选，仅作上下文记录）

        Returns:
            是否成功通知
        """
        return self.notify_agent('agent_reminder', {
            'agent_id': agent_id,
            'message': message,
            'remind_at': remind_at,
        })


# 全局单例
agent_service = AgentNotificationService()
