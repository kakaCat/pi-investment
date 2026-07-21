"""时间序列分析 API - FastAPI 版（从 Flask timeseries.py 迁移，响应契约保持一致）

复用同一 ds 单例与 domain.quantlib.timeseries 计算器（ARIMACalculator/
GARCHCalculator/KalmanFilterCalculator）。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body
import structlog

from adapters.inbound.fastapi_app.shared import ds, api_response, handle_api_error

from domain.quantlib.timeseries import (
    ARIMACalculator,
    GARCHCalculator,
    KalmanFilterCalculator,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["TimeSeries - 时间序列"])


def _get_price_series(symbol: str, start_date: str = None, end_date: str = None):
    """获取股票价格序列（与 Flask timeseries.py 一致）。"""
    from datetime import datetime, timedelta
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)
    if klines_df is None or klines_df.is_empty():
        return None
    klines = klines_df.to_dicts()
    return [float(k.get('close', 0)) for k in klines]


def _compute_returns(prices: list):
    """计算收益率序列（与 Flask timeseries.py 一致）。"""
    if len(prices) < 2:
        return []
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] != 0:
            returns.append((prices[i] - prices[i - 1]) / prices[i - 1])
        else:
            returns.append(0.0)
    return returns


def _symbol(payload: Dict[str, Any]):
    return payload.get('symbol') or payload.get('symbols')


def _missing_symbol():
    return api_response(None, success=False, message="Missing required parameter: symbol")


def _no_data(symbol):
    return api_response(None, success=False, message=f"No data found for symbol: {symbol}")


# ============ ARIMA ============

@router.post('/api/timeseries/arima/fit')
@handle_api_error
def arima_fit(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = _symbol(payload)
    if not symbol:
        return _missing_symbol()
    prices = _get_price_series(symbol, payload.get('start_date'), payload.get('end_date'))
    if not prices:
        return _no_data(symbol)
    order = payload.get('order', [1, 1, 1])
    if isinstance(order, str):
        order = [int(x.strip()) for x in order.split(',')]
    order = tuple(order)
    seasonal_order = payload.get('seasonal_order')
    if seasonal_order:
        if isinstance(seasonal_order, str):
            seasonal_order = [int(x.strip()) for x in seasonal_order.split(',')]
        seasonal_order = tuple(seasonal_order)
    calc = ARIMACalculator()
    result = calc.fit(data=prices, order=order, seasonal_order=seasonal_order)
    return api_response(result)


@router.post('/api/timeseries/arima/forecast')
@handle_api_error
def arima_forecast(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = _symbol(payload)
    if not symbol:
        return _missing_symbol()
    forecast_steps = int(payload.get('forecast_steps', 10))
    prices = _get_price_series(symbol, payload.get('start_date'), payload.get('end_date'))
    if not prices:
        return _no_data(symbol)
    order = payload.get('order', [1, 1, 1])
    if isinstance(order, str):
        order = [int(x.strip()) for x in order.split(',')]
    order = tuple(order)
    calc = ARIMACalculator()
    fit_result = calc.fit(data=prices, order=order)
    if not fit_result.get('success'):
        return api_response(fit_result)
    forecast_result = calc.forecast(steps=forecast_steps)
    return api_response(forecast_result)


@router.post('/api/timeseries/arima/auto-order')
@handle_api_error
def arima_auto_order(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = _symbol(payload)
    if not symbol:
        return _missing_symbol()
    forecast_steps = int(payload.get('forecast_steps', 10))
    prices = _get_price_series(symbol, payload.get('start_date'), payload.get('end_date'))
    if not prices:
        return _no_data(symbol)
    calc = ARIMACalculator()
    auto_result = calc.auto_select_order(data=prices)
    if not auto_result.get('success'):
        return api_response(auto_result)
    best_order = auto_result['value']['best_order']
    fit_result = calc.fit(data=prices, order=best_order)
    if fit_result.get('success'):
        forecast_result = calc.forecast(steps=forecast_steps)
        auto_result['value']['forecast'] = forecast_result.get('value', {})
    return api_response(auto_result)


# ============ GARCH ============

@router.post('/api/timeseries/garch/fit')
@handle_api_error
def garch_fit(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = _symbol(payload)
    if not symbol:
        return _missing_symbol()
    prices = _get_price_series(symbol, payload.get('start_date'), payload.get('end_date'))
    if not prices:
        return _no_data(symbol)
    returns = _compute_returns(prices)
    if not returns:
        return api_response(None, success=False, message="Insufficient data to compute returns")
    p = int(payload.get('p', 1))
    q = int(payload.get('q', 1))
    calc = GARCHCalculator()
    result = calc.fit(returns=returns, p=p, q=q)
    return api_response(result)


@router.post('/api/timeseries/garch/forecast')
@handle_api_error
def garch_forecast(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = _symbol(payload)
    if not symbol:
        return _missing_symbol()
    forecast_steps = int(payload.get('forecast_steps', 5))
    prices = _get_price_series(symbol, payload.get('start_date'), payload.get('end_date'))
    if not prices:
        return _no_data(symbol)
    returns = _compute_returns(prices)
    if not returns:
        return api_response(None, success=False, message="Insufficient data to compute returns")
    p = int(payload.get('p', 1))
    q = int(payload.get('q', 1))
    calc = GARCHCalculator()
    fit_result = calc.fit(returns=returns, p=p, q=q)
    if not fit_result.get('success'):
        return api_response(fit_result)
    forecast_result = calc.forecast_volatility(steps=forecast_steps)
    return api_response(forecast_result)


@router.post('/api/timeseries/garch/var')
@handle_api_error
def garch_var(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = _symbol(payload)
    if not symbol:
        return _missing_symbol()
    confidence = float(payload.get('confidence', 0.95))
    prices = _get_price_series(symbol, payload.get('start_date'), payload.get('end_date'))
    if not prices:
        return _no_data(symbol)
    returns = _compute_returns(prices)
    if not returns:
        return api_response(None, success=False, message="Insufficient data to compute returns")
    p = int(payload.get('p', 1))
    q = int(payload.get('q', 1))
    calc = GARCHCalculator()
    fit_result = calc.fit(returns=returns, p=p, q=q)
    if not fit_result.get('success'):
        return api_response(fit_result)
    var_result = calc.calculate_var(confidence=confidence)
    return api_response(var_result)


# ============ Kalman ============

@router.post('/api/timeseries/kalman/filter')
@handle_api_error
def kalman_filter(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = _symbol(payload)
    if not symbol:
        return _missing_symbol()
    prices = _get_price_series(symbol, payload.get('start_date'), payload.get('end_date'))
    if not prices:
        return _no_data(symbol)
    calc = KalmanFilterCalculator()
    result = calc.fit_local_level(
        observations=prices,
        initial_level=payload.get('initial_level'),
        level_variance=payload.get('level_variance'),
        obs_variance=payload.get('obs_variance'))
    return api_response(result)


@router.post('/api/timeseries/kalman/smooth')
@handle_api_error
def kalman_smooth(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = _symbol(payload)
    if not symbol:
        return _missing_symbol()
    prices = _get_price_series(symbol, payload.get('start_date'), payload.get('end_date'))
    if not prices:
        return _no_data(symbol)
    calc = KalmanFilterCalculator()
    fit_result = calc.fit_local_level(
        observations=prices,
        initial_level=payload.get('initial_level'),
        level_variance=payload.get('level_variance'),
        obs_variance=payload.get('obs_variance'))
    filter_result = fit_result.get('metadata', {}).get('filter_result')
    if not filter_result:
        return api_response(None, success=False, message="Failed to get filter result")
    smooth_result = calc.smooth(filter_result)
    return api_response(smooth_result)


@router.post('/api/timeseries/kalman/local-level')
@handle_api_error
def kalman_local_level(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = _symbol(payload)
    if not symbol:
        return _missing_symbol()
    prices = _get_price_series(symbol, payload.get('start_date'), payload.get('end_date'))
    if not prices:
        return _no_data(symbol)
    calc = KalmanFilterCalculator()
    result = calc.fit_local_level(observations=prices)
    return api_response(result)
