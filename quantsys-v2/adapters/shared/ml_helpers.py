"""ML 路由助手（框架无关）"""
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
from concurrent.futures import ThreadPoolExecutor, as_completed

from adapters.outbound.repositories import MlModelORMRepository
from adapters.outbound.repositories import TraceabilityORMRepository

logger = logging.getLogger(__name__)

MODEL_DIR = Path(".pi-invest/ml/models")

# 延迟初始化，避免模块加载时实例化抽象类
_model_repo = None
_trace_repo = None


def _get_model_repo():
    """获取 ML 模型 Repository（延迟初始化）"""
    global _model_repo
    if _model_repo is None:
        try:
            _model_repo = MlModelORMRepository()
        except TypeError as e:
            logger.warning(f"MlModelORMRepository 初始化失败: {e}")
            _model_repo = None
    return _model_repo


def _get_trace_repo():
    """获取追踪 Repository（延迟初始化）"""
    global _trace_repo
    if _trace_repo is None:
        try:
            _trace_repo = TraceabilityORMRepository()
        except TypeError as e:
            logger.warning(f"TraceabilityORMRepository 初始化失败: {e}")
            _trace_repo = None
    return _trace_repo


# ── local helpers (mirror server.py utilities to avoid circular imports) ──


def _to_snake_case(camel_str: str) -> str:
    if not isinstance(camel_str, str):
        return camel_str
    return re.sub(r"(?<!^)(?=[A-Z])", "_", camel_str).lower()


def _convert_keys_to_snake(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {_to_snake_case(k): _convert_keys_to_snake(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_keys_to_snake(item) for item in obj]
    return obj


def _sanitize_for_json(obj: Any) -> Any:
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _ml_error_handler(f):
    from fastapi.responses import JSONResponse

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        except KeyError as e:
            return JSONResponse({"success": False, "error": f"缺少参数: {e}"}, status_code=400)
        except FileNotFoundError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=200)
        except ImportError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)
        except Exception as e:
            logger.error(f"ML API错误: {e}", exc_info=True)
            return JSONResponse({"success": False, "error": "服务器内部错误"}, status_code=500)

    return wrapper


def _strip_suffix(symbol: str) -> str:
    """Remove .SH/.SZ/.HK suffix for DB queries."""
    s = symbol.strip().upper()
    for suf in (".SH", ".SZ", ".HK"):
        if s.endswith(suf):
            return s[: -len(suf)]
    return s


def _normalize_kline(row: dict) -> dict:
    """Ensure kline row has 'date' and standard field names."""
    out = dict(row)
    if "date" not in out:
        out["date"] = str(out.get("trade_date", ""))
    if "trade_date" in out:
        out["trade_date"] = str(out["trade_date"])
    return out


def _create_target(klines_dict: dict[str, list[dict]]) -> dict[str, int]:
    """
    Create binary target: 1 if next-day close > current close, else 0.
    Returns dict keyed by 'symbol_date'.
    """
    targets: dict[str, int] = {}
    for symbol, klines in klines_dict.items():
        if len(klines) < 2:
            continue
        closes = [float(k.get("close", 0)) for k in klines]
        for i in range(len(klines) - 1):
            k = klines[i]
            date = str(k.get("date", k.get("trade_date", "")))
            if closes[i] > 0:
                forward_return = (closes[i + 1] - closes[i]) / closes[i]
            else:
                forward_return = 0
            key = f"{symbol}_{date}"
            targets[key] = 1 if forward_return > 0 else 0
    return targets


def _confidence_label(prob: float) -> str:
    if prob >= 0.75:
        return "high"
    if prob >= 0.6:
        return "medium"
    return "low"


def _save_ml_predictions(
    predictions: list[dict], model_type: str, version: str
) -> None:
    """Persist ML predictions to quant.ml_predictions (best-effort)."""
    try:
        import uuid as _uuid

        exec_id = str(_uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        for p in predictions:
            _get_trace_repo().save_ml_prediction({
                "execution_id": exec_id,
                "symbol": p.get("symbol", ""),
                "prediction_time": now,
                "model_type": model_type,
                "model_version": version,
                "feature_count": 0,
                "prediction": p.get("predicted_class", 0),
                "confidence": p.get("confidence", "low"),
                "prob_down": round(1 - p.get("probability", 0.5), 4),
                "prob_up": p.get("probability", 0.5),
            })
        logger.info("Saved %d ml_predictions trace records", len(predictions))
    except Exception as e:
        logger.debug("ml_predictions trace skipped: %s", e)


def _resolve_latest_version(model_type: str) -> str | None:
    """Resolve 'latest' to the actual version string from DB or filesystem.

    Cross-validates DB metadata against filesystem mtime to prevent
    stale-DB bug where a model file exists but metadata was never written.
    Returns the version with the newest timestamp across both sources.
    """
    db_version: str | None = None
    db_train_date: str | None = None
    file_version: str | None = None
    file_mtime: float = 0.0

    # 1) Query DB for latest
    try:
        db_model = _get_model_repo().get_by_type_version(model_type, "latest")
        if db_model and db_model.get("version"):
            candidate_version = db_model["version"]
            # DB 元数据可能指向已丢失的模型文件（如训练后被清理），
            # 文件不存在时不应采信 DB 记录，否则预测会以"模型未找到"失败
            if (MODEL_DIR / f"{model_type}_{candidate_version}.pkl").exists():
                db_version = candidate_version
                db_train_date = db_model.get("train_date", "")
            else:
                logger.warning(
                    "DB latest model %s_%s has no file on disk, ignoring DB record",
                    model_type, candidate_version,
                )
    except Exception:
        pass

    # 2) Scan filesystem for latest by mtime (only standard timestamp format)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    candidates = sorted(
        MODEL_DIR.glob(f"{model_type}_*.pkl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        # Only accept standard timestamp format (YYYYMMDD_HHMMSS), skip custom versions
        stem = candidate.stem  # e.g. "xgboost_20260524_122532"
        version_part = stem[len(model_type) + 1:]
        # Must match: 8 digits + underscore + 6 digits
        if re.match(r'^\d{8}_\d{6}$', version_part):
            file_version = version_part
            file_mtime = candidate.stat().st_mtime
            break

    # 3) Cross-validate: prefer the source with newer timestamp
    #    File mtime → convert to comparable float (epoch seconds)
    #    DB train_date → parse ISO datetime → epoch seconds
    file_ts = file_mtime  # already epoch seconds
    db_ts = 0.0
    if db_train_date:
        try:
            # Handle both ISO formats: with and without timezone
            dt_str = db_train_date.replace("Z", "+00:00")
            if "+" in dt_str or dt_str.endswith("Z"):
                from datetime import timezone as _tz
                dt = datetime.fromisoformat(dt_str)
            else:
                dt = datetime.fromisoformat(dt_str)
            db_ts = dt.timestamp()
        except (ValueError, TypeError):
            pass

    # Prioritize DB models (they are validated and tested)
    # Only use filesystem if DB is completely empty
    if db_version:
        logger.info("Using DB model: %s (trained: %s)", db_version, db_train_date)
        return db_version

    # Fallback: file exists but no DB record at all
    if file_version:
        logger.warning(
            "No DB models found, using filesystem model: %s (mtime=%.0f). "
            "This model has not been validated.",
            file_version, file_ts
        )
        return file_version

    logger.error("No %s models found in DB or filesystem", model_type)
    return None


# ── route registration ──


