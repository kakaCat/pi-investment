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

from qs_watch.application.services.watch_engine.conditions import (
    DEFAULT_DAILY_EMIT_CAP, EvalContext, evaluate,
    freshness_of,
)
from qs_watch.application.services.watch_engine.market_watch_service import MARKET_SCOPES
from qs_watch.application.services.watch_engine.rule_evaluator import RuleEvaluator
from qs_watch.application.services.watch_engine.staged_break_manager import (
    OUTCOME_CONFIRMED, OUTCOME_EXPIRED, StagedBreakManager,
)
from qs_watch.application.services.watch_engine.state_manager import StateManager
from qs_watch.application.services.watch_engine.trigger_judge import TriggerJudge
from qs_watch.domain.watch.services.disposition import (
    DEDUP_WINDOW_SEC, DISPOSITION_AUTO_OBSERVED, normalize_symbol,
)
from qs_watch.domain.watch.services import noise_policy
from qs_watch.application.services.watch_engine.deduplication_manager import DeduplicationManager
from qs_watch.application.services.watch_engine.disposition_engine import DispositionEngine
from qs_watch.application.services.watch_engine.escalation_coordinator import EscalationCoordinator
from qs_watch.domain.watch.services.escalation_checker import EscalationChecker
from qs_watch.domain.watch.models import QuoteData
from qs_trading.domain.trading.services.market_session_policy import (
    TOTAL_TRADING_MINUTES,   # 单一出处（RFC 016 §8.1）；本模块继续再导出以兼容既有 importer
    MarketSessionPolicy,
)

logger = structlog.get_logger(__name__)

# 运行态持久化开关（REQ-c9f899 R10）：默认关闭 —— 关掉时行为与改造前完全一致
RUNTIME_PERSIST_ENV = 'WATCH_RUNTIME_PERSIST_ENABLED'


def _runtime_persist_enabled() -> bool:
    return os.getenv(RUNTIME_PERSIST_ENV, 'false').strip().lower() in (
        '1', 'true', 'yes', 'on')


#: 抑噪期触发的归档理由（REQ-c9f899 R6 / t8）：与 NoiseSelfHealService 已经建出的
#: 「修规则」待办呼应——告诉读者这条触发为什么不推送、去哪里看它的处置。
SUPPRESSED_TRIGGER_REASON = '规则处于抑噪期（反复触发），已改造为修规则待办'

#: 每日通知上限归档文案（REQ-261016155500-4f2a wt:engine:1）：每规则每条件每日
#: ≤ DEFAULT_DAILY_EMIT_CAP 次通知，超限只归档不打扰（与抑噪同通道，reason 区分）。
#: 直接内插常量（曾用 %d 占位忘记格式化，数字会原样落库——2026-10-16 审核修正）。
DAILY_CAP_REASON = ('当日通知次数已达上限（每规则每条件每日 '
                    f'{DEFAULT_DAILY_EMIT_CAP} 次），仅归档不推送')

#: 两段式伏击「触及未确认」的归档理由（2026-10-19 P1）：观察窗到期确认未成立，
#: 落一条 suppressed 样本供复盘（盘感样本的事实源），不通知、不占日配额。
STAGED_EXPIRED_REASON = '伏击观察窗到期未确认（触及≠信号），仅归档样本'


def _build_runtime_store():
    """懒构造运行态适配器；装配失败只记日志返回 None（降级为纯内存，不阻断启动）。

    延迟 import：默认关闭时不必为未启用的持久化加载 ORM/适配器链路。
    """
    try:
        from adapters.outbound.repositories.watch_runtime_state_repository import (
            WatchRuntimeStateRepository,
        )
        return WatchRuntimeStateRepository()
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
                 outcome_backfill_service=None):
        self.rule_repo = rule_repo
        self.quote_service = quote_service
        self.notifier = notifier
        self.observe_agg = observe_agg
        self.avg_volume_provider = avg_volume_provider
        # 2026-10-20 扩展条件（ma_break/rsi/fund_flow）的取数 provider；None=对应条件降级
        self.fund_flow_provider = fund_flow_provider
        self.kline_closes_provider = kline_closes_provider
        # 市场环境复合门缓存（_check_market_gate 用，60s TTL）
        self._gate_cache: tuple = (None, None)
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
            'sidecar_running': bool(self._sidecar_thread and self._sidecar_thread.is_alive()),
            # 心跳可观测（REQ-c9f899 t10）：外部排障时先看这三项——
            # last_at 为空 = 从未写出心跳（未启用或写失败）；failures>0 = 存活信号在丢。
            'heartbeat_enabled': _heartbeat_enabled(),
            'heartbeat_last_at': (self._last_heartbeat_at.isoformat()
                                  if self._last_heartbeat_at else None),
            'heartbeat_failures': self._heartbeat_failures,
        }

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
        if not (TradingDayGuard.is_trading_day(now.date())
                and self.is_trading_time(now.time())):
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
                interval = max(1.0, (self.fast_interval if self.fast_mode
                                     else self.base_interval) - elapsed)
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

        # A1（2026-10-19）：同 tick 同 symbol 只取一次价——此前同标的 N 条规则每 tick
        # 发 N 次行情请求，规则多时 tick 时长线性膨胀。按 symbol 去重取价后逐规则
        # 共享同一 quote（价格点天然一致）。
        # 价格历史也按 symbol 推一次：同 tick 同 symbol 重复推点会产生同 ts 重复行，
        # 批量 upsert 的 ON CONFLICT 直接抛 CardinalityViolation（2026-10-16 实测
        # watch_price_history 0 行、冷却/去重每 tick 全丢）。
        quotes: Dict[str, Any] = {}
        quote_error_symbols: Set[str] = set()
        for symbol in dict.fromkeys(r.symbol for r in active_rules):   # 保序去重
            try:
                quotes[symbol] = self.quote_service.get_realtime_quote(symbol)
            except Exception as e:
                # 取价异常隔离（P0-1）：数据源抖一次只让该标的本轮失明
                logger.error('取价异常跳过（本轮该标的规则失明，其余标的不受影响）',
                             symbol=symbol, error=str(e))
                quote_error_symbols.add(symbol)
        for symbol, quote in quotes.items():
            if quote is not None:
                self._push_history(symbol, now, float(quote.price))

        for rule in active_rules:
            if rule.symbol in quote_error_symbols:
                continue   # 异常已记日志（上方取价循环）
            quote = quotes.get(rule.symbol)
            if quote is None:
                logger.warning('取价失败跳过', symbol=rule.symbol)
                self._note_quote_failure(rule, now)
                continue
            if self.state.quote_fail_days.get(rule.symbol):
                self.state.quote_fail_days[rule.symbol] = 0
            ctx = self._build_ctx(rule, now)

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
                    if outcome == OUTCOME_CONFIRMED:
                        self._process_condition(rule, idx, cond, quote, result,
                                                now, events)
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
                self._process_condition(rule, idx, cond, quote, result, now, events)

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

    def _check_market_gate(self, gate: dict, now) -> tuple:
        """市场环境复合门判定：返回 (blocked, reason)。

        gate spec（action_params.market_gate）：
          index        看哪个指数（默认 000001.SH）
          max_down_pct 指数跌幅 ≤ 此值（如 -1.5）→ 拦截（系统性风险日不接飞刀）
          max_up_pct   指数涨幅 ≥ 此值（如 +3.0）→ 拦截（过热追高保护，可选）
        数据缺失 fail-open 不拦截；市场快照 60s 缓存。
        """
        idx = str(gate.get('index') or '000001.SH')
        state = None
        cached_at, cached = self._gate_cache
        if cached is not None and (now - cached_at).total_seconds() < 60:
            state = cached
        elif self.market_watch_service is not None:
            provider = getattr(self.market_watch_service, 'state_provider', None)
            if provider is not None:
                try:
                    state = provider.get_state()
                    self._gate_cache = (now, state)
                except Exception as e:  # noqa: BLE001 - 取数失败 fail-open
                    logger.warning('市场门取数失败（放行）', error=str(e))
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
        lines = ['今日规则体检：%d 条待处理（调阈值/退役/补激活后自动消失）：' % len(rows)]
        for t in rows[:8]:
            lines.append('• 规则#%s %s：%s' % (t.rule_id, t.symbol,
                                              (t.disposition_reason or '')[:60]))
        if len(rows) > 8:
            lines.append('• …另有 %d 条（详情查 watch_triggers）' % (len(rows) - 8))
        from qs_watch.application.services.watch_engine.watch_channels import send_watch_receipt
        ok = send_watch_receipt({'kind': 'daily_review', 'message': '\n'.join(lines),
                                 'level': 'P2'})
        if ok:
            logger.info('收盘体检日报已发', count=len(rows))
        else:
            logger.warning('收盘体检日报未送达', count=len(rows))

    def _process_condition(self, rule, idx: int, cond: dict, quote, result,
                           now, events) -> None:
        """单条条件的「评估后」流水线（个股与市场级共用，2026-10-19 提取）。

        覆盖：闩锁/冷却/迟滞 → 陈旧驻留 → 日上限（宪法豁免）→ 抑噪 → 升级 →
        处置五门 → 去重/重叠治理 → 通知或聚合缓冲 → 日通知计数 → 待办 →
        介入记账 → 止损使命退役 → 闩锁回退 → 事件记录。

        为什么提取：市场级规则（P6）此前走「半条流水线」（notified=False 写死、
        闩锁纯内存、不占预算、不建待办）——评估器不同（MarketRuleEvaluator 吃
        市场快照），但评估之后的路**完全相同**。market scan 把评估结果连同
        quote 轻量投影（price=指标值）喂进本方法，两条数据通道共用一条处置链。
        返回 None；产出的事件追加进 events（tick 的返回载体）。
        """
        # 三段判定（闩锁/冷却/迟滞带）委托 TriggerJudge：未触发→迟滞带内保持
        # 闩锁、带外重新武装；持续成立→不重复；冷却内→跳过。
        # value=result.value：price_break 的迟滞带按现价判定（combined/velocity
        # 等非价格条件 value 语义不同或为空 → within_hysteresis_band 直接放行）。
        if not self.judge.should_emit(rule.id, idx, result.triggered, cond, now,
                                      value=result.value):
            return

        # ── 陈旧驻留判定（2026-10-19 用户裁定）─────────────────────
        # 昨收已在触发侧 = 非今日新穿越（零信息增量）：它不是市场事件，
        # 是规则失真信号。不发消息不进缓冲，闩锁锁住（今日不再报），
        # 每规则每日落一条「阈值失真」治理项进 agent 摘要队列。
        if freshness_of(cond, getattr(quote, 'prev_close', None)) is False:
            self._handle_stale_residency(rule, idx, cond, quote, result, now)
            return

        # ── 每日通知上限短路（REQ-261016155500-4f2a wt:engine:1）──────────
        # 每规则每条件每日 ≤ DEFAULT_DAILY_EMIT_CAP 次通知：超限不通知、不建待办、
        # 不进摘要队列，只落一条 suppressed=true 归档（与抑噪同通道，reason 区分）。
        # 宪法豁免（2026-10-19）：exit_stop 等宪法级意图不适用日上限——与 dedup
        # 守卫同源裁定（止损被吞 = 资损风险）。注意本判定在升级检查之前，故
        # 「L1 升级成 L2」的触发仍受上限约束，只有规则意图本身宪法级才豁免。
        if (self.judge.daily_emit_exceeded(rule.id, idx, now)
                and not self._is_constitutional(rule)):
            capped = self._record_suppressed_trigger(
                rule, cond, quote, result, reason=DAILY_CAP_REASON)
            self.judge.mark_emitted(rule.id, idx, now, rule.symbol)
            events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                           'condition': cond, 'price': float(quote.price),
                           'message': result.message,
                           'disposition': DISPOSITION_AUTO_OBSERVED,
                           'disposition_reason': DAILY_CAP_REASON,
                           'dup_of': None,
                           'trigger_id': getattr(capped, 'id', None),
                           'trigger_level': self._get_trigger_level(rule),
                           'suppressed': True,
                           'notified': False})
            logger.info('日上限触发已归档（不推送/不进队列）', rule_id=rule.id,
                        symbol=rule.symbol,
                        trigger_id=getattr(capped, 'id', None))
            return

        # ── 抑噪期短路（REQ-c9f899 R6 / t8）──────────────────────────
        # 该规则反复触发、已被 NoiseSelfHealService 置抑噪态（noise_state +
        # suppress_until）：本次触发不升级、**不进摘要队列、不建待办**
        # （修规则待办已由自愈 scan 建好），只落一条 suppressed=true 的归档触发
        # 供聚合与复盘；到点自动恢复原级别。判据复用 noise_policy.is_suppressed
        # 单一事实源（与自愈服务同源，不新造第二份口径）。
        if noise_policy.is_suppressed(getattr(rule, 'noise_state', None),
                                      getattr(rule, 'suppress_until', None), now):
            # 归档节流（P1-6，2026-10-19）：抑噪期每日每规则只留一条 suppressed
            # 样本（账不丢、可复盘），后续触发只闩锁/冷却不再落库——否则会按
            # 冷却周期灌归档表，且这些行会喂大自愈的噪音统计（自反馈）。
            if rule.id in self.state.suppressed_reported:
                suppressed_trigger = None
            else:
                self.state.suppressed_reported.add(rule.id)
                suppressed_trigger = self._record_suppressed_trigger(rule, cond, quote, result)
            self.judge.mark_emitted(rule.id, idx, now, rule.symbol)
            events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                           'condition': cond, 'price': float(quote.price),
                           'message': result.message,
                           'disposition': DISPOSITION_AUTO_OBSERVED,
                           'disposition_reason': SUPPRESSED_TRIGGER_REASON,
                           'dup_of': None,
                           'trigger_id': getattr(suppressed_trigger, 'id', None),
                           'trigger_level': self._get_trigger_level(rule),
                           'suppressed': True,
                           'notified': False})
            logger.info('抑噪期触发已归档（不推送/不进队列）', rule_id=rule.id,
                        symbol=rule.symbol,
                        trigger_id=getattr(suppressed_trigger, 'id', None))
            return
        
        # 升级检查：L0/L1 触发满足条件时自动升级为 L2（委托 EscalationCoordinator）
        escalation_reason = self.escalation.check(rule, cond, quote, result, now)
        trigger_level = self._get_trigger_level(rule)
        
        # ── 处置决策（REQ-f08def）─────────────────────────────
        # 机械优先：去重合并 / observe 类归档当场收敛（零 LLM），
        # 只有 L2 或升级触发才进 agent 摘要队列（用户硬约束：token 成本）。
        # escalation_reason 带进处置结论（2026-09-14）：此前 decide() 只收到
        # escalated 布尔，固定回一句「升级策略命中（L1→L2）」，使「哪条升级
        # 路径命中」在库里不可考（核查时曾被此误导）。
        disposition, disposition_reason = self.disposition.decide(
            rule, cond, quote, escalated=bool(escalation_reason),
            escalation_reason=escalation_reason)
        # 去重：同标的同向窗内合并；跨规则重叠另转治理（每对每天一次）。
        # 守卫（REQ-261016155500-4f2a wt:engine:2）：dedup 命中**不再无条件**改判
        # deduped——escalated/exit_stop 是宪法级消息（止损被吞 = 资损风险），
        # 只合并展示（标注先响规则）照发不误；其余处置维持合并不通知。
        # ── 市场环境复合门（2026-10-20，流程图 H 节点「二次校验市场环境」）────
        # 个股信号成立后查大盘：环境异常（如暴跌）则「只记录不动作」——伏击单不在
        # 系统性风险日接飞刀。规则侧开关：action_params.market_gate。
        # 拦截=归档一条触发（notified=False）+ 闩锁/冷却/日计数照常，直接 return。
        ap = getattr(rule, 'action_params', None)
        gate = ap.get('market_gate') if isinstance(ap, dict) else None
        if gate and disposition in ('pending', 'escalated'):
            blocked, gate_why = self._check_market_gate(gate, now)
            if blocked:
                try:
                    gated_trigger = self.notifier.record_only(
                        rule, cond, quote, result, disposition=DISPOSITION_AUTO_OBSERVED,
                        disposition_reason=gate_why)
                except Exception as e:
                    logger.error('市场门归档失败（不闩锁，下 tick 重试）',
                                 rule_id=rule.id, error=str(e))
                    return
                self.judge.bump_daily_emit(rule.id, idx, now)
                self.judge.mark_emitted(rule.id, idx, now, rule.symbol)
                self.dedup.mark_notified(rule, cond, now,
                                         getattr(gated_trigger, 'id', 0) or 0)
                events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                               'condition': cond, 'price': float(quote.price),
                               'message': result.message,
                               'disposition': DISPOSITION_AUTO_OBSERVED,
                               'disposition_reason': gate_why,
                               'dup_of': None, 'merged_from_rule': None,
                               'trigger_id': getattr(gated_trigger, 'id', None),
                               'trigger_level': self._get_trigger_level(rule),
                               'notified': False})
                logger.info('市场门拦截（只记录不动作）', rule_id=rule.id,
                            symbol=rule.symbol, reason=gate_why)
                return

        outcome = self.dedup.check(rule, cond, now)
        dup_of = None
        merged_from_rule = None
        if outcome.is_duplicate:
            if disposition in ('pending', 'auto_observed', 'ignored', 'expired'):
                disposition = 'deduped'
                disposition_reason = self.dedup.reason_text(outcome)
                dup_of = outcome.dup_of
            else:
                merged_from_rule = outcome.prev_rule_id
                disposition_reason = (
                    (disposition_reason + '；') if disposition_reason else ''
                ) + '与规则#%s 同事件（%ds 窗内），已合并展示但不吞消息' % (
                    outcome.prev_rule_id, self.dedup_window_sec)
            if outcome.overlap_pair:
                reason = self.dedup.overlap_reason(outcome.overlap_pair, outcome.key)
                try:
                    self.notifier.record_governance(
                        rule, reason,
                        {'overlap_with_rule': outcome.overlap_pair[0],
                         'key': list(outcome.key)})
                    logger.info('规则重叠已转治理',
                                rules=list(outcome.overlap_pair),
                                key=list(outcome.key))
                except Exception as e:
                    logger.error('规则重叠治理项记录失败', error=str(e))

        try:
            # 金额门取数复用一次（与级别判定的"是否持仓"输入同源，避免重复查库）
            action_amount = self._position_value(rule)
            # 按级别渲染（t12 §6-项1）：仅闭环开启（todo_service 注入）时给级别；
            # 否则 None → 通知保持旧渲染（默认行为与改造前一致）。
            notify_level = self._notify_level(rule, disposition,
                                              has_position=bool(action_amount))
            notify_kwargs = dict(
                escalation_reason=escalation_reason,
                disposition=disposition,
                disposition_reason=disposition_reason,
                dup_of=dup_of,
                action_amount_yuan=action_amount,
                merged_from_rule=merged_from_rule,
            )
            if notify_level:
                notify_kwargs['level'] = notify_level
            # 观察聚合路由（REQ-261016155500-4f2a wt:validate:1）：无判据 observe
            # 触发不进即时通道，落库后入 15 分钟聚合缓冲（卡内逐条可溯源）；
            # 有判据 observe 与 escalated/pending 等需动作类照旧即时单发。
            buffered = (self.observe_agg is not None
                        and self.observe_agg.should_buffer(rule, disposition))
            if buffered:
                buffer_reason = ((disposition_reason or '')
                                 + '；已进 15 分钟聚合缓冲（合屏发送）')
                trigger = self.notifier.record_only(
                    rule, cond, quote, result, disposition=disposition,
                    disposition_reason=buffer_reason)
                disposition_reason = buffer_reason
                from qs_watch.domain.watch.services.watch_message import (
                    relation_of, resolve_action,
                )
                self.observe_agg.add(
                    getattr(rule, 'linked_account', None) or getattr(rule, 'account', None),
                    rule.symbol,
                    {'rule_id': rule.id,
                     'trigger_id': getattr(trigger, 'id', None),
                     'message': result.message,
                     'price': float(quote.price),
                     'name': getattr(quote, 'name', None),
                     'at': now.isoformat()},
                    now, float(quote.price),
                    action_text=resolve_action(
                        action_params=getattr(rule, 'action_params', None),
                        next_action_hint=getattr(rule, 'next_action_hint', None),
                        intent=getattr(rule, 'intent', None),
                        rule_id=rule.id).text,
                    relation_text=relation_of(
                        rule,
                        self._pnl_of(rule, quote)))
            else:
                trigger = self.notifier.notify(rule, cond, quote, result, **notify_kwargs)
        except Exception as e:
            # 不闩锁、不记 _last_triggered，下个 tick 重试（at-least-once）
            logger.error('通知发送失败', rule_id=rule.id, cond=cond, error=str(e))
            return
        # 送达成功才算一次「日通知」（上限计数的事实源）：notifier 内部吞发送
        # 异常并以 trigger.notified 反映结果，失败不计数、行为与改前一致。
        # 聚合缓冲也计入日上限（2026-10-19）：缓冲路径 trigger.notified 恒 False
        # （设计上不单发），此前 observe 聚合通道完全不受日上限约束——恰是噪音
        # 最大的通道。入缓冲即计一次（用户会在聚合卡里看到它）。
        if buffered or trigger is None or getattr(trigger, 'notified', False):
            self.judge.bump_daily_emit(rule.id, idx, now)
        # ── 落待办（REQ-c9f899 t12）：闭环唯一载体 ────────────────────────
        # 触发 → 待办是「L1→L2→L3 晋升 + 到期巡检 + 三段回执」的载体；没有它闭环空转。
        # 位置说明（对父指令的 1 处偏差，已在汇报声明）：待办需要 trigger_id 做溯源与
        # 幂等（同一触发最多一条待办）+ 回填 watch_triggers.todo_id，而 trigger_id 只在
        # notifier.notify 落完触发记录后才存在，故创建紧跟在 notify 返回之后（不是之前）。
        # 失败只记日志，绝不打断通知/记账/闩锁（tick 的 at-least-once 靠后续触发重试）。
        # 聚合缓冲的触发不建待办（2026-10-19）：无判据 observe 属「记录不打扰」，
        # 且聚合卡最长 15 分钟后才到用户——待办 SLA 时钟不应早于用户可见。
        if not buffered:
            try:
                self._create_watch_todo(rule, now, disposition, trigger, notify_level)
            except Exception as e:  # 双保险：helper 已自吞异常，tick 不许被打挂
                logger.error('建待办异常（tick 继续）', rule_id=rule.id, error=str(e))
        if disposition != 'deduped':
            self.dedup.mark_notified(rule, cond, now,
                                     getattr(trigger, 'id', 0) or 0)
        if disposition == 'escalated':
            # 增量门 + 预算记账：escalated = 进 agent 摘要队列 = 一次潜在介入
            norm = normalize_symbol(rule.symbol)
            intent = str(getattr(rule, 'intent', '') or '') or                         str((rule.action_hint or {}).get('action_on_trigger', '') if isinstance(getattr(rule, 'action_hint', None), dict) else '')
            self.state.last_intervention[(norm, intent or 'unknown')] = now
            self.state.interventions_today += 1
            if self.ledger is not None:
                self.ledger.record(
                    symbol=rule.symbol, intent=(intent or None), rule_id=rule.id,
                    trigger_kind='price', outcome='escalated',
                    trigger_ids=[getattr(trigger, 'id', None)],
                )
        # ── 止损使命完成自动退役（2026-10-19 用户裁定：过期的由引擎处理）─
        # exit_stop 触发即消费：这条止损线已被穿越，无论用户是否执行卖出，
        # 原阈值都已失效（再挂只会变成陈旧驻留噪音）。引擎直接退役规则并
        # 落治理注记——未平仓的新风控线由 agent 起草、用户确认后重建。
        self._maybe_retire_executed_stop(rule, disposition, now)
        self.judge.mark_emitted(rule.id, idx, now, rule.symbol)
        # 未送达不闩锁（REQ-261016155500-4f2a wt:engine:2）：notifier 先落库后
        # 发送，失败时 trigger.notified=False——回退闩锁/冷却（保留事件日志），
        # 下个 tick 重判再走 notify 的补发短路（同一 trigger 行重发，不新建不双发）。
        if (not buffered and trigger is not None
                and not getattr(trigger, 'notified', False)):
            # ⚠️ 聚合缓冲路径（buffered=True）的 trigger.notified 恒为 False
            # （设计上就不单发），绝不可走这里——否则闩锁/冷却每发即毁，
            # 规则每 60s dedup 窗口到期就复读（2026-10-19 实测规则 #239
            # 6 分钟触发 25 次的根因）。
            self.state.latched.discard((rule.id, idx))
            self.state.last_triggered.pop((rule.id, idx), None)
        # 可观测性（2026-09-11，w-aebfddcd E2E 发现）：事件必须带**处置结论**，
        # 否则调用方无法区分"命中并通知"与"命中但被去重/被预算压掉"，只能回查库。
        # disposition 即答案：escalated/pending=进队列并推送；deduped=只归档不打扰；
        # auto_observed/ignored/expired=记录但不打扰。
        # notified 口径（REQ-261016155500-4f2a wt:engine:2）：与 notifier 真实发送
        # 结果一致（trigger.notified）——此前 auto_observed 实际已推送却记 False，
        # 观测口径撒谎会误导排障。
        events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                       'condition': cond, 'price': float(quote.price),
                       'message': result.message,
                       'disposition': disposition,
                       'disposition_reason': disposition_reason,
                       'dup_of': dup_of,
                       'merged_from_rule': merged_from_rule,
                       'trigger_id': getattr(trigger, 'id', None),
                       'trigger_level': trigger_level,
                       'notified': bool(getattr(trigger, 'notified', False))})

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

    #: 连续多少个交易日取数失败报「疑似停牌/退市」治理项
    QUOTE_FAIL_GOVERNANCE_DAYS = 3

    def _note_quote_failure(self, rule, now):
        """取数失败计数：连续 N 个交易日失败 → 每规则每日一条停牌/退市治理项。

        此前取数失败只是静默跳过——规则对停牌/退市标的永久失效且无人发现。
        """
        sym = str(rule.symbol)
        n = self.state.quote_fail_days.get(sym, 0) + 1
        self.state.quote_fail_days[sym] = n
        if n < self.QUOTE_FAIL_GOVERNANCE_DAYS or sym in self.state.quote_fail_reported:
            return
        self.state.quote_fail_reported.add(sym)
        try:
            self.notifier.record_governance(
                rule,
                '疑似停牌/退市：标的 %s 连续 %d 个交易日取数失败 → 建议复核标的状态，'
                '确认后退役规则（取数失败期规则等同失效）' % (sym, n),
                {'quote_fail_days': n, 'suspected_halt': True})
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

    def _handle_stale_residency(self, rule, idx, cond, quote, result, now):
        """陈旧驻留处置（2026-10-19）：闩锁 + 每日一次阈值失真治理项（不进用户群）。

        闩锁必须置上：否则下一 tick 还会命中同一条件。治理项每规则每日一条
        （state.stale_reported 去重），经 record_governance 落 meta_review
        进 agent 摘要队列——规则失真是 agent 该修的活，不是用户该看的事。
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

    def _record_suppressed_trigger(self, rule, cond, quote, result,
                                   reason=None):
        """触发只落库归档（suppressed=true），完全不外发。

        两个调用场景（reason 区分溯源）：
          · 抑噪期（R6/t8）：规则被自愈置抑噪态（默认 reason）；
          · 日上限（REQ-261016155500-4f2a）：每规则每条件每日通知达上限后只归档。

        为什么不复用 notifier.notify：notify 会按 trigger_level 选 agent 通道（=摘要队列）
        并推送，而抑噪/超限的语义正是"不推送、不进队列、不建待办"——只保留审计与聚合口径。

        触发仓储挂在 notifier 上（引擎本不持有 trigger_repo，装配在 inbound 层），
        故这里经 notifier 取；拿不到或落库失败只记日志，**绝不让异常打崩 tick**
        （抑噪是降噪手段，不该成为新的故障源）。
        """
        repo = getattr(self.notifier, 'trigger_repo', None)
        if repo is None:
            logger.warning('抑噪触发无法落库（notifier 未挂 trigger_repo）',
                           rule_id=getattr(rule, 'id', None))
            return None
        try:
            return repo.record(
                rule_id=rule.id, symbol=rule.symbol, condition=cond,
                trigger_price=float(quote.price),
                detail={'value': result.value, 'message': result.message},
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
