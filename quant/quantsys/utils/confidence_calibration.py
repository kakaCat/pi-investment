"""
Bayesian confidence calibration for trading signals.

Implements a sigmoid-based calibration to prevent overconfident predictions.
"""
import numpy as np
from typing import Union


def bayesian_calibrate(
    raw_confidence: float,
    k: float = 0.3,
    max_confidence: float = 0.85
) -> float:
    """
    Apply Bayesian calibration to raw confidence scores.

    Uses sigmoid function to map raw scores to calibrated confidence:
    confidence = 1 / (1 + e^(-k * raw_score))

    Then caps at max_confidence to prevent overconfidence.

    Args:
        raw_confidence: Raw confidence score (0-1)
        k: Steepness parameter (default: 0.3)
            - Higher k = steeper curve = more aggressive calibration
            - Lower k = gentler curve = more conservative calibration
        max_confidence: Maximum allowed confidence (default: 0.85)

    Returns:
        Calibrated confidence score (0-max_confidence)

    Examples:
        >>> bayesian_calibrate(1.0)  # Perfect signal
        0.85
        >>> bayesian_calibrate(0.5)  # Neutral signal
        ~0.50
        >>> bayesian_calibrate(0.0)  # Weak signal
        ~0.15
    """
    if raw_confidence < 0 or raw_confidence > 1:
        raise ValueError(f"raw_confidence must be in [0, 1], got {raw_confidence}")

    # Convert to logit space (centered around 0)
    # Map [0, 1] to approximately [-10, 10]
    logit = (raw_confidence - 0.5) * 20

    # Apply sigmoid with steepness k
    calibrated = 1 / (1 + np.exp(-k * logit))

    # Cap at max_confidence
    return min(calibrated, max_confidence)


def calibrate_rsi_confidence(
    rsi: float,
    threshold: float,
    action: str,
    k: float = 0.3,
    max_confidence: float = 0.85
) -> float:
    """
    Calibrate RSI-based signal confidence.

    Args:
        rsi: RSI value (0-100)
        threshold: Threshold value (e.g., 30 for oversold, 70 for overbought)
        action: 'buy' or 'sell'
        k: Steepness parameter
        max_confidence: Maximum confidence

    Returns:
        Calibrated confidence score
    """
    if action == 'buy':
        # For buy signals, lower RSI = higher confidence
        # RSI 0 -> raw_conf 1.0, RSI 30 -> raw_conf 0.5
        raw_confidence = max(0, (threshold - rsi) / threshold)
    else:  # sell
        # For sell signals, higher RSI = higher confidence
        # RSI 100 -> raw_conf 1.0, RSI 70 -> raw_conf 0.5
        raw_confidence = max(0, (rsi - threshold) / (100 - threshold))

    return bayesian_calibrate(raw_confidence, k, max_confidence)


def calibrate_ma_confidence(
    ma_diff_pct: float,
    k: float = 0.3,
    max_confidence: float = 0.85
) -> float:
    """
    Calibrate MA crossover signal confidence.

    Args:
        ma_diff_pct: Percentage difference between MAs (absolute value)
        k: Steepness parameter
        max_confidence: Maximum confidence

    Returns:
        Calibrated confidence score
    """
    # Larger separation = higher confidence
    # 0% -> 0.3, 2% -> 0.7, 5%+ -> 1.0
    raw_confidence = min(1.0, 0.3 + (ma_diff_pct / 0.05) * 0.7)

    return bayesian_calibrate(raw_confidence, k, max_confidence)


def calibrate_bollinger_confidence(
    distance_pct: float,
    k: float = 0.3,
    max_confidence: float = 0.85
) -> float:
    """
    Calibrate Bollinger Bands signal confidence.

    Args:
        distance_pct: Distance from band as percentage (absolute value)
        k: Steepness parameter
        max_confidence: Maximum confidence

    Returns:
        Calibrated confidence score
    """
    # Further from band = higher confidence
    # 0% -> 0.4, 2% -> 0.8, 5%+ -> 1.0
    raw_confidence = min(1.0, 0.4 + (distance_pct / 0.05) * 0.6)

    return bayesian_calibrate(raw_confidence, k, max_confidence)


def calibrate_macd_confidence(
    dif_dea_diff: float,
    k: float = 0.3,
    max_confidence: float = 0.85
) -> float:
    """
    Calibrate MACD signal confidence.

    Args:
        dif_dea_diff: Absolute difference between DIF and DEA
        k: Steepness parameter
        max_confidence: Maximum confidence

    Returns:
        Calibrated confidence score
    """
    # Larger difference = higher confidence
    # 0 -> 0.3, 0.01 -> 0.7, 0.02+ -> 1.0
    raw_confidence = min(1.0, 0.3 + (dif_dea_diff / 0.02) * 0.7)

    return bayesian_calibrate(raw_confidence, k, max_confidence)


def calibrate_kdj_confidence(
    k_value: float,
    threshold: float,
    action: str,
    k_param: float = 0.3,
    max_confidence: float = 0.85
) -> float:
    """
    Calibrate KDJ signal confidence.

    Args:
        k_value: K value from KDJ indicator
        threshold: Threshold value (e.g., 20 for oversold, 80 for overbought)
        action: 'buy' or 'sell'
        k_param: Steepness parameter
        max_confidence: Maximum confidence

    Returns:
        Calibrated confidence score
    """
    if action == 'buy':
        # Lower K = higher confidence
        raw_confidence = max(0, (threshold - k_value) / threshold)
    else:  # sell
        # Higher K = higher confidence
        raw_confidence = max(0, (k_value - threshold) / (100 - threshold))

    return bayesian_calibrate(raw_confidence, k_param, max_confidence)


def calibrate_stop_loss_confidence(
    distance_from_entry_pct: float,
    k: float = 0.3,
    max_confidence: float = 0.75
) -> float:
    """
    Calibrate stop-loss signal confidence.

    Stop-loss signals should have lower max confidence since they're
    defensive rather than predictive.

    Args:
        distance_from_entry_pct: How far price has moved from entry (as %)
        k: Steepness parameter
        max_confidence: Maximum confidence (default 0.75, lower than normal)

    Returns:
        Calibrated confidence score
    """
    # Larger loss = higher urgency but not necessarily higher confidence
    # 5% loss -> 0.6, 10% loss -> 0.75
    raw_confidence = min(1.0, 0.5 + (distance_from_entry_pct / 0.1) * 0.5)

    return bayesian_calibrate(raw_confidence, k, max_confidence)


def calibrate_take_profit_confidence(
    distance_from_entry_pct: float,
    k: float = 0.3,
    max_confidence: float = 0.75
) -> float:
    """
    Calibrate take-profit signal confidence.

    Take-profit signals should have lower max confidence since they're
    based on predetermined targets rather than market conditions.

    Args:
        distance_from_entry_pct: How far price has moved from entry (as %)
        k: Steepness parameter
        max_confidence: Maximum confidence (default 0.75, lower than normal)

    Returns:
        Calibrated confidence score
    """
    # Larger profit = higher confidence in taking it
    # 10% profit -> 0.6, 20% profit -> 0.75
    raw_confidence = min(1.0, 0.5 + (distance_from_entry_pct / 0.2) * 0.5)

    return bayesian_calibrate(raw_confidence, k, max_confidence)
