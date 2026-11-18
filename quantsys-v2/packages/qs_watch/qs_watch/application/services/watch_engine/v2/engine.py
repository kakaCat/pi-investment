"""WatchEngineV2 —— 持仓驱动盯盘判定与投递链。

激活规则按 symbol 去重取价，随后执行失效判定、持仓分类和条件求值。定时任务可注入
``TriggerArchive``，形成投递前落台账、投递后回写结果、成功才提交循环计数的闭环。
未注入通知依赖时保持影子判定；生产由 JobRegistry 定时驱动，不启动常驻循环。

规则仓储、行情、名称和持仓查询均由宿主注入，本模块不 import L0 适配层。
"""
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

#: 主循环默认拍间隔（秒）；V1 全局档同口径，规则级 interval 由后续卡细化。
DEFAULT_TICK_INTERVAL_SEC = 5.0


@dataclass
class TickResult:
    """一拍的产出快照（判定模块接入前的骨架形态）。

    ``symbols`` 是**去重后**实际发起取价的集合 —— 单测据此断言
    取价输入集合 == 激活 symbol 集合。
    """

    rules: List[Any]                      # list_by_state('active') 全量（未过滤）
    symbols: List[str] = field(default_factory=list)          # 去重、排序后的取价集合
    quotes: Dict[str, Any] = field(default_factory=dict)      # symbol → quote / None
    #: 判定链产出（invalidation / trigger 两类；影子期只留痕不投递）
    judgments: List[Any] = field(default_factory=list)


class WatchEngineV2:
    """持仓驱动盯盘引擎（V2 骨架）。

    参数：
        rule_repo:      规则仓储，需有 ``list_by_state(state) -> List[rule]``
                        （生产实现 = adapters 侧 WatchRuleRepository）。
        quote_service:  行情服务，需有 ``get_realtime_quote(symbol) -> quote``
                        （生产实现复用 V1 同款 RealtimeQuoteServiceV2）。
        tick_interval_sec: run_forever 主循环拍间隔。
    """

    def __init__(self, rule_repo, quote_service,
                 tick_interval_sec: float = DEFAULT_TICK_INTERVAL_SEC,
                 log=None,
                 judge: bool = True,
                 cycle_store=None,
                 agent_sender=None,
                 feishu_sender=None,
                 account_agent_map=None,
                 name_resolver=None,
                 position_reader=None,
                 evaluation_context=None,
                 staged_manager=None,
                 market_watch_service=None,
                 agent_price_tracker=None):
        from .evaluation_context import EvaluationContextFactory
        from .staged_break_manager import StagedBreakManager

        self._rule_repo = rule_repo
        self._quote_service = quote_service
        self._tick_interval_sec = float(tick_interval_sec)
        self._log = log or logger
        self._stop_event = threading.Event()
        self._judge = judge
        self._cycle_store = cycle_store
        self._agent_sender = agent_sender
        self._agent_price_tracker = (agent_price_tracker if agent_price_tracker is not None
                                     else {})
        self._feishu_sender = feishu_sender
        self._account_agent_map = account_agent_map or {}
        self._name_resolver = name_resolver
        self._position_reader = position_reader
        self._market_watch = market_watch_service
        self._context = evaluation_context or EvaluationContextFactory()
        self._staged = staged_manager or StagedBreakManager()
        self._staged.restore_from_store()
        self._suppressed_reported = set()
        self._suppressed_day = None

    # ── ① 激活规则加载 ────────────────────────────────────────────────────

    def load_active_rules(self) -> List[Any]:
        """加载全部激活规则（t2 验收：激活数 = 库一致）。

        不在此处做任何过滤 —— 持仓状态/到期/失效全是**对比维度**，
        判定阶段才用（需求文档流程图 ①②③）。
        """
        rules = self._rule_repo.list_by_state('active')
        rules = list(rules or [])
        self._attach_stock_names(rules)
        return rules

    def _attach_stock_names(self, rules) -> None:
        """回填公司名称到 rule.stock_name（渲染标题用）。

        规则表只有 symbol；名称来源由注入的 resolver 决定（生产 = stocks 表），
        缺 resolver/查不到时保持空串（标题退化为「(代码)」仍可定位）。
        """
        if self._name_resolver is None or not rules:
            return
        symbols = {r.symbol for r in rules if getattr(r, 'symbol', None)}
        if not symbols:
            return
        try:
            names = self._name_resolver(symbols) or {}
        except Exception:  # noqa: BLE001 - 名称解析失败不影响判定
            self._log.warning('v2.name_resolve_failed')
            return
        for rule in rules:
            name = names.get(getattr(rule, 'symbol', ''))
            if name:
                try:
                    rule.stock_name = name
                except Exception:  # noqa: BLE001 - 只读对象跳过
                    pass

    # ── ② 统一取价前置 ────────────────────────────────────────────────────

    @staticmethod
    def active_symbols(rules: List[Any]) -> List[str]:
        """激活规则的 symbol 集合（去重、排序，确定性输出便于断言/对账）。"""
        return sorted({r.symbol for r in rules if getattr(r, 'symbol', None)})

    def fetch_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """按去重后的 symbol 集合统一取价（t2 验收：取价输入集合 == 激活 symbol 集合）。

        单票取价失败只置 None 并留 warning —— 一拍出问题不拖垮其余 symbol，
        后续 invalidation 的止损豁免等逻辑拿 None 走 fail-open。
        """
        quotes: Dict[str, Any] = {}
        for symbol in symbols:
            try:
                quotes[symbol] = self._quote_service.get_realtime_quote(symbol)
            except Exception as exc:  # noqa: BLE001 - 行情源单票故障不拖垮整拍
                self._log.warning('v2.quote_failed', symbol=symbol, error=str(exc))
                quotes[symbol] = None
        return quotes

    # ── 一拍 ───────────────────────────────────────────────────────────────

    def tick(self) -> TickResult:
        """一拍：加载 → 统一取价（前置）→ 失效扫描 → 分类判定 → 路由投递。"""
        rules = self.load_active_rules()
        symbols = self.active_symbols(rules)
        quotes = self.fetch_quotes(symbols)
        result = TickResult(rules=rules, symbols=symbols, quotes=quotes)
        # 影子期只留痕：每拍一条结构化日志（backend.md 可观测性口径）
        self._log.info('v2.tick', active_rules=len(rules), symbols=len(symbols))
        # 判定链（t3~t8 模块接入；未注入 sender 时只判定不投递 = 影子）
        if self._judge:
            try:
                result.judgments = self._run_chain(rules, quotes)
            except Exception:  # noqa: BLE001 - 判定链异常不杀主循环
                self._log.exception('v2.chain_failed')
        return result

    # ── 判定链（失效 → 分类 → 判定 → 路由 → 投递）──────────────────────────

    def run_chain(self, rules, quotes, archive=None, now=None, assessments=None):
        """公开入口：定时任务可注入归档器、判定时刻和评估指标集合。"""
        return self._run_chain(rules, quotes, archive=archive, now=now,
                               assessments=assessments)

    def _run_chain(self, rules, quotes, archive=None, now=None, assessments=None) -> List[Any]:
        """失效 → 分类判定 → 投递前归档 → 路由投递 → 回写并提交计数。"""
        from . import invalidation, position_engine, router, unpositioned_engine

        now = now or datetime.now()
        if self._suppressed_day != now.date():
            self._suppressed_reported.clear()
            self._suppressed_day = now.date()
        self._staged.reset_daily(now)
        self._context.prepare(quotes, now)
        self._attach_stock_names(rules)
        outcomes: List[Any] = []
        for rule in rules:
            symbol = getattr(rule, 'symbol', None)
            quote = quotes.get(symbol)
            if quote is None:
                continue
            try:
                from types import SimpleNamespace
                from qs_watch.domain.watch.services import noise_policy
                rule_id = getattr(rule, 'id', None)
                if noise_policy.is_suppressed(
                        getattr(rule, 'noise_state', None),
                        getattr(rule, 'suppress_until', None), now):
                    if archive is not None:
                        archive.evaluated(rule, quote)
                    if rule_id not in self._suppressed_reported:
                        judgment = SimpleNamespace(
                            intent=str(getattr(rule, 'intent', '') or ''),
                            triggered=False,
                            suppressed_conditions=[{
                                'condition': cond,
                                'value': getattr(quote, 'price', None),
                                'message': '规则处于抑噪期，仅留样本不通知',
                            } for cond in (getattr(rule, 'conditions', None) or [])],
                            suppressed_kind='noise_suppressed',
                            degraded=False,
                            distance_ratio=None,
                        )
                        if assessments is not None:
                            assessments[rule_id] = judgment
                        if archive is not None and archive.record_suppressed(rule, judgment):
                            self._suppressed_reported.add(rule_id)
                    continue
                position = self._read_position(rule)
                state = self._position_state(rule, position)
                event = invalidation.check_invalidation(rule, quote)
                if event is not None:
                    delivery = self._handle_invalidation(rule, event, quote, state)
                    outcomes.append(('invalidation', rule, event, delivery))
                    continue

                ctx = self._context.build(rule, quote, now)
                from .rule_policy import position_intent
                if state == 'holding' or position_intent(getattr(rule, 'intent', None)):
                    judgment = position_engine.evaluate(
                        rule, quote, position=state or None, now=now, ctx=ctx,
                        staged_manager=self._staged)
                else:
                    judgment = unpositioned_engine.evaluate(
                        rule, quote, now=now, ctx=ctx, staged_manager=self._staged)
                if assessments is not None:
                    assessments[getattr(rule, 'id', None)] = judgment
                if archive is not None:
                    archive.evaluated(rule, quote)
                    archive.record_suppressed(rule, judgment)
                if not getattr(judgment, 'triggered', False):
                    continue

                self._enrich_judgment(rule, judgment, quote, state, position)
                if archive is not None and not archive.before_delivery(rule, judgment):
                    outcomes.append(('trigger', rule, judgment, None, None))
                    continue
                if (getattr(judgment, 'observe_only', False)
                        and str(getattr(rule, 'trigger_channel', 'agent') or 'agent') != 'direct'):
                    outcomes.append(('trigger', rule, judgment, None, None))
                    continue

                route = self._route(rule, judgment)
                delivery = self._deliver(rule, judgment, state, route, quote)
                if archive is not None:
                    archive.after_delivery(judgment, delivery)
                if self._route_completed(rule, route, delivery):
                    router.commit_route(rule, self._cycle_store, route)
                outcomes.append(('trigger', rule, judgment, route, delivery))
            except Exception:  # noqa: BLE001 - 单条规则异常不影响其余
                self._log.exception('v2.rule_chain_failed',
                                    rule_id=getattr(rule, 'id', None))
        return outcomes

    def run_market_chain(self, archive=None, now=None):
        """市场快照评估后复用 V2 归档与投递，不走股票条件管线。"""
        from types import SimpleNamespace
        from . import router

        now = now or datetime.now()
        empty = {'outcomes': [], 'scanned': 0, 'triggered': 0, 'degraded': []}
        if self._market_watch is None:
            return empty
        scan = self._market_watch.scan_market_rules(now)
        outcomes = []
        for candidate in scan.get('evaluated') or []:
            rule = candidate['rule']
            result = candidate['result']
            quote = candidate['quote']
            triggered = bool(getattr(result, 'triggered', False))
            judgment = SimpleNamespace(
                intent=str(getattr(rule, 'intent', '') or 'trend_observe'),
                triggered=triggered,
                hit_conditions=([{
                    'condition': candidate['cond'],
                    'value': getattr(result, 'value', None),
                    'message': getattr(result, 'message', ''),
                }] if triggered else []),
                suppressed_conditions=[],
                degraded=False,
                observe_only=False,
            )
            if archive is not None:
                archive.evaluated(rule, quote)
            if not triggered:
                continue
            if archive is not None and not archive.before_delivery(rule, judgment):
                outcomes.append(('trigger', rule, judgment, None, None))
                continue
            state = str(getattr(rule, 'position_state', '') or '').lower()
            route = self._route(rule, judgment)
            delivery = self._deliver(rule, judgment, state, route, quote)
            if archive is not None:
                archive.after_delivery(judgment, delivery)
            if self._route_completed(rule, route, delivery):
                router.commit_route(rule, self._cycle_store, route)
            outcomes.append(('trigger', rule, judgment, route, delivery))
        return {
            'outcomes': outcomes,
            'scanned': int(scan.get('scanned') or 0),
            'triggered': int(scan.get('triggered') or 0),
            'degraded': list(scan.get('degraded') or []),
            'skipped': scan.get('skipped'),
        }

    def staged_pending(self) -> int:
        return self._staged.pending()

    def flush_state(self) -> None:
        self._staged.flush()

    def _read_position(self, rule):
        if self._position_reader is None:
            return None
        try:
            return self._position_reader(
                getattr(rule, 'account', None), getattr(rule, 'symbol', None))
        except Exception as exc:  # noqa: BLE001 - 查询失败回落规则状态，止损仍 fail-open
            self._log.warning('v2.position_read_failed',
                              rule_id=getattr(rule, 'id', None), error=str(exc))
            return None

    @staticmethod
    def _position_state(rule, position) -> str:
        if position is not None:
            shares = getattr(position, 'shares_total', None)
            if shares is not None:
                return 'holding' if int(shares) > 0 else 'none'
        return str(getattr(rule, 'position_state', '') or '').lower()

    def _enrich_judgment(self, rule, judgment, quote, state, position=None) -> None:
        try:
            price = float(getattr(quote, 'price', None))
            raw_cost = ((getattr(position, 'avg_cost', None) or getattr(rule, 'cost_price', None))
                        if position is not None else getattr(rule, 'cost_price', None))
            cost = float(raw_cost)
            if price > 0 and cost > 0:
                judgment.pnl_pct = round((price - cost) / cost * 100.0, 2)
        except (TypeError, ValueError):
            pass
        if position is not None:
            judgment.sellable = getattr(position, 'shares_available', None)

    @staticmethod
    def _route_completed(rule, route, delivery) -> bool:
        from . import router
        if route is None or str(getattr(rule, 'trigger_channel', 'agent')) == 'direct':
            return False
        if route.route == router.ROUTE_SKIP:
            return True
        return bool(getattr(delivery, 'delivered', False))

    def _handle_invalidation(self, rule, event, quote, state):
        """失效闭环：规则标 invalid + 投递对应 agent 裁决（改阈值回 active / 退役）。

        幂等：标 invalid 后规则退出 active 集合，下一拍不再进判定链，天然不重复投递。
        落库失败则只记日志、不投递（避免"通知了但规则还在盯"的双重事实）。
        """
        rule_id = getattr(rule, 'id', None)
        try:
            self._rule_repo.update_fields(
                rule_id,
                rule_state='invalid',
                invalid_reason=event.reason,
                invalid_at=event.at or datetime.now(),
            )
        except Exception:  # noqa: BLE001 - 单条失效落库失败不阻断其余规则
            self._log.exception('v2.invalidation_persist_failed', rule_id=rule_id)
            return None

        from types import SimpleNamespace

        from . import notify_agent

        judgment = SimpleNamespace(
            intent='invalidation',
            triggered=True,
            hit_conditions=[{'message': event.reason}],
            quote=quote,
        )
        position_state = state if state in ('holding', 'none') else None
        delivery = notify_agent.send(
            rule, judgment, position_state,
            sender=self._agent_sender,
            account_agent_map=self._account_agent_map,
            price_tracker=self._agent_price_tracker,
            use_price_gate=False,  # 失效裁决必达，但仍更新“上次成功发 agent”价格
        )
        self._log.info(
            'v2.rule_invalidated', rule_id=rule_id,
            deviation_pct=event.deviation_pct,
            delivered=bool(getattr(delivery, 'delivered', False)),
        )
        return delivery

    def _route(self, rule, judgment):
        from . import router
        archive_driven = hasattr(judgment, '_v2_delivery_allowed')
        if archive_driven and not judgment._v2_delivery_allowed:
            self._log.info(
                'v2.delivery_blocked',
                rule_id=getattr(rule, 'id', None),
                reasons=getattr(judgment, '_v2_delivery_block_reasons', []),
            )
            return None
        channel = str(getattr(rule, 'trigger_channel', 'agent') or 'agent')
        if archive_driven:
            # 同一 trigger 由事件状态驱动，不再进入 10-cycle 重投：
            # 首次/失败重试走固定通道；成功或终态在上一段直接硬停。
            if channel == 'direct':
                return router.RouteDecision(router.ROUTE_DIRECT, 0, 'event_pending')
            if self._cycle_store is None:
                return None
            return router.RouteDecision(router.ROUTE_AGENT, 1, 'event_pending')
        if channel == 'direct':
            if getattr(judgment, '_v2_new_trigger', True):
                return router.RouteDecision(router.ROUTE_DIRECT, 0, 'direct_channel')
            return router.RouteDecision(router.ROUTE_SKIP, 0, 'direct_edge_latched')
        if self._cycle_store is None:
            return None
        return router.route_trigger(rule, self._cycle_store, commit=False)

    def _deliver(self, rule, judgment, state, route, quote):
        """按路由决策投递；归档模式的事件由 archive 在路由前完成去重。"""
        from . import notify_agent, notify_feishu, router

        judgment.quote = quote  # 供提示词/模板渲染
        state = state if state in ('holding', 'none') else None

        if route is None:
            return None  # 影子
        if route.route == router.ROUTE_SKIP:
            return None
        if route.route == router.ROUTE_AGENT:
            return notify_agent.send(
                rule, judgment, state,
                sender=self._agent_sender,
                account_agent_map=self._account_agent_map,
                price_tracker=self._agent_price_tracker,
                # archive 已按 trigger 去重；新 rearm 边沿不能被上一事件的
                # 1% 价格门槛误杀。该门槛仅保留给无台账兼容路径。
                use_price_gate=not hasattr(judgment, '_v2_delivery_allowed'),
            )
        if route.route == router.ROUTE_DIRECT:
            return notify_feishu.send(
                rule, judgment, state,
                entry=notify_feishu.ENTRY_DIRECT,
                sender=self._feishu_sender,
            )
        return None

    # ── 常驻主循环 ─────────────────────────────────────────────────────────

    def stop(self) -> None:
        """请求退出 run_forever 循环，并保存状态、回收取数资源。"""
        self._stop_event.set()
        self._staged.flush()
        self._context.shutdown()

    def run_forever(self) -> None:
        """常驻循环：tick → 按拍间隔等待 → 下一拍；异常逐拍隔离不退出线程。"""
        self._log.info('v2.engine_started', interval_sec=self._tick_interval_sec)
        while not self._stop_event.is_set():
            started = time.monotonic()
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - 单拍失败不杀线程
                self._log.exception('v2.tick_failed')
            elapsed = time.monotonic() - started
            wait_sec = max(self._tick_interval_sec - elapsed, 0.0)
            self._stop_event.wait(wait_sec)
        self._log.info('v2.engine_stopped')


def create_engine_v2(rule_repo, quote_service,
                     tick_interval_sec: Optional[float] = None,
                     log=None, **chain_deps) -> WatchEngineV2:
    """装配入口（watch_bootstrap V2 启动分支用，backend.md IF-1）。

    只做参数转发，不 import 任何 L0 实现 —— 实现选择留在调用方。
    chain_deps: judge / cycle_store / agent_sender / feishu_sender / account_agent_map
                / agent_price_tracker
    """
    kwargs: Dict[str, Any] = dict(chain_deps)
    if tick_interval_sec is not None:
        kwargs['tick_interval_sec'] = tick_interval_sec
    if log is not None:
        kwargs['log'] = log
    return WatchEngineV2(rule_repo=rule_repo, quote_service=quote_service, **kwargs)
