"""WatchEngine 盯盘引擎核心

tick() 为一次完整判定（同步、可单测）；run_forever() 为常驻循环。
仅交易日（周一至周五）9:30-11:30 / 13:00-15:00 运行。
"""
import time as time_module
from datetime import datetime, time, timedelta
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

from application.services.watch_engine.conditions import (
    DEFAULT_COOLDOWN_SEC, EvalContext, evaluate,
)
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

        # 均量取数保护（2026-09-11，w-aebfddcd）：外部 K 线降级链离线时单 tick 实测 127s，
        # tick 本该 60s 一次被拖成两分钟一次。策略：按日缓存 + 硬超时 + 失败熔断。
        self._avg_volume_cache: Dict[str, float] = {}
        self._avg_volume_fail: Dict[str, datetime] = {}
        self._avg_volume_inflight: Dict[str, Any] = {}
        self._avg_volume_cache_date = None
        self._avg_volume_timeout_sec = float(os.getenv('WATCH_AVG_VOLUME_TIMEOUT_SEC', '1.0'))
        self._avg_volume_fail_ttl_sec = float(os.getenv('WATCH_AVG_VOLUME_FAIL_TTL_SEC', '600'))
        self._avg_volume_breaker_n = int(os.getenv('WATCH_AVG_VOLUME_BREAKER_N', '3'))
        self._avg_volume_consec_fail = 0
        self._avg_volume_blocked_until: Optional[datetime] = None
        self._avg_volume_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='avgvol')
        self._history: Dict[str, List[Tuple[datetime, float]]] = {}
        self._last_triggered: Dict[Tuple[int, int], datetime] = {}
        self._latched: set = set()
        # 去重窗（REQ-f08def）：key=(归一化标的,方向) -> (最近一次触发时间, 触发记录 id)
        # 同标的同向在该窗内只通知一次，重复的仍落库（disposition='deduped' + dup_of）
        # key -> (最近触发时间, 触发记录 id, 规则 id)。带 rule_id 才能分辨
        # 同一条规则多条件重复（物理去重，保留）与跨规则重叠（业务问题，转治理）
        self._recent_notified: Dict[Tuple[str, str], Tuple[datetime, int, int]] = {}
        self._overlap_reported: set = set()
        self.dedup_window_sec = DEDUP_WINDOW_SEC
        # 介入判据（REQ-f08def P3，RFC 014 v3 §3）：金额门/增量门/经济门/预算门所需的注入
        self._position_value_provider = position_value_provider
        self._account_total_provider = account_total_provider
        self._intervention_cfg = InterventionConfig()
        # 增量门（同标的同议题 4h 冷却）：key=(归一化标的,意图) -> 最近介入时间
        self._last_intervention: Dict[Tuple[str, str], datetime] = {}
        self._interventions_today: int = 0
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
        self._avg_volume_cache: Dict[str, float] = {}
        self._state_date = None
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
                self._interventions_today = self.ledger.count_today()
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
                if not result.triggered:
                    # 条件回到未触发状态 → 解除闩锁，重新武装（允许下次穿越再报）
                    self._latched.discard((rule.id, idx))
                    continue
                if (rule.id, idx) in self._latched:
                    # 条件持续成立（电平保持）→ 不重复推送，等重新武装
                    continue
                if self._in_cooldown(rule.id, idx, cond, now):
                    continue
                
                # 升级检查：L0/L1 触发满足条件时自动升级为 L2
                escalation_reason = None
                trigger_level = self._get_trigger_level(rule)
                
                if trigger_level in ('L0', 'L1'):
                    # 查询触发频率和并发触发数
                    recent_count = self._get_recent_trigger_count(rule.id, cond)
                    concurrent_count = self._get_concurrent_trigger_count(rule.symbol, now)
                    
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
                    gate=gate_ctx, cfg=self._intervention_cfg)
                dup_of = None
                prev = self._recent_notified.get(key)
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
                        if pair not in self._overlap_reported:
                            self._overlap_reported.add(pair)
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
                    self._recent_notified[key] = (
                        now, getattr(trigger, 'id', 0) or 0, int(getattr(rule, 'id', 0) or 0))
                if disposition == 'escalated':
                    # 增量门 + 预算记账：escalated = 进 agent 摘要队列 = 一次潜在介入
                    norm = normalize_symbol(rule.symbol)
                    intent = str(getattr(rule, 'intent', '') or '') or                         str((rule.action_hint or {}).get('action_on_trigger', '') if isinstance(getattr(rule, 'action_hint', None), dict) else '')
                    self._last_intervention[(norm, intent or 'unknown')] = now
                    self._interventions_today += 1
                    if self.ledger is not None:
                        self.ledger.record(
                            symbol=rule.symbol, intent=(intent or None), rule_id=rule.id,
                            trigger_kind='price', outcome='escalated',
                            trigger_ids=[getattr(trigger, 'id', None)],
                        )
                self._last_triggered[(rule.id, idx)] = now
                self._latched.add((rule.id, idx))
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

        # 去重窗裁剪：清掉已过期的键，避免长跑进程内的无界增长
        if self._recent_notified:
            cutoff = now.timestamp() - self.dedup_window_sec
            self._recent_notified = {
                k: v for k, v in self._recent_notified.items() if v[0].timestamp() >= cutoff
            }

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
            total = self._account_total()
            if mpp and total:
                amount = float(mpp) / 100.0 * float(total)
                ev = amount * 0.03
        return GateContext(
            intent=intent or None,
            amount_yuan=amount,
            last_intervention_at=self._last_intervention.get((norm, topic)),
            expected_value_yuan=ev,
            trigger_kind='price',
            daily_wake_count=self._interventions_today,
            change_pct=getattr(quote, 'change_pct', None),
        )

    def _position_value(self, rule) -> Optional[float]:
        if self._position_value_provider is None:
            return None
        try:
            return self._position_value_provider(rule)
        except Exception:
            return None

    def _account_total(self) -> Optional[float]:
        if self._account_total_provider is None:
            return None
        try:
            return self._account_total_provider()
        except Exception:
            return None

    def _reset_daily_state_if_needed(self, now: datetime):
        """跨天重置：均量缓存过期 + 清理已删除规则的残留状态"""
        current_date = now.date()
        if self._state_date == current_date:
            return
        self._state_date = current_date
        self._avg_volume_cache.clear()
        # 跨天全量重新武装：新的一天允许持续成立的条件再报一次（每日最多一次）
        self._latched.clear()
        self._recent_notified.clear()
        self._overlap_reported.clear()
        self._last_intervention.clear()
        self._interventions_today = 0
        active_ids = {r.id for r in self.rule_repo.list_enabled()}
        self._last_triggered = {k: v for k, v in self._last_triggered.items()
                                if k[0] in active_ids}
        active_symbols = {r.symbol for r in self.rule_repo.list_enabled()}
        self._history = {s: buf for s, buf in self._history.items()
                         if s in active_symbols}

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
            price_history=tuple(self._history.get(rule.symbol, ())),
            avg_volume_20d=self._get_avg_volume(rule.symbol),
            elapsed_fraction=elapsed_trading_fraction(now),
        )

    def _push_history(self, symbol: str, ts: datetime, price: float):
        buf = self._history.setdefault(symbol, [])
        buf.append((ts, price))
        cutoff = ts - timedelta(minutes=self.history_minutes)
        self._history[symbol] = [(t, p) for t, p in buf if t >= cutoff]

    def _get_avg_volume(self, symbol: str) -> Optional[float]:
        """20 日均量（供 volume_surge 类条件）：按日缓存 + 硬超时 + 失败熔断

        2026-09-11（w-aebfddcd）：该值走外部 K 线供应商降级链（baostock 60s 超时 → 腾讯 →
        akshare），供应商离线时单次 tick 实测 127 秒，把 60 秒的 tick 拖成两分钟，
        快档 10 秒形同虚设 —— 盯盘时效被外部源绑架。
        现在：取不到就**快速放弃**（按"无均量"处理，相关条件当次跳过），绝不拖住 tick；
        连续失败达阈值则整体熔断一段时间，避免每个标的都去撞同一堵墙。
        """
        if self.avg_volume_provider is None:
            return None
        now = self.now_fn()
        if self._avg_volume_cache_date != now.date():
            self._avg_volume_cache.clear()
            self._avg_volume_fail.clear()
            self._avg_volume_cache_date = now.date()
        if self._avg_volume_blocked_until is not None and now < self._avg_volume_blocked_until:
            return None
        if symbol in self._avg_volume_cache:
            return self._avg_volume_cache[symbol]
        failed_at = self._avg_volume_fail.get(symbol)
        if failed_at is not None and (now - failed_at).total_seconds() < self._avg_volume_fail_ttl_sec:
            return None
        fut = self._avg_volume_inflight.get(symbol)
        if fut is None:
            fut = self._avg_volume_pool.submit(self.avg_volume_provider, symbol)
            self._avg_volume_inflight[symbol] = fut
        try:
            value = fut.result(timeout=self._avg_volume_timeout_sec)
        except FuturesTimeout:
            # 在途 future 保留：完成后再回收（下次命中即取到值），不每 tick 重新发起
            self._note_avg_volume_failure(symbol, now, '超时 %.1fs' % self._avg_volume_timeout_sec)
            return None
        except Exception as e:  # noqa: BLE001 - 任何取数异常都不该影响 tick
            self._avg_volume_inflight.pop(symbol, None)
            self._note_avg_volume_failure(symbol, now, str(e))
            return None
        self._avg_volume_inflight.pop(symbol, None)
        if value:
            self._avg_volume_cache[symbol] = float(value)
            self._avg_volume_consec_fail = 0
            return self._avg_volume_cache[symbol]
        self._note_avg_volume_failure(symbol, now, '空值')
        return None

    def _note_avg_volume_failure(self, symbol: str, now: datetime, why: str) -> None:
        self._avg_volume_fail[symbol] = now
        self._avg_volume_consec_fail += 1
        if self._avg_volume_consec_fail >= self._avg_volume_breaker_n:
            self._avg_volume_blocked_until = now + timedelta(seconds=self._avg_volume_fail_ttl_sec)
            logger.warning('均量取数连续失败，熔断 %ds（期内按无均量处理）',
                           symbol=symbol, reason=why, ttl=self._avg_volume_fail_ttl_sec)
        else:
            logger.warning('均量取数失败（按无均量处理）', symbol=symbol, reason=why)

    def _in_cooldown(self, rule_id: int, cond_idx: int, cond: dict, now: datetime) -> bool:
        last = self._last_triggered.get((rule_id, cond_idx))
        if last is None:
            return False
        cooldown = cond.get('cooldown_sec', DEFAULT_COOLDOWN_SEC)
        return (now - last).total_seconds() < cooldown

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

    def _get_recent_trigger_count(self, rule_id: int, cond: dict) -> int:
        """获取规则近 10 分钟内的触发次数"""
        # 从 _last_triggered 中统计
        count = 0
        window = timedelta(minutes=10)
        now = self.now_fn()
        for (rid, idx), ts in self._last_triggered.items():
            if rid == rule_id and (now - ts) < window:
                count += 1
        return count

    def _get_concurrent_trigger_count(self, symbol: str, now: datetime) -> int:
        """获取同 symbol 近 60 秒内的并发触发规则数"""
        count = 0
        window = timedelta(seconds=60)
        # 从 _last_triggered 中统计（需要知道 symbol，但 _last_triggered 只存 rule_id）
        # 简化：从 events 中统计或从 trigger_repo 查询
        # 这里简化实现：返回 0（实际实现需要查询 trigger_repo）
        return count
