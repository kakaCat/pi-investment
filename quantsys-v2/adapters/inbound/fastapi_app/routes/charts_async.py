"""
图表数据 API (FastAPI 异步版本)

图表数据查询

flask_parity_router：从 Flask charts.py 迁移的 4 个图表端点（响应契约保持一致）：
- /api/charts/accuracy    模型准确率趋势图
- /api/charts/equity      回测权益曲线图
- /api/charts/comparison  策略对比图
- /api/charts/importance  特征重要性图表
"""
import os
import json
import base64 as _base64
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog

from application.services.core_async_services import DataAsyncService
from adapters.inbound.fastapi_app.shared import (
    ds, api_response, error_response, handle_api_error, sanitize_for_json,
    strategy_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/charts",
    tags=["Charts - 图表数据"]
)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.get("/kline/{symbol}", response_model=ApiResponse, summary="K线图数据")
async def get_kline_chart(
    symbol: str,
    period: str = Query("daily", description="周期: daily/weekly/monthly"),
    limit: int = Query(250, description="返回数量")
):
    """
    获取K线图数据
    """
    try:
        service = DataAsyncService()
        klines = await service.get_klines(symbol, limit=limit)

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "period": period,
                "data": klines
            }
        }
    except Exception as e:
        logger.exception(f"Get kline chart failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/price/{symbol}", response_model=ApiResponse, summary="价格走势图")
async def get_price_chart(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期")
):
    """
    获取价格走势图数据
    """
    try:
        service = DataAsyncService()
        klines = await service.get_klines(symbol, start_date, end_date)

        # 提取价格数据
        prices = [{"date": k["trade_date"], "price": k["close"]} for k in klines]

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "prices": prices
            }
        }
    except Exception as e:
        logger.exception(f"Get price chart failed: {e}")
        return {"success": False, "error": str(e)}


# =====================================================================
# Flask charts.py parity 迁移（契约冻结：字段名/状态码与 Flask 完全一致）
# =====================================================================

flask_parity_router = APIRouter(tags=["Charts - 图表 (Flask parity)"])

_CHART_DIR = Path(os.getcwd()) / '.pi-invest' / 'quant' / 'charts'


def _import_visualizer():
    """Lazy import visualizer with sys.path adjustment for quant package.

    注意：与 Flask charts.py 完全一致地逐字复制——其中 `visualizer` 未定义，
    会抛 NameError，被各端点捕获后返回 503。保持该既有行为以冻结契约。
    """
    _quant_path = Path(os.getcwd()).parent / 'quant'
    if str(_quant_path) not in __import__('sys').path:
        __import__('sys').path.insert(0, str(_quant_path))
    return visualizer


@flask_parity_router.get('/api/charts/accuracy')
@handle_api_error
def chart_accuracy(days: int = Query(90)):
    """模型准确率趋势图"""
    try:
        visualizer = _import_visualizer()
    except Exception:
        return error_response({'success': False, 'error': 'Chart module not available'}, 503)

    _CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(_CHART_DIR / 'accuracy_trend.png')

    result = visualizer.plot_model_accuracy_trend(days=days, output_path=output_path)

    image_b64 = None
    if Path(output_path).exists():
        image_b64 = _base64.b64encode(Path(output_path).read_bytes()).decode('utf-8')

    return api_response({
        'chart_data': sanitize_for_json(result),
        'image_base64': image_b64,
        'image_path': output_path,
    })


@flask_parity_router.get('/api/charts/equity')
@handle_api_error
def chart_equity(backtest_result: Optional[str] = Query(None)):
    """回测权益曲线图"""
    try:
        visualizer = _import_visualizer()
    except Exception:
        return error_response({'success': False, 'error': 'Chart module not available'}, 503)

    if backtest_result:
        backtest_result_obj = json.loads(backtest_result)
    else:
        latest = ds.backtest.get_all_backtests(limit=1)
        backtest_result_obj = latest[0] if latest else {}

    _CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(_CHART_DIR / 'equity_curve.png')

    result = visualizer.plot_equity_curve(backtest_result=backtest_result_obj, output_path=output_path)

    image_b64 = None
    if Path(output_path).exists():
        image_b64 = _base64.b64encode(Path(output_path).read_bytes()).decode('utf-8')

    return api_response({
        'chart_data': sanitize_for_json(result),
        'image_base64': image_b64,
    })


@flask_parity_router.get('/api/charts/comparison')
@handle_api_error
def chart_comparison(strategies_performance: Optional[str] = Query(None)):
    """策略对比图"""
    try:
        visualizer = _import_visualizer()
    except Exception:
        return error_response({'success': False, 'error': 'Chart module not available'}, 503)

    if strategies_performance:
        strategies_performance_obj = json.loads(strategies_performance)
    else:
        all_strategies = strategy_service.list_strategies()
        strategies_performance_obj = []
        for s in (all_strategies or [])[:10]:
            stats = ds.backtest.get_backtest_stats(strategy_name=str(s.get('id')))
            if stats:
                strategies_performance_obj.append({
                    'name': s.get('name', 'Unknown'),
                    'total_return': stats.get('avg_return', 0),
                    'sharpe_ratio': stats.get('avg_sharpe', 0),
                    'max_drawdown': stats.get('avg_max_drawdown', 0),
                })

    _CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(_CHART_DIR / 'strategy_comparison.png')

    result = visualizer.plot_strategy_comparison(strategies_performance=strategies_performance_obj, output_path=output_path)

    image_b64 = None
    if Path(output_path).exists():
        image_b64 = _base64.b64encode(Path(output_path).read_bytes()).decode('utf-8')

    return api_response({
        'chart_data': sanitize_for_json(result),
        'image_base64': image_b64,
    })


@flask_parity_router.get('/api/charts/importance')
@handle_api_error
def chart_importance(
    model_path: Optional[str] = Query(None),
    top_n: int = Query(20),
):
    """特征重要性图表"""
    try:
        visualizer = _import_visualizer()
    except Exception:
        return error_response({'success': False, 'error': 'Chart module not available'}, 503)

    _CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(_CHART_DIR / 'feature_importance.png')

    if model_path is None:
        model_path = str(Path(os.getcwd()) / 'ml' / 'models' / 'xgboost_latest.pkl')

    result = visualizer.plot_feature_importance(model_path=model_path, output_path=output_path)

    image_b64 = None
    if Path(output_path).exists():
        image_b64 = _base64.b64encode(Path(output_path).read_bytes()).decode('utf-8')

    return api_response({
        'chart_data': sanitize_for_json(result),
        'image_base64': image_b64,
    })
