"""市况领域策略（纯领域逻辑，零外部依赖）

RFC 016 §4.5.3（2026-09-12）：**市况判定的唯一实现**。三种"开始"在此定义且只在此定义：

    - 可报价开始 09:15（集合竞价，价格已在变）—— 价格新鲜窗口起点
    - 可撮合开始 09:25（可撮合，尚未连续交易）
    - 可连续交易开始 09:30（`is_market_open` / 交易分钟起点）

现有代码把这三者揉在一个 `Phase` 里，才需要在 `daily_orchestrator` 用 `>= 9:31`
硬门槛兜"进了阶段但不撮合"——本策略把三者显式分开。

**边界语义**：沿用既有实现（`start <= t <= end`）——11:30 与 15:00 均算**盘中**，
故这两个端点显式归入交易相位（见 `_INCLUSIVE_END`）。

**收敛约束**：全仓此后不得再用裸常量表达时段，一律经本策略或
`application/services/market_session_service.py`。
"""
from __future__ import annotations

from datetime import datetime, time
from typing import Optional, Tuple

from domain.trading.models.market_session import (
    MarketSession,
    SessionPhase,
    SessionWindow,
)

# ── 时间常量（唯一出处）────────────────────────────────────────────────
CALL_AUCTION_START = time(9, 15)      # 可报价开始（集合竞价）
MATCHING_START = time(9, 25)          # 可撮合开始
CONTINUOUS_START = time(9, 30)        # 可连续交易开始
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
CONTINUOUS_END = time(15, 0)
PRICE_FRESH_GRACE_END = time(15, 5)   # 收盘后 5 分钟宽限（报价仍在落定）

MORNING_MINUTES = 120
AFTERNOON_MINUTES = 120
TOTAL_TRADING_MINUTES = MORNING_MINUTES + AFTERNOON_MINUTES   # 240（对齐旧 watch_engine 常量）

# 相位窗口（顺序即优先级；半开区间 [start, end)）
SESSION_BOUNDS: Tuple[SessionWindow, ...] = (
    SessionWindow(SessionPhase.CALL_AUCTION, CALL_AUCTION_START, MATCHING_START),
    SessionWindow(SessionPhase.OPENING, MATCHING_START, CONTINUOUS_START),
    SessionWindow(SessionPhase.MORNING, CONTINUOUS_START, MORNING_END),
    SessionWindow(SessionPhase.LUNCH_BREAK, MORNING_END, AFTERNOON_START),
    SessionWindow(SessionPhase.AFTERNOON, AFTERNOON_START, CONTINUOUS_END),
)

# 端点闭合：这两个时刻算"盘中"，半开区间会被下一相位吃掉，故显式归入交易相位
_INCLUSIVE_END = {
    MORNING_END: SessionPhase.MORNING,
    CONTINUOUS_END: SessionPhase.AFTERNOON,
}

# "盘中"相位（is_market_open 的定义）
_OPEN_PHASES = (SessionPhase.MORNING, SessionPhase.AFTERNOON)

# 当日相位边界（升序），供 next_boundary 使用
_BOUNDARIES: Tuple[time, ...] = (
    CALL_AUCTION_START, MATCHING_START, CONTINUOUS_START,
    MORNING_END, AFTERNOON_START, CONTINUOUS_END,
)


def _minutes(t: time) -> float:
    """time → 当日分钟数（含秒的小数部分）"""
    return t.hour * 60 + t.minute + t.second / 60.0


class MarketSessionPolicy:
    """市况判定策略（纯函数，无 IO、无状态）"""

    # ------------------------------------------------------------ 窗口/开始
    @staticmethod
    def window_of(phase: SessionPhase) -> Optional[SessionWindow]:
        """相位的窗口（无窗口的相位返回 None）"""
        for w in SESSION_BOUNDS:
            if w.phase == phase:
                return w
        return None

    @staticmethod
    def session_start_of(phase: SessionPhase) -> Optional[time]:
        """**相位开始时刻**（"开始时间"的唯一查询入口）

        取代散落各处的 `PHASE_SCHEDULE[phase][0]` 与硬编码 09:30/13:00。
        """
        w = MarketSessionPolicy.window_of(phase)
        return w.start if w else None

    @staticmethod
    def next_boundary(t: time) -> Optional[time]:
        """当日下一个相位边界（无更晚边界时返回 None）"""
        for b in _BOUNDARIES:
            if t < b:
                return b
        return None

    # ---------------------------------------------------------------- 判定
    @staticmethod
    def phase_for(t: time, *, is_trading_day: bool = True) -> SessionPhase:
        """时刻 → 相位（非交易日一律 NON_TRADING_DAY）

        入参**先截到整分钟**再判定：调用方传的是 `datetime.now().time()`（秒/微秒非零），
        而端点闭合（11:30 / 15:00 算盘中）与既有实现 `hm = hour*100 + minute` 一样是
        **整分钟粒度**语义。若不截断，`time(11,30,7)` 会落进 LUNCH_BREAK、
        `time(15,0,7)` 落进 AFTER_HOURS —— 11:30 / 15:00 两个节拍被静默跳过
        （审查发现的真实回归，2026-09-12）。
        """
        t = t.replace(second=0, microsecond=0)
        if not is_trading_day:
            return SessionPhase.NON_TRADING_DAY
        edge = _INCLUSIVE_END.get(t)
        if edge is not None:
            return edge
        for w in SESSION_BOUNDS:
            if w.start <= t < w.end:
                return w.phase
        return SessionPhase.PRE_OPEN if t < CALL_AUCTION_START else SessionPhase.AFTER_HOURS

    @staticmethod
    def is_market_open(phase: SessionPhase) -> bool:
        """连续竞价中（下单硬约束的判据）"""
        return phase in _OPEN_PHASES

    @staticmethod
    def is_price_fresh_window(t: time, *, is_trading_day: bool) -> bool:
        """报价是否可能仍在变动（09:15–15:00 + 收盘后 5 分钟宽限）

        与 `phase_for` 一致：**截到整分钟**再比较，避免 15:05:30 被判"不新鲜"
        而 15:05:00 被判"新鲜"这种秒级悬崖（宽限窗口按整分钟口径）。
        """
        if not is_trading_day:
            return False
        t = t.replace(second=0, microsecond=0)
        if t > PRICE_FRESH_GRACE_END:
            return False
        return t >= CALL_AUCTION_START

    # ------------------------------------------------------ 交易分钟/进度
    @staticmethod
    def elapsed_trading_minutes(t: time, *, is_trading_day: bool = True) -> int:
        """当日已交易分钟（午休不计，0..240）

        整分钟口径（**向下取整**）：09:30 → 0；11:30 → 120；午休 → 120；
        13:00 → 120；15:00 及以后 → 240。

        ⚠️ 与旧 `watch_engine.elapsed_trading_fraction` **并非逐点等价**：后者用
        `.seconds/60` 保留小数分钟（10:00:30 → 0.127083），本函数取整（→ 0.125）。
        迁移消费方（如 volume_surge 同期均量折算）时须注意这 ≤0.4% 的差异；
        旧函数在 `watch_engine/engine.py:439` 仍在运行，尚未被本函数取代。
        """
        if not is_trading_day:
            return 0
        if t <= CONTINUOUS_START:
            return 0
        if t <= MORNING_END:
            return min(MORNING_MINUTES, int(_minutes(t) - _minutes(CONTINUOUS_START)))
        if t < AFTERNOON_START:
            return MORNING_MINUTES
        if t <= CONTINUOUS_END:
            return min(
                TOTAL_TRADING_MINUTES,
                MORNING_MINUTES + int(_minutes(t) - _minutes(AFTERNOON_START)),
            )
        return TOTAL_TRADING_MINUTES

    @staticmethod
    def session_progress(t: time, *, is_trading_day: bool = True) -> float:
        """已交易比例 0~1（= elapsed/240，供 volume_surge 折算同期均量）"""
        elapsed = MarketSessionPolicy.elapsed_trading_minutes(t, is_trading_day=is_trading_day)
        return round(min(1.0, max(0.0, elapsed / TOTAL_TRADING_MINUTES)), 4)

    # -------------------------------------------------------- 价格新鲜度
    @staticmethod
    def minute_freshness_ok(
        latest_minute_at: Optional[datetime],
        now: datetime,
        *,
        threshold_minutes: int = 5,
    ) -> bool:
        """开市态专用的分钟级新鲜度复检（D4 的第二半）

        非开市态不需要它——那时"最新交易日收盘价"即为新鲜（见
        `MarketSession.price_is_fresh`）。
        """
        if latest_minute_at is None:
            return False
        # 容忍 aware/naive 混用（DB 的分钟时间戳普遍为 naive，时钟为 aware）
        a = latest_minute_at.replace(tzinfo=None) if latest_minute_at.tzinfo else latest_minute_at
        b = now.replace(tzinfo=None) if now.tzinfo else now
        delta = (b - a).total_seconds()
        return 0 <= delta <= threshold_minutes * 60   # 单侧：未来时间戳不算新鲜

    # ------------------------------------------------------------ 组装 VO
    def evaluate(
        self,
        now: datetime,
        *,
        is_trading_day: bool,
        day_source: str = 'unknown',
        day_degraded: bool = False,
        day_reason: str = '',
    ) -> MarketSession:
        """组装市况值对象（日级判定由调用方注入——真源是 TradingDayGuard）"""
        t = now.time()
        phase = self.phase_for(t, is_trading_day=is_trading_day)
        window = self.window_of(phase)
        nxt = self.next_boundary(t)

        parts = ['相位 ' + phase.value]
        parts.append('交易日' if is_trading_day else '非交易日')
        if window is not None:
            parts.append('窗口 %s-%s' % (window.start.strftime('%H:%M'), window.end.strftime('%H:%M')))
        if day_reason:
            parts.append(day_reason)
        if day_degraded:
            parts.append('日级判定降级（启发式，须复核）')

        return MarketSession(
            at=now.isoformat(),
            day=now.date().isoformat(),
            phase=phase,
            is_trading_day=is_trading_day,
            is_market_open=self.is_market_open(phase),
            is_price_fresh_window=self.is_price_fresh_window(t, is_trading_day=is_trading_day),
            phase_start=window.start.strftime('%H:%M') if window else '',
            phase_end=window.end.strftime('%H:%M') if window else '',
            next_boundary_at=(
                # 保留 tzinfo（与 at 同口径；datetime.combine 默认丢 tz）
                datetime.combine(now.date(), nxt, tzinfo=now.tzinfo).isoformat()
                if (nxt is not None and is_trading_day) else ''
            ),
            elapsed_trading_minutes=self.elapsed_trading_minutes(t, is_trading_day=is_trading_day),
            session_progress=self.session_progress(t, is_trading_day=is_trading_day),
            source='clock+' + str(day_source or 'unknown'),
            degraded=bool(day_degraded),
            reason='；'.join(parts),
        )
