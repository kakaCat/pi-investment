"""成交回调端口（交易包中立侧）单测 —— REQ-261021194640-69b8 IF-1 / IF-2，卡 t-c6c5d2

本文件是「中立成交端口 + 旧路径转发」这张卡的验收锚点，四条判据各一组：

  1. **端口存在且中立**：`qs_trading.application.ports.fill_listener` 可独立 import，
     不 import 任何消费方（不感知 qs_watch / 宿主）；
  2. **注册 / 注销生效**：注册后读得到，注销后归 None；非法监听者拒绝注册；
  3. **旧 import 等价**：`application.trading.paper_trading_engine` 里的同名符号
     与端口侧是**同一对象**（不是复制品），且两侧共享同一个注册位；
  4. **`notify_fill` 语义**：未注册返回 False 且不抛错；有监听者返回 True 并收到
     一条 FillEvent；监听者抛错时仍返回 False 且**不向上抛**。

全部不连库、不起进程：只碰端口与模块级注册位。
"""
from datetime import datetime

import pytest

from qs_trading.application.ports.fill_listener import (
    FillEvent,
    IFillListener,
    get_fill_listener,
    notify_fill,
    register_fill_listener,
    unregister_fill_listener,
)
import qs_trading.application.ports.fill_listener as port
import application.trading.paper_trading_engine as legacy

ACCOUNT = 'agent_virtual'
SYMBOL = '600000.SH'


def _event(**overrides):
    base = dict(account_name=ACCOUNT, symbol=SYMBOL, action='sell', shares=1000,
                price=10.0, trade_id=1234, order_id=99,
                filled_at=datetime(2026, 10, 21, 10, 0, 0),
                source='watch_directive', reason='止损触发')
    base.update(overrides)
    return FillEvent(**base)


class Recording:
    """最小合法实现：有 on_fill 即可（结构协议，不继承）。"""

    def __init__(self):
        self.events = []

    def on_fill(self, event):
        self.events.append(event)
        return {'status': 'ok'}


class Boom:
    def on_fill(self, event):
        raise RuntimeError('watch 侧挂了')


@pytest.fixture(autouse=True)
def _clean_fill_registry():
    """模块级注册位是进程级状态：每条测试前后都清空，避免跨测试串味。"""
    unregister_fill_listener()
    yield
    unregister_fill_listener()


# ═══════════════════════════════════════════════════════════════════════════
# 判据 1：端口在交易包中立侧，事件形状与协议可用
# ═══════════════════════════════════════════════════════════════════════════

class TestPortShape:

    def test_port_lives_in_trading_package(self):
        assert port.__name__ == 'qs_trading.application.ports.fill_listener'
        assert '/packages/qs_trading/qs_trading/application/ports/' in port.__file__

    def test_port_does_not_import_consumers(self):
        """中立性：端口模块的命名空间里不得出现任何消费方（盯盘/宿主）。"""
        names = set(dir(port))
        for forbidden in ('qs_watch', 'FillSyncService', 'watch_engine', 'fastapi_app'):
            assert forbidden not in names

    def test_fill_event_fields_and_to_dict(self):
        event = _event()
        assert event.account_name == ACCOUNT
        assert event.symbol == SYMBOL
        assert event.action == 'sell'
        assert event.shares == 1000
        assert event.price == 10.0
        assert event.trade_id == 1234
        assert event.order_id == 99
        assert event.decision_audit_id is None          # 默认不虚报审计号
        assert event.source == 'watch_directive'

        projected = event.to_dict()
        assert projected['filled_at'] == '2026-10-21T10:00:00'
        assert projected['trade_id'] == 1234
        assert projected['decision_audit_id'] is None

    def test_fill_event_is_frozen(self):
        event = _event()
        with pytest.raises(Exception):
            event.symbol = 'other'                       # frozen dataclass

    def test_ifilllistener_is_runtime_checkable(self):
        assert isinstance(Recording(), IFillListener)     # 结构协议
        assert not isinstance(object(), IFillListener)    # 无 on_fill 不算


# ═══════════════════════════════════════════════════════════════════════════
# 判据 2：注册 / 注销生效
# ═══════════════════════════════════════════════════════════════════════════

class TestRegistration:

    def test_register_then_get(self):
        assert get_fill_listener() is None
        listener = Recording()
        register_fill_listener(listener)
        assert get_fill_listener() is listener

    def test_unregister_clears(self):
        register_fill_listener(Recording())
        unregister_fill_listener()
        assert get_fill_listener() is None

    def test_register_none_is_logout(self):
        register_fill_listener(Recording())
        register_fill_listener(None)
        assert get_fill_listener() is None

    def test_register_rejects_invalid_listener(self):
        class NoOnFill:
            pass

        with pytest.raises(TypeError):
            register_fill_listener(NoOnFill())
        assert get_fill_listener() is None                # 拒绝后注册位不变


# ═══════════════════════════════════════════════════════════════════════════
# 判据 3：旧 import（application.trading.paper_trading_engine）等价
# ═══════════════════════════════════════════════════════════════════════════

class TestLegacyImportEquivalence:

    @pytest.mark.parametrize('name', [
        'FillEvent', 'IFillListener',
        'register_fill_listener', 'get_fill_listener', 'unregister_fill_listener',
    ])
    def test_legacy_name_is_same_object(self, name):
        assert getattr(legacy, name) is getattr(port, name)

    def test_legacy_and_port_share_one_registry(self):
        listener = Recording()
        legacy.register_fill_listener(listener)           # 旧路径注册
        assert port.get_fill_listener() is listener       # 新路径读得到
        port.unregister_fill_listener()                   # 新路径注销
        assert legacy.get_fill_listener() is None         # 旧路径也归 None

    def test_notify_fill_uses_shared_registry(self):
        listener = Recording()
        register_fill_listener(listener)
        assert notify_fill(_event()) is True
        assert len(listener.events) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 判据 4：notify_fill 语义（未注册 False / 消费 True / 异常吞掉）
# ═══════════════════════════════════════════════════════════════════════════

class TestNotifyFill:

    def test_unregistered_returns_false_without_raising(self):
        assert get_fill_listener() is None
        assert notify_fill(_event()) is False             # 不抛错、静默 no-op

    def test_registered_returns_true_and_delivers_event(self):
        listener = Recording()
        register_fill_listener(listener)
        event = _event()
        assert notify_fill(event) is True
        assert listener.events == [event]                 # 同一条事实对象

    def test_listener_exception_is_swallowed(self):
        register_fill_listener(Boom())
        assert notify_fill(_event()) is False             # 抛错被吞，返回 False

    def test_explicit_listener_overrides_registry(self):
        """实例级监听器优先（引擎按实例注入时用），且不污染模块级注册位。"""
        registered, explicit = Recording(), Recording()
        register_fill_listener(registered)
        assert notify_fill(_event(), listener=explicit) is True
        assert len(explicit.events) == 1
        assert registered.events == []                   # 注册位那条没被调用

    def test_explicit_listener_none_falls_back_to_registry(self):
        listener = Recording()
        register_fill_listener(listener)
        assert notify_fill(_event(), listener=None) is True
        assert len(listener.events) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 旧引擎行为等价：_notify_fill 走端口出口，且成交路径不受回调异常影响
# ═══════════════════════════════════════════════════════════════════════════

class TestEngineStillForwards:

    def test_engine_uses_global_registry_when_no_instance_listener(self):
        """引擎未注入实例监听器时，走模块级注册位（改造前口径）。"""
        listener = Recording()
        register_fill_listener(listener)

        engine = legacy.PaperTradingEngine.__new__(legacy.PaperTradingEngine)
        engine.account_name = ACCOUNT
        engine._fill_listener = None
        signal = type('S', (), {'symbol': '600000', 'strategy_name': 'rotation',
                                'reason': '动量突破'})()

        engine._notify_fill(signal=signal, action='BUY', shares=2000,
                            filled_price=9.9, trade_id=777)

        assert len(listener.events) == 1
        event = listener.events[0]
        assert isinstance(event, FillEvent)
        assert event.trade_id == 777
        assert event.action == 'buy'                      # 统一小写
        assert event.shares == 2000
        assert event.source == 'rotation'

    def test_engine_skips_callback_when_trade_not_persisted(self):
        """trade_id=None（未落库）→ 一条事件都不发，绝不虚报成交。"""
        listener = Recording()
        register_fill_listener(listener)

        engine = legacy.PaperTradingEngine.__new__(legacy.PaperTradingEngine)
        engine.account_name = ACCOUNT
        engine._fill_listener = None
        signal = type('S', (), {'symbol': '600000', 'strategy_name': 'rotation',
                                'reason': None})()

        engine._notify_fill(signal=signal, action='buy', shares=100,
                            filled_price=10.0, trade_id=None)
        assert listener.events == []

    def test_engine_callback_exception_does_not_propagate(self):
        """监听者抛错不得穿到成交路径（成交已提交）。"""
        register_fill_listener(Boom())

        engine = legacy.PaperTradingEngine.__new__(legacy.PaperTradingEngine)
        engine.account_name = ACCOUNT
        engine._fill_listener = None
        signal = type('S', (), {'symbol': '600000', 'strategy_name': 'rotation',
                                'reason': None})()

        engine._notify_fill(signal=signal, action='sell', shares=100,
                            filled_price=10.0, trade_id=1)   # 不抛错即通过
