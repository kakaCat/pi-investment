"""
Feature extraction from trading signals for ML model training and prediction.
"""

def extract_features(signal: dict) -> dict:
    """
    Extract ML features from a signal object.

    Args:
        signal: Signal dictionary with indicators

    Returns:
        Dictionary of normalized features for ML model
    """
    indicators = signal.get('indicators', {})

    # Safe get with defaults
    rsi = indicators.get('rsi', 50)
    ma5 = indicators.get('ma5', 0)
    ma20 = indicators.get('ma20', 1)
    ma60 = indicators.get('ma60', 1)
    macd_hist = indicators.get('macd_histogram', 0)
    bb_upper = indicators.get('bollinger_upper', 0)
    bb_lower = indicators.get('bollinger_lower', 0)
    current_price = indicators.get('close', signal.get('price', 0))
    volume_ratio = indicators.get('volume_ratio', 1)

    # Calculate derived features
    ma5_ma20_ratio = ma5 / ma20 if ma20 > 0 else 1
    ma20_ma60_ratio = ma20 / ma60 if ma60 > 0 else 1
    bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else 0.5

    # Strategy condition match ratio
    reason = signal.get('reason', '')
    conditions_matched = len(reason.split(',')) if reason else 1
    conditions_matched_ratio = min(conditions_matched / 3, 1.0)

    # Action encoding
    action = 0 if signal.get('action') == 'buy' else 1

    return {
        'rsi': rsi,
        'ma5_ma20_ratio': ma5_ma20_ratio,
        'ma20_ma60_ratio': ma20_ma60_ratio,
        'macd_histogram': macd_hist,
        'bb_position': bb_position,
        'volume_ratio': volume_ratio,
        'conditions_matched_ratio': conditions_matched_ratio,
        'action': action
    }


def features_to_array(features: dict) -> list:
    """
    Convert feature dictionary to ordered array for model input.

    Order must match training order.
    """
    return [
        features['rsi'],
        features['ma5_ma20_ratio'],
        features['ma20_ma60_ratio'],
        features['macd_histogram'],
        features['bb_position'],
        features['volume_ratio'],
        features['conditions_matched_ratio'],
        features['action']
    ]
