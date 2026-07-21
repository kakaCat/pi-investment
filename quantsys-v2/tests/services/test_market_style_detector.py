# tests/services/test_market_style_detector.py
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from application.services.market_style_detector import MarketStyleDetector


def test_detector_initialization():
    """测试检测器初始化"""
    detector = MarketStyleDetector()

    assert detector is not None
    assert hasattr(detector, 'detect')


def test_calculate_momentum_score():
    """测试动量得分计算"""
    detector = MarketStyleDetector()

    # 构造动量市数据：RSI > 55, MACD 金叉 > 60%, 成交量放大
    metrics = {
        'rsi_avg': 58.0,
        'macd_golden_ratio': 0.65,
        'volume_growth': 1.15
    }

    score = detector._calculate_momentum_score(metrics)

    assert score > 50  # 动量市得分应该较高
    assert 0 <= score <= 100


def test_calculate_oscillation_score():
    """测试震荡市得分计算"""
    detector = MarketStyleDetector()

    # 构造震荡市数据：RSI 中性, 价格接近 MA20
    metrics = {
        'rsi_avg': 50.0,
        'price_to_ma20': 1.0
    }

    score = detector._calculate_oscillation_score(metrics)

    assert score > 50  # 震荡市得分应该较高
    assert 0 <= score <= 100


def test_calculate_low_volatility_score():
    """测试低波动得分计算"""
    detector = MarketStyleDetector()

    # 构造低波动数据：ATR 低分位数, 波动率比率低
    metrics = {
        'atr_percentile': 20.0,
        'volatility_ratio': 0.8
    }

    score = detector._calculate_low_volatility_score(metrics)

    assert score > 50  # 低波动得分应该较高
    assert 0 <= score <= 100


def test_calculate_value_score():
    """测试价值市得分计算"""
    detector = MarketStyleDetector()

    # 构造价值市数据：小盘超额收益, PE 低分位数
    metrics = {
        'small_cap_excess_return': 0.05,
        'pe_ratio_percentile': 30.0
    }

    score = detector._calculate_value_score(metrics)

    assert score >= 0  # 价值市得分应该非负
    assert 0 <= score <= 100


def test_select_dominant_style():
    """测试主导风格选择"""
    detector = MarketStyleDetector()

    scores = {
        'momentum': 75.0,
        'oscillation': 45.0,
        'low_volatility': 30.0,
        'value': 50.0
    }

    style, confidence = detector._select_dominant_style(scores)

    assert style == 'momentum'
    assert confidence > 0
    assert confidence <= 1.0


def test_select_dominant_style_empty_scores():
    """测试空得分情况"""
    detector = MarketStyleDetector()

    scores = {}

    style, confidence = detector._select_dominant_style(scores)

    assert style == 'unknown'
    assert confidence == 0.0


def test_select_dominant_style_all_zero():
    """测试所有得分为零的情况"""
    detector = MarketStyleDetector()

    scores = {
        'momentum': 0.0,
        'oscillation': 0.0,
        'low_volatility': 0.0,
        'value': 0.0
    }

    style, confidence = detector._select_dominant_style(scores)

    assert style == 'unknown'
    assert confidence == 0.0


@pytest.fixture
def mock_kline_data():
    """生成模拟 K 线数据"""
    def _generate_kline(symbol: str, days: int = 30) -> list:
        """为单只股票生成 K 线数据（返回 list of dicts）"""
        # 生成随机价格数据
        np.random.seed(hash(symbol) % 2**32)
        close_prices = 100 + np.cumsum(np.random.randn(days) * 2)
        high_prices = close_prices + np.random.rand(days) * 3
        low_prices = close_prices - np.random.rand(days) * 3
        open_prices = close_prices + np.random.randn(days)
        volumes = np.random.randint(1000000, 10000000, days)

        # 生成技术指标
        rsi_values = 50 + np.random.randn(days) * 15  # RSI 在 20-80 之间
        macd_values = np.random.randn(days) * 2
        macd_signal_values = macd_values - np.random.randn(days) * 0.5
        atr_values = np.abs(np.random.randn(days) * 3) + 2

        # 构造返回数据
        klines = []
        base_date = date.today() - timedelta(days=days)
        for i in range(days):
            klines.append({
                'trade_date': base_date + timedelta(days=i),
                'open': float(open_prices[i]),
                'high': float(high_prices[i]),
                'low': float(low_prices[i]),
                'close': float(close_prices[i]),
                'volume': int(volumes[i]),
                'rsi': float(rsi_values[i]),
                'macd': float(macd_values[i]),
                'macd_signal': float(macd_signal_values[i]),
                'atr': float(atr_values[i]),
            })

        return klines

    return _generate_kline


def test_aggregate_indicators_success(mock_kline_data, monkeypatch):
    """测试指标聚合成功"""
    detector = MarketStyleDetector()

    # 生成 250 只股票的股票池
    stock_pool = [f"{600000 + i}.SH" for i in range(250)]
    trade_date = date(2026, 5, 29)

    # Mock KlineRepository.get_daily_klines
    def mock_get_daily_klines(symbol, start_date, end_date, fields=None):
        return mock_kline_data(symbol, days=30)

    monkeypatch.setattr(detector.kline_repo, 'get_daily_klines', mock_get_daily_klines)

    # 调用聚合方法
    metrics = detector._aggregate_indicators(stock_pool, trade_date)

    # 验证返回结果
    assert metrics is not None
    assert 'rsi_avg' in metrics
    assert 'macd_golden_ratio' in metrics
    assert 'atr_percentile' in metrics
    assert 'volume_growth' in metrics

    # 验证值的范围
    assert 0 <= metrics['rsi_avg'] <= 100
    assert 0 <= metrics['macd_golden_ratio'] <= 1
    assert 0 <= metrics['atr_percentile'] <= 100
    assert metrics['volume_growth'] > 0


def test_aggregate_indicators_insufficient_data(mock_kline_data, monkeypatch):
    """测试数据不足时的处理"""
    detector = MarketStyleDetector()

    # 只有 50 只股票（< MIN_STOCKS_REQUIRED=200）
    stock_pool = [f"{600000 + i}.SH" for i in range(50)]
    trade_date = date(2026, 5, 29)

    # Mock KlineRepository.get_daily_klines
    def mock_get_daily_klines(symbol, start_date, end_date, fields=None):
        return mock_kline_data(symbol, days=30)

    monkeypatch.setattr(detector.kline_repo, 'get_daily_klines', mock_get_daily_klines)

    # 调用聚合方法
    metrics = detector._aggregate_indicators(stock_pool, trade_date)

    # 验证返回 None
    assert metrics is None
