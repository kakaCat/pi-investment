"""M3-1 信号追踪 API

端点：
- POST   /api/signals/track          记录信号
- PUT    /api/signals/track/update   批量更新表现（盘后例程）
- GET    /api/signals/track/report   统计报告
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel, Field
import structlog

from adapters.inbound.fastapi_app.shared import api_response, error_response, handle_api_error
from application.services.signal_tracking_service import SignalTrackingService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Signal Tracking - 信号质量追踪"])


# === 请求模型 ===

class RecordSignalRequest(BaseModel):
    """记录信号请求"""
    signal_date: str = Field(..., description="信号日期 YYYY-MM-DD")
    symbol: str = Field(..., description="股票代码，如 600519")
    grade: str = Field(..., description="信号级别 A/B/C")
    source: str = Field(..., description="信号来源：strategy_execute/opportunity_scan/mainline_stocks/watch_rule")
    price: float = Field(..., description="买入价格")
    reason: Optional[str] = Field(None, description="信号理由")
    
    class Config:
        json_schema_extra = {
            "example": {
                "signal_date": "2024-08-27",
                "symbol": "600519",
                "grade": "A",
                "source": "mainline_stocks",
                "price": 1850.50,
                "reason": "主线白酒+技术突破+资金流入"
            }
        }


class UpdatePerformanceRequest(BaseModel):
    """更新表现请求"""
    signal_date: Optional[str] = Field(None, description="指定更新日期（None=更新最近30天）")
    lookback_days: int = Field(30, description="回溯天数")


# === API 端点 ===

@router.post('/api/signals/track')
@handle_api_error
def record_signal(request: RecordSignalRequest = Body(...)):
    """记录买入信号
    
    用于：R-009 信号分级规则，agent 调用此 API 记录信号
    
    Returns:
        {"success": True, "data": {"signal_id": 123}}
    """
    service = SignalTrackingService()
    
    result = service.record_signal(
        signal_date=request.signal_date,
        symbol=request.symbol,
        grade=request.grade,
        source=request.source,
        price=request.price,
        reason=request.reason
    )
    
    return api_response({
        "signal_id": result["signal_id"],
        "message": result["message"]
    })


@router.put('/api/signals/track/update')
@handle_api_error
def update_performance(request: UpdatePerformanceRequest = Body(...)):
    """批量更新信号表现（盘后例程调用）
    
    回填 5/10/20 日后的价格和收益率
    
    Returns:
        {"success": True, "data": {"updated": 15, "details": {...}}}
    """
    service = SignalTrackingService()
    
    result = service.update_performance(
        signal_date=request.signal_date,
        lookback_days=request.lookback_days
    )
    
    return api_response({
        "updated": result["updated"],
        "details": result["details"]
    })


@router.get('/api/signals/track/report')
@handle_api_error
def get_report(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    grade: Optional[str] = Query(None, description="过滤级别 A/B/C"),
    source: Optional[str] = Query(None, description="过滤来源")
):
    """获取信号统计报告
    
    返回各级别信号的胜率和平均收益
    
    Returns:
        {
            "success": True,
            "data": {
                "total": 100,
                "by_grade": {
                    "A": {"count": 30, "hit_rate_5d": 0.75, "avg_return_5d": 0.08, ...},
                    "B": {...},
                    "C": {...}
                },
                "by_source": {...},
                "recent_signals": [...]
            }
        }
    """
    service = SignalTrackingService()
    
    stats = service.get_statistics(
        start_date=start_date,
        end_date=end_date,
        grade=grade,
        source=source
    )
    
    return api_response(stats)


# ============ signal_perf_backfill_daily job handler（2026-09-01 investor w-8366e526） ============
# ADR-002 后 v2 定时任务由 Agent OS 调度（webhook 模式）。原 signal-perf-backfill-daily 在
# DSH 原生调度迁移中被禁用为 /bin/true 空壳，回填职责悬空（审计 §7.2 #3）。此处注册
# webhook handler：盘后由 Agent OS 触发，直接调用 SignalTrackingService.update_performance
# 回填信号 5/10/20 日表现，不依赖 agent 响应，保证胜率统计与验证门样本持续更新。
try:
    from api.internal.scheduler_webhook import register_job_handler

    @register_job_handler("signal_perf_backfill_daily")
    async def handle_signal_perf_backfill(metadata=None):
        """盘后回填信号 5/10/20 日表现（15:45 由 Agent OS 触发）"""
        try:
            lookback_days = 30
            if metadata and isinstance(metadata, dict):
                lookback_days = int(metadata.get("lookback_days", 30))
            service = SignalTrackingService()
            result = service.update_performance(lookback_days=lookback_days)
            return {
                "status": "ok",
                "updated": result.get("updated", 0),
                "details": result.get("details", {}),
            }
        except Exception as e:
            logger.exception(f"signal_perf_backfill_daily job failed: {e}")
            return {"status": "error", "error": str(e)}
except ImportError as _e:  # pytest 或最小化启动场景下可选依赖缺失不阻塞路由加载
    pass
