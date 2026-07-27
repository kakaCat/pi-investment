"""
backtest routes.
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, jsonify, request

import math

logger = logging.getLogger(__name__)

from adapters.inbound.api.shared import (
    ds,
    api_response,
    handle_api_error,
    sanitize_for_json,
    convert_keys_to_snake,
    convert_keys_to_camel,
    _safe_float,
    _V2_ROOT,
    _PROJECT_ROOT_PATH,
    _LEGACY_QUANT_ROOT,
    _load_pipeline_runs,
    _save_pipeline_runs,
    _get_pipeline_run,
    _update_pipeline_run,
    acquire_task,
    release_task,
    get_running_tasks_snapshot,
    strategy_service,
    stock_pool_service,
    factor_adapter,
    scoring_service,
    _read_watchlist,
    _write_watchlist,
    _read_groups,
    _write_groups,
    _parse_sina_a_quote,
    _parse_sina_hk_quote,
    to_camel_case,
    to_snake_case,
    get_query_params_snake_case,
    enrich_stock_data,
    signal_to_opportunity,
)

backtest_bp = Blueprint('backtest', __name__)

@backtest_bp.route('/api/backtest/results', methods=['GET'])
@handle_api_error
def get_backtest_results():
    """Get backtest results with optional limit"""
    try:
        symbol = request.args.get('symbol')
        strategy_name = request.args.get('strategy')
        limit = request.args.get('limit', 20, type=int)

        if symbol and strategy_name:
            results = ds.backtest.get_backtests_by_strategy(strategy_name, symbol=symbol)
        elif strategy_name:
            results = ds.backtest.get_backtests_by_strategy(strategy_name)
        else:
            results = ds.backtest.get_all_backtests(limit=limit)

        return jsonify({
            'success': True,
            'summary': sanitize_for_json(results),
            'count': len(results)
        })

    except Exception as e:
        logger.error(f"Failed to get backtest results: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@backtest_bp.route('/api/backtest', methods=['POST'])
def run_backtest():
    """运行回测 - 支持 strategy_name、strategy_id 或 indicator_id"""
    raw_data = request.get_json() or {}

    data = convert_keys_to_snake(raw_data)

    if 'strategy' in data and 'strategy_name' not in data:
        data['strategy_name'] = data['strategy']

    # 处理 indicator_id（指标回测）
    if 'indicator_id' in data and 'strategy_name' not in data:
        try:
            indicator_id = int(data['indicator_id'])
            # 指标回测使用特殊的策略名称
            data['strategy_name'] = f"indicator_{indicator_id}"
            logger.info(f"Running indicator backtest for indicator_id={indicator_id}")
        except (ValueError, TypeError) as e:
            return jsonify({'error': f'无效的 indicator_id: {e}'}), 400

    if 'strategy_id' in data and 'strategy_name' not in data:
        try:
            strat = strategy_service.get_strategy(int(data['strategy_id']))
            if not strat:
                return jsonify({'error': f'策略不存在: {data["strategy_id"]}'}), 404
            data['strategy_name'] = strat.get('name') or f"strategy_{data['strategy_id']}"
        except (ValueError, TypeError) as e:
            return jsonify({'error': f'无效的 strategy_id: {e}'}), 400

    if 'parameters' not in data and isinstance(data.get('params'), dict):
        data['parameters'] = data['params']

    if 'parameters' in data and isinstance(data['parameters'], dict):
        params = data['parameters']

        param_mappings = {
            'fast_period': 'ma_short',
            'slow_period': 'ma_long',
            'rsi_period': 'rsi_period',
            'short_period': 'ma_short',
            'long_period': 'ma_long',
            # PE均值回归参数
            'pe_heavy_buy': 'pe_heavy_buy',
            'pe_batch_buy': 'pe_batch_buy',
            'pe_reduce': 'pe_reduce',
            'pe_liquidate': 'pe_liquidate',
            'eps_start': 'eps_start',
            'eps_end': 'eps_end',
            'stop_loss_pct': 'stop_loss_pct',
            'take_profit_pct': 'take_profit_pct',
            'dividend_yield': 'dividend_yield',
            # PB均值回归参数
            'pb_heavy_buy': 'pb_heavy_buy',
            'pb_batch_buy': 'pb_batch_buy',
            'pb_reduce': 'pb_reduce',
            'pb_liquidate': 'pb_liquidate',
            'roe_mean': 'roe_mean',
        }

        for source_key, target_key in param_mappings.items():
            if source_key in params and target_key not in data:
                data[target_key] = params[source_key]

        del data['parameters']
    data.pop('params', None)

    # 处理 initialCash -> initial_capital 映射
    if 'initial_cash' in data and 'initial_capital' not in data:
        data['initial_capital'] = data['initial_cash']

    required = ['strategy_name', 'symbol', 'start_date', 'end_date', 'initial_capital']
    for field in required:
        if field not in data:
            return jsonify({'error': f'缺少必需参数: {field}'}), 400

    strategy_name = data['strategy_name'].lower()
    # 对于指标回测，不需要额外的策略参数验证
    if 'indicator' not in strategy_name:
        if 'ma' in strategy_name or 'cross' in strategy_name:
            if 'ma_short' not in data:
                return jsonify({'error': '移动平均策略缺少参数: ma_short (或 fastPeriod)'}), 400
            if 'ma_long' not in data:
                return jsonify({'error': '移动平均策略缺少参数: ma_long (或 slowPeriod)'}), 400
        elif 'rsi' in strategy_name:
            if 'rsi_period' not in data:
                return jsonify({'error': 'RSI策略缺少参数: rsi_period (或 rsiPeriod)'}), 400
        elif 'pe' in strategy_name and 'mean' in strategy_name:
            # PE均值回归 — 参数都来自 parameters 字段（peLow/peHigh），有默认值
            pass

    try:
        workflow_data = ds.get_backtest_workflow_data(
            data['symbol'],
            data['start_date'],
            data['end_date'],
            period=data.get('period')
        )

        klines = workflow_data['klines']
        if not klines:
            return jsonify({'error': '没有K线数据'}), 400

        initial_capital = float(data['initial_capital'])

        if 'pe' in strategy_name and 'mean' in strategy_name:
            result = run_pe_mean_reversion_backtest(data, klines, initial_capital)
        elif 'pb' in strategy_name and 'mean' in strategy_name:
            result = run_pb_mean_reversion_backtest(data, klines, initial_capital)
        else:
            result = save_simple_backtest(data, klines, initial_capital)
        result = convert_keys_to_camel(result)
        return jsonify(sanitize_for_json(result))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@backtest_bp.route('/api/backtest/run', methods=['POST'])
@handle_api_error
def run_backtest_alias():
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
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400

    data = convert_keys_to_snake(data)

    # 1. 参数校验
    required = ['strategy_id', 'symbol', 'start_date', 'end_date']
    for field in required:
        if field not in data:
            return jsonify({'success': False, 'error': f'缺少必需参数: {field}'}), 400

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
        return jsonify({'success': False, 'error': f'参数错误: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"回测失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f'回测失败: {str(e)}'}), 500


# 回测执行助手（已解耦到中立层，向后兼容再导出）
from adapters.shared.backtest_helpers import (
    save_simple_backtest, run_pe_mean_reversion_backtest, run_pb_mean_reversion_backtest,
)
@backtest_bp.route('/api/performance/strategy/<strategy_id>', methods=['GET'])
def get_strategy_performance(strategy_id):
    """获取策略表现"""
    try:
        results = ds.backtest.get_backtests_by_strategy(strategy_id, limit=20)
        stats = ds.backtest.get_backtest_stats(strategy_name=strategy_id)

        return jsonify(sanitize_for_json({
            'strategy_id': strategy_id,
            'backtest_count': len(results),
            'stats': stats,
            'recent_results': results[:5]
        }))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@backtest_bp.route('/api/performance/comparison', methods=['GET'])
@handle_api_error
def get_performance_comparison():
    """多策略性能对比（兼容 Express 前端）"""
    days = request.args.get('days', 30, type=int)
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


@backtest_bp.route('/api/backtest/strategy', methods=['POST'])
@handle_api_error
def backtest_strategy_v2():
    """
    单资产策略回测（v2 - 使用 StrategyCodeService）

    返回 15 个指标：
    - 基础：total_return, annual_return, sharpe_ratio, sortino_ratio, calmar_ratio, max_drawdown
    - 风险：volatility, downside_volatility
    - 交易：win_rate, profit_loss_ratio, avg_holding_days, trade_frequency,
            max_consecutive_wins, max_consecutive_losses, profit_factor
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400

    data = convert_keys_to_snake(data)

    # 验证必需参数
    required = ['strategy_id', 'symbol', 'start_date', 'end_date']
    for field in required:
        if field not in data:
            return jsonify({'success': False, 'error': f'缺少必需参数: {field}'}), 400

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
        return jsonify({'success': False, 'error': f'参数错误: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"回测失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f'回测失败: {str(e)}'}), 500


@backtest_bp.route('/api/backtest/portfolio', methods=['POST'])
@handle_api_error
def backtest_portfolio():
    """
    多资产组合回测（带风险归因）

    请求体：
    {
        "strategyIds": [1, 2, 3],
        "symbols": ["000001.SH", "000858.SZ", "601318.SH"],
        "weights": [0.4, 0.3, 0.3],
        "startDate": "2023-01-01",
        "endDate": "2024-01-01",
        "initialCash": 1000000,
        "enableAttribution": true
    }

    返回：
    {
        "success": true,
        "data": {
            "totalReturn": 0.15,
            "sharpeRatio": 1.8,
            ...其他15个指标,
            "attribution": {
                "portfolioVolatility": 0.2156,
                "contributions": {
                    "000001.SH": {
                        "weight": 0.4,
                        "volatility": 0.25,
                        "percentageContribution": 45.2,
                        "correlationWithPortfolio": 0.92
                    },
                    ...
                }
            },
            "assets": [...],
            "portfolioEquityCurve": [...]
        }
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400

    data = convert_keys_to_snake(data)

    # 验证必需参数
    required = ['strategy_ids', 'symbols', 'weights', 'start_date', 'end_date']
    for field in required:
        if field not in data:
            return jsonify({'success': False, 'error': f'缺少必需参数: {field}'}), 400

    try:
        strategy_ids = data['strategy_ids']
        symbols = data['symbols']
        weights = data['weights']
        start_date = data['start_date']
        end_date = data['end_date']
        initial_cash = float(data.get('initial_cash', 1000000))
        enable_attribution = data.get('enable_attribution', True)

        # 验证列表长度一致
        if len(strategy_ids) != len(symbols) or len(symbols) != len(weights):
            return jsonify({
                'success': False,
                'error': f'策略、股票、权重数量必须一致: {len(strategy_ids)}, {len(symbols)}, {len(weights)}'
            }), 400

        # 验证权重和为1
        import numpy as np
        if not np.isclose(sum(weights), 1.0, atol=0.01):
            return jsonify({
                'success': False,
                'error': f'权重必须和为1，当前为 {sum(weights)}'
            }), 400

        # 调用 StrategyCodeService
        from application.services.strategy_code_service import StrategyCodeService
        service = StrategyCodeService()

        result = service.backtest_portfolio(
            strategy_ids=strategy_ids,
            symbols=symbols,
            weights=weights,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            enable_attribution=enable_attribution
        )

        # 转换为驼峰命名（前端兼容）
        result = convert_keys_to_camel(result)

        return api_response(result, message='组合回测完成')

    except ValueError as e:
        return jsonify({'success': False, 'error': f'参数错误: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"组合回测失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f'组合回测失败: {str(e)}'}), 500


# ═══════════════════════════════════════════════════════════════
# 批量回测
# ═══════════════════════════════════════════════════════════════

@backtest_bp.route('/api/backtest/batch', methods=['POST'])
@handle_api_error
def run_backtest_batch():
    """
    批量回测：对多个 (strategy_id, symbol) 组合依次回测，返回排名汇总。

    入参：
    {
        "jobs": [
            {"strategy_id": 53, "symbol": "000001", "start_date": "2025-01-01", "end_date": "2026-01-01"},
            {"strategy_id": 53, "symbol": "000425", "start_date": "2025-01-01", "end_date": "2026-01-01"}
        ],
        "initial_capital": 100000   # 可选，默认100万
    }

    返回：
    {
        "success": true,
        "data": {
            "summary": {"total": 5, "profitable": 2, "best": {...}, "worst": {...}},
            "results": [...],
            "errors": [...]
        }
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400

    data = convert_keys_to_snake(data)

    jobs = data.get('jobs', [])
    if not jobs:
        return jsonify({'success': False, 'error': 'jobs 不能为空'}), 400

    global_initial_capital = float(data.get('initial_capital', 1000000))

    from application.services.strategy_code_service import StrategyCodeService
    from concurrent.futures import ThreadPoolExecutor, as_completed

    service = StrategyCodeService()

    results = []
    errors = []

    logger.info(f"批量回测开始: {len(jobs)} 个任务")

    # 并发执行回测任务
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for job in jobs:
            future = executor.submit(
                service.backtest_strategy,
                strategy_id=int(job['strategy_id']),
                symbol=job['symbol'],
                start_date=job.get('start_date', '2025-01-01'),
                end_date=job.get('end_date', datetime.now().strftime('%Y-%m-%d')),
                initial_cash=float(job.get('initial_capital', global_initial_capital)),
                period=job.get('period', None)
            )
            futures[future] = job

        for future in as_completed(futures):
            job = futures[future]
            try:
                result = future.result(timeout=300)  # 5分钟超时

                # 只保留关键指标，不返回完整 trades（太大）
                results.append({
                    'strategy_id': job['strategy_id'],
                    'symbol': job['symbol'],
                    'period': job.get('period', 'daily'),
                    'total_return': result['total_return'],
                    'annual_return': result['annual_return'],
                    'sharpe_ratio': result['sharpe_ratio'],
                    'max_drawdown': result['max_drawdown'],
                    'win_rate': result['win_rate'],
                    'profit_factor': result.get('profit_factor', 0),
                    'total_trades': result['total_trades'],
                    'start_date': job.get('start_date', '2025-01-01'),
                    'end_date': job.get('end_date', datetime.now().strftime('%Y-%m-%d')),
                })
            except TimeoutError:
                logger.error(f"回测超时: {job}")
                errors.append({
                    'strategy_id': job.get('strategy_id'),
                    'symbol': job.get('symbol'),
                    'error': '回测超时（5分钟）'
                })
            except Exception as e:
                logger.error(f"回测失败: {job}, error={e}")
                errors.append({
                    'strategy_id': job.get('strategy_id'),
                    'symbol': job.get('symbol'),
                    'error': str(e)
                })

    # 排名：按 total_return 降序
    results.sort(key=lambda r: r['total_return'], reverse=True)

    profitable = [r for r in results if r['total_return'] > 0]

    summary = {
        'total': len(jobs),
        'success': len(results),
        'errors': len(errors),
        'profitable': len(profitable),
        'best': results[0] if results else None,
        'worst': results[-1] if results else None,
    }

    logger.info(f"批量回测完成: 成功={len(results)}, 失败={len(errors)}")

    return api_response({
        'summary': summary,
        'results': results,
        'errors': errors if errors else None,
    }, message=f'{len(results)}/{len(jobs)} 完成')


@backtest_bp.route('/api/backtest/combo', methods=['POST'])
def combo_backtest():
    """Combo strategy backtest endpoint."""
    from adapters.inbound.api.shared import combo_backtest_service
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400
    
    # Validate required params
    mode = data.get('mode')
    strategies = data.get('strategies')
    symbols = data.get('symbols')
    
    if not mode or not strategies or not symbols:
        return jsonify({
            'success': False,
            'error': 'mode, strategies, and symbols are required'
        }), 400
    
    if mode not in ['portfolio', 'ensemble', 'pipeline']:
        return jsonify({
            'success': False,
            'error': f'Invalid mode: {mode}. Must be portfolio, ensemble, or pipeline'
        }), 400
    
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
        
        return jsonify({'success': True, 'data': result})
        
    except ValueError as e:
        logger.warning(f"Combo backtest validation error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Combo backtest failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# 因子分层回测端点
# ============================================================================

@backtest_bp.route('/api/backtest/factor-layering', methods=['POST'])
def factor_layering_backtest():
    """
    因子分层回测
    
    Request:
        {
            "factor_name": "reversal_1d",
            "symbols": ["600519", "000858"],  // 可选
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "n_quantiles": 10,  // 可选，默认10
            "holding_period": 20  // 可选，默认20
        }
    
    Response:
        {
            "success": true,
            "factor_name": "reversal_1d",
            "effectiveness_score": 8.5,
            "layer_stats": {...},
            "ic_stats": {...},
            ...
        }
    """
    from application.services.factor_layering_service import FactorLayeringService
    
    data = request.get_json() or {}
    factor_name = data.get('factor_name')
    
    if not factor_name:
        return jsonify({
            'success': False,
            'error': 'factor_name is required'
        }), 400
    
    try:
        service = FactorLayeringService()
        result = service.run_layering_backtest(
            factor_name=factor_name,
            symbols=data.get('symbols'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            n_quantiles=data.get('n_quantiles', 10),
            holding_period=data.get('holding_period', 20)
        )

        # 使用 api_response 自动处理 NaN 序列化
        from adapters.inbound.api.shared import api_response
        return api_response(result)
        
    except Exception as e:
        logger.error(f"Factor layering backtest failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@backtest_bp.route('/api/backtest/factor-layering/batch', methods=['POST'])
def batch_factor_layering_backtest():
    """
    批量因子分层回测
    
    Request:
        {
            "factor_names": ["reversal_1d", "momentum_6m", "rsi14"],
            "symbols": [...],  // 可选
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "n_quantiles": 10
        }
    
    Response:
        {
            "success": true,
            "count": 3,
            "results": [...],
            "ranking": [
                {"factor_name": "reversal_1d", "effectiveness_score": 8.5, ...},
                ...
            ]
        }
    """
    from application.services.factor_layering_service import FactorLayeringService
    
    data = request.get_json() or {}
    factor_names = data.get('factor_names')
    
    if not factor_names or not isinstance(factor_names, list):
        return jsonify({
            'success': False,
            'error': 'factor_names (list) is required'
        }), 400
    
    try:
        service = FactorLayeringService()
        result = service.run_batch_layering_backtest(
            factor_names=factor_names,
            symbols=data.get('symbols'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            n_quantiles=data.get('n_quantiles', 10)
        )

        # 使用 api_response 自动处理 NaN 序列化
        from adapters.inbound.api.shared import api_response
        return api_response(result)
        
    except Exception as e:
        logger.error(f"Batch factor layering backtest failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
