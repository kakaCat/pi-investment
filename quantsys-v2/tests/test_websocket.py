"""
WebSocket和事件驱动系统测试
"""
import pytest
from flask import Flask
from flask_socketio import SocketIO, SocketIOTestClient
from infrastructure.events.event_bus import EventBus
from adapters.inbound.api.websocket import ConnectionManager, init_connection_manager
from datetime import datetime


class TestEventBus:
    """事件总线测试"""

    def test_subscribe_and_publish_sync(self):
        """测试同步订阅和发布"""
        bus = EventBus()
        received = []

        def handler(data):
            received.append(data)

        bus.subscribe("test_event", handler)
        bus.publish_sync("test_event", {"value": 123})

        assert len(received) == 1
        assert received[0]["value"] == 123

    def test_multiple_subscribers(self):
        """测试多个订阅者"""
        bus = EventBus()
        received1 = []
        received2 = []

        def handler1(data):
            received1.append(data)

        def handler2(data):
            received2.append(data)

        bus.subscribe("test_event", handler1)
        bus.subscribe("test_event", handler2)
        bus.publish_sync("test_event", {"value": 456})

        assert len(received1) == 1
        assert len(received2) == 1
        assert received1[0]["value"] == 456
        assert received2[0]["value"] == 456

    def test_unsubscribe(self):
        """测试取消订阅"""
        bus = EventBus()
        received = []

        def handler(data):
            received.append(data)

        bus.subscribe("test_event", handler)
        bus.publish_sync("test_event", {"value": 1})
        bus.unsubscribe("test_event", handler)
        bus.publish_sync("test_event", {"value": 2})

        assert len(received) == 1
        assert received[0]["value"] == 1

    def test_event_history(self):
        """测试事件历史"""
        bus = EventBus()
        bus.publish_sync("event1", {"data": "a"})
        bus.publish_sync("event2", {"data": "b"})
        bus.publish_sync("event1", {"data": "c"})

        all_history = bus.get_history()
        assert len(all_history) == 3

        event1_history = bus.get_history(event_type="event1")
        assert len(event1_history) == 2
        assert event1_history[0]["data"]["data"] == "a"
        assert event1_history[1]["data"]["data"] == "c"

    def test_get_subscriber_count(self):
        """测试获取订阅者数量"""
        bus = EventBus()

        def handler1(data):
            pass

        def handler2(data):
            pass

        bus.subscribe("event1", handler1)
        bus.subscribe("event1", handler2)
        bus.subscribe("event2", handler1)

        assert bus.get_subscriber_count("event1") == 2
        assert bus.get_subscriber_count("event2") == 1
        assert bus.get_subscriber_count() == 3

    def test_clear_history(self):
        """测试清空历史"""
        bus = EventBus()
        bus.publish_sync("test", {"data": 1})
        bus.publish_sync("test", {"data": 2})

        assert len(bus.get_history()) == 2

        bus.clear_history()
        assert len(bus.get_history()) == 0


class TestConnectionManager:
    """连接管理器测试"""

    @pytest.fixture
    def app(self):
        """创建测试Flask应用"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'
        return app

    @pytest.fixture
    def socketio(self, app):
        """创建测试SocketIO实例"""
        return SocketIO(app, async_mode='threading')

    @pytest.fixture
    def manager(self, socketio):
        """创建测试连接管理器"""
        return init_connection_manager(socketio)

    def test_connect_and_disconnect(self, manager):
        """测试连接和断开"""
        session_id = "test_session_1"
        symbol = "000001.SZ"

        # 连接
        manager.connect(session_id, symbol)
        assert manager.get_connection_count(symbol) == 1
        assert symbol in manager.get_subscribed_symbols(session_id)

        # 断开
        manager.disconnect(session_id, symbol)
        assert manager.get_connection_count(symbol) == 0
        assert symbol not in manager.get_subscribed_symbols(session_id)

    def test_multiple_connections(self, manager):
        """测试多个连接"""
        manager.connect("session1", "000001.SZ")
        manager.connect("session2", "000001.SZ")
        manager.connect("session3", "000002.SZ")

        assert manager.get_connection_count("000001.SZ") == 2
        assert manager.get_connection_count("000002.SZ") == 1
        assert manager.get_connection_count() == 3

    def test_disconnect_all(self, manager):
        """测试断开所有订阅"""
        session_id = "test_session"
        manager.connect(session_id, "000001.SZ")
        manager.connect(session_id, "000002.SZ")

        assert len(manager.get_subscribed_symbols(session_id)) == 2

        manager.disconnect(session_id)
        assert len(manager.get_subscribed_symbols(session_id)) == 0

    def test_get_subscribed_symbols(self, manager):
        """测试获取订阅列表"""
        session_id = "test_session"
        manager.connect(session_id, "000001.SZ")
        manager.connect(session_id, "000002.SZ")
        manager.connect(session_id, "600000.SH")

        symbols = manager.get_subscribed_symbols(session_id)
        assert len(symbols) == 3
        assert "000001.SZ" in symbols
        assert "000002.SZ" in symbols
        assert "600000.SH" in symbols


class TestWebSocketIntegration:
    """WebSocket集成测试"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        from adapters.inbound.api.server_websocket import app, socketio
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def socketio(self, app):
        """获取SocketIO实例"""
        from adapters.inbound.api.server_websocket import socketio
        return socketio

    @pytest.fixture
    def client(self, app, socketio):
        """创建测试客户端"""
        return socketio.test_client(app)

    def test_connect(self, client):
        """测试WebSocket连接"""
        assert client.is_connected()
        received = client.get_received()
        assert len(received) > 0
        assert received[0]['name'] == 'connected'

    def test_subscribe(self, client):
        """测试订阅"""
        client.emit('subscribe', {'symbol': '000001.SZ'})
        received = client.get_received()

        # 找到subscribed消息
        subscribed_msg = None
        for msg in received:
            if msg['name'] == 'subscribed':
                subscribed_msg = msg
                break

        assert subscribed_msg is not None
        assert subscribed_msg['args'][0]['symbol'] == '000001.SZ'

    def test_unsubscribe(self, client):
        """测试取消订阅"""
        # 先订阅
        client.emit('subscribe', {'symbol': '000001.SZ'})
        client.get_received()  # 清空接收队列

        # 再取消订阅
        client.emit('unsubscribe', {'symbol': '000001.SZ'})
        received = client.get_received()

        unsubscribed_msg = None
        for msg in received:
            if msg['name'] == 'unsubscribed':
                unsubscribed_msg = msg
                break

        assert unsubscribed_msg is not None
        assert unsubscribed_msg['args'][0]['symbol'] == '000001.SZ'

    def test_ping_pong(self, client):
        """测试心跳"""
        client.emit('ping')
        received = client.get_received()

        pong_msg = None
        for msg in received:
            if msg['name'] == 'pong':
                pong_msg = msg
                break

        assert pong_msg is not None
        assert 'timestamp' in pong_msg['args'][0]

    def test_get_subscriptions(self, client):
        """测试获取订阅列表"""
        # 订阅多个股票
        client.emit('subscribe', {'symbol': '000001.SZ'})
        client.emit('subscribe', {'symbol': '000002.SZ'})
        client.get_received()  # 清空接收队列

        # 获取订阅列表
        client.emit('get_subscriptions')
        received = client.get_received()

        subscriptions_msg = None
        for msg in received:
            if msg['name'] == 'subscriptions':
                subscriptions_msg = msg
                break

        assert subscriptions_msg is not None
        symbols = subscriptions_msg['args'][0]['symbols']
        assert len(symbols) == 2
        assert '000001.SZ' in symbols
        assert '000002.SZ' in symbols


class TestEventHandlers:
    """事件处理器测试"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        from adapters.inbound.api.server_websocket import app
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def socketio(self):
        """获取SocketIO实例"""
        from adapters.inbound.api.server_websocket import socketio
        return socketio

    @pytest.fixture
    def client(self, app, socketio):
        """创建测试客户端"""
        return socketio.test_client(app)

    def test_quote_update_event(self, client):
        """测试行情更新事件"""
        from infrastructure.events.event_bus import event_bus

        # 订阅股票
        client.emit('subscribe', {'symbol': '000001.SZ'})
        client.get_received()  # 清空接收队列

        # 发布行情更新事件
        event_bus.publish_sync('quote_update', {
            'symbol': '000001.SZ',
            'price': 10.5,
            'volume': 1000000,
            'timestamp': datetime.now().isoformat()
        })

        # 检查是否收到消息
        received = client.get_received()
        quote_msg = None
        for msg in received:
            if msg['name'] == 'message' and msg['args'][0].get('type') == 'quote':
                quote_msg = msg
                break

        assert quote_msg is not None
        assert quote_msg['args'][0]['symbol'] == '000001.SZ'
        assert quote_msg['args'][0]['price'] == 10.5

    def test_signal_generated_event(self, client):
        """测试信号生成事件"""
        from infrastructure.events.event_bus import event_bus

        # 订阅股票
        client.emit('subscribe', {'symbol': '000001.SZ'})
        client.get_received()

        # 发布信号生成事件
        event_bus.publish_sync('signal_generated', {
            'symbol': '000001.SZ',
            'signal': 'buy',
            'strategy': 'test_strategy',
            'confidence': 0.85,
            'timestamp': datetime.now().isoformat()
        })

        # 检查是否收到消息
        received = client.get_received()
        signal_msg = None
        for msg in received:
            if msg['name'] == 'message' and msg['args'][0].get('type') == 'signal':
                signal_msg = msg
                break

        assert signal_msg is not None
        assert signal_msg['args'][0]['symbol'] == '000001.SZ'
        assert signal_msg['args'][0]['signal'] == 'buy'
        assert signal_msg['args'][0]['confidence'] == 0.85


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
