"""
股票池管理 API (FastAPI 完整异步版本)

集成 StockPoolAsyncService
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from infrastructure.persistence.orm.async_config import get_async_session
from application.services.stock_pool_async_service import StockPoolAsyncService

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/pools",
    tags=["Stock Pools - 股票池管理"]
)


# ==================== Pydantic 模型 ====================

class CreatePoolRequest(BaseModel):
    """创建股票池请求"""
    name: str = Field(..., min_length=1, max_length=100, description="池子名称")
    pool_type: str = Field(..., description="池子类型: static/dynamic")
    description: Optional[str] = Field(None, description="描述")
    symbols: Optional[List[str]] = Field(default=[], description="股票代码列表")
    filter_template: Optional[Dict] = Field(None, description="筛选条件模板")
    scan_enabled: bool = Field(default=True, description="是否启用扫描")


class UpdatePoolRequest(BaseModel):
    """更新股票池请求"""
    name: Optional[str] = Field(None, description="池子名称")
    description: Optional[str] = Field(None, description="描述")
    scan_enabled: Optional[bool] = Field(None, description="是否启用扫描")


class PoolResponse(BaseModel):
    """股票池响应"""
    id: int
    name: str
    pool_type: str
    member_count: int
    scan_enabled: bool
    description: Optional[str] = None
    created_at: Optional[str] = None


class ApiResponse(BaseModel):
    """通用API响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


# ==================== 依赖注入 ====================

async def get_pool_service():
    """获取股票池服务实例"""
    return StockPoolAsyncService()


# ==================== 路由 ====================

@router.post("", response_model=ApiResponse, status_code=201, summary="创建股票池")
async def create_pool(
    request: CreatePoolRequest,
    service: StockPoolAsyncService = Depends(get_pool_service)
):
    """
    创建股票池

    支持两种类型:
    - **static**: 静态池，手动添加股票
    - **dynamic**: 动态池，基于筛选条件自动更新
    """
    try:
        from datetime import datetime

        pool_data = {
            'name': request.name,
            'pool_type': request.pool_type,
            'description': request.description,
            'symbols': request.symbols,
            'filter_template': request.filter_template,
            'scan_enabled': request.scan_enabled,
            'members': [],
            'created_at': datetime.now()
        }

        pool = await service.create_pool(pool_data)

        if not pool:
            raise HTTPException(status_code=500, detail="创建股票池失败")

        return {
            "success": True,
            "data": pool
        }

    except Exception as e:
        logger.exception(f"Create pool failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("", response_model=ApiResponse, summary="列出所有股票池")
async def list_pools(
    pool_type: Optional[str] = None,
    limit: int = 100,
    service: StockPoolAsyncService = Depends(get_pool_service)
):
    """
    列出所有股票池

    - **pool_type**: 可选，筛选池子类型 (static/dynamic)
    - **limit**: 返回数量限制，默认100
    """
    try:
        pools = await service.list_pools(pool_type=pool_type, limit=limit)

        return {
            "success": True,
            "data": pools
        }

    except Exception as e:
        logger.exception(f"List pools failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/enabled", response_model=ApiResponse, summary="获取启用的股票池")
async def get_enabled_pools(
    service: StockPoolAsyncService = Depends(get_pool_service)
):
    """
    获取所有启用扫描的股票池
    """
    try:
        pools = await service.get_enabled_pools()

        return {
            "success": True,
            "data": pools
        }

    except Exception as e:
        logger.exception(f"Get enabled pools failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/{pool_id}", response_model=ApiResponse, summary="获取股票池详情")
async def get_pool(
    pool_id: int,
    service: StockPoolAsyncService = Depends(get_pool_service)
):
    """
    获取股票池详情

    - **pool_id**: 股票池ID
    """
    try:
        pool = await service.get_pool(pool_id)

        if not pool:
            raise HTTPException(status_code=404, detail=f"股票池 {pool_id} 不存在")

        return {
            "success": True,
            "data": pool
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get pool failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.put("/{pool_id}", response_model=ApiResponse, summary="更新股票池")
async def update_pool(
    pool_id: int,
    request: UpdatePoolRequest,
    service: StockPoolAsyncService = Depends(get_pool_service)
):
    """
    更新股票池

    - **pool_id**: 股票池ID
    """
    try:
        # 构建更新数据
        updates = {}
        if request.name is not None:
            updates['name'] = request.name
        if request.description is not None:
            updates['description'] = request.description
        if request.scan_enabled is not None:
            updates['scan_enabled'] = request.scan_enabled

        if not updates:
            return {
                "success": False,
                "error": "没有提供更新字段"
            }

        success = await service.update_pool(pool_id, updates)

        if not success:
            raise HTTPException(status_code=404, detail=f"股票池 {pool_id} 不存在或更新失败")

        return {
            "success": True,
            "data": {"message": f"股票池 {pool_id} 更新成功"}
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Update pool failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.delete("/{pool_id}", response_model=ApiResponse, summary="删除股票池")
async def delete_pool(
    pool_id: int,
    service: StockPoolAsyncService = Depends(get_pool_service)
):
    """
    删除股票池

    - **pool_id**: 股票池ID
    """
    try:
        success = await service.delete_pool(pool_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"股票池 {pool_id} 不存在或删除失败")

        return {
            "success": True,
            "data": {"message": f"股票池 {pool_id} 删除成功"}
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Delete pool failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/scan/universe", response_model=ApiResponse, summary="获取扫描范围")
async def get_scan_universe(
    watchlist: List[str] = [],
    service: StockPoolAsyncService = Depends(get_pool_service)
):
    """
    获取扫描范围（自选股 + 热门股票池）

    - **watchlist**: 用户自选股列表
    """
    try:
        universe = await service.get_scan_universe(watchlist)

        return {
            "success": True,
            "data": {
                "symbols": universe,
                "count": len(universe)
            }
        }

    except Exception as e:
        logger.exception(f"Get scan universe failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
