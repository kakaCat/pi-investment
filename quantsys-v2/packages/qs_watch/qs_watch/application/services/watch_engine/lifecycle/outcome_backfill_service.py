"""预判验证回填服务（2026-10-20 P3：记录行情，验证交易体系）

用户的目的④：「观察走势是否符合你之前的预判，积累盘感，复盘用。盘感本质是
大量行情样本的记忆，不是直觉。」

本服务把每条触发变成可统计的样本：触发后第 5/10/20 个交易日回填收盘价对照，
预判方向在回填时快照（domain/watch/services/outcome_direction.py），命中与否
由纯函数 judge_hit 判定。suppressed 的「触及未确认」样本同样回填——
没买的对不对，和买了的对不对，都是伏击点质量的证据。

运行位：引擎 sidecar 每日一次（与板块映射重建同通道，绝不在 tick 热路径跑）。
取数走 qs_market_data 的 DataProviderManager（仓内 Data Access Rules）。
"""
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import structlog

from qs_ops.application.services.trading_day_guard import TradingDayGuard
from qs_watch.domain.watch.services.outcome_direction import (
    infer_expected_direction, judge_hit,
)

logger = structlog.get_logger(__name__)

#: 回填窗口（交易日）
HORIZONS = (5, 10, 20)
#: 只回填最近 N 天的触发（窗口有界；更老的样本没有运营意义）
LOOKBACK_DAYS = 90
#: 单轮每窗口最多回填条数（防数据源风暴；余下的下一轮补）
PER_HORIZON_CAP = 200


def add_trading_days(d: date, n: int) -> date:
    """d 之后第 n 个交易日（含 d 当天若为交易日则计为第 0 个——从次日开始数）。

    步数有界：TradingDayGuard 对无法核实的远期日期可能 fail-closed 恒 False
    （2026-10-20 实测 horizon=20 撞上国庆后死循环到 date 溢出）——超过
    n*4+15 个自然日仍未数满就按 best-effort 返回（足够覆盖任意连长假），
    宁可近似也不许把回填线程钉死。
    """
    cur, left = d, n
    guard = n * 4 + 15
    steps = 0
    while left > 0 and steps < guard:
        cur += timedelta(days=1)
        steps += 1
        if TradingDayGuard.is_trading_day(cur):
            left -= 1
    return cur


class OutcomeBackfillService:
    def __init__(self, outcome_repo, data_manager=None,
                 now_fn: Callable[[], datetime] = datetime.now):
        self._repo = outcome_repo
        self._manager = data_manager  # None → 惰性取单例（测试注入友好）
        self._now = now_fn

    def backfill(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """每日回填入口。逐窗口找「到期未回填」的触发，取回填日收盘价落库。

        单条失败不拖垮整批；返回 {filled, failed, skipped_future} 供 sidecar 记日志。
        """
        now = now or self._now()
        today = now.date()
        since = now - timedelta(days=LOOKBACK_DAYS)
        filled, failed = 0, 0
        for horizon in HORIZONS:
            try:
                pendings = self._repo.pending_triggers(
                    horizon, due_before=today, since=since, limit=PER_HORIZON_CAP)
            except Exception as e:  # noqa: BLE001
                logger.error('待回填清单查询失败', horizon=horizon, error=str(e))
                continue
            for t in pendings:
                try:
                    if self._fill_one(t, horizon, today):
                        filled += 1
                except Exception as e:  # noqa: BLE001
                    failed += 1
                    logger.error('单条回填失败', trigger_id=t['trigger_id'],
                                 horizon=horizon, error=str(e))
        return {'filled': filled, 'failed': failed}

    # ── 内部 ────────────────────────────────────────────────

    def _fill_one(self, trigger: Dict[str, Any], horizon: int, today: date) -> bool:
        trigger_date = trigger['triggered_at'].date()
        due = add_trading_days(trigger_date, horizon)
        if due > today:
            return False  # 还没到回填日（清单按 trigger 日过滤是宽口径，这里精判）
        close = self._close_on(trigger['symbol'], due)
        if close is None:
            logger.warning('回填日收盘价缺失（保留待下轮）',
                           symbol=trigger['symbol'], due=str(due))
            return False
        trigger_price = float(trigger['trigger_price'])
        pct = round((close / trigger_price - 1) * 100, 4) if trigger_price else None
        direction = infer_expected_direction(trigger.get('intent'),
                                             trigger.get('condition'))
        return self._repo.record(
            trigger_id=trigger['trigger_id'], rule_id=trigger.get('rule_id'),
            symbol=trigger['symbol'], horizon_td=horizon,
            trigger_at=trigger['triggered_at'], trigger_price=trigger_price,
            expected_direction=direction, check_date=due, close_price=close,
            pct_change=pct, hit=judge_hit(direction, pct))

    def _close_on(self, symbol: str, d: date) -> Optional[float]:
        """回填日收盘价（本地日 K 优先；DataProviderManager 自动回退）。"""
        manager = self._manager or self._default_manager()
        bare = str(symbol).split('.')[0]
        start = (d - timedelta(days=10)).strftime('%Y-%m-%d')
        res = manager.get_klines(bare, 'daily', start, d.strftime('%Y-%m-%d'))
        if not res.get('success'):
            return None
        rows = res.get('data') or []
        closes = []
        for r in rows:
            # KlineData 对象（.date/.close）或 dict 两种形状都接（manager 返回对象，
            # 测试桩给 dict）——date 统一截成 YYYY-MM-DD。
            dd = getattr(r, 'date', None) if not isinstance(r, dict) else (
                r.get('trade_date') or r.get('date'))
            cc = getattr(r, 'close', None) if not isinstance(r, dict) else r.get('close')
            if dd is not None and cc is not None:
                closes.append((str(dd)[:10], float(cc)))
        if not closes:
            return None
        target = d.strftime('%Y-%m-%d')
        exact = [c for dd, c in closes if dd == target]
        if exact:
            return exact[-1]
        # 回填日非交易日/缺行：取之前最近一个交易日的收盘（诚实口径，不瞎编）
        before = [(dd, c) for dd, c in closes if dd < target]
        return before[-1][1] if before else None

    @staticmethod
    def _default_manager():
        from qs_market_data.adapters.outbound.datasources.manager import (
            get_data_provider_manager,
        )
        return get_data_provider_manager()
