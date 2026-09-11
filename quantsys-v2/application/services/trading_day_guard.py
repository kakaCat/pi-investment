"""交易日判断唯一入口（步2 收口，2026-09-11，w-f4aa1f6a）

## 为什么需要它
交易日判断此前散落 6+ 处、各自实现不同，已造成真实事故：
- **2026-08-08（周六）5 个账户被写入净值快照**（agent_virtual/user_main/v13/v14/v15），
  污染净值、回撤、熔断与归因口径（现已标记 is_synthetic=true 并从统计口径排除）；
- `quant.trading_calendar` 长期**空表**，而 data_pipeline_service 仍从它读交易日集合
  → TimeAlignmentStage 拿到空日历、静默降级；
- 2026-08-12 事故：用"当天日K是否已落库"当唯一判据 → 06:30/14:30 的调度检查永远判"今天不是
  交易日" → v13/v14 调仓从不执行却被记为 success（静默失败）。

## 语义（唯一真源：judge_trading_day 纯函数 + K线数据）
- 周末 → 非交易日
- 未来日期 → 非交易日
- 该日 daily_klines 有记录 → 交易日（精确覆盖法定节假日）
- 判定对象是"今天"且当日K线尚未落库（盘中；日K 17:40 才更新）→ 近期市场活跃
  （7 个自然日内有K线）则视为交易日，并标记 **degraded=True**（属启发式判断，必须可见）
- 其它（过去的工作日无K线 = 节假日；数据断供）→ 非交易日

## 用法
    from application.services.trading_day_guard import TradingDayGuard
    v = TradingDayGuard.check('2026-08-08')     # → is_trading_day=False, source='weekend'
    v = TradingDayGuard.check()                  # 今天
    if not TradingDayGuard.is_trading_day(d):
        ...
写入型路径（净值快照、按日统计落库）用 `should_write_daily()`，它返回判定对象供留痕。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Optional, Tuple, Union

import structlog

logger = structlog.get_logger(__name__)

# 进程级 TTL 缓存：watch_engine / daily_orchestrator 是高频 tick（秒级），
# 不能每轮都查库（两次索引查询虽只要 ~0.12ms，但秒级 tick 会累积）。
_CACHE_TTL_SECONDS = 60
_verdict_cache: Dict[date, Tuple[float, 'TradingDayVerdict']] = {}

# 判定来源（R-013：数据来源必须可标注）
SOURCE_WEEKEND = 'weekend'
SOURCE_FUTURE = 'future'
SOURCE_KLINE = 'kline-data'
SOURCE_INTRADAY = 'intraday-recent-market'
SOURCE_NO_DATA = 'no-kline-data'
SOURCE_UNAVAILABLE = 'unavailable'


def judge_trading_day(
    day: date,
    *,
    kline_exists_on_date: bool,
    latest_kline_date: Optional[date],
    today: date,
) -> bool:
    """判定某天是否为交易日（纯函数，可单测；语义见模块 docstring）。

    2026-09-11（w-f4aa1f6a）：从 live_trading.simulation_trader 提升为共享唯一实现，
    原处保留同名再导出以兼容既有调用与测试。
    """
    if day.weekday() >= 5:
        return False
    if day > today:
        return False
    if kline_exists_on_date:
        return True
    if day == today:
        if latest_kline_date is None:
            return False
        return (today - latest_kline_date).days <= 7
    return False


@dataclass(frozen=True)
class TradingDayVerdict:
    """判定结果（含来源与降级标记，便于留痕与排查）。"""

    day: date
    is_trading_day: bool
    source: str
    degraded: bool
    reason: str

    def as_dict(self) -> dict:
        return {
            'day': self.day.isoformat(),
            'is_trading_day': self.is_trading_day,
            'source': self.source,
            'degraded': self.degraded,
            'reason': self.reason,
        }


def _normalize(day: Union[None, str, date, datetime]) -> date:
    if day is None:
        return datetime.now().date()
    if isinstance(day, datetime):
        return day.date()
    if isinstance(day, date):
        return day
    return datetime.strptime(str(day)[:10], '%Y-%m-%d').date()


class TradingDayGuard:
    """交易日判断唯一入口。"""

    @classmethod
    def check(
        cls,
        day: Union[None, str, date, datetime] = None,
        *,
        use_cache: bool = True,
    ) -> TradingDayVerdict:
        """返回判定 + 来源 + 降级标记；数据源不可用时保守判非交易日并留痕。

        use_cache=True 时按"日期"缓存 60 秒（高频 tick 场景）；写入型路径需要
        实时判定时可传 use_cache=False。
        """
        d = _normalize(day)
        if use_cache:
            hit = _verdict_cache.get(d)
            if hit and (time.time() - hit[0]) < _CACHE_TTL_SECONDS:
                return hit[1]

        verdict = cls._compute(d)
        _verdict_cache[d] = (time.time(), verdict)
        if len(_verdict_cache) > 32:  # 只保留最近 32 个日期，防长期驻留
            for stale_day in sorted(_verdict_cache)[:-32]:
                _verdict_cache.pop(stale_day, None)
        return verdict

    @classmethod
    def _compute(cls, d: date) -> TradingDayVerdict:
        today = datetime.now().date()

        if d.weekday() >= 5:
            return TradingDayVerdict(d, False, SOURCE_WEEKEND, False, '周末')
        if d > today:
            return TradingDayVerdict(d, False, SOURCE_FUTURE, False, '未来日期')

        try:
            exists, latest = cls._kline_stats(d)
        except Exception as e:  # noqa: BLE001 - 数据源不可用必须可见且保守
            logger.warning('trading_day_guard_datasource_unavailable', day=d.isoformat(), error=str(e))
            return TradingDayVerdict(
                d, False, SOURCE_UNAVAILABLE, True,
                f'日K数据源不可用（{e}）→ 保守判非交易日',
            )

        ok = judge_trading_day(d, kline_exists_on_date=exists, latest_kline_date=latest, today=today)
        if exists:
            return TradingDayVerdict(d, True, SOURCE_KLINE, False, '该日已有日K数据')
        if ok:  # 只可能是"今天 + 近 7 日有K线"的盘中启发式
            return TradingDayVerdict(
                d, True, SOURCE_INTRADAY, True,
                f'当日K线未落库，按近期市场活跃（最近K线 {latest}）判为交易日',
            )
        reason = '过去的工作日无日K数据（法定节假日或数据断供）'
        return TradingDayVerdict(d, False, SOURCE_NO_DATA, False, reason)

    @classmethod
    def is_trading_day(cls, day: Union[None, str, date, datetime] = None) -> bool:
        return cls.check(day).is_trading_day

    @classmethod
    def should_write_daily(cls, day: Union[None, str, date, datetime] = None) -> TradingDayVerdict:
        """写入型路径（净值快照/按日统计）守卫：非交易日不得写入按日数据。

        2026-08-08 那 5 条周末合成快照就是缺少这道守卫造成的。
        """
        v = cls.check(day)
        if not v.is_trading_day:
            logger.info(
                'skip_daily_write_non_trading_day',
                day=v.day.isoformat(), source=v.source, reason=v.reason,
            )
        return v

    # ------------------------------------------------------------------
    @staticmethod
    def _kline_stats(day: date):
        """(该日是否有K线, 最近K线日期)；两条查询均走 daily_klines 索引（实测 0.12ms）。"""
        from infrastructure.persistence.database.engine import db_cursor

        with db_cursor() as cursor:
            cursor.execute(
                'SELECT EXISTS (SELECT 1 FROM quant.daily_klines WHERE trade_date = %s) AS exists_on_date,'
                ' (SELECT max(trade_date) FROM quant.daily_klines) AS latest_date',
                (day,),
            )
            row = cursor.fetchone()

        if row is None:
            return False, None
        if isinstance(row, dict):
            return bool(row.get('exists_on_date')), row.get('latest_date')
        return bool(row[0]), row[1]
