"""
ML query handlers for the QuantSys CLI daemon.

Migrated from the legacy akshare_bridge.py. These functions handle model
training, prediction, signal combination, and visualization.
"""

import json
import pickle
import numpy as np
from datetime import datetime
from pathlib import Path
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
    from .context import build_context

    ctx = build_context()
    return arbitrate_signals(ctx.quant_root, params)


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


def _train_model(params: Dict[str, Any]) -> Any:
    """Train a new ML model."""
    from quantsys.ml.training_service import MLTrainingService
    from .context import build_context

    try:
        ctx = build_context()

        # 获取数据库连接
        import psycopg2
        import os

        conn = psycopg2.connect(
            host=os.getenv('PGHOST', '127.0.0.1'),
            port=os.getenv('PGPORT', '5432'),
            database=os.getenv('PGDATABASE', 'quant_investment'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', '')
        )

        service = MLTrainingService(conn)

        # 加载训练数据
        data_df, labels_df = service.load_training_data(
            days=params.get("days", 180),
            future_days=params.get("future_days", 5),
            return_threshold=params.get("return_threshold", 0.05),
            symbols=params.get("symbols")
        )

        # 准备特征
        X, y, feature_names = service.prepare_features(data_df)

        # 训练模型
        model_type = params.get("model_type", "xgboost")
        if model_type == "xgboost":
            report = service.train_xgboost(X, y, feature_names, n_splits=params.get("cv_splits", 5))
        else:
            conn.close()
            return {
                "success": False,
                "error": f"Unsupported model type: {model_type}"
            }

        # 保存报告
        job_id = params.get("job_id", f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        service.save_training_report(report, job_id)

        conn.close()

        # 清理 NaN 值
        def clean_nan(obj):
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nan(v) for v in obj]
            elif isinstance(obj, float) and np.isnan(obj):
                return None
            else:
                return obj

        return clean_nan(report)

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def _list_models(params: Dict[str, Any]) -> Any:
    """List all trained models."""
    try:
        model_dir = Path.home() / '.pi-invest' / 'ml' / 'models'

        if not model_dir.exists():
            return {"models": [], "total": 0}

        models = []

        for model_file in model_dir.glob("xgboost_model_*.pkl"):
            timestamp = model_file.stem.replace("xgboost_model_", "")
            report_file = model_dir / f"training_report_{timestamp}.json"

            if report_file.exists():
                with open(report_file) as f:
                    report = json.load(f)

                # 清理 NaN 值
                def clean_nan(obj):
                    if isinstance(obj, dict):
                        return {k: clean_nan(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [clean_nan(v) for v in obj]
                    elif obj is None or (isinstance(obj, float) and np.isnan(obj)):
                        return None
                    else:
                        return obj

                models.append({
                    "model_id": timestamp,
                    "model_type": "xgboost",
                    "model_path": str(model_file),
                    "timestamp": report.get("timestamp"),
                    "test_accuracy": clean_nan(report.get("test_metrics", {}).get("accuracy")),
                    "test_f1": clean_nan(report.get("test_metrics", {}).get("f1")),
                    "n_features": report.get("n_features")
                })

        # 按时间倒序排序
        models.sort(key=lambda x: x["timestamp"] if x["timestamp"] else "", reverse=True)

        return {"models": models, "total": len(models)}

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "models": [],
            "total": 0
        }


def _evaluate_model(params: Dict[str, Any]) -> Any:
    """Evaluate a trained model."""
    try:
        model_id = params.get("model_id", "latest")
        model_dir = Path.home() / '.pi-invest' / 'ml' / 'models'

        if model_id == "latest":
            report_file = model_dir / "training_report_latest.json"
        else:
            report_file = model_dir / f"training_report_{model_id}.json"

        if not report_file.exists():
            return {
                "success": False,
                "error": f"Model report not found: {report_file}"
            }

        with open(report_file) as f:
            report = json.load(f)

        # 清理 NaN 值
        def clean_nan(obj):
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nan(v) for v in obj]
            elif obj is None or (isinstance(obj, float) and np.isnan(obj)):
                return None
            else:
                return obj

        return clean_nan({
            "success": True,
            "model_id": model_id,
            "model_type": report.get("model_type"),
            "timestamp": report.get("timestamp"),
            "data": report.get("data"),
            "cv_results": report.get("cv_results"),
            "test_metrics": report.get("test_metrics"),
            "feature_importance": report.get("feature_importance"),
            "feature_names": report.get("feature_names")
        })

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def _monitor_model(params: Dict[str, Any]) -> Any:
    """Monitor model for feature drift."""
    try:
        model_id = params.get("model_id", "latest")
        model_dir = Path.home() / '.pi-invest' / 'ml' / 'models'

        # 加载模型
        if model_id == "latest":
            model_file = model_dir / "xgboost_latest.pkl"
            report_file = model_dir / "training_report_latest.json"
        else:
            model_file = model_dir / f"xgboost_model_{model_id}.pkl"
            report_file = model_dir / f"training_report_{model_id}.json"

        if not model_file.exists():
            return {
                "success": False,
                "error": f"Model not found: {model_file}"
            }

        if not report_file.exists():
            return {
                "success": False,
                "error": f"Model report not found: {report_file}"
            }

        with open(model_file, 'rb') as f:
            model = pickle.load(f)

        with open(report_file) as f:
            report = json.load(f)

        # 获取训练时的特征重要性
        train_importance = np.array(report.get("feature_importance", []))
        feature_names = report.get("feature_names", [])

        # 当前模型的特征重要性
        current_importance = model.feature_importances_

        # 计算漂移（欧氏距离）
        drift_score = float(np.linalg.norm(train_importance - current_importance))

        # 找出变化最大的特征
        importance_diff = np.abs(train_importance - current_importance)
        top_drift_indices = np.argsort(importance_diff)[-10:][::-1]

        top_drifts = [
            {
                "feature": feature_names[i],
                "train_importance": float(train_importance[i]),
                "current_importance": float(current_importance[i]),
                "drift": float(importance_diff[i])
            }
            for i in top_drift_indices
        ]

        drift_threshold = params.get("drift_threshold", 0.1)

        return {
            "success": True,
            "model_id": model_id,
            "drift_score": drift_score,
            "drift_threshold": drift_threshold,
            "is_drifted": drift_score > drift_threshold,
            "top_drifts": top_drifts,
            "recommendation": "Retrain model" if drift_score > drift_threshold else "Model is stable"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Register all ML handlers with the daemon method map
def register_all() -> None:
    register_daemon_method("run_confidence_calibration", _run_confidence_calibration)
    register_daemon_method("predict_signal_confidence", _predict_signal_confidence)
    register_daemon_method("combine_strategy_signals", _combine_strategy_signals)
    register_daemon_method("plot_model_accuracy_trend", _plot_model_accuracy_trend)
    register_daemon_method("plot_equity_curve", _plot_equity_curve)
    register_daemon_method("plot_strategy_comparison", _plot_strategy_comparison)
    register_daemon_method("plot_feature_importance", _plot_feature_importance)

    # New ML daemon methods
    register_daemon_method("train_model", _train_model)
    register_daemon_method("list_models", _list_models)
    register_daemon_method("evaluate_model", _evaluate_model)
    register_daemon_method("monitor_model", _monitor_model)
