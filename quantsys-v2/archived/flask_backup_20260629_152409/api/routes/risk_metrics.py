"""
风险指标 API 路由
"""
from flask import Blueprint, request, jsonify
from application.services.risk_metrics_service import RiskMetricsService
from adapters.inbound.api.utils.validators import validate_required_fields
import logging

logger = logging.getLogger(__name__)

risk_metrics_bp = Blueprint('risk_metrics', __name__, url_prefix='/api/risk')


@risk_metrics_bp.route('/metrics', methods=['POST'])
def calculate_metrics():
    """
    计算风险指标

    POST /api/risk/metrics

    请求体:
    {
        "returns": [0.01, -0.02, 0.03, ...],  // 必需：收益率序列
        "benchmark_returns": [0.005, -0.01, 0.02, ...],  // 可选：基准收益率
        "risk_free": 0.03  // 可选：年化无风险利率（默认3%）
    }

    响应:
    {
        "success": true,
        "metrics": {
            "sharpe_ratio": 1.52,
            "sortino_ratio": 1.89,
            "calmar_ratio": 0.85,
            "max_drawdown": -0.18,
            "annual_return": 0.25,
            "annual_volatility": 0.16,
            "var_95": -0.032,
            "cvar_95": -0.045,
            "cumulative_return": 0.28,
            "alpha": 0.05,  // 如果提供了benchmark_returns
            "beta": 1.12,
            "information_ratio": 0.65
        }
    }
    """
    try:
        data = request.get_json()

        # 验证必需字段
        validate_required_fields(data, ['returns'])

        returns = data.get('returns')
        benchmark_returns = data.get('benchmark_returns')
        risk_free = data.get('risk_free', 0.03)

        # 验证数据
        if not isinstance(returns, list) or len(returns) == 0:
            return jsonify({
                'success': False,
                'error': 'returns必须是非空列表'
            }), 400

        if benchmark_returns is not None:
            if not isinstance(benchmark_returns, list):
                return jsonify({
                    'success': False,
                    'error': 'benchmark_returns必须是列表'
                }), 400

            if len(benchmark_returns) != len(returns):
                return jsonify({
                    'success': False,
                    'error': 'benchmark_returns长度必须与returns相同'
                }), 400

        # 计算指标
        service = RiskMetricsService(risk_free=risk_free)
        metrics = service.calculate_all_metrics(
            returns=returns,
            benchmark_returns=benchmark_returns
        )

        return jsonify({
            'success': True,
            'metrics': metrics
        })

    except ValueError as e:
        logger.warning(f"参数验证失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"计算风险指标失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'计算失败: {str(e)}'
        }), 500


@risk_metrics_bp.route('/sharpe', methods=['POST'])
def calculate_sharpe():
    """
    单独计算夏普比率

    POST /api/risk/sharpe

    请求体:
    {
        "returns": [0.01, -0.02, 0.03, ...],
        "risk_free": 0.03  // 可选
    }

    响应:
    {
        "success": true,
        "sharpe_ratio": 1.52
    }
    """
    try:
        data = request.get_json()
        validate_required_fields(data, ['returns'])

        returns = data.get('returns')
        risk_free = data.get('risk_free', 0.03)

        if not isinstance(returns, list) or len(returns) == 0:
            return jsonify({
                'success': False,
                'error': 'returns必须是非空列表'
            }), 400

        service = RiskMetricsService(risk_free=risk_free)
        sharpe = service.calculate_sharpe_ratio(returns)

        return jsonify({
            'success': True,
            'sharpe_ratio': sharpe
        })

    except Exception as e:
        logger.error(f"计算夏普比率失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'计算失败: {str(e)}'
        }), 500


@risk_metrics_bp.route('/sortino', methods=['POST'])
def calculate_sortino():
    """
    单独计算索提诺比率

    POST /api/risk/sortino
    """
    try:
        data = request.get_json()
        validate_required_fields(data, ['returns'])

        returns = data.get('returns')
        risk_free = data.get('risk_free', 0.03)

        if not isinstance(returns, list) or len(returns) == 0:
            return jsonify({
                'success': False,
                'error': 'returns必须是非空列表'
            }), 400

        service = RiskMetricsService(risk_free=risk_free)
        sortino = service.calculate_sortino_ratio(returns)

        return jsonify({
            'success': True,
            'sortino_ratio': sortino
        })

    except Exception as e:
        logger.error(f"计算索提诺比率失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'计算失败: {str(e)}'
        }), 500


@risk_metrics_bp.route('/alpha-beta', methods=['POST'])
def calculate_alpha_beta():
    """
    计算Alpha和Beta

    POST /api/risk/alpha-beta

    请求体:
    {
        "returns": [0.01, -0.02, 0.03, ...],
        "benchmark_returns": [0.005, -0.01, 0.02, ...],
        "risk_free": 0.03  // 可选
    }

    响应:
    {
        "success": true,
        "alpha": 0.05,
        "beta": 1.12
    }
    """
    try:
        data = request.get_json()
        validate_required_fields(data, ['returns', 'benchmark_returns'])

        returns = data.get('returns')
        benchmark_returns = data.get('benchmark_returns')
        risk_free = data.get('risk_free', 0.03)

        if not isinstance(returns, list) or len(returns) == 0:
            return jsonify({
                'success': False,
                'error': 'returns必须是非空列表'
            }), 400

        if not isinstance(benchmark_returns, list) or len(benchmark_returns) == 0:
            return jsonify({
                'success': False,
                'error': 'benchmark_returns必须是非空列表'
            }), 400

        if len(returns) != len(benchmark_returns):
            return jsonify({
                'success': False,
                'error': 'returns和benchmark_returns长度必须相同'
            }), 400

        service = RiskMetricsService(risk_free=risk_free)
        alpha, beta = service.calculate_alpha_beta(returns, benchmark_returns)

        return jsonify({
            'success': True,
            'alpha': alpha,
            'beta': beta
        })

    except Exception as e:
        logger.error(f"计算Alpha/Beta失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'计算失败: {str(e)}'
        }), 500


@risk_metrics_bp.route('/var-cvar', methods=['POST'])
def calculate_var_cvar():
    """
    计算VaR和CVaR

    POST /api/risk/var-cvar

    请求体:
    {
        "returns": [0.01, -0.02, 0.03, ...],
        "cutoff": 0.05  // 可选，默认0.05（95%置信度）
    }

    响应:
    {
        "success": true,
        "var": -0.032,
        "cvar": -0.045
    }
    """
    try:
        data = request.get_json()
        validate_required_fields(data, ['returns'])

        returns = data.get('returns')
        cutoff = data.get('cutoff', 0.05)

        if not isinstance(returns, list) or len(returns) == 0:
            return jsonify({
                'success': False,
                'error': 'returns必须是非空列表'
            }), 400

        if not (0 < cutoff < 1):
            return jsonify({
                'success': False,
                'error': 'cutoff必须在0到1之间'
            }), 400

        service = RiskMetricsService()
        var = service.calculate_var(returns, cutoff=cutoff)
        cvar = service.calculate_cvar(returns, cutoff=cutoff)

        return jsonify({
            'success': True,
            'var': var,
            'cvar': cvar,
            'cutoff': cutoff
        })

    except Exception as e:
        logger.error(f"计算VaR/CVaR失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'计算失败: {str(e)}'
        }), 500
