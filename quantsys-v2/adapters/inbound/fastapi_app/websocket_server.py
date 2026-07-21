"""
QuantSys V2 WebSocket 服务 - FastAPI 版本
替换 Flask-SocketIO，提供更好的性能和原生异步支持

端口: 5003
连接: ws://localhost:5003/ws
"""
import sys
import os
from pathlib import Path
from typing import Dict, Set
import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).resolve().parent.parent.parent.parent / '.env'
load_dotenv(env_path)

# 确保项目根目录在 PYTHONPATH
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 统一使用结构化日志配置
from infrastructure.logging import configure_structured_logging
configure_structured_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_format=os.getenv("LOG_FORMAT") == "json",
    enable_trace_id=True
)

import structlog
logger = structlog.get_logger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="QuantSys V2 WebSocket",
    description="Real-time data streaming for QuantSys V2",
    version="2.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 连接管理 ====================

class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 所有活跃连接
        self.active_connections: Set[WebSocket] = set()
        # 订阅频道: channel -> set of websockets
        self.subscriptions: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """接受新连接"""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        """断开连接"""
        async with self._lock:
            self.active_connections.discard(websocket)
            # 从所有订阅中移除
            for channel in list(self.subscriptions.keys()):
                self.subscriptions[channel].discard(websocket)
                if not self.subscriptions[channel]:
                    del self.subscriptions[channel]
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def subscribe(self, websocket: WebSocket, channel: str):
        """订阅频道"""
        async with self._lock:
            if channel not in self.subscriptions:
                self.subscriptions[channel] = set()
            self.subscriptions[channel].add(websocket)
        logger.info(f"Client subscribed to channel: {channel}")

    async def unsubscribe(self, websocket: WebSocket, channel: str):
        """取消订阅"""
        async with self._lock:
            if channel in self.subscriptions:
                self.subscriptions[channel].discard(websocket)
                if not self.subscriptions[channel]:
                    del self.subscriptions[channel]
        logger.info(f"Client unsubscribed from channel: {channel}")

    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        if not self.active_connections:
            return

        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                disconnected.add(connection)

        # 清理断开的连接
        for conn in disconnected:
            await self.disconnect(conn)

    async def broadcast_to_channel(self, channel: str, message: dict):
        """广播消息到指定频道"""
        if channel not in self.subscriptions:
            return

        disconnected = set()
        for connection in self.subscriptions[channel]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to channel {channel}: {e}")
                disconnected.add(connection)

        # 清理断开的连接
        for conn in disconnected:
            await self.disconnect(conn)


# 全局连接管理器
manager = ConnectionManager()


# ==================== WebSocket 端点 ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    主 WebSocket 端点

    消息格式:
    {
        "type": "subscribe" | "unsubscribe" | "ping",
        "channel": "市场数据频道名称",
        "data": {...}
    }

    支持的频道:
    - market_data: 市场实时数据
    - signals: 信号推送
    - game_alerts: 游戏智能告警
    - pool_changes: 股票池变化
    - executions: 执行记录
    """
    await manager.connect(websocket)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get("type")
                channel = message.get("channel")

                if msg_type == "subscribe":
                    if channel:
                        await manager.subscribe(websocket, channel)
                        await websocket.send_json({
                            "type": "subscribed",
                            "channel": channel,
                            "status": "ok"
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Channel name required"
                        })

                elif msg_type == "unsubscribe":
                    if channel:
                        await manager.unsubscribe(websocket, channel)
                        await websocket.send_json({
                            "type": "unsubscribed",
                            "channel": channel,
                            "status": "ok"
                        })

                elif msg_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })

    except WebSocketDisconnect:
        await manager.disconnect(websocket)


# ==================== HTTP API (用于触发推送) ====================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "connections": len(manager.active_connections),
        "channels": list(manager.subscriptions.keys())
    }


@app.post("/broadcast")
async def broadcast_message(message: dict):
    """
    广播消息到所有连接的客户端

    Body:
    {
        "type": "notification",
        "data": {...}
    }
    """
    await manager.broadcast(message)
    return {"status": "ok", "recipients": len(manager.active_connections)}


@app.post("/broadcast/{channel}")
async def broadcast_to_channel(channel: str, message: dict):
    """
    广播消息到指定频道

    Body:
    {
        "type": "signal",
        "data": {...}
    }
    """
    await manager.broadcast_to_channel(channel, message)
    recipients = len(manager.subscriptions.get(channel, set()))
    return {"status": "ok", "channel": channel, "recipients": recipients}


# ==================== 后台任务 (示例) ====================

async def background_market_data_pusher():
    """
    后台任务：定期推送市场数据
    实际使用时从数据源获取最新数据
    """
    while True:
        try:
            await asyncio.sleep(5)  # 每5秒推送一次

            # 示例：推送市场数据到 market_data 频道
            market_message = {
                "type": "market_update",
                "data": {
                    "timestamp": "2026-06-29T12:00:00",
                    "indices": {
                        "000001.SH": 3200.00,
                        "399001.SZ": 11000.00
                    }
                }
            }
            await manager.broadcast_to_channel("market_data", market_message)

        except Exception as e:
            logger.error(f"Background task error: {e}")
            await asyncio.sleep(10)


@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("🚀 WebSocket server starting...")
    logger.info("📡 WebSocket endpoint: ws://localhost:5003/ws")

    # 启动后台任务（可选）
    # asyncio.create_task(background_market_data_pusher())


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info("👋 WebSocket server shutting down...")

    # 关闭所有连接
    for connection in list(manager.active_connections):
        try:
            await connection.close()
        except Exception:
            pass


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    import os

    host = os.environ.get('QUANTSYS_API_HOST', '127.0.0.1')
    port = int(os.environ.get('QUANTSYS_WS_PORT', '5003'))

    logger.info(f"Starting WebSocket server on {host}:{port}")

    uvicorn.run(
        "websocket_server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )
