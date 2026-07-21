"""
WebSocket服务器 - 集成Flask-SocketIO和事件驱动架构

使用方法:
    from adapters.inbound.api.server_websocket import app, socketio
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
"""
import logging
import os
from flask import Flask, request
from flask_socketio import SocketIO, emit, disconnect
from flask_cors import CORS

from adapters.inbound.api.websocket import init_connection_manager, get_connection_manager
from infrastructure.events.event_bus import event_bus
from infrastructure.events import handlers  # 导入以注册处理器

logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'quantsys-v2-secret-key'
CORS(app, resources={r"/*": {"origins": "*"}})

# 初始化SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=False
)

# 初始化连接管理器
init_connection_manager(socketio)


# ==================== WebSocket事件处理 ====================

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    session_id = request.sid
    logger.info(f"客户端连接: session_id={session_id}")
    emit('connected', {
        'session_id': session_id,
        'message': 'Connected to QuantSys V2 WebSocket server',
        'timestamp': handlers.datetime.now().isoformat()
    })


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开连接"""
    session_id = request.sid
    logger.info(f"客户端断开: session_id={session_id}")

    try:
        manager = get_connection_manager()
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"断开连接处理失败: {e}")


@socketio.on('subscribe')
def handle_subscribe(data):
    """
    订阅股票行情

    Args:
        data: {"symbol": "000001.SZ"}
    """
    session_id = request.sid
    symbol = data.get('symbol')

    if not symbol:
        emit('error', {'message': 'Missing symbol parameter'})
        return

    try:
        manager = get_connection_manager()
        manager.connect(session_id, symbol)

        emit('subscribed', {
            'symbol': symbol,
            'message': f'Subscribed to {symbol}',
            'timestamp': handlers.datetime.now().isoformat()
        })

        logger.info(f"订阅成功: session={session_id}, symbol={symbol}")
    except Exception as e:
        logger.error(f"订阅失败: {e}")
        emit('error', {'message': f'Subscription failed: {str(e)}'})


@socketio.on('unsubscribe')
def handle_unsubscribe(data):
    """
    取消订阅股票行情

    Args:
        data: {"symbol": "000001.SZ"}
    """
    session_id = request.sid
    symbol = data.get('symbol')

    if not symbol:
        emit('error', {'message': 'Missing symbol parameter'})
        return

    try:
        manager = get_connection_manager()
        manager.disconnect(session_id, symbol)

        emit('unsubscribed', {
            'symbol': symbol,
            'message': f'Unsubscribed from {symbol}',
            'timestamp': handlers.datetime.now().isoformat()
        })

        logger.info(f"取消订阅: session={session_id}, symbol={symbol}")
    except Exception as e:
        logger.error(f"取消订阅失败: {e}")
        emit('error', {'message': f'Unsubscription failed: {str(e)}'})


@socketio.on('ping')
def handle_ping():
    """心跳检测"""
    emit('pong', {'timestamp': handlers.datetime.now().isoformat()})


@socketio.on('get_subscriptions')
def handle_get_subscriptions():
    """获取当前订阅列表"""
    session_id = request.sid

    try:
        manager = get_connection_manager()
        symbols = manager.get_subscribed_symbols(session_id)

        emit('subscriptions', {
            'symbols': list(symbols),
            'count': len(symbols),
            'timestamp': handlers.datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取订阅列表失败: {e}")
        emit('error', {'message': f'Failed to get subscriptions: {str(e)}'})


# ==================== HTTP API端点（用于测试） ====================

@app.route('/api/ws/health', methods=['GET'])
def ws_health():
    """WebSocket服务健康检查"""
    try:
        manager = get_connection_manager()
        return {
            'status': 'ok',
            'websocket': 'enabled',
            'total_connections': manager.get_connection_count(),
            'event_bus_subscribers': event_bus.get_subscriber_count()
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}, 500


@app.route('/api/ws/stats', methods=['GET'])
def ws_stats():
    """WebSocket连接统计"""
    try:
        manager = get_connection_manager()
        return {
            'total_connections': manager.get_connection_count(),
            'symbols': {
                symbol: manager.get_connection_count(symbol)
                for symbol in manager.active_connections.keys()
            },
            'event_history_count': len(event_bus.event_history)
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}, 500


@app.route('/api/ws/test/publish_quote', methods=['POST'])
def test_publish_quote():
    """测试端点：手动触发行情更新事件"""
    from flask import request as flask_request
    data = flask_request.get_json() or {}

    symbol = data.get('symbol')
    price = data.get('price')

    if not symbol or price is None:
        return {'error': 'Missing symbol or price'}, 400

    try:
        event_bus.publish('quote_update', {
            'symbol': symbol,
            'price': float(price),
            'volume': data.get('volume', 1000000),
            'change': data.get('change', 0),
            'change_pct': data.get('change_pct', 0),
            'timestamp': handlers.datetime.now().isoformat()
        })
        return {'status': 'ok', 'message': f'Quote update published for {symbol}'}
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/api/ws/test/publish_signal', methods=['POST'])
def test_publish_signal():
    """测试端点：手动触发信号生成事件"""
    from flask import request as flask_request
    data = flask_request.get_json() or {}

    symbol = data.get('symbol')
    signal = data.get('signal')

    if not symbol or not signal:
        return {'error': 'Missing symbol or signal'}, 400

    try:
        event_bus.publish('signal_generated', {
            'symbol': symbol,
            'signal': signal,
            'strategy': data.get('strategy', 'test_strategy'),
            'confidence': data.get('confidence', 0.75),
            'price': data.get('price'),
            'reason': data.get('reason', 'Test signal'),
            'timestamp': handlers.datetime.now().isoformat()
        })
        return {'status': 'ok', 'message': f'Signal published for {symbol}'}
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/api/ws/test/publish_risk', methods=['POST'])
def test_publish_risk():
    """测试端点：手动触发风险告警事件"""
    from flask import request as flask_request
    data = flask_request.get_json() or {}

    symbol = data.get('symbol')
    risk_type = data.get('risk_type', 'concentration')

    if not symbol:
        return {'error': 'Missing symbol'}, 400

    try:
        event_bus.publish('risk_alert', {
            'symbol': symbol,
            'risk_type': risk_type,
            'level': data.get('level', 'medium'),
            'message': data.get('message', f'Risk alert for {symbol}'),
            'value': data.get('value'),
            'threshold': data.get('threshold'),
            'timestamp': handlers.datetime.now().isoformat()
        })
        return {'status': 'ok', 'message': f'Risk alert published for {symbol}'}
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/api/events/history', methods=['GET'])
def get_event_history():
    """获取事件历史"""
    from flask import request as flask_request
    event_type = flask_request.args.get('event_type')
    limit = flask_request.args.get('limit', 100, type=int)

    try:
        history = event_bus.get_history(event_type=event_type, limit=limit)
        return {
            'events': history,
            'count': len(history),
            'event_type': event_type
        }
    except Exception as e:
        return {'error': str(e)}, 500


if __name__ == '__main__':
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 启动服务器
    logger.info("启动QuantSys V2 WebSocket服务器...")
    socketio.run(
        app,
        host=os.environ.get('QUANTSYS_API_HOST', '127.0.0.1'),
        port=int(os.environ.get('QUANTSYS_WS_PORT', '5003')),
        debug=True,
    )
