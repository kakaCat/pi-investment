"""信号类任务处理器（选股扫描/信号执行/股票池刷新）

2026-10-01（REQ-261001145152-3982 t-686185）：由 scheduler_tasks.py（原 1607 行）
机械拆分而来；函数体与签名**逐字未改**，原模块保留为转发壳，既有导入路径不受影响。
"""
from qs_kernel.domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta
import json
from qs_ops.application.services.scheduler_tasks_common import logger  # noqa: F401

DEFAULT_SCAN_STRATEGY_IDS = [272, 273]

def _scan_pool_signals_by_name(
    pool_name: str,
    strategy_ids=None,
    lookback_days: int = 60,
) -> list:
    """按池名扫描信号：解析池→symbols，调用 PoolSignalScanner。

    Returns: 买入/卖出信号列表，每个信号附带 pool/strategy_id/signal_type。
    """
    from qs_sourcing.application.services.pool_signal_scanner import PoolSignalScanner
    # 2026-09-03 修复（258 同类）：显式调用 getter 拿实例，裸名导入会拿到函数
    # （2026-10-21 直连 DI 唯一入口，去掉 adapters.shared.services 薄转发绕行）
    from infrastructure.services.service_factory import ServiceFactory
    stock_pool_service = ServiceFactory.get_stock_pool_service()

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
        # 2026-09-03 修复（258）：须显式调用 getter 拿实例；2026-10-21 直连 DI 唯一入口
        from infrastructure.services.service_factory import ServiceFactory
        service = ServiceFactory.get_stock_pool_service()

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
    """每日信号执行——独立量化虚拟交易闭环（rotation_main 账户）。

    2026-10-20 重绑（用户裁定：量化虚拟交易不走「信号→推送 Agent→agent_virtual」
    主链路，是独立闭环）：原实现是"兜底推送 Agent"（07:30 跑，实测天天
    signals_pending=0——调度线程长事务快照看不到早盘 06:52 新提交的信号），
    真实执行器 SignalExecutionScheduler 只被测试调用，导致近 90 天 962 条信号
    全部停在 pending、rotation_main 从未成交。现改为收盘后（15:40）真实执行：
    收集当日 pending → 风控 → 模拟引擎成交 → 状态回写（executed/approved/
    rejected）→ signal_executions 日志。
    """
    params = params or {}

    # 防调度线程长事务快照读到旧数据（2026-10-19 07:30 signals_pending=0 的
    # 成因即此——同 model_train 的 _release_thread_session 处置）
    from qs_ops.application.services.scheduler_tasks_training_guard import _release_thread_session
    _release_thread_session()

    from qs_sourcing.application.services.signal_execution_scheduler import SignalExecutionScheduler

    logger.info("Starting daily signal execution (independent paper-trading loop)")

    try:
        scheduler = SignalExecutionScheduler()
        result = scheduler.execute_pending_signals()

        return {
            "action": "signal_execution_daily",
            "status": "success" if result.get('success') else "failed",
            **{k: v for k, v in result.items() if k != 'success'},
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Signal execution failed: {e}")
        return {
            "action": "signal_execution_daily",
            "status": "failed",
            "error": str(e)
        }
    finally:
        _release_thread_session()


