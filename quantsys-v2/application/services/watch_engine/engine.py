"""WatchEngine 盯盘引擎核心

tick() 为一次完整判定（同步、可单测）；run_forever() 为常驻循环。
仅交易日（周一至周五）9:30-11:30 / 13:00-15:00 运行。
"""
import time as time_module
from datetime import datetime, time, timedelta
from typing import Callable, Dict, List, Optional, Tuple

import structlog

from application.services.watch_engine.conditions import (
    DEFAULT_COOLDOWN_SEC, EvalContext, evaluate,
)

logger = structlog.get_logger(__name__)

TOTAL_TRADING_MINUTES = 240  # 上午120 + 下午120


def elapsed_trading_fraction(now: datetime) -> float:
    """当日已过交易时间比例（0~1），供 volume_surge 折算同期均量"""
    t = now.time()
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    if t <= time(9, 30):
        return 0.0
    if t <= morning_end:
        minutes = (now - now.replace(hour=9, minute=30, second=0)).seconds / 60
    elif t < afternoon_start:
        minutes = 120
    elif t <= time(15, 0):
        minutes = 120 + (now - now.replace(hour=13, minute=0, second=0)).seconds / 60
    else:
        minutes = TOTAL_TRADING_MINUTES
    return min(1.0, max(0.0, minutes / TOTAL_TRADING_MINUTES))


class WatchEngine:
    def __init__(self, rule_repo, quote_service, notifier,
                 avg_volume_provider: Optional[Callable[[str], Optional[float]]] = None,
                 base_interval: int = 60, fast_interval: int = 10,
                 buffer_ratio: float = 0.2, history_minutes: int = 30,
                 now_fn: Callable[[], datetime] = datetime.now):
        self.rule_repo = rule_repo
        self.quote_service = quote_service
        self.notifier = notifier
        self.avg_volume_provider = avg_volume_provider
        self.base_interval = base_interval
        self.fast_interval = fast_interval
        self.buffer_ratio = buffer_ratio
        self.history_minutes = history_minutes
        self.now_fn = now_fn

        self._history: Dict[str, List[Tuple[datetime, float]]] = {}
        self._last_triggered: Dict[Tuple[int, int], datetime] = {}
        self._avg_volume_cache: Dict[str, float] = {}
        self._state_date = None  # 状态所属日期，跨天重置
        self.fast_mode = False
        self._stopped = False

    @staticmethod
    def is_trading_time(t: time) -> bool:
        return (time(9, 30) <= t <= time(11, 30)) or (time(13, 0) <= t <= time(15, 0))

    def stop(self):
        self._stopped = True

    # ── 主循环 ──────────────────────────────────────────────

    def run_forever(self):
        logger.info('WatchEngine 启动', base_interval=self.base_interval,
                    fast_interval=self.fast_interval)
        while not self._stopped:
            now = self.now_fn()
            if now.weekday() < 5 and self.is_trading_time(now.time()):
                try:
                    self.tick()
                except Exception as e:
                    logger.error('WatchEngine tick 异常', error=str(e))
                interval = self.fast_interval if self.fast_mode else self.base_interval
            else:
                interval = 60  # 非交易时段低频心跳
            time_module.sleep(interval)
        logger.info('WatchEngine 已停止')

    # ── 单次判定 ────────────────────────────────────────────

    def tick(self) -> List[dict]:
        now = self.now_fn()
        self._reset_daily_state_if_needed(now)
        rules = self.rule_repo.list_enabled()
        events = []
        fast = False

        for rule in rules:
            if not self._in_active_window(rule, now):
                continue
            quote = self.quote_service.get_realtime_quote(rule.symbol)
            if quote is None:
                logger.warning('取价失败跳过', symbol=rule.symbol)
                continue
            self._push_history(rule.symbol, now, float(quote.price))
            ctx = self._build_ctx(rule, now)

            for idx, cond in enumerate(rule.conditions):
                try:
                    result = evaluate(cond, quote, ctx, now=now)
                except Exception as e:
                    logger.error('条件评估异常', rule_id=rule.id, cond=cond, error=str(e))
                    continue
                if result.distance_ratio is not None and result.distance_ratio <= self.buffer_ratio:
                    fast = True
                if not result.triggered:
                    continue
                if self._in_cooldown(rule.id, idx, cond, now):
                    continue
                try:
                    self.notifier.notify(rule, cond, quote, result)
                except Exception as e:
                    # 不设置 _last_triggered，下个 tick 重试（at-least-once）
                    logger.error('通知发送失败', rule_id=rule.id, cond=cond, error=str(e))
                    continue
                self._last_triggered[(rule.id, idx)] = now
                events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                               'condition': cond, 'price': float(quote.price),
                               'message': result.message})

        self.fast_mode = fast
        return events

    # ── 内部 ────────────────────────────────────────────────

    def _reset_daily_state_if_needed(self, now: datetime):
        """跨天重置：均量缓存过期 + 清理已删除规则的残留状态"""
        current_date = now.date()
        if self._state_date == current_date:
            return
        self._state_date = current_date
        self._avg_volume_cache.clear()
        active_ids = {r.id for r in self.rule_repo.list_enabled()}
        self._last_triggered = {k: v for k, v in self._last_triggered.items()
                                if k[0] in active_ids}
        active_symbols = {r.symbol for r in self.rule_repo.list_enabled()}
        self._history = {s: buf for s, buf in self._history.items()
                         if s in active_symbols}

    def _in_active_window(self, rule, now: datetime) -> bool:
        windows = getattr(rule, 'active_window', None)
        if not windows:
            return True
        current = now.strftime('%H:%M')
        try:
            return any(start <= current <= end for w in windows
                       for start, end in [w.split('-')])
        except (ValueError, AttributeError, TypeError) as e:
            # 畸形窗口格式 fail-open：记 warning，不丢监控
            logger.warning('active_window 格式错误，放行监控',
                           rule_id=getattr(rule, 'id', None),
                           active_window=windows, error=str(e))
            return True

    def _build_ctx(self, rule, now: datetime) -> EvalContext:
        cost = getattr(rule, 'cost_price', None)
        return EvalContext(
            cost_price=float(cost) if cost is not None else None,
            price_history=tuple(self._history.get(rule.symbol, ())),
            avg_volume_20d=self._get_avg_volume(rule.symbol),
            elapsed_fraction=elapsed_trading_fraction(now),
        )

    def _push_history(self, symbol: str, ts: datetime, price: float):
        buf = self._history.setdefault(symbol, [])
        buf.append((ts, price))
        cutoff = ts - timedelta(minutes=self.history_minutes)
        self._history[symbol] = [(t, p) for t, p in buf if t >= cutoff]

    def _get_avg_volume(self, symbol: str) -> Optional[float]:
        if self.avg_volume_provider is None:
            return None
        if symbol not in self._avg_volume_cache:
            try:
                value = self.avg_volume_provider(symbol)
                if value:
                    self._avg_volume_cache[symbol] = value
            except Exception as e:
                logger.warning('均量获取失败', symbol=symbol, error=str(e))
                return None
        return self._avg_volume_cache.get(symbol)

    def _in_cooldown(self, rule_id: int, cond_idx: int, cond: dict, now: datetime) -> bool:
        last = self._last_triggered.get((rule_id, cond_idx))
        if last is None:
            return False
        cooldown = cond.get('cooldown_sec', DEFAULT_COOLDOWN_SEC)
        return (now - last).total_seconds() < cooldown
