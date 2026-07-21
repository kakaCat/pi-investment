"""
股票池管理 API (FastAPI 版本)

迁移自 Flask 的 pools.py
"""
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/pools",
    tags=["Stock Pools"]
)


# ==================== Pydantic 模型 ====================

class CreatePoolRequest(BaseModel):
    """创建股票池请求"""
    name: str = Field(..., min_length=1, max_length=100, description="池子名称")
    pool_type: str = Field(..., description="池子类型: static/dynamic")
    symbols: Optional[List[str]] = Field(None, description="股票代码列表")
    filter_template: Optional[Dict] = Field(None, description="筛选条件模板")
    refresh_interval: Optional[int] = Field(None, description="刷新间隔(秒)")
    description: Optional[str] = Field(None, description="描述")


class PoolResponse(BaseModel):
    """股票池响应"""
    id: int
    name: str
    pool_type: str
    member_count: int
    created_at: str
    description: Optional[str] = None


class ApiResponse(BaseModel):
    """通用API响应"""
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None


# ==================== 路由 ====================

@router.post("", response_model=ApiResponse, status_code=201)
async def create_pool(request: CreatePoolRequest):
    """
    创建股票池

    支持两种类型:
    - static: 静态池，手动添加股票
    - dynamic: 动态池，基于筛选条件自动更新
    """
    try:
        # TODO: 接入实际 Service
        # from adapters.inbound.api.shared import stock_pool_service
        # pool = stock_pool_service.create_pool(...)

        return {
            "success": True,
            "data": {
                "id": 1,
                "name": request.name,
                "pool_type": request.pool_type,
                "member_count": len(request.symbols) if request.symbols else 0,
                "created_at": "2026-06-26T12:00:00"
            }
        }
    except Exception as e:
        logger.exception(f"Create pool failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ApiResponse)
async def list_pools():
    """
    列出所有股票池
    """
    try:
        # TODO: 接入实际 Service
        return {
            "success": True,
            "data": [
                {"id": 1, "name": "价值股池", "pool_type": "dynamic", "member_count": 50},
                {"id": 2, "name": "成长股池", "pool_type": "dynamic", "member_count": 30}
            ]
        }
    except Exception as e:
        logger.exception(f"List pools failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{pool_id}", response_model=ApiResponse)
async def get_pool(pool_id: int):
    """
    获取股票池详情
    """
    try:
        # TODO: 接入实际 Service
        return {
            "success": True,
            "data": {
                "id": pool_id,
                "name": "价值股池",
                "pool_type": "dynamic",
                "member_count": 50,
                "members": ["600519.SH", "000858.SZ"],
                "created_at": "2026-06-26T12:00:00"
            }
        }
    except Exception as e:
        logger.exception(f"Get pool failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{pool_id}", response_model=ApiResponse)
async def delete_pool(pool_id: int):
    """
    删除股票池
    """
    try:
        # TODO: 接入实际 Service
        return {
            "success": True,
            "data": {"message": f"Pool {pool_id} deleted"}
        }
    except Exception as e:
        logger.exception(f"Delete pool failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
