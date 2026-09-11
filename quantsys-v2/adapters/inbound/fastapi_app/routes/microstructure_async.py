"""微观结构 API（分钟线 / 交易状态 / 执行成本估算）

RFC 015 §4.4（2026-09-11 REQ-cf627b）。数据流：
    agent-dh 工具 / web → 本路由（入站适配器）
        → application/services/microstructure_service（编排，零 adapters 依赖）
            → domain.trading.services.TradingStatusPolicy（领域判定）
            → 端口 ← adapters.outbound（minute_kline providers / repositories）

组合根说明：具体实现的装配放在**本文件**（入站适配器），因此应用层可以完全不出现
adapters 导入（ADR-001 依赖倒置红线；应用层用构造函数注入）。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
import structlog

from adapters.inbound.fastapi_app.shared import error_response
from application.services.microstructure_service import (
    MicrostructureService,
    get_microstructure_service,
    set_microstructure_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Microstructure - 分钟线/交易状态"])


def get_service() -> MicrostructureService:
    """组合根：装配 IDataProviderManager + ITradingStatusRepository（进程级复用）"""
    svc = get_microstructure_service()
    if svc is None:
        from adapters.outbound.datasources.manager import get_data_provider_manager
        from adapters.outbound.repositories.trading_status_repository import get_trading_status_repo
        svc = MicrostructureService(
            manager=get_data_provider_manager(),
            status_repo=get_trading_status_repo(),
        )
        set_microstructure_service(svc)
    return svc


@router.get('/api/stocks/{symbol}/minute-klines')
def get_minute_klines(
    symbol: str,
    period: str = Query(default='5m', description='1m/5m/15m/30m/60m'),
    date: Optional[str] = Query(default=None, description='单日，YYYY-MM-DD'),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(default=240, ge=1, le=1023),
    cross_check: bool = Query(default=False, description='true=触发跨源一致性校验（§1.5.6，会多打一次上游）'),
):
    """分钟K线（多源故障转移；全源失败显式失败，不返回空数组冒充成功）"""
    try:
        if date:
            start_date = start_date or date
            end_date = end_date or date
        svc = get_service()
        if cross_check:
            result = svc.get_minute_klines(symbol, period, start_date, end_date, limit)
            check = svc.cross_check_minute_klines(symbol, period, start_date, end_date, limit)
            result['cross_source_check'] = check
            if check.get('cross_source_conflict'):
                result['cross_source_conflict'] = check['cross_source_conflict']
            return result
        return svc.get_minute_klines(symbol, period, start_date, end_date, limit)
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error('get_minute_klines failed', symbol=symbol, error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)


@router.get('/api/stocks/{symbol}/trading-status')
def get_trading_status(symbol: str):
    """下单前交易状态（ST/停牌/涨跌停/可交易；跨源冲突保守取不可交易）"""
    try:
        return get_service().get_trading_status(symbol)
    except Exception as e:
        logger.error('get_trading_status failed', symbol=symbol, error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)


@router.post('/api/execution/estimate')
def estimate_execution(payload: Optional[Dict[str, Any]] = Body(None)):
    """执行成本估算（参与率/滑点/冲击成本，供 R-003 拆单决策）

    Body: {"symbol": "600150", "side": "BUY", "quantity": 10000, "price": 39.75}
    （price 可省略，用最新 bar 收盘价）
    """
    params = payload or {}
    symbol = params.get('symbol')
    side = params.get('side')
    quantity = params.get('quantity')
    if not symbol or side is None or quantity is None:
        return error_response(
            {'success': False, 'error': 'symbol / side / quantity 均为必填'}, 400
        )
    try:
        return get_service().estimate_execution(
            symbol=str(symbol), side=str(side), quantity=quantity, price=params.get('price'),
        )
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error('estimate_execution failed', symbol=symbol, error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)
