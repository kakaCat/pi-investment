"""
统一策略交易 API 路由 - FastAPI 版本

提供配置驱动的策略 API，支持所有策略版本（V13/V14/V15...）
避免重复代码，统一接口

API 端点：
    GET  /api/strategy/list                          - 列出所有策略
    GET  /api/strategy/<strategy_name>/account-info  - 账户信息
    GET  /api/strategy/<strategy_name>/positions     - 持仓明细
    POST /api/strategy/<strategy_name>/rebalance     - 手动调仓
    POST /api/strategy/<strategy_name>/daily-check   - 每日检查

使用示例：
    # V13
    curl http://localhost:5001/api/strategy/v13/account-info
    curl -X POST http://localhost:5001/api/strategy/v13/rebalance

    # V14
    curl http://localhost:5001/api/strategy/v14/account-info
    curl -X POST http://localhost:5001/api/strategy/v14/rebalance

    # 未来 V15（无需修改代码）
    curl http://localhost:5001/api/strategy/v15/account-info
"""
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import structlog

from application.services.strategy_service import StrategyService

logger = structlog.get_logger(__name__)

# 创建统一策略路由
router = APIRouter(
    prefix="/strategy",
    tags=["Unified Strategy Trading - 统一策略交易"]
)


# ==================== Pydantic 模型 ====================

class ApiResponse(BaseModel):
    """标准 API 响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class RebalanceRequest(BaseModel):
    """调仓请求"""
    rebalance_days: Optional[int] = Field(None, description="覆盖调仓周期")
    max_positions: Optional[int] = Field(None, description="覆盖最大持仓数")


class DailyCheckRequest(BaseModel):
    """每日检查请求"""
    enable_stop_loss: Optional[bool] = Field(True, description="是否启用止损")
    enable_rebalance: Optional[bool] = Field(True, description="是否启用调仓")


# ==================== 路由端点 ====================

@router.get("/list", response_model=ApiResponse, summary="列出所有策略")
async def list_strategies():
    """
    列出所有可用策略

    Returns:
        {
            "success": true,
            "data": {
                "strategies": ["v13", "v14"],
                "count": 2
            }
        }
    """
    try:
        service = StrategyService()
        strategies = service.list_strategies()

        return {
            "success": True,
            "data": {
                "strategies": strategies,
                "count": len(strategies)
            }
        }

    except Exception as e:
        logger.exception(f"列出策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{strategy_name}/account-info", response_model=ApiResponse, summary="获取账户信息")
async def get_account_info(strategy_name: str):
    """
    获取策略账户信息（统一接口）

    Args:
        strategy_name: 策略名称（v13/v14/v15...）

    Returns:
        {
            "success": true,
            "data": {
                "strategy_name": "v13",
                "account_name": "default",
                "total_value": 120000,
                "cash": 30000,
                "position_value": 90000,
                "positions_count": 5,
                "cumulative_return": 0.20,
                "last_rebalance_date": "2026-06-29",
                "config": {...}
            }
        }

    Examples:
        GET /api/strategy/v13/account-info
        GET /api/strategy/v14/account-info
    """
    try:
        service = StrategyService()
        account = service.get_account_info(strategy_name)

        return {
            "success": True,
            "data": account
        }

    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_name} - {e}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.exception(f"获取账户信息失败: {strategy_name} - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{strategy_name}/positions", response_model=ApiResponse, summary="获取持仓明细")
async def get_positions(strategy_name: str):
    """
    获取策略持仓明细（统一接口）

    Args:
        strategy_name: 策略名称

    Returns:
        {
            "success": true,
            "data": [
                {
                    "symbol": "600000",
                    "name": "浦发银行",
                    "shares": 1000,
                    "cost": 10.5,
                    "current_price": 11.2,
                    "market_value": 11200,
                    "profit": 700,
                    "profit_pct": 0.0667
                }
            ]
        }

    Examples:
        GET /api/strategy/v13/positions
        GET /api/strategy/v14/positions
    """
    try:
        service = StrategyService()
        positions = service.get_positions(strategy_name)

        return {
            "success": True,
            "data": positions
        }

    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_name} - {e}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.exception(f"获取持仓失败: {strategy_name} - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{strategy_name}/rebalance", response_model=ApiResponse, summary="手动调仓")
async def manual_rebalance(
    strategy_name: str,
    request: RebalanceRequest = Body(default=None)
):
    """
    手动触发调仓（统一接口）

    Args:
        strategy_name: 策略名称
        request: 可选参数
            - rebalance_days: 覆盖调仓周期
            - max_positions: 覆盖最大持仓数

    Returns:
        {
            "success": true,
            "data": {
                "strategy": "v13",
                "status": "success",
                "account_name": "default",
                "timestamp": "2026-07-02T23:00:00",
                "result": {...}
            }
        }

    Examples:
        POST /api/strategy/v13/rebalance
        POST /api/strategy/v14/rebalance
        {
            "rebalance_days": 3,
            "max_positions": 10
        }
    """
    try:
        service = StrategyService()

        # 获取可选参数
        params = request.dict(exclude_none=True) if request else {}

        result = service.manual_rebalance(strategy_name, **params)

        return {
            "success": True,
            "data": result
        }

    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_name} - {e}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.exception(f"手动调仓失败: {strategy_name} - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{strategy_name}/daily-check", response_model=ApiResponse, summary="每日检查")
async def daily_check(
    strategy_name: str,
    request: DailyCheckRequest = Body(default=None)
):
    """
    执行每日检查（统一接口）

    Args:
        strategy_name: 策略名称
        request: 可选参数
            - enable_stop_loss: 是否启用止损（默认True）
            - enable_rebalance: 是否启用调仓（默认True）

    Returns:
        {
            "success": true,
            "data": {
                "strategy": "v13",
                "status": "success",
                "account_name": "default",
                "timestamp": "2026-07-02T23:00:00",
                "initial_value": 120000,
                "final_value": 121500,
                "cash": 30000,
                "positions_count": 5,
                "cumulative_return": 0.215
            }
        }

    Examples:
        POST /api/strategy/v13/daily-check
        POST /api/strategy/v14/daily-check
        {
            "enable_stop_loss": false,
            "enable_rebalance": true
        }
    """
    try:
        service = StrategyService()

        # 获取可选参数
        params = request.dict(exclude_none=True) if request else {}

        result = service.daily_check(strategy_name, **params)

        return {
            "success": True,
            "data": result
        }

    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_name} - {e}")
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.exception(f"每日检查失败: {strategy_name} - {e}")
        raise HTTPException(status_code=500, detail=str(e))
