"""
Portfolio optimization API routes
"""
from flask import Blueprint, request
from adapters.inbound.api.shared import api_response, handle_api_error
from domain.quantlib.portfolio.markowitz import MarkowitzOptimizer
from domain.quantlib.portfolio.black_litterman import BlackLittermanOptimizer
from domain.quantlib.portfolio.risk_parity import RiskParityOptimizer
import numpy as np

portfolio_bp = Blueprint('portfolio', __name__)


def _convert_numpy_to_list(obj):
    """递归转换 numpy 数组为 Python 列表，以支持 JSON 序列化"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: _convert_numpy_to_list(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_to_list(item) for item in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    else:
        return obj


@portfolio_bp.route('/api/portfolio/markowitz/optimize', methods=['POST'])
@handle_api_error
def markowitz_optimize():
    """Markowitz 均值方差优化"""
    data = request.get_json()

    expected_returns = data.get('expected_returns')
    cov_matrix = data.get('covariance_matrix')
    objective = data.get('method', 'max_sharpe')
    target_return = data.get('target_return')
    risk_free_rate = data.get('risk_free_rate', 0.0)
    lower_bound = data.get('lower_bound', 0.0)
    upper_bound = data.get('upper_bound', 1.0)
    allow_short = data.get('allow_short', False)

    if not expected_returns or not cov_matrix:
        return api_response(None, success=False, message="expected_returns and covariance_matrix are required")

    # 转换为 numpy 数组
    expected_returns = np.array(expected_returns)
    cov_matrix = np.array(cov_matrix)

    # 创建优化器
    optimizer = MarkowitzOptimizer(risk_free_rate=risk_free_rate)

    # 执行优化
    result = optimizer.optimize(
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        objective=objective,
        target_return=target_return,
        risk_free_rate=risk_free_rate,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        allow_short=allow_short
    )

    # 转换 numpy 数组为列表
    result = _convert_numpy_to_list(result)

    return api_response(result)


@portfolio_bp.route('/api/portfolio/black-litterman/optimize', methods=['POST'])
@handle_api_error
def black_litterman_optimize():
    """Black-Litterman 模型优化"""
    data = request.get_json()

    market_weights = data.get('market_weights')
    cov_matrix = data.get('covariance_matrix')
    views = data.get('views')
    risk_aversion = data.get('risk_aversion', 2.5)
    tau = data.get('tau', 0.025)
    risk_free_rate = data.get('risk_free_rate', 0.0)

    if not market_weights or not cov_matrix:
        return api_response(None, success=False, message="market_weights and covariance_matrix are required")

    # 转换为 numpy 数组
    market_weights = np.array(market_weights)
    cov_matrix = np.array(cov_matrix)

    # 创建优化器
    optimizer = BlackLittermanOptimizer(risk_free_rate=risk_free_rate)

    # 执行优化
    result = optimizer.optimize(
        market_weights=market_weights,
        cov_matrix=cov_matrix,
        views=views,
        risk_aversion=risk_aversion,
        tau=tau,
        risk_free_rate=risk_free_rate
    )

    # 转换 numpy 数组为列表
    result = _convert_numpy_to_list(result)

    return api_response(result)


@portfolio_bp.route('/api/portfolio/risk-parity/optimize', methods=['POST'])
@handle_api_error
def risk_parity_optimize():
    """Risk Parity 风险平价优化"""
    data = request.get_json()

    cov_matrix = data.get('covariance_matrix')
    target_risk = data.get('target_risk')
    target_volatility = data.get('target_volatility')
    lower_bound = data.get('lower_bound', 0.0)
    upper_bound = data.get('upper_bound', 1.0)
    risk_free_rate = data.get('risk_free_rate', 0.0)

    if not cov_matrix:
        return api_response(None, success=False, message="covariance_matrix is required")

    # 转换为 numpy 数组
    cov_matrix = np.array(cov_matrix)
    if target_risk:
        target_risk = np.array(target_risk)

    # 创建优化器
    optimizer = RiskParityOptimizer(risk_free_rate=risk_free_rate)

    # 执行优化
    result = optimizer.optimize(
        cov_matrix=cov_matrix,
        target_risk=target_risk,
        target_volatility=target_volatility,
        lower_bound=lower_bound,
        upper_bound=upper_bound
    )

    # 转换 numpy 数组为列表
    result = _convert_numpy_to_list(result)

    return api_response(result)


@portfolio_bp.route('/api/portfolio/risk-parity/risk-decomposition', methods=['POST'])
@handle_api_error
def risk_parity_decomposition():
    """Risk Parity 风险分解"""
    data = request.get_json()

    weights = data.get('weights')
    cov_matrix = data.get('covariance_matrix')

    if not weights or not cov_matrix:
        return api_response(None, success=False, message="weights and covariance_matrix are required")

    # 转换为 numpy 数组
    weights = np.array(weights)
    cov_matrix = np.array(cov_matrix)

    # 创建优化器
    optimizer = RiskParityOptimizer()

    # 计算风险分解
    result = optimizer.calculate_risk_decomposition(
        weights=weights,
        cov_matrix=cov_matrix
    )

    # 转换 numpy 数组为列表
    result = _convert_numpy_to_list(result)

    return api_response(result)


@portfolio_bp.route('/api/portfolio', methods=['GET'])
@handle_api_error
def get_portfolio():
    """
    获取当前持仓

    Response:
    {
        "success": true,
        "data": {
            "holdings": [...],
            "total_value": 100000.0,
            "total_cost": 90000.0,
            "total_pnl": 10000.0,
            "total_pnl_pct": 0.1111,
            "cash": 50000.0,
            "last_updated": "2026-06-24T15:00:00"
        }
    }
    """
    from pathlib import Path
    import json
    from datetime import datetime

    try:
        # 读取 .pi-invest/portfolio.json
        pi_dir = Path.cwd().parent / '.pi-invest'
        portfolio_path = pi_dir / 'portfolio.json'

        if not portfolio_path.exists():
            # 返回空持仓
            return api_response({
                'holdings': [],
                'total_value': 0,
                'total_cost': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'cash': 0,
                'last_updated': datetime.now().isoformat()
            })

        # 读取并返回持仓数据
        with open(portfolio_path, 'r', encoding='utf-8') as f:
            portfolio_data = json.load(f)

        return api_response(portfolio_data)

    except Exception as e:
        return api_response(None, success=False, message=f"读取持仓失败: {str(e)}")


@portfolio_bp.route('/api/portfolio/holdings', methods=['GET'])
@handle_api_error
def get_holdings():
    """获取持仓列表"""
    from pathlib import Path
    import json

    try:
        pi_dir = Path.cwd().parent / '.pi-invest'
        portfolio_path = pi_dir / 'portfolio.json'

        if not portfolio_path.exists():
            return api_response([])

        with open(portfolio_path, 'r', encoding='utf-8') as f:
            portfolio_data = json.load(f)

        return api_response(portfolio_data.get('holdings', []))

    except Exception as e:
        return api_response(None, success=False, message=f"读取持仓失败: {str(e)}")


@portfolio_bp.route('/api/portfolio/stats', methods=['GET'])
@handle_api_error
def get_portfolio_stats():
    """获取持仓统计"""
    from pathlib import Path
    import json

    try:
        pi_dir = Path.cwd().parent / '.pi-invest'
        portfolio_path = pi_dir / 'portfolio.json'

        if not portfolio_path.exists():
            return api_response({
                'total_value': 0,
                'total_cost': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'position_count': 0,
                'cash': 0
            })

        with open(portfolio_path, 'r', encoding='utf-8') as f:
            portfolio_data = json.load(f)

        stats = {
            'total_value': portfolio_data.get('total_value', 0),
            'total_cost': portfolio_data.get('total_cost', 0),
            'total_pnl': portfolio_data.get('total_pnl', 0),
            'total_pnl_pct': portfolio_data.get('total_pnl_pct', 0),
            'position_count': len(portfolio_data.get('holdings', [])),
            'cash': portfolio_data.get('cash', 0)
        }

        return api_response(stats)

    except Exception as e:
        return api_response(None, success=False, message=f"读取统计失败: {str(e)}")


@portfolio_bp.route('/api/portfolio/optimize', methods=['POST'])
@handle_api_error
def optimize_portfolio():
    """
    组合优化
    
    使用 cvxpy 进行科学的组合权重优化
    
    Request:
    {
        "symbols": ["600000.SH", "600519.SH", "000858.SZ"],
        "expected_returns": [0.10, 0.15, 0.08],  // 可选，不提供则自动估计
        "method": "mean_variance",  // mean_variance, min_variance, max_sharpe, risk_parity
        "risk_aversion": 1.0,  // 风险厌恶系数
        "risk_free_rate": 0.02,  // 无风险利率
        "constraints": {
            "long_only": true,
            "max_weight": 0.3,
            "min_weight": 0.05
        },
        "start_date": "2024-01-01",  // 用于估计参数
        "end_date": "2024-12-31"
    }
    
    Response:
    {
        "success": true,
        "data": {
            "weights": {
                "600000.SH": 0.35,
                "600519.SH": 0.40,
                "000858.SZ": 0.25
            },
            "expected_return": 0.125,
            "risk": 0.18,
            "sharpe": 0.58,
            "method": "mean_variance"
        }
    }
    """
    from application.services.portfolio_optimization_service import PortfolioOptimizationService
    import numpy as np
    
    data = request.get_json() or {}
    
    # 参数验证
    symbols = data.get('symbols')
    if not symbols:
        return jsonify({
            'success': False,
            'error': 'symbols 参数不能为空'
        }), 400
    
    method = data.get('method', 'mean_variance')
    if method not in ['mean_variance', 'min_variance', 'max_sharpe', 'risk_parity']:
        return jsonify({
            'success': False,
            'error': f'不支持的优化方法: {method}'
        }), 400
    
    try:
        # 获取或估计参数
        expected_returns = data.get('expected_returns')
        cov_matrix = data.get('cov_matrix')
        
        # 如果没有提供，从历史数据估计
        if expected_returns is None or cov_matrix is None:
            # TODO: 从历史数据估计收益率和协方差
            # 这里暂时使用示例数据
            n = len(symbols)
            expected_returns = np.random.uniform(0.05, 0.15, n)
            cov_matrix = np.eye(n) * 0.04
        else:
            expected_returns = np.array(expected_returns)
            cov_matrix = np.array(cov_matrix)
        
        # 其他参数
        risk_aversion = data.get('risk_aversion', 1.0)
        risk_free_rate = data.get('risk_free_rate', 0.02)
        constraints = data.get('constraints', {})
        
        # 创建优化服务
        service = PortfolioOptimizationService()
        
        # 根据方法选择优化算法
        if method == 'mean_variance':
            result = service.mean_variance_optimization(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                risk_aversion=risk_aversion,
                constraints=constraints
            )
        elif method == 'min_variance':
            result = service.minimum_variance(
                cov_matrix=cov_matrix,
                constraints=constraints
            )
        elif method == 'max_sharpe':
            result = service.maximum_sharpe(
                expected_returns=expected_returns,
                cov_matrix=cov_matrix,
                risk_free_rate=risk_free_rate,
                constraints=constraints
            )
        elif method == 'risk_parity':
            result = service.risk_parity(
                cov_matrix=cov_matrix,
                constraints=constraints
            )
        
        # 转换权重数组为字典
        weights_dict = {
            symbol: float(weight)
            for symbol, weight in zip(symbols, result['weights'])
        }
        
        # 构建响应
        response_data = {
            'weights': weights_dict,
            'method': method
        }
        
        # 添加其他指标
        if 'expected_return' in result:
            response_data['expected_return'] = float(result['expected_return'])
        if 'risk' in result:
            response_data['risk'] = float(result['risk'])
        if 'sharpe' in result:
            response_data['sharpe'] = float(result['sharpe'])
        if 'risk_contributions' in result:
            response_data['risk_contributions'] = {
                symbol: float(contrib)
                for symbol, contrib in zip(symbols, result['risk_contributions'])
            }
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"组合优化失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
