# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file


# TODO: Extract magic numbers to named constants: [1e-09, 0.2, 0.5, 0.55, 3]...


# Extracted Constants


# Extracted Constants

CONST_1eNEG_09 = 1e-09

CONST_0_2 = 0.2

CONST_0_5 = 0.5

CONST_0_55 = 0.55

CONST_3 = 3

CONST_4 = 4

CONST_5 = 5

CONST_20 = 20

CONST_30 = 30

CONST_50 = 50



CONST_1eNEG_09 = 1e-09

CONST_0_2 = 0.2

CONST_0_5 = 0.5

CONST_0_55 = 0.55

CONST_3 = 3

CONST_4 = 4

CONST_5 = 5

CONST_20 = 20

CONST_30 = 30

CONST_50 = 50



"""ML 引擎 API - FastAPI 版（从 Flask ml_routes.py 迁移，响应契约保持一致）

复用 ml_routes.py 的模块级辅助函数（_convert_keys_to_snake/_ml_error_handler/
_normalize_kline/_get_model_repo 等）与 ML 服务（MLTrainer/FeatureEngineer/MLPredictor），
并使用同一 ds 单例。handler 逻辑与 Flask 一致。
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
import structlog

from adapters.inbound.fastapi_app.shared import stock_repo, kline_repo, factor_repo
# 复用中立层 ml_helpers 的辅助函数（同一实现）
from adapters.shared.ml_helpers import (
    MODEL_DIR, _json, _get_model_repo, _convert_keys_to_snake, _sanitize_for_json,
    _ml_error_handler, _strip_suffix, _normalize_kline, _confidence_label,
    _save_ml_predictions, _resolve_latest_version,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["ML - 机器学习"])


def _validate_train_params(data):
    """验证训练参数"""
    model_type = data.get("model_type", "xgboost")
    if model_type == "randomforest":
        model_type = "xgboost"
    if model_type not in ("xgboost", "lightgbm"):
        return None, JSONResponse(status_code=400, content={
            "success": False,
            "error": f"不支持的模型类型: {model_type}"
        })
    return model_type, None

def _get_train_symbols(data):
    """获取训练股票列表"""
    symbols = data.get("symbols")
    if symbols:
        return [_strip_suffix(s) for s in symbols]

    stocks = stock_repo.get_all(limit=50)
    symbols = [s["symbol"] for s in stocks]
    if not symbols:
        return None
    return symbols

def _fetch_klines_parallel(symbols: List[str], start_date: str, end_date: str):
    """并行获取K线数据"""
    klines_dict: dict = {}

    def _fetch_one_kline(sym: str):
        try:
            rows = kline_repo.get_daily_klines(sym, start_date, end_date)
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
    return klines_dict

def _process_factors_for_symbol(sym: str, klines_dict: dict, start_date: str, end_date: str):
    """处理单个股票的因子数据"""
    try:
        factors_data = factor_repo.get_factors_range(sym, start_date, end_date)
        if factors_data is None or factors_data.is_empty():
            return []

        by_date: dict = {}
        for fv in factors_data.iter_rows(named=True):
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

def _prepare_training_data(all_rows: list):
    """准备训练数据"""
    X = pd.DataFrame(all_rows)
    y = X.pop("__target")
    X = X.drop(columns=["__symbol", "__date"], errors="ignore")
    X = X.fillna(X.median(numeric_only=True)).fillna(0)

    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X = pd.DataFrame(X_scaled, columns=X.columns)
    return X, y

def _save_model_to_db(model_type: str, version: str, model_path: str, results: dict, X: pd.DataFrame, params: dict):
    """保存模型元数据到数据库"""
    train_date = datetime.now(timezone.utc).isoformat()
    feature_importance = results.get("feature_importance", {})
    feature_names = list(X.columns)
    _get_model_repo()._ensure_db(max_retries=5, retry_delay=2.0)

    def _to_native(val):
        import numpy as _np
        if isinstance(val, dict):
            return {k: _to_native(v) for k, v in val.items()}
        if isinstance(val, (list, tuple)):
            return [_to_native(v) for v in val]
        if isinstance(val, _np.floating):
            return float(val)
        if isinstance(val, _np.integer):
            return int(val)
        if isinstance(val, _np.bool_):
            return bool(val)
        return val

    db_saved = False
    last_error = None
    time_sleep = __import__("time")

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
        except (RuntimeError, Exception) as e:
            last_error = e
        if retry_attempt < 3:
            time_sleep.sleep(retry_attempt * 2)

    if not db_saved:
        logger.error("Model metadata DB write FAILED after 3 retries: %s", last_error)

@router.post('/api/ml/train')
@_ml_error_handler
def ml_train(payload: Optional[Dict[str, Any]] = Body(None)):
    """Train an ML model (xgboost / lightgbm / randomforest)."""
    data = _convert_keys_to_snake(payload or {})

    # 验证参数
    model_type, error_resp = _validate_train_params(data)
    if error_resp:
        return error_resp

    start_date = data.get("start_date", "2020-01-01")
    end_date = data.get("end_date", datetime.now().strftime("%Y-%m-%d"))
    test_size = float(data.get("test_size", 0.2))
    params = data.get("params", {})

    # 获取股票列表
    symbols = _get_train_symbols(data)
    if not symbols:
        return JSONResponse(status_code=400, content={"success": False, "error": "没有可用的股票数据"})

    logger.info("ML train: model=%s, symbols=%d", model_type, len(symbols))

    # 并行获取K线数据
    klines_dict = _fetch_klines_parallel(symbols, start_date, end_date)
    if not klines_dict:
        return JSONResponse(status_code=400, content={"success": False, "error": "指定日期范围内没有K线数据"})

    # 并行处理因子数据
    all_rows: list = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_process_factors_for_symbol, s, klines_dict, start_date, end_date): s for s in symbols}
        for future in as_completed(futures):
            all_rows.extend(future.result())

    __import__("time").sleep(1.0)

    if len(all_rows) < 10:
        return JSONResponse(status_code=400, content={"success": False, "error": f"有效样本不足 (仅有{len(all_rows)}条)"})

    # 准备训练数据
    X, y = _prepare_training_data(all_rows)

    # 训练模型
    from application.services.ml_pipeline.trainer import MLTrainer
    trainer = MLTrainer(model_type=model_type)
    results = trainer.train(X, y, test_size=test_size, params=params)

    # 保存模型文件
    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = str(MODEL_DIR / f"{model_type}_{version}.pkl")
    try:
        trainer.save_model(version=version)
    except Exception as e:
        logger.warning("Model file save skipped: %s", e)

    # 保存模型元数据到数据库
    _save_model_to_db(model_type, version, model_path, results, X, params)

    # 构建返回结果
    feature_importance = results.get("feature_importance", {})
    training_results = {
        "train_accuracy": results.get("train_accuracy", 0), "test_accuracy": results.get("test_accuracy", 0),
        "precision": results.get("test_precision", 0), "recall": results.get("test_recall", 0),
        "f1_score": results.get("test_f1", 0), "feature_importance": feature_importance,
        "version": version, "model_type": model_type,
        "train_samples": int(len(X)), "feature_count": len(X.columns),
    }
    return {"success": True, "data": {"training_results": _sanitize_for_json(training_results)}}


def _check_model_deprecated(model_type: str):
    """检查模型是否已废弃"""
    if model_type in ("xgboost", "randomforest"):
        return JSONResponse(status_code=200, content={
            "success": False,
            "error": f"{model_type} 模型已下线（2026-05 旧模型，特征与 DB 因子不匹配，输出恒定不可信）。请改用 model_type='lightgbm'（每日重训、特征同源）",
            "model_gate": {"passed": False, "level": "rejected", "reason": "deprecated_model"},
        })
    return None

def _resolve_model_version(model_type: str, version: str):
    """解析模型版本"""
    if version == "latest":
        resolved = _resolve_latest_version(model_type)
        if not resolved:
            return None, JSONResponse(status_code=200, content={
                "success": False,
                "error": f"没有可用的 {model_type} 模型，请先训练"
            })
        return resolved, None
    return version, None

def _load_predictor(model_type: str, version: str):
    """加载预测器"""
    from application.services.ml_pipeline.predictor import MLPredictor
    predictor = MLPredictor(model_type=model_type)
    try:
        predictor.load_model(version=version)
        return predictor, None
    except FileNotFoundError:
        return None, JSONResponse(status_code=200, content={
            "success": False,
            "error": f"模型未找到: {model_type}_{version}"
        })
    except Exception as e:
        return None, JSONResponse(status_code=500, content={
            "success": False,
            "error": f"模型加载失败: {str(e)}"
        })

def _check_model_gate(predictor):
    """检查模型质量门禁"""
    test_accuracy = (predictor.model_info or {}).get("test_accuracy")
    model_gate: Dict[str, Any] = {"passed": True, "level": "normal"}

    if test_accuracy is None:
        return model_gate, None

    try:
        acc = float(test_accuracy)
        if acc < 0.50:
            return None, JSONResponse(status_code=200, content={
                "success": False,
                "error": f"模型上线门禁拦截：test_accuracy={acc:.3f} 低于随机水平(0.50)，预测不可信，拒绝服务",
                "model_gate": {"passed": False, "level": "rejected", "test_accuracy": acc},
            })
        elif acc < 0.55:
            model_gate = {
                "passed": True, "level": "degraded", "test_accuracy": acc,
                "warning": f"test_accuracy={acc:.3f} 接近随机(0.50~0.55)，预测价值有限，谨慎使用"
            }
    except (TypeError, ValueError):
        pass

    return model_gate, None

def _prepare_features_from_db(symbols: List[str], model_features: List[str], scaler):
    """从数据库因子准备特征"""
    rows = []
    for symbol in symbols:
        try:
            fobjs = factor_repo.get_latest_factors(symbol)
            fdict: dict = {}
            fdate = ""
            for fo in fobjs or []:
                if isinstance(fo, dict):
                    name, val, d = fo.get("factor_name"), fo.get("factor_value"), fo.get("factor_date")
                else:
                    name = getattr(fo, "factor_name", None)
                    val = getattr(fo, "factor_value", None)
                    d = getattr(fo, "factor_date", None)
                if not name:
                    continue
                try:
                    fdict[name] = float(val or 0)
                except (TypeError, ValueError):
                    fdict[name] = 0.0
                d = str(d or "")
                if d > fdate:
                    fdate = d
            rows.append({"symbol": symbol, "date": fdate,
                         **{n: fdict.get(n, 0.0) for n in model_features}})
        except Exception as e:
            logger.warning("Skip %s factors: %s", symbol, str(e))

    if not rows:
        return None, None, JSONResponse(status_code=400, content={
            "success": False,
            "error": "没有可用的因子数据"
        })

    metadata = pd.DataFrame([{"symbol": r["symbol"], "date": r["date"]} for r in rows])
    X_raw = pd.DataFrame(rows)[model_features]
    X_ordered = pd.DataFrame(scaler.transform(X_raw), columns=model_features)
    return metadata, X_ordered, None

def _prepare_features_legacy(symbols: List[str], predictor):
    """使用旧方法从K线准备特征"""
    from application.services.ml_pipeline.feature_engineering import FeatureEngineer

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - pd.DateOffset(days=180)).strftime("%Y-%m-%d")

    klines_dict: dict = {}
    for symbol in symbols:
        try:
            rows = kline_repo.get_daily_klines(symbol, start_date, end_date)
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
        return None, None, JSONResponse(status_code=400, content={
            "success": False,
            "error": "没有可用的K线数据"
        })

    engineer = FeatureEngineer()
    try:
        features_df = engineer.extract_features(klines_dict)
    except Exception as e:
        return None, None, JSONResponse(status_code=500, content={
            "success": False,
            "error": f"特征提取失败: {str(e)}"
        })

    if features_df.empty:
        return None, None, JSONResponse(status_code=400, content={
            "success": False,
            "error": "无法提取特征"
        })

    try:
        metadata, X = engineer.prepare_features(features_df, handle_missing="fill", fit_scaler=True)
    except Exception as e:
        return None, None, JSONResponse(status_code=500, content={
            "success": False,
            "error": f"特征准备失败: {str(e)}"
        })

    missing = set(predictor.feature_names) - set(X.columns)
    if missing:
        for col in missing:
            X[col] = 0.0
    X_ordered = X[predictor.feature_names]
    return metadata, X_ordered, None

def _build_predictions(metadata, preds):
    """构建预测结果"""
    predictions: list = []
    for idx, row in metadata.iterrows():
        prob_up = float(preds.iloc[idx]["prob_up"]) if "prob_up" in preds.columns else 0.5
        pred_class = int(preds.iloc[idx]["prediction"])
        confidence = _confidence_label(prob_up)
        predictions.append({
            "symbol": row.get("symbol", ""), "date": str(row.get("date", "")),
            "predicted_class": pred_class, "probability": round(prob_up, 4), "confidence": confidence,
        })

    # 去重，保留最新日期
    seen: set = set()
    deduped: list = []
    for p in sorted(predictions, key=lambda x: x["date"], reverse=True):
        sym = p["symbol"]
        if sym not in seen:
            seen.add(sym)
            deduped.append(p)
    deduped.reverse()
    return deduped

@router.post('/api/ml/predict')
@_ml_error_handler
def ml_predict(payload: Optional[Dict[str, Any]] = Body(None)):
    """Make batch predictions for given symbols."""
    data = _convert_keys_to_snake(payload or {})

    model_type = data.get("model_type", "lightgbm")
    raw_symbols: list = data.get("symbols", [])
    symbols = [_strip_suffix(s) for s in raw_symbols]
    version = data.get("version", "latest")

    if not symbols:
        return JSONResponse(status_code=400, content={"success": False, "error": "请指定股票代码"})

    # 检查废弃模型
    deprecated_resp = _check_model_deprecated(model_type)
    if deprecated_resp:
        return deprecated_resp

    # 解析版本号
    version, error_resp = _resolve_model_version(model_type, version)
    if error_resp:
        return error_resp

    # 加载预测器
    predictor, error_resp = _load_predictor(model_type, version)
    if error_resp:
        return error_resp

    # 检查模型质量门禁
    model_gate, error_resp = _check_model_gate(predictor)
    if error_resp:
        return error_resp

    # 准备特征
    model_features = list(predictor.feature_names or [])
    scaler_path = predictor.model_dir / f"{model_type}_{version}_scaler.pkl"

    if model_features and scaler_path.exists():
        import pickle as _pickle
        with open(scaler_path, "rb") as f:
            scaler = _pickle.load(f)
        metadata, X_ordered, error_resp = _prepare_features_from_db(symbols, model_features, scaler)
    else:
        metadata, X_ordered, error_resp = _prepare_features_legacy(symbols, predictor)

    if error_resp:
        return error_resp

    # 执行预测
    try:
        preds = predictor.predict(X_ordered, return_proba=True)
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": f"预测失败: {str(e)}"})

    # 构建预测结果
    deduped = _build_predictions(metadata, preds)

    # 保存预测结果
    try:
        _save_ml_predictions(deduped, model_type, version)
    except Exception as e:
        logger.warning("Failed to save predictions to traceability: %s", str(e))

    return {"success": True, "data": {"predictions": _sanitize_for_json(deduped), "model_gate": model_gate}}


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


@router.get('/api/ml/models')
@_ml_error_handler
def ml_models_list(
    model_type: Optional[str] = Query(None),
    status: Optional[str] = Query("ready"),
    limit: int = Query(20),
):
    """列出所有模型（Flask ml_routes.py GET /api/ml/models parity）"""
    models = _get_model_repo().list_models(model_type, status, limit)
    return {
        "success": True,
        "models": _sanitize_for_json(models),
        "total": len(models),
    }


@router.get('/api/ml/model/evaluate')
@_ml_error_handler
def ml_model_evaluate(model_type: str = Query("xgboost"), version: str = Query("latest")):
    """评估模型（agent model_evaluate）— 返回 ModelEvaluation（metrics + training_report）"""
    if model_type == "randomforest":
        model_type = "xgboost"
    db_model = _get_model_repo().get_by_type_version(model_type, version)
    if not db_model:
        return {"success": False, "error": f"模型不存在: {model_type} {version}"}

    fi_raw = db_model.get("feature_importance") or {}
    if isinstance(fi_raw, str):
        fi_raw = _json.loads(fi_raw)

    metrics = {
        "train_accuracy": float(db_model.get("train_accuracy") or 0),
        "test_accuracy": float(db_model.get("test_accuracy") or 0),
        "precision": float(db_model.get("precision") or 0),
        "recall": float(db_model.get("recall") or 0),
        "f1_score": float(db_model.get("f1_score") or 0),
        "roc_auc": float(db_model.get("roc_auc") or 0),
    }
    training_report: dict = {"feature_importance": fi_raw}
    for key, out_key in (("confusion_matrix", "confusion_matrix"), ("cv_scores", "cv_scores")):
        val = db_model.get(key)
        if val is not None:
            training_report[out_key] = _json.loads(val) if isinstance(val, str) else val

    return {"success": True, "evaluation": _sanitize_for_json({
        "model_type": db_model.get("model_type", model_type),
        "version": db_model.get("version", ""),
        "metrics": metrics,
        "training_report": training_report,
    })}


@router.get('/api/ml/model/monitor')
@_ml_error_handler
def ml_model_monitor(model_type: str = Query("xgboost"), version: str = Query("latest"), days: int = Query(30)):
    """监控模型漂移（agent model_monitor）— 比较近期 vs 基线数据分布，返回 ModelMonitor"""
    if model_type == "randomforest":
        model_type = "xgboost"
    db_model = _get_model_repo().get_by_type_version(model_type, version)
    if not db_model:
        return {"success": False, "error": f"模型不存在: {model_type} {version}"}

    fi_raw = db_model.get("feature_importance") or {}
    if isinstance(fi_raw, str):
        fi_raw = _json.loads(fi_raw)
    top_features = sorted(fi_raw.items(), key=lambda kv: -abs(kv[1]))[:5] if fi_raw else []

    drift_score, top_drift = _compute_drift(top_features, days)

    threshold = 0.5
    drift_detected = drift_score > threshold
    if drift_score > 1.0:
        recommendation = "建议尽快重新训练模型（数据分布已显著漂移）"
    elif drift_detected:
        recommendation = "建议密切监控并准备重新训练（检测到中等漂移）"
    else:
        recommendation = "模型状态正常，无需操作"

    return {"success": True, "monitor": _sanitize_for_json({
        "model_type": db_model.get("model_type", model_type),
        "version": db_model.get("version", ""),
        "drift_detected": drift_detected,
        "drift_score": round(drift_score, 3),
        "threshold": threshold,
        "recommendation": recommendation,
        "top_drift_features": top_drift,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })}


def _compute_drift(top_features, days: int):
    """计算数据分布漂移（近期 days 天 vs 其前 days 天基线），返回 (drift_score, top_drift_features)。

    用样本股票近期 K 线计算关键特征（日收益、波动率、RSI）的分布偏移，
    按 |近期均值-基线均值|/(基线标准差+eps) 衡量漂移。
    """
    import math
    sample_symbols = ['600519', '000001']
    feature_recent: dict = {}
    feature_baseline: dict = {}

    closes_all: list = []
    for sym in sample_symbols:
        try:
            kdf = kline_repo.get_daily_klines(
                sym,
                (datetime.now() - timedelta(days=days * 2 + 30)).strftime('%Y-%m-%d'),
                datetime.now().strftime('%Y-%m-%d'))
            if kdf is None or kdf.is_empty():
                continue
            closes = [float(k.get('close', 0)) for k in kdf.to_dicts()]
            closes_all.append(closes)
        except Exception:
            continue

    def _features(closes, start, end):
        seg = closes[start:end]
        if len(seg) < 3:
            return None
        rets = [(seg[i] - seg[i-1]) / seg[i-1] for i in range(1, len(seg)) if seg[i-1] != 0]
        if not rets:
            return None
        mean_ret = sum(rets) / len(rets)
        var = sum((r - mean_ret) ** 2 for r in rets) / len(rets)
        vol = math.sqrt(var)
        gains = [r for r in rets if r > 0]
        losses = [-r for r in rets if r < 0]
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 1e-9
        rsi = 100 - 100 / (1 + (avg_gain / avg_loss if avg_loss else 0)) if rets else 50
        return {'daily_return': mean_ret, 'volatility': vol, 'rsi': rsi}

    for closes in closes_all:
        if len(closes) < days * 2:
            continue
        base = _features(closes, 0, days)
        recent = _features(closes, days, days * 2)
        if base and recent:
            for k in base:
                feature_baseline.setdefault(k, []).append(base[k])
                feature_recent.setdefault(k, []).append(recent[k])

    drifts = []
    for k in feature_baseline:
        b = feature_baseline[k]
        r = feature_recent[k]
        mean_b = sum(b) / len(b)
        mean_r = sum(r) / len(r)
        std_b = math.sqrt(sum((x - mean_b) ** 2 for x in b) / len(b)) if len(b) > 1 else 0
        drift = abs(mean_r - mean_b) / (std_b + 1e-9)
        drifts.append({'feature': k, 'drift': round(drift, 3)})

    drifts.sort(key=lambda x: -x['drift'])
    drift_score = drifts[0]['drift'] if drifts else 0.0
    return drift_score, drifts[:5]



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
