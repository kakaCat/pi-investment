"""ML 引擎 API - FastAPI 版（从 Flask ml_routes.py 迁移，响应契约保持一致）

复用 ml_routes.py 的模块级辅助函数（_convert_keys_to_snake/_ml_error_handler/
_normalize_kline/_get_model_repo 等）与 ML 服务（MLTrainer/FeatureEngineer/MLPredictor），
并使用同一 ds 单例。handler 逻辑与 Flask 一致。
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
import structlog

from adapters.inbound.fastapi_app.shared import ds
# 复用中立层 ml_helpers 的辅助函数（同一实现）
from adapters.shared.ml_helpers import (
    MODEL_DIR, _json, _get_model_repo, _convert_keys_to_snake, _sanitize_for_json,
    _ml_error_handler, _strip_suffix, _normalize_kline, _confidence_label,
    _save_ml_predictions, _resolve_latest_version,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["ML - 机器学习"])


@router.post('/api/ml/train')
@_ml_error_handler
def ml_train(payload: Optional[Dict[str, Any]] = Body(None)):
    """Train an ML model (xgboost / lightgbm / randomforest)."""
    data = _convert_keys_to_snake(payload or {})

    model_type = data.get("model_type", "xgboost")
    start_date = data.get("start_date", "2020-01-01")
    end_date = data.get("end_date", datetime.now().strftime("%Y-%m-%d"))
    test_size = float(data.get("test_size", 0.2))
    symbols: list = [_strip_suffix(s) for s in (data.get("symbols") or [])] if data.get("symbols") else None
    params = data.get("params", {})

    if model_type == "randomforest":
        model_type = "xgboost"
    if model_type not in ("xgboost", "lightgbm"):
        return JSONResponse(status_code=400, content={"success": False, "error": f"不支持的模型类型: {model_type}"})

    if not symbols:
        stocks = ds.stock.get_all(limit=50)
        symbols = [s["symbol"] for s in stocks]
    if not symbols:
        return JSONResponse(status_code=400, content={"success": False, "error": "没有可用的股票数据"})

    logger.info("ML train: model=%s, symbols=%d", model_type, len(symbols))

    klines_dict: dict = {}

    def _fetch_one_kline(sym: str):
        try:
            rows = ds.kline.get_daily_klines(sym, start_date, end_date)
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

    if not klines_dict:
        return JSONResponse(status_code=400, content={"success": False, "error": "指定日期范围内没有K线数据"})

    all_rows: list = []

    def _process_one_symbol(sym: str):
        try:
            factors_data = ds.factor.get_factors_range(sym, start_date, end_date)
            if not factors_data:
                return []
            by_date: dict = {}
            for fv in factors_data:
                d = str(fv.get("factor_date") or fv.get("date", ""))
                if not d:
                    continue
                by_date.setdefault(d, {})[fv["factor_name"]] = float(fv.get("factor_value", 0) or 0)
            close_map: dict = {}
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

    time_sleep = __import__("time")
    time_sleep.sleep(1.0)

    if len(all_rows) < 10:
        return JSONResponse(status_code=400, content={"success": False, "error": f"有效样本不足 (仅有{len(all_rows)}条)"})

    X = pd.DataFrame(all_rows)
    y = X.pop("__target")
    X = X.drop(columns=["__symbol", "__date"], errors="ignore")
    X = X.fillna(X.median(numeric_only=True)).fillna(0)
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X = pd.DataFrame(X_scaled, columns=X.columns)

    from application.services.ml_pipeline.trainer import MLTrainer
    trainer = MLTrainer(model_type=model_type)
    results = trainer.train(X, y, test_size=test_size, params=params)

    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = str(MODEL_DIR / f"{model_type}_{version}.pkl")
    try:
        trainer.save_model(version=version)
    except Exception as e:
        logger.warning("Model file save skipped: %s", e)

    train_date = datetime.now(timezone.utc).isoformat()
    feature_importance = results.get("feature_importance", {})
    feature_names = list(X.columns)
    _get_model_repo()._ensure_db(max_retries=5, retry_delay=2.0)

    def _to_native(val):
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
    for retry_attempt in range(1, 4):
        try:
            _get_model_repo().save_model(_to_native({
                "model_type": model_type, "version": version, "model_path": model_path,
                "train_accuracy": results.get("train_accuracy"), "test_accuracy": results.get("test_accuracy"),
                "precision": results.get("test_precision"), "recall": results.get("test_recall"),
                "f1_score": results.get("test_f1"), "roc_auc": results.get("test_roc_auc"),
                "feature_count": len(feature_names), "train_samples": int(len(X)),
                "feature_importance": _json.dumps(feature_importance),
                "training_params": _json.dumps(params), "training_report": _json.dumps(results),
                "status": "ready", "train_date": train_date,
            }))
            db_saved = True
            break
        except RuntimeError as e:
            last_error = e
        except Exception as e:
            last_error = e
        if retry_attempt < 3:
            wait = retry_attempt * 2
            time_sleep.sleep(wait)

    if not db_saved:
        logger.error("Model metadata DB write FAILED after 3 retries: %s", last_error)

    training_results = {
        "train_accuracy": results.get("train_accuracy", 0), "test_accuracy": results.get("test_accuracy", 0),
        "precision": results.get("test_precision", 0), "recall": results.get("test_recall", 0),
        "f1_score": results.get("test_f1", 0), "feature_importance": feature_importance,
        "version": version, "model_type": model_type,
        "train_samples": int(len(X)), "feature_count": len(feature_names),
    }
    return {"success": True, "data": {"training_results": _sanitize_for_json(training_results)}}


@router.post('/api/ml/predict')
@_ml_error_handler
def ml_predict(payload: Optional[Dict[str, Any]] = Body(None)):
    """Make batch predictions for given symbols."""
    start_time = time.time()
    data = _convert_keys_to_snake(payload or {})

    model_type = data.get("model_type", "xgboost")
    raw_symbols: list = data.get("symbols", [])
    symbols = [_strip_suffix(s) for s in raw_symbols]
    version = data.get("version", "latest")

    if not symbols:
        return JSONResponse(status_code=400, content={"success": False, "error": "请指定股票代码"})
    if model_type == "randomforest":
        model_type = "xgboost"

    if version == "latest":
        resolved = _resolve_latest_version(model_type)
        if not resolved:
            return JSONResponse(status_code=200, content={"success": False, "error": f"没有可用的 {model_type} 模型，请先训练"})
        version = resolved

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - pd.DateOffset(days=180)).strftime("%Y-%m-%d")

    klines_dict: dict = {}
    for symbol in symbols:
        try:
            rows = ds.kline.get_daily_klines(symbol, start_date, end_date)
            import polars as pl
            if isinstance(rows, pl.DataFrame):
                if rows.is_empty():
                    continue
                rows = rows.to_dicts()
            if rows:
                klines_dict[symbol] = [_normalize_kline(r) for r in rows]
        except Exception as e:
            logger.warning("Skip %s (error: %s)", symbol, str(e))

    if not klines_dict:
        return JSONResponse(status_code=400, content={"success": False, "error": "没有可用的K线数据"})

    from application.services.ml_pipeline.feature_engineering import FeatureEngineer
    from application.services.ml_pipeline.predictor import MLPredictor
    engineer = FeatureEngineer()
    try:
        features_df = engineer.extract_features(klines_dict)
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"特征提取失败: {str(e)}"})
    if features_df.empty:
        return JSONResponse(status_code=400, content={"success": False, "error": "无法提取特征"})

    try:
        metadata, X = engineer.prepare_features(features_df, handle_missing="fill", fit_scaler=True)
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"特征准备失败: {str(e)}"})

    predictor = MLPredictor(model_type=model_type)
    try:
        predictor.load_model(version=version)
    except FileNotFoundError as e:
        return JSONResponse(status_code=200, content={"success": False, "error": f"模型未找到: {model_type}_{version}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"模型加载失败: {str(e)}"})

    missing = set(predictor.feature_names) - set(X.columns)
    if missing:
        for col in missing:
            X[col] = 0.0
    X_ordered = X[predictor.feature_names]

    try:
        preds = predictor.predict(X_ordered, return_proba=True)
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"预测失败: {str(e)}"})

    predictions: list = []
    for idx, row in metadata.iterrows():
        prob_up = float(preds.iloc[idx]["prob_up"]) if "prob_up" in preds.columns else 0.5
        pred_class = int(preds.iloc[idx]["prediction"])
        confidence = _confidence_label(prob_up)
        predictions.append({
            "symbol": row.get("symbol", ""), "date": str(row.get("date", "")),
            "predicted_class": pred_class, "probability": round(prob_up, 4), "confidence": confidence,
        })

    seen: set = set()
    deduped: list = []
    for p in sorted(predictions, key=lambda x: x["date"], reverse=True):
        sym = p["symbol"]
        if sym not in seen:
            seen.add(sym)
            deduped.append(p)
    deduped.reverse()

    try:
        _save_ml_predictions(deduped, model_type, version)
    except Exception as e:
        logger.warning("Failed to save predictions to traceability: %s", str(e))

    return {"success": True, "data": {"predictions": _sanitize_for_json(deduped)}}


@router.get('/api/ml/model/info')
@_ml_error_handler
def ml_model_info(model_type: str = Query("xgboost"), version: str = Query("latest")):
    """Get metadata for the latest model of a given type (DB primary, file fallback)."""
    if model_type == "randomforest":
        model_type = "xgboost"
    try:
        db_model = _get_model_repo().get_by_type_version(model_type, version)
        if db_model:
            fi_raw = db_model.get("feature_importance") or {}
            if isinstance(fi_raw, str):
                fi_raw = _json.loads(fi_raw)
            return {"success": True, "data": {"model_info": _sanitize_for_json({
                "model_type": db_model.get("model_type", model_type), "version": db_model.get("version", ""),
                "training_date": db_model.get("train_date", ""), "samples_trained": db_model.get("train_samples", 0),
                "accuracy": db_model.get("test_accuracy", 0), "features_count": db_model.get("feature_count", 0),
                "model_path": db_model.get("model_path", ""),
            })}}
    except Exception as e:
        logger.debug("DB read skipped: %s", e)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    candidates = sorted(MODEL_DIR.glob(f"{model_type}_*.pkl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return {"success": True, "data": {"model_info": {}}}
    stem = candidates[0].stem
    file_version = stem[len(model_type) + 1:]
    report_path = MODEL_DIR / f"training_report_{file_version}.json"
    info: dict = {"model_type": model_type, "version": file_version, "model_path": str(candidates[0])}
    if report_path.exists():
        try:
            report = _json.loads(report_path.read_text())
            info["training_date"] = report.get("train_date", "")
            info["samples_trained"] = report.get("train_size", 0)
            info["accuracy"] = report.get("test_accuracy", 0)
            info["features_count"] = report.get("feature_count", 0)
        except (_json.JSONDecodeError, OSError):
            pass
    return {"success": True, "data": {"model_info": _sanitize_for_json(info)}}


@router.get('/api/ml/features')
@_ml_error_handler
def ml_features(model_type: Optional[str] = Query(None)):
    """Get feature importance from the latest trained model (DB primary, file fallback)."""
    if model_type == "randomforest":
        model_type = "xgboost"
    try:
        importance = _get_model_repo().get_feature_importance(model_type)
        if importance:
            total = sum(importance.values()) or 1
            features = [{"name": name, "importance": round(val / total * 100, 2)} for name, val in importance.items()]
            features.sort(key=lambda x: x["importance"], reverse=True)
            return {"success": True, "data": {"features": _sanitize_for_json(features)}}
    except Exception as e:
        logger.debug("DB read skipped: %s", e)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    reports = sorted(MODEL_DIR.glob("training_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if model_type and reports:
        pkl_versions = {p.stem[len(model_type) + 1:] for p in MODEL_DIR.glob(f"{model_type}_*.pkl")}
        reports = [r for r in reports if r.stem.replace("training_report_", "") in pkl_versions]
    if not reports:
        return {"success": True, "data": {"features": []}}
    try:
        report = _json.loads(reports[0].read_text())
    except (_json.JSONDecodeError, OSError):
        return {"success": True, "data": {"features": []}}
    importance = report.get("feature_importance", {})
    if not importance:
        return {"success": True, "data": {"features": []}}
    total = sum(importance.values()) or 1
    features = [{"name": name, "importance": round(val / total * 100, 2)} for name, val in importance.items()]
    features.sort(key=lambda x: x["importance"], reverse=True)
    return {"success": True, "data": {"features": _sanitize_for_json(features)}}
