"""WatchEngine 触发通知器：唤醒 Agent + WS 广播 + 审计落库"""
import time
from typing import Optional

import requests
import structlog

logger = structlog.get_logger(__name__)


class WatchNotifier:
    def __init__(self, agent_service, trigger_repo=None,
                 ws_url: Optional[str] = 'http://127.0.0.1:5003/broadcast/market_data',
                 max_retries: int = 3, retry_interval: float = 1.0):
        self.agent_service = agent_service
        self.trigger_repo = trigger_repo
        self.ws_url = ws_url
        self.max_retries = max_retries
        self.retry_interval = retry_interval

    def notify(self, rule, condition: dict, quote, result) -> bool:
        """触发通知。返回是否成功唤醒 Agent（失败也落库待补发）"""
        payload = self._build_payload(rule, condition, quote, result)
        notified = self._notify_agent_with_retry(payload)
        self._broadcast_ws(payload)
        self._record(rule, condition, quote, result, notified)
        return notified

    def _build_payload(self, rule, condition, quote, result) -> dict:
        price = float(quote.price)
        change_pct = None
        if getattr(quote, 'prev_close', None):
            change_pct = round((price - float(quote.prev_close)) / float(quote.prev_close) * 100, 2)
        elif getattr(quote, 'change_pct', None) is not None:
            change_pct = float(quote.change_pct)
        pnl_pct = None
        cost = getattr(rule, 'cost_price', None)
        if cost:
            pnl_pct = round((price - float(cost)) / float(cost) * 100, 2)
        return {
            'rule_id': rule.id,
            'symbol': rule.symbol,
            'name': getattr(quote, 'name', None),
            'price': price,
            'change_pct': change_pct,
            'pnl_pct': pnl_pct,
            'condition': condition,
            'message': result.message,
            'context': getattr(rule, 'context', None),
        }

    def _notify_agent_with_retry(self, payload) -> bool:
        for attempt in range(1, self.max_retries + 1):
            result = self.agent_service.notify_agent_detailed('watch_triggered', payload)
            if result == 'ok':
                return True
            if result == 'timeout':
                # 事件大概率已送达（wake 同步等待 LLM 决策，超时是常态），不重试避免重复唤醒
                logger.info('唤醒 Agent 超时（事件已送达，不重试）', symbol=payload['symbol'])
                return True
            logger.warning('唤醒 Agent 失败，重试', attempt=attempt,
                           symbol=payload['symbol'])
            if attempt < self.max_retries:
                time.sleep(self.retry_interval)
        logger.error('唤醒 Agent 最终失败（已落库待补发）', symbol=payload['symbol'])
        return False

    def _broadcast_ws(self, payload):
        if not self.ws_url:
            return
        try:
            requests.post(self.ws_url, json={'type': 'watch_triggered', 'data': payload},
                          timeout=3)
        except Exception as e:
            logger.debug('WS 广播失败（忽略）', error=str(e))

    def _record(self, rule, condition, quote, result, notified):
        if self.trigger_repo is None:
            return
        try:
            self.trigger_repo.record(
                rule_id=rule.id, symbol=rule.symbol, condition=condition,
                trigger_price=float(quote.price),
                detail={'value': result.value, 'message': result.message},
                notified=notified,
            )
        except Exception as e:
            logger.error('触发记录落库失败', error=str(e))
