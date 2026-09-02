"""WatchEngine 触发通知器：notify_mode 分流 + WS 广播 + 审计落库

notify_mode 两种模式（watch_rules.notify_mode）：
- direct：纯提醒，直接发飞书（不唤醒 Agent，不经 LLM）
- agent：需 LLM 处理，唤醒 Agent（/wake），由 Agent 分析后决定推送内容

兜底：agent 模式唤醒失败（最终失败）时，降级直接发飞书，保证提醒可达。
"""
import time
from typing import Optional

import requests
import structlog

logger = structlog.get_logger(__name__)


def _norm_symbol(symbol: str) -> str:
    """'002241.SZ' -> '002241'（stocks 表为纯 6 位代码）。"""
    return (symbol or '').split('.')[0].strip()


def _lookup_stock_name(symbol: str) -> Optional[str]:
    """兜底查股票名称（quant.stocks）。失败返回 None，不影响主流程。"""
    try:
        from infrastructure.persistence.orm import get_session
        from sqlalchemy import text
        session = get_session()
        row = session.execute(
            text("SELECT name FROM quant.stocks WHERE symbol = :s LIMIT 1"),
            {"s": _norm_symbol(symbol)},
        ).fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.debug('股票名称兜底查询失败', symbol=symbol, error=str(e))
        return None


def _direction_advice(condition: dict) -> str:
    """从 condition.direction 解读操作倾向（结合 price_break/pnl 等类型）。"""
    if not isinstance(condition, dict):
        return ''
    params = condition.get('params') or {}
    direction = params.get('direction')
    ctype = condition.get('type', '')
    if direction == 'above':
        # 上破：强势信号。对持仓股为止盈/锁利参考，对观察股为买入候选
        return '📈 方向：上破（强势）——持仓参考止盈/锁利，空仓为买入候选'
    if direction == 'below':
        # 下破：弱势信号。对持仓股为止损/风险预警，对观察股暂避
        return '📉 方向：下破（弱势）——持仓警惕止损，空仓暂不介入'
    return f'类型：{ctype}' if ctype else ''


class WatchNotifier:
    def __init__(self, agent_service, trigger_repo=None, feishu_service=None,
                 ws_url: Optional[str] = 'http://127.0.0.1:5003/broadcast/market_data',
                 max_retries: int = 3, retry_interval: float = 1.0):
        self.agent_service = agent_service
        self.trigger_repo = trigger_repo
        self.feishu_service = feishu_service
        self.ws_url = ws_url
        self.max_retries = max_retries
        self.retry_interval = retry_interval

    def notify(self, rule, condition: dict, quote, result) -> bool:
        """触发通知。按 notify_mode 分流；返回是否成功送达（失败也落库待补发）"""
        payload = self._build_payload(rule, condition, quote, result)
        mode = getattr(rule, 'notify_mode', None) or 'direct'

        if mode == 'agent':
            logger.info('准备唤醒 Agent', rule_id=rule.id, symbol=rule.symbol, payload=payload)
            notified = self._notify_agent_with_retry(payload)
            if not notified:
                # 兜底：唤醒失败降级直接发飞书，保证提醒可达
                logger.warning('唤醒 Agent 失败，降级直接发飞书', symbol=rule.symbol)
                notified = self._send_feishu(payload)
        else:
            # direct：纯提醒，直接发飞书
            logger.info('直接发飞书提醒', rule_id=rule.id, symbol=rule.symbol)
            notified = self._send_feishu(payload)

        self._broadcast_ws(payload)
        self._record(rule, condition, quote, result, notified)
        return notified

    def _send_feishu(self, payload) -> bool:
        """直接发飞书告警（类型 1 纯提醒，不经 LLM）"""
        if self.feishu_service is None:
            logger.error('feishu_service 未注入，无法直接发飞书', symbol=payload['symbol'])
            return False
        try:
            name = payload.get('name') or ''
            symbol = payload['symbol']
            display = f"{name}（{symbol}）" if name else symbol

            # 组织带名称 + 买卖方向 + 预案的消息体
            lines = [f"**{display}** 触发盯盘条件"]
            base_msg = payload.get('message')
            if base_msg:
                lines.append(f"**触发**：{base_msg}")
            advice = _direction_advice(payload.get('condition'))
            if advice:
                lines.append(advice)
            context = payload.get('context')
            if context:
                lines.append(f"**预案**：{context}")

            data = {
                'price': payload.get('price'),
                'change_pct': payload.get('change_pct'),
                'pnl_pct': payload.get('pnl_pct'),
                'condition': payload.get('condition'),
            }
            return bool(self.feishu_service.send_alert(
                alert_type='signal',
                symbol=display,  # 标题带名称：💡 SIGNAL - 歌尔股份（002241.SZ）
                message="\n".join(lines),
                data=data,
            ))
        except Exception as e:
            logger.error('直接发飞书失败', symbol=payload['symbol'], error=str(e))
            return False

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
        # 名称兜底：quote.name 为空时查 stocks 表（symbol 规范化去后缀）
        name = getattr(quote, 'name', None) or _lookup_stock_name(rule.symbol)
        return {
            'rule_id': rule.id,
            'symbol': rule.symbol,
            'name': name,
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
