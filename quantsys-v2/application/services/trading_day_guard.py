"""交易日判断唯一入口（步2 收口，2026-09-11，w-f4aa1f6a）

## 为什么需要它
交易日判断此前散落 6+ 处、各自实现不同，已造成真实事故：
- **2026-08-08（周六）5 个账户被写入净值快照**（agent_virtual/user_main/v13/v14/v15），
  污染净值、回撤、熔断与归因口径。
  ⚠️ **订正（2026-10-06，REQ-261006190953-fc43 卡 G）**：本行原写着「已标记某个合成标记列、
  并从统计口径排除」——**实测既不存在该列、全仓也没有一处代码引用它**，那是一条
  "未实现的缓解被写成既成事实"的注释（会让人以为脏数据已经处理过了）。真实状态：
  这类行**当时既没被标记、也没被排除**；本需求用「写入闸门 + 存量清理」处理，口径见
  `docs/requirements/REQ-261006190953-fc43/design/data-model.md` §1；
- `quant.trading_calendar` 长期**空表**，而 data_pipeline_service 仍从它读交易日集合
  → TimeAlignmentStage 拿到空日历、静默降级；
- 2026-08-12 事故：用"当天日K是否已落库"当唯一判据 → 06:30/14:30 的调度检查永远判"今天不是
  交易日" → v13/v14 调仓从不执行却被记为 success（静默失败）。

## 语义（唯一真源：judge_trading_day 纯函数 + 交易日历解析链）
- 周末 → 非交易日（`weekend`）
- 未来日期 → 非交易日（`future`）
- 其余 → 走 `application.services.trading_day_resolver.resolve_trading_day(day)`
  （与 `last_closed_trading_day` **共用同一条取数链**：`quant.trading_calendar` 表 →
  DataProviderManager → 周一~周五回退 + `degraded`）：
  - 日历答"该日是交易日" → 交易日（`trading-calendar`）
  - 日历答"该日不在交易日历中" → 非交易日（`trading-calendar-holiday`，精确覆盖法定节假日）
  - 解析链降级（工作日回退）→ **结论照用**但 `degraded=True` + 留痕/告警（不许静默，
    也不许把"日历不可用"当成"休市"）
  - 解析链异常 → 保守判非交易日 + `degraded=True` + `unavailable`
- K 线**只作事后交叉校验**（不再决定判定）：日历说交易日、该**过去**日却无日K
  → 记 `degraded=True` + 留痕（判定不变）。2026-10-04（REQ-261004154902-a7cd · FR-3）：
  「今天 + 近 7 日有K线」的启发式已**移除**——它把 2026 年国庆（10-05/06/07）判成交易日、
  把复市首日 10-08 判成休市（差 8 天 > 7）。

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
from typing import Any, Callable, Dict, Optional, Tuple, Union

import structlog

from application.services.trading_day_resolver import (
    TradingDayResult,
    resolve_trading_day,
)

logger = structlog.get_logger(__name__)

# 进程级 TTL 缓存：watch_engine / daily_orchestrator 是高频 tick（秒级），
# 不能每轮都查库（两次索引查询虽只要 ~0.12ms，但秒级 tick 会累积）。
_CACHE_TTL_SECONDS = 60
_verdict_cache: Dict[date, Tuple[float, 'TradingDayVerdict']] = {}

# 判定来源（R-013：数据来源必须可标注）
SOURCE_WEEKEND = 'weekend'
SOURCE_FUTURE = 'future'
# ── 2026-10-04（REQ-261004154902-a7cd · FR-3）：判定真源收敛到交易日历解析链 ──
#: 日历链答"该日是交易日"
SOURCE_CALENDAR = 'trading-calendar'
#: 日历链答"该日不在交易日历中"（法定节假日 / 休市）
SOURCE_CALENDAR_HOLIDAY = 'trading-calendar-holiday'
# 以下三个来源常量已**不再由 _compute 产出**（K 线不再是判定真源，只做事后交叉校验）。
# 保留常量为兼容既有导入，勿据此写新分支。
SOURCE_KLINE = 'kline-data'
SOURCE_INTRADAY = 'intraday-recent-market'
SOURCE_NO_DATA = 'no-kline-data'
SOURCE_UNAVAILABLE = 'unavailable'
# 判定器自身异常（既非"数据说不是交易日"，也非"数据源不可用"）。2026-09-14（复查 M4）：
# 与 SOURCE_UNAVAILABLE 分开，避免"代码 bug"被读成"今天真的不是交易日"。
SOURCE_COMPUTE_ERROR = 'compute-error'

# 降级日的 Loud 留痕去重：tick 每分钟一次，不能把同一件事刷成日志洪水。
_DEGRADED_LOUD_KEY: set = set()

# 日历链降级（工作日回退）的留痕去重：与上面那张表分开——同一天既可能"日历链降级"、
# 又可能"降级判定被布尔入口消费"，两件事都要各自可见，不能互相吃掉。
_CALENDAR_DEGRADED_LOGGED: set = set()

# ── 降级 → 主动外发告警（2026-09-14，用户放行）────────────────────────────────
# 为什么需要：09-14 的事故是"整天的盘前撮合/T1 结算被跳过而无人知晓"。光有 ERROR 日志
# 不够——日志没人盯就不算告警。这里把降级升级为主动外发（飞书），并做去噪与升级：
#   · 判定器自身异常（compute-error）= 代码 bug → 首次即 **high**；
#   · 数据源不可用（unavailable）→ 首次 normal，**持续超过 30 分钟仍未恢复**升 high 再报一次；
#   · 每个【日+来源】最多外发 2 条（首发 + 一次升级），避免 tick 每分钟刷屏。
_ALERT_COOLDOWN_SECONDS = 30 * 60
_ALERT_MAX_PER_DAY = 2
_degraded_alert_state: Dict[Tuple[str, str], Dict[str, Any]] = {}

# 外发通道（依赖注入，默认 None = 不主动外发）。
# 守卫是热路径模块，不自己 import 通知栈：由应用启动时注入
# （adapters/inbound/fastapi_app/main.py → install_degraded_alert_notifier）。
_degraded_alert_sink: Optional[Callable[[str, str, str], bool]] = None


def install_degraded_alert_notifier(sink: Optional[Callable[[str, str, str], bool]]) -> None:
    """注入降级告警的外发通道。

    sink(title, content, urgency) -> bool；传 None 可关闭外发（测试/离线环境）。
    签名里只有原始类型，守卫不需要认识 NotificationFacade/领域模型。
    """
    global _degraded_alert_sink
    _degraded_alert_sink = sink


def reset_degraded_loud_log() -> None:
    """清空"降级 Loud 留痕"与"降级外发"去重表（测试用；也便于运维手工复位）。"""
    _DEGRADED_LOUD_KEY.clear()
    _CALENDAR_DEGRADED_LOGGED.clear()
    _degraded_alert_state.clear()


def _now_seconds() -> float:
    return time.time()


def notify_degraded(title: str, content: str, urgency: str) -> bool:
    """生产用降级告警通道：经 NotificationFacade 发飞书（失败只记日志，绝不抛出）。

    为什么放在守卫模块而不是 main：通道实现属于"守卫的输出端口"，放这里让
    install_degraded_alert_notifier(notify_degraded) 成为启动期一行接线，
    同时保持守卫核心（判定/去重）不依赖通知栈——延迟 import，调用时才解析。
    """
    try:
        from application.notification import get_notification_facade

        return bool(get_notification_facade().send_card(
            title=title, content=content,
            urgency='high' if urgency == 'high' else 'normal',
        ))
    except Exception as e:  # noqa: BLE001 - 告警失败不影响判定
        logger.error('trading_day_guard_alert_notify_failed', error=str(e)[:200])
        return False


def judge_trading_day(
    day: date,
    *,
    kline_exists_on_date: bool,
    latest_kline_date: Optional[date],
    today: date,
    calendar_has_day: Optional[bool] = None,
) -> bool:
    """判定某天是否为交易日（纯函数，可单测；语义见模块 docstring）。

    2026-09-11（w-f4aa1f6a）：从 live_trading.simulation_trader 提升为共享唯一实现，
    原处保留同名再导出以兼容既有调用与测试。

    2026-10-04（REQ-261004154902-a7cd · FR-3）：末位新增可选入参 `calendar_has_day`。
    - `calendar_has_day=None`（缺省）→ **完全退回旧逻辑**（K 线口径），既有 8 条单测不破；
    - `calendar_has_day` 为 bool → 以交易日历为准：周末/未来仍是 False，其余直接取该值，
      K 线参数不参与判定（K 线在 `TradingDayGuard._compute` 里只做事后交叉校验）。
    """
    if day.weekday() >= 5:
        return False
    if day > today:
        return False
    if calendar_has_day is not None:
        return bool(calendar_has_day)
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
        """判定链（唯一实现）：周末 → 未来 → 交易日历解析链 → K 线事后交叉校验。

        2026-10-04（REQ-261004154902-a7cd · FR-3）：原「今天 + 近 7 日有 K 线」启发式已删除。
        """
        today = datetime.now().date()

        if d.weekday() >= 5:
            return TradingDayVerdict(d, False, SOURCE_WEEKEND, False, '周末')
        if d > today:
            return TradingDayVerdict(d, False, SOURCE_FUTURE, False, '未来日期')

        # ③ 交易日历解析链（表 → provider → 工作日回退）；与探针共用同一条链。
        try:
            resolved: TradingDayResult = resolve_trading_day(d)
        except Exception as e:  # noqa: BLE001 - 数据源不可用必须可见且保守
            logger.warning('trading_day_guard_datasource_unavailable', day=d.isoformat(), error=str(e))
            return TradingDayVerdict(
                d, False, SOURCE_UNAVAILABLE, True,
                f'交易日历解析链不可用（{e}）→ 保守判非交易日',
            )

        # 判据：链给出的 `<= d` 最大交易日 == d ⟺ 该日是交易日（见 resolver 模块 docstring）
        calendar_has_day = (resolved.date == d)
        degraded = bool(resolved.degraded)
        notes = []
        if resolved.degraded:
            notes.append('日历链降级：按周一~周五口径判定，法定节假日可能被误判')
            cls._log_calendar_chain_degraded(d, resolved)

        # K 线只作**事后**交叉校验：日历说交易日、该过去日却无日K → 记降级（判定不变）。
        # 当日不查（日K 17:40 才落库，「今天还没K线」正是被删除的启发式）。
        kline_exists = False
        if calendar_has_day:
            kline_exists, conflict, note = cls._kline_cross_check(d, today)
            if conflict:
                degraded = True
                notes.append(note)

        is_trading = judge_trading_day(
            d,
            kline_exists_on_date=kline_exists,
            latest_kline_date=None,
            today=today,
            calendar_has_day=calendar_has_day,
        )
        if is_trading:
            source = SOURCE_CALENDAR
            reason = f'交易日历判定为交易日（来源 {resolved.source}）'
        else:
            source = SOURCE_CALENDAR_HOLIDAY
            reason = f'交易日历判定为非交易日（来源 {resolved.source}：该日不在交易日历中）'
        if notes:
            reason = f'{reason}；' + '；'.join(notes)
        return TradingDayVerdict(d, is_trading, source, degraded, reason)

    @classmethod
    def _kline_cross_check(cls, d: date, today: date) -> Tuple[bool, bool, str]:
        """K 线事后交叉校验 → `(该日是否有日K, 是否冲突/不可用, 留痕说明)`。

        只对**过去**日做（`d >= today` 直接跳过：当日日K 17:40 才落库）。
        取数异常不再等于"非交易日"——判定已由日历给出，这里只如实标注降级。
        """
        if d >= today:
            return False, False, ''
        try:
            exists, _latest = cls._kline_stats(d)
        except Exception as e:  # noqa: BLE001 - 交叉校验不可用必须可见，但不得改变判定
            logger.warning('trading_day_guard_kline_crosscheck_failed',
                           day=d.isoformat(), error=str(e)[:200])
            return False, True, '日K交叉校验不可用（判定仍以日历为准）'
        if not exists:
            logger.warning(
                'trading_day_guard_calendar_kline_conflict',
                day=d.isoformat(),
                note='日历说该日是交易日，但该日无日K数据；判定不变，需人工核对日历或行情源',
            )
            return False, True, '该日无日K数据（日历与K线冲突，判定不变）'
        return True, False, ''

    @classmethod
    def _log_calendar_chain_degraded(cls, d: date, resolved: TradingDayResult) -> None:
        """解析链降级（工作日回退）必须可见：按【日+链来源】去重，避免 tick 刷屏。"""
        key = (d.isoformat(), resolved.source)
        if key in _CALENDAR_DEGRADED_LOGGED:
            return
        _CALENDAR_DEGRADED_LOGGED.add(key)
        logger.warning(
            'trading_day_guard_calendar_chain_degraded',
            day=d.isoformat(), calendar_source=resolved.source,
            note='交易日历与 provider 均不可用，已按周一~周五口径判定；'
                 '法定节假日会被当作交易日（判为交易日时不可当作"已经核过市"）',
        )

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
            cls._alert_degraded(verdict)
        return verdict.is_trading_day

    @classmethod
    def _log_degraded_loud(cls, verdict: 'TradingDayVerdict') -> None:
        key = (verdict.day.isoformat(), verdict.source)
        if key in _DEGRADED_LOUD_KEY:
            return
        _DEGRADED_LOUD_KEY.add(key)
        # 计算型降级（判定器自身异常）比数据源降级更严重：它是代码 bug，不是行情问题。
        emit = logger.error if verdict.source == SOURCE_COMPUTE_ERROR else logger.warning
        # 降级 ≠ 一定是"判非交易日"：日历链降级时结论照用（工作日口径），
        # 判为交易日意味着"可能把休市日当交易日"——留痕要说清是哪种。
        if verdict.is_trading_day:
            note = ('该判定为"日历不可用时的周一~周五口径"，可能把休市日当作交易日；'
                    '需要区分处置请改用 check() 取 verdict')
        else:
            note = ('该判定为"保守视为非交易日"，依赖它的工作当天会被跳过；'
                    '需要区分处置请改用 check() 取 verdict')
        emit(
            'trading_day_guard_degraded_verdict_consumed_as_bool',
            day=verdict.day.isoformat(), source=verdict.source, reason=verdict.reason,
            note=note,
        )

    @classmethod
    def _alert_degraded(cls, verdict: 'TradingDayVerdict') -> None:
        """把降级通过注入的通道主动外发（飞书）。未注入/失败都只留痕，绝不影响判定。

        去噪规则见模块常量：每【日+来源】首发 1 条；数据源类问题持续 30 分钟仍降级再升
        一次 high；最多 2 条/天。判定器自身异常（可能是代码 bug）首发即 high。
        """
        sink = _degraded_alert_sink
        if sink is None:
            return
        key = (verdict.day.isoformat(), verdict.source)
        state = _degraded_alert_state.get(key)
        now = _now_seconds()
        is_bug = verdict.source == SOURCE_COMPUTE_ERROR

        if state is None:
            urgency = 'high' if is_bug else 'normal'
        elif state.get('count', 0) >= _ALERT_MAX_PER_DAY:
            return
        elif not is_bug and now - float(state.get('last', 0)) >= _ALERT_COOLDOWN_SECONDS:
            urgency = 'high'          # 持续未恢复 → 升级再报一次
        else:
            return

        if verdict.is_trading_day:
            # 日历链降级时结论照用（工作日口径）→ 风险方向相反：可能把休市日当交易日而误开火。
            headline = (
                '交易日判定已降级：交易日历与 provider 均不可用，现按「周一~周五」口径判为**交易日**。\n'
                '若当天实为法定休市，盘前撮合 / T1 结算 / 盯盘轮转会误开火——请尽快核对行情源与\n'
                'quant.trading_calendar 刷新任务。'
            )
        else:
            headline = (
                '交易日判定已降级为「保守视为非交易日」，依赖它的工作今天会被跳过'
                '（盘前撮合 / T1 结算 / 盯盘轮转）。这与 2026-09-14 那次"或与全天不动"同类，'
                '请尽快确认。'
            )
        content = (
            headline + '\n\n'
            '日期: %s\n'
            '来源: %s\n'
            '原因: %s\n'
            '判定结果: is_trading_day=%s / degraded=%s\n\n'
            '处置建议: 来源为 compute-error 时优先查代码/入参；为 unavailable 时先查数据库与行情源连通性。'
            % (verdict.day.isoformat(), verdict.source, verdict.reason,
               verdict.is_trading_day, verdict.degraded)
        )
        try:
            ok = bool(sink('交易日判定降级（判定层异常/数据源不可用）', content, urgency))
        except Exception as e:  # noqa: BLE001 - 告警失败绝不能反过来影响判定
            logger.warning('trading_day_guard_alert_send_failed',
                           day=verdict.day.isoformat(), source=verdict.source, error=str(e)[:200])
            return

        _degraded_alert_state[key] = {
            'count': (state or {}).get('count', 0) + 1,
            'last': now,
            'urgency': urgency,
        }
        logger.info('trading_day_guard_degraded_alert_sent',
                    day=verdict.day.isoformat(), source=verdict.source,
                    urgency=urgency, delivered=ok,
                    alert_seq=_degraded_alert_state[key]['count'])

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
