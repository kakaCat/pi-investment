"""观察类触发聚合缓冲（REQ-261016155500-4f2a wt:validate:1，2026-10-16）

背景（调研根因一/设计 §3.1）：无「变化判据」的 observe 触发是群里 98% 的噪音
（price_break 电平触发复读）。迟滞带 + 日上限已把单条件压到 ≤2 卡/日，本条再把
**无判据 observe** 的多次触发按「账户 × 标的」合成一张 15 分钟聚合卡——
保留推送原则（卡内逐条 trigger_id 可溯源），只改呈现密度。

路由规则（engine tick）：
  · observe 类（auto_observed）且规则**无** observation_criterion → 进缓冲；
  · 有判据（action_params.observation_criterion 非空）→ 维持即时单发
    （判据由 agent 在回填时给出，存在即视为"该叫"的信号已声明）；
  · escalated/pending 等需动作类 → 不受影响，照旧即时单发。

落库口径：缓冲的每条触发照常落 watch_triggers（notified=False，reason 标
「已进聚合缓冲」）——审计不丢；聚合卡本身经 send_watch_receipt 发盯盘群。
"""
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

#: 聚合窗口（秒）：同标的首次入缓冲起 15 分钟一屏
AGG_WINDOW_SEC = int(os.environ.get('WATCH_OBSERVE_AGG_WINDOW_SEC', '900'))
#: 每标的每日聚合卡上限（收盘 flush 不受限）
DAILY_AGG_CAP_PER_SYMBOL = 8
#: 总开关（默认开；false = 无判据 observe 也即时单发，退回改前行为）
OBSERVE_AGG_ENABLED = os.environ.get('WATCH_OBSERVE_AGG', 'true').strip().lower() \
    not in ('false', '0', 'off')


def _has_observation_criterion(rule: Any) -> bool:
    """规则是否声明了「观察到什么变化才值得叫我」。"""
    ap = getattr(rule, 'action_params', None)
    if isinstance(ap, dict) and (ap.get('observation_criterion') or '').strip():
        return True
    return False


class ObserveAggregator:
    """15 分钟聚合缓冲（无状态依赖注入；sender 负责真实投递）。

    sender(title: str, content: str) -> bool —— 由装配层接 watch_channels 的
    盯盘群投递；返回 False 表示投递失败（下轮随缓冲重试，不丢）。
    """

    def __init__(self, sender: Callable[[str, str], bool],
                 window_sec: int = AGG_WINDOW_SEC,
                 daily_cap: int = DAILY_AGG_CAP_PER_SYMBOL):
        self._sender = sender
        self._window = timedelta(seconds=window_sec)
        self._daily_cap = daily_cap
        # key=(account, symbol) -> {'items': [...], 'window_start': dt, 'low':f, 'high':f}
        self._buffers: Dict[Tuple[Optional[str], str], Dict[str, Any]] = {}
        # (date, symbol) -> 当日已 flush 次数
        self._flush_counts: Dict[Tuple[Any, str], int] = {}

    @staticmethod
    def enabled() -> bool:
        return OBSERVE_AGG_ENABLED

    def should_buffer(self, rule: Any, disposition: str) -> bool:
        """该触发是否走聚合缓冲（engine 判定入口，纯函数语义）。"""
        if not OBSERVE_AGG_ENABLED:
            return False
        if str(disposition or '') != 'auto_observed':
            return False
        return not _has_observation_criterion(rule)

    def add(self, account: Optional[str], symbol: str, item: Dict[str, Any],
            now: datetime, price: float) -> None:
        """入缓冲（同 key 合并；窗口从首条起算）。"""
        key = (account, symbol)
        buf = self._buffers.get(key)
        if buf is None:
            buf = {'items': [], 'window_start': now,
                   'low': float(price), 'high': float(price)}
            self._buffers[key] = buf
        buf['items'].append(item)
        buf['low'] = min(buf['low'], float(price))
        buf['high'] = max(buf['high'], float(price))

    def maybe_flush(self, now: datetime, market_open: bool = True) -> int:
        """到期/收盘 flush；返回发出的聚合卡张数。每 tick 由引擎调用一次。"""
        flushed = 0
        for key in list(self._buffers.keys()):
            buf = self._buffers[key]
            expired = now - buf['window_start'] >= self._window
            count_key = (now.date(), key[1])
            over_cap = self._flush_counts.get(count_key, 0) >= self._daily_cap
            if not expired and market_open:
                continue
            if over_cap and market_open:
                continue                       # 超上限：压到收盘再合屏（不丢）
            if self._flush(key, buf, now):
                flushed += 1
                self._flush_counts[count_key] = self._flush_counts.get(count_key, 0) + 1
                del self._buffers[key]
            else:
                buf['window_start'] = now      # 投递失败：顺延窗口，下 tick 重试（不丢）
        return flushed

    def _flush(self, key, buf: Dict[str, Any], now: datetime) -> bool:
        account, symbol = key
        items: List[Dict[str, Any]] = buf['items']
        name = (items[0].get('name') or '').strip()
        display = '%s（%s）' % (name, symbol) if name else symbol
        n = len(items)
        last = items[-1]
        lines = [
            '**%s** 今日第 %d 次触发聚合 ｜ 现价 %.2f（区间 %.2f ~ %.2f）'
            % (display, n, float(last.get('price') or 0), buf['low'], buf['high']),
            '最近：%s' % (last.get('message') or '-'),
            '逐条溯源：',
        ]
        lines.extend(
            '- #%s 规则#%s %s %s'
            % (it.get('trigger_id') or '-', it.get('rule_id') or '-',
               (it.get('at') or '')[-8:] if it.get('at') else '-',
               (it.get('message') or '')[:40])
            for it in items[:10])
        if n > 10:
            lines.append('- … 另有 %d 条（watch_triggers 可溯）' % (n - 10))
        title = '📋 观察聚合 · %s%s' % (
            symbol, '｜%s' % account if account else '')
        try:
            ok = bool(self._sender(title, '\n'.join(lines)))
        except Exception as e:  # noqa: BLE001 - 投递失败由调用方顺延重试
            logger.error('聚合卡投递失败', symbol=symbol, error=str(e))
            return False
        if ok:
            logger.info('观察聚合卡已发', symbol=symbol, count=n,
                        account=account, first=buf['window_start'])
        return ok

    def pending_count(self) -> int:
        return sum(len(b['items']) for b in self._buffers.values())
