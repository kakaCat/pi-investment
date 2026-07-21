"""
健康检查和测试路由

第一个 FastAPI 路由示例
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict

router = APIRouter(prefix="/api/test", tags=["Test"])


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str
    framework: str
    message: str


@router.get("/health", response_model=HealthResponse)
async def test_health():
    """
    FastAPI 健康检查

    测试 FastAPI 应用是否正常运行
    """
    return HealthResponse(
        status="ok",
        framework="fastapi",
        message="FastAPI is working!"
    )


@router.get("/info")
async def test_info() -> Dict:
    """
    获取 API 信息

    返回 FastAPI 应用的基本信息
    """
    return {
        "name": "QuantSys V2",
        "framework": "FastAPI",
        "features": [
            "Auto OpenAPI docs",
            "Data validation with Pydantic",
            "Async/await support",
            "High performance",
            "Type hints"
        ]
    }
