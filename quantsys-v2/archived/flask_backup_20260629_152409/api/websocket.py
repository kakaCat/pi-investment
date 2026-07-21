"""
WebSocket连接管理器 - 兼容性shim

此模块已迁移到 runtime.websocket
"""
from adapters.inbound.api.websocket import (  # noqa: F401
    ConnectionManager,
    init_connection_manager,
    get_connection_manager,
)

__all__ = [
    "ConnectionManager",
    "init_connection_manager",
    "get_connection_manager",
]
