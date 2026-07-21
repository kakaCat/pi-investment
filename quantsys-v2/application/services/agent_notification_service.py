"""
Agent 通知服务
V2 任务完成后调用此服务通知 Agent
"""
import os
import logging
import structlog
import requests
from typing import Dict, Any, Optional
from datetime import datetime

LOG_FILE = os.getenv('AGENT_NOTIFY_LOG', '/tmp/agent_notify.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = structlog.get_logger(__name__)


class AgentNotificationService:
    """Agent 通知服务

    V2 任务执行完成后，通过此服务唤醒 Agent 进行智能分析和推送
    """

    def __init__(self, agent_url: Optional[str] = None):
        self.agent_url = agent_url or os.getenv('AGENT_API_URL', 'http://localhost:3001')
        self.timeout = int(os.getenv('AGENT_TIMEOUT', '30'))
        self.enabled = os.getenv('AGENT_NOTIFY_ENABLED', 'true').lower() == 'true'

    def notify_agent(self, event: str, data: Dict[str, Any]) -> bool:
        """通知 Agent 处理事件

        Args:
            event: 事件类型 (daily_report, market_alert, position_alert 等)
            data: 事件数据

        Returns:
            是否成功通知
        """
        if not self.enabled:
            logger.debug(f"Agent notify disabled, skipping: {event}")
            return False

        try:
            payload = {
                'event': event,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Notifying Agent: {event}")

            response = requests.post(
                f'{self.agent_url}/wake',
                json=payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"Agent notified successfully: {event}")
                    return True
                else:
                    logger.warning(f"Agent notification failed: {result.get('error')}")
                    return False
            else:
                logger.error(f"Agent API error {response.status_code}: {response.text}")
                return False

        except requests.exceptions.Timeout:
            logger.error(f"Agent notification timeout: {event}")
            return False
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Agent at {self.agent_url}")
            return False
        except Exception as e:
            logger.error(f"Failed to notify Agent: {e}")
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
