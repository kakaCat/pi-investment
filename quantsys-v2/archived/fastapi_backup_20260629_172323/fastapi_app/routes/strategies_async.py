"""
策略管理 API (FastAPI 异步版本)

集成 StrategyCodeAsyncService
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog

from application.services.core_async_services import StrategyCodeAsyncService

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/strategies",
    tags=["Strategies - 策略管理"]
)


# ==================== Pydantic 模型 ====================

class CreateStrategyRequest(BaseModel):
    """创建策略请求"""
    strategy_name: str = Field(..., min_length=1, max_length=100, description="策略名称")
    strategy_type: str = Field(..., description="策略类型")
    description: Optional[str] = Field(None, description="策略描述")
    parameters: Optional[Dict] = Field(None, description="策略参数")


class UpdateStrategyRequest(BaseModel):
    """更新策略请求"""
    strategy_name: Optional[str] = Field(None, description="策略名称")
    description: Optional[str] = Field(None, description="策略描述")
    parameters: Optional[Dict] = Field(None, description="策略参数")


class RunStrategyRequest(BaseModel):
    """运行策略请求"""
    symbols: List[str] = Field(..., description="股票代码列表")


class ApiResponse(BaseModel):
    """通用API响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


# ==================== 依赖注入 ====================

async def get_strategy_service():
    """获取策略服务实例"""
    return StrategyCodeAsyncService()


# ==================== 路由 ====================

@router.get("", response_model=ApiResponse, summary="列出所有策略")
async def list_strategies(
    strategy_type: Optional[str] = Query(None, description="策略类型"),
    service: StrategyCodeAsyncService = Depends(get_strategy_service)
):
    """
    列出所有策略

    - **strategy_type**: 策略类型（可选）
    """
    try:
        strategies = await service.list_strategies(strategy_type=strategy_type)

        return {
            "success": True,
            "data": strategies
        }

    except Exception as e:
        logger.exception(f"List strategies failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/{strategy_id}", response_model=ApiResponse, summary="获取策略详情")
async def get_strategy(
    strategy_id: int,
    service: StrategyCodeAsyncService = Depends(get_strategy_service)
):
    """
    获取策略详情

    - **strategy_id**: 策略ID
    """
    try:
        strategy = await service.get_strategy(strategy_id)

        if not strategy:
            raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

        return {
            "success": True,
            "data": strategy
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get strategy failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("", response_model=ApiResponse, status_code=201, summary="创建策略")
async def create_strategy(
    request: CreateStrategyRequest,
    service: StrategyCodeAsyncService = Depends(get_strategy_service)
):
    """
    创建策略
    """
    try:
        strategy_data = {
            'strategy_name': request.strategy_name,
            'strategy_type': request.strategy_type,
            'description': request.description,
            'parameters': request.parameters
        }

        strategy_id = await service.create_strategy(strategy_data)

        if not strategy_id:
            raise HTTPException(status_code=500, detail="创建策略失败")

        return {
            "success": True,
            "data": {"id": strategy_id, "message": "策略创建成功"}
        }

    except Exception as e:
        logger.exception(f"Create strategy failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/{strategy_id}/run", response_model=ApiResponse, summary="运行策略")
async def run_strategy(
    strategy_id: int,
    request: RunStrategyRequest,
    service: StrategyCodeAsyncService = Depends(get_strategy_service)
):
    """
    运行策略生成信号

    - **strategy_id**: 策略ID
    - **symbols**: 股票代码列表
    """
    try:
        signals = await service.run_strategy(strategy_id, request.symbols)

        return {
            "success": True,
            "data": {
                "signals": signals,
                "count": len(signals)
            }
        }

    except Exception as e:
        logger.exception(f"Run strategy failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
