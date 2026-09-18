"""WatchEngine 盯盘引擎核心

tick() 为一次完整判定（同步、可单测）；run_forever() 为常驻循环。
仅交易日（周一至周五）9:30-11:30 / 13:00-15:00 运行。
"""
import os
import time as time_module
from datetime import datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional

import structlog

from application.services.watch_engine.conditions import EvalContext, evaluate
from application.services.watch_engine.rule_evaluator import RuleEvaluator
from application.services.watch_engine.state_manager import StateManager
from application.services.watch_engine.trigger_judge import TriggerJudge
from domain.watch.services.disposition import (
    DEDUP_WINDOW_SEC, DISPOSITION_AUTO_OBSERVED, normalize_symbol,
)
from domain.watch.services import noise_policy
from application.services.watch_engine.deduplication_manager import DeduplicationManager
from application.services.watch_engine.disposition_engine import DispositionEngine
from application.services.watch_engine.escalation_coordinator import EscalationCoordinator
from domain.watch.services.escalation_checker import EscalationChecker
from domain.watch.models import QuoteData
from domain.trading.services.market_session_policy import (
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
                 base_interval: int = 60, fast_interval: int = 10,
                 buffer_ratio: float = 0.2, history_minutes: int = 30,
                 now_fn: Callable[[], datetime] = datetime.now,
                 escalation_checker: Optional[EscalationChecker] = None,
                 position_value_provider: Optional[Callable] = None,
                 account_total_provider: Optional[Callable] = None,
                 digest_service=None, ledger=None, meta_review_service=None,
                 position_lifecycle_service=None, market_watch_service=None,
                 runtime_state_store=None,
                 todo_service=None, receipt_service=None, sla_job=None,
                 self_heal_service=None):
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
        try:
            self._heartbeat_interval_sec = float(
                os.getenv(HEARTBEAT_INTERVAL_ENV, str(DEFAULT_HEARTBEAT_INTERVAL_SEC)))
        except (TypeError, ValueError):
            self._heartbeat_interval_sec = DEFAULT_HEARTBEAT_INTERVAL_SEC
        self.state = StateManager(event_retention_min=30,
                                  dedup_window_sec=self.dedup_window_sec,
                                  store=self._runtime_store)
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
        # 市场级盯盘（P6）：指数/涨停家数/情绪/量能/板块——盯盘是紧盯市场的工具
        self.market_watch_service = market_watch_service
        # ── 闭环装配（REQ-c9f899 t12 §6-项8）──────────────────────────────
        # 仅当 WATCH_TODO_ENABLED 开启时由 factory 注入（TodoService/ReceiptService/
        # WatchSlaJob/NoiseSelfHealService）；默认 None → 引擎行为与改造前一致：
        # 不建待办、通知不带级别（旧渲染路径）。
        self.todo_service = todo_service
        self.receipt_service = receipt_service
        self.sla_job = sla_job
        self.self_heal_service = self_heal_service
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
        # 2026-09-11（w-f4aa1f6a 步2）：交易日判断收敛到唯一入口（原为只判周末）
        from application.services.trading_day_guard import TradingDayGuard
        while not self._stopped:
            now = self.now_fn()
            # 心跳（t10）：线程若死，外部巡检据此发现"引擎不再产生心跳"
            self._write_heartbeat(now)
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
                # 摘要门：队列非空 + 冷却窗 + 当日预算（状态落库，重启不清零）
                try:
                    if self.digest_service is not None:
                        self.digest_service.maybe_wake(now)
                except Exception as e:
                    logger.error('摘要门异常', error=str(e))
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
                # 持仓生命周期联动：每日一次（买入完成/清仓收摊，RFC 014 v3 §2.3）
                try:
                    if (self.position_lifecycle_service is not None
                            and self._last_lifecycle_date != now.date()):
                        s = self.position_lifecycle_service.reconcile(now)
                        self._last_lifecycle_date = now.date()
                        if s.get('retired') or s.get('created'):
                            logger.info('持仓生命周期联动完成', retired=s['retired'], created=s['created'])
                except Exception as e:
                    logger.error('持仓生命周期联动异常', error=str(e))
                interval = self.fast_interval if self.fast_mode else self.base_interval
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
                # 三段判定（闩锁/冷却）委托 TriggerJudge：未触发→重新武装、
                # 持续成立→不重复、冷却内→跳过
                if not self.judge.should_emit(rule.id, idx, result.triggered, cond, now):
                    continue

                # ── 抑噪期短路（REQ-c9f899 R6 / t8）──────────────────────────
                # 该规则反复触发、已被 NoiseSelfHealService 置抑噪态（noise_state +
                # suppress_until）：本次触发不升级、**不进摘要队列、不建待办**
                # （修规则待办已由自愈 scan 建好），只落一条 suppressed=true 的归档触发
                # 供聚合与复盘；到点自动恢复原级别。判据复用 noise_policy.is_suppressed
                # 单一事实源（与自愈服务同源，不新造第二份口径）。
                if noise_policy.is_suppressed(getattr(rule, 'noise_state', None),
                                              getattr(rule, 'suppress_until', None), now):
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
                    continue
                
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
                # 去重：同标的同向窗内合并；跨规则重叠另转治理（每对每天一次）
                outcome = self.dedup.check(rule, cond, now)
                dup_of = None
                if outcome.is_duplicate:
                    disposition = 'deduped'
                    disposition_reason = self.dedup.reason_text(outcome)
                    dup_of = outcome.dup_of
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
                    )
                    if notify_level:
                        notify_kwargs['level'] = notify_level
                    trigger = self.notifier.notify(rule, cond, quote, result, **notify_kwargs)
                except Exception as e:
                    # 不闩锁、不记 _last_triggered，下个 tick 重试（at-least-once）
                    logger.error('通知发送失败', rule_id=rule.id, cond=cond, error=str(e))
                    continue
                # ── 落待办（REQ-c9f899 t12）：闭环唯一载体 ────────────────────────
                # 触发 → 待办是「L1→L2→L3 晋升 + 到期巡检 + 三段回执」的载体；没有它闭环空转。
                # 位置说明（对父指令的 1 处偏差，已在汇报声明）：待办需要 trigger_id 做溯源与
                # 幂等（同一触发最多一条待办）+ 回填 watch_triggers.todo_id，而 trigger_id 只在
                # notifier.notify 落完触发记录后才存在，故创建紧跟在 notify 返回之后（不是之前）。
                # 失败只记日志，绝不打断通知/记账/闩锁（tick 的 at-least-once 靠后续触发重试）。
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
                self.judge.mark_emitted(rule.id, idx, now, rule.symbol)
                # 可观测性（2026-09-11，w-aebfddcd E2E 发现）：事件必须带**处置结论**，
                # 否则调用方无法区分"命中并通知"与"命中但被去重/被预算压掉"，只能回查库。
                # disposition 即答案：escalated/pending=进队列并推送；deduped=只归档不打扰；
                # auto_observed/ignored/expired=记录但不打扰。
                events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                               'condition': cond, 'price': float(quote.price),
                               'message': result.message,
                               'disposition': disposition,
                               'disposition_reason': disposition_reason,
                               'dup_of': dup_of,
                               'trigger_id': getattr(trigger, 'id', None),
                               'trigger_level': trigger_level,
                               'notified': disposition not in ('deduped', 'auto_observed',
                                                               'ignored', 'expired')})

        # 去重窗裁剪：清掉已过期的键，避免长跑进程内的无界增长（委托 StateManager）
        self.state.prune_dedup(now)

        # 市场级规则扫描（P6）：与个股 tick 分开的数据通道；服务自带节流与闩锁
        try:
            if self.market_watch_service is not None:
                self.market_watch_service.scan_market_rules(now)
        except Exception as e:
            logger.error('市场级扫描异常', error=str(e))

        # 运行态落库（REQ-c9f899 R10）：tick 末尾只写脏键（节流即"每 tick 一次"）。
        # 开关关闭时 state.store=None，flush 内部直接返回，零 I/O。
        try:
            self._flush_runtime_state()
        except Exception as e:  # 双保险：flush 已自吞异常，tick 不许被它打崩
            logger.error('运行态落库异常', error=str(e))

        self.fast_mode = fast
        return events

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
        return self.state.restore_from_store(now=self.now_fn(), symbols=symbols)

    def _flush_runtime_state(self) -> bool:
        """tick 末尾落库入口（委托 StateManager；未启用时 no-op 返回 False）。

        now 由引擎时钟注入：三类扩展的窗口裁剪/节流都以它为准（此前 StateManager
        内部取 datetime.now() 会与引擎注入的 now_fn 形成两套时间口径）。
        """
        return self.state.flush(now=self.now_fn())

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
            from domain.watch.services.disposition import CONSTITUTIONAL_INTENTS, intent_of
            from domain.watch.services.level_resolver import resolve_level

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
            from domain.trading.services.market_session_policy import CONTINUOUS_END as _close
        except Exception:  # noqa: BLE001 - 常量缺失时退回最简口径（当日 15:00）
            _close = time(15, 0)
        day_close = datetime.combine(now.date(), _close)
        due = day_close if day_close > now else now + timedelta(minutes=1)
        return due, max(1, int((due - now).total_seconds()))

    @staticmethod
    def _todo_account(rule):
        """规则归属账户（复用 rule_guard.effective_account 单一出处；失败退回 account）"""
        try:
            from domain.watch.services.rule_guard import effective_account
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
            from domain.watch.services.disposition import intent_of, is_trade_intent
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
        )

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

    def _record_suppressed_trigger(self, rule, cond, quote, result):
        """抑噪期触发只落库归档（suppressed=true），完全不外发（R6 / t8）。

        为什么不复用 notifier.notify：notify 会按 trigger_level 选 agent 通道（=摘要队列）
        并推送，而抑噪期的语义正是"不推送、不进队列、不建待办"——只保留审计与聚合口径。

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
                disposition_reason=SUPPRESSED_TRIGGER_REASON, suppressed=True,
            )
        except Exception as e:  # noqa: BLE001 - 落库失败不得中断本轮 tick
            logger.error('抑噪触发落库失败', rule_id=getattr(rule, 'id', None), error=str(e))
            return None

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
