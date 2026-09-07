"""组合优化 API - FastAPI 版（从 Flask portfolio.py 迁移，响应契约保持一致）

覆盖端点：
- /api/portfolio/markowitz/optimize              Markowitz 均值方差优化
- /api/portfolio/black-litterman/optimize        Black-Litterman 模型优化
- /api/portfolio/risk-parity/optimize            Risk Parity 风险平价优化
- /api/portfolio/risk-parity/risk-decomposition  Risk Parity 风险分解

复用同一 domain.quantlib.portfolio 优化器实现，保证 parity。
（/api/portfolio 持仓/交易等其他端点不在本批迁移范围。）
"""
from typing import Any, Dict, Optional

import numpy as np
from fastapi import APIRouter, Body
import structlog

from adapters.inbound.fastapi_app.shared import api_response, handle_api_error
from domain.quantlib.portfolio.markowitz import MarkowitzOptimizer
from domain.quantlib.portfolio.black_litterman import BlackLittermanOptimizer
from domain.quantlib.portfolio.risk_parity import RiskParityOptimizer

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Portfolio - 组合优化"])


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


def _require_json_body(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """对齐 Flask request.get_json()：无 body 时抛异常 → handle_api_error 返回 500"""
    if payload is None:
        raise Exception("400 Bad Request: Failed to decode JSON object")
    return payload


@router.post('/api/portfolio/markowitz/optimize')
@handle_api_error
def markowitz_optimize(payload: Optional[Dict[str, Any]] = Body(None)):
    """Markowitz 均值方差优化"""
    data = _require_json_body(payload)

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


@router.post('/api/portfolio/black-litterman/optimize')
@handle_api_error
def black_litterman_optimize(payload: Optional[Dict[str, Any]] = Body(None)):
    """Black-Litterman 模型优化"""
    data = _require_json_body(payload)

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


@router.post('/api/portfolio/risk-parity/optimize')
@handle_api_error
def risk_parity_optimize(payload: Optional[Dict[str, Any]] = Body(None)):
    """Risk Parity 风险平价优化"""
    data = _require_json_body(payload)

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


@router.post('/api/portfolio/risk-parity/risk-decomposition')
@handle_api_error
def risk_parity_decomposition(payload: Optional[Dict[str, Any]] = Body(None)):
    """Risk Parity 风险分解"""
    data = _require_json_body(payload)

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
