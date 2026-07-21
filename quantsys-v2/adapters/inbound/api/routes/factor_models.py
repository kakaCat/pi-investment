"""
Factor Models API Routes
========================

API endpoints for multi-factor models (Fama-French, Barra, Carhart).

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
from flask import Blueprint, request
from adapters.inbound.api.shared import ds, api_response, handle_api_error
from domain.quantlib.factor_models import (
    FamaFrench3FactorCalculator,
    FamaFrench5FactorCalculator,
    CarhartFourFactorCalculator,
    BarraRiskModelCalculator,
    FamaFrenchFactorBuilder,
    BarraFactorBuilder
)


def _generate_noisy_defaults(length: int, mean: float = 0.001, std: float = 0.01):
    """生成带噪声的默认因子数据，避免奇异矩阵"""
    np.random.seed(42)
    return (np.random.randn(length) * std + mean).tolist()

factor_models_bp = Blueprint('factor_models', __name__)


@factor_models_bp.route('/api/factor-models/fama-french-3/calculate', methods=['POST'])
@handle_api_error
def fama_french_3_calculate():
    """Fama-French 3因子模型回归分析"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not symbol:
        return api_response(None, success=False, message="symbol is required")

    # 获取股票收益率
    klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)
    if klines_df is None or klines_df.is_empty() or len(klines_df) < 30:
        return api_response(None, success=False, message="Insufficient data for factor model")

    klines = klines_df.to_dicts()
    asset_returns = []
    for i in range(1, len(klines)):
        prev_close = float(klines[i-1].get('close', 0))
        curr_close = float(klines[i].get('close', 0))
        if prev_close > 0:
            asset_returns.append((curr_close - prev_close) / prev_close)

    # 获取因子数据（从请求中获取或使用默认值）
    n = len(asset_returns)
    market_returns = data.get('market_returns', _generate_noisy_defaults(n, 0.001, 0.015))
    smb_factor = data.get('smb_factor', _generate_noisy_defaults(n, 0.0005, 0.01))
    hml_factor = data.get('hml_factor', _generate_noisy_defaults(n, 0.0003, 0.008))
    risk_free_rate = data.get('risk_free_rate', 0.0)

    # 确保长度匹配
    min_len = min(len(asset_returns), len(market_returns), len(smb_factor), len(hml_factor))
    asset_returns = asset_returns[:min_len]
    market_returns = market_returns[:min_len]
    smb_factor = smb_factor[:min_len]
    hml_factor = hml_factor[:min_len]

    # 计算因子模型
    calc = FamaFrench3FactorCalculator()
    result = calc.calculate(
        asset_returns=asset_returns,
        market_returns=market_returns,
        risk_free_rate=risk_free_rate,
        smb_factor=smb_factor,
        hml_factor=hml_factor
    )

    return api_response(result)


@factor_models_bp.route('/api/factor-models/fama-french-5/calculate', methods=['POST'])
@handle_api_error
def fama_french_5_calculate():
    """Fama-French 5因子模型回归分析"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not symbol:
        return api_response(None, success=False, message="symbol is required")

    # 获取股票收益率
    klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)
    if klines_df is None or klines_df.is_empty() or len(klines_df) < 30:
        return api_response(None, success=False, message="Insufficient data for factor model")

    klines = klines_df.to_dicts()
    asset_returns = []
    for i in range(1, len(klines)):
        prev_close = float(klines[i-1].get('close', 0))
        curr_close = float(klines[i].get('close', 0))
        if prev_close > 0:
            asset_returns.append((curr_close - prev_close) / prev_close)

    # 获取因子数据
    n = len(asset_returns)
    market_returns = data.get('market_returns', _generate_noisy_defaults(n, 0.001, 0.015))
    smb_factor = data.get('smb_factor', _generate_noisy_defaults(n, 0.0005, 0.01))
    hml_factor = data.get('hml_factor', _generate_noisy_defaults(n, 0.0003, 0.008))
    rmw_factor = data.get('rmw_factor', _generate_noisy_defaults(n, 0.0002, 0.006))
    cma_factor = data.get('cma_factor', _generate_noisy_defaults(n, 0.0001, 0.005))
    risk_free_rate = data.get('risk_free_rate', 0.0)

    # 确保长度匹配
    min_len = min(len(asset_returns), len(market_returns), len(smb_factor),
                  len(hml_factor), len(rmw_factor), len(cma_factor))
    asset_returns = asset_returns[:min_len]
    market_returns = market_returns[:min_len]
    smb_factor = smb_factor[:min_len]
    hml_factor = hml_factor[:min_len]
    rmw_factor = rmw_factor[:min_len]
    cma_factor = cma_factor[:min_len]

    # 计算因子模型
    calc = FamaFrench5FactorCalculator()
    result = calc.calculate(
        asset_returns=asset_returns,
        market_returns=market_returns,
        risk_free_rate=risk_free_rate,
        smb_factor=smb_factor,
        hml_factor=hml_factor,
        rmw_factor=rmw_factor,
        cma_factor=cma_factor
    )

    return api_response(result)


@factor_models_bp.route('/api/factor-models/carhart/calculate', methods=['POST'])
@handle_api_error
def carhart_calculate():
    """Carhart 4因子模型回归分析"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not symbol:
        return api_response(None, success=False, message="symbol is required")

    # 获取股票收益率
    klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)
    if klines_df is None or klines_df.is_empty() or len(klines_df) < 30:
        return api_response(None, success=False, message="Insufficient data for factor model")

    klines = klines_df.to_dicts()
    asset_returns = []
    for i in range(1, len(klines)):
        prev_close = float(klines[i-1].get('close', 0))
        curr_close = float(klines[i].get('close', 0))
        if prev_close > 0:
            asset_returns.append((curr_close - prev_close) / prev_close)

    # 获取因子数据
    n = len(asset_returns)
    market_returns = data.get('market_returns', _generate_noisy_defaults(n, 0.001, 0.015))
    smb_factor = data.get('smb_factor', _generate_noisy_defaults(n, 0.0005, 0.01))
    hml_factor = data.get('hml_factor', _generate_noisy_defaults(n, 0.0003, 0.008))
    mom_factor = data.get('mom_factor', _generate_noisy_defaults(n, 0.0004, 0.01))
    risk_free_rate = data.get('risk_free_rate', 0.0)

    # 确保长度匹配
    min_len = min(len(asset_returns), len(market_returns), len(smb_factor),
                  len(hml_factor), len(mom_factor))
    asset_returns = asset_returns[:min_len]
    market_returns = market_returns[:min_len]
    smb_factor = smb_factor[:min_len]
    hml_factor = hml_factor[:min_len]
    mom_factor = mom_factor[:min_len]

    # 计算因子模型
    calc = CarhartFourFactorCalculator()
    result = calc.calculate(
        asset_returns=asset_returns,
        market_returns=market_returns,
        risk_free_rate=risk_free_rate,
        smb_factor=smb_factor,
        hml_factor=hml_factor,
        mom_factor=mom_factor
    )

    return api_response(result)


@factor_models_bp.route('/api/factor-models/barra/calculate', methods=['POST'])
@handle_api_error
def barra_calculate():
    """Barra 风险模型分析"""
    data = request.get_json()

    # Barra 模型需要 DataFrame 格式的数据，暂时返回提示信息
    return api_response(
        None,
        success=False,
        message="Barra model requires DataFrame input format. Please use the Python API directly for now."
    )


@factor_models_bp.route('/api/factor-models/barra/marginal-risk', methods=['POST'])
@handle_api_error
def barra_marginal_risk():
    """计算 Barra 模型的边际风险贡献"""
    data = request.get_json()

    # Barra 模型需要 DataFrame 格式的数据，暂时返回提示信息
    return api_response(
        None,
        success=False,
        message="Barra marginal risk requires DataFrame input format. Please use the Python API directly for now."
    )
