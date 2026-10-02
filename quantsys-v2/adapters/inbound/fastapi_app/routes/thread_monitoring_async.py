"""
线程池监控路由

提供线程池状态查询接口

2026-10-02（REQ-261001145152-3982 审查·清理空转自研池）：
本路由原先读 `infrastructure/threading/thread_pool.py`（`ManagedThreadPool`，301 行）——
实测那套的**三个池入口全仓零调用者**（`get_default_pool` / `get_io_pool` / `get_compute_pool`
无人调用），真正提交后台任务的是 `infrastructure.concurrency.thread_manager.submit_background`。
该模块已删除，本路由改读**实际在用**的那套管理器。

接口形状保持不变：
- `pool_name` 过滤改在路由内做（管理器的 `get_pool_status()` 无参数，返回全部）；
- `is_shutdown` 恒为 `False`——管理器关闭时会清空注册表（`_pools.clear()`），
  因此**还列得出来的池必然是未关闭的**，这个取值是准确的而非占位。
"""

from fastapi import APIRouter
from typing import Dict, Any, Optional

from infrastructure.concurrency.thread_manager import get_pool_status

router = APIRouter(prefix="/api/monitoring/threads", tags=["monitoring"])


@router.get("/status")
async def get_thread_pool_status(pool_name: Optional[str] = None) -> Dict[str, Any]:
    """
    获取线程池状态

    Args:
        pool_name: 线程池名称（如 'api-bg'、'background' 等，取决于调用方命名）
                  如果不提供，返回所有线程池状态

    Returns:
        线程池状态信息
    """
    all_status = get_pool_status()
    if pool_name is None:
        data: Dict[str, Any] = all_status
    else:
        data = {pool_name: all_status[pool_name]} if pool_name in all_status else {}

    return {
        "success": True,
        "data": data
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
                    "is_shutdown": False,   # 关闭时会清空注册表 → 还列得出的必然未关闭
                }
                for name, status in all_status.items()
            ]
        }
    }
