"""
Agent 通知服务
V2 任务完成后调用此服务通知 Agent
"""
import logging
import structlog
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from infrastructure.config import get_config

config = get_config()

LOG_FILE = config.external.agent_notify_log
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

    def __init__(self, agent_url: Optional[str] = None, timeout: Optional[int] = None):
        config = get_config()
        self.agent_url = agent_url or config.external.agent_api_url
        # timeout 显式传入优先（如盯盘路径需要更短超时），否则读配置
        self.timeout = timeout if timeout is not None else config.external.agent_timeout
        self.enabled = config.external.agent_notify_enabled
        self.token = config.external.agent_api_token

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
