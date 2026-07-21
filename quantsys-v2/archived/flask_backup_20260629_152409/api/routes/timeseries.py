"""
Time series analysis routes - ARIMA, GARCH, Kalman Filter.
"""
import logging
from flask import Blueprint, request

from adapters.inbound.api.shared import (
    ds,
    api_response,
    handle_api_error,
    get_query_params_snake_case,
)

from domain.quantlib.timeseries import (
    ARIMACalculator,
    GARCHCalculator,
    KalmanFilterCalculator,
    CointegrationCalculator,
    GrangerCausalityCalculator,
)

logger = logging.getLogger(__name__)

timeseries_bp = Blueprint('timeseries', __name__)


def _get_price_series(symbol: str, start_date: str = None, end_date: str = None):
    """获取股票价格序列"""
    # 默认日期：end_date 默认今天，start_date 默认一年前
    from datetime import datetime, timedelta
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)
    if klines_df is None or klines_df.is_empty():
        return None

    klines = klines_df.to_dicts()
    # 提取收盘价序列
    prices = [float(k.get('close', 0)) for k in klines]
    return prices


def _compute_returns(prices: list):
    """计算收益率序列"""
    if len(prices) < 2:
        return []

    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] != 0:
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        else:
            returns.append(0.0)

    return returns


def _get_aligned_price_series(symbols: list, start_date: str = None, end_date: str = None):
    """获取多个股票的对齐价格序列（只保留共同交易日）"""
    # 获取每个股票的 klines 数据（带时间戳）
    all_series = {}
    for symbol in symbols:
        klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)
        print(f"[DEBUG] Symbol {symbol}: klines={len(klines_df) if klines_df is not None else 0}")
        if klines_df is None or klines_df.is_empty():
            logger.warning(f"No klines data for symbol {symbol}")
            return None

        klines = klines_df.to_dicts()
        # 构建 {trade_date: price} 字典
        series = {}
        for k in klines:
            trade_date = k.get('trade_date')  # 使用 trade_date 而不是 timestamp
            close_price = float(k.get('close', 0))
            if trade_date:
                series[trade_date] = close_price

        all_series[symbol] = series
        print(f"[DEBUG] Symbol {symbol}: series length={len(series)}")
        logger.info(f"Symbol {symbol}: {len(series)} data points")

    # 找到所有股票的共同交易日
    common_dates = set(all_series[symbols[0]].keys())
    for symbol in symbols[1:]:
        common_dates &= set(all_series[symbol].keys())

    print(f"[DEBUG] Common dates: {len(common_dates)}")
    logger.info(f"Common dates: {len(common_dates)}")

    if not common_dates:
        return None

    # 按日期排序
    common_dates = sorted(list(common_dates))

    # 构建对齐后的价格序列
    aligned_series = {}
    for symbol in symbols:
        aligned_series[symbol] = [all_series[symbol][date] for date in common_dates]

    return aligned_series


# ============================================================================
# ARIMA Routes
# ============================================================================

@timeseries_bp.route('/api/timeseries/arima/fit', methods=['POST'])
@handle_api_error
def arima_fit():
    """ARIMA 模型拟合"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    if not symbol:
        return api_response(None, success=False, message="Missing required parameter: symbol")

    start_date = data.get('start_date')
    end_date = data.get('end_date')

    # 获取价格序列
    prices = _get_price_series(symbol, start_date, end_date)
    if not prices:
        return api_response(None, success=False, message=f"No data found for symbol: {symbol}")

    # 解析 order 参数
    order = data.get('order', [1, 1, 1])
    if isinstance(order, str):
        order = [int(x.strip()) for x in order.split(',')]
    order = tuple(order)

    # 解析 seasonal_order 参数
    seasonal_order = data.get('seasonal_order')
    if seasonal_order:
        if isinstance(seasonal_order, str):
            seasonal_order = [int(x.strip()) for x in seasonal_order.split(',')]
        seasonal_order = tuple(seasonal_order)

    # 拟合 ARIMA 模型
    calc = ARIMACalculator()
    result = calc.fit(
        data=prices,
        order=order,
        seasonal_order=seasonal_order
    )

    return api_response(result)


@timeseries_bp.route('/api/timeseries/arima/forecast', methods=['POST'])
@handle_api_error
def arima_forecast():
    """ARIMA 预测"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    if not symbol:
        return api_response(None, success=False, message="Missing required parameter: symbol")

    start_date = data.get('start_date')
    end_date = data.get('end_date')
    forecast_steps = int(data.get('forecast_steps', 10))

    # 获取价格序列
    prices = _get_price_series(symbol, start_date, end_date)
    if not prices:
        return api_response(None, success=False, message=f"No data found for symbol: {symbol}")

    # 解析 order 参数
    order = data.get('order', [1, 1, 1])
    if isinstance(order, str):
        order = [int(x.strip()) for x in order.split(',')]
    order = tuple(order)

    # 拟合并预测
    calc = ARIMACalculator()
    fit_result = calc.fit(data=prices, order=order)

    if not fit_result.get('success'):
        return api_response(fit_result)

    forecast_result = calc.forecast(steps=forecast_steps)

    return api_response(forecast_result)


@timeseries_bp.route('/api/timeseries/arima/auto-order', methods=['POST'])
@handle_api_error
def arima_auto_order():
    """ARIMA 自动选参"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    if not symbol:
        return api_response(None, success=False, message="Missing required parameter: symbol")

    start_date = data.get('start_date')
    end_date = data.get('end_date')
    forecast_steps = int(data.get('forecast_steps', 10))

    # 获取价格序列
    prices = _get_price_series(symbol, start_date, end_date)
    if not prices:
        return api_response(None, success=False, message=f"No data found for symbol: {symbol}")

    # 自动选参
    calc = ARIMACalculator()
    auto_result = calc.auto_select_order(data=prices)

    if not auto_result.get('success'):
        return api_response(auto_result)

    # 使用最优参数进行预测
    best_order = auto_result['value']['best_order']
    fit_result = calc.fit(data=prices, order=best_order)

    if fit_result.get('success'):
        forecast_result = calc.forecast(steps=forecast_steps)
        auto_result['value']['forecast'] = forecast_result.get('value', {})

    return api_response(auto_result)


# ============================================================================
# GARCH Routes
# ============================================================================

@timeseries_bp.route('/api/timeseries/garch/fit', methods=['POST'])
@handle_api_error
def garch_fit():
    """GARCH 模型拟合"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    if not symbol:
        return api_response(None, success=False, message="Missing required parameter: symbol")

    start_date = data.get('start_date')
    end_date = data.get('end_date')

    # 获取价格序列并计算收益率
    prices = _get_price_series(symbol, start_date, end_date)
    if not prices:
        return api_response(None, success=False, message=f"No data found for symbol: {symbol}")

    returns = _compute_returns(prices)
    if not returns:
        return api_response(None, success=False, message="Insufficient data to compute returns")

    # 解析 GARCH 参数
    p = int(data.get('p', 1))
    q = int(data.get('q', 1))

    # 拟合 GARCH 模型
    calc = GARCHCalculator()
    result = calc.fit(returns=returns, p=p, q=q)

    return api_response(result)


@timeseries_bp.route('/api/timeseries/garch/forecast', methods=['POST'])
@handle_api_error
def garch_forecast():
    """GARCH 波动率预测"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    if not symbol:
        return api_response(None, success=False, message="Missing required parameter: symbol")

    start_date = data.get('start_date')
    end_date = data.get('end_date')
    forecast_steps = int(data.get('forecast_steps', 5))

    # 获取价格序列并计算收益率
    prices = _get_price_series(symbol, start_date, end_date)
    if not prices:
        return api_response(None, success=False, message=f"No data found for symbol: {symbol}")

    returns = _compute_returns(prices)
    if not returns:
        return api_response(None, success=False, message="Insufficient data to compute returns")

    # 解析 GARCH 参数
    p = int(data.get('p', 1))
    q = int(data.get('q', 1))

    # 拟合并预测
    calc = GARCHCalculator()
    fit_result = calc.fit(returns=returns, p=p, q=q)

    if not fit_result.get('success'):
        return api_response(fit_result)

    forecast_result = calc.forecast_volatility(steps=forecast_steps)

    return api_response(forecast_result)


@timeseries_bp.route('/api/timeseries/garch/var', methods=['POST'])
@handle_api_error
def garch_var():
    """GARCH VaR 计算"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    if not symbol:
        return api_response(None, success=False, message="Missing required parameter: symbol")

    start_date = data.get('start_date')
    end_date = data.get('end_date')
    confidence = float(data.get('confidence', 0.95))

    # 获取价格序列并计算收益率
    prices = _get_price_series(symbol, start_date, end_date)
    if not prices:
        return api_response(None, success=False, message=f"No data found for symbol: {symbol}")

    returns = _compute_returns(prices)
    if not returns:
        return api_response(None, success=False, message="Insufficient data to compute returns")

    # 解析 GARCH 参数
    p = int(data.get('p', 1))
    q = int(data.get('q', 1))

    # 拟合并计算 VaR
    calc = GARCHCalculator()
    fit_result = calc.fit(returns=returns, p=p, q=q)

    if not fit_result.get('success'):
        return api_response(fit_result)

    var_result = calc.calculate_var(confidence=confidence)

    return api_response(var_result)


# ============================================================================
# Kalman Filter Routes
# ============================================================================

@timeseries_bp.route('/api/timeseries/kalman/filter', methods=['POST'])
@handle_api_error
def kalman_filter():
    """卡尔曼滤波"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    if not symbol:
        return api_response(None, success=False, message="Missing required parameter: symbol")

    start_date = data.get('start_date')
    end_date = data.get('end_date')

    # 获取价格序列
    prices = _get_price_series(symbol, start_date, end_date)
    if not prices:
        return api_response(None, success=False, message=f"No data found for symbol: {symbol}")

    # 卡尔曼滤波 - 使用局部水平模型
    calc = KalmanFilterCalculator()

    # 使用局部水平模型（自动估计参数）
    result = calc.fit_local_level(
        observations=prices,
        initial_level=data.get('initial_level'),
        level_variance=data.get('level_variance'),
        obs_variance=data.get('obs_variance')
    )

    return api_response(result)


@timeseries_bp.route('/api/timeseries/kalman/smooth', methods=['POST'])
@handle_api_error
def kalman_smooth():
    """卡尔曼平滑（需要先进行滤波）"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    if not symbol:
        return api_response(None, success=False, message="Missing required parameter: symbol")

    start_date = data.get('start_date')
    end_date = data.get('end_date')

    # 获取价格序列
    prices = _get_price_series(symbol, start_date, end_date)
    if not prices:
        return api_response(None, success=False, message=f"No data found for symbol: {symbol}")

    # 卡尔曼平滑需要先进行滤波
    calc = KalmanFilterCalculator()

    # 先使用局部水平模型进行滤波
    fit_result = calc.fit_local_level(
        observations=prices,
        initial_level=data.get('initial_level'),
        level_variance=data.get('level_variance'),
        obs_variance=data.get('obs_variance')
    )

    # 然后进行平滑（从 metadata 中提取 filter_result）
    filter_result = fit_result.get('metadata', {}).get('filter_result')
    if not filter_result:
        return api_response(None, success=False, message="Failed to get filter result")

    smooth_result = calc.smooth(filter_result)

    return api_response(smooth_result)


@timeseries_bp.route('/api/timeseries/kalman/local-level', methods=['POST'])
@handle_api_error
def kalman_local_level():
    """卡尔曼局部水平模型（趋势提取）"""
    data = request.get_json()

    symbol = data.get('symbol') or data.get('symbols')
    if not symbol:
        return api_response(None, success=False, message="Missing required parameter: symbol")

    start_date = data.get('start_date')
    end_date = data.get('end_date')

    # 获取价格序列
    prices = _get_price_series(symbol, start_date, end_date)
    if not prices:
        return api_response(None, success=False, message=f"No data found for symbol: {symbol}")

    # 局部水平模型
    calc = KalmanFilterCalculator()
    result = calc.fit_local_level(observations=prices)

    return api_response(result)


# ============================================================================
# Cointegration & Causality Routes (Bonus)
# ============================================================================

@timeseries_bp.route('/api/timeseries/cointegration/test', methods=['POST'])
@handle_api_error
def cointegration_test():
    """协整检验"""
    data = request.get_json()

    symbols = data.get('symbols', [])
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.split(',')]

    if len(symbols) < 2:
        return api_response(None, success=False, message="At least 2 symbols required for cointegration test")

    start_date = data.get('start_date')
    end_date = data.get('end_date')

    # 获取对齐后的价格序列
    aligned_series = _get_aligned_price_series(symbols, start_date, end_date)
    if not aligned_series or len(aligned_series) < 2:
        return api_response(None, success=False, message="Insufficient data for cointegration test")

    # 协整检验 - 使用 Engle-Granger 方法
    calc = CointegrationCalculator()

    # 将价格序列转换为列表格式
    series_list = [aligned_series[sym] for sym in symbols]

    # 默认使用 Engle-Granger 检验（适用于两个序列）
    test_method = data.get('method', 'engle_granger')

    if test_method == 'johansen' or len(series_list) > 2:
        # Johansen 检验（适用于多个序列）
        result = calc.johansen_test(series_list)
    else:
        # Engle-Granger 检验（适用于两个序列）
        result = calc.engle_granger_test(series_list[0], series_list[1])

    return api_response(result)


@timeseries_bp.route('/api/timeseries/causality/test', methods=['POST'])
@handle_api_error
def causality_test():
    """格兰杰因果检验"""
    data = request.get_json()

    symbols = data.get('symbols', [])
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.split(',')]

    if len(symbols) != 2:
        return api_response(None, success=False, message="Exactly 2 symbols required for Granger causality test")

    start_date = data.get('start_date')
    end_date = data.get('end_date')
    max_lag = int(data.get('max_lag', 5))

    # 获取对齐后的价格序列
    aligned_series = _get_aligned_price_series(symbols, start_date, end_date)
    if not aligned_series:
        return api_response(None, success=False, message="Insufficient data for causality test")

    # 格兰杰因果检验
    calc = GrangerCausalityCalculator()
    result = calc.test(
        x=aligned_series[symbols[0]],
        y=aligned_series[symbols[1]],
        maxlag=max_lag
    )

    # Convert bool to int for JSON serialization
    if 'value' in result and 'x_granger_causes_y' in result['value']:
        result['value']['x_granger_causes_y'] = int(result['value']['x_granger_causes_y'])

    return api_response(result)
