"""
ML Engine API Routes

Provides training, prediction, model info, and feature importance endpoints
for the web-frontend ML Engine page.

Persistence: model metadata → quant.ml_models (PostgreSQL)
             model binary   → .pi-invest/ml/models/*.pkl (local disk)
"""
from __future__ import annotations

import json as _json
import logging
import math
import re
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any

import pandas as pd
from flask import jsonify, request
from concurrent.futures import ThreadPoolExecutor, as_completed

from adapters.outbound.repositories import MlModelORMRepository
from adapters.outbound.repositories import TraceabilityORMRepository

logger = logging.getLogger(__name__)

# ML 助手（已解耦到中立层，向后兼容再导出）
from adapters.shared.ml_helpers import (
    MODEL_DIR, _json, _get_model_repo, _convert_keys_to_snake, _sanitize_for_json,
    _ml_error_handler, _strip_suffix, _normalize_kline, _confidence_label,
    _save_ml_predictions, _resolve_latest_version,
)
def register_ml_routes(app, ds):
    """Register ML engine API routes on the Flask app."""

    # ── POST /api/ml/train ──────────────────────────────────────────

    @app.route("/api/ml/train", methods=["POST"])
    @_ml_error_handler
    def ml_train():
        """Train an ML model (xgboost / lightgbm / randomforest)."""
        data = request.get_json() or {}
        data = _convert_keys_to_snake(data)

        model_type = data.get("model_type", "xgboost")
        start_date = data.get("start_date", "2020-01-01")
        end_date = data.get("end_date", datetime.now().strftime("%Y-%m-%d"))
        test_size = float(data.get("test_size", 0.2))
        symbols: list[str] = [_strip_suffix(s) for s in (data.get("symbols") or [])] if data.get("symbols") else None
        params = data.get("params", {})

        # Validate model_type (frontend sends randomforest → map to xgboost)
        if model_type == "randomforest":
            model_type = "xgboost"  # fallback: no RF trainer yet
        if model_type not in ("xgboost", "lightgbm"):
            return jsonify({"success": False, "error": f"不支持的模型类型: {model_type}"}), 400

        # Resolve symbols (default to top 50 by market cap for speed)
        if not symbols:
            stocks = ds.stock.get_all(limit=50)
            symbols = [s["symbol"] for s in stocks]

        if not symbols:
            return jsonify({"success": False, "error": "没有可用的股票数据"}), 400

        logger.info(
            "ML train: model=%s, symbols=%d, %s→%s, test_size=%.2f",
            model_type,
            len(symbols),
            start_date,
            end_date,
            test_size,
        )

        # Parallel fetch klines
        klines_dict: dict[str, list[dict]] = {}

        def _fetch_one_kline(sym: str):
            try:
                rows = ds.kline.get_daily_klines(sym, start_date, end_date)
                # 🔧 兼容 polars DataFrame
                import polars as pl
                if isinstance(rows, pl.DataFrame):
                    if rows.is_empty():
                        return sym, None
                    rows = rows.to_dicts()
                if rows:
                    return sym, [_normalize_kline(r) for r in rows]
            except Exception:
                logger.debug("Skip %s (no kline data)", sym)
            return sym, None

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_fetch_one_kline, s): s for s in symbols}
            for future in as_completed(futures):
                sym, rows = future.result()
                if rows:
                    klines_dict[sym] = rows

        logger.info("ML train: fetched klines for %d/%d symbols", len(klines_dict), len(symbols))

        if not klines_dict:
            return jsonify({"success": False, "error": "指定日期范围内没有K线数据"}), 400

        # Build feature matrix from pre-calculated factor_values in DB (parallel)
        all_rows: list[dict] = []

        def _process_one_symbol(sym: str):
            try:
                factors_data = ds.factor.get_factors_range(sym, start_date, end_date)
                # get_factors_range 返回 polars DataFrame：bool(df) 抛 TypeError，
                # 直接迭代产出 Series 而非 dict，必须用 is_empty + iter_rows(named=True)
                if factors_data is None or factors_data.is_empty():
                    return []
                # Pivot: {factor_date: {factor_name: value}}
                by_date: dict[str, dict[str, float]] = {}
                for fv in factors_data.iter_rows(named=True):
                    d = str(fv.get("factor_date") or fv.get("date", ""))
                    if not d:
                        continue
                    by_date.setdefault(d, {})[fv["factor_name"]] = float(
                        fv.get("factor_value", 0) or 0
                    )
                # Merge with kline close for target
                close_map: dict[str, float] = {}
                klines = klines_dict.get(sym, [])
                for k in klines:
                    d = str(k.get("date", k.get("trade_date", "")))
                    close_map[d] = float(k.get("close", 0))

                rows = []
                sorted_dates = sorted(by_date.keys())
                for i in range(len(sorted_dates) - 1):
                    cur_date = sorted_dates[i]
                    next_date = sorted_dates[i + 1]
                    cur_close = close_map.get(cur_date, 0)
                    next_close = close_map.get(next_date, 0)
                    if cur_close <= 0:
                        continue
                    row = dict(by_date[cur_date])
                    row["__target"] = 1 if next_close > cur_close else 0
                    row["__symbol"] = sym
                    row["__date"] = cur_date
                    rows.append(row)
                return rows
            except Exception:
                logger.debug("Skip factor data for %s", sym)
                return []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_process_one_symbol, s): s for s in symbols}
            for future in as_completed(futures):
                all_rows.extend(future.result())

        logger.info("ML train: processed factors for %d symbols, %d total samples", len(symbols), len(all_rows))

        # Give parallel DB connections time to drain before the critical DB write
        # Prevents "too many clients" error from saturating PostgreSQL's connection pool
        import time as _time
        _time.sleep(1.0)

        if len(all_rows) < 10:
            return jsonify(
                {"success": False, "error": f"有效样本不足 (仅有{len(all_rows)}条)"}
            ), 400

        X = pd.DataFrame(all_rows)
        y = X.pop("__target")
        X = X.drop(columns=["__symbol", "__date"], errors="ignore")

        # Fill NaN and scale
        X = X.fillna(X.median(numeric_only=True)).fillna(0)
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X = pd.DataFrame(X_scaled, columns=X.columns)

        # Train
        from application.services.ml_pipeline.trainer import MLTrainer

        trainer = MLTrainer(model_type=model_type)
        results = trainer.train(X, y, test_size=test_size, params=params)

        # Persist model file + metadata to DB
        version = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = str(MODEL_DIR / f"{model_type}_{version}.pkl")
        try:
            trainer.save_model(version=version)
        except Exception as e:
            logger.warning("Model file save skipped: %s", e)

        # Write metadata to quant.ml_models (with retry for transient DB failures)
        train_date = datetime.now(timezone.utc).isoformat()
        feature_importance = results.get("feature_importance", {})
        feature_names = list(X.columns)

        # Force re-connect before critical metadata write (parallel workers may have
        # exhausted the connection pool during factor extraction)
        _get_model_repo()._ensure_db(max_retries=5, retry_delay=2.0)

        # Convert numpy types to native Python for psycopg2 compatibility
        def _to_native(val):
            """Recursively convert numpy types to native Python."""
            import numpy as _np
            if isinstance(val, (dict,)):
                return {k: _to_native(v) for k, v in val.items()}
            if isinstance(val, (list, tuple)):
                return [_to_native(v) for v in val]
            if isinstance(val, (_np.floating,)):
                return float(val)
            if isinstance(val, (_np.integer,)):
                return int(val)
            if isinstance(val, (_np.bool_,)):
                return bool(val)
            return val

        db_saved = False
        last_error = None
        for retry_attempt in range(1, 4):  # up to 3 retries
            try:
                _get_model_repo().save_model(_to_native({
                    "model_type": model_type,
                    "version": version,
                    "model_path": model_path,
                    "train_accuracy": results.get("train_accuracy"),
                    "test_accuracy": results.get("test_accuracy"),
                    "precision": results.get("test_precision"),
                    "recall": results.get("test_recall"),
                    "f1_score": results.get("test_f1"),
                    "roc_auc": results.get("test_roc_auc"),
                    "feature_count": len(feature_names),
                    "train_samples": int(len(X)),
                    "feature_importance": _json.dumps(feature_importance),
                    "training_params": _json.dumps(params),
                    "training_report": _json.dumps(results),
                    "status": "ready",
                    "train_date": train_date,
                }))
                logger.info(
                    "Model metadata saved to DB: %s v%s (attempt %d)",
                    model_type, version, retry_attempt
                )
                db_saved = True
                break
            except RuntimeError as e:
                # _get_db() raises RuntimeError when connection exhausted
                last_error = e
                logger.warning(
                    "DB save attempt %d/3 failed (connection): %s",
                    retry_attempt, e
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "DB save attempt %d/3 failed: %s",
                    retry_attempt, e
                )
            if retry_attempt < 3:
                wait = retry_attempt * 2  # 2s, 4s backoff
                logger.info("Retrying DB save in %ds...", wait)
                import time as _time
                _time.sleep(wait)

        if not db_saved:
            logger.error(
                "⚠️  CRITICAL: Model file saved to disk (%s) but DB metadata write FAILED after 3 retries. "
                "model_predict with 'latest' may not use this model. Error: %s",
                model_path, last_error
            )

        training_results = {
            "train_accuracy": results.get("train_accuracy", 0),
            "test_accuracy": results.get("test_accuracy", 0),
            "precision": results.get("test_precision", 0),
            "recall": results.get("test_recall", 0),
            "f1_score": results.get("test_f1", 0),
            "feature_importance": feature_importance,
            "version": version,
            "model_type": model_type,
            "train_samples": int(len(X)),
            "feature_count": len(feature_names),
        }

        return jsonify(
            {
                "success": True,
                "data": {
                    "training_results": _sanitize_for_json(training_results)
                },
            }
        )

    # ── POST /api/ml/predict ────────────────────────────────────────

    @app.route("/api/ml/predict", methods=["POST"])
    @_ml_error_handler
    def ml_predict():
        """Make batch predictions for given symbols."""
        import time
        start_time = time.time()

        data = request.get_json() or {}
        data = _convert_keys_to_snake(data)

        model_type = data.get("model_type", "xgboost")
        raw_symbols: list[str] = data.get("symbols", [])
        symbols = [_strip_suffix(s) for s in raw_symbols]
        version = data.get("version", "latest")

        if not symbols:
            return jsonify({"success": False, "error": "请指定股票代码"}), 400

        if model_type == "randomforest":
            model_type = "xgboost"

        # Resolve "latest" to actual version
        if version == "latest":
            resolved = _resolve_latest_version(model_type)
            if not resolved:
                return jsonify({"success": False, "error": f"没有可用的 {model_type} 模型，请先训练"}), 200
            version = resolved

        logger.info("ML predict: model=%s, symbols=%d, version=%s", model_type, len(symbols), version)

        # Fetch latest klines (need enough history for factor calculation, ~120 days)
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - pd.DateOffset(days=180)).strftime("%Y-%m-%d")

        logger.info("Fetching klines for %d symbols: %s to %s", len(symbols), start_date, end_date)
        klines_dict: dict[str, list[dict]] = {}
        for symbol in symbols:
            try:
                rows = ds.kline.get_daily_klines(symbol, start_date, end_date)
                # 🔧 兼容 polars DataFrame
                import polars as pl
                if isinstance(rows, pl.DataFrame):
                    if rows.is_empty():
                        logger.debug("Skip %s (empty DataFrame)", symbol)
                        continue
                    rows = rows.to_dicts()
                if rows:
                    klines_dict[symbol] = [_normalize_kline(r) for r in rows]
                    logger.debug("Fetched %d klines for %s", len(rows), symbol)
            except Exception as e:
                logger.warning("Skip %s (error: %s)", symbol, str(e))

        if not klines_dict:
            return jsonify({"success": False, "error": "没有可用的K线数据"}), 400

        logger.info("Klines fetched for %d/%d symbols (%.2fs)", len(klines_dict), len(symbols), time.time() - start_time)

        # Feature extraction with timeout protection
        from application.services.ml_pipeline.feature_engineering import FeatureEngineer
        from application.services.ml_pipeline.predictor import MLPredictor

        engineer = FeatureEngineer()

        logger.info("Starting feature extraction...")
        try:
            features_df = engineer.extract_features(klines_dict)
            logger.info("Feature extraction completed: shape=%s (%.2fs)", features_df.shape, time.time() - start_time)
        except Exception as e:
            logger.error("Feature extraction failed: %s", str(e), exc_info=True)
            return jsonify({"success": False, "error": f"特征提取失败: {str(e)}"}), 500

        if features_df.empty:
            return jsonify({"success": False, "error": "无法提取特征"}), 400

        # Prepare features (use same scaler fit as training — here we fit on current data)
        logger.info("Preparing features...")
        try:
            metadata, X = engineer.prepare_features(features_df, handle_missing="fill", fit_scaler=True)
            logger.info("Features prepared: X.shape=%s (%.2fs)", X.shape, time.time() - start_time)
        except Exception as e:
            logger.error("Feature preparation failed: %s", str(e), exc_info=True)
            return jsonify({"success": False, "error": f"特征准备失败: {str(e)}"}), 500

        # Load model & predict
        logger.info("Loading model: %s version=%s", model_type, version)
        predictor = MLPredictor(model_type=model_type)
        try:
            predictor.load_model(version=version)
            logger.info("Model loaded successfully")
        except FileNotFoundError as e:
            logger.error("Model not found: %s", str(e))
            return jsonify({"success": False, "error": f"模型未找到: {model_type}_{version}"}), 200
        except Exception as e:
            logger.error("Model load failed: %s", str(e), exc_info=True)
            return jsonify({"success": False, "error": f"模型加载失败: {str(e)}"}), 500

        # Align features with model
        missing = set(predictor.feature_names) - set(X.columns)
        if missing:
            logger.info("Padding missing features with 0: %s", missing)
            for col in missing:
                X[col] = 0.0
        X_ordered = X[predictor.feature_names]

        # Predict
        logger.info("Making predictions...")
        try:
            preds = predictor.predict(X_ordered, return_proba=True)
            logger.info("Predictions completed (%.2fs)", time.time() - start_time)
        except Exception as e:
            logger.error("Prediction failed: %s", str(e), exc_info=True)
            return jsonify({"success": False, "error": f"预测失败: {str(e)}"}), 500

        # Build response — one prediction per symbol (latest date)
        predictions: list[dict] = []
        for idx, row in metadata.iterrows():
            prob_up = float(preds.iloc[idx]["prob_up"]) if "prob_up" in preds.columns else 0.5
            pred_class = int(preds.iloc[idx]["prediction"])
            confidence = _confidence_label(prob_up)
            predictions.append(
                {
                    "symbol": row.get("symbol", ""),
                    "date": str(row.get("date", "")),
                    "predicted_class": pred_class,
                    "probability": round(prob_up, 4),
                    "confidence": confidence,
                }
            )

        # Deduplicate: keep only the latest date per symbol
        seen: set[str] = set()
        deduped: list[dict] = []
        for p in sorted(predictions, key=lambda x: x["date"], reverse=True):
            sym = p["symbol"]
            if sym not in seen:
                seen.add(sym)
                deduped.append(p)
        deduped.reverse()

        # Persist predictions to traceability table (best-effort)
        try:
            _save_ml_predictions(deduped, model_type, version)
        except Exception as e:
            logger.warning("Failed to save predictions to traceability: %s", str(e))

        logger.info("ML predict completed: %d predictions in %.2fs", len(deduped), time.time() - start_time)

        return jsonify(
            {
                "success": True,
                "data": {"predictions": _sanitize_for_json(deduped)},
            }
        )

    # ── GET /api/ml/model/info ──────────────────────────────────────

    @app.route("/api/ml/model/info", methods=["GET"])
    @_ml_error_handler
    def ml_model_info():
        """Get metadata for the latest model of a given type (DB primary, file fallback)."""
        model_type = request.args.get("model_type", "xgboost")
        version = request.args.get("version", "latest")
        if model_type == "randomforest":
            model_type = "xgboost"

        # 1) Try DB
        try:
            db_model = _get_model_repo().get_by_type_version(model_type, version)
            if db_model:
                fi_raw = db_model.get("feature_importance") or {}
                if isinstance(fi_raw, str):
                    fi_raw = _json.loads(fi_raw)
                return jsonify({
                    "success": True,
                    "data": {
                        "model_info": _sanitize_for_json({
                            "model_type": db_model.get("model_type", model_type),
                            "version": db_model.get("version", ""),
                            "training_date": db_model.get("train_date", ""),
                            "samples_trained": db_model.get("train_samples", 0),
                            "accuracy": db_model.get("test_accuracy", 0),
                            "features_count": db_model.get("feature_count", 0),
                            "model_path": db_model.get("model_path", ""),
                        })
                    },
                })
        except Exception as e:
            logger.debug("DB read skipped: %s", e)

        # 2) File fallback (legacy models trained before DB migration)
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        candidates = sorted(
            MODEL_DIR.glob(f"{model_type}_*.pkl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return jsonify({"success": True, "data": {"model_info": {}}})

        stem = candidates[0].stem
        file_version = stem[len(model_type) + 1:]
        report_path = MODEL_DIR / f"training_report_{file_version}.json"
        info: dict[str, Any] = {
            "model_type": model_type,
            "version": file_version,
            "model_path": str(candidates[0]),
        }
        if report_path.exists():
            try:
                report = _json.loads(report_path.read_text())
                info["training_date"] = report.get("train_date", "")
                info["samples_trained"] = report.get("train_size", 0)
                info["accuracy"] = report.get("test_accuracy", 0)
                info["features_count"] = report.get("feature_count", 0)
            except (_json.JSONDecodeError, OSError):
                pass

        return jsonify({
            "success": True,
            "data": {"model_info": _sanitize_for_json(info)},
        })

    # ── GET /api/ml/models ──────────────────────────────────────────

    @app.route("/api/ml/models", methods=["GET"])
    @_ml_error_handler
    def ml_models_list():
        """列出所有模型"""
        model_type = request.args.get("model_type")
        status = request.args.get("status", "ready")
        limit = int(request.args.get("limit", 20))

        models = _get_model_repo().list_models(model_type, status, limit)

        return jsonify({
            "success": True,
            "models": _sanitize_for_json(models),
            "total": len(models)
        })

    # ── GET /api/ml/model/evaluate ──────────────────────────────────

    @app.route("/api/ml/model/evaluate", methods=["GET"])
    @_ml_error_handler
    def ml_model_evaluate():
        """评估模型性能"""
        model_type = request.args.get("model_type", "xgboost")
        version = request.args.get("version", "latest")

        model = _get_model_repo().get_by_type_version(model_type, version)
        if not model:
            return jsonify({"success": False, "error": "模型不存在"}), 404

        # 解析 training_report
        report = model.get("training_report", {})
        if isinstance(report, str):
            report = _json.loads(report)

        return jsonify({
            "success": True,
            "evaluation": {
                "model_type": model["model_type"],
                "version": model["version"],
                "metrics": {
                    "train_accuracy": model.get("train_accuracy"),
                    "test_accuracy": model.get("test_accuracy"),
                    "precision": model.get("precision"),
                    "recall": model.get("recall"),
                    "f1_score": model.get("f1_score"),
                    "roc_auc": model.get("roc_auc")
                },
                "training_report": report
            }
        })

    # ── GET /api/ml/model/monitor ────────────────────────────────

    @app.route("/api/ml/model/monitor", methods=["GET"])
    @_ml_error_handler
    def ml_model_monitor():
        """监控模型漂移（简化版）"""
        model_type = request.args.get("model_type", "xgboost")
        version = request.args.get("version", "latest")
        days = int(request.args.get("days", 30))

        model = _get_model_repo().get_by_type_version(model_type, version)
        if not model:
            return jsonify({"success": False, "error": "模型不存在"}), 404

        # 简化实现：返回固定的监控结果
        return jsonify({
            "success": True,
            "monitor": {
                "model_type": model["model_type"],
                "version": model["version"],
                "drift_detected": False,
                "drift_score": 0.0,
                "threshold": 0.3,
                "recommendation": "模型监控功能简化版，建议使用 web-frontend 查看详细指标",
                "top_drift_features": [],
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
        })

    # ── GET /api/ml/features ────────────────────────────────────────

    @app.route("/api/ml/features", methods=["GET"])
    @_ml_error_handler
    def ml_features():
        """Get feature importance from the latest trained model (DB primary, file fallback)."""
        model_type = request.args.get("model_type")
        if model_type == "randomforest":
            model_type = "xgboost"

        # 1) Try DB
        try:
            importance = _get_model_repo().get_feature_importance(model_type)
            if importance:
                total = sum(importance.values()) or 1
                features = [
                    {"name": name, "importance": round(val / total * 100, 2)}
                    for name, val in importance.items()
                ]
                features.sort(key=lambda x: x["importance"], reverse=True)
                return jsonify({
                    "success": True,
                    "data": {"features": _sanitize_for_json(features)},
                })
        except Exception as e:
            logger.debug("DB read skipped: %s", e)

        # 2) File fallback
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        reports = sorted(
            MODEL_DIR.glob("training_report_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if model_type and reports:
            pkl_versions = {
                p.stem[len(model_type) + 1:]
                for p in MODEL_DIR.glob(f"{model_type}_*.pkl")
            }
            reports = [
                r for r in reports
                if r.stem.replace("training_report_", "") in pkl_versions
            ]

        if not reports:
            return jsonify({"success": True, "data": {"features": []}})

        try:
            report = _json.loads(reports[0].read_text())
        except (_json.JSONDecodeError, OSError):
            return jsonify({"success": True, "data": {"features": []}})

        importance = report.get("feature_importance", {})
        if not importance:
            return jsonify({"success": True, "data": {"features": []}})

        total = sum(importance.values()) or 1
        features = [
            {"name": name, "importance": round(val / total * 100, 2)}
            for name, val in importance.items()
        ]
        features.sort(key=lambda x: x["importance"], reverse=True)

        return jsonify({
            "success": True,
            "data": {"features": _sanitize_for_json(features)},
        })
