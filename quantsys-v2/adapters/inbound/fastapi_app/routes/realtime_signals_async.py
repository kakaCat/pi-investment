"""
实时信号 API (FastAPI 异步版本)
迁移自 Flask adapters/inbound/api/routes/realtime_signals.py

实时信号推送和查询
"""
from fastapi import APIRouter, Query, WebSocket, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog

from adapters.outbound.repositories.signal_async_repository import SignalAsyncRepository
from infrastructure.persistence.orm.async_config import get_async_session_context
from adapters.shared.services import realtime_signal_service

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/realtime-signals",
    tags=["Realtime Signals - 实时信号"]
)


# ==================== Pydantic 模型 ====================

class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class T1SignalRequest(BaseModel):
    """T+1 信号生成请求"""
    strategy_id: str = Field(..., description="策略 ID")
    symbols: List[str] = Field(..., description="股票代码列表")
    execution_date: Optional[str] = Field(None, description="执行日期 YYYY-MM-DD，默认次日")


class FilterExecutableRequest(BaseModel):
    """可执行信号过滤请求"""
    signals: List[Dict] = Field(..., description="原始信号列表")
    max_gap_pct: float = Field(3.0, description="最大可接受价差（%）")
    check_realtime: bool = Field(True, description="是否检查实时价格")


class MorningScanRequest(BaseModel):
    """早盘扫描请求"""
    strategy_ids: List[str] = Field(..., description="策略 ID 列表")
    stock_pool: List[str] = Field(..., description="股票池（股票代码列表）")
    notify: bool = Field(False, description="是否推送通知")


# ==================== 路由端点 ====================

@router.get("/latest", response_model=ApiResponse, summary="获取最新信号")
async def get_latest_signals(
    limit: int = Query(20, description="返回数量"),
    status: Optional[str] = Query(None, description="状态过滤")
):
    """
    获取最新生成的信号

    Query Params:
        - limit: 返回数量（默认 20）
        - status: 状态过滤（pending/executed/closed）

    Returns:
        {
            "success": true,
            "data": {
                "signals": [...],
                "count": 10,
                "timestamp": "2026-06-29T20:00:00"
            }
        }
    """
    try:
        async with get_async_session_context() as session:
            signal_repo = SignalAsyncRepository(session)

            signals = await signal_repo.get_signals(
                status=status,
                limit=limit
            )

            return {
                "success": True,
                "data": {
                    "signals": signals,
                    "count": len(signals)
                }
            }

    except Exception as e:
        logger.exception(f"获取最新信号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/t1/generate", response_model=ApiResponse, summary="生成 T+1 信号")
async def generate_t1_signals(request: T1SignalRequest):
    """
    生成 T+1 信号（今日收盘后生成，明日执行）

    Agent 在每日收盘后（15:00）调用此接口，生成次日交易信号

    Args:
        request: T+1 信号生成请求
            - strategy_id: 策略 ID（如 "273"）
            - symbols: 股票代码列表（如 ["600726", "000001"]）
            - execution_date: 执行日期（可选，默认次日）

    Returns:
        {
            "success": true,
            "data": [
                {
                    "symbol": "600726",
                    "entry_price": 9.71,
                    "signal_type": "BUY",
                    "execution_date": "2026-06-30",
                    "mode": "T+1",
                    "generated_at": "2026-06-29T15:30:00"
                }
            ],
            "count": 1
        }

    Example:
        POST /api/realtime-signals/t1/generate
        {
            "strategy_id": "273",
            "symbols": ["600726", "000001"],
            "execution_date": "2026-06-30"
        }
    """
    try:
        if not request.strategy_id or not request.symbols:
            return {
                "success": False,
                "error": "缺少必填参数: strategy_id, symbols"
            }

        service = realtime_signal_service
        signals = service.generate_t1_signals(
            request.strategy_id,
            request.symbols,
            request.execution_date
        )

        return {
            "success": True,
            "data": signals,
            "count": len(signals)
        }

    except Exception as e:
        logger.exception(f"生成 T+1 信号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filter/executable", response_model=ApiResponse, summary="过滤可执行信号")
async def filter_executable(request: FilterExecutableRequest):
    """
    过滤可执行信号（检查价格偏离）

    Agent 在开盘前检查信号的入场价格与实时价格的偏离度，
    过滤掉偏离过大的信号，避免高位追入

    Args:
        request: 过滤请求
            - signals: 原始信号列表
            - max_gap_pct: 最大可接受价差（%，默认 3.0）
            - check_realtime: 是否检查实时价格（默认 True）

    Returns:
        {
            "success": true,
            "data": {
                "executable": [...],   // 可执行信号
                "rejected": [...]      // 被拒绝的信号
            },
            "summary": {
                "total": 10,
                "executable": 7,
                "rejected": 3
            }
        }

    Example:
        POST /api/realtime-signals/filter/executable
        {
            "signals": [
                {"symbol": "600726", "entry_price": 9.71, ...}
            ],
            "max_gap_pct": 3.0,
            "check_realtime": true
        }

    Response:
        {
            "success": true,
            "data": {
                "executable": [
                    {"symbol": "600726", "entry_price": 9.71, "current_price": 9.80, "gap_pct": 0.9, "executable": true}
                ],
                "rejected": [
                    {"symbol": "000001", "entry_price": 10.0, "current_price": 10.5, "gap_pct": 5.0, "executable": false, "reason": "价格偏离过大"}
                ]
            },
            "summary": {
                "total": 2,
                "executable": 1,
                "rejected": 1
            }
        }
    """
    try:
        service = realtime_signal_service

        executable = service.filter_executable_signals(
            request.signals,
            max_gap_pct=request.max_gap_pct,
            check_realtime=request.check_realtime
        )

        # 分离可执行和被拒绝的信号
        rejected = [s for s in request.signals if not s.get('executable', True)]

        return {
            "success": True,
            "data": {
                "executable": executable,
                "rejected": rejected
            },
            "summary": {
                "total": len(request.signals),
                "executable": len(executable),
                "rejected": len(rejected)
            }
        }

    except Exception as e:
        logger.exception(f"过滤可执行信号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/morning-scan", response_model=ApiResponse, summary="早盘扫描")
async def morning_scan(request: MorningScanRequest):
    """
    早盘扫描（每日 9:00 定时调用）

    Agent 定时任务在每日 9:00 扫描股票池，
    对所有股票应用策略，生成当日交易机会

    Args:
        request: 早盘扫描请求
            - strategy_ids: 策略 ID 列表（如 ["273", "274"]）
            - stock_pool: 股票池（股票代码列表）
            - notify: 是否推送通知（默认 False）

    Returns:
        {
            "success": true,
            "data": [...],  // 可执行信号列表
            "summary": {
                "total_scanned": 100,
                "signals_generated": 5,
                "executable": 3
            }
        }

    Example:
        POST /api/realtime-signals/morning-scan
        {
            "strategy_ids": ["273", "274"],
            "stock_pool": ["600726", "000001", "600519"],
            "notify": true
        }

    Response:
        {
            "success": true,
            "data": [
                {
                    "symbol": "600726",
                    "signal_type": "BUY",
                    "entry_price": 9.71,
                    "strategy_id": "273",
                    "executable": true
                }
            ],
            "summary": {
                "total_scanned": 3,
                "signals_generated": 5,
                "executable": 1
            }
        }
    """
    try:
        if not request.strategy_ids or not request.stock_pool:
            return {
                "success": False,
                "error": "缺少必填参数: strategy_ids, stock_pool"
            }

        service = realtime_signal_service

        # 通知回调（可选）
        notification_callback = None
        if request.notify:
            def send_notification(signals):
                # TODO: 集成飞书/企业微信推送
                logger.info(f"推送 {len(signals)} 个信号")
            notification_callback = send_notification

        signals = service.schedule_morning_scan(
            request.strategy_ids,
            request.stock_pool,
            notification_callback
        )

        # 过滤可执行信号
        executable = [s for s in signals if s.get('executable', True)]

        return {
            "success": True,
            "data": executable,
            "summary": {
                "total_scanned": len(request.stock_pool),
                "signals_generated": len(signals),
                "executable": len(executable)
            }
        }

    except Exception as e:
        logger.exception(f"早盘扫描失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
