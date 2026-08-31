"""
健康检查和系统状态 API - FastAPI 异步版本
"""
from fastapi import APIRouter, Response
from datetime import datetime
import structlog
from pathlib import Path
import os

from adapters.shared.services import portfolio_repo, risk_repo, signal_repo

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("")
async def health_check():
    """
    基础健康检查

    返回服务状态和数据库连接状态
    """
    try:
        from adapters.outbound.repositories import StockORMRepository
        repo = StockORMRepository()
        stocks = repo.get_all(limit=1)

        return {
            'status': 'ok',
            'db_connected': True,
            'db_info': {
                'provider': 'postgres',
                'stock_count': len(stocks),
                'version': 'v2'
            },
            'framework': 'fastapi',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.exception(f"Health check failed: {e}")
        return {
            'status': 'error',
            'db_connected': False,
            'error': str(e),
            'framework': 'fastapi'
        }


@router.get("/db")
async def health_db_pool():
    """
    数据库连接池健康检查

    返回连接池状态和利用率

    状态码:
    - 200: healthy (utilization < 80%)
    - 200: degraded (80% <= utilization < 100%)
    - 503: unhealthy (pool 未初始化或连接数已满)
    """
    try:
        from infrastructure.persistence.database.engine import get_pool_status
        status = get_pool_status()

        if not status.get('initialized', False):
            return Response(
                content='{"status": "unhealthy", "reason": "Connection pool not initialized"}',
                status_code=503,
                media_type="application/json"
            )

        # 计算利用率
        total = status.get('total', 0)
        checked_out = status.get('checked_out', 0)
        utilization = (checked_out / total * 100) if total > 0 else 0

        response_data = {
            'status': 'healthy',
            'utilization': f'{utilization:.1f}%',
            'pool_status': status
        }

        # 告警阈值: 80%
        status_code = 200
        if utilization >= 100:
            response_data['status'] = 'unhealthy'
            response_data['reason'] = f'Pool exhausted: {checked_out}/{total} connections in use'
            status_code = 503
            logger.error(f"DB pool unhealthy: {response_data}")
        elif utilization >= 80:
            response_data['status'] = 'degraded'
            response_data['reason'] = f'High utilization: {checked_out}/{total} connections in use'
            logger.warning(f"DB pool degraded: {response_data}")

        return Response(
            content=str(response_data),
            status_code=status_code,
            media_type="application/json"
        )

    except Exception as e:
        logger.exception(f"Health check failed: {e}")
        return Response(
            content=f'{{"status": "unhealthy", "reason": "Health check error: {str(e)}"}}',
            status_code=503,
            media_type="application/json"
        )


@router.get("/db/metrics")
async def db_metrics():
    """
    Prometheus 格式的连接池指标

    返回纯文本格式的监控指标
    """
    try:
        from infrastructure.persistence.database.engine import get_pool_status
        status = get_pool_status()

        if not status.get('initialized', False):
            return Response(
                content="# Pool not initialized\n",
                status_code=503,
                media_type="text/plain"
            )

        total = status.get('total', 0)
        checked_out = status.get('checked_out', 0)
        utilization = (checked_out / total * 100) if total > 0 else 0

        metrics = []

        # Pool size
        metrics.append("# HELP db_pool_size Current pool size")
        metrics.append("# TYPE db_pool_size gauge")
        metrics.append(f"db_pool_size {status.get('pool_size', 0)}")

        # Checked out
        metrics.append("# HELP db_pool_checked_out Connections currently checked out")
        metrics.append("# TYPE db_pool_checked_out gauge")
        metrics.append(f"db_pool_checked_out {checked_out}")

        # Checked in
        metrics.append("# HELP db_pool_checked_in Connections currently checked in")
        metrics.append("# TYPE db_pool_checked_in gauge")
        metrics.append(f"db_pool_checked_in {status.get('checked_in', 0)}")

        # Overflow
        metrics.append("# HELP db_pool_overflow Overflow connections")
        metrics.append("# TYPE db_pool_overflow gauge")
        metrics.append(f"db_pool_overflow {status.get('overflow', 0)}")

        # Total
        metrics.append("# HELP db_pool_total Total pool capacity")
        metrics.append("# TYPE db_pool_total gauge")
        metrics.append(f"db_pool_total {total}")

        # Utilization
        metrics.append("# HELP db_pool_utilization Pool utilization percentage")
        metrics.append("# TYPE db_pool_utilization gauge")
        metrics.append(f"db_pool_utilization {utilization:.2f}")

        return Response(
            content="\n".join(metrics) + "\n",
            status_code=200,
            media_type="text/plain; charset=utf-8"
        )

    except Exception as e:
        logger.exception(f"Metrics collection failed: {e}")
        return Response(
            content=f"# Error: {str(e)}\n",
            status_code=503,
            media_type="text/plain; charset=utf-8"
        )


@router.get("/platform/status")
async def platform_status():
    """
    平台状态检查

    返回数据库、信号、模型、报告等状态
    """
    try:
        holdings = portfolio_repo.get_all_holdings() if portfolio_repo else []
        balance = risk_repo.get_latest_balance() if risk_repo else None
        signals = signal_repo.get_latest_signals(limit=10) if signal_repo else []

        # 检查模型是否存在
        model_loaded = False
        model_paths = [
            Path(os.getcwd()) / 'ml' / 'models' / 'xgboost_latest.pkl',
            Path(os.getcwd()) / 'quant' / 'quantsys' / 'ml' / 'models' / 'xgboost_latest.pkl',
        ]
        for mp in model_paths:
            if mp.exists():
                model_loaded = True
                break

        # 检查最近报告
        report_dir = Path(os.getcwd()) / '.pi-invest' / 'reports'
        recent_report = False
        if report_dir.exists():
            cutoff = datetime.now().timestamp() - 86400
            for f in report_dir.iterdir():
                if f.is_file() and f.stat().st_mtime > cutoff:
                    recent_report = True
                    break

        db_connected = balance is not None

        return {
            'success': True,
            'data': {
                'status': 'running' if db_connected else 'degraded',
                'holdings_count': len(holdings),
                'balance': balance,
                'recent_signals': len(signals),
                'db_connected': db_connected,
                'model_loaded': model_loaded,
                'recent_report': recent_report,
                'timestamp': datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.exception(f"Platform status check failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }
