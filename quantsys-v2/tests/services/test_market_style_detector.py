import pytest
from application.services.market_style_detector import MarketStyleDetector


def test_detector_initialization():
    detector = MarketStyleDetector()
    assert detector is not None
    assert hasattr(detector, 'detect_market_style')
    assert detector.kline_repo is None
    assert detector.stock_repo is None


def test_detect_market_style_returns_result():
    detector = MarketStyleDetector()
    result = detector.detect_market_style()
    assert isinstance(result, dict)
    assert 'style' in result
    assert 'confidence' in result
    assert 'scores' in result
    assert 'indicators' in result
    assert 'recommended_factors' in result
    assert 'detection_date' in result


def test_detect_market_style_with_lookback():
    detector = MarketStyleDetector()
    result = detector.detect_market_style(lookback_days=30)
    assert result['style'] in detector.STYLE_FACTORS


def test_calculate_value_style_score():
    detector = MarketStyleDetector()
    score = detector._calculate_value_style_score(60)
    assert 0 <= score <= 1


def test_calculate_growth_style_score():
    detector = MarketStyleDetector()
    score = detector._calculate_growth_style_score(60)
    assert 0 <= score <= 1


def test_calculate_cycle_style_score():
    detector = MarketStyleDetector()
    score = detector._calculate_cycle_style_score(60)
    assert 0 <= score <= 1


def test_get_detailed_indicators():
    detector = MarketStyleDetector()
    indicators = detector._get_detailed_indicators(60)
    assert isinstance(indicators, dict)
    assert 'banking_performance' in indicators
    assert 'tech_performance' in indicators
    assert 'cycle_performance' in indicators


def test_get_default_result():
    detector = MarketStyleDetector()
    result = detector._get_default_result()
    assert result['style'] == detector.STYLE_GROWTH
    assert result['confidence'] == 0.33
    assert result['scores'][detector.STYLE_VALUE] == 0.33


def test_recommended_factors_match_dominant_style():
    detector = MarketStyleDetector()
    result = detector.detect_market_style()
    expected = detector.STYLE_FACTORS[result['style']]
    assert result['recommended_factors'] == expected


def test_detect_market_style_returns_default_on_exception():
    detector = MarketStyleDetector()
    original = detector._calculate_value_style_score
    detector._calculate_value_style_score = lambda x: 1 / 0
    try:
        result = detector.detect_market_style()
        assert result['style'] == detector.STYLE_GROWTH
    finally:
        detector._calculate_value_style_score = original
