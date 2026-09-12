"""市况服务（应用层编排）

RFC 016 §4.5：市况的**唯一对外入口**。应用层只做编排，不做判定：

- **日级真源**：仍由 `application.services.trading_day_guard.TradingDayGuard` 提供
  —— 不另造第二条日级真源（2026-08-08 周末写入 5 条合成净值快照的教训）；
- **时段判定**：委托领域策略 `domain.trading.services.market_session_policy`（纯函数，零 IO）；
- **时钟**：经 `domain.trading.ports.IMarketClock` 端口注入；默认实现在构造函数内
  **局部导入**（DI，遵守"应用层类型注解只用端口 ABC"的约定）。

使用方一律经本服务取市况，**不得**再自算时段或 weekday。
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional

from application.services.trading_day_guard import TradingDayGuard
from domain.trading.models.market_session import MarketSession, SessionPhase
from domain.trading.ports.IMarketClock import IMarketClock
from domain.trading.services.market_session_policy import MarketSessionPolicy

# 「最近交易日」回溯上限（覆盖国庆/春节等连续假期）
_LAST_TRADING_DAY_LOOKBACK = 15


class MarketSessionService:
    """市况服务（无状态；时钟可注入以便单测）"""

    def __init__(self, clock: Optional[IMarketClock] = None):
        if clock is None:
            from adapters.outbound.clock.beijing_clock import BeijingClock  # DI：局部导入具体实现
            clock = BeijingClock()
        self._clock = clock
        self._policy = MarketSessionPolicy()

    # ---------------------------------------------------------------- 快照
    def current(self, now: Optional[datetime] = None) -> MarketSession:
        """当前市况快照（日级判定 + 时段判定 → 值对象）"""
        at = now or self._clock.now()
        verdict = TradingDayGuard.check(at.date())
        return self._policy.evaluate(
            at,
            is_trading_day=verdict.is_trading_day,
            day_source=verdict.source,
            day_degraded=verdict.degraded,
            day_reason=verdict.reason,
        )

    # ------------------------------------------------------------ 常用判据
    def phase(self, now: Optional[datetime] = None) -> SessionPhase:
        """当前相位"""
        return self.current(now).phase

    def is_market_open(self, now: Optional[datetime] = None) -> bool:
        """连续竞价中（下单硬约束的判据；= MORNING / AFTERNOON）"""
        return self.current(now).is_market_open

    def is_price_fresh_window(self, now: Optional[datetime] = None) -> bool:
        """报价是否可能仍在变动（09:15–15:00 + 收盘后 5 分钟宽限）"""
        return self.current(now).is_price_fresh_window

    def is_trading_day(self, day: Optional[datetime] = None) -> bool:
        """当日是否交易日（透传日级真源）"""
        return self.current(day).is_trading_day

    # -------------------------------------------------- 开始时间 / 交易进度
    def session_start_of(self, phase: SessionPhase) -> Optional[time]:
        """**相位开始时刻**（取代散落的 `PHASE_SCHEDULE[phase][0]` 与硬编码 09:30/13:00）"""
        return MarketSessionPolicy.session_start_of(phase)

    def next_boundary_at(self, now: Optional[datetime] = None) -> Optional[datetime]:
        """下一个相位边界的完整时刻（当日无更晚边界时返回 None）"""
        at = now or self._clock.now()
        nxt = MarketSessionPolicy.next_boundary(at.time())
        return datetime.combine(at.date(), nxt) if nxt is not None else None

    def elapsed_trading_minutes(self, now: Optional[datetime] = None) -> int:
        """当日已交易分钟（午休不计，0..240）"""
        return self.current(now).elapsed_trading_minutes

    def session_progress(self, now: Optional[datetime] = None) -> float:
        """已交易比例 0~1（取代 `watch_engine.elapsed_trading_fraction`）"""
        return self.current(now).session_progress

    # ------------------------------------------------------------ 价格相关
    def expected_price_date(self, now: Optional[datetime] = None) -> str:
        """期望价日期 = 最近一个交易日（含今日）——取价门面 `stale` 判据（RFC 016 D4）

        非开市日读到该日期的收盘价即为新鲜（"已收盘最终价"，不是陈旧）。
        """
        day = (now or self._clock.now()).date()
        for _ in range(_LAST_TRADING_DAY_LOOKBACK):
            if TradingDayGuard.is_trading_day(day):
                return day.isoformat()
            day -= timedelta(days=1)
        return day.isoformat()

    # ------------------------------------------------------ 硬约束（fail-closed）
    def assert_can_trade(self, now: Optional[datetime] = None) -> MarketSession:
        """下单前置硬约束：非开市即拒绝（fail-closed）

        ⚠️ 尚未接线到下单链路（RFC 016 阶段 P5）；当前仅提供判据，不改变既有行为。
        调用方约定：捕获 ValueError → HTTP 422（与既有 `_check_trading_window` 同口径）。
        """
        session = self.current(now)
        if not session.is_market_open:
            raise ValueError('当前非连续竞价时段（%s），禁止委托' % session.phase.value)
        return session

    def assert_daily_write_allowed(self, day: Optional[datetime] = None) -> bool:
        """写入型守卫（净值快照/按日统计）：非交易日不得写入

        委托 `TradingDayGuard.should_write_daily`（**唯一真源**，不复制判据）。
        """
        return TradingDayGuard.should_write_daily(day).is_trading_day
