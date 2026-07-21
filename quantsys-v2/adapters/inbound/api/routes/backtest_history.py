"""
回测历史查询和策略性能对比 API 路由
"""
from flask import Blueprint, jsonify, request
from adapters.inbound.api.shared import handle_api_error, api_response, convert_keys_to_camel
import logging

logger = logging.getLogger(__name__)

backtest_history_bp = Blueprint('backtest_history', __name__)


@backtest_history_bp.route('/api/backtest/history', methods=['GET'])
@handle_api_error
def get_backtest_history():
    """
    查询回测历史记录

    Query参数:
    - strategy_name: 策略名称（可选）
    - symbol: 股票代码（可选）
    - limit: 返回数量限制（默认20）

    返回:
    {
      "success": true,
      "data": [
        {
          "id": 1,
          "strategyName": "新能源动量策略 v1.0",
          "symbol": "300750.SZ",
          "startDate": "2025-01-01",
          "endDate": "2026-06-04",
          "annualReturn": 0.0959,
          "sharpeRatio": 1.71,
          "maxDrawdown": -0.0296,
          "totalTrades": 24,
          "winRate": 0.54,
          "createdAt": "2026-06-04T10:35:00"
        }
      ],
      "count": 1
    }
    """
    from adapters.outbound.repositories import BacktestORMRepository

    strategy_name = request.args.get('strategy_name')
    symbol = request.args.get('symbol')
    limit = request.args.get('limit', 20, type=int)

    backtest_repo = BacktestORMRepository()
    results = backtest_repo.get_all_backtests(
        strategy_name=strategy_name,
        symbol=symbol,
        limit=limit
    )

    # 转换 ORM 对象为字典，然后转换为驼峰命名
    results_dict = [r.to_dict() for r in results]
    results_camel = [convert_keys_to_camel(r) for r in results_dict]

    return api_response({
        'items': results_camel,
        'count': len(results_camel)
    })


@backtest_history_bp.route('/api/backtest/stats', methods=['GET'])
@handle_api_error
def get_backtest_stats():
    """
    获取回测统计信息

    Query参数:
    - strategy_name: 策略名称（可选）

    返回:
    {
      "success": true,
      "data": {
        "totalBacktests": 10,
        "avgSharpe": 1.25,
        "avgReturn": 0.08,
        "avgMaxDrawdown": -0.05,
        "bestSharpe": 1.71,
        "bestReturn": 0.12
      }
    }
    """
    from adapters.outbound.repositories import BacktestORMRepository

    strategy_name = request.args.get('strategy_name')

    backtest_repo = BacktestORMRepository()
    stats = backtest_repo.get_backtest_stats(strategy_name=strategy_name)

    # 转换为驼峰命名
    stats_camel = convert_keys_to_camel(stats)

    return api_response(stats_camel)


@backtest_history_bp.route('/api/strategies/performance-comparison', methods=['POST'])
@handle_api_error
def compare_strategy_performance():
    """
    对比多个策略的性能

    请求体:
    {
      "strategy_names": ["策略A", "策略B", "策略C"],
      "symbol": "300750.SZ",  // 可选：指定股票对比
      "metric": "sharpe_ratio"  // 可选：排序指标，默认 sharpe_ratio
    }

    返回:
    {
      "success": true,
      "data": {
        "comparison": [
          {
            "strategyName": "策略A",
            "avgSharpe": 1.71,
            "avgReturn": 0.0959,
            "avgDrawdown": -0.0296,
            "backtestCount": 3,
            "bestSymbol": "300750.SZ"
          }
        ],
        "ranking": ["策略A", "策略B", "策略C"]
      }
    }
    """
    from adapters.outbound.repositories import BacktestORMRepository

    data = request.get_json()
    strategy_names = data.get('strategy_names', [])
    symbol = data.get('symbol')
    metric = data.get('metric', 'sharpe_ratio')

    if not strategy_names:
        return jsonify({'success': False, 'error': '请提供至少一个策略名称'}), 400

    backtest_repo = BacktestORMRepository()
    comparison = []

    for strategy_name in strategy_names:
        stats = backtest_repo.get_backtest_stats(strategy_name=strategy_name)

        # 如果指定了symbol，获取该股票的回测记录
        if symbol:
            backtests = backtest_repo.get_backtests_by_strategy(strategy_name, symbol=symbol)
        else:
            backtests = backtest_repo.get_backtests_by_strategy(strategy_name, limit=100)

        # 找到最佳股票
        best_symbol = None
        best_metric_value = float('-inf')
        if backtests:
            for bt in backtests:
                value = bt.get(metric, 0) or 0
                if value > best_metric_value:
                    best_metric_value = value
                    best_symbol = bt.get('symbol')

        comparison.append({
            'strategy_name': strategy_name,
            'avg_sharpe': stats.get('avg_sharpe', 0),
            'avg_return': stats.get('avg_return', 0),
            'avg_max_drawdown': stats.get('avg_max_drawdown', 0),
            'backtest_count': stats.get('total_backtests', 0),
            'best_sharpe': stats.get('best_sharpe', 0),
            'best_symbol': best_symbol,
            'best_metric_value': best_metric_value
        })

    # 根据指标排序
    comparison.sort(key=lambda x: x.get(f'avg_{metric}', 0) or x.get('best_metric_value', 0), reverse=True)
    ranking = [c['strategy_name'] for c in comparison]

    # 转换为驼峰命名
    comparison_camel = [convert_keys_to_camel(c) for c in comparison]

    return api_response({
        'comparison': comparison_camel,
        'ranking': ranking
    })
