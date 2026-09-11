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
from domain.watch.services.escalation_checker import EscalationChecker
from domain.watch.models import QuoteData

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
                 now_fn: Callable[[], datetime] = datetime.now,
                 escalation_checker: Optional[EscalationChecker] = None):
        self.rule_repo = rule_repo
        self.quote_service = quote_service
        self.notifier = notifier
        self.avg_volume_provider = avg_volume_provider
        self.base_interval = base_interval
        self.fast_interval = fast_interval
        self.buffer_ratio = buffer_ratio
        self.history_minutes = history_minutes
        self.now_fn = now_fn
        self.escalation_checker = escalation_checker or EscalationChecker()

        self._history: Dict[str, List[Tuple[datetime, float]]] = {}
        self._last_triggered: Dict[Tuple[int, int], datetime] = {}
        self._latched: set = set()
        self._avg_volume_cache: Dict[str, float] = {}
        self._state_date = None
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
        # 2026-09-11（w-f4aa1f6a 步2）：交易日判断收敛到唯一入口（原为只判周末）
        from application.services.trading_day_guard import TradingDayGuard
        while not self._stopped:
            now = self.now_fn()
            if TradingDayGuard.is_trading_day(now.date()) and self.is_trading_time(now.time()):
                try:
                    self.tick()
                except Exception as e:
                    logger.error('WatchEngine tick 异常', error=str(e))
                finally:
                    # tick 内 rule_repo 查询留下的 scoped session 每轮释放——
                    # 否则盯盘线程连接长期 idle in transaction（挡 autovacuum/
                    # 持旧快照，2026-08-18 后台线程连接治理）
                    try:
                        from infrastructure.persistence.orm import close_session
                        close_session()
                    except Exception:
                        pass
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
                    # 条件回到未触发状态 → 解除闩锁，重新武装（允许下次穿越再报）
                    self._latched.discard((rule.id, idx))
                    continue
                if (rule.id, idx) in self._latched:
                    # 条件持续成立（电平保持）→ 不重复推送，等重新武装
                    continue
                if self._in_cooldown(rule.id, idx, cond, now):
                    continue
                
                # 升级检查：L0/L1 触发满足条件时自动升级为 L2
                escalation_reason = None
                trigger_level = self._get_trigger_level(rule)
                
                if trigger_level in ('L0', 'L1'):
                    # 查询触发频率和并发触发数
                    recent_count = self._get_recent_trigger_count(rule.id, cond)
                    concurrent_count = self._get_concurrent_trigger_count(rule.symbol, now)
                    
                    quote_data = QuoteData(
                        symbol=rule.symbol,
                        price=float(quote.price),
                        change_pct=getattr(quote, 'change_pct', None),
                        volume=getattr(quote, 'volume', None),
                        prev_close=getattr(quote, 'prev_close', None),
                    )
                    
                    escalation_reason = self.escalation_checker.should_escalate(
                        rule=rule,
                        condition=cond,
                        quote=quote_data,
                        result=result,
                        recent_trigger_count=recent_count,
                        concurrent_trigger_count=concurrent_count,
                    )
                
                try:
                    self.notifier.notify(rule, cond, quote, result, escalation_reason=escalation_reason)
                except Exception as e:
                    # 不闩锁、不记 _last_triggered，下个 tick 重试（at-least-once）
                    logger.error('通知发送失败', rule_id=rule.id, cond=cond, error=str(e))
                    continue
                self._last_triggered[(rule.id, idx)] = now
                self._latched.add((rule.id, idx))
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
        # 跨天全量重新武装：新的一天允许持续成立的条件再报一次（每日最多一次）
        self._latched.clear()
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

    def _get_trigger_level(self, rule) -> str:
        """获取规则的触发层级（L0/L1/L2）"""
        action_hint = getattr(rule, 'action_hint', None)
        if not action_hint:
            return 'L1'  # 默认 L1
        
        import json
        try:
            if isinstance(action_hint, str):
                ah = json.loads(action_hint)
            else:
                ah = action_hint
            return ah.get('trigger_level', 'L1')
        except Exception:
            return 'L1'

    def _get_recent_trigger_count(self, rule_id: int, cond: dict) -> int:
        """获取规则近 10 分钟内的触发次数"""
        # 从 _last_triggered 中统计
        count = 0
        window = timedelta(minutes=10)
        now = self.now_fn()
        for (rid, idx), ts in self._last_triggered.items():
            if rid == rule_id and (now - ts) < window:
                count += 1
        return count

    def _get_concurrent_trigger_count(self, symbol: str, now: datetime) -> int:
        """获取同 symbol 近 60 秒内的并发触发规则数"""
        count = 0
        window = timedelta(seconds=60)
        # 从 _last_triggered 中统计（需要知道 symbol，但 _last_triggered 只存 rule_id）
        # 简化：从 events 中统计或从 trigger_repo 查询
        # 这里简化实现：返回 0（实际实现需要查询 trigger_repo）
        return count
