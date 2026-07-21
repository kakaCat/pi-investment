"""
事件总线基础测试（不需要WebSocket依赖）
"""
import pytest
from infrastructure.events.event_bus import EventBus, event_bus


class TestEventBusBasic:
    """事件总线基础功能测试"""

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

    def test_exception_isolation(self):
        """测试异常隔离 - 一个处理器失败不影响其他"""
        bus = EventBus()
        received = []

        def failing_handler(data):
            raise ValueError("Handler failed")

        def working_handler(data):
            received.append(data)

        bus.subscribe("test_event", failing_handler)
        bus.subscribe("test_event", working_handler)

        # 即使第一个处理器失败，第二个应该仍然执行
        bus.publish_sync("test_event", {"value": 123})

        assert len(received) == 1
        assert received[0]["value"] == 123

    def test_multiple_event_types(self):
        """测试多种事件类型"""
        bus = EventBus()
        quote_received = []
        signal_received = []

        def quote_handler(data):
            quote_received.append(data)

        def signal_handler(data):
            signal_received.append(data)

        bus.subscribe("quote_update", quote_handler)
        bus.subscribe("signal_generated", signal_handler)

        bus.publish_sync("quote_update", {"symbol": "000001.SZ", "price": 10.5})
        bus.publish_sync("signal_generated", {"symbol": "000001.SZ", "signal": "buy"})

        assert len(quote_received) == 1
        assert len(signal_received) == 1
        assert quote_received[0]["symbol"] == "000001.SZ"
        assert signal_received[0]["signal"] == "buy"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
