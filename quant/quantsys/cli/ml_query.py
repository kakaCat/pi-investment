"""
ML query handlers for the QuantSys CLI daemon.

Migrated from the legacy akshare_bridge.py. These functions handle model
training, prediction, signal combination, and visualization.
"""

from typing import Any, Dict

from .daemon import register_daemon_method


def _run_confidence_calibration(params: Dict[str, Any]) -> Any:
    """Calibrate prediction confidence scores."""
    from quantsys.ml.confidence_calibrator import ConfidenceCalibrator

    calibrator = ConfidenceCalibrator()
    return calibrator.run(
        forward_days=params.get("forward_days", 5),
        return_threshold=params.get("return_threshold", 0.02),
        max_symbols=params.get("max_symbols", 500),
        lookback_days=params.get("lookback_days", 180),
    )


def _predict_signal_confidence(params: Dict[str, Any]) -> Any:
    """Predict signal confidence for a given stock."""
    from quantsys.ml.signal_predictor import SignalPredictor

    predictor = SignalPredictor()
    return predictor.predict(
        symbol=params.get("symbol"),
        model_name=params.get("model_name"),
        features=params.get("features"),
    )


def _combine_strategy_signals(params: Dict[str, Any]) -> Any:
    """Combine signals from multiple strategies."""
    from .strategy_analytics import arbitrate_signals
    from .context import CliContext

    ctx = CliContext(db_path=None, output_dir=None, python="python3")
    return arbitrate_signals(ctx, params)


def _plot_model_accuracy_trend(params: Dict[str, Any]) -> Any:
    """Generate model accuracy trend chart."""
    from quantsys.ml.visualizer import plot_model_accuracy_trend

    return plot_model_accuracy_trend(
        model_name=params.get("model_name"),
        output_path=params.get("output_path"),
    )


def _plot_equity_curve(params: Dict[str, Any]) -> Any:
    """Generate equity curve chart."""
    from quantsys.ml.visualizer import plot_equity_curve

    return plot_equity_curve(
        portfolio_history=params.get("portfolio_history"),
        benchmark=params.get("benchmark"),
        output_path=params.get("output_path"),
    )


def _plot_strategy_comparison(params: Dict[str, Any]) -> Any:
    """Generate strategy comparison chart."""
    from quantsys.ml.visualizer import plot_strategy_comparison

    return plot_strategy_comparison(
        strategy_results=params.get("strategy_results"),
        output_path=params.get("output_path"),
    )


def _plot_feature_importance(params: Dict[str, Any]) -> Any:
    """Generate feature importance chart."""
    from quantsys.ml.visualizer import plot_feature_importance

    return plot_feature_importance(
        feature_importance=params.get("feature_importance"),
        model_name=params.get("model_name"),
        top_n=params.get("top_n", 20),
        output_path=params.get("output_path"),
    )


# Register all ML handlers with the daemon method map
def register_all() -> None:
    register_daemon_method("run_confidence_calibration", _run_confidence_calibration)
    register_daemon_method("predict_signal_confidence", _predict_signal_confidence)
    register_daemon_method("combine_strategy_signals", _combine_strategy_signals)
    register_daemon_method("plot_model_accuracy_trend", _plot_model_accuracy_trend)
    register_daemon_method("plot_equity_curve", _plot_equity_curve)
    register_daemon_method("plot_strategy_comparison", _plot_strategy_comparison)
    register_daemon_method("plot_feature_importance", _plot_feature_importance)
