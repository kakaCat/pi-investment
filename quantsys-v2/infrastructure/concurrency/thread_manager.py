"""统一线程池管理（Phase 4 任务 8）

替代 API 路由中散落的 threading.Thread(target=..., daemon=True).start()
火后即忘模式——裸线程在负载下无上限创建，且无法观测/复用。

使用方式:
    from infrastructure.concurrency.thread_manager import submit_background

    submit_background("api-bg", task_function, arg1, arg2, kw=1)

注意：长驻 daemon 循环（WatchEngine / Orchestrator / Scheduler run_loop）
不适用本模块——它们是无限循环，池线程永不归还，应继续用专用线程并由
FastAPI lifespan 管理优雅停止。
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

_pools: Dict[str, ThreadPoolExecutor] = {}
_lock = threading.Lock()

# 命名池默认容量（API 后台任务多为 IO 密集，给足并发但设上限）
_DEFAULT_MAX_WORKERS = 8


def get_thread_pool(name: str, max_workers: int = _DEFAULT_MAX_WORKERS) -> ThreadPoolExecutor:
    """获取或创建命名线程池（同名校验容量一致）"""
    with _lock:
        pool = _pools.get(name)
        if pool is None:
            pool = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix=f"{name}-worker"
            )
            _pools[name] = pool
            logger.info("thread_pool_created", name=name, max_workers=max_workers)
        return pool


def submit_background(pool_name: str, fn, *args, max_workers: int = _DEFAULT_MAX_WORKERS, **kwargs) -> Future:
    """向命名池提交后台任务，返回 Future（调用方可忽略或等待）"""
    pool = get_thread_pool(pool_name, max_workers=max_workers)
    future = pool.submit(fn, *args, **kwargs)
    return future


def get_pool_status() -> Dict[str, dict]:
    """获取所有线程池状态（观测用，访问私有属性属已知局限）"""
    status = {}
    with _lock:
        for name, pool in _pools.items():
            status[name] = {
                'max_workers': pool._max_workers,
                'active_threads': len([t for t in pool._threads if t.is_alive()]),
                'pending_tasks': pool._work_queue.qsize(),
            }
    return status


def shutdown_all_pools(wait: bool = True):
    """关闭所有线程池（应用退出时由 lifespan 调用）"""
    with _lock:
        for name, pool in _pools.items():
            logger.info("thread_pool_shutdown", name=name)
            pool.shutdown(wait=wait)
        _pools.clear()
