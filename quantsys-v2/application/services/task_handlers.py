"""
调度任务 handler 函数（从 scheduler_tasks.py 提取）

仅保留测试仍依赖的 handler 函数和分发机制。
新代码应使用 application.jobs.* 中的 Job 类。
"""
import logging
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================
# Handler 函数
# ============================================================

def handle_signal_execution_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """每日信号汇总推送（兜底重推）"""
    params = params or {}

    from application.services.signal_execution_scheduler import SignalExecutionScheduler

    logger.info("Starting daily signal summary push (fallback)")

    try:
        scheduler = SignalExecutionScheduler()
        signals = scheduler._collect_signals(date.today().strftime('%Y-%m-%d'))

        pushed = False
        if signals and not params.get('skip_notify'):
            from application.services.agent_notification_service import agent_service
            result = agent_service.notify_agent_detailed('signals_ready', {
                'trade_date': date.today().isoformat(),
                'signal_count': len(signals),
                'signals': signals[:20],
                'account': 'agent_virtual',
                'source': 'signal_execution_daily_fallback',
            })
            pushed = result in ('ok', 'timeout')

        return {
            "action": "signal_execution_daily",
            "status": "success",
            "signals_pending": len(signals),
            "pushed": pushed,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Signal execution fallback failed: {e}")
        return {
            "action": "signal_execution_daily",
            "status": "failed",
            "error": str(e),
        }


def _is_pool_refresh_due(pool: Dict[str, Any], today: date) -> bool:
    """判断动态池是否到期该刷新。"""
    interval = (pool.get('refresh_interval') or 'daily').lower()
    if interval == 'weekly':
        last = pool.get('last_refreshed_at')
        if not last:
            return True
        try:
            last_date = datetime.fromisoformat(str(last).split(' ')[0]).date()
            return (today - last_date).days >= 7
        except ValueError:
            return True
    return True


def handle_pool_refresh_daily(
    params: Dict[str, Any] = None,
    service=None,
) -> Dict[str, Any]:
    """每日动态池刷新任务"""
    params = params or {}
    logger.info("Starting pool_refresh_daily task")

    if service is None:
        from adapters.shared.services import stock_pool_service
        service = stock_pool_service

    today = date.today()
    refreshed, skipped, failed = [], [], []

    for pool in service.list_pools():
        if pool.get('pool_type') != 'dynamic':
            continue
        if not _is_pool_refresh_due(pool, today):
            skipped.append({'pool_id': pool['id'], 'name': pool['name']})
            continue
        try:
            before_symbols = set(service.get_pool(pool['id']).get('symbols', []))
            service.refresh_pool(pool['id'])
            after_symbols = set(service.get_pool(pool['id']).get('symbols', []))
            refreshed.append({
                'pool_id': pool['id'],
                'name': pool['name'],
                'added': sorted(after_symbols - before_symbols),
                'removed': sorted(before_symbols - after_symbols),
            })
        except Exception as e:
            logger.error(f"Failed to refresh pool {pool['id']}: {e}")
            failed.append({'pool_id': pool['id'], 'name': pool['name'], 'error': str(e)})

    changed = [r for r in refreshed if r['added'] or r['removed']]
    if changed and not params.get('skip_notify'):
        try:
            from application.services.agent_notification_service import agent_service
            agent_service.notify_agent('pool_changed', {
                'trade_date': today.isoformat(),
                'pools_changed': changed,
                'account': 'agent_virtual',
            })
        except Exception as e:
            logger.warning(f"pool_changed notify failed: {e}")

    return {
        "action": "pool_refresh_daily",
        "status": "success" if not failed else "partial",
        "refreshed": len(refreshed),
        "changed": len(changed),
        "skipped": len(skipped),
        "failed": failed,
        "timestamp": datetime.now().isoformat(),
    }


def handle_agent_reminder(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Agent提醒任务处理器"""
    params = params or {}

    agent_id = params.get("agent_id", "default_agent")
    message = params.get("message", "这是一个提醒")
    remind_at = params.get("remind_at")

    logger.info(f"Agent Reminder for {agent_id}: {message}")

    try:
        try:
            from application.services.agent_notification_service import AgentNotificationService
            notification_service = AgentNotificationService()
            notification_service.send_reminder(
                agent_id=agent_id,
                message=message,
                remind_at=remind_at,
            )
        except Exception as notify_error:
            logger.warning(f"Notification service not available: {notify_error}")

        logger.info(f"Agent {agent_id} reminder: {message} (scheduled for {remind_at})")

        return {
            "action": "agent_reminder",
            "status": "success",
            "agent_id": agent_id,
            "message": message,
            "remind_at": remind_at,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Agent reminder failed: {e}")
        return {
            "action": "agent_reminder",
            "status": "failed",
            "error": str(e),
        }


def handle_decision_score_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """决策打分每日任务"""
    try:
        from application.services.evolution.decision_score_service import DecisionScoreService
        result = DecisionScoreService().score_mature_decisions()
        return {"action": "decision_score_daily", "status": "success",
                **result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"决策打分任务失败: {e}")
        return {"action": "decision_score_daily", "status": "failed",
                "error": str(e), "timestamp": datetime.now().isoformat()}


def handle_daily_equity_snapshot(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """全账户每日净值快照"""
    from application.services.evolution.daily_snapshot_service import DailySnapshotService

    logger.info("Starting daily_equity_snapshot task")
    try:
        params = params or {}
        target = date.fromisoformat(params['date']) if params.get('date') else None
        result = DailySnapshotService().snapshot_all_accounts(target_date=target)
        return {
            "action": "daily_equity_snapshot",
            "status": "success",
            **result,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"daily_equity_snapshot failed: {e}")
        return {
            "action": "daily_equity_snapshot",
            "status": "failed",
            "error": str(e),
        }


def handle_chan_scan(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """缠论买卖点池内扫描"""
    from application.services.chan_scan_service import ChanScanService

    logger.info("Starting chan_scan task")
    try:
        summary = ChanScanService().scan()
        return {
            "action": "chan_scan",
            "status": "success",
            **summary,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"chan_scan failed: {e}")
        return {
            "action": "chan_scan",
            "status": "failed",
            "error": str(e),
        }


def handle_chan_knowledge_distill(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """缠论信号胜率蒸馏"""
    from application.services.chan_knowledge_distiller import ChanKnowledgeDistiller

    logger.info("Starting chan_knowledge_distill task")
    try:
        params = params or {}
        result = ChanKnowledgeDistiller(
            window_days=params.get('window_days', 20),
            lookback_days=params.get('lookback_days', 90),
        ).distill()
        return {
            "action": "chan_knowledge_distill",
            "status": "success",
            **result,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"chan_knowledge_distill failed: {e}")
        return {
            "action": "chan_knowledge_distill",
            "status": "failed",
            "error": str(e),
        }


def handle_evolution_fitness_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """双侧捕获适应度每日计算"""
    from application.services.evolution.evolution_fitness_service import EvolutionFitnessService

    logger.info("Starting evolution_fitness_daily task")
    try:
        params = params or {}
        result = EvolutionFitnessService().compute_all_accounts(
            window_days=params.get('window_days', 20))
        return {
            "action": "evolution_fitness_daily",
            "status": "success",
            **result,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"evolution_fitness_daily failed: {e}")
        return {
            "action": "evolution_fitness_daily",
            "status": "failed",
            "error": str(e),
        }


def handle_missed_opportunity_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """踏空捕获每日任务"""
    try:
        from application.services.evolution.missed_opportunity_service import MissedOpportunityService
        result = MissedOpportunityService().capture()
        return {"action": "missed_opportunity_daily", "status": "success",
                **result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"踏空捕获任务失败: {e}")
        return {"action": "missed_opportunity_daily", "status": "failed",
                "error": str(e), "timestamp": datetime.now().isoformat()}


def handle_factor_compute(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """因子计算任务（盘后批量重算并落库）"""
    from datetime import timedelta

    params = params or {}
    logger.info("Starting factor_compute task")

    try:
        from domain.backtest.stages.factor_stage import FactorStage
        from adapters.shared.fund_flow_helpers import (
            _inject_fund_flow_to_klines, _extract_fund_flow_factors,
        )
        from adapters.outbound.repositories import KlineORMRepository, FactorORMRepository

        symbols = params.get('symbols')
        if not symbols:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            from domain.ports import IStockRepository
            repo = EnhancedServiceFactory.resolve(IStockRepository)
            stocks = repo.get_all(limit=params.get('max_symbols', 500))
            symbols = [s['symbol'] for s in stocks]

        requested = params.get('factors') or None
        if requested == ['all']:
            requested = None

        lookback_days = params.get('lookback_days', 300)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        computed = 0
        failed = []
        for sym in symbols:
            try:
                kline_repo = KlineORMRepository()
                klines_df = kline_repo.get_daily_klines(sym, start_date, end_date)
                if klines_df is None or klines_df.is_empty():
                    failed.append(sym)
                    continue

                klines = klines_df.to_dicts()
                klines = _inject_fund_flow_to_klines(klines, sym)

                stage = FactorStage(name='factors', factor_names=requested)
                stage_input = {'symbol': sym, 'klines': klines}
                if requested:
                    stage_input['requested_factors'] = requested

                result = stage.process(stage_input)
                factors = result.get('factors', {})

                all_requested = requested or stage.DEFAULT_TECHNICAL_FACTORS
                computed_names = set(factors.keys())
                missing = set(all_requested) - computed_names
                if missing and len(klines) < 250:
                    logger.warning(f"{sym}: {len(missing)} factors dropped (insufficient data {len(klines)}<250): {sorted(missing)}")

                fund_factors = _extract_fund_flow_factors(klines)
                factors.update(fund_factors)

                last_row = klines[-1]
                latest_date = last_row.get('trade_date') or last_row.get('date') or ''
                FactorORMRepository().save_factors(sym, str(latest_date), factors)
                computed += 1
            except Exception as sym_err:
                logger.warning(f"factor compute failed for {sym}: {sym_err}")
                failed.append(sym)

        return {
            "action": "factor_compute",
            "status": "success",
            "symbols_count": len(symbols),
            "factors_computed": computed,
            "failed": failed[:20],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Factor compute failed: {e}")
        return {
            "action": "factor_compute",
            "status": "failed",
            "error": str(e),
        }


# ============================================================
# Handler Registry（兼容旧代码的分发机制）
# ============================================================

_TASK_HANDLERS: Dict[str, Callable] = {
    "signal_execution_daily": handle_signal_execution_daily,
    "pool_refresh_daily": handle_pool_refresh_daily,
    "agent_reminder": handle_agent_reminder,
    "decision_score_daily": handle_decision_score_daily,
    "daily_equity_snapshot": handle_daily_equity_snapshot,
    "chan_scan": handle_chan_scan,
    "chan_knowledge_distill": handle_chan_knowledge_distill,
    "evolution_fitness_daily": handle_evolution_fitness_daily,
    "missed_opportunity_daily": handle_missed_opportunity_daily,
    "factor_compute": handle_factor_compute,
}


def get_task_handler(name: str) -> Optional[Callable]:
    """获取调度任务 handler"""
    return _TASK_HANDLERS.get(name)
