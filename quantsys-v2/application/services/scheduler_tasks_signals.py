"""信号类任务处理器（选股扫描/信号执行/股票池刷新）

2026-10-01（REQ-261001145152-3982 t-686185）：由 scheduler_tasks.py（原 1607 行）
机械拆分而来；函数体与签名**逐字未改**，原模块保留为转发壳，既有导入路径不受影响。
"""
from domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta
import json
from application.services.scheduler_tasks_common import logger  # noqa: F401

DEFAULT_SCAN_STRATEGY_IDS = [272, 273]

def _scan_pool_signals_by_name(
    pool_name: str,
    strategy_ids=None,
    lookback_days: int = 60,
) -> list:
    """按池名扫描信号：解析池→symbols，调用 PoolSignalScanner。

    Returns: 买入/卖出信号列表，每个信号附带 pool/strategy_id/signal_type。
    """
    from application.services.pool_signal_scanner import PoolSignalScanner
    # 2026-09-03 修复（258 同类）：显式调用 getter 拿实例，裸名导入会拿到函数（services.py 显式绑定挡住惰性代理）
    from adapters.shared.services import get_stock_pool_service
    stock_pool_service = get_stock_pool_service()

    strategy_ids = strategy_ids or DEFAULT_SCAN_STRATEGY_IDS

    # 解析池名 → pool_id → symbols
    pools_by_name = {p['name']: p for p in stock_pool_service.list_pools()}
    if pool_name not in pools_by_name:
        raise ValueError(f"股票池不存在: {pool_name}")
    pool = stock_pool_service.get_pool(pools_by_name[pool_name]['id'])
    symbols = pool.get('symbols', [])
    if not symbols:
        return []

    scanner = PoolSignalScanner(IKlineRepository(), IStrategyRepository())
    signals = []
    for strategy_id in strategy_ids:
        result = scanner.scan_pool_signals(
            symbols=symbols,
            strategy_id=strategy_id,
            lookback_days=lookback_days,
        )
        for s in result.get('buy_signals', []):
            signals.append({**s, 'pool': pool_name, 'strategy_id': strategy_id, 'signal_type': 'buy'})
        for s in result.get('sell_signals', []):
            signals.append({**s, 'pool': pool_name, 'strategy_id': strategy_id, 'signal_type': 'sell'})
    return signals


def handle_signal_generate(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """信号生成任务"""
    params = params or {}

    logger.info("Starting signal_generate task")

    try:
        # 获取要扫描的池子
        pools = params.get('pools', ['主选池', '备选池'])
        strategy_ids = params.get('strategy_ids')

        all_signals = []
        pools_scanned = 0

        for pool_name in pools:
            try:
                signals = _scan_pool_signals_by_name(pool_name, strategy_ids=strategy_ids)
                all_signals.extend(signals)
                pools_scanned += 1
            except Exception as e:
                logger.warning(f"Failed to scan pool {pool_name}: {e}")

        # 按信号强度排序（无 strength 字段的信号排最后）
        all_signals.sort(key=lambda x: x.get('strength', 0), reverse=True)

        return {
            "action": "signal_generate",
            "status": "success",
            "pools_scanned": pools_scanned,
            "signals_generated": len(all_signals),
            "top_signals": all_signals[:20],  # 返回前20个信号
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        return {
            "action": "signal_generate",
            "status": "failed",
            "error": str(e)
        }


def _is_pool_refresh_due(pool: Dict[str, Any], today: date) -> bool:
    """判断动态池是否到期该刷新。

    refresh_interval 约定：'daily' 每个交易日刷；'weekly' 距上次 ≥7 天；
    其他/缺失值按 daily 处理（宁多刷不漏刷）。
    """
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
    """每日动态池刷新任务（02:00）

    刷新所有到期动态池，记录成员变更；有变更时通知 Agent（pool_changed）。
    service 参数用于测试注入；默认使用 API 共享单例。
    """
    params = params or {}
    logger.info("Starting pool_refresh_daily task")

    if service is None:
        # 2026-09-03 修复（258）：裸名导入拿到的是函数（services.py 显式绑定挡住惰性代理），须显式调用 getter 拿实例
        from adapters.shared.services import get_stock_pool_service
        service = get_stock_pool_service()

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


def handle_signal_execution_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """每日信号汇总推送（兜底重推）

    2026-07-24 盈利闭环改造：v2 不再自动下单。本任务只把当日 pending
    信号再次推送给 Agent（orchestrator MARKET_OPEN 推送的兜底），
    Agent 侧按信号 ID 判重，重复推送不会重复交易。
    """
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
            # timeout 视为已送达（agent 正在处理），不重推
            pushed = result in ('ok', 'timeout')

        return {
            "action": "signal_execution_daily",
            "status": "success",
            "signals_pending": len(signals),
            "pushed": pushed,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Signal summary push failed: {e}")
        return {
            "action": "signal_execution_daily",
            "status": "failed",
            "error": str(e)
        }


