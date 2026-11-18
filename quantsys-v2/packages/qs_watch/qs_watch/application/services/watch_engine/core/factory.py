"""Watch 旁路服务与 V2 共享实例装配。"""
import os
import threading
from typing import Mapping, Optional

import structlog

from qs_agenthub.application.services.agent_notification_service import AgentNotificationService
from qs_market_data.adapters.outbound.datasources.market_state_provider import MarketStateProvider
from qs_market_data.application.services.realtime_quote_service_v2 import RealtimeQuoteServiceV2
from qs_watch.application.services.watch_engine.digest_service import WatchDigestService
from qs_watch.application.services.watch_engine.held_sector_map import HeldSectorMapService
from qs_watch.application.services.watch_engine.market_watch_service import MarketWatchService
from qs_watch.application.services.watch_engine.meta_review_service import WatchMetaReviewService
from qs_watch.application.services.watch_engine.position_lifecycle_service import PositionLifecycleService
from qs_watch.application.services.watch_engine.outcome_backfill_service import OutcomeBackfillService
from qs_watch.application.services.watch_engine.engine import WatchEngine
from ._repo_resolver import (
    news_alert_repo,
    news_source,
    pool_member_source,
    sim_position_repo,
    todo_repo,
    watch_digest_state_repo,
    watch_outcome_repo,
    watch_rule_repo,
    watch_trigger_repo,
    watch_pool_binding_repo,
)

logger = structlog.get_logger(__name__)

POLICY_WATCH_ENABLED_ENV = 'WATCH_POLICY_WATCH_ENABLED'
POLICY_SCAN_INTERVAL_ENV = 'WATCH_POLICY_SCAN_INTERVAL_SEC'
DEFAULT_POLICY_SCAN_INTERVAL_SEC = 300.0
POLICY_SCAN_MIN_INTERVAL_SEC = 30.0
POLICY_SCAN_START_DELAY_SEC = 15.0
POLICY_SCAN_FAIL_BACKOFF_SEC = 60.0
POLICY_SCAN_THREAD_NAME = 'watch-policy-scan'
SECTOR_RESONANCE_POOL_ENV = 'WATCH_SECTOR_RESONANCE_POOL_ID'
_AUTO = object()


def _build_pool_watch_service():
    from qs_watch.application.services.watch_engine.pool_watch_service import PoolWatchService
    return PoolWatchService(
        watch_pool_binding_repo(), pool_member_source(), watch_rule_repo())


def _build_news_watch_service(bridge=None):
    from qs_watch.application.services.watch_engine.news_watch_service import NewsWatchService
    from qs_watch.application.services.watch_engine.watch_channels import send_watch_receipt
    return NewsWatchService(
        news_source=news_source(), alert_repo=news_alert_repo(),
        position_repo=sim_position_repo(),
        accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
        sender=send_watch_receipt, bridge=bridge)


class _WatchRuleCandidateSource:
    def __init__(self, rule_repo=None):
        self._rule_repo = rule_repo

    def get_members(self, pool_id=None):  # noqa: ARG002
        repo = self._rule_repo or watch_rule_repo()
        return [{'symbol': rule.symbol} for rule in (repo.list_enabled() or [])
                if str(getattr(rule, 'symbol', '') or '').strip()]


def _sector_resonance_pool_id() -> Optional[int]:
    raw = os.getenv(SECTOR_RESONANCE_POOL_ENV, '').strip()
    if not raw:
        return None
    try:
        pool_id = int(raw)
    except (TypeError, ValueError):
        return None
    return pool_id if pool_id > 0 else None


def _policy_watch_enabled() -> bool:
    return os.getenv(POLICY_WATCH_ENABLED_ENV, 'true').strip().lower() in (
        '1', 'true', 'yes', 'on')


def _policy_scan_interval() -> float:
    raw = os.getenv(POLICY_SCAN_INTERVAL_ENV)
    if raw is None or not str(raw).strip():
        return DEFAULT_POLICY_SCAN_INTERVAL_SEC
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_POLICY_SCAN_INTERVAL_SEC
    if value <= 0:
        return DEFAULT_POLICY_SCAN_INTERVAL_SEC
    if value < POLICY_SCAN_MIN_INTERVAL_SEC:
        logger.warning('政策盯盘扫描间隔过小，抬到下限', value=value,
                       min=POLICY_SCAN_MIN_INTERVAL_SEC)
        return POLICY_SCAN_MIN_INTERVAL_SEC
    return value


def build_policy_watch_service(news_service=_AUTO, bridge=None):
    if not _policy_watch_enabled():
        return None
    stage = 'import'
    try:
        from qs_watch.application.services.watch_engine.policy_news_source import PolicyNewsSource
        from qs_watch.application.services.watch_engine.policy_watch_service import PolicyWatchService
        from qs_watch.application.services.watch_engine.watch_channels import send_watch_receipt
        stage = 'news_source'
        source = PolicyNewsSource()
        stage = 'candidates'
        pool_id = _sector_resonance_pool_id()
        candidate_source = pool_member_source() if pool_id is not None else _WatchRuleCandidateSource()
        stage = 'news_service'
        if news_service is _AUTO:
            try:
                news_service = _build_news_watch_service()
            except Exception as exc:  # noqa: BLE001
                logger.error('政策盯盘确认核验查询装配失败（候选池命中将标注未核验，'
                             '持仓 P0/P2 路由不受影响）', error=str(exc))
                news_service = None
        stage = 'service'
        return PolicyWatchService(
            news_source=source,
            position_repo=sim_position_repo(),
            accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
            candidate_source=candidate_source,
            candidate_pool_id=pool_id or 0,
            alert_repo=news_alert_repo(),
            news_service=news_service,
            sender=send_watch_receipt,
            bridge=bridge,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error('政策盯盘扫描装配失败，降级为不启动（引擎照常运行）',
                     stage=stage, error=str(exc))
        return None


def start_policy_watch_scanner(engine=None, stop_event=None, service=None):
    if service is None:
        service = build_policy_watch_service(
            bridge=getattr(engine, 'news_todo_bridge', None),
            news_service=(getattr(engine, 'news_watch_service', None)
                          if engine is not None else _AUTO))
    if service is None:
        return None, None
    interval = _policy_scan_interval()

    def _stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    def _wait(seconds: float) -> None:
        if stop_event is not None:
            stop_event.wait(seconds)
        else:
            threading.Event().wait(seconds)

    def _loop():
        _wait(min(POLICY_SCAN_START_DELAY_SEC, interval))
        while not _stopped():
            delay = interval
            try:
                result = service.scan()
                if isinstance(result, Mapping) and result.get('skipped'):
                    logger.warning('政策盯盘扫描未完成', reason=result.get('reason'))
            except Exception as exc:  # noqa: BLE001
                logger.error('政策盯盘扫描异常', error=str(exc))
                delay = POLICY_SCAN_FAIL_BACKOFF_SEC
            finally:
                try:
                    from qs_kernel.infrastructure.persistence.orm import close_session
                    close_session()
                except Exception:
                    pass
            _wait(delay)

    thread = threading.Thread(target=_loop, name=POLICY_SCAN_THREAD_NAME, daemon=True)
    thread.start()
    return service, thread


def build_watch_loop_services():
    from qs_watch.application.services.watch_engine import watch_loop_wiring as wiring
    runtime_store = None
    if wiring.watch_runtime_persist_enabled():
        try:
            runtime_store = wiring.build_runtime_store()
        except Exception as exc:  # noqa: BLE001
            logger.error('运行态持久化装配失败', error=str(exc))
    todo_service = receipt_service = sla_job = self_heal_service = None
    if wiring.watch_todo_enabled():
        try:
            todo_service = wiring.build_todo_service()
            receipt_service = wiring.build_receipt_service()
            sla_job = wiring.build_sla_job(receipt_service=receipt_service)
        except Exception as exc:  # noqa: BLE001
            logger.error('盯盘闭环装配失败', error=str(exc))
            todo_service = receipt_service = sla_job = None
        if todo_service is not None and wiring.watch_self_heal_enabled():
            try:
                self_heal_service = wiring.build_self_heal_service(todo_service)
            except Exception as exc:  # noqa: BLE001
                logger.error('规则自愈装配失败', error=str(exc))
    return runtime_store, todo_service, receipt_service, sla_job, self_heal_service


_MARKET_WATCH_SERVICE = None


def get_market_watch_service():
    global _MARKET_WATCH_SERVICE
    if _MARKET_WATCH_SERVICE is None:
        _MARKET_WATCH_SERVICE = MarketWatchService(
            rule_repo=watch_rule_repo(),
            trigger_repo=watch_trigger_repo(),
            state_provider=MarketStateProvider(),
            held_sector_map=HeldSectorMapService(
                position_repo=sim_position_repo(),
                accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
            ),
        )
    return _MARKET_WATCH_SERVICE


def create_watch_engine() -> WatchEngine:
    try:
        from qs_watch.application.services.watch_engine import watch_loop_wiring as wiring
        name_resolver = wiring.build_name_resolver()
    except Exception:  # noqa: BLE001
        name_resolver = None

    market_watch = get_market_watch_service()
    digest_service = None
    if os.getenv('WATCH_DIGEST_ENABLED', 'false').lower() == 'true':
        digest_service = WatchDigestService(
            trigger_repo=watch_trigger_repo(),
            rule_repo=watch_rule_repo(),
            agent_service=AgentNotificationService(
                timeout=int(os.getenv('WATCH_DIGEST_WAKE_TIMEOUT_SEC', '10'))),
            state_repo=watch_digest_state_repo(),
            market_watch_service=market_watch,
            dry_run=os.getenv('WATCH_DIGEST_DRY_RUN', 'true').lower() != 'false',
        )

    _, todo_service, _, _, _ = build_watch_loop_services()
    news_todo_bridge = None
    if todo_service is not None:
        try:
            from qs_watch.application.services.watch_engine.news_todo_bridge import NewsTodoBridge
            news_todo_bridge = NewsTodoBridge(todo_service, todo_repo=todo_repo())
        except Exception as exc:  # noqa: BLE001
            logger.error('消息待办桥装配失败', error=str(exc))
    try:
        news_watch_service = (_build_news_watch_service(bridge=news_todo_bridge)
                              if news_todo_bridge is not None else _build_news_watch_service())
    except Exception as exc:  # noqa: BLE001
        logger.error('消息监控服务装配失败', error=str(exc))
        news_watch_service = None

    engine = WatchEngine(
        rule_repo=watch_rule_repo(),
        digest_service=digest_service,
        meta_review_service=WatchMetaReviewService(
            rule_repo=watch_rule_repo(),
            trigger_repo=watch_trigger_repo(),
            todo_service=todo_service,
        ),
        pool_watch_service=_build_pool_watch_service(),
        news_watch_service=news_watch_service,
        position_lifecycle_service=PositionLifecycleService(
            rule_repo=watch_rule_repo(),
            position_repo=sim_position_repo(),
            accounts=("agent_virtual", "agent_brain", "user_main_simulation"),
        ),
        market_watch_service=market_watch,
        outcome_backfill_service=OutcomeBackfillService(
            outcome_repo=watch_outcome_repo()),
        trigger_repo=watch_trigger_repo(),
        name_resolver=name_resolver,
    )
    engine.news_todo_bridge = news_todo_bridge
    _register_fill_sync_listener(engine, todo_service)
    return engine


def _register_fill_sync_listener(engine, todo_service) -> None:
    try:
        from application.trading.paper_trading_engine import register_fill_listener
        from qs_watch.application.services.watch_engine.fill_sync_service import FillSyncService
        listener = FillSyncService(
            rule_repo=engine.rule_repo,
            todo_service=todo_service,
            todo_repo=todo_repo(),
            trigger_repo=watch_trigger_repo(),
            position_repo=sim_position_repo(),
            lifecycle=getattr(engine, 'position_lifecycle_service', None),
            plan_progress=_plan_progress_port(),
            t_trade_progress=_t_trade_progress_port(engine.rule_repo),
        )
        register_fill_listener(listener)
    except Exception as exc:  # noqa: BLE001
        logger.error('成交回执同步装配失败', error=str(exc))


def _plan_progress_port():
    try:
        from adapters.outbound.repositories.plan_progress_port import PlanProgressPort
        return PlanProgressPort()
    except Exception as exc:  # noqa: BLE001
        logger.error('计划推进端口装配失败', error=str(exc))
        return None


def _t_trade_progress_port(rule_repo):
    try:
        from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
        from adapters.outbound.repositories.t_trade_repository import TTradeRepository
        from qs_watch.application.services.watch_engine.lifecycle.t_trade_watch_service import (
            TTradeWatchService,
        )
        simulation_repo = SimulationORMRepository()
        return TTradeWatchService(
            rule_repo=rule_repo,
            cycle_repo=TTradeRepository(simulation_repo=simulation_repo),
        ).on_fill
    except Exception as exc:  # noqa: BLE001
        logger.error('做T推进端口装配失败', error=str(exc))
        return None


def start_watch_sidecars_in_thread() -> WatchEngine:
    engine = create_watch_engine()
    engine._ensure_sidecar_thread()
    try:
        start_policy_watch_scanner(engine)
    except Exception as exc:  # noqa: BLE001
        logger.error('政策盯盘扫描线程启动失败（旁路服务照常运行）', error=str(exc))
    logger.info('✓ WatchEngine 旁路服务已启动（股票判定归 V2）')
    return engine
