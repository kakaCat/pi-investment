"""
FastAPI 共享辅助模块

从中立共享层 adapters.shared 复用框架无关实现（同一 ds 单例 + 同一序列化逻辑），
并提供 FastAPI 兼容的 api_response / handle_api_error / error_response，
保证迁移后响应契约与 Flask 完全一致（parity）。
"""
import functools
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse
import structlog

# 复用中立共享层（同一 ds 单例 + 同一序列化 → 保证 parity）；不依赖 Flask 路径
from adapters.shared import (
    sanitize_for_json,
    convert_keys_to_camel,
    convert_keys_to_snake,
    _read_watchlist,
    _write_watchlist,
    _read_groups,
    _write_groups,
    strategy_service,
    stock_pool_service,
    pool_validation_service,
    scoring_service,
    sector_rotation_service,
    signal_to_opportunity,
    _safe_float,
    _load_pipeline_runs,
    _save_pipeline_runs,
    _get_pipeline_run,
    _update_pipeline_run,
    acquire_task,
    release_task,
    get_running_tasks_snapshot,
    signal_repo,
    stock_repo,
    kline_repo,
    portfolio_repo,
    factor_repo, risk_repo,
    execution_repo,
    backtest_repo,
    simulation_repo,
)

logger = structlog.get_logger(__name__)


def get_query_params_snake_case(request) -> Dict:
    """FastAPI 版：从 request.query_params 取查询参数并转蛇形（对齐 Flask 版行为）。"""
    return convert_keys_to_snake(dict(request.query_params))


__all__ = [
    "sanitize_for_json", "convert_keys_to_camel", "convert_keys_to_snake",
    "_read_watchlist", "_write_watchlist", "_read_groups", "_write_groups",
    "strategy_service", "stock_pool_service", "pool_validation_service",
    "scoring_service", "sector_rotation_service",
    "signal_to_opportunity", "get_query_params_snake_case", "_safe_float",
    "_load_pipeline_runs", "_save_pipeline_runs", "_get_pipeline_run", "_update_pipeline_run",
    "acquire_task", "release_task", "get_running_tasks_snapshot",
    "api_response", "error_response", "handle_api_error",
    "signal_repo", "stock_repo", "kline_repo", "portfolio_repo", "factor_repo", "risk_repo", "execution_repo", "backtest_repo", "simulation_repo",
]


def api_response(data: Any, success: bool = True, message: Optional[str] = None) -> Dict:
    """标准 API 响应（与 Flask api_response 契约一致；返回 dict 由 FastAPI 序列化）"""
    response: Dict[str, Any] = {
        "success": success,
        "data": convert_keys_to_camel(sanitize_for_json(data)),
    }
    if message:
        response["message"] = message
    return response


def error_response(payload: Dict, status_code: int) -> JSONResponse:
    """非 200 错误响应（保留 Flask 的状态码与响应体形状）"""
    return JSONResponse(content=sanitize_for_json(payload), status_code=status_code)


def handle_api_error(f):
    """API 错误处理装饰器（与 Flask 版契约一致）"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        except KeyError as e:
            return JSONResponse({"success": False, "error": f"缺少参数: {e}"}, status_code=400)
        except Exception as e:
            logger.error(f"API错误: {e}", exc_info=True)
            return JSONResponse({"success": False, "error": f"服务器内部错误: {e}"}, status_code=500)

    return wrapper
