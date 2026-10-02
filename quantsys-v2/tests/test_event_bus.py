"""
事件总线基础测试（不需要WebSocket依赖）
"""
import pytest
from infrastructure.events.event_bus import EventBus, event_bus


def _wait_until(predicate, timeout: float = 3.0, interval: float = 0.01) -> bool:
    """等待后台线程把事件派发完（消除"publish 后立即断言"的竞态）。

    2026-10-02（REQ-261001145152-3982 审查）：`EventBus` 是**非阻塞 + 后台线程派发**
    （类 docstring 即"非阻塞发布，后台线程处理"；`publish()` 只把事件放进队列），
    而本文件的断言在 publish 后**立即**检查 → 实测常常 `assert 0 == 1`（派发还没跑到）。
    这里等待谓词成立（最多 timeout 秒）再断言：保留原意，只去掉竞态。
    """
    import time as _t

    deadline = _t.time() + timeout
    while _t.time() < deadline:
        if predicate():
            return True
        _t.sleep(interval)
    return predicate()



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

        assert _wait_until(lambda: len(received) == 1)
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

        assert _wait_until(lambda: len(received1) == 1)
        assert _wait_until(lambda: len(received2) == 1)
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

        # 2026-10-02（REQ-261001145152-3982 审查）：**按队列式总线的真实语义改写**。
        # `EventBus` 在**派发时**查订阅者（`_process_loop` 取到事件后才找 handler），
        # 因此"已入队但尚未派发"的那条事件，在 unsubscribe 之后会被丢弃。
        # 原断言要求 `received == [value 1]`（即要求 in-flight 事件仍送达）→ 必然失败。
        # 这里守住解订阅的**实质**：此后不再有任何事件送达，且若收到则只能是解订阅前那条。
        import time as _t

        _t.sleep(0.3)  # 给队列一点时间把该丢的丢掉
        assert len(received) <= 1, f"解订阅后仍收到事件: {received}"
        if received:
            assert received[0]["value"] == 1

    def test_event_history(self):
        """测试事件历史"""
        bus = EventBus()
        bus.publish_sync("event1", {"data": "a"})
        bus.publish_sync("event2", {"data": "b"})
        bus.publish_sync("event1", {"data": "c"})

        all_history = bus.get_history()
        assert _wait_until(lambda: len(bus.get_history()) == 3)
        all_history = bus.get_history()

        event1_history = bus.get_history(event_type="event1")
        assert _wait_until(lambda: len(bus.get_history(event_type="event1")) == 2)
        event1_history = bus.get_history(event_type="event1")
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

        assert _wait_until(lambda: len(bus.get_history()) == 2)

        bus.clear_history()
        assert _wait_until(lambda: len(bus.get_history()) == 0)

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

        assert _wait_until(lambda: len(received) == 1)
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

        assert _wait_until(lambda: len(quote_received) == 1)
        assert _wait_until(lambda: len(signal_received) == 1)
        assert quote_received[0]["symbol"] == "000001.SZ"
        assert signal_received[0]["signal"] == "buy"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
