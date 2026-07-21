"""
回测历史 API (FastAPI 异步版本)

迁移自 Flask backtest_history.py

下方 flask_parity_router 为 Flask backtest.py 迁移（响应契约保持一致）：
- GET  /api/backtest/results
- POST /api/backtest/run
- GET  /api/performance/strategy/{strategy_id}
- GET  /api/performance/comparison
- POST /api/backtest/strategy
- POST /api/backtest/combo
"""
from datetime import datetime
import json

from fastapi import APIRouter, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog

from application.services.backtest_async_engine import BacktestAsyncEngine
from application.services.core_async_services import PerformanceAnalysisAsyncService

from adapters.inbound.fastapi_app.shared import (
    ds,
    api_response,
    error_response,
    handle_api_error,
    sanitize_for_json,
    convert_keys_to_snake,
    convert_keys_to_camel,
    strategy_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/backtest",
    tags=["Backtest - 回测历史"]
)


class ApiResponse(BaseModel):
    """API响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.get("/history", response_model=ApiResponse, summary="查询回测历史")
async def get_backtest_history(
    strategy_name: Optional[str] = Query(None, description="策略名称"),
    symbol: Optional[str] = Query(None, description="股票代码"),
    limit: int = Query(20, description="返回数量")
):
    """
    查询回测历史记录

    支持按策略名称和股票代码过滤
    """
    try:
        engine = BacktestAsyncEngine()

        results = await engine.get_recent_backtests(
            strategy_name=strategy_name,
            limit=limit
        )

        return {
            "success": True,
            "data": {
                "items": results,
                "count": len(results)
            }
        }

    except Exception as e:
        logger.exception(f"Get backtest history failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/stats", response_model=ApiResponse, summary="回测统计信息")
async def get_backtest_stats(
    strategy_name: Optional[str] = Query(None, description="策略名称")
):
    """
    获取回测统计信息

    包含总数、平均收益、最佳策略等
    """
    try:
        service = PerformanceAnalysisAsyncService()

        if strategy_name:
            stats = await service.analyze_strategy_performance(strategy_name)
        else:
            # 获取整体统计
            stats = {
                "totalBacktests": 0,
                "avgReturn": 0,
                "avgSharpe": 0
            }

        return {
            "success": True,
            "data": stats
        }

    except Exception as e:
        logger.exception(f"Get backtest stats failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/compare", response_model=ApiResponse, summary="策略性能对比")
async def compare_strategies(
    strategy_names: List[str] = Query(..., description="策略名称列表")
):
    """
    对比多个策略的性能
    """
    try:
        service = PerformanceAnalysisAsyncService()

        comparison = []
        for name in strategy_names:
            perf = await service.analyze_strategy_performance(name)
            comparison.append(perf)

        return {
            "success": True,
            "data": {
                "strategies": comparison,
                "count": len(comparison)
            }
        }

    except Exception as e:
        logger.exception(f"Compare strategies failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ═══════════════════════════════════════════════════════════════
# Flask backtest.py 迁移（parity 契约冻结，勿改业务逻辑）
# ═══════════════════════════════════════════════════════════════

flask_parity_router = APIRouter(tags=["Backtest - Flask parity 迁移"])


def _flask_jsonify_check(payload: Any) -> None:
    """模拟 Flask jsonify 的严格序列化（parity 契约）。

    Flask jsonify 遇到不可序列化对象（如 BacktestResult 领域对象）时抛
    TypeError("Object of type X is not JSON serializable")，被处理器内
    except 捕获后返回 500。FastAPI 默认 jsonable_encoder 会宽松地序列化
    __dict__，行为不同；此处用标准 json.dumps 复现 Flask 的严格失败。
    """
    json.dumps(payload)


@flask_parity_router.get('/api/backtest/results')
@handle_api_error
def get_backtest_results(symbol: Optional[str] = Query(None),
                         strategy: Optional[str] = Query(None),
                         limit: int = Query(20)):
    """Get backtest results with optional limit"""
    try:
        if symbol and strategy:
            results = ds.backtest.get_backtests_by_strategy(strategy, symbol=symbol)
        elif strategy:
            results = ds.backtest.get_backtests_by_strategy(strategy)
        else:
            results = ds.backtest.get_all_backtests(limit=limit)

        payload = {
            'success': True,
            'summary': sanitize_for_json(results),
            'count': len(results)
        }
        _flask_jsonify_check(payload)
        return payload

    except Exception as e:
        logger.error(f"Failed to get backtest results: {str(e)}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)


@flask_parity_router.post('/api/backtest/run')
@handle_api_error
def run_backtest_alias(payload: Optional[Dict[str, Any]] = Body(None)):
    """
    运行策略回测（CLI 入口）

    入参：
    {
        "strategy_id": 53,
        "symbol": "000001",
        "start_date": "2025-11-27",
        "end_date": "2026-05-27",
        "initial_capital": 100000,
        "period": null,              # 可选: null=日线, '5min'=5分钟线（启用T+1）
        "commission": 0.0003,      # 可选，暂不支持
        "slippage": 0.0005         # 可选，暂不支持
    }

    业务逻辑：
    1. 参数校验
    2. 加载策略代码（通过 strategy_id）
    3. 获取 K 线数据
    4. 策略信号生成
    5. 回测模拟（使用 StrategyCodeService）
    6. 指标计算
    7. 返回结果
    """
    data = payload
    if not data:
        return error_response({'success': False, 'error': '请求体不能为空'}, 400)

    data = convert_keys_to_snake(data)

    # 1. 参数校验
    required = ['strategy_id', 'symbol', 'start_date', 'end_date']
    for field in required:
        if field not in data:
            return error_response({'success': False, 'error': f'缺少必需参数: {field}'}, 400)

    try:
        strategy_id = int(data['strategy_id'])
        symbol = data['symbol']
        start_date = data['start_date']
        end_date = data['end_date']

        # 参数适配：initial_capital → initial_cash
        initial_cash = float(data.get('initial_capital', data.get('initial_cash', 1000000)))
        period = data.get('period', None)  # 分钟K线周期

        # commission 和 slippage 暂不支持（StrategyCodeService 内部使用固定值）
        if 'commission' in data or 'slippage' in data:
            logger.warning(f"commission/slippage 参数暂不支持，将使用默认值")

        # 2. 调用 StrategyCodeService.backtest_strategy()
        from application.services.strategy_code_service import StrategyCodeService
        service = StrategyCodeService()

        result = service.backtest_strategy(
            strategy_id=strategy_id,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            period=period
        )

        # 3. 转换为驼峰命名（CLI 兼容）
        result = convert_keys_to_camel(result)
        # DEBUG: attach period info
        result['_period'] = period
        result['_equity_len'] = len(result.get('equityCurve', []))
        result['_trades'] = result.get('totalTrades', 0)

        # 4. 自动保存回测结果到数据库
        try:
            from adapters.outbound.repositories import BacktestORMRepository
            backtest_repo = BacktestORMRepository()

            # 获取策略名称
            strategy = strategy_service.get_strategy(strategy_id)
            strategy_name = strategy.get('name', f'strategy_{strategy_id}')

            # 准备保存数据
            backtest_data = {
                'strategy_name': strategy_name,
                'symbol': symbol,
                'start_date': start_date,
                'end_date': end_date,
                'initial_capital': initial_cash,
                'final_capital': result.get('finalCapital', initial_cash),
                'total_return': result.get('totalReturn', 0),
                'annual_return': result.get('annualReturn', 0),
                'sharpe_ratio': result.get('sharpeRatio', 0),
                'max_drawdown': result.get('maxDrawdown', 0),
                'win_rate': result.get('winRate', 0),
                'total_trades': result.get('totalTrades', 0) or result.get('Trades', 0),
                'winning_trades': result.get('winningTrades', 0),
                'losing_trades': result.get('losingTrades', 0),
                'avg_win': result.get('avgWin', 0),
                'avg_loss': result.get('avgLoss', 0),
                'profit_factor': result.get('profitFactor', 0),
                'parameters': {'period': period} if period else {},
                'equity_curve': result.get('equityCurve', []),
                'trade_details': result.get('tradeDetails', [])
            }

            # 保存到数据库
            backtest_id = backtest_repo.save_backtest_result(backtest_data)
            result['_backtest_id'] = backtest_id
            logger.info(f"回测结果已保存，ID: {backtest_id}")

            # 5. 更新策略的metadata（记录最新回测）
            try:
                from adapters.outbound.repositories import StrategyORMRepository
                strategy_repo = StrategyORMRepository()

                # 获取当前metadata
                current_metadata = strategy.get('metadata') or {}

                # 更新last_backtest
                current_metadata['last_backtest'] = {
                    'backtest_id': backtest_id,
                    'date': datetime.now().isoformat(),
                    'symbol': symbol,
                    'annual_return': result.get('annualReturn', 0),
                    'sharpe_ratio': result.get('sharpeRatio', 0),
                    'max_drawdown': result.get('maxDrawdown', 0),
                    'total_trades': result.get('totalTrades', 0) or result.get('Trades', 0),
                    'win_rate': result.get('winRate', 0)
                }

                # 保存metadata
                strategy_repo.update_metadata(strategy_id, current_metadata)
                logger.info(f"策略 {strategy_id} 的 metadata 已更新")
            except Exception as meta_err:
                logger.warning(f"更新策略metadata失败: {str(meta_err)}")

        except Exception as save_err:
            logger.warning(f"保存回测结果失败（不影响返回）: {str(save_err)}")

        return api_response(result, message='回测完成')

    except ValueError as e:
        return error_response({'success': False, 'error': f'参数错误: {str(e)}'}, 400)
    except Exception as e:
        logger.error(f"回测失败: {str(e)}", exc_info=True)
        return error_response({'success': False, 'error': f'回测失败: {str(e)}'}, 500)


@flask_parity_router.get('/api/performance/strategy/{strategy_id}')
def get_strategy_performance(strategy_id: str):
    """获取策略表现"""
    try:
        results = ds.backtest.get_backtests_by_strategy(strategy_id, limit=20)
        stats = ds.backtest.get_backtest_stats(strategy_name=strategy_id)

        payload = sanitize_for_json({
            'strategy_id': strategy_id,
            'backtest_count': len(results),
            'stats': stats,
            'recent_results': results[:5]
        })
        _flask_jsonify_check(payload)
        return payload
    except Exception as e:
        return error_response({'error': str(e)}, 500)


@flask_parity_router.get('/api/performance/comparison')
@handle_api_error
def get_performance_comparison(days: int = Query(30)):
    """多策略性能对比（兼容 Express 前端）"""
    all_strategies = strategy_service.list_strategies()

    comparisons = []
    for s in (all_strategies or []):
        sid = str(s.get('id', ''))
        stats = ds.backtest.get_backtest_stats(strategy_name=sid)
        if stats:
            comparisons.append({
                'strategy_id': sid,
                'name': s.get('name', 'Unknown'),
                'type': s.get('code_type', 'strategy'),
                'avg_return': stats.get('avg_return', 0),
                'avg_sharpe': stats.get('avg_sharpe', 0),
                'avg_max_drawdown': stats.get('avg_max_drawdown', 0),
                'avg_win_rate': stats.get('avg_win_rate', 0),
                'backtest_count': stats.get('count', 0),
            })

    return api_response({'strategies': comparisons, 'count': len(comparisons)})


@flask_parity_router.post('/api/backtest/strategy')
@handle_api_error
def backtest_strategy_v2(payload: Optional[Dict[str, Any]] = Body(None)):
    """
    单资产策略回测（v2 - 使用 StrategyCodeService）

    返回 15 个指标：
    - 基础：total_return, annual_return, sharpe_ratio, sortino_ratio, calmar_ratio, max_drawdown
    - 风险：volatility, downside_volatility
    - 交易：win_rate, profit_loss_ratio, avg_holding_days, trade_frequency,
            max_consecutive_wins, max_consecutive_losses, profit_factor
    """
    data = payload
    if not data:
        return error_response({'success': False, 'error': '请求体不能为空'}, 400)

    data = convert_keys_to_snake(data)

    # 验证必需参数
    required = ['strategy_id', 'symbol', 'start_date', 'end_date']
    for field in required:
        if field not in data:
            return error_response({'success': False, 'error': f'缺少必需参数: {field}'}, 400)

    try:
        strategy_id = int(data['strategy_id'])
        symbol = data['symbol']
        start_date = data['start_date']
        end_date = data['end_date']
        initial_cash = float(data.get('initial_cash', 1000000))

        # 调用 StrategyCodeService
        from application.services.strategy_code_service import StrategyCodeService
        service = StrategyCodeService()

        result = service.backtest_strategy(
            strategy_id=strategy_id,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash
        )

        # 转换为驼峰命名（前端兼容）
        result = convert_keys_to_camel(result)

        return api_response(result, message='回测完成')

    except ValueError as e:
        return error_response({'success': False, 'error': f'参数错误: {str(e)}'}, 400)
    except Exception as e:
        logger.error(f"回测失败: {str(e)}", exc_info=True)
        return error_response({'success': False, 'error': f'回测失败: {str(e)}'}, 500)


@flask_parity_router.post('/api/backtest/combo')
def combo_backtest(payload: Optional[Dict[str, Any]] = Body(None)):
    """Combo strategy backtest endpoint."""
    from adapters.inbound.api.shared import combo_backtest_service

    data = payload
    if not data:
        return error_response({'success': False, 'error': 'Request body required'}, 400)

    # Validate required params
    mode = data.get('mode')
    strategies = data.get('strategies')
    symbols = data.get('symbols')

    if not mode or not strategies or not symbols:
        return error_response({
            'success': False,
            'error': 'mode, strategies, and symbols are required'
        }, 400)

    if mode not in ['portfolio', 'ensemble', 'pipeline']:
        return error_response({
            'success': False,
            'error': f'Invalid mode: {mode}. Must be portfolio, ensemble, or pipeline'
        }, 400)

    try:
        result = combo_backtest_service.backtest_combo(
            mode=mode,
            strategies=strategies,
            symbols=symbols,
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            initial_capital=data.get('initial_capital', 1000000.0),
            ensemble_method=data.get('ensemble_method', 'weighted'),
            pipeline_config=data.get('pipeline_config', {})
        )

        return {'success': True, 'data': result}

    except ValueError as e:
        logger.warning(f"Combo backtest validation error: {e}")
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error(f"Combo backtest failed: {e}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)
