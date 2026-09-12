"""市况值对象（交易时段判定 · DDD 领域模型）

RFC 016 §4.5（2026-09-12）：把"当前处于哪个交易相位、是否开市、报价是否在变、
本相位何时开始/结束、当日已交易多久"建模为**不可变值对象**，供下单闸门 / 盯盘 /
编排器 / 取价门面共用同一口径，取代散落各处的时间常量。

领域层零外部依赖（仅 dataclasses / enum / datetime）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from enum import Enum


class SessionPhase(str, Enum):
    """交易相位（枚举值即对外契约字段 `session_phase`，一经确定不得随意改名）

    注意：**不用** `market_phase` 之名——该字段在本仓已被 Wyckoff 市场阶段占用
    （`accumulation`/`markup`/`distribution`/`markdown`，见 battlefield_assessor）。
    """
    NON_TRADING_DAY = 'non_trading_day'
    PRE_OPEN = 'pre_open'            # 当日 < 09:15
    CALL_AUCTION = 'call_auction'    # 09:15–09:25  集合竞价（价格已在变）
    OPENING = 'opening'             # 09:25–09:30  可撮合、尚未连续交易
    MORNING = 'morning'             # 09:30–11:30
    LUNCH_BREAK = 'lunch_break'     # 11:30–13:00（明确**不属于**盘中）
    AFTERNOON = 'afternoon'         # 13:00–15:00
    AFTER_HOURS = 'after_hours'     # > 15:00


@dataclass(frozen=True)
class SessionWindow:
    """相位的时间窗（"开始时间"的唯一载体）

    Attributes:
        phase: 相位
        start: 相位开始时刻
        end: 相位结束时刻
    """
    phase: SessionPhase
    start: time
    end: time


@dataclass(frozen=True)
class MarketSession:
    """市况（值对象，不可变）

    Attributes:
        at: 判定时点 ISO8601（对齐 TradingStatus.as_of）
        day: 判定日 YYYY-MM-DD
        phase: 当前相位
        is_trading_day: 当日是否交易日（与 TradingDayGuard 同源，不另造真源）
        is_market_open: 是否连续竞价中（= MORNING / AFTERNOON）。
            **不叫 `is_open`**——该名在本仓已被熔断器占用（circuit_breaker.is_open）。
        is_price_fresh_window: 报价是否可能仍在变动（09:15–15:00 + 收盘后 5 分钟宽限）
        phase_start: 当前相位开始 HH:MM（无窗口的相位为空串）
        phase_end: 当前相位结束 HH:MM
        next_boundary_at: 下一相位边界 ISO8601（当日无更晚边界时为空串）
        elapsed_trading_minutes: 当日已交易分钟（午休不计，0..240）
        session_progress: elapsed_trading_minutes / 240，0~1
        source: 判定来源（'clock' + 日级来源）
        degraded: 任一环节降级（日级为启发式判定 / 数据源不可用）必须可见（R-013）
        reason: 人可读、可复核（对齐 TradingStatusPolicy 的 reason 组装风格）
    """
    at: str
    day: str
    phase: SessionPhase
    is_trading_day: bool
    is_market_open: bool
    is_price_fresh_window: bool
    phase_start: str
    phase_end: str
    next_boundary_at: str
    elapsed_trading_minutes: int
    session_progress: float
    source: str
    degraded: bool
    reason: str

    def to_dict(self) -> dict:
        """序列化（API / 工具层统一用 dict 输出）"""
        return {
            'at': self.at,
            'day': self.day,
            'session_phase': self.phase.value,
            'is_trading_day': self.is_trading_day,
            'is_market_open': self.is_market_open,
            'is_price_fresh_window': self.is_price_fresh_window,
            'phase_start': self.phase_start,
            'phase_end': self.phase_end,
            'next_boundary_at': self.next_boundary_at,
            'elapsed_trading_minutes': self.elapsed_trading_minutes,
            'session_progress': self.session_progress,
            'source': self.source,
            'degraded': self.degraded,
            'reason': self.reason,
        }

    def price_is_fresh(self, as_of_date: str, expected_price_date: str) -> bool:
        """价格日期是否达到期望（RFC 016 D4，领域规则，不下沉到应用层）

        判据 `as_of_date >= expected_price_date`：
        - **非开市**：休市日读到最近一个交易日收盘价 → True（是"已收盘最终价"，不是陈旧）；
        - **开市**：调用方另需按分钟级新鲜度复检（`MarketSessionPolicy.minute_freshness_ok`）。
        """
        return str(as_of_date or '') >= str(expected_price_date or '')
