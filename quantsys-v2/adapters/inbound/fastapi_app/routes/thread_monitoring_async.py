"""
线程池监控路由

提供线程池状态查询接口
"""

from fastapi import APIRouter
from typing import Dict, Any, Optional

from infrastructure.threading.thread_pool import get_pool_status, shutdown_all_pools

router = APIRouter(prefix="/api/monitoring/threads", tags=["monitoring"])


@router.get("/status")
async def get_thread_pool_status(pool_name: Optional[str] = None) -> Dict[str, Any]:
    """
    获取线程池状态

    Args:
        pool_name: 线程池名称 ('default', 'io', 'compute')
                  如果不提供，返回所有线程池状态

    Returns:
        线程池状态信息
    """
    return {
        "success": True,
        "data": get_pool_status(pool_name)
    }


@router.get("/pools")
async def list_available_pools() -> Dict[str, Any]:
    """
    列出所有可用的线程池

    Returns:
        线程池列表和简要信息
    """
    all_status = get_pool_status()

    return {
        "success": True,
        "data": {
            "pools": [
                {
                    "name": name,
                    "max_workers": status["max_workers"],
                    "active_threads": status["active_threads"],
                    "is_shutdown": status["is_shutdown"],
                }
                for name, status in all_status.items()
            ]
        }
    }
