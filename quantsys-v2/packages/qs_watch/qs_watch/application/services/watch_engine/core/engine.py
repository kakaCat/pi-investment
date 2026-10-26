"""WatchEngine 盯盘引擎核心

tick() 为一次完整判定（同步、可单测）；run_forever() 为常驻循环。
仅交易日（周一至周五）9:30-11:30 / 13:00-15:00 运行。
"""
import os
import threading
import time as time_module
from datetime import datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional, Set

import structlog

from qs_market_data.application.services.quote_providers.base import (
    AllProvidersCoolingDownError,
)

from qs_watch.application.services.watch_engine.conditions import (
    EvalContext, evaluate,
)
from qs_watch.application.services.watch_engine.market_watch_service import MARKET_SCOPES
from qs_watch.application.services.watch_engine.rule_evaluator import RuleEvaluator
from qs_watch.application.services.watch_engine.staged_break_manager import (
    OUTCOME_CONFIRMED, OUTCOME_EXPIRED, StagedBreakManager,
)
from qs_watch.application.services.watch_engine.pipeline import (
    PIPELINE, PipelineResult, TriggerContext,
)
from qs_watch.application.services.watch_engine.pipeline.constants import (
    DAILY_CAP_REASON, SUPPRESSED_TRIGGER_REASON,
)
from qs_watch.application.services.watch_engine.state_manager import StateManager
from qs_watch.application.services.watch_engine.trigger_judge import TriggerJudge
from qs_watch.domain.watch.services.disposition import (
    CONSTITUTIONAL_INTENTS, DEDUP_WINDOW_SEC, DISPOSITION_AUTO_OBSERVED, intent_of,
)
from qs_watch.domain.watch.services import noise_policy
from qs_watch.application.services.watch_engine.deduplication_manager import DeduplicationManager
from qs_watch.application.services.watch_engine.disposition_engine import DispositionEngine
from qs_watch.application.services.watch_engine.environment_gate_service import (
    EnvironmentGateService,
)
from qs_watch.application.services.watch_engine.escalation_coordinator import EscalationCoordinator
from qs_watch.domain.watch.services.escalation_checker import EscalationChecker
from qs_watch.domain.watch.models import QuoteData
from qs_trading.domain.trading.services.market_session_policy import (
    TOTAL_TRADING_MINUTES,   # 单一出处（RFC 016 §8.1）；本模块继续再导出以兼容既有 importer
    MarketSessionPolicy,
)

from qs_watch.application.services.watch_engine._repo_resolver import (
    runtime_state_store,
)

logger = structlog.get_logger(__name__)

# 运行态持久化开关（REQ-c9f899 R10）：默认关闭 —— 关掉时行为与改造前完全一致
RUNTIME_PERSIST_ENV = 'WATCH_RUNTIME_PERSIST_ENABLED'


def _runtime_persist_enabled() -> bool:
    return os.getenv(RUNTIME_PERSIST_ENV, 'false').strip().lower() in (
        '1', 'true', 'yes', 'on')


# 归档理由文案（抑噪 / 日上限）随流水线阶段下沉到 `pipeline/constants.py`
# （阶段模块反向 import engine 会成环）。此处 re-export，既有
# `from ...engine import DAILY_CAP_REASON` 的调用方零改动。

#: 两段式伏击「触及未确认」的归档理由（2026-10-19 P1）：观察窗到期确认未成立，
#: 落一条 suppressed 样本供复盘（盘感样本的事实源），不通知、不占日配额。
STAGED_EXPIRED_REASON = '伏击观察窗到期未确认（触及≠信号），仅归档样本'

#: 确认核验未通过的归档理由前缀（2026-10-20，机会闭环 M2）：staged_break 确认成立
#: 但利空/流动性/共振三道核验有明确失败 → 判「假信号」，只归档样本供复盘，
#: 不通知、不进摘要队列、不建待办。具体失败项接在冒号后（pipeline.reason）。
CONFIRM_VERIFY_FAILED_REASON = '假信号：确认核验未通过，仅归档样本'

#: 环境闸豁免理由（用户 2026-10-20 裁定）：环境不达标时 exit_stop/保护线类信号
#: **照常通知**——止损被吞 = 资损风险，与日上限/dedup 的宪法豁免同源。
#: 判定只认规则声明的动作类型与结构化锚点（见 `_env_gate_exemption`），
#: 绝不匹配消息文案；具体锚点接在括号里，事件与日志可回溯。
ENV_GATE_EXEMPT_REASON = '止损/保护线豁免：环境闸放行，照常通知'

# ── 规则级盯盘频率（RFC 017 §2.3，`per-rule-interval` 卡）──────────────────

#: 规则级频率的引擎侧下限（秒）：保护行情源。仓储只拒绝无法解释的值（<1/负数/布尔），
#: 因此 1–4s 是**可落库但不可执行**的配置——引擎按 5s 执行并 warn（不静默失真）。
RULE_INTERVAL_FLOOR_SEC = 5


def _rule_interval_sec(rule) -> Optional[int]:
    """规则的 `interval_sec` 读口径（fail-open）：正整数秒 / None（跟随全局档）。

    语义与仓储 `rule_interval_sec` / `normalize_interval_sec` 一致：NULL、缺列
    （旧库未迁移）、非法值一律 → None。**引擎不 import 仓储**：`qs_watch` 是 L1
    包，仓储属 L0 适配层，反向依赖会破坏包边界（`packages/qs_watch/CLAUDE.md`）；
    故此处只读属性、按同一口径归一，两处口径由 `test_watch_per_rule_interval.py`
    与仓储测试共同钉住。
    """
    try:
        raw = getattr(rule, 'interval_sec', None)
    except Exception:  # noqa: BLE001 - 分离态/过期对象/缺列懒加载失败都按未设置处理
        return None
    if raw is None or isinstance(raw, bool):
        return None
    try:
        seconds = int(raw)
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 1 else None


# ── 持仓状态门（RFC 017 §2.2，`position-state-branch` 卡）────────────────────
#
# 为什么在 tick 层而不是 `_process_condition` 的流水线：状态门回答「这条规则这
# 一拍要不要判」，结论必须在**取价之前**就有——放进流水线意味着先取价、先算条
# 件、再丢弃结果，与「未到期不取价」（RFC §2.3）是同一条纪律。位置：活性过滤之
# 后、到期门之前（RFC 017 §2.2 的实施裁定）；pipeline 仍是 15 阶段，不增第 16 个。
#
# 分支表（`t_trade` 按订正归 holding 分支）：
#
#   | position_state | entry | add_position / t_trade / exit_* | 观察类 |
#   |----------------|-------|---------------------------------|--------|
#   | 'none'         | 求值  | 跳过（无仓位无可加/可卖）        | 求值   |
#   | 'holding'      | 跳过  | 求值（含增仓，2026-10-22 裁定）  | 求值   |
#   | None（未知）   | 求值  | 求值                            | 求值   |
#   注：add_position 原归「持仓跳过」，2026-10-22 用户裁定「持仓的看增仓」——
#   已持仓回调加仓是合理操作，改到 holding 求值、none 跳过（空仓无仓可加）。
#
# 两条硬口径（改这里之前先读 RFC 017 §2.2 / §4.6）：
#   1. **None 不是 'none'**：NULL/缺列/非法值 → 状态不可知 → 一律求值（旧库与
#      存量规则行为等价）；
#   2. **宪法级止损永不因状态跳过**：`exit_stop` 对上 'none'（状态滞后）照常求值
#      ——「已买入但状态还没翻转」时静默跳过止损 = 资损风险；宁可多喊一次。

#: 状态值（与仓储 `normalize_position_state` 同一值域；这里不重复实现归一）。
POSITION_STATE_NONE = 'none'
POSITION_STATE_HOLDING = 'holding'

#: 意图族：entry（建仓）只在「确认空仓」时求值（持仓时跳过——已有仓位不再喊建仓）。
POSITION_STATE_ENTRY_INTENTS = ('entry',)

#: 意图族：add_position（增仓）只在「确认持仓」时求值（2026-10-22 用户裁定
#: 「持仓的看增仓」——已持仓回调加仓是合理操作；空仓跳过，无仓可加）。
POSITION_STATE_ADD_INTENTS = ('add_position',)

#: 意图族：exit 族只在「确认持仓」时求值（空仓跳过）。
#: `t_trade` 归持仓分支：A股 T+1 下没有底仓无法做 T（RFC 017 §2.2 的订正）。
POSITION_STATE_EXIT_INTENTS = ('t_trade', 'exit_stop', 'exit_take_profit', 'exit_reduce')

#: 意图族标签（日志/事件用）。
POSITION_FAMILY_ENTRY = 'entry'
POSITION_FAMILY_ADD = 'add'
POSITION_FAMILY_EXIT = 'exit'
POSITION_FAMILY_OBSERVE = 'observe'

#: 跳过原因（日志可观测；也是「本拍为什么没判这条规则」的唯一答案）。
POSITION_STATE_SKIP_ENTRY_HELD = 'position_state_entry_skipped_holding'
POSITION_STATE_SKIP_ADD_FLAT = 'position_state_add_skipped_flat'
POSITION_STATE_SKIP_EXIT_FLAT = 'position_state_exit_skipped_flat'

#: 不一致事件 kind（tick 事件流里与 trigger 事件区分，不伪装成一次触发）。
STATE_MISMATCH_EVENT = 'state_mismatch'

#: `state_mismatch` 事件的原因码（不一致但 fail-open 的两类）。
MISMATCH_UNREADABLE = 'position_state_unreadable'
MISMATCH_STOP_WITHOUT_HOLDING = 'constitutional_exit_without_holding'

#: `getattr` 未取到属性（缺列/旧部署）与读取抛异常 的两种哨兵。
_ATTR_MISSING = object()
_ATTR_READ_ERROR = object()

#: 读口径缓存（延迟 import 仓储 `rule_position_state`；见 `_load_position_state_reader`）。
_READER_UNSET = object()
_POSITION_STATE_READER = _READER_UNSET


def position_state_family(intent) -> str:
    """意图 → 持仓分支族（entry / exit / observe）。

    只做**归类**，不做意图推导：intent 必须来自 `disposition.intent_of(rule)`
    （与处置/分级同源），否则「声明 buy 却没写 intent」的规则会绕过分支
    （rule_guard 修过的同一个坑）。未知意图一律 observe = 照常求值。
    """
    text = str(intent or '').strip()
    if text in POSITION_STATE_ENTRY_INTENTS:
        return POSITION_FAMILY_ENTRY
    if text in POSITION_STATE_ADD_INTENTS:
        return POSITION_FAMILY_ADD
    if text in POSITION_STATE_EXIT_INTENTS:
        return POSITION_FAMILY_EXIT
    return POSITION_FAMILY_OBSERVE


def _load_position_state_reader():
    """延迟加载仓储读口径 `rule_position_state()`（L1 引擎不反向常驻 import L0）。

    失败只记一次 error 并缓存 None：读不到口径 = 状态不可知 → 全部规则照常求值
    （fail-open），绝不因为没读到状态就静默不判（RFC 017 §4.6）。
    """
    global _POSITION_STATE_READER
    if _POSITION_STATE_READER is not _READER_UNSET:
        return _POSITION_STATE_READER
    try:
        # 2026-10-21：读口径正典在 qs_watch.domain.watch.services（qs_watch 内部域名引，无跨包）
        from qs_watch.domain.watch.services.position_state_policy import rule_position_state
    except Exception as e:  # noqa: BLE001 - 旧部署/缺依赖：读不到就按不可知
        logger.error('持仓状态读口径不可用（全部规则按状态不可知 fail-open）',
                     error=str(e))
        _POSITION_STATE_READER = None
        return None
    _POSITION_STATE_READER = rule_position_state
    return _POSITION_STATE_READER


def read_rule_position_state(rule) -> Optional[str]:
    """规则持仓状态读口径：`'none'` / `'holding'` / `None`（**不可知**）。

    **必须**走仓储 `rule_position_state()`：NULL、缺列、非法值 → None 的归一
    只有那一处实现，引擎侧绝不自己写第二套（口径漂移就是漏判止损的入口）。
    读口径本身不可用（import 失败）时同样返回 None —— 未知一律 fail-open。
    """
    reader = _load_position_state_reader()
    if reader is None:
        return None
    try:
        return reader(rule)
    except Exception as e:  # noqa: BLE001 - 读失败 = 不可知（不是"确认空仓"）
        logger.error('持仓状态读取异常（按状态不可知 fail-open）',
                     rule_id=getattr(rule, 'id', None), error=str(e))
        return None


def _declared_position_state(rule):
    """规则上**原始声明**的 position_state（只用于识别"声明了但读不懂"）。

    与读口径分开：缺列/未迁移返回 `_ATTR_MISSING`（旧行为，静默 fail-open），
    读取抛异常返回 `_ATTR_READ_ERROR`（异常，须留痕）；其余原样返回。
    """
    try:
        return getattr(rule, 'position_state', _ATTR_MISSING)
    except Exception:  # noqa: BLE001 - 分离态/懒加载失败：读不到就按异常处理
        return _ATTR_READ_ERROR


def _state_mismatch_payload(rule, state, intent, family, reason, declared) -> dict:
    """不一致事件载荷（warn 日志与 `state_mismatch` 事件共用同一份事实）。"""
    return {
        'kind': STATE_MISMATCH_EVENT,
        'rule_id': getattr(rule, 'id', None),
        'symbol': getattr(rule, 'symbol', None),
        'intent': intent,
        'intent_family': family,
        'position_state': state,
        'declared_position_state': (
            None if declared is _ATTR_MISSING or declared is _ATTR_READ_ERROR
            else repr(declared)),
        'reason': reason,
        'fail_open': True,   # 语义：本条仍照常求值（不是 suppression）
    }


def position_state_verdict(rule):
    """状态门判定：返回 `(skip_reason, mismatch)`。

    `skip_reason` 非空 = 本拍不判这条规则（entry 族在持仓 / exit 族在确认空仓）；
    `mismatch` 非空 = 状态与意图不一致但 **fail-open 照常求值**，由 tick 在真的
    记录一次触发时落 `state_mismatch` 事件——不触发就不刷事件，否则一条空仓止损
    规则每拍刷一条不一致，真实异常会被淹掉。

    市场级规则（scope ∈ MARKET_SCOPES）不在此门管辖：它们的"标的"是市场快照
    伪标的（指数/板块/情绪），没有个股持仓语义。
    """
    if getattr(rule, 'scope', None) in MARKET_SCOPES:
        return None, None
    intent = intent_of(rule)          # 与处置/分级同源，不新造推导
    family = position_state_family(intent)
    state = read_rule_position_state(rule)
    if state is None:
        declared = _declared_position_state(rule)
        if declared is not _ATTR_MISSING and declared is not None:
            # 声明了非空值却读不出：非法值/读取异常 —— 旧规则缺列是 _ATTR_MISSING。
            return None, _state_mismatch_payload(
                rule, state, intent, family, MISMATCH_UNREADABLE, declared)
        return None, None             # 不可知 → fail-open，不见怪
    if intent in CONSTITUTIONAL_INTENTS and state != POSITION_STATE_HOLDING:
        # 宪法级止损对上「确认空仓」：可能是状态滞后 → 不跳过，留痕后照常求值。
        return None, _state_mismatch_payload(
            rule, state, intent, family, MISMATCH_STOP_WITHOUT_HOLDING,
            _declared_position_state(rule))
    if family == POSITION_FAMILY_ENTRY and state == POSITION_STATE_HOLDING:
        return POSITION_STATE_SKIP_ENTRY_HELD, None
    if family == POSITION_FAMILY_ADD and state == POSITION_STATE_NONE:
        # 增仓对确认空仓无意义（无仓可加）→ 跳过；已持仓回调加仓在上方 holding 分支照常求值。
        return POSITION_STATE_SKIP_ADD_FLAT, None
    if family == POSITION_FAMILY_EXIT and state == POSITION_STATE_NONE:
        return POSITION_STATE_SKIP_EXIT_FLAT, None
    return None, None


def _build_runtime_store():
    """懒构造运行态适配器；装配失败只记日志返回 None（降级为纯内存，不阻断启动）。

    延迟 import：默认关闭时不必为未启用的持久化加载 ORM/适配器链路。
    """
    try:

        return runtime_state_store()
    except Exception as e:  # noqa: BLE001
        logger.error('运行态持久化适配器装配失败，降级为纯内存（冷却重启仍会丢）',
                     error=str(e))
        return None


#: 心跳开关与节流（REQ-c9f899 t10）。心跳与「状态持久化」开关**解耦**：
#: 持久化关掉时冷却是可接受的退化，但没有心跳则「引擎线程死了」这件事无人发现——
#: 那正是 2026-08-05 事故（规则在、无人判定）的模式。
HEARTBEAT_ENABLED_ENV = 'WATCH_HEARTBEAT_ENABLED'
HEARTBEAT_INTERVAL_ENV = 'WATCH_HEARTBEAT_INTERVAL_SEC'
DEFAULT_HEARTBEAT_INTERVAL_SEC = 30.0


def _heartbeat_enabled() -> bool:
    return os.getenv(HEARTBEAT_ENABLED_ENV, 'true').strip().lower() in ('1', 'true', 'yes', 'on')


def elapsed_trading_fraction(now: datetime) -> float:
    """当日已过交易时间比例（0~1），供 volume_surge 折算同期均量

    RFC 016 §8.1：折算口径收敛到 `MarketSessionPolicy.session_progress`
    （此前此处是又一份实现，`TOTAL_TRADING_MINUTES` 也是本地副本）。

    与旧实现的差异**仅在子分钟**：旧用小数分钟、策略按整分钟向下取整（≤0.4%），
    **整分钟时刻完全一致**（既有断言 9:30→0.0 / 11:30→0.5 / 14:00→0.75 / 15:00→1.0 全部成立）。
    """
    return MarketSessionPolicy.session_progress(now.time(), is_trading_day=True)


class WatchEngine:
    def __init__(self, rule_repo, quote_service, notifier,
                 avg_volume_provider: Optional[Callable[[str], Optional[float]]] = None,
                 fund_flow_provider: Optional[Callable[[str], Optional[dict]]] = None,
                 kline_closes_provider: Optional[Callable[[str], Optional[tuple]]] = None,
                 base_interval: int = 60, fast_interval: int = 10,
                 buffer_ratio: float = 0.2, history_minutes: int = 30,
                 now_fn: Callable[[], datetime] = datetime.now,
                 escalation_checker: Optional[EscalationChecker] = None,
                 position_value_provider: Optional[Callable] = None,
                 account_total_provider: Optional[Callable] = None,
                 digest_service=None, ledger=None, meta_review_service=None,
                 position_lifecycle_service=None, market_watch_service=None,
                 pool_watch_service=None, news_watch_service=None,
                 runtime_state_store=None,
                 todo_service=None, observe_agg=None, staged_manager=None,
                 outcome_backfill_service=None, environment_gate_service=None,
                 confirm_verify_pipeline=None):
        self.rule_repo = rule_repo
        self.quote_service = quote_service
        self.notifier = notifier
        self.observe_agg = observe_agg
        self.avg_volume_provider = avg_volume_provider
        # 2026-10-20 扩展条件（ma_break/rsi/fund_flow）的取数 provider；None=对应条件降级
        self.fund_flow_provider = fund_flow_provider
        self.kline_closes_provider = kline_closes_provider
        # 市场环境复合门缓存（_market_state 用，60s TTL）——全局环境闸与
        # per-rule market_gate 共用同一份 MarketState 快照（一次取数两处用）。
        self._gate_cache: tuple = (None, None)
        # 全局环境闸（2026-10-20）：tick 前置判一次（指数/板块主线/资金氛围）。
        # 默认服务是纯判定（无 I/O），取数由 market_watch_service.state_provider 承担；
        # 构造函数留注入点只为测试调阈值，生产装配无需改动（默认即开）。
        self.environment_gate = environment_gate_service or EnvironmentGateService()
        # 上一次拦截原因：tick 级日志只在原因变化时打，避免拦截期每 10s 刷屏
        self._last_env_gate_reason: Optional[str] = None
        # 确认核验流水线（2026-10-20，机会闭环 M2）：staged_break 确认成立后
        # 依次跑 利空/流动性/共振，全过才进触发流水线；失败归档假信号样本。
        # None = 未装配 → 行为与改造前完全一致（确认即进流水线），既有测试/回滚零影响。
        self.confirm_verify_pipeline = confirm_verify_pipeline
        self.base_interval = base_interval
        self.fast_interval = fast_interval
        self.buffer_ratio = buffer_ratio
        self.history_minutes = history_minutes
        self.now_fn = now_fn
        self.escalation_checker = escalation_checker or EscalationChecker()

        # 均量取数保护（按日缓存/硬超时/失败熔断）→ RuleEvaluator，见下方装配
        # 触发/去重/介入状态收敛到 StateManager（2026-09-14 重构 P1，行为等价迁移）：
        # 原先 9 个状态字段散在本类，既无法整体快照（线上定位靠猜），也无法脱离
        # 引擎实例单测。搬入后由 snapshot() 统一观测。
        self.dedup_window_sec = DEDUP_WINDOW_SEC
        # 运行态持久化（REQ-c9f899 R10）：路径与开关只在此处一处收敛。
        #   显式注入 store（tests/调用方装配）视为启用；否则读 WATCH_RUNTIME_PERSIST_ENABLED
        #   （默认 false → store=None → StateManager 全部持久化逻辑 no-op，行为等价）。
        if runtime_state_store is not None:
            self._runtime_store = runtime_state_store
        elif _runtime_persist_enabled():
            self._runtime_store = _build_runtime_store()
        else:
            self._runtime_store = None
        self._runtime_restored = False
        # 心跳（t10）：独立于持久化开关；首次写入时间与失败计数供观测
        self._heartbeat_store = None
        self._last_heartbeat_at = None
        self._heartbeat_failures = 0
        # 独立心跳写线程（2026-10-16）：与主循环 tick 时长彻底解耦——主循环任何一段
        # （取价/摘要门投递/落库）卡住时，存活信号仍按 interval 续写，巡检不误报。
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop = threading.Event()
        try:
            self._heartbeat_interval_sec = float(
                os.getenv(HEARTBEAT_INTERVAL_ENV, str(DEFAULT_HEARTBEAT_INTERVAL_SEC)))
        except (TypeError, ValueError):
            self._heartbeat_interval_sec = DEFAULT_HEARTBEAT_INTERVAL_SEC
        self.state = StateManager(event_retention_min=30,
                                  dedup_window_sec=self.dedup_window_sec,
                                  store=self._runtime_store)
        # 两段式伏击状态机（2026-10-19 P1）：staged_break 条件的触及→观察→确认
        # 状态归它管；与 StateManager 共用同一个运行态 store（各自专用方法，互不干扰）。
        self.staged = staged_manager or StagedBreakManager(store=self._runtime_store)
        # 去重（同标的同向合并 + 跨规则重叠转治理）→ DeduplicationManager
        self.dedup = DeduplicationManager(self.state, self.dedup_window_sec)
        # 规则取数保护（2026-09-14 重构 P1）：原内联在本类的按日缓存 / 硬超时 /
        # 失败熔断移入 RuleEvaluator；引擎保留 _get_avg_volume 薄封装（测试与
        # e2e monkeypatch 依赖该入口名）。
        self.evaluator = RuleEvaluator(avg_volume_provider=avg_volume_provider)
        # 触发判据（闩锁/冷却/标记）→ TriggerJudge（2026-09-14 重构 P1）
        self.judge = TriggerJudge(self.state)
        # 介入判据（REQ-f08def P3，RFC 014 v3 §3）：金额门/增量门/经济门/预算门所需的注入
        # 处置决策（GateContext 组装 + domain decide）→ DispositionEngine
        self.disposition = DispositionEngine(
            state=self.state,
            position_value_provider=position_value_provider,
            account_total_provider=account_total_provider,
        )
        # 升级协调（频率/共振统计 + 调用 domain EscalationChecker）→ EscalationCoordinator
        self.escalation = EscalationCoordinator(self.state, self.now_fn, escalation_checker)
        # 增量门（同标的同议题 4h 冷却）与当日介入计数 → StateManager
        # 摘要门（REQ-f08def P2/P4）：何时唤醒 agent 的判据由本服务负责，
        # 挂在引擎 loop 里——引擎本就是盯盘唯一宿主，无需外部定时器/脚本。
        self.digest_service = digest_service
        # 介入记账（P4）：预算计数落库，修掉"重启清零 → 每日预算形同虚设"
        self.ledger = ledger
        # 元触发复核（P7）：规则不能无限期盯下去（频次/静默/滞留/到期 → 回到 agent）
        self.meta_review_service = meta_review_service
        self._last_meta_scan_date = None
        # 持仓生命周期联动（P5）：买入成交 → 等买规则退役 + 补挂止损；清仓 → 卖出族收摊
        self.position_lifecycle_service = position_lifecycle_service
        self._last_lifecycle_date = None
        # 池级盯盘（2026-10-20）：选池↔盯盘接线，每日对账成员↔规则
        self.pool_watch_service = pool_watch_service
        self._last_pool_sync_date = None
        # 收盘体检日报的日幂等（2026-10-20）
        self._last_review_sent_date = None
        # 消息监控（2026-10-20 流程图 M/N）：持仓突发消息→破坏逻辑评估提醒
        self.news_watch_service = news_watch_service
        self._last_held_map_date = None   # P2：持仓板块映射的每日重建水位
        # P3 预判验证闭环（2026-10-20）：走势回填服务，sidecar 每日驱动；None=未装配不跑
        self.outcome_backfill_service = outcome_backfill_service
        self._last_outcome_backfill_date = None
        # 市场级盯盘（P6）：指数/涨停家数/情绪/量能/板块——盯盘是紧盯市场的工具
        self.market_watch_service = market_watch_service
        # ── 闭环装配（REQ-c9f899 t12 §6-项8）──────────────────────────────
        # 仅当 WATCH_TODO_ENABLED 开启时由 factory 注入 TodoService；默认 None →
        # 引擎行为与改造前一致：不建待办、通知不带级别（旧渲染路径）。
        # 2026-10-19 清死注入：receipt_service/sla_job/self_heal_service 此前注入后
        # 全包零调用（回执/SLA 巡检在 inbound 定时任务侧，自愈由 interval job 调起），
        # 已从构造函数移除——它们不属于引擎的依赖面。
        self.todo_service = todo_service
        # sidecar 线程句柄（B-8：摘要门/元复核/持仓联动移出 tick 热路径）
        self._sidecar_thread: Optional[threading.Thread] = None
        # A2：上一轮 tick 耗时（毫秒），供 get_metrics 观测
        self._last_tick_ms: Optional[int] = None
        # 规则级频率（RFC 017 §2.3）：调度缓存（last_eval_at / next_due_at）由
        # StateManager.schedule 持有（状态与观测同源）；这里只存每拍的观测量。
        # deferred_rules = 本拍被到期门挡下的规则数；floor_warned = 已 warn 过的
        # 「interval_sec 低于 5s 下限」规则（同一条规则只提醒一次，不刷屏）。
        self._last_deferred_rules = 0
        self._interval_floor_warned: Set[int] = set()
        # 持仓状态门观测量（RFC 017 §2.2）：本拍被状态门跳过的规则数（按 reason）
        # + 累计落过的不一致事件数；get_metrics 能直接看出「门挡了多少、为什么」。
        self._last_state_skips = {
            POSITION_STATE_SKIP_ENTRY_HELD: 0,
            POSITION_STATE_SKIP_ADD_FLAT: 0,
            POSITION_STATE_SKIP_EXIT_FLAT: 0,
        }
        self._state_mismatch_count = 0
        # （原此处重复声明 _avg_volume_cache，已随 P1 清理；
        #   触发事件日志与跨天日期已移入 StateManager）
        self.fast_mode = False
        self._stopped = False

    @staticmethod
    def is_trading_time(t: time) -> bool:
        """交易时段判定（RFC 016 §8.1：收敛到 MarketSessionPolicy）

        只判时段、不判日级——日级由调用方负责（`:133` 走 TradingDayGuard、`:186` 走 weekday）。
        子分钟端点按整分钟口径闭合（11:30 / 15:00 算盘中），与巡检闸门、摘要门同口径。
        """
        return MarketSessionPolicy.is_market_open(
            MarketSessionPolicy.phase_for(t, is_trading_day=True)
        )

    def stop(self):
        self._stopped = True
        self._heartbeat_stop.set()   # 心跳/sidecar 线程随引擎一并停止（优雅退出）
        # 回收线程池（2026-10-19）：均量取数池与 WS 广播池此前无回收路径
        try:
            self.evaluator.shutdown()
        except Exception:  # noqa: BLE001 - 停止路径不许抛
            pass
        try:
            shutdown_ws = getattr(self.notifier, 'shutdown', None)
            if callable(shutdown_ws):
                shutdown_ws()
        except Exception:  # noqa: BLE001
            pass

    def get_metrics(self) -> Dict[str, Any]:
        """引擎运行指标（只读，无副作用）

        2026-09-14 重构 P1：StateManager.snapshot() 的出口。此前引擎状态
        全散在实例字段里，线上排障只能靠在日志里猜；现在可一次性读出
        各状态规模与日期，便于判断"状态是否在正常增长/是否跨天重置"。
        """
        return {
            **self.state.snapshot(),
            'fast_mode': self.fast_mode,
            'base_interval': self.base_interval,
            'fast_interval': self.fast_interval,
            # A2：上一轮 tick 耗时（毫秒）——慢 tick 此前完全不可见
            'last_tick_ms': self._last_tick_ms,
            # 规则级频率可观测（RFC 017 §2.3）：本拍被到期门挡下的规则数 +
            # 每条设了 interval_sec 的规则「离下一拍还有几秒」——排障时能一眼
            # 看出「哪些规则被频率门挡住/还有多久轮到它」。
            'rule_deferred': self._last_deferred_rules,
            # 持仓状态门可观测（RFC 017 §2.2）：本拍跳过计数（按 reason）+ 累计
            # 落过的不一致事件数——排障时一眼看出「门挡了多少、为什么挡」。
            'position_state_skipped': dict(self._last_state_skips),
            'position_state_mismatch': self._state_mismatch_count,
            'rule_next_due_in_sec': self.seconds_until_next_due(),
            'rule_schedule': self.state.schedule.view(self.now_fn()),
            'sidecar_running': bool(self._sidecar_thread and self._sidecar_thread.is_alive()),
            # 心跳可观测（REQ-c9f899 t10）：外部排障时先看这三项——
            # last_at 为空 = 从未写出心跳（未启用或写失败）；failures>0 = 存活信号在丢。
            'heartbeat_enabled': _heartbeat_enabled(),
            'heartbeat_last_at': (self._last_heartbeat_at.isoformat()
                                  if self._last_heartbeat_at else None),
            'heartbeat_failures': self._heartbeat_failures,
        }

    # ── 规则级频率（RFC 017 §2.3）──────────────────────────
    #
    # 调度口径（逐条对应 RFC §2.3，`per-rule-interval` 卡的验收面）：
    #   · 每规则记 last_eval_at（StateManager.schedule，**进程内存**）；
    #   · interval_sec 已设 → next_due_at = last_eval_at + max(5s, interval_sec)，
    #     未到期本拍不取价、不评估、不动闩锁/冷却；
    #   · interval_sec 为 NULL/缺列/非法 → **跟随全局档**：循环本身已按 base/fast
    #     节拍跑，故逐拍求值 = 改造前行为（存量规则节奏一秒都不改）；
    #   · 临期提速：本拍观察到 distance_ratio <= buffer_ratio → 下一拍
    #     effective = min(interval_sec, fast_interval)，即最多 fast_interval 秒；
    #   · 下限 5s：引擎侧 clamp（写入 1–4s 的规则按 5s 执行并 warn 一次）；
    #   · 重启恢复：调度缓存为空 = 首拍全部到期（早一拍，不会重复触发——
    #     闩锁/冷却/去重窗仍由运行态 store 恢复）。

    def _configured_interval(self, rule) -> Optional[int]:
        """该规则声明的 interval_sec（已按 5s 下限 clamp）；None = 跟随全局档。

        低于下限只 warn 一次（每条规则一次）：静默按原值执行会让「写 3s 却每 5s
        才判」变成一个无人知晓的失真；按 5s 执行又不解释则是另一个。
        """
        raw = _rule_interval_sec(rule)
        if raw is None:
            return None
        rule_id = getattr(rule, 'id', None)
        if raw < RULE_INTERVAL_FLOOR_SEC:
            if rule_id not in self._interval_floor_warned:
                self._interval_floor_warned.add(rule_id)
                logger.warning('规则 interval_sec 低于引擎下限，按 %ds 执行',
                               rule_id=rule_id, interval_sec=raw,
                               floor_sec=RULE_INTERVAL_FLOOR_SEC)
            return RULE_INTERVAL_FLOOR_SEC
        return raw

    def effective_rule_interval(self, rule) -> Optional[float]:
        """该规则下一拍的调度间隔（秒）；None = 跟随全局档（逐拍求值）。"""
        configured = self._configured_interval(rule)
        if configured is None:
            return None
        interval = float(configured)
        if self.state.schedule.is_near(getattr(rule, 'id', None)):
            # 临期提速（RFC §2.3）：最多 fast_interval；下限仍由 5s 保护兜住。
            interval = min(interval, float(self.fast_interval))
        return max(float(RULE_INTERVAL_FLOOR_SEC), interval)

    def rule_next_due_at(self, rule) -> Optional[datetime]:
        """下一拍到期时刻；None = 立即到期（无规则级频率，或从未求值过）。

        「从未求值过 → 到期」是重启恢复的口径：新进程调度缓存为空，全部规则
        首拍求值一次，不会因为上一代进程的 last_eval_at 失忆而漏拍。
        """
        interval = self.effective_rule_interval(rule)
        if interval is None:
            return None
        last = self.state.schedule.last_eval_at.get(getattr(rule, 'id', None))
        if last is None:
            return None
        return last + timedelta(seconds=interval)

    def _rule_is_due(self, rule, now: datetime) -> bool:
        """到期门：未设 interval_sec 一律到期（跟随循环档），否则看 next_due_at。"""
        due = self.rule_next_due_at(rule)
        return due is None or now >= due

    def seconds_until_next_due(self, now: Optional[datetime] = None) -> Optional[float]:
        """最早到期的剩余秒数（None = 没有规则级闹钟）；供 get_metrics 与 sleep。"""
        return self.state.schedule.next_due_in(now if now is not None else self.now_fn())

    def next_sleep_interval(self, band_sec: float, elapsed_sec: float = 0.0,
                            now: Optional[datetime] = None) -> float:
        """主循环下一拍的睡眠秒数：clamp(min(档位间隔, 最早到期剩余), 1, 档位间隔)。

        为什么必须看最早到期：主循环固定睡 60s 时，interval_sec=30 的规则
        永远等不到第二拍（每拍都会因未到期被跳过）——规则级频率形同虚设。
        """
        band = max(1.0, float(band_sec) - max(0.0, float(elapsed_sec)))
        remaining = self.seconds_until_next_due(now)
        if remaining is None:
            return band
        return max(1.0, min(band, remaining))

    def _refresh_rule_schedule(self, active_rules) -> None:
        """tick 末尾刷新调度观察：下一拍到期时刻 + 已删除/停用规则的缓存裁剪。

        对**全部在役规则**重算（不只本拍到期的）：PATCH 改小 interval_sec 后，
        下一拍的 sleep 必须按新间隔算——只刷新到期规则会让变更最多晚一个旧间隔
        才生效（`next_sleep_interval` 读的就是这份 next_due_at）。

        只给**设了 interval_sec 的规则**记 next_due_at：NULL = 跟随循环档，
        由循环节拍本身兜住，不需要规则级闹钟（也不会因闹钟把循环挑快/挑慢）。
        """
        schedule = self.state.schedule
        schedule.retain({getattr(r, 'id', None) for r in active_rules})
        for rule in active_rules:
            rule_id = getattr(rule, 'id', None)
            interval = self.effective_rule_interval(rule)
            if interval is None:
                schedule.set_next_due(rule_id, None)
                continue
            last = schedule.last_eval_at.get(rule_id)
            schedule.set_next_due(
                rule_id,
                last + timedelta(seconds=interval) if last is not None else None,
                int(interval),
            )

    # ── 心跳 ────────────────────────────────────────────────

    def _write_heartbeat(self, now) -> bool:
        """写引擎心跳（存活信号）。失败只记日志，绝不打断主循环。

        与 WATCH_RUNTIME_PERSIST_ENABLED 解耦：后者控制"冷却是真的"，前者控制
        "引擎还活着这件事可被外部发现"。节流到 heartbeat_interval_sec，避免每 tick 写库。
        """
        if not _heartbeat_enabled():
            return False
        if (self._last_heartbeat_at is not None
                and (now - self._last_heartbeat_at).total_seconds() < self._heartbeat_interval_sec):
            return False
        if self._heartbeat_store is None:
            self._heartbeat_store = _build_runtime_store()
        if self._heartbeat_store is None:
            return False  # 适配器不可用 → 告警侧会看到"从未有心跳"，由巡检处置
        try:
            self._heartbeat_store.save_meta(heartbeat_at=now, state_date=now.date())
            self._last_heartbeat_at = now
            self._heartbeat_failures = 0
            return True
        except Exception as e:  # noqa: BLE001 - 心跳失败不许打挂主循环
            self._heartbeat_failures += 1
            logger.error('心跳写入失败（引擎仍在跑，但存活信号丢失）',
                         error=str(e), failures=self._heartbeat_failures)
            return False

    def spawn_heartbeat_thread(self):
        '''启动独立心跳写线程：按 heartbeat_interval_sec 定时写存活信号。

        2026-10-16 线上事故：摘要门投递（agent 离线 x 默认 300s 超时）把主循环每轮
        卡 ~5 分钟，而心跳此前只在主循环每轮开头写一次——心跳年龄周期性冲破 180s
        巡检阈值，「心跳丢失」误报。本线程让存活信号与主循环各阶段耗时解耦。

        幂等：重复调用返回已启动的线程；未启用心跳（WATCH_HEARTBEAT_ENABLED=false）
        返回 None。写入仍走 _write_heartbeat 的节流与失败计数，行为可观测。
        '''
        if not _heartbeat_enabled():
            return None
        if self._heartbeat_thread is not None:
            return self._heartbeat_thread

        def _loop():
            while not self._heartbeat_stop.is_set():
                try:
                    self._write_heartbeat(self.now_fn())
                except Exception as e:  # noqa: BLE001 - 心跳线程绝不抛出
                    logger.error('心跳线程写入异常', error=str(e))
                self._heartbeat_stop.wait(self._heartbeat_interval_sec)
            logger.info('WatchEngine 心跳线程已停止')

        self._heartbeat_thread = threading.Thread(
            target=_loop, name='watch-heartbeat', daemon=True)
        self._heartbeat_thread.start()
        logger.info('WatchEngine 心跳线程已启动', interval_sec=self._heartbeat_interval_sec)
        return self._heartbeat_thread

    # ── sidecar（B-8：摘要门/元复核/持仓联动的独立巡检线程）────────────

    def _ensure_sidecar_thread(self):
        """摘要门/元触发复核/持仓生命周期联动的独立线程（2026-10-19）。

        这三个任务此前串在 tick 热路径上：摘要门投递（agent 离线 10s 超时）或
        每日任务一慢，判定节拍就被推迟（2026-10-16 事故只修了心跳、没修主循环，
        本线程是那个缺口的闭环）。幂等：重复调用返回既有线程；三个服务都没装配
        时不起线程（行为与改造前一致）。复用心跳的 stop 事件，随引擎一并停止。
        """
        if self._sidecar_thread is not None:
            return self._sidecar_thread
        if (self.digest_service is None and self.meta_review_service is None
                and self.position_lifecycle_service is None):
            return None

        def _loop():
            while not self._stopped:
                try:
                    self._run_sidecar(self.now_fn())
                except Exception as e:  # noqa: BLE001 - 双保险（内部已逐块隔离）
                    logger.error('sidecar 巡检异常', error=str(e))
                finally:
                    # 会话收尾（2026-10-21, w-6224baac）：sidecar 每拍兜底归还，
                    # 防新增路径漏关（内部逐块 finally 只覆盖既有块）
                    try:
                        from qs_kernel.infrastructure.persistence.orm import close_session
                        close_session()
                    except Exception:
                        pass
                self._heartbeat_stop.wait(30)   # 30s 一拍；stop 即醒
            logger.info('WatchEngine sidecar 线程已停止')

        self._sidecar_thread = threading.Thread(
            target=_loop, name='watch-sidecar', daemon=True)
        self._sidecar_thread.start()
        logger.info('WatchEngine sidecar 线程已启动（摘要门/元复核/持仓联动）')
        return self._sidecar_thread

    def _run_sidecar(self, now) -> None:
        """摘要门 + 每日一次任务（原 run_forever 热路径块的平移，语义不变）。"""
        from qs_ops.application.services.trading_day_guard import TradingDayGuard
        if not TradingDayGuard.is_trading_day(now.date()):
            return
        if not self.is_trading_time(now.time()):
            # FR-4（2026-10-21）：盘后消息与收盘日报独立于盘中任务窗口。
            self._run_sidecar_offhours(now)
            return
        from infrastructure.persistence.orm import close_session
        # 摘要门：队列非空 + 冷却窗 + 当日预算（状态落库，重启不清零）
        try:
            if self.digest_service is not None:
                self.digest_service.maybe_wake(now)
        except Exception as e:
            logger.error('摘要门异常', error=str(e))
        finally:
            close_session()
        # 元触发复核：每日一次（规则不能无限期盯下去，RFC 014 v3 §13）
        try:
            if (self.meta_review_service is not None
                    and self._last_meta_scan_date != now.date()):
                summary = self.meta_review_service.scan(now)
                self._last_meta_scan_date = now.date()
                if summary.get('raised'):
                    logger.info('元触发复核完成', raised=summary['raised'])
        except Exception as e:
            logger.error('元触发复核异常', error=str(e))
        finally:
            close_session()
        # 持仓生命周期联动：每日一次（买入完成/清仓收摊，RFC 014 v3 §2.3）
        try:
            if (self.position_lifecycle_service is not None
                    and self._last_lifecycle_date != now.date()):
                s = self.position_lifecycle_service.reconcile(now)
                self.position_lifecycle_service.expire_overdue_rules(now)
                self._last_lifecycle_date = now.date()
                if s.get('retired') or s.get('created'):
                    logger.info('持仓生命周期联动完成', retired=s['retired'], created=s['created'])
        except Exception as e:
            logger.error('持仓生命周期联动异常', error=str(e))
        finally:
            close_session()
        # 持仓板块映射重建：每日一次（P2 市场环境联动，2026-10-19）。
        # 逐板块外呼的重活只在 sidecar 跑；tick 热路径只读缓存快照。
        # 独立于生命周期联动：持仓有变动（联动重建/收摊）的同日语义正好覆盖。
        try:
            if (self.market_watch_service is not None
                    and self._last_held_map_date != now.date()):
                self.market_watch_service.refresh_held_boards()
                self._last_held_map_date = now.date()
        except Exception as e:
            logger.error('持仓板块映射重建异常', error=str(e))
        finally:
            close_session()
        # 走势回填：每日一次（P3 预判验证闭环，2026-10-20）。
        # 触发后第 5/10/20 个交易日回填收盘对照——盘感样本库的入料口。
        try:
            if (self.outcome_backfill_service is not None
                    and self._last_outcome_backfill_date != now.date()):
                s = self.outcome_backfill_service.backfill(now)
                self._last_outcome_backfill_date = now.date()
                if s.get('filled') or s.get('failed'):
                    logger.info('走势回填完成', filled=s['filled'], failed=s['failed'])
        except Exception as e:
            logger.error('走势回填异常', error=str(e))
        finally:
            close_session()
        # 池级盯盘对账：每日一次（2026-10-20 选池↔盯盘接线）
        try:
            if (self.pool_watch_service is not None
                    and self._last_pool_sync_date != now.date()):
                rs = self.pool_watch_service.reconcile_all(now)
                self._last_pool_sync_date = now.date()
                total_created = sum(int(r.get('created') or 0) for r in rs)
                if total_created or len(rs) > 1:
                    logger.info('池盯盘对账完成', bindings=len(rs), created=total_created)
        except Exception as e:
            logger.error('池盯盘对账异常', error=str(e))
        finally:
            close_session()
        # 消息监控扫描（2026-10-20）：sidecar 每拍调用，服务内部 15 分钟节流 +
        # 工作日 08:00-22:00 窗口（盘后公告也要接，次日决策用）
        try:
            if self.news_watch_service is not None:
                ns = self.news_watch_service.scan(now)
                if ns.get('scanned') and ns.get('reported'):
                    logger.info('消息监控命中', reported=ns['reported'],
                                details=ns.get('details'))
        except Exception as e:
            logger.error('消息监控异常', error=str(e))
        finally:
            close_session()
        # 收盘体检日报（2026-10-20）：meta_review 治理项在摘要门关闭时无人消费，
        # 收盘把未处理项合成一张人话卡发盯盘群，一张/日。
        try:
            if (not self.is_trading_time(now.time())
                    and self._last_review_sent_date != now.date()):
                self._send_daily_review(now)
                self._last_review_sent_date = now.date()
        except Exception as e:  # noqa: BLE001 - 日报失败不阻断 sidecar
            logger.error('收盘体检日报异常', error=str(e))
        finally:
            close_session()

    def _run_sidecar_offhours(self, now) -> None:
        """盘后段：消息扫描（交易日 08:00–22:00）+ 收盘日报（一日一次）。

        2026-10-21（REQ-261021194640-69b8 FR-4）：此前整个 sidecar 只在盘中跑，
        15:00 后消息扫描与服务内部 08:00–22:00 窗口永远对不上，盘后公告永不扫描。
        本方法只做「盘后仍需跑」的两件事，其余日频任务节奏不变。
        """
        from infrastructure.persistence.orm import close_session
        try:
            if self.news_watch_service is not None:
                ns = self.news_watch_service.scan(now)
                if ns.get('scanned') and ns.get('reported'):
                    logger.info('消息监控命中（盘后段）', reported=ns['reported'],
                                details=ns.get('details'))
        except Exception as e:
            logger.error('消息监控异常（盘后段）', error=str(e))
        finally:
            close_session()
        try:
            if (not self.is_trading_time(now.time())
                    and self._last_review_sent_date != now.date()):
                self._send_daily_review(now)
                self._last_review_sent_date = now.date()
        except Exception as e:  # noqa: BLE001 - 日报失败不阻断盘后段
            logger.error('收盘体检日报异常（盘后段）', error=str(e))
        finally:
            close_session()

    # ── 主循环 ──────────────────────────────────────────────

    def run_forever(self):
        logger.info('WatchEngine 启动', base_interval=self.base_interval,
                    fast_interval=self.fast_interval)
        # 启动恢复（REQ-c9f899 R10）：把库里的闩锁/冷却基准灌回内存——重启不再让冷却失效
        try:
            restored = self._restore_runtime_state()
            if self.state.store is not None:
                logger.info('运行态恢复完成', rows=restored, degraded=self.state.degraded)
        except Exception as e:  # 双保险：restore 已自吞异常，启动不许被它打断
            logger.error('运行态恢复异常', error=str(e))
        # sidecar 线程：摘要门/元复核/持仓联动（B-8）——幂等，未装配服务时不起
        self._ensure_sidecar_thread()
        # 2026-09-11（w-f4aa1f6a 步2）：交易日判断收敛到唯一入口（原为只判周末）
        from qs_ops.application.services.trading_day_guard import TradingDayGuard  # 2026-10-19：L1 shim → qs_ops 真身
        while not self._stopped:
            now = self.now_fn()
            # 心跳（t10）：线程若死，外部巡检据此发现"引擎不再产生心跳"。
            # 2026-10-19 双写竞态修正：独立心跳线程（spawn_heartbeat_thread，factory
            # 启动时拉起）已按 interval 续写；主循环只在心跳线程未启动时兜底写
            # （standalone/测试场景）——两路无锁并发写 _heartbeat_store/_last_heartbeat_at
            # 是竞态源，生产路径只留心跳线程一路。
            if self._heartbeat_thread is None:
                self._write_heartbeat(now)
            if TradingDayGuard.is_trading_day(now.date()) and self.is_trading_time(now.time()):
                # B-8（2026-10-19）：摘要门/元复核/持仓联动已移入 sidecar 线程
                # （_ensure_sidecar_thread），本循环只剩判定热路径——2026-10-16 事故
                # 的完整修复：那次只把心跳挪出主循环，慢任务仍挡 tick。
                tick_started = time_module.monotonic()
                try:
                    self.tick()
                except Exception as e:
                    logger.error('WatchEngine tick 异常', error=str(e))
                finally:
                    # tick 内 rule_repo 查询留下的 scoped session 每轮释放——
                    # 否则盯盘线程连接长期 idle in transaction（挡 autovacuum/
                    # 持旧快照，2026-08-18 后台线程连接治理）
                    try:
                        from qs_kernel.infrastructure.persistence.orm import close_session
                        close_session()
                    except Exception:
                        pass
                # A2（2026-10-19）：间隔补偿 + 耗时可观测——慢 tick 不再让判定节拍
                # 整体漂移（此前固定 sleep，tick 卡 5 分钟节拍就漂移 5 分钟）。
                elapsed = time_module.monotonic() - tick_started
                self._last_tick_ms = int(elapsed * 1000)
                # 规则级频率（RFC 017 §2.3）：sleep 还要看「最早到期」——固定睡
                # 档位间隔时，interval_sec 小于档位的规则永远等不到第二拍。
                band = (self.fast_interval if self.fast_mode else self.base_interval)
                interval = self.next_sleep_interval(band, elapsed)
            else:
                interval = 60  # 非交易时段低频心跳
            time_module.sleep(interval)
        logger.info('WatchEngine 已停止')

    # ── 单次判定 ────────────────────────────────────────────

    def tick(self) -> List[dict]:
        now = self.now_fn()
        # 时段自检（2026-09-11，w-aebfddcd 场景矩阵发现）：此前交易时段守卫只在 run_forever 的
        # 循环里，tick() 本身不看表 —— 任何旁路调用（补跑脚本/新服务/其他窗口）都会在盘后
        # 照样判定并推送通知。铁律：交易时段外一律不产出事件。
        if now.weekday() >= 5 or not self.is_trading_time(now.time()):
            return []
        self._reset_daily_state_if_needed(now)
        # ── 全局环境闸（2026-10-20，tick 前置）──────────────────────────
        # 每 tick 只判一次；MarketState 复用 60s 缓存（下方 per-rule market_gate
        # 读同一份快照，不重复取数）。环境不达标 → 个股信号全部只归档不动作；
        # 市场级规则（scope=market/sector）本质是环境本身的信号，不在此列。
        env_gate = self._check_environment_gate(now)
        if env_gate[0] and env_gate[1] != self._last_env_gate_reason:
            logger.warning('环境闸拦截：个股信号只记录不动作', reason=env_gate[1])
        self._last_env_gate_reason = env_gate[1] or None
        # 预算计数每 tick 从库刷新一次（不每规则查，避免 N+1）；库不可用时沿用内存值
        if self.ledger is not None:
            try:
                self.state.interventions_today = self.ledger.count_today()
            except Exception:
                pass
        rules = self.rule_repo.list_enabled()
        events = []
        fast = False

        # 活性过滤：活跃窗口 + 抑噪留样短路（P1-6，2026-10-19：已留样的抑噪规则
        # 不取价不评估——归档样本每日一条已够复盘，再评估是纯浪费且灌归档表喂大
        # 噪音统计）。
        active_rules = []
        for rule in rules:
            # 市场级规则（scope=market/sector，2026-10-20）：走 market_watch_service 的
            # 市场快照扫描，不走个股行情通道。此前个体管线也会给它们取价——#268 的
            # 伪标的 HELD_SECTORS 每 tick 产生一次必败取价，给全部数据源灌失败计数、
            # 把熔断器打到常冷，随后大量真实取价被跳过（早盘全市场盯盘失明的根因）。
            if getattr(rule, 'scope', None) in MARKET_SCOPES:
                continue
            if not self._in_active_window(rule, now):
                continue
            if (rule.id in self.state.suppressed_reported
                    and noise_policy.is_suppressed(getattr(rule, 'noise_state', None),
                                                   getattr(rule, 'suppress_until', None), now)):
                continue
            active_rules.append(rule)

        # ── 持仓状态门（RFC 017 §2.2，`position-state-branch` 卡）──────────
        # 位置：活性过滤之后、到期门之前（规则级过滤）。被跳过的规则本拍**不取价、
        # 不评估、不动闩锁/冷却、也不推进到期时钟**——没有求值就不算一拍（否则下
        # 一拍会误判「已评估过」，把状态翻转后的首拍推迟一个 interval）。
        # 状态不可知（None）与「不一致但 fail-open」的规则照常进到期门。
        position_rules = []
        pending_mismatches: Dict[Any, dict] = {}
        state_skips = {
            POSITION_STATE_SKIP_ENTRY_HELD: 0,
            POSITION_STATE_SKIP_ADD_FLAT: 0,
            POSITION_STATE_SKIP_EXIT_FLAT: 0,
        }
        for rule in active_rules:
            skip_reason, mismatch = position_state_verdict(rule)
            if mismatch is not None:
                pending_mismatches[rule.id] = mismatch
            if skip_reason:
                state_skips[skip_reason] += 1
                logger.debug('持仓状态门跳过规则', rule_id=rule.id,
                             symbol=rule.symbol, reason=skip_reason)
                continue
            position_rules.append(rule)
        self._last_state_skips = state_skips

        # ── 到期门（RFC 017 §2.3，`per-rule-interval` 卡）────────────────
        # interval_sec 未到期的规则本拍**不取价、不评估、不动闩锁/冷却**（RFC §2.3）。
        # 规则 CRUD 写入后无需热重载：tick 每拍 `rule_repo.list_enabled()` 重载 →
        # 下一拍按新 interval 重算到期（`rule_next_due_at` 用 last_eval_at + 当前配置）。
        # interval_sec 为 NULL 的规则不设规则级门：它跟随全局档，而循环本身就是
        # base/fast 节拍——逐拍求值 = 改造前的行为，存量规则节奏一秒都不改。
        # 为什么 NULL 不做「按档位间隔」的硬门：循环为更短 interval 的规则而早醒时，
        # 把存量规则挡在门外只会让它**推迟**判定（止损漏判风险）；宁可多判一次。
        due_rules = []
        deferred = 0
        for rule in position_rules:
            if self._rule_is_due(rule, now):
                due_rules.append(rule)
                # 一拍 = 一次求值尝试：即便随后取价失败也记这一拍，否则失败标的
                # 会被每个 tick 重试（行情源压力），且 next_due_at 永远停在过去
                # → 主循环 sleep 退化成 1s 空转。
                self.state.schedule.mark_evaluated(rule.id, now)
                self.state.schedule.mark_near(rule.id, False)   # 本拍重新判定临期
            else:
                deferred += 1
        self._last_deferred_rules = deferred

        # A1（2026-10-19）：同 tick 同 symbol 只取一次价——此前同标的 N 条规则每 tick
        # 发 N 次行情请求，规则多时 tick 时长线性膨胀。按 symbol 去重取价后逐规则
        # 共享同一 quote（价格点天然一致）。
        # 价格历史也按 symbol 推一次：同 tick 同 symbol 重复推点会产生同 ts 重复行，
        # 批量 upsert 的 ON CONFLICT 直接抛 CardinalityViolation（2026-10-16 实测
        # watch_price_history 0 行、冷却/去重每 tick 全丢）。
        # 到期门之后取价（RFC §2.3）：某 symbol 的规则**全部**未到期 → 本 tick 不取该
        # symbol；只要还有一条到期，就取一次价给到期的规则共享——合并取价不被破坏。
        quotes: Dict[str, Any] = {}
        quote_error_symbols: Set[str] = set()
        # 熔断冷却跳过的标的：上游集体休克，**不是**标的故障——
        # 不计入停牌/退市计数（2026-10-21 误报 70 条的根因之一）。
        quote_cooling_symbols: Set[str] = set()
        for symbol in dict.fromkeys(r.symbol for r in due_rules):   # 保序去重
            try:
                quotes[symbol] = self.quote_service.get_realtime_quote(symbol)
            except AllProvidersCoolingDownError as e:
                # 所有数据源熔断冷却中 → 本轮整体失明是预期行为。
                # 旧实现把它与「真实全灭」混为 None，被 _note_quote_failure 累计，
                # 90 秒内凑满 3 次即误报「疑似停牌/退市」。
                logger.warning('数据源熔断冷却中，本轮跳过（不计入停牌计数）',
                               symbol=symbol, blocked=e.blocked)
                quote_cooling_symbols.add(symbol)
            except Exception as e:
                # 取价异常隔离（P0-1）：数据源抖一次只让该标的本轮失明
                logger.error('取价异常跳过（本轮该标的规则失明，其余标的不受影响）',
                             symbol=symbol, error=str(e))
                quote_error_symbols.add(symbol)
        for symbol, quote in quotes.items():
            if quote is not None:
                self._push_history(symbol, now, float(quote.price))

        for rule in due_rules:
            if rule.symbol in quote_error_symbols:
                continue   # 异常已记日志（上方取价循环）
            if rule.symbol in quote_cooling_symbols:
                # 熔断冷却：上游集体休克，非标的故障——不计入停牌/退市治理。
                # （2026-10-21：旧实现此处与真实失败同走 _note_quote_failure，
                #  90 秒内累计 3 次即误报「疑似停牌/退市」，共 70 条假治理项。）
                continue
            quote = quotes.get(rule.symbol)
            if quote is None:
                logger.warning('取价失败跳过', symbol=rule.symbol)
                self._note_quote_failure(rule, now)
                continue
            if self.state.quote_fail_days.get(rule.symbol):
                self.state.quote_fail_days[rule.symbol] = set()
            ctx = self._build_ctx(rule, now)
            near = False   # 本拍是否观察到临近阈值（决定下一拍是否提速）
            events_before = len(events)   # 状态不一致只在真的记录触发时落事件

            for idx, cond in enumerate(rule.conditions):
                # 两段式伏击（2026-10-19 P1）：staged_break 不走无状态 evaluate——
                # 触及只进观察态（静默），确认成立才进 _process_condition 正常流水线；
                # 窗口到期未确认只归档 suppressed 样本（复盘用，不通知）。
                if isinstance(cond, dict) and cond.get('type') == 'staged_break':
                    try:
                        outcome, result = self.staged.process(
                            rule.id, idx, cond, quote, ctx, now)
                    except Exception as e:
                        logger.error('staged_break 评估异常', rule_id=rule.id,
                                     cond=cond, error=str(e))
                        continue
                    if (result is not None and result.distance_ratio is not None
                            and result.distance_ratio <= self.buffer_ratio):
                        fast = True
                        near = True
                    if outcome == OUTCOME_CONFIRMED:
                        # 确认核验（2026-10-20，机会闭环 M2）：形态确认成立后先过
                        # 利空/流动性/共振三道核验，全过才进触发流水线；失败归档
                        # 假信号样本（不通知/不建待办）。核验挂在 _process_condition
                        # 的陈旧驻留/环境闸之后——那两者不是市场事件，不该跑核验。
                        self._process_condition(rule, idx, cond, quote, result,
                                                now, events, env_gate=env_gate,
                                                verify_confirm=True)
                    elif outcome == OUTCOME_EXPIRED:
                        self._archive_staged_expired(rule, cond, quote, result,
                                                     now, events)
                    continue
                try:
                    result = evaluate(cond, quote, ctx, now=now)
                except Exception as e:
                    logger.error('条件评估异常', rule_id=rule.id, cond=cond, error=str(e))
                    continue
                if result.distance_ratio is not None and result.distance_ratio <= self.buffer_ratio:
                    fast = True
                    near = True
                self._process_condition(rule, idx, cond, quote, result, now, events,
                                        env_gate=env_gate)
            # 持仓状态不一致（RFC 017 §2.2）：只有本拍真的记录了一次触发事件才落
            # `state_mismatch`——被闩锁/陈旧驻留/抑噪挡下的拍不产生事件，否则一条
            # 空仓止损规则每拍刷一条，把真实异常淹掉（与事件流既有语义一致）。
            mismatch = pending_mismatches.get(rule.id)
            if mismatch is not None and len(events) > events_before:
                logger.warning('持仓状态与意图不一致（fail-open 照常求值）',
                               rule_id=rule.id, symbol=rule.symbol,
                               intent=mismatch.get('intent'),
                               intent_family=mismatch.get('intent_family'),
                               position_state=mismatch.get('position_state'),
                               declared_position_state=mismatch.get(
                                   'declared_position_state'),
                               reason=mismatch.get('reason'))
                self._state_mismatch_count += 1
                events.append(dict(mismatch))
            # 临期提速（RFC 017 §2.3）：本拍有任一条件临近阈值 → 这条规则下一拍
            # 提速到 min(interval_sec, fast_interval)；没临近就回到声明频率。
            self.state.schedule.mark_near(rule.id, near)

        # 调度观察刷新（到期门的事实源）：下一拍到期时刻 + 已删除规则缓存裁剪
        self._refresh_rule_schedule(active_rules)

        # 去重窗裁剪：清掉已过期的键，避免长跑进程内的无界增长（委托 StateManager）
        self.state.prune_dedup(now)

        # 市场级规则扫描（P6，2026-10-19 并入主流水线）：取数/评估/节流在市场服务，
        # 触发后的闩锁/冷却/日上限/抑噪/升级/处置/去重/通知/待办与个股**完全同路**
        # （_process_condition）——此前市场级命中 notified=False 写死、闩锁纯内存、
        # 不占预算、不建待办，即使判出 escalated 也无人接收（半条流水线）。
        try:
            if self.market_watch_service is not None:
                for cand in (self.market_watch_service.scan_market_rules(now)
                             .get('evaluated') or []):
                    self._process_condition(
                        cand['rule'], cand['idx'], cand['cond'],
                        cand['quote'], cand['result'], now, events)
        except Exception as e:
            logger.error('市场级扫描异常', error=str(e))

        # 观察聚合缓冲 flush（wt:validate:1）：到期窗口合屏发卡；交易时段结束
        # （收盘 tick）时强刷残余——不丢任何已入缓冲的触发。
        try:
            if self.observe_agg is not None:
                self.observe_agg.maybe_flush(
                    now, market_open=self.is_trading_time(now.time()))
        except Exception as e:  # noqa: BLE001 - flush 失败不阻断 tick
            logger.error('观察聚合 flush 异常', error=str(e))

        # 运行态落库（REQ-c9f899 R10）：tick 末尾只写脏键（节流即"每 tick 一次"）。
        # 开关关闭时 state.store=None，flush 内部直接返回，零 I/O。
        try:
            self._flush_runtime_state()
        except Exception as e:  # 双保险：flush 已自吞异常，tick 不许被它打崩
            logger.error('运行态落库异常', error=str(e))

        self.fast_mode = fast
        return events

    # ── 市场状态与环境闸 ────────────────────────────────────

    def _market_state(self, now):
        """市场状态快照（60s TTL 缓存；全局环境闸与 per-rule market_gate 共用）。

        为什么抽出来：两处判定消费同一份 MarketState——tick 前置的环境闸取一次，
        循环里的 market_gate 若再取一次就是同 tick 双份外呼（数据源抖动时还可能
        一份拦截一份放行）。缓存键是引擎时钟（`now_fn`），测试可冻结时间。

        取数失败/未装配端口 → None（fail-open）：不把「没数据」当事实。
        """
        cached_at, cached = self._gate_cache
        if cached is not None and (now - cached_at).total_seconds() < 60:
            return cached
        if self.market_watch_service is None:
            return None
        provider = getattr(self.market_watch_service, 'state_provider', None)
        if provider is None:
            return None
        try:
            state = provider.get_state()
        except Exception as e:  # noqa: BLE001 - 取数失败 fail-open
            logger.warning('市场状态取数失败（环境闸/市场门放行）', error=str(e))
            return None
        if state is not None:
            self._gate_cache = (now, state)
        return state

    def _check_environment_gate(self, now) -> tuple:
        """全局环境闸（tick 前置）：返回 (blocked, reason)。

        三维判定（指数涨跌 / 板块主线强度 / 资金氛围）委托纯服务
        EnvironmentGateService——本方法只负责取快照与 fail-open 兜底：
          · 无快照 / 取数失败 / 判定异常 → (False, '')，与既有市场门同口径；
          · 数据缺失的维度由服务标 skipped，绝不用 0 冒充事实再拦截。

        拦截语义：引擎对个股信号**只归档不动作**（见 _process_condition 的
        env_gate 分支）；reason 已是一句可直接进通知/日志的中文。
        """
        # 环境闸拦截已按 2026-10-22 用户裁定移除：信号**直接发用户**，不由程序
        # 写死过滤（判定 vs 决策——与失效阈值同一方向：事实归用户，决策归 agent）。
        # 此前该闸还叠加 degraded bug（拿 51 只样本假涨跌比拦信号）与「拦了不说」。
        # WATCH_ENV_GATE_ENABLED=true 可恢复旧拦截行为（默认关闭，可回滚）。
        if os.environ.get('WATCH_ENV_GATE_ENABLED', '').strip().lower() not in ('1', 'true', 'yes'):
            return False, ''
        state = self._market_state(now)
        if state is None:
            return False, ''
        # 消费口径与 service 文档一致：优先 check(state) -> (blocked, reason)
        # （与 _check_market_gate 完全同形）；没有 check 时退到 evaluate(state)。
        # 两种入口都兜同一个异常边界：环境闸自身故障不得让盯盘全体失明。
        try:
            checker = getattr(self.environment_gate, 'check', None)
            if callable(checker):
                blocked, reason = checker(state)
            else:
                decision = self.environment_gate.evaluate(state)
                blocked, reason = decision.blocked, decision.reason
        except Exception as e:  # noqa: BLE001 - 环境闸自身故障不得让盯盘全体失明
            logger.error('环境闸判定异常（fail-open 放行）', error=str(e))
            return False, ''
        return bool(blocked), str(reason or '')

    def _check_market_gate(self, gate: dict, now) -> tuple:
        """市场环境复合门判定（per-rule 加严项）：返回 (blocked, reason)。

        gate spec（action_params.market_gate）：
          index        看哪个指数（默认 000001.SH）
          max_down_pct 指数跌幅 ≤ 此值（如 -1.5）→ 拦截（系统性风险日不接飞刀）
          max_up_pct   指数涨幅 ≥ 此值（如 +3.0）→ 拦截（过热追高保护，可选）
        数据缺失 fail-open 不拦截；市场快照复用 _market_state 的 60s 缓存。
        """
        idx = str(gate.get('index') or '000001.SH')
        state = self._market_state(now)
        if state is None:
            return False, ''
        try:
            pct = state.index_change_pct(idx)
        except Exception:  # noqa: BLE001
            pct = None
        if pct is None:
            return False, ''
        max_down = gate.get('max_down_pct')
        if max_down is not None and pct <= float(max_down):
            return True, ('市场门拦截：%s 跌 %.2f%% 触线 %.2f%%——环境异常，'
                          '本次信号只记录不动作' % (idx, pct, float(max_down)))
        max_up = gate.get('max_up_pct')
        if max_up is not None and pct >= float(max_up):
            return True, ('市场门拦截：%s 涨 %.2f%% 触线 +%.2f%%——过热保护，'
                          '本次信号只记录不动作' % (idx, pct, float(max_up)))
        return False, ''

    def _send_daily_review(self, now) -> None:
        """收盘体检日报：未处理的 meta_review 治理项 → 一张人话卡发盯盘群。"""
        repo = getattr(self.notifier, 'trigger_repo', None)
        if repo is None:
            return
        rows = repo.list_triggers(dispositions=('meta_review',), limit=50) or []
        if not rows:
            return
        # 公司名批量解析（2026-10-20 用户反馈：纯编号不友好）——走 notifier 注入的
        # StockNameResolver 端口一次联查；解析不到如实显示编号（R-013 不臆造）。
        names: dict = {}
        resolver = getattr(self.notifier, '_name_resolver', None)
        syms = sorted({str(t.symbol).split('.')[0] for t in rows})
        if resolver is not None:
            try:
                names = resolver.resolve_batch(syms) or {}
            except Exception as e:  # noqa: BLE001 - 名称是增益，失败降级为编号
                logger.debug('日报名称解析失败（降级编号）', error=str(e))

        def _disp(sym):
            bare = str(sym).split('.')[0]
            return '%s（%s）' % (names.get(bare) or bare, bare)

        lines = ['今日规则体检：%d 条待处理（调阈值/退役/补激活后自动消失）：' % len(rows)]
        for t in rows[:8]:
            lines.append('• 规则#%s %s：%s' % (t.rule_id, _disp(t.symbol),
                                              (t.disposition_reason or '')[:60]))
        if len(rows) > 8:
            lines.append('• …另有 %d 条（详情查 watch_triggers）' % (len(rows) - 8))
        # 今日处置段（2026-10-20）：agent/人收敛的触发也进日报——「信号→处置→报告」
        # 闭环的推送端：用户每天收盘后被动收到"今天处理了啥、为什么"，无需拉清单。
        try:
            today_rows = [t for t in repo.list_triggers(
                dispositions=('handled', 'ignored', 'expired'), limit=300)
                if getattr(t, 'disposition_at', None)
                and t.disposition_at.date() == now.date()]
            if today_rows:
                lines.append('')
                lines.append('今日已处置 %d 条（agent/人）：' % len(today_rows))
                for t in today_rows[:6]:
                    lines.append('• 规则#%s %s → %s：%s'
                                 % (t.rule_id, _disp(t.symbol), t.disposition,
                                    (t.disposition_reason or '')[:50]))
                if len(today_rows) > 6:
                    lines.append('• …另有 %d 条' % (len(today_rows) - 6))
        except Exception as e:  # noqa: BLE001 - 处置段失败不废整张日报
            logger.warning('处置段生成失败（日报继续）', error=str(e))
        from qs_watch.application.services.watch_engine.watch_channels import send_watch_receipt
        ok = send_watch_receipt({'kind': 'daily_review', 'message': '\n'.join(lines),
                                 'level': 'P2'})
        if ok:
            logger.info('收盘体检日报已发', count=len(rows))
        else:
            logger.warning('收盘体检日报未送达', count=len(rows))

    def _process_condition(self, rule, idx: int, cond: dict, quote, result,
                           now, events, env_gate: Optional[tuple] = None,
                           verify_confirm: bool = False) -> PipelineResult:
        """单条条件的「评估后」流水线（个股与市场级共用，2026-10-19 提取）。

        15 步已拆成有序阶段，注册表在
        `watch_engine/pipeline/registry.py`（`DEFAULT_STAGES`，唯一装配点）；
        本方法只构造 TriggerContext 并跑链，**不认识任何具体阶段**——加/删/
        调阶段只改注册表，tick 骨架不动。维护指南：
        `quantsys-v2/docs/guides/watch-pipeline-stages.md`。

        阶段顺序（与改造前逐句等价）：
          闩锁/冷却/迟滞 → 陈旧驻留 → 全局环境闸（个股）→ 确认核验（仅
          staged_break 确认）→ 日上限（宪法豁免）→ 抑噪 → 升级 → 处置五门 →
          per-rule market_gate（加严项）→ 去重/重叠治理 → 通知或聚合缓冲 →
          日通知计数 → 待办 → 送达后结算（去重标记/介入记账/止损使命退役）→
          闩锁回退 + 事件记录。

        env_gate：tick 前置算出的 (blocked, reason)，**只对个股传入**（市场级
        规则本就是环境本身的信号）；None = 不做全局环境拦截。

        verify_confirm：staged_break 确认成立时传 True，先过利空/流动性/共振
        三道核验（失败只归档假信号样本、直接返回）。放在陈旧驻留/环境闸之后：
        那两者不是市场事件（规则失真 / 环境日），不该触发核验外呼。

        为什么提取：市场级规则（P6）此前走「半条流水线」——评估器不同
        （MarketRuleEvaluator 吃市场快照），但评估之后的路**完全相同**。

        返回 PipelineResult（含 trace，供排障/测试断言路径）；副作用（通知/
        归档/落库/闩锁）与改造前一致，调用方忽略返回值即为旧行为。
        """
        ctx = TriggerContext(
            engine=self, rule=rule, idx=idx, cond=cond, quote=quote,
            result=result, now=now, events=events, env_gate=env_gate,
            verify_confirm=verify_confirm)
        return PIPELINE.run(ctx)

    # ── 内部 ────────────────────────────────────────────────

    def _restore_runtime_state(self) -> int:
        """启动恢复入口（幂等：同进程只恢复一次）；未启用持久化返回 0。

        返工 B+C（2026-09-18）：除闩锁/冷却基准外，同时恢复去重窗、触发事件窗口与
        价格历史。价格历史按**启用规则覆盖的 symbols** 有界恢复（口径与理由见
        StateManager._restore_history）；取规则列表失败时退化为按窗口恢复，
        绝不让恢复动作影响引擎启动。
        """
        if self.state.store is None or self._runtime_restored:
            return 0
        self._runtime_restored = True
        symbols = None
        try:
            symbols = {str(getattr(r, 'symbol', '') or '') for r in self.rule_repo.list_enabled()}
            symbols.discard('')
        except Exception as e:  # noqa: BLE001 - 拿不到规则不阻断恢复
            logger.warning('启动恢复取启用规则失败，价格历史退化为按窗口恢复', error=str(e))
            symbols = None
        staged_restored = self.staged.restore_from_store()
        if staged_restored:
            logger.info('staged 观察态已恢复', count=staged_restored)
        return self.state.restore_from_store(now=self.now_fn(), symbols=symbols)

    def _flush_runtime_state(self) -> bool:
        """tick 末尾落库入口（委托 StateManager；未启用时 no-op 返回 False）。

        now 由引擎时钟注入：三类扩展的窗口裁剪/节流都以它为准（此前 StateManager
        内部取 datetime.now() 会与引擎注入的 now_fn 形成两套时间口径）。
        staged 观察态独立 flush（脏才写，失败不抛）。
        """
        flushed = self.state.flush(now=self.now_fn())
        self.staged.flush()
        return flushed

    def _build_gate_ctx(self, rule, cond, quote):
        """委托 DispositionEngine（保留入口名）"""
        return self.disposition.build_gate(rule, cond, quote)

    def _position_value(self, rule) -> Optional[float]:
        """委托 DispositionEngine（tick 的 action_amount_yuan 仍走这里）"""
        return self.disposition.position_value(rule)

    def _account_total(self, rule=None) -> Optional[float]:
        """委托 DispositionEngine"""
        return self.disposition.account_total(rule)

    def _notify_level(self, rule, disposition, *, has_position: bool = False) -> Optional[str]:
        """规则 → 待办级别 P0..P3（REQ-c9f899 t12 §6-项1 的**生产端**）。

        为什么只在闭环开启时返回级别：未注入 todo_service（WATCH_TODO_ENABLED=false）时
        通知必须保持既有形态（旧 WatchTriggeredFormatter），不能悄悄换渲染——默认全关
        行为与改造前一致是 t12 的硬约束。

        判定完全复用 domain 纯函数 resolve_level（单一事实源），本方法只做输入组装。
        任何异常都降级为 None（旧渲染），绝不让级别判定打挂通知主路径。
        """
        if self.todo_service is None:
            return None
        try:
            from qs_watch.domain.watch.services.disposition import CONSTITUTIONAL_INTENTS, intent_of
            from qs_watch.domain.watch.services.level_resolver import resolve_level

            intent = intent_of(rule)
            action_hint = getattr(rule, 'action_hint', None)
            action_on_trigger = (action_hint.get('action_on_trigger')
                                 if isinstance(action_hint, dict) else None)
            return resolve_level(
                intent=intent,
                has_position=has_position,
                is_constitutional=(intent in CONSTITUTIONAL_INTENTS),
                action_on_trigger=action_on_trigger,
                trigger_level=self._get_trigger_level(rule),
                scope=getattr(rule, 'scope', None),
                is_governance=(disposition == 'meta_review'),
            )
        except Exception as e:  # noqa: BLE001 - 级别判定失败降级旧渲染，不阻断通知
            logger.warning('级别判定失败，通知按旧路径渲染（不带级别）',
                           rule_id=getattr(rule, 'id', None), error=str(e))
            return None

    # ── 待办创建（REQ-c9f899 t12：触发 → 待办的唯一落点）──────────────────

    def _create_watch_todo(self, rule, now, disposition, trigger, level):
        """触发落成待办（仅在 WATCH_TODO_ENABLED 开启、即 todo_service 注入时）。

        约束（全部可被 tests/application/test_t12_todo_creation.py 证伪）：
          · 只 P0/P1/P2 建待办，**P3 不建**（R1：P3 是纯归档，只进日终汇总；建待办会灌满表）；
          · disposition='deduped' 不建（去重合并的触发不是独立事件）；
          · 同一 trigger_id 最多一条待办（已有 todo_id 即跳过）；
          · 建完回填 watch_triggers.todo_id（失败只记日志，不回滚、不打挂 tick）；
          · 任何异常都自吞并返回 None（调用方还会再包一层，tick 绝不被打挂）。
        """
        if self.todo_service is None or not level:
            return None
        level_value = str(level).strip().upper()
        if level_value == 'P3':
            return None  # R1：P3 纯归档，不建待办
        if str(disposition or '').strip().lower() == 'deduped':
            return None
        trigger_id = getattr(trigger, 'id', None)
        if trigger_id is None:
            # 触发未落库（记录失败）：没有溯源载体，不建（否则待办成了无源之水）
            return None
        if getattr(trigger, 'todo_id', None):
            return None  # 幂等：同一触发已有待办
        try:
            due_at, sla_seconds = self._todo_due(level_value, now)
            todo = self.todo_service.create(
                rule.symbol, level=level_value, sla_seconds=sla_seconds, due_at=due_at,
                account=self._todo_account(rule), rule_id=getattr(rule, 'id', None),
                trigger_id=trigger_id,
                action_kind=self._todo_action_kind(rule, disposition))
        except Exception as e:  # noqa: BLE001 - 建待办失败不得打挂 tick
            logger.error('建待办失败（tick 继续，等后续触发重试）', rule_id=getattr(rule, 'id', None),
                         trigger_id=trigger_id, level=level_value, error=str(e))
            return None
        # 回填 watch_triggers.todo_id（失败只记日志：待办已建，回填是溯源增益不是前提）
        try:
            repo = getattr(self.notifier, 'trigger_repo', None)
            if repo is not None and hasattr(repo, 'set_todo_id'):
                repo.set_todo_id(trigger_id, getattr(todo, 'id', None))
        except Exception as e:  # noqa: BLE001
            logger.warning('触发回填 todo_id 失败（只记账，不回滚）', trigger_id=trigger_id,
                           todo_id=getattr(todo, 'id', None), error=str(e))
        logger.info('触发已落待办', todo_id=getattr(todo, 'id', None), trigger_id=trigger_id,
                    rule_id=getattr(rule, 'id', None), level=level_value,
                    flow_state=getattr(todo, 'flow_state', None))
        return todo

    @staticmethod
    def _todo_due(level, now):
        """级别 → (due_at, sla_seconds)。P0=now+300s / P1=now+1800s / P2=当日收盘 15:00。

        P2 的收盘时刻取 MarketSessionPolicy 的 CONTINUOUS_END（单一出处，不硬编码 15:00），
        取不到时回退 datetime.time(15, 0)。tick 仅在交易时段运行，故 15:00 通常在未来；
        若已过（异常/补跑），due 退化为 now+1min，避免 due_at 落在过去被巡检立即晋升。
        """
        lv = str(level or '').strip().upper()
        if lv == 'P0':
            return now + timedelta(seconds=300), 300
        if lv == 'P1':
            return now + timedelta(seconds=1800), 1800
        try:
            from qs_trading.domain.trading.services.market_session_policy import CONTINUOUS_END as _close
        except Exception:  # noqa: BLE001 - 常量缺失时退回最简口径（当日 15:00）
            _close = time(15, 0)
        day_close = datetime.combine(now.date(), _close)
        due = day_close if day_close > now else now + timedelta(minutes=1)
        return due, max(1, int((due - now).total_seconds()))

    @staticmethod
    def _todo_account(rule):
        """规则归属账户（复用 rule_guard.effective_account 单一出处；失败退回 account）"""
        try:
            from qs_watch.domain.watch.services.rule_guard import effective_account
            return effective_account(rule)
        except Exception:  # noqa: BLE001
            return getattr(rule, 'account', None)

    @staticmethod
    def _todo_action_kind(rule, disposition):
        """规则意图 → 待办 action_kind（trade/rule_change/observe）。

        治理项（meta_review，规则重叠等）→ rule_change；交易类意图 → trade；其余 → observe。
        映射复用 domain 的 is_trade_intent / intent_of（单一事实源）。
        """
        if str(disposition or '').strip().lower() == 'meta_review':
            return 'rule_change'
        try:
            from qs_watch.domain.watch.services.disposition import intent_of, is_trade_intent
            return 'trade' if is_trade_intent(intent_of(rule)) else 'observe'
        except Exception:  # noqa: BLE001
            return 'observe'

    def _reset_daily_state_if_needed(self, now: datetime):
        """跨天重置：均量缓存过期 + 清理已删除规则的残留状态

        状态部分委托 StateManager.reset_daily；规则列表只查一次（原实现为
        last_triggered 与 history 各查一次，同一 tick 内结果相同）。
        """
        if self.state.current_date == now.date():
            return
        self.evaluator.reset_daily(now)
        self.staged.reset_daily()   # 观察窗不隔夜：跨天回到待命重新等触及
        active = self.rule_repo.list_enabled()
        self.state.reset_daily(
            now,
            active_rule_ids={r.id for r in active},
            active_symbols={r.symbol for r in active},
        )

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
            price_history=tuple(self.state.history.get(rule.symbol, ())),
            avg_volume_20d=self._get_avg_volume(rule.symbol),
            elapsed_fraction=elapsed_trading_fraction(now),
            daily_closes=self._get_daily_closes(rule.symbol),
            fund_flow=self._get_fund_flow(rule.symbol),
        )

    def _get_daily_closes(self, symbol: str):
        """日线收盘序列（ma_break/rsi 算料）；provider 缺失/失败 → ()（条件降级）。"""
        if self.kline_closes_provider is None:
            return ()
        try:
            closes = self.kline_closes_provider(symbol)
            return tuple(closes) if closes else ()
        except Exception as e:  # noqa: BLE001 - 取数失败降级不判定
            logger.debug('日线收盘取数失败（MA/RSI 降级）', symbol=symbol, error=str(e))
            return ()

    def _get_fund_flow(self, symbol: str):
        """资金流向摘要（fund_flow 条件）；provider 缺失/失败 → None（条件降级）。"""
        if self.fund_flow_provider is None:
            return None
        try:
            return self.fund_flow_provider(symbol)
        except Exception as e:  # noqa: BLE001
            logger.debug('资金流向取数失败（降级）', symbol=symbol, error=str(e))
            return None

    def _push_history(self, symbol: str, ts: datetime, price: float):
        """委托 StateManager（价格历史属状态）"""
        self.state.push_history(symbol, ts, price, self.history_minutes)

    def _get_avg_volume(self, symbol: str) -> Optional[float]:
        """委托 RuleEvaluator（保留薄封装）

        为何不直接调 evaluator：11 处测试直接调用本方法，且 e2e 通过
        engine._get_avg_volume = lambda ... 替换取数入口来隔离外部源；
        改名或绕开会让这些守护失效。
        """
        return self.evaluator.get_avg_volume(symbol, self.now_fn())

    def _note_avg_volume_failure(self, symbol: str, now: datetime, why: str) -> None:
        """委托 RuleEvaluator（同上，保留入口名）"""
        self.evaluator.note_failure(symbol, now, why)

    def _in_cooldown(self, rule_id: int, cond_idx: int, cond: dict, now: datetime) -> bool:
        """委托 TriggerJudge（保留入口名：tick 与既有测试路径不变）"""
        return self.judge.in_cooldown(rule_id, cond_idx, cond, now)

    def _get_trigger_level(self, rule) -> str:
        """委托 EscalationCoordinator（保留入口名）"""
        return self.escalation._get_trigger_level(rule)

    @staticmethod
    def _is_constitutional(rule) -> bool:
        """宪法级意图判定（止损等）：日上限豁免判据（2026-10-19）。

        复用 domain 的 intent_of + CONSTITUTIONAL_INTENTS 单一事实源。判定失败
        按非宪法处理（维持上限）——宁可多归档一条，不在异常路径上放开噪音闸。
        """
        try:
            from qs_watch.domain.watch.services.disposition import (
                CONSTITUTIONAL_INTENTS, intent_of,
            )
            return intent_of(rule) in CONSTITUTIONAL_INTENTS
        except Exception as e:  # noqa: BLE001
            logger.warning('宪法意图判定失败，按非宪法处理（日上限仍生效）',
                           rule_id=getattr(rule, 'id', None), error=str(e))
            return False

    #: 「保护线」条件类型（环境闸豁免的结构锚点之一）：这些条件向下穿越即保护线
    #: 本身——价格破位止损、均线破位止损、浮亏达线止损。方向读 params.direction
    #: 结构化字段，不解析任何文案。
    PROTECTIVE_CONDITION_TYPES = ('price_break', 'ma_break', 'pnl_pct')

    @classmethod
    def _protection_line_anchor(cls, rule, cond) -> str:
        """保护线结构锚点：命中返回锚点说明，空串 = 非保护线（纯结构判定）。

        持仓保护线至少具备下列一个结构化标记；四条都不满足的 exit_stop 只是
        「止损意图」的普通告警（如 symbol 级价格上破提醒），不含保护线语义：
          · scope=position          —— position_lifecycle 生成的持仓规则；
          · lifecycle_stage=holding —— 已进入持仓阶段；
          · cost_price 有值         —— 止损线锚定持仓成本（浮亏达线类）；
          · action_hint.stop_loss    —— 规则显式声明了保护线价位（ActionHint 字段）；
          · 触发条件是下行保护阈值（price_break/ma_break/pnl_pct 且 direction=below）。
        **绝不**读 context/message 里的「止损」字样：文案可改、可翻译，不是事实源。
        """
        scope = str(getattr(rule, 'scope', '') or '').strip().lower()
        if scope == 'position':
            return 'scope=position'
        stage = str(getattr(rule, 'lifecycle_stage', '') or '').strip().lower()
        if stage == 'holding':
            return 'lifecycle_stage=holding'
        if getattr(rule, 'cost_price', None) is not None:
            return 'cost_price'
        hint = getattr(rule, 'action_hint', None)
        hint_stop = (hint.get('stop_loss') if isinstance(hint, dict)
                     else getattr(hint, 'stop_loss', None))
        if hint_stop is not None:
            return 'action_hint.stop_loss'
        ctype = str((cond or {}).get('type') or '')
        params = (cond or {}).get('params') or {}
        if ctype in cls.PROTECTIVE_CONDITION_TYPES:
            direction = str(params.get('direction') or '').strip().lower()
            if direction == 'below':
                return 'condition:%s:below' % ctype
        return ''

    def _env_gate_exemption(self, rule, cond) -> tuple:
        """环境闸豁免判定：返回 (exempt, reason)。

        用户 2026-10-20 裁定：环境不达标时 exit_stop/保护线类信号**照常通知**，
        其余个股信号仍只归档。判据全部来自规则声明的动作类型与结构化字段，
        不看消息文案（判据可回溯、可单测）：
          ① 动作类型 ∈ CONSTITUTIONAL_INTENTS（复用 disposition 单一事实源；
             intent 缺省时由 intent_of 按 action_on_trigger 归一，如 sell+pnl_pct
             below → exit_stop）；
          ② 保护线结构锚点非空（见 `_protection_line_anchor`）。
        两条同时成立才豁免：豁免的是「持仓保护线」，不是「带止损字样的任何规则」。
        """
        try:
            from qs_watch.domain.watch.services.disposition import intent_of
            intent = intent_of(rule)
        except Exception as e:  # noqa: BLE001 - 判定失败按不豁免处理（不放开噪音闸）
            logger.warning('环境闸豁免判定失败，按不豁免处理',
                           rule_id=getattr(rule, 'id', None), error=str(e))
            return False, ''
        if not self._is_constitutional(rule):
            return False, ''
        anchor = self._protection_line_anchor(rule, cond)
        if not anchor:
            return False, ''
        return True, '%s（intent=%s，锚点=%s）' % (
            ENV_GATE_EXEMPT_REASON, intent, anchor)

    #: 连续多少个交易日取数失败报「疑似停牌/退市」治理项
    QUOTE_FAIL_GOVERNANCE_DAYS = 3

    def _note_quote_failure(self, rule, now):
        """取数失败计数：连续 N 个**交易日**失败 → 每规则每日一条停牌/退市治理项。

        此前取数失败只是静默跳过——规则对停牌/退市标的永久失效且无人发现。

        2026-10-21 修复（误报 70 条的根因之二）：
        原实现是「每次评估拍 +1」，docstring 写的却是「连续 N 个交易日」——
        两者不是一回事。实测 002007 的 3 次失败发生在 10-20 的
        09:31:02.343 / 09:31:02.343 / 09:32:24.785（**90 秒内**）即触发
        「连续 3 个交易日取数失败」。叠加熔断级联（5 源逐个失败后全体冷却
        60 秒，所有标的批量失明），10-20/10-21 共产出 70 条假治理项，
        29 个标的实测 100% 未停牌。

        现在按**交易日**计数：记录失败日集合，跨天只保留当日——
        同一交易日内无论失败多少次都只算 1 天。
        """
        sym = str(rule.symbol)
        day = now.date()
        days = self.state.quote_fail_days.setdefault(sym, set())
        days.add(day)
        # 只保留最近 QUOTE_FAIL_GOVERNANCE_DAYS 个交易日（自然形成"连续"窗口）
        recent = sorted(days)[-self.QUOTE_FAIL_GOVERNANCE_DAYS:]
        self.state.quote_fail_days[sym] = set(recent)
        n = len(recent)
        if n < self.QUOTE_FAIL_GOVERNANCE_DAYS or sym in self.state.quote_fail_reported:
            return
        self.state.quote_fail_reported.add(sym)
        try:
            self.notifier.record_governance(
                rule,
                '疑似停牌/退市：标的 %s 连续 %d 个交易日取数失败 → 建议复核标的状态，'
                '确认后退役规则（取数失败期规则等同失效）' % (sym, n),
                {'quote_fail_days': n, 'suspected_halt': True,
                 'failed_dates': [d.isoformat() for d in recent]})
            logger.warning('连续取数失败已转治理', symbol=sym, days=n)
        except Exception as e:  # noqa: BLE001
            logger.error('停牌治理项记录失败', symbol=sym, error=str(e))

    def _maybe_retire_executed_stop(self, rule, disposition, now):
        """止损触发后自动退役规则（exit_stop 使命完成）。

        只处理 exit_stop：止损即清仓，线破 = 使命完成。
        exit_reduce/exit_take_profit（减仓档）是部分动作，不退役——剩余仓位
        的后续风控线由 agent 复核（治理项已在 digest 链路）。
        deduped/suppressed 的触发不算消费（那是一次合并/归档，不是线破事件本身）。
        """
        if str(getattr(rule, 'intent', '') or '') != 'exit_stop':
            return
        if disposition in ('deduped',):
            return
        if not getattr(rule, 'enabled', True):
            return
        # 用户真身账户的规则归属用户本人（2026-10-19 用户裁定："拿着，不应该修改
        # 规则"）——止损触发≠止损执行，用户可能继续持有，而原止损线仍是用户的
        # 有效指令。引擎**不退役不修改**，只落治理注记提示 agent 来向用户确认；
        # agent 自有账户（agent_brain/agent_virtual）才走自动退役。
        acct = getattr(rule, 'linked_account', None) or getattr(rule, 'account', None)
        if acct == 'user_main_simulation':
            try:
                self.notifier.record_governance(
                    rule,
                    '止损线已触发（用户账户）：现价已穿越止损线，规则保持原样不改动——'
                    '请 agent 向用户确认：已执行止损则规则可退役；继续持有则需用户'
                    '指定新风控线（引擎不代改）。',
                    {'user_account_stop_triggered': True})
                logger.info('用户账户止损触发已转治理（规则不改动）',
                            rule_id=rule.id, symbol=rule.symbol)
            except Exception as e:  # noqa: BLE001
                logger.error('用户止损治理注记失败', rule_id=rule.id, error=str(e))
            return
        try:
            banner = ('[止损已触发 %s] 阈值线已被穿越，规则使命完成，引擎自动退役。'
                      '未平仓的新风控线由 agent 起草、用户确认后重建。'
                      % now.strftime('%Y-%m-%d %H:%M'))
            notes = list(getattr(rule, 'ops_notes', None) or [])
            notes.append({'at': now.isoformat(), 'by': 'watch_engine/stop_retire',
                          'text': banner})
            self.rule_repo.update_fields(
                rule.id, enabled=False, lifecycle_stage='closed', ops_notes=notes)
            logger.info('止损规则已自动退役', rule_id=rule.id, symbol=rule.symbol)
        except Exception as e:  # noqa: BLE001 - 退役失败不阻断 tick（下轮重试）
            logger.error('止损规则自动退役失败', rule_id=getattr(rule, 'id', None),
                         error=str(e))

    @staticmethod
    def _pnl_of(rule, quote):
        """规则成本价 → 当前浮盈亏 %（无成本价返回 None；relation_of 的消费端）。"""
        cost = getattr(rule, 'cost_price', None)
        if not cost:
            return None
        try:
            return round((float(quote.price) - float(cost)) / float(cost) * 100, 2)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    def _confirm_verify(self, rule, cond, quote, result, now, events) -> bool:
        """staged_break 确认成立后的三道核验闸（2026-10-20，机会闭环 M2）。

        返回 True = 放行到触发流水线；False = 判「假信号」（已归档，调用方不得通知）。

        调用位置：_process_condition 的陈旧驻留/环境闸之后（那两者不是市场事件，
        不该触发核验外呼），日上限/抑噪之前（先判真伪，再谈投送节流）。

        口径：
          · 未装配流水线 → 直接放行（行为与改造前一致，回滚/未接线零影响）；
          · 流水线自身异常 → fail-open 放行并记日志（核验是旁路，不能因它让盯盘失明）；
          · 核验失败 → 经 suppressed 归档口落一条样本（detail 带三道逐项结论），
            不发通知、不进摘要队列、不建待办、不占日通知配额。

        为什么不闩锁：staged 状态机在确认时已清掉观察态，下一 tick 会从 WATCHING
        重新等触及；假信号归档后若再出现新的触及→确认，应当重新核验（可能是新的
        消息面/盘口事实），用闩锁压掉会漏掉真正的第二次机会。
        """
        pipeline = self.confirm_verify_pipeline
        if pipeline is None:
            return True
        try:
            verify = pipeline.verify(rule.symbol, quote=quote, now=now)
        except Exception as e:  # noqa: BLE001 - 核验旁路故障不得让信号全体失明
            logger.error('确认核验流水线异常（fail-open 放行）',
                         rule_id=getattr(rule, 'id', None),
                         symbol=getattr(rule, 'symbol', None), error=str(e))
            return True
        if getattr(verify, 'passed', True):
            if not getattr(verify, 'verified', True):
                logger.info('确认核验通过但未完整（fail-open）', rule_id=rule.id,
                            symbol=rule.symbol,
                            skipped=getattr(verify, 'skipped_stages', ()))
            return True

        reason = '%s：%s' % (
            CONFIRM_VERIFY_FAILED_REASON,
            getattr(verify, 'reason', '') or '未说明')
        archived = self._archive_confirm_verify_failed(
            rule, cond, quote, result, reason=reason, verify=verify)
        detail = None
        to_dict = getattr(verify, 'to_dict', None)
        if callable(to_dict):
            try:
                detail = to_dict()
            except Exception:  # noqa: BLE001 - 事件附注失败不影响归档结论
                detail = None
        events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                       'condition': cond, 'price': float(quote.price),
                       'message': result.message,
                       'disposition': DISPOSITION_AUTO_OBSERVED,
                       'disposition_reason': reason,
                       'dup_of': None, 'merged_from_rule': None,
                       'trigger_id': getattr(archived, 'id', None),
                       'trigger_level': self._get_trigger_level(rule),
                       'suppressed': True, 'notified': False,
                       'false_signal': True,
                       'confirm_verify': detail})
        logger.info('确认核验未通过，假信号已归档（不通知/不建待办）',
                    rule_id=rule.id, symbol=rule.symbol,
                    failed_stages=getattr(verify, 'failed_stages', ()),
                    trigger_id=getattr(archived, 'id', None))
        return False

    def _archive_confirm_verify_failed(self, rule, cond, quote, result,
                                       reason: str, verify=None):
        """核验失败样本归档口：suppressed 落库（detail 带逐项结论），不发送。

        与抑噪/日上限/环境闸/伏击过期共用 _record_suppressed_trigger 通道，
        reason 区分溯源；部分测试假件只提供 notifier.record_only、没有
        trigger_repo——退化为 record_only，归档不能因端口形态不同而丢失。
        两者都失败 → None：调用方已判假信号（不通知），归档失败只记日志。
        """
        extra = {'false_signal': True}
        failed = getattr(verify, 'failed_stages', ())
        if failed:
            extra['failed_stages'] = list(failed)
        to_dict = getattr(verify, 'to_dict', None)
        if callable(to_dict):
            try:
                extra['confirm_verify'] = to_dict()
            except Exception:  # noqa: BLE001
                pass
        if getattr(self.notifier, 'trigger_repo', None) is not None:
            archived = self._record_suppressed_trigger(
                rule, cond, quote, result, reason=reason, detail_extra=extra)
            if archived is not None:
                return archived
        record_only = getattr(self.notifier, 'record_only', None)
        if callable(record_only):
            try:
                return record_only(rule, cond, quote, result,
                                   disposition=DISPOSITION_AUTO_OBSERVED,
                                   disposition_reason=reason)
            except Exception as e:  # noqa: BLE001 - 归档失败只记日志，不阻断 tick
                logger.error('确认核验样本归档失败（record_only）',
                             rule_id=getattr(rule, 'id', None), error=str(e))
        return None

    def _handle_stale_residency(self, rule, idx, cond, quote, result, now):
        """陈旧驻留处置（2026-10-19）+ 失效实时判定标 invalid（2026-10-22 三分支）。

        闩锁必须置上：否则下一 tick 还会命中同一条件。
        治理项每规则每日一条（state.stale_reported 去重）。

        失效实时判定（2026-10-22）：价格偏离 >20% 且非宪法级止损 → 标
        rule_state='invalid' + 投递 agent 裁决（改/删），替代原「阈值失真」治理项
        （二者互斥：命中失效就不再报失真，避免同一规则两条治理噪音）。
        止损线破是资损事实，永不标失效（走退役/治理，CONSTITUTIONAL_INTENTS 排除）。
        """
        self.judge.mark_emitted(rule.id, idx, now, rule.symbol)
        if rule.id in self.state.stale_reported:
            return
        self.state.stale_reported.add(rule.id)
        try:
            threshold = float((cond.get('params') or {}).get('price'))
            price = float(quote.price)
            dev = (price - threshold) / abs(threshold) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            dev = None

        # 失效实时判定：偏离超 **agent 设定的规则阈值**（必填，像止盈价/止损价一样是
        # 规则的具体参数，2026-10-22 用户裁定——不是程序常量）+ 非宪法级 + 仍 active
        # → 标 invalid 并投递。阈值 NULL（缺列库/异常数据）= 本拍不判失效，退回治理项。
        inv_threshold = getattr(rule, 'invalidation_threshold_pct', None)
        if (dev is not None and inv_threshold is not None
                and abs(dev) > float(inv_threshold)
                and str(getattr(rule, 'intent', '') or '') not in CONSTITUTIONAL_INTENTS
                and str(getattr(rule, 'rule_state', 'active') or 'active') == 'active'):
            self._mark_invalid_and_dispatch(
                rule, dev, threshold, price, now, float(inv_threshold))
            return

        reason = ('阈值失真：现价 %.2f 偏离阈值 %.2f（%+.1f%%），昨收已在触发侧'
                  '（陈旧驻留，非新穿越）→ 建议调阈值或退役此规则'
                  % (float(quote.price), threshold, dev)) if dev is not None else (
                  '阈值失真：昨收已在触发侧（陈旧驻留）→ 建议调阈值或退役此规则')
        try:
            self.notifier.record_governance(
                rule, reason,
                {'stale_residency': True,
                 'deviation_pct': round(dev, 2) if dev is not None else None})
            logger.info('陈旧驻留已转治理（不发消息）', rule_id=rule.id,
                        symbol=rule.symbol)
        except Exception as e:  # noqa: BLE001 - 治理项失败不阻断 tick
            logger.error('陈旧驻留治理项记录失败', rule_id=rule.id, error=str(e))

    def _mark_invalid_and_dispatch(self, rule, dev, threshold, price, now, inv_threshold):
        """标 invalid + 投递 agent 裁决（2026-10-22 三分支落地）。

        命中失效阈值（inv_threshold = agent 按规则设定的失效偏离%，必填）：规则退出
        active（list_by_state 不再返回它，停止盘中误触发），invalid_reason/invalid_at
        留痕，投递 agent 摘要队列请其裁决——调阈值回 active，或退役归 archived。
        触发优先于失效的铁律由调用方保证（stale_residency 只在「昨收已在触发侧」的
        陈旧规则上判，止损已由宪法豁免排除）。
        """
        reason = ('价格偏离 %.1f%%（现价 %.2f vs 阈值 %.2f，超 agent 设定失效线 %.1f%%），'
                  '规则标失效，待 agent 裁决（调阈值回 active / 退役归 archived）'
                  % (dev, price, threshold, inv_threshold))
        try:
            self.rule_repo.update_fields(
                rule.id, rule_state='invalid',
                invalid_reason=reason, invalid_at=now)
        except Exception as e:  # noqa: BLE001 - 标失效失败不阻断，退回治理项
            logger.error('标失效失败', rule_id=rule.id, error=str(e))
            return
        try:
            self.notifier.record_governance(
                rule, '[失效待裁决] ' + reason,
                {'invalidated': True, 'deviation_pct': round(dev, 2),
                 'actions': ['adjust_threshold', 'retire']})
            logger.info('规则已标失效并投递 agent', rule_id=rule.id,
                        symbol=rule.symbol, dev=round(dev, 2))
        except Exception as e:  # noqa: BLE001 - 投递失败不阻断（规则已标 invalid）
            logger.error('失效投递 agent 失败', rule_id=rule.id, error=str(e))

    def _archive_environment_trigger(self, rule, cond, quote, result, reason):
        """环境闸拦截的归档口：只落库、不发送（返回触发对象或 None）。

        优先走 suppressed 归档通道（`_record_suppressed_trigger`，
        watch_triggers.suppressed=true）：环境拦截与抑噪/日上限/伏击过期同属
        「只记录不动作」，用同一列给复盘侧一个可过滤的口径。

        退化为 `notifier.record_only`（不标记 suppressed）：部分装配/测试假件
        只提供 notifier 的落库口、没有 trigger_repo——归档不能因端口形态不同
        而丢失（丢失就会退化成"没记录也没动作"，比拦截本身更难排障）。

        两者都失败 → None：调用方不闩锁，下 tick 重试（at-least-once）。
        """
        if getattr(self.notifier, 'trigger_repo', None) is not None:
            archived = self._record_suppressed_trigger(
                rule, cond, quote, result, reason=reason)
            if archived is not None:
                return archived
        record_only = getattr(self.notifier, 'record_only', None)
        if not callable(record_only):
            return None
        try:
            return record_only(rule, cond, quote, result,
                               disposition=DISPOSITION_AUTO_OBSERVED,
                               disposition_reason=reason)
        except Exception as e:  # noqa: BLE001 - 归档失败由调用方决定重试
            logger.error('环境闸归档失败（record_only）',
                         rule_id=getattr(rule, 'id', None), error=str(e))
            return None

    def _record_suppressed_trigger(self, rule, cond, quote, result,
                                   reason=None, detail_extra=None):
        """触发只落库归档（suppressed=true），完全不外发。

        调用场景（reason 区分溯源，detail_extra 追加结构化留痕）：
          · 抑噪期（R6/t8）：规则被自愈置抑噪态（默认 reason）；
          · 日上限（REQ-261016155500-4f2a）：每规则每条件每日通知达上限后只归档；
          · 全局环境闸（2026-10-20）：环境不达标时个股信号全部只归档不动作；
          · 确认核验失败（2026-10-20，M2）：假信号样本，detail_extra 带三道逐项结论。

        为什么不复用 notifier.notify：notify 会按 trigger_level 选 agent 通道（=摘要队列）
        并推送，而抑噪/超限/环境拦截/假信号的语义正是"不推送、不进队列、不建待办"——只保留
        审计与聚合口径。

        触发仓储挂在 notifier 上（引擎本不持有 trigger_repo，装配在 inbound 层），
        故这里经 notifier 取；拿不到或落库失败只记日志，**绝不让异常打崩 tick**
        （抑噪是降噪手段，不该成为新的故障源）。
        """
        repo = getattr(self.notifier, 'trigger_repo', None)
        if repo is None:
            logger.warning('抑噪触发无法落库（notifier 未挂 trigger_repo）',
                           rule_id=getattr(rule, 'id', None))
            return None
        detail = {'value': result.value, 'message': result.message}
        if detail_extra:
            detail.update(detail_extra)
        try:
            return repo.record(
                rule_id=rule.id, symbol=rule.symbol, condition=cond,
                trigger_price=float(quote.price),
                detail=detail,
                notified=False, disposition=DISPOSITION_AUTO_OBSERVED,
                disposition_reason=reason or SUPPRESSED_TRIGGER_REASON, suppressed=True,
            )
        except Exception as e:  # noqa: BLE001 - 落库失败不得中断本轮 tick
            logger.error('抑噪触发落库失败', rule_id=getattr(rule, 'id', None), error=str(e))
            return None

    def _archive_staged_expired(self, rule, cond, quote, result, now, events) -> None:
        """两段式伏击「触及未确认」：归档 suppressed 样本（不通知/不占配额/不建待办）。

        与抑噪/日上限共用 _record_suppressed_trigger 通道（reason 区分溯源）。
        这些样本是「盘感样本积累」的事实源：触及了但没确认的伏击，复盘时
        正是它们回答「这个伏击点胜率如何」。
        """
        archived = self._record_suppressed_trigger(rule, cond, quote, result,
                                                   reason=STAGED_EXPIRED_REASON)
        events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                       'condition': cond, 'price': float(quote.price),
                       'message': result.message,
                       'disposition': DISPOSITION_AUTO_OBSERVED,
                       'disposition_reason': STAGED_EXPIRED_REASON,
                       'dup_of': None,
                       'trigger_id': getattr(archived, 'id', None),
                       'trigger_level': self._get_trigger_level(rule),
                       'suppressed': True,
                       'notified': False})

    def _record_trigger_event(self, now: datetime, rule_id: int, symbol: str) -> None:
        """委托 StateManager（保留薄封装：既有调用点与测试直接用它）"""
        self.state.record_trigger_event(now, rule_id, symbol)

    def _get_recent_trigger_count(self, rule_id: int, window_minutes: int = 10) -> int:
        """委托 StateManager（保留薄封装）"""
        return self.state.recent_trigger_count(self.now_fn(), rule_id, window_minutes)

    def _get_concurrent_trigger_count(self, symbol: str, rule_id: int,
                                      window_seconds: int = 60) -> int:
        """委托 StateManager（保留薄封装）"""
        return self.state.concurrent_trigger_count(self.now_fn(), symbol, rule_id, window_seconds)
