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
# 判定器自身异常（既非"数据说不是交易日"，也非"数据源不可用"）。2026-09-14（复查 M4）：
# 与 SOURCE_UNAVAILABLE 分开，避免"代码 bug"被读成"今天真的不是交易日"。
SOURCE_COMPUTE_ERROR = 'compute-error'

# 降级日的 Loud 留痕去重：tick 每分钟一次，不能把同一件事刷成日志洪水。
_DEGRADED_LOUD_KEY: set = set()


def reset_degraded_loud_log() -> None:
    """清空"降级 Loud 留痕"去重表（测试用；也便于运维手工复位）。"""
    _DEGRADED_LOUD_KEY.clear()


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


def _best_effort_day(day) -> date:
    """归一化失败时，给降级结论挑一个**能被解释**的日期：能解析出就用它，否则用今天。

    仅用于 TradingDayVerdict.day 的展示/留痕；判定结果恒为 False（保守）。
    """
    try:
        return _normalize(day)
    except Exception:  # noqa: BLE001 - 此处只需一个可用日期
        return datetime.now().date()


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
        try:
            d = _normalize(day)
        except Exception as e:  # noqa: BLE001
            # 归一化失败同样不许击穿调用方（2026-09-14 w-0f022172 复查 m1）：
            # _normalize 对畸形输入会抛 ValueError（实测 check('')、check('2026/09/14')、
            # check('garbage')），而它在 try 之外 —— 调度器传进脏日期就会 500/整天跳过。
            # 保守下限：判非交易日 + 标降级 + 留痕。
            logger.warning('trading_day_guard_normalize_failed', raw=repr(day),
                           error=f'{type(e).__name__}: {e}')
            return TradingDayVerdict(
                _best_effort_day(day), False, SOURCE_COMPUTE_ERROR, True,
                f'日期入参无法解析（{day!r}: {e}）→ 保守判非交易日',
            )
        if use_cache:
            hit = _verdict_cache.get(d)
            if hit and (time.time() - hit[0]) < _CACHE_TTL_SECONDS:
                return hit[1]

        try:
            verdict = cls._compute(d)
        except Exception as e:  # noqa: BLE001
            # 最后一道兜底（2026-09-14 w-2129d492）：本 Guard 的契约是"数据源不可用 →
            # 保守判非交易日 + 标注降级"，**不是**把异常抛给调用方。_compute 只兜了取数异常，
            # 判定阶段的异常曾漏网：一次 TypeError 沿 resume_from_breakpoint →
            # start_orchestrator 上抛，把 orchestrator 的 tick 线程打死（09-14 全天 255 次
            # tick error，盘前撮合与 T1 结算全天未执行）。保护性判定不允许变成可用性故障，
            # 故此处兜底为"不可用/降级"并强制留痕，绝不静默。
            logger.warning('trading_day_guard_compute_failed',
                           day=d.isoformat(), error=f'{type(e).__name__}: {e}')
            verdict = TradingDayVerdict(
                d, False, SOURCE_COMPUTE_ERROR, True,
                f'交易日判定异常（{type(e).__name__}: {e}）→ 保守判非交易日',
            )
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
        """布尔便捷入口。

        2026-09-14（复查 M4）：**降级时不再静默**。调用方（orchestrator 的 tick /
        resume_from_breakpoint、watch_engine、kline/job 等 10 余处）拿到的只是布尔值，
        degraded/reason 在这一层被丢弃 —— 于是"数据源不可读"或"判定器异常"会表现为
        "今天不用干活"，整天的盘前撮合/T1 结算静默跳过，表面与正常休市无异。
        其代价与 09-14 那次事故等价，只是更安静。
        这里按日 + 来源去重补一条 ERROR 留痕（tick 每分钟一次，不能刷屏）；
        需要按降级原因分流处置的调用方请直接用 check() 拿 verdict。
        """
        verdict = cls.check(day)
        if verdict.degraded:
            cls._log_degraded_loud(verdict)
        return verdict.is_trading_day

    @classmethod
    def _log_degraded_loud(cls, verdict: 'TradingDayVerdict') -> None:
        key = (verdict.day.isoformat(), verdict.source)
        if key in _DEGRADED_LOUD_KEY:
            return
        _DEGRADED_LOUD_KEY.add(key)
        # 计算型降级（判定器自身异常）比数据源降级更严重：它是代码 bug，不是行情问题。
        emit = logger.error if verdict.source == SOURCE_COMPUTE_ERROR else logger.warning
        emit(
            'trading_day_guard_degraded_verdict_consumed_as_bool',
            day=verdict.day.isoformat(), source=verdict.source, reason=verdict.reason,
            note='该判定为"保守视为非交易日"，依赖它的工作当天会被跳过；'
                 '需要区分处置请改用 check() 取 verdict',
        )

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
        """(该日是否有K线, 最近K线日期)。

        2026-09-14（w-32314d00，REQ-24e15d B3）：原来把两个子查询塞进一条裸 SQL、
        再靠 isinstance(row, dict) 兼容两种结果形态；现拆成两个仓储方法，各自只返回一个值。
        """
        from adapters.outbound.repositories.kline_repository import KlineORMRepository

        repo = KlineORMRepository()
        exists_on_date = repo.has_bar_on_date(day)
        # 类型契约（2026-09-14 w-2129d492）：judge_trading_day 要拿它做日期相减
        # （today - latest_kline_date），必须是 date 而不是字符串。重构前裸 SQL 经 psycopg2
        # 直接回 date 对象；换成仓储后 get_latest_trade_date() 回 'YYYY-MM-DD' 字符串
        # → "今天 + 近 7 日有K线"的盘中启发式分支直接 TypeError（09-14 orchestrator 停摆根因）。
        # 无论取数层回 date / datetime / 字符串，都在此归一到 date（None 仍为 None）。
        raw_latest = repo.get_latest_trade_date()
        latest = _normalize(raw_latest) if raw_latest is not None else None
        return exists_on_date, latest
