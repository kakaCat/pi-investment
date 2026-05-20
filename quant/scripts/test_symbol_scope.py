import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import calculate_factors, generate_signals, ml_retrain


def test_factor_and_signal_scripts_parse_comma_separated_symbols():
    assert calculate_factors.parse_symbols("000001, 600036\n600519") == [
        "000001",
        "600036",
        "600519",
    ]
    assert generate_signals.parse_symbols("sz000001,SH600036") == [
        "000001",
        "600036",
    ]


def test_factor_and_signal_scripts_accept_job_id_argument():
    factor_parser = calculate_factors.build_arg_parser()
    signal_parser = generate_signals.build_arg_parser()

    factor_args = factor_parser.parse_args(["--job-id", "factor_compute_123", "--symbols", "000001"])
    signal_args = signal_parser.parse_args(["--job-id", "signal_generate_123", "--symbols", "000001"])

    assert factor_args.job_id == "factor_compute_123"
    assert factor_args.symbols == "000001"
    assert signal_args.job_id == "signal_generate_123"
    assert signal_args.symbols == "000001"


def test_ml_retrain_filters_training_frames_to_selected_symbols():
    import pandas as pd

    retrainer = ml_retrain.MLRetrainer.__new__(ml_retrain.MLRetrainer)
    klines = pd.DataFrame([
        {"symbol": "000001", "date": "2026-05-18", "close": 10},
        {"symbol": "600036", "date": "2026-05-18", "close": 20},
        {"symbol": "600519", "date": "2026-05-18", "close": 30},
    ])
    factors = pd.DataFrame([
        {"symbol": "000001", "date": "2026-05-18", "factor_name": "MA5", "factor_value": 10},
        {"symbol": "600036", "date": "2026-05-18", "factor_name": "MA5", "factor_value": 20},
        {"symbol": "600519", "date": "2026-05-18", "factor_name": "MA5", "factor_value": 30},
    ])

    filtered_klines, filtered_factors = retrainer.filter_training_frames(
        klines,
        factors,
        ["000001", "600036"],
    )

    assert filtered_klines["symbol"].tolist() == ["000001", "600036"]
    assert filtered_factors["symbol"].tolist() == ["000001", "600036"]
