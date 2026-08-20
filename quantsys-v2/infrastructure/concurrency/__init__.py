"""统一并发管理"""
from infrastructure.concurrency.thread_manager import (
    get_thread_pool,
    submit_background,
    get_pool_status,
    shutdown_all_pools,
)

__all__ = [
    'get_thread_pool',
    'submit_background',
    'get_pool_status',
    'shutdown_all_pools',
]
