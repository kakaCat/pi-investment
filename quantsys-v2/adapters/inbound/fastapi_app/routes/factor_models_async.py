"""Factor Models API - FastAPI 版（从 Flask factor_models.py 迁移，响应契约保持一致）

覆盖端点：
- /api/factor-models/fama-french-3/calculate  Fama-French 3因子模型回归分析
- /api/factor-models/fama-french-5/calculate  Fama-French 5因子模型回归分析
- /api/factor-models/carhart/calculate        Carhart 4因子模型回归分析
- /api/factor-models/barra/calculate          Barra 风险模型分析（桩：提示用 Python API）

复用同一 ds 单例与 domain.quantlib.factor_models 计算器，保证 parity。
（/api/factor-models/barra/marginal-risk 不在本批迁移范围。）
"""
from typing import Any, Dict, Optional

import numpy as np
from fastapi import APIRouter, Body
import structlog

from adapters.inbound.fastapi_app.shared import ds, api_response, handle_api_error
from domain.quantlib.factor_models import (
    FamaFrench3FactorCalculator,
    FamaFrench5FactorCalculator,
    CarhartFourFactorCalculator,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Factor Models - 因子模型"])


def _generate_noisy_defaults(length: int, mean: float = 0.001, std: float = 0.01):
    """生成带噪声的默认因子数据，避免奇异矩阵"""
    np.random.seed(42)
    return (np.random.randn(length) * std + mean).tolist()


def _require_json_body(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """对齐 Flask request.get_json()：无 body 时抛异常 → handle_api_error 返回 500"""
    if payload is None:
        raise Exception("400 Bad Request: Failed to decode JSON object")
    return payload


def _extract_asset_returns(symbol, start_date, end_date):
    """从 K 线数据提取日收益率序列；数据不足时返回 None"""
    klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)
    if klines_df is None or klines_df.is_empty() or len(klines_df) < 30:
        return None

    klines = klines_df.to_dicts()
    asset_returns = []
    for i in range(1, len(klines)):
        prev_close = float(klines[i - 1].get('close', 0))
        curr_close = float(klines[i].get('close', 0))
        if prev_close > 0:
            asset_returns.append((curr_close - prev_close) / prev_close)
    return asset_returns


@router.post('/api/factor-models/fama-french-3/calculate')
@handle_api_error
def fama_french_3_calculate(payload: Optional[Dict[str, Any]] = Body(None)):
    """Fama-French 3因子模型回归分析"""
    data = _require_json_body(payload)

    symbol = data.get('symbol') or data.get('symbols')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not symbol:
        return api_response(None, success=False, message="symbol is required")

    # 获取股票收益率
    asset_returns = _extract_asset_returns(symbol, start_date, end_date)
    if asset_returns is None:
        return api_response(None, success=False, message="Insufficient data for factor model")

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


@router.post('/api/factor-models/fama-french-5/calculate')
@handle_api_error
def fama_french_5_calculate(payload: Optional[Dict[str, Any]] = Body(None)):
    """Fama-French 5因子模型回归分析"""
    data = _require_json_body(payload)

    symbol = data.get('symbol') or data.get('symbols')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not symbol:
        return api_response(None, success=False, message="symbol is required")

    # 获取股票收益率
    asset_returns = _extract_asset_returns(symbol, start_date, end_date)
    if asset_returns is None:
        return api_response(None, success=False, message="Insufficient data for factor model")

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


@router.post('/api/factor-models/carhart/calculate')
@handle_api_error
def carhart_calculate(payload: Optional[Dict[str, Any]] = Body(None)):
    """Carhart 4因子模型回归分析"""
    data = _require_json_body(payload)

    symbol = data.get('symbol') or data.get('symbols')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not symbol:
        return api_response(None, success=False, message="symbol is required")

    # 获取股票收益率
    asset_returns = _extract_asset_returns(symbol, start_date, end_date)
    if asset_returns is None:
        return api_response(None, success=False, message="Insufficient data for factor model")

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


@router.post('/api/factor-models/barra/calculate')
@handle_api_error
def barra_calculate(payload: Optional[Dict[str, Any]] = Body(None)):
    """Barra 风险模型分析"""
    data = _require_json_body(payload)

    # Barra 模型需要 DataFrame 格式的数据，暂时返回提示信息
    return api_response(
        None,
        success=False,
        message="Barra model requires DataFrame input format. Please use the Python API directly for now."
    )
