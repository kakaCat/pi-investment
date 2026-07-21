"""
WebSocket连接管理器 - Flask-SocketIO实现
"""
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from typing import Dict, Set
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self, socketio: SocketIO):
        """
        初始化连接管理器

        Args:
            socketio: Flask-SocketIO实例
        """
        self.socketio = socketio
        self.active_connections: Dict[str, Set[str]] = {}  # symbol -> set of session IDs
        self.session_subscriptions: Dict[str, Set[str]] = {}  # session_id -> set of symbols

    def connect(self, session_id: str, symbol: str):
        """
        客户端连接并订阅股票

        Args:
            session_id: 会话ID
            symbol: 股票代码
        """
        # 加入房间（以股票代码为房间名）
        join_room(symbol)

        # 记录连接
        if symbol not in self.active_connections:
            self.active_connections[symbol] = set()
        self.active_connections[symbol].add(session_id)

        if session_id not in self.session_subscriptions:
            self.session_subscriptions[session_id] = set()
        self.session_subscriptions[session_id].add(symbol)

        logger.info(f"客户端订阅: session={session_id}, symbol={symbol}, "
                   f"当前连接数: {len(self.active_connections[symbol])}")

    def disconnect(self, session_id: str, symbol: str = None):
        """
        客户端断开连接

        Args:
            session_id: 会话ID
            symbol: 股票代码（可选，如果不提供则断开所有订阅）
        """
        if symbol:
            # 断开特定股票订阅
            leave_room(symbol)
            if symbol in self.active_connections:
                self.active_connections[symbol].discard(session_id)
                if not self.active_connections[symbol]:
                    del self.active_connections[symbol]

            if session_id in self.session_subscriptions:
                self.session_subscriptions[session_id].discard(symbol)
                if not self.session_subscriptions[session_id]:
                    del self.session_subscriptions[session_id]

            logger.info(f"客户端断开: session={session_id}, symbol={symbol}")
        else:
            # 断开所有订阅
            if session_id in self.session_subscriptions:
                symbols = list(self.session_subscriptions[session_id])
                for sym in symbols:
                    self.disconnect(session_id, sym)

    def broadcast(self, symbol: str, message: dict):
        """
        向订阅该股票的所有客户端广播消息

        Args:
            symbol: 股票代码
            message: 消息内容
        """
        if symbol in self.active_connections and self.active_connections[symbol]:
            self.socketio.emit('message', message, room=symbol)
            logger.debug(f"广播消息: symbol={symbol}, 接收者数量={len(self.active_connections[symbol])}")

    def broadcast_to_all(self, message: dict):
        """
        向所有连接的客户端广播消息

        Args:
            message: 消息内容
        """
        self.socketio.emit('broadcast', message)
        logger.debug(f"全局广播: 消息={message.get('type', 'unknown')}")

    def get_connection_count(self, symbol: str = None) -> int:
        """
        获取连接数

        Args:
            symbol: 股票代码（可选）

        Returns:
            连接数
        """
        if symbol:
            return len(self.active_connections.get(symbol, set()))
        return sum(len(sessions) for sessions in self.active_connections.values())

    def get_subscribed_symbols(self, session_id: str) -> Set[str]:
        """
        获取会话订阅的股票列表

        Args:
            session_id: 会话ID

        Returns:
            股票代码集合
        """
        return self.session_subscriptions.get(session_id, set()).copy()


# 全局连接管理器（需要在初始化时设置socketio实例）
_manager = None


def init_connection_manager(socketio: SocketIO) -> ConnectionManager:
    """
    初始化全局连接管理器

    Args:
        socketio: Flask-SocketIO实例

    Returns:
        ConnectionManager实例
    """
    global _manager
    _manager = ConnectionManager(socketio)
    return _manager


def get_connection_manager() -> ConnectionManager:
    """
    获取全局连接管理器

    Returns:
        ConnectionManager实例

    Raises:
        RuntimeError: 如果管理器未初始化
    """
    if _manager is None:
        raise RuntimeError("ConnectionManager not initialized. Call init_connection_manager first.")
    return _manager
