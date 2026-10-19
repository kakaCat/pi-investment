"""WatchEngine 装配：构建引擎 + 后台线程启动"""
import os
import threading
from datetime import datetime, timedelta
from typing import Optional
from qs_kernel.domain.ports.datasource_ports import IDataProviderManager

import structlog

from qs_market_data.adapters.outbound.datasources.manager import get_data_provider_manager
from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository
)
from qs_agenthub.application.services.agent_notification_service import AgentNotificationService  # 2026-10-19：L1 → qs_agenthub 真身
from qs_market_data.application.services.realtime_quote_service_v2 import RealtimeQuoteServiceV2
from qs_watch.application.services.watch_engine.engine import WatchEngine
from qs_watch.application.services.watch_engine.notifier import WatchNotifier
from qs_watch.application.services.watch_engine.digest_service import WatchDigestService
from qs_watch.application.services.watch_engine.intervention_ledger import InterventionLedger
from adapters.outbound.repositories.watch_state_repository import (
    WatchDigestStateRepository, WatchInterventionRepository,
)
from qs_watch.application.services.watch_engine.meta_review_service import WatchMetaReviewService
from qs_watch.application.services.watch_engine.position_lifecycle_service import PositionLifecycleService
from qs_watch.application.services.watch_engine.market_watch_service import MarketWatchService
from qs_watch.application.services.watch_engine.held_sector_map import HeldSectorMapService
from qs_watch.application.services.watch_engine.outcome_backfill_service import OutcomeBackfillService
from adapters.outbound.repositories.watch_outcome_repository import WatchOutcomeRepository
from qs_market_data.adapters.outbound.datasources.market_state_provider import MarketStateProvider
from adapters.outbound.repositories.simulation_position_repository import SimulationPositionRepository
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

logger = structlog.get_logger(__name__)


def make_avg_volume_provider():
    """近 20 日日均成交量 provider。失败返回 None（volume_surge 降级不判定）"""
    def provider(symbol: str) -> Optional[float]:
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')
        # 归一化为裸代码：akshare 只接受 6 位代码，DB miss 时 fallback 会失败
        bare_symbol = symbol.split('.')[0]
        result: IDataProviderManager = get_data_provider_manager().get_klines(bare_symbol, 'daily', start, end)
        if not result.get('success'):
            logger.warning('均量获取失败，volume_surge 降级', symbol=symbol)
            return None
        # data 为 List[KlineData] dataclass（非 dict），用属性访问；兼容 dict 兜底
        volumes = []
        for k in result['data'][-20:]:
            v = k.get('volume') if isinstance(k, dict) else getattr(k, 'volume', None)
            if v:
                volumes.append(v)
        if not volumes:
            logger.warning('均量获取失败，volume_surge 降级', symbol=symbol, reason='empty_volumes')
            return None
        return sum(volumes) / len(volumes)
    return provider


def build_watch_loop_services():
    """按开关装配闭环服务（REQ-c9f899 t12 §6-项8）——**可单测的纯装配决策**。

    返回 (runtime_store, todo_service, receipt_service, sla_job, self_heal_service)。
    默认全关（WATCH_TODO_ENABLED=false / WATCH_SELF_HEAL_ENABLED=false /
    WATCH_RUNTIME_PERSIST_ENABLED=false）→ 全 None，引擎行为与改造前**一致**。
    与进程外定时任务共用同一份 watch_loop_wiring 装配函数，避免两条真相。
    任一装配异常都降级（回旧路径/内存态）并记日志，绝不阻断引擎启动。
    """
    from qs_watch.application.services.watch_engine import watch_loop_wiring as _wiring

    runtime_store = None
    if _wiring.watch_runtime_persist_enabled():
        try:
            runtime_store = _wiring.build_runtime_store()
            logger.info('运行态持久化已显式装配（WATCH_RUNTIME_PERSIST_ENABLED=true）')
        except Exception as e:  # noqa: BLE001 - 装配失败降级为内存态，不阻断启动
            logger.error('运行态持久化装配失败，降级为内存态（冷却重启会丢）', error=str(e))
            runtime_store = None

    todo_service = receipt_service = sla_job = self_heal_service = None
    if _wiring.watch_todo_enabled():
        try:
            todo_service = _wiring.build_todo_service()
            receipt_service = _wiring.build_receipt_service()
            sla_job = _wiring.build_sla_job(receipt_service=receipt_service)
            logger.info('盯盘闭环已装配（WATCH_TODO_ENABLED=true）')
        except Exception as e:  # noqa: BLE001 - 装配失败回旧路径（不建待办），不阻断启动
            logger.error('盯盘闭环装配失败，降级为旧路径（不建待办）', error=str(e))
            todo_service = receipt_service = sla_job = None
        if todo_service is not None and _wiring.watch_self_heal_enabled():
            try:
                self_heal_service = _wiring.build_self_heal_service(todo_service)
                logger.info('规则自愈已装配（WATCH_SELF_HEAL_ENABLED=true）')
            except Exception as e:  # noqa: BLE001
                logger.error('规则自愈装配失败（抑噪/修复不可用）', error=str(e))
                self_heal_service = None

    return runtime_store, todo_service, receipt_service, sla_job, self_heal_service


def create_watch_engine() -> WatchEngine:
    _pos_repo = SimulationPositionRepository()
    _sim_repo = SimulationORMRepository()   # 复用单例：原实现在闭包内每次调用新建（每 tick 每规则一次）

    def position_value_provider(rule):
        # 介入判据金额门：持仓级动作影响金额 = 该标的持仓市值
        # 2026-09-13（w-c8cae280，独立审阅 M4）：无归属账户的规则不再借用 agent_virtual 的持仓
        # —— 那会让『通用观察』规则按别人的持仓市值过金额门；无账户即跳过该门（返回 None）。
        account = getattr(rule, 'account', None)
        if not account:
            return None
        symbol = str(getattr(rule, 'symbol', '')).split('.')[0]
        try:
            pos = _pos_repo.get_position(account, symbol)
            if pos is None:
                return None
            return float(getattr(pos, 'market_value', 0) or 0)
        except Exception:
            return None

    def account_total_provider(rule=None):
        # 介入判据金额门：账户总资产
        # 2026-09-13（w-c8cae280，独立审阅 M4）：原实现恒用 agent_virtual 的总资产当所有规则的门槛。
        # 现优先用规则归属账户；无归属时用 agent-dh 自有账户（可用 WATCH_ENGINE_DEFAULT_ACCOUNT 覆盖）。
        account = (getattr(rule, 'account', None) if rule is not None else None) \
            or os.getenv('WATCH_ENGINE_DEFAULT_ACCOUNT', 'agent_brain')
        try:
            status = _sim_repo.get_account_status(account)
            if isinstance(status, dict):
                return float(status.get('total_value') or 0) or None
            return float(getattr(status, 'total_value', 0) or 0) or None
        except Exception:
            return None

    # 通知器：金额门取数复用**同一个** account_total_provider（REQ-c9f899 t12 §6-项2，
    # 勿另造第二份账户取数口径；缺数据时 provider 返回 None → 金额门关闭，不抛错）。
    # 标的名解析走 StockNameResolver 端口（与 SLA 巡检同一实现，单一取数口径）；
    # 装配失败降级 None → notifier 回退旧直连路径（名称是渲染增益，不阻断启动）。
    try:
        from qs_watch.application.services.watch_engine import watch_loop_wiring as _w
        _name_resolver = _w.build_name_resolver()
    except Exception:  # noqa: BLE001
        _name_resolver = None
    notifier = WatchNotifier(
        trigger_repo=WatchTriggerRepository(),
        account_total_provider=account_total_provider,
        name_resolver=_name_resolver,
    )

    _market_watch = MarketWatchService(
        rule_repo=WatchRuleRepository(),
        trigger_repo=WatchTriggerRepository(),
        state_provider=MarketStateProvider(),
        # P2 市场环境联动（2026-10-19）：持仓→板块映射，账户口径与 P5 生命周期一致
        # （agent 三账户；v13/v14 传统量化策略自有日检闭环，不进盯盘联动）。
        # 每日重建由引擎 sidecar 驱动（refresh_held_boards），tick 只读缓存。
        held_sector_map=HeldSectorMapService(
            position_repo=SimulationPositionRepository(),
            accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
        ),
    )

    # 摘要门（REQ-f08def P2/P4）：唤醒走 AgentNotificationService → POST /wake（官方通道）。
    #
    # ⚠️ 默认关闭，必须显式 WATCH_DIGEST_ENABLED=true 才生效（2026-09-11 w-c8cae280）。
    # 原因不是技术：摘要门一旦运行会真的唤醒 agent 去处置待处置触发，而这些触发里
    # 含真实买卖预案（如 300750「下破333=挂单建仓≤10%」）→ 可能产生真实委托。
    # 按 RFC 014 v3 §3.4（L3 交接态）：替用户决定下单是越权，故默认关，等明确授权。
    import os as _os
    if _os.getenv('WATCH_DIGEST_ENABLED', 'false').lower() == 'true':
        digest_service = WatchDigestService(
            trigger_repo=WatchTriggerRepository(),
            rule_repo=WatchRuleRepository(),
            agent_service=AgentNotificationService(
                # 唤醒是 fire-and-forget：agent 离线时绝不能用默认 300s 超时（AGENT_TIMEOUT）
                # 把引擎主循环卡死——2026-10-16 实测每轮循环被卡 ~5 分钟，心跳周期性
                # 「丢失」误报。10s 足够局域网唤醒投递；失败按原路径留痕下轮重试。
                timeout=int(os.getenv('WATCH_DIGEST_WAKE_TIMEOUT_SEC', '10'))),
            state_repo=WatchDigestStateRepository(),   # 端口实现（ADR-001：SQL 只在适配器层）
            market_watch_service=_market_watch,        # 摘要内嵌市场状态（P6）
            # 影子模式默认**开**（fail-safe）：只写日志不发唤醒；显式 WATCH_DIGEST_DRY_RUN=false
            # 才是真开（会叫 agent 处置，agent 自有账户可自主下单）。
            dry_run=_os.getenv('WATCH_DIGEST_DRY_RUN', 'true').lower() != 'false',
        )
    else:
        digest_service = None
        import structlog as _structlog
        _structlog.get_logger(__name__).info(
            '摘要门未启用（WATCH_DIGEST_ENABLED != true）—— 触发照常落库归档，但不唤醒 agent')

    # 闭环装配（REQ-c9f899 t12 §6-项8）：默认全关 → 全 None（行为与改造前一致）
    runtime_store, todo_service, receipt_service, sla_job, self_heal_service = \
        build_watch_loop_services()

    return WatchEngine(
        rule_repo=WatchRuleRepository(),
        quote_service=RealtimeQuoteServiceV2(),
        notifier=notifier,
        avg_volume_provider=make_avg_volume_provider(),
        position_value_provider=position_value_provider,
        account_total_provider=account_total_provider,
        digest_service=digest_service,
        # P4 介入记账：预算计数落库；P7 元触发复核：规则健康度回到 agent
        ledger=InterventionLedger(WatchInterventionRepository()),
        meta_review_service=WatchMetaReviewService(
            rule_repo=WatchRuleRepository(),
            trigger_repo=WatchTriggerRepository(),
        ),
        # P5 持仓生命周期联动：规则使命跟着交易走
        position_lifecycle_service=PositionLifecycleService(
            rule_repo=WatchRuleRepository(),
            position_repo=SimulationPositionRepository(),
            # 2026-10-19 修正：此前默认只盯 agent_virtual——user_main（用户真身）与
            # agent_brain 的持仓联动（清仓收摊/补挂止损/阶段推进/成本同步）从不执行，
            # 是 #128 徐工止损规则触发后永远挂着的结构性根因。
            accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
        ),
        # P6 市场级盯盘：取数走 IMarketStateProvider 端口，实现是 MarketStateProvider 适配器
        market_watch_service=_market_watch,
        # 闭环装配（REQ-c9f899 t12）：默认 None → 行为与改造前一致。
        # 2026-10-19：receipt_service/sla_job/self_heal_service 不再注入引擎
        # （死注入已清——SLA/回执在 inbound 定时任务侧，自愈由 interval job 调起），
        # 它们仍由 build_watch_loop_services 装配供 wiring/定时任务使用。
        runtime_state_store=runtime_store,
        todo_service=todo_service,
        # 观察聚合缓冲（REQ-261016155500-4f2a wt:validate:1）：无判据 observe 15min 合屏
        observe_agg=_build_observe_aggregator(),
        # P3 预判验证闭环（2026-10-20）：走势回填，sidecar 每日一次；
        # 取数走 qs_market_data 单例（服务内惰性取），仓储 L1 暂留同其它 watch 仓储。
        outcome_backfill_service=OutcomeBackfillService(
            outcome_repo=WatchOutcomeRepository()),
    )


def _build_observe_aggregator():
    """观察聚合缓冲装配：发送走盯盘群回执通道（watch_symbol 频道）。

    开关 WATCH_OBSERVE_AGG（默认开）；关闭时返回 None = 引擎完全退回即时单发。
    """
    from qs_watch.application.services.watch_engine.observe_aggregator import (
        OBSERVE_AGG_ENABLED, ObserveAggregator,
    )
    if not OBSERVE_AGG_ENABLED:
        return None

    def _sender(title: str, content: str) -> bool:
        from qs_watch.application.services.watch_engine.watch_channels import send_watch_receipt
        return send_watch_receipt({
            'kind': 'observe_digest',    # 聚合卡专用 kind（非三段回执语义，不落 receipts 表）
            'os_channel': 'watch_symbol',
            'message': '%s\n%s' % (title, content),
        })

    return ObserveAggregator(sender=_sender)


def start_watch_engine_in_thread() -> tuple[WatchEngine, threading.Thread]:
    """daemon 线程启动引擎，随主进程退出。返回 (engine, thread) 供调用方留存句柄优雅停止"""
    engine = create_watch_engine()
    thread = threading.Thread(target=engine.run_forever, name='watch-engine', daemon=True)
    thread.start()
    # 独立心跳写线程：存活信号与主循环各阶段耗时解耦（主循环被慢 I/O 卡住时
    # 巡检不再误报「心跳丢失」；2026-10-16 事故修补）。
    engine.spawn_heartbeat_thread()
    logger.info('✓ WatchEngine 已在后台线程启动')
    return engine, thread
