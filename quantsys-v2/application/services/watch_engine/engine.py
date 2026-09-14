"""WatchEngine 盯盘引擎核心

tick() 为一次完整判定（同步、可单测）；run_forever() 为常驻循环。
仅交易日（周一至周五）9:30-11:30 / 13:00-15:00 运行。
"""
import time as time_module
from datetime import datetime, time
from typing import Any, Callable, Dict, List, Optional

import structlog

from application.services.watch_engine.conditions import EvalContext, evaluate
from application.services.watch_engine.rule_evaluator import RuleEvaluator
from application.services.watch_engine.state_manager import StateManager
from application.services.watch_engine.trigger_judge import TriggerJudge
from domain.watch.services.disposition import (
    DEDUP_WINDOW_SEC, GateContext, InterventionConfig,
    decide as decide_disposition, dedup_key, normalize_symbol,
)
from domain.watch.services.escalation_checker import EscalationChecker
from domain.watch.models import QuoteData
from domain.trading.services.market_session_policy import (
    TOTAL_TRADING_MINUTES,   # 单一出处（RFC 016 §8.1）；本模块继续再导出以兼容既有 importer
    MarketSessionPolicy,
)

logger = structlog.get_logger(__name__)


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
                 position_lifecycle_service=None, market_watch_service=None):
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
        self.state = StateManager(event_retention_min=30,
                                  dedup_window_sec=self.dedup_window_sec)
        # 规则取数保护（2026-09-14 重构 P1）：原内联在本类的按日缓存 / 硬超时 /
        # 失败熔断移入 RuleEvaluator；引擎保留 _get_avg_volume 薄封装（测试与
        # e2e monkeypatch 依赖该入口名）。
        self.evaluator = RuleEvaluator(avg_volume_provider=avg_volume_provider)
        # 触发判据（闩锁/冷却/标记）→ TriggerJudge（2026-09-14 重构 P1）
        self.judge = TriggerJudge(self.state)
        # 介入判据（REQ-f08def P3，RFC 014 v3 §3）：金额门/增量门/经济门/预算门所需的注入
        self._position_value_provider = position_value_provider
        self._account_total_provider = account_total_provider
        self._intervention_cfg = InterventionConfig()
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
        }

    # ── 主循环 ──────────────────────────────────────────────

    def run_forever(self):
        logger.info('WatchEngine 启动', base_interval=self.base_interval,
                    fast_interval=self.fast_interval)
        # 2026-09-11（w-f4aa1f6a 步2）：交易日判断收敛到唯一入口（原为只判周末）
        from application.services.trading_day_guard import TradingDayGuard
        while not self._stopped:
            now = self.now_fn()
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
                
                # 升级检查：L0/L1 触发满足条件时自动升级为 L2
                escalation_reason = None
                trigger_level = self._get_trigger_level(rule)
                
                if trigger_level in ('L0', 'L1'):
                    # 查询触发频率和并发触发数
                    recent_count = self._get_recent_trigger_count(rule.id)
                    concurrent_count = self._get_concurrent_trigger_count(rule.symbol, rule.id)
                    
                    quote_data = QuoteData(
                        symbol=rule.symbol,
                        price=float(quote.price),
                        change_pct=getattr(quote, 'change_pct', None),
                        volume=getattr(quote, 'volume', None),
                        prev_close=getattr(quote, 'prev_close', None),
                    )
                    
                    escalation_reason = self.escalation_checker.should_escalate(
                        rule=rule,
                        condition=cond,
                        quote=quote_data,
                        result=result,
                        recent_trigger_count=recent_count,
                        concurrent_trigger_count=concurrent_count,
                    )
                
                # ── 处置决策（REQ-f08def）─────────────────────────────
                # 机械优先：去重合并 / observe 类归档当场收敛（零 LLM），
                # 只有 L2 或升级触发才进 agent 摘要队列（用户硬约束：token 成本）。
                key = dedup_key(rule, cond)
                gate_ctx = self._build_gate_ctx(rule, cond, quote)
                disposition, disposition_reason = decide_disposition(
                    rule, cond, escalated=bool(escalation_reason),
                    gate=gate_ctx, cfg=self._intervention_cfg,
                    # 2026-09-14：把原始升级原因带进处置结论。此前 decide() 只收到
                    # escalated 布尔，固定回一句「升级策略命中（L1→L2）」，
                    # 使「哪条升级路径命中」在库里不可考（核查时曾被此误导）。
                    escalation_reason=escalation_reason)
                dup_of = None
                prev = self.state.recent_notified.get(key)
                if prev is not None and (now - prev[0]).total_seconds() < self.dedup_window_sec:
                    disposition = 'deduped'
                    disposition_reason = (
                        f'同标的同向 {self.dedup_window_sec}s 内已触发（key={key[0]}/{key[1]}），'
                        f'合并到触发 #{prev[1]}，不再重复通知'
                    )
                    dup_of = prev[1]
                    # 跨规则重叠 → 属于「规则该重设」的业务问题（用户 2026-09-11）：
                    # 除合并通知外，另落一条治理项交 agent 处置（同一天同一对规则只报一次）
                    prev_rule_id = prev[2] if len(prev) > 2 else None
                    if prev_rule_id is not None and prev_rule_id != rule.id:
                        pair = tuple(sorted((int(prev_rule_id), int(rule.id))))
                        if pair not in self.state.overlap_reported:
                            self.state.overlap_reported.add(pair)
                            reason = ('规则重叠：规则 #%s 与 #%s 在同一事件（%s/%s）上重复表达 → '
                                      '建议合并为一条多档规则、调阈值或退役其一' %
                                      (pair[0], pair[1], key[0], key[1]))
                            try:
                                self.notifier.record_governance(
                                    rule, reason,
                                    {'overlap_with_rule': pair[0], 'key': list(key)})
                                logger.info('规则重叠已转治理', rules=list(pair), key=list(key))
                            except Exception as e:
                                logger.error('规则重叠治理项记录失败', error=str(e))

                try:
                    trigger = self.notifier.notify(
                        rule, cond, quote, result,
                        escalation_reason=escalation_reason,
                        disposition=disposition,
                        disposition_reason=disposition_reason,
                        dup_of=dup_of,
                        action_amount_yuan=self._position_value(rule),
                    )
                except Exception as e:
                    # 不闩锁、不记 _last_triggered，下个 tick 重试（at-least-once）
                    logger.error('通知发送失败', rule_id=rule.id, cond=cond, error=str(e))
                    continue
                if disposition != 'deduped':
                    self.state.recent_notified[key] = (
                        now, getattr(trigger, 'id', 0) or 0, int(getattr(rule, 'id', 0) or 0))
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

        self.fast_mode = fast
        return events

    # ── 内部 ────────────────────────────────────────────────

    def _build_gate_ctx(self, rule, cond, quote) -> GateContext:
        '''构建介入判据上下文（RFC 014 v3 §3.2）。数据不足时留 None → 对应门跳过。'''
        ah = rule.action_hint if isinstance(getattr(rule, 'action_hint', None), dict) else {}
        intent = str(getattr(rule, 'intent', '') or ah.get('action_on_trigger') or '').strip()
        norm = normalize_symbol(rule.symbol)
        topic = intent or ah.get('action_on_trigger') or 'unknown'
        amount = None
        ev = None
        if intent in ('exit_stop', 'exit_take_profit', 'exit_reduce', 'add_position', 't_trade'):
            # 持仓级动作：金额 = 持仓市值
            amount = self._position_value(rule)
            if amount is not None:
                ev = amount * 0.05  # 粗估：一个 5% 动作的利害关系
        elif intent == 'entry':
            # 买入意向金额：action_hint.max_position_pct × 账户总资产（若有）
            mpp = ah.get('max_position_pct')
            total = self._account_total(rule)
            if mpp and total:
                amount = float(mpp) / 100.0 * float(total)
                ev = amount * 0.03
        return GateContext(
            intent=intent or None,
            amount_yuan=amount,
            last_intervention_at=self.state.last_intervention.get((norm, topic)),
            expected_value_yuan=ev,
            trigger_kind='price',
            daily_wake_count=self.state.interventions_today,
            change_pct=getattr(quote, 'change_pct', None),
        )

    def _position_value(self, rule) -> Optional[float]:
        if self._position_value_provider is None:
            return None
        try:
            return self._position_value_provider(rule)
        except Exception:
            return None

    def _account_total(self, rule=None) -> Optional[float]:
        # 2026-09-13（w-c8cae280）：透传规则，让金额门按规则归属账户取值。
        if self._account_total_provider is None:
            return None
        try:
            return self._account_total_provider(rule)
        except Exception:
            return None

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
        """获取规则的触发层级（L0/L1/L2）"""
        action_hint = getattr(rule, 'action_hint', None)
        if not action_hint:
            return 'L1'  # 默认 L1
        
        import json
        try:
            if isinstance(action_hint, str):
                ah = json.loads(action_hint)
            else:
                ah = action_hint
            return ah.get('trigger_level', 'L1')
        except Exception:
            return 'L1'

    def _record_trigger_event(self, now: datetime, rule_id: int, symbol: str) -> None:
        """委托 StateManager（保留薄封装：既有调用点与测试直接用它）"""
        self.state.record_trigger_event(now, rule_id, symbol)

    def _get_recent_trigger_count(self, rule_id: int, window_minutes: int = 10) -> int:
        """该规则近 window_minutes 分钟内的触发次数（含本次触达）

        2026-09-14 修正：原实现遍历 _last_triggered 统计「不同条件的最新触发」，
        同一条件多次触发只算 1。实测 45 条启用规则中 36 条只有 1 个条件，而
        policy 的 max_triggers_per_window.count 为 3 —— 该路径恒达不到阈值，
        「触发频率升级」整体失效。
        """
        return self.state.recent_trigger_count(self.now_fn(), rule_id, window_minutes)

    def _get_concurrent_trigger_count(self, symbol: str, rule_id: int,
                                      window_seconds: int = 60) -> int:
        """同标的近 window_seconds 秒内触发过的**不同规则数**（含本次）

        2026-09-14 修正：原实现是占位（恒返回 0，注释自述「实际实现需要查询
        trigger_repo」），导致 escalation_policy.multi_rule_confluence 命中后
        永远等不到 concurrent_trigger_count >= 2，「多规则共振升级」整体失效。
        现从事件日志按 symbol 去重统计 rule_id，并计入本次当前规则。
        """
        return self.state.concurrent_trigger_count(self.now_fn(), symbol, rule_id,
                                                   window_seconds)
