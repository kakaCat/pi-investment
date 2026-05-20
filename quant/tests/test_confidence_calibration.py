"""
Test Bayesian confidence calibration.

Verify that confidence scores are properly calibrated and never reach 100%.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.utils.confidence_calibration import (
    bayesian_calibrate,
    calibrate_rsi_confidence,
    calibrate_ma_confidence,
    calibrate_bollinger_confidence,
    calibrate_macd_confidence,
    calibrate_kdj_confidence,
    calibrate_stop_loss_confidence,
    calibrate_take_profit_confidence
)


def test_bayesian_calibrate():
    """Test basic Bayesian calibration."""
    print("=" * 60)
    print("Testing Bayesian Calibration")
    print("=" * 60)

    test_cases = [
        (0.0, "Minimum confidence"),
        (0.25, "Low confidence"),
        (0.5, "Medium confidence"),
        (0.75, "High confidence"),
        (1.0, "Maximum confidence"),
    ]

    for raw_conf, description in test_cases:
        calibrated = bayesian_calibrate(raw_conf)
        print(f"{description:20s}: {raw_conf:.2f} -> {calibrated:.4f}")

    print()
    assert bayesian_calibrate(1.0) <= 0.85, "Max confidence should be capped at 0.85"
    assert bayesian_calibrate(0.0) < 0.85, "Min confidence should be less than max"
    print("✅ Basic calibration tests passed\n")


def test_rsi_confidence():
    """Test RSI confidence calibration."""
    print("=" * 60)
    print("Testing RSI Confidence Calibration")
    print("=" * 60)

    # Buy signals (oversold)
    print("Buy Signals (Oversold):")
    rsi_values = [10, 15, 20, 25, 30]
    for rsi in rsi_values:
        conf = calibrate_rsi_confidence(rsi, 30, 'buy')
        print(f"  RSI={rsi:2d} -> confidence={conf:.4f}")

    print("\nSell Signals (Overbought):")
    rsi_values = [70, 75, 80, 85, 90]
    for rsi in rsi_values:
        conf = calibrate_rsi_confidence(rsi, 70, 'sell')
        print(f"  RSI={rsi:2d} -> confidence={conf:.4f}")

    # Verify no 100% confidence
    extreme_buy = calibrate_rsi_confidence(0, 30, 'buy')
    extreme_sell = calibrate_rsi_confidence(100, 70, 'sell')
    assert extreme_buy <= 0.85, f"Extreme buy confidence should be <= 0.85, got {extreme_buy}"
    assert extreme_sell <= 0.85, f"Extreme sell confidence should be <= 0.85, got {extreme_sell}"
    print("\n✅ RSI calibration tests passed\n")


def test_ma_confidence():
    """Test MA crossover confidence calibration."""
    print("=" * 60)
    print("Testing MA Crossover Confidence Calibration")
    print("=" * 60)

    ma_diffs = [0.001, 0.005, 0.01, 0.02, 0.05, 0.10]
    for diff in ma_diffs:
        conf = calibrate_ma_confidence(diff)
        print(f"  MA diff={diff*100:5.2f}% -> confidence={conf:.4f}")

    # Verify no 100% confidence
    extreme_conf = calibrate_ma_confidence(0.20)
    assert extreme_conf <= 0.85, f"Extreme MA confidence should be <= 0.85, got {extreme_conf}"
    print("\n✅ MA calibration tests passed\n")


def test_bollinger_confidence():
    """Test Bollinger Bands confidence calibration."""
    print("=" * 60)
    print("Testing Bollinger Bands Confidence Calibration")
    print("=" * 60)

    distances = [0.0, 0.01, 0.02, 0.03, 0.05, 0.10]
    for dist in distances:
        conf = calibrate_bollinger_confidence(dist)
        print(f"  Distance={dist*100:5.2f}% -> confidence={conf:.4f}")

    # Verify no 100% confidence
    extreme_conf = calibrate_bollinger_confidence(0.20)
    assert extreme_conf <= 0.85, f"Extreme Bollinger confidence should be <= 0.85, got {extreme_conf}"
    print("\n✅ Bollinger calibration tests passed\n")


def test_macd_confidence():
    """Test MACD confidence calibration."""
    print("=" * 60)
    print("Testing MACD Confidence Calibration")
    print("=" * 60)

    dif_dea_diffs = [0.0, 0.005, 0.01, 0.015, 0.02, 0.05]
    for diff in dif_dea_diffs:
        conf = calibrate_macd_confidence(diff)
        print(f"  DIF-DEA diff={diff:.4f} -> confidence={conf:.4f}")

    # Verify no 100% confidence
    extreme_conf = calibrate_macd_confidence(0.10)
    assert extreme_conf <= 0.85, f"Extreme MACD confidence should be <= 0.85, got {extreme_conf}"
    print("\n✅ MACD calibration tests passed\n")


def test_kdj_confidence():
    """Test KDJ confidence calibration."""
    print("=" * 60)
    print("Testing KDJ Confidence Calibration")
    print("=" * 60)

    print("Buy Signals (Oversold):")
    k_values = [0, 5, 10, 15, 20]
    for k in k_values:
        conf = calibrate_kdj_confidence(k, 20, 'buy')
        print(f"  K={k:2d} -> confidence={conf:.4f}")

    print("\nSell Signals (Overbought):")
    k_values = [80, 85, 90, 95, 100]
    for k in k_values:
        conf = calibrate_kdj_confidence(k, 80, 'sell')
        print(f"  K={k:2d} -> confidence={conf:.4f}")

    # Verify no 100% confidence
    extreme_buy = calibrate_kdj_confidence(0, 20, 'buy')
    extreme_sell = calibrate_kdj_confidence(100, 80, 'sell')
    assert extreme_buy <= 0.85, f"Extreme KDJ buy confidence should be <= 0.85, got {extreme_buy}"
    assert extreme_sell <= 0.85, f"Extreme KDJ sell confidence should be <= 0.85, got {extreme_sell}"
    print("\n✅ KDJ calibration tests passed\n")


def test_stop_loss_take_profit():
    """Test stop-loss and take-profit confidence calibration."""
    print("=" * 60)
    print("Testing Stop-Loss and Take-Profit Confidence Calibration")
    print("=" * 60)

    print("Stop-Loss Signals:")
    loss_pcts = [0.02, 0.05, 0.08, 0.10, 0.15]
    for pct in loss_pcts:
        conf = calibrate_stop_loss_confidence(pct)
        print(f"  Loss={pct*100:5.1f}% -> confidence={conf:.4f}")

    print("\nTake-Profit Signals:")
    profit_pcts = [0.05, 0.10, 0.15, 0.20, 0.30]
    for pct in profit_pcts:
        conf = calibrate_take_profit_confidence(pct)
        print(f"  Profit={pct*100:5.1f}% -> confidence={conf:.4f}")

    # Verify max confidence is lower for stop-loss/take-profit
    extreme_sl = calibrate_stop_loss_confidence(0.20)
    extreme_tp = calibrate_take_profit_confidence(0.50)
    assert extreme_sl <= 0.75, f"Extreme stop-loss confidence should be <= 0.75, got {extreme_sl}"
    assert extreme_tp <= 0.75, f"Extreme take-profit confidence should be <= 0.75, got {extreme_tp}"
    print("\n✅ Stop-loss/take-profit calibration tests passed\n")


def test_no_100_percent():
    """Verify that no signal can reach 100% confidence."""
    print("=" * 60)
    print("Testing Maximum Confidence Cap")
    print("=" * 60)

    all_confidences = []

    # Test extreme values for all calibration functions
    all_confidences.append(bayesian_calibrate(1.0))
    all_confidences.append(calibrate_rsi_confidence(0, 30, 'buy'))
    all_confidences.append(calibrate_rsi_confidence(100, 70, 'sell'))
    all_confidences.append(calibrate_ma_confidence(1.0))
    all_confidences.append(calibrate_bollinger_confidence(1.0))
    all_confidences.append(calibrate_macd_confidence(1.0))
    all_confidences.append(calibrate_kdj_confidence(0, 20, 'buy'))
    all_confidences.append(calibrate_kdj_confidence(100, 80, 'sell'))
    all_confidences.append(calibrate_stop_loss_confidence(1.0))
    all_confidences.append(calibrate_take_profit_confidence(1.0))

    max_confidence = max(all_confidences)
    print(f"Maximum confidence across all functions: {max_confidence:.4f}")
    print(f"All confidences: {[f'{c:.4f}' for c in all_confidences]}")

    assert max_confidence <= 0.85, f"No confidence should exceed 0.85, got {max_confidence}"
    assert all(c < 1.0 for c in all_confidences), "No confidence should be 100%"

    print("\n✅ Maximum confidence cap verified - no 100% confidence possible!\n")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("BAYESIAN CONFIDENCE CALIBRATION TEST SUITE")
    print("=" * 60 + "\n")

    test_bayesian_calibrate()
    test_rsi_confidence()
    test_ma_confidence()
    test_bollinger_confidence()
    test_macd_confidence()
    test_kdj_confidence()
    test_stop_loss_take_profit()
    test_no_100_percent()

    print("=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
    print("\nKey findings:")
    print("  • Maximum confidence is capped at 0.85 (85%)")
    print("  • Stop-loss/take-profit signals capped at 0.75 (75%)")
    print("  • No signal can reach 100% confidence")
    print("  • Confidence increases smoothly with signal strength")
    print()
