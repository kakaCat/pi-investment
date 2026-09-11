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

# ── 多目标投递（2026-09-11，w-aebfddcd）────────────────────────────────────────
# 用户定调：「盯盘要给 agent 处理，按照分类投递 agent-ts 或者 agent-dh」。
# 分类 → agent 的**决策**在 domain/notification/policies/watch_delivery_policy.py，
# 本服务只负责"把事件送到指定 agent 的 wake 端点"这一件传输层的事。
AGENT_DH = 'agent-dh'
AGENT_TS = 'agent-ts'
DEFAULT_TARGET = AGENT_DH

#: agent 键 → 默认 wake 基地址
#:   agent-dh :13080 = DSH investment profile（当前唯一在线，POST /wake）
#:   agent-ts :3002  = 旧版 TS agent（npm run wake，需显式拉起；未在线时投递层会回退）
DEFAULT_TARGET_URLS = {
    AGENT_DH: 'http://127.0.0.1:13080',
    AGENT_TS: 'http://127.0.0.1:3002',
}

#: agent 键 → 覆盖用环境变量（按序取第一个非空）
TARGET_URL_ENVS = {
    AGENT_DH: ('AGENT_API_URL_DH', 'AGENT_API_URL'),
    AGENT_TS: ('AGENT_API_URL_TS',),
}


class AgentNotificationService:
    """Agent 通知服务

    V2 任务执行完成后，通过此服务唤醒 Agent 进行智能分析和推送
    """

    def __init__(self, agent_url: Optional[str] = None, timeout: Optional[int] = None,
                 targets: Optional[Dict[str, str]] = None):
        #: 显式传入的地址（最高优先级）：历史契约——构造时给 agent_url 即指定默认 agent 的落点
        self._explicit_url = agent_url.rstrip('/') if agent_url else None
        #: 默认落点：显式传入 > AGENT_API_URL_DH > AGENT_API_URL > 内置默认
        self.agent_url = (self._explicit_url or self._env_url(DEFAULT_TARGET)
                          or DEFAULT_TARGET_URLS[DEFAULT_TARGET]).rstrip('/')
        #: agent 键 → 基地址覆盖（不传则由 env 解析）
        self.targets = dict(targets) if targets else {}
        # timeout 显式传入优先（如盯盘路径需要更短超时），否则读环境变量
        # 默认 300s（5min）：daily_review 等复杂事件需要多轮工具调用，30s 必然超时
        self.timeout = timeout if timeout is not None else int(os.getenv('AGENT_TIMEOUT', '300'))
        self.enabled = os.getenv('AGENT_NOTIFY_ENABLED', 'true').lower() == 'true'
        self.token = os.getenv('AGENT_API_TOKEN')

    def notify_agent(self, event: str, data: Dict[str, Any], target: Optional[str] = None) -> bool:
        """通知 Agent 处理事件

        Args:
            event: 事件类型 (daily_report, market_alert, position_alert 等)
            data: 事件数据
            target: 处置该事件的 agent 键（agent-dh / agent-ts）；None=默认 agent

        Returns:
            是否成功通知
        """
        return self.notify_agent_detailed(event, data, target=target) == 'ok'

    # ── 目标解析（分类→agent 的决策在 domain 策略，这里只解析地址）──────
    @staticmethod
    def _env_url(target: str) -> Optional[str]:
        for key in TARGET_URL_ENVS.get(target, ()):
            val = os.getenv(key)
            if val and val.strip():
                return val.strip().rstrip('/')
        return None

    def resolve_target_url(self, target: Optional[str] = None) -> str:
        """agent 键 → wake 基地址（显式 targets > 环境变量 > 内置默认 > 历史 agent_url）"""
        key = target or DEFAULT_TARGET
        if self.targets.get(key):
            return str(self.targets[key]).rstrip('/')
        if self._explicit_url and key == DEFAULT_TARGET:
            # 构造显式传入的 agent_url 就是默认 agent 的地址（不得被环境变量悄悄盖掉）
            return self._explicit_url
        return (self._env_url(key) or DEFAULT_TARGET_URLS.get(key)
                or self.agent_url).rstrip('/')

    def notify_agent_detailed(self, event: str, data: Dict[str, Any],
                              target: Optional[str] = None) -> str:
        """通知指定 agent 并返回详细结果（按分类投递，见 watch_delivery_policy）

        Args:
            target: 处置 agent 键（agent-dh / agent-ts）；None = 默认 agent

        Returns:
            'ok'      - 成功送达并确认
            'timeout' - 请求超时（事件大概率已送达，Agent 正在处理，不应重试）
            'error'   - 连接失败/其他错误（事件未送达，可重试）
            'disabled'- 通知被禁用

        回退纪律（2026-09-11，w-aebfddcd）：目标 agent 连接失败时回退到默认 agent，
        并在 payload 里标注 delivery_target / delivery_fallback_from ——
        **绝不静默丢事件**（盯盘事件里有止损这类不能丢的东西）。
        """
        if not self.enabled:
            logger.debug(f"Agent notify disabled, skipping: {event}")
            return 'disabled'

        key = target or DEFAULT_TARGET
        url = self.resolve_target_url(key)
        status, detail = self._post_once(url, event, data, target_key=key)

        if status == 'error' and key != DEFAULT_TARGET:
            fallback_url = self.resolve_target_url(DEFAULT_TARGET)
            # structlog 的 event= 是保留字段（日志正文），业务字段一律用 notify_event
            logger.error("目标 agent 投递失败，回退默认 agent",
                         notify_event=event, target=key, url=url, detail=str(detail)[:200])
            fb_data = dict(data or {})
            fb_data['delivery_target'] = key
            fb_data['delivery_fallback_from'] = key
            fb_data['delivery_fallback_reason'] = str(detail)[:200]
            status, detail = self._post_once(fallback_url, event, fb_data,
                                             target_key=DEFAULT_TARGET)
            if status == 'ok':
                logger.warning("回退投递成功", notify_event=event,
                               target=key, fallback=DEFAULT_TARGET)
        return status

    def _post_once(self, url: str, event: str, data: Dict[str, Any],
                   target_key: Optional[str] = None) -> tuple:
        """单次投递：返回 (status, detail)"""
        try:
            payload = {
                'event': event,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }

            logger.info("Notifying Agent", notify_event=event, target=target_key, url=url)

            headers = {'Content-Type': 'application/json'}
            if self.token:
                headers['X-Wake-Token'] = self.token
            response = requests.post(
                f'{url}/wake',
                json=payload,
                timeout=self.timeout,
                headers=headers
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"Agent notified successfully: {event}")
                    return 'ok', None
                detail = str(result.get('error'))[:200]
                logger.warning(f"Agent notification failed: {detail}")
                return 'error', detail
            detail = f"HTTP {response.status_code}: {response.text[:200]}"
            logger.error(f"Agent API error {detail}")
            return 'error', detail

        except requests.exceptions.Timeout:
            logger.error(f"Agent notification timeout: {event}")
            return 'timeout', 'timeout'
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Agent at {url}")
            return 'error', f'cannot connect: {url}'
        except Exception as e:
            logger.error(f"Failed to notify Agent: {e}")
            return 'error', str(e)[:200]

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
