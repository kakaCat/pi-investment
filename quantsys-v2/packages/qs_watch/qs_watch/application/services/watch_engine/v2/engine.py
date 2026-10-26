"""WatchEngineV2 —— 持仓驱动盯盘引擎骨架（REQ-261022235419-2299 / t-b8ffa6）

本骨架只保证两件事（decomposition.md t2）：

1. **加载**：tick 内 ``rule_repo.list_by_state('active')`` 取全部激活规则；
2. **统一取价前置**：激活规则按 symbol 去重后**一次性**取价 ——
   取价输入集合 == 激活 symbol 集合（不过滤、不遗漏，失效/到期/持仓都是
   对比维度而不是取价前置过滤条件）。

判定模块（position_engine / unpositioned_engine / invalidation / router /
notify_*）在 t3~t8 接入本 tick 的取价结果；影子期只留日志不投递。

宿主契约与 V1 一致（backend.md IF-1）：lifespan 起独立后台线程，
``run_forever()`` 常驻、``stop()`` 优雅退出。

依赖注入说明：``qs_watch`` 是 L1 包，不 import L0 适配层 —— 规则仓储与
行情服务均由调用方（watch_bootstrap V2 启动分支）注入，本模块只依赖
它们的接口形状（``list_by_state(state)`` / ``get_realtime_quote(symbol)``）。
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
                 name_resolver=None):
        self._rule_repo = rule_repo
        self._quote_service = quote_service
        self._tick_interval_sec = float(tick_interval_sec)
        self._log = log or logger
        self._stop_event = threading.Event()
        # ── 判定链依赖（全部可选；缺省 = 影子判定，不投递）────────────────
        self._judge = judge                    # False = 只要取价骨架
        self._cycle_store = cycle_store        # router 的计数存储（缺省不路由）
        self._agent_sender = agent_sender      # (agent, account, prompt) -> bool
        self._feishu_sender = feishu_sender    # (title, body) -> bool
        self._account_agent_map = account_agent_map or {}
        #: 公司名称解析（symbol -> name）；规则表不存名称，渲染前回填到 rule.stock_name
        self._name_resolver = name_resolver

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

    def run_chain(self, rules, quotes):
        """公开入口：定时任务（scheduled.py）调用的唯一业务入口。

        与 run_forever 的 tick 共用同一条 `_run_chain`，不复制判定/路由逻辑；
        差异只在"谁驱动"——常驻循环不再启动，改由 4 个定时任务按档位驱动。
        """
        return self._run_chain(rules, quotes)

    def _run_chain(self, rules, quotes) -> List[Any]:
        """对全部激活规则跑一遍判定链，返回判定结果列表。

        顺序严格按 architecture.md 主流程：
        ① 失效扫描（全票，独立于持仓与触发，止损豁免）
        ② 持仓分类（holding → position_engine；none → unpositioned_engine）
        ③ 命中 → 路由（10 次循环）→ 投递（notify_agent / notify_feishu）

        任何一环的单条失败都只影响该条规则（异常隔离）。
        """
        from . import invalidation, position_engine, unpositioned_engine

        outcomes: List[Any] = []
        for rule in rules:
            symbol = getattr(rule, 'symbol', None)
            quote = quotes.get(symbol)
            if quote is None:
                continue  # 本拍无价：失明但不是故障（下拍重试）
            try:
                state = str(getattr(rule, 'position_state', '') or '').lower()

                # ① 失效判定（覆盖全票；止损豁免）
                event = invalidation.check_invalidation(rule, quote)
                if event is not None:
                    # 2026-10-24：失效闭环——标 invalid（退出 active）+ 投递 agent 裁决。
                    # 此前只返回事件，规则永远僵在 active，等于没有作废能力。
                    delivery = self._handle_invalidation(rule, event, quote, state)
                    outcomes.append(('invalidation', rule, event, delivery))
                    continue  # 已作废，不再判定触发

                # ② 持仓分类判定
                if state == 'holding':
                    judgment = position_engine.evaluate(rule, quote, position='holding')
                elif state == 'none':
                    judgment = unpositioned_engine.evaluate(rule, quote)
                else:
                    # 持仓真值不可知：止损 fail-open 交给 position_engine（它会留痕）
                    judgment = position_engine.evaluate(rule, quote)

                if not getattr(judgment, 'triggered', False):
                    continue

                # 观察类只留痕不投递（R-5：观察不产生交易动作，也不该唤醒 agent）。
                # 仍返回 trigger outcome → scheduled._archive 落 watch_triggers 供复盘。
                if getattr(judgment, 'observe_only', False):
                    outcomes.append(('trigger', rule, judgment, None, None))
                    continue

                # ③ 路由 + 投递
                route = self._route(rule)
                delivery = self._deliver(rule, judgment, state, route, quote)
                outcomes.append(('trigger', rule, judgment, route, delivery))
            except Exception:  # noqa: BLE001 - 单条规则异常不影响其余
                self._log.exception('v2.rule_chain_failed',
                                    rule_id=getattr(rule, 'id', None))
        return outcomes

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
        )
        self._log.info(
            'v2.rule_invalidated', rule_id=rule_id,
            deviation_pct=event.deviation_pct,
            delivered=bool(getattr(delivery, 'delivered', False)),
        )
        return delivery

    def _route(self, rule):
        from . import router
        if self._cycle_store is None:
            return None  # 无 store：影子期不路由（只判定）
        return router.route_trigger(rule, self._cycle_store)

    def _deliver(self, rule, judgment, state, route, quote):
        """按路由决策投递：agent 首发 → notify_agent；第 10 次 → notify_feishu 直通。"""
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
        """请求退出 run_forever 循环（lifespan 优雅停止句柄用）。"""
        self._stop_event.set()

    def run_forever(self) -> None:
        """常驻循环：tick → 按拍间隔等待 → 下一拍；异常逐拍隔离不退出线程。"""
        self._log.info('v2.engine_started', interval_sec=self._tick_interval_sec)
        while not self._stop_event.is_set():
            started = time.monotonic()
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - 单拍失败不杀线程（探活靠心跳兜底）
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
    """
    kwargs: Dict[str, Any] = dict(chain_deps)
    if tick_interval_sec is not None:
        kwargs['tick_interval_sec'] = tick_interval_sec
    if log is not None:
        kwargs['log'] = log
    return WatchEngineV2(rule_repo=rule_repo, quote_service=quote_service, **kwargs)
