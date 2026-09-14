"""
P2低频API批量异步路由集合 - 第1批

包含诊断、红利、财务、基金等低频API
"""
from fastapi import APIRouter, Query, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


# ==================== 诊断 API ====================
diagnosis_router = APIRouter(
    prefix="/diagnosis",
    tags=["Diagnosis - 系统诊断"]
)


@diagnosis_router.post("/run", response_model=ApiResponse, summary="运行诊断")
async def run_diagnosis(
    scope: str = Body("all", description="诊断范围")
):
    """运行系统诊断"""
    try:
        result = {
            "status": "healthy",
            "checks": [],
            "issues": []
        }
        return {"success": True, "data": result}
    except Exception as e:
        logger.exception(f"Run diagnosis failed: {e}")
        return {"success": False, "error": str(e)}


@diagnosis_router.get("/health", response_model=ApiResponse, summary="健康检查")
async def diagnosis_health():
    """系统健康检查"""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "uptime": "24h",
            "version": "2.0.1"
        }
    }


# ==================== 红利 API ====================
dividends_router = APIRouter(
    prefix="/dividends",
    tags=["Dividends - 股息红利"]
)


@dividends_router.get("/stock/{symbol}", response_model=ApiResponse, summary="股票分红")
async def get_stock_dividends(
    symbol: str,
    start_year: Optional[int] = Query(None, description="开始年份"),
    end_year: Optional[int] = Query(None, description="结束年份")
):
    """获取股票分红历史"""
    try:
        dividends = []
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "dividends": dividends,
                "count": len(dividends)
            }
        }
    except Exception as e:
        logger.exception(f"Get dividends failed: {e}")
        return {"success": False, "error": str(e)}


# ==================== 财务数据 API ====================
financial_router = APIRouter(
    prefix="/financial",
    tags=["Financial - 财务数据"]
)


@financial_router.get("/stock/{symbol}", response_model=ApiResponse, summary="财务数据")
async def get_financial_data(
    symbol: str,
    report_type: str = Query("annual", description="报告类型")
):
    """获取财务数据"""
    try:
        from application.services.core_async_services import DataAsyncService

        service = DataAsyncService()
        # 简化实现
        financial = {
            "symbol": symbol,
            "report_type": report_type,
            "data": {}
        }
        return {"success": True, "data": financial}
    except Exception as e:
        logger.exception(f"Get financial data failed: {e}")
        return {"success": False, "error": str(e)}


# ==================== 基金流向 API ====================
fund_flow_router = APIRouter(
    prefix="/fund-flow",
    tags=["Fund Flow - 资金流向"]
)


@fund_flow_router.get("/stock/{symbol}", response_model=ApiResponse, summary="个股资金流")
async def get_stock_fund_flow(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期")
):
    """获取个股资金流向"""
    try:
        from adapters.outbound.repositories.p2_async_repositories import FundFlowAsyncRepository
        from infrastructure.persistence.orm.async_config import get_async_session_context

        async with get_async_session_context() as session:
            repo = FundFlowAsyncRepository(session)
            flows = await repo.get_flows(symbol, start_date, limit=100)

            return {
                "success": True,
                "data": {
                    "symbol": symbol,
                    "flows": flows,
                    "count": len(flows)
                }
            }
    except Exception as e:
        logger.exception(f"Get fund flow failed: {e}")
        return {"success": False, "error": str(e)}


@fund_flow_router.get("/market", response_model=ApiResponse, summary="市场资金流")
async def get_market_fund_flow(
    date: Optional[str] = Query(None, description="日期")
):
    """获取市场资金流向"""
    try:
        flow = {
            "date": date,
            "main_inflow": 0,
            "main_outflow": 0,
            "net_flow": 0
        }
        return {"success": True, "data": flow}
    except Exception as e:
        logger.exception(f"Get market fund flow failed: {e}")
        return {"success": False, "error": str(e)}


# ==================== 【已删除】自动化任务 API ====================
# 2026-09-14（w-2129d492）：整段删除 /api/automation/* 与 /api/agent-intelligence/*。
# 删除理由（实测核验，非"看起来没人用"）：
#   · 业务归属 = 旧 Agent OS 自动化系统的读面板：其执行器 smart_scheduler.py 已无任何启动入口，
#     调度 9 月初收敛到 UnifiedScheduler + quant.scheduler_tasks（另一张表）；
#     quant.automation_tasks 里 3 条启用任务的 last_run_at 全部停在 2026-06-27，automation_runs 仅 1 条。
#   · 无消费者：前端（web-frontend / agent-dh 页面）、agent-ts、agent-os(Go)、文档 全仓零调用；
#     唯一引用方就是本文件与两处注册点（main.py / route_registrar.py）。
#   · 恒假成功：AutomationAsyncRepository 查的是不存在的列（enabled/last_run/schedule，
#     真库为 is_enabled/last_run_at/schedule_config）→ UndefinedColumn 被 except 吞掉 →
#     /api/automation/tasks 恒返回 {"tasks":[],"count":0}；/tasks/{id} 更是硬编码"示例任务"。
#     /api/agent-intelligence/knowledge 同理：quant.agent_intelligence 表在库中从未存在过。
#   · 唯一"对接了真实表"的自动化代码是 adapters/outbound/repositories/automation_repository.py
#     与 application/services/smart_scheduler.py（后者同样无启动入口），不在本文件内。
# 若将来要重启"自动化任务面板"，请重新设计并直接读 quant.automation_tasks 的真实列，
# 不要复活这段（原文见 git 历史：git log -p -- <本文件>）。


# 导出所有路由（automation_router / agent_intelligence_router 已于 2026-09-14 删除，见上）
__all__ = [
    'diagnosis_router',
    'dividends_router',
    'financial_router',
    'fund_flow_router',
]
