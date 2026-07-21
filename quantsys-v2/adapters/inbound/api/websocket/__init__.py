"""
WebSocket运行时模块

提供WebSocket连接管理功能
"""
from adapters.inbound.api.websocket.connection_manager import (
    ConnectionManager,
    init_connection_manager,
    get_connection_manager,
)

__all__ = [
    "ConnectionManager",
    "init_connection_manager",
    "get_connection_manager",
]
