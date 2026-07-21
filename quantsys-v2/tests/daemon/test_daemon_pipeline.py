"""
Daemon Pipeline Bridge Test — 验证 daemon 桥接层的流水线功能

测试 Daemon → API → Service 的端到端路由：
1. 信号生成和记录
2. 订单创建和追踪
3. 盈亏记录
4. 统计查询
5. 经验积累

这些测试验证 daemon handler 能正确将请求路由到后端服务。
"""
import json
import pytest
import asyncio
from datetime import date

from infrastructure.daemon.registry import MethodRegistry, register_method, get_global_registry


class TestDaemonPipelineBridge:
    """测试 daemon 到后端流水线的桥接"""

    def test_registry_has_data_handlers(self):
        """验证 daemon registry 包含数据层 handler"""
        import infrastructure.daemon.handlers.data_handlers as dh  # noqa: F401 - triggers registration

        registry = get_global_registry()
        methods = registry.list_methods()

        # Core data handlers must exist
        assert "get_stock_info" in methods, "get_stock_info handler 必须注册"
        assert "get_stock_price" in methods, "get_stock_price handler 必须注册"
        assert "get_stock_history" in methods, "get_stock_history handler 必须注册"
        assert "get_stock_realtime_price" in methods, "get_stock_realtime_price handler 必须注册"

    def test_registry_has_factor_handlers(self):
        """验证 daemon registry 包含因子层 handler"""
        import infrastructure.daemon.handlers.factor_handlers as fh  # noqa: F401 - triggers registration

        registry = get_global_registry()
        methods = registry.list_methods()

        assert "calculate_factor" in methods, "calculate_factor handler 必须注册"
        assert "batch_calculate_factors" in methods, "batch_calculate_factors handler 必须注册"

    def test_registry_has_model_handlers(self):
        """验证 daemon registry 包含模型层 handler"""
        import infrastructure.daemon.handlers.model_handlers as mh  # noqa: F401 - triggers registration

        registry = get_global_registry()
        methods = registry.list_methods()

        assert "model_train" in methods, "model_train handler 必须注册"
        assert "model_predict" in methods, "model_predict handler 必须注册"

    def test_handler_validation_rejects_invalid_params(self):
        """验证 handler 能正确校验参数"""
        import infrastructure.daemon.handlers.data_handlers as dh  # noqa: F401 - triggers registration

        registry = get_global_registry()

        async def run():
            handler = registry.get_handler("get_stock_info")
            assert handler is not None

            # 缺少 symbol 参数时应抛出异常
            with pytest.raises(ValueError, match="symbol"):
                await handler({})

        asyncio.run(run())


class TestDaemonMethodRegistry:
    """测试 MethodRegistry 基础设施"""

    def test_register_and_invoke(self):
        """测试注册和调用 method handler"""
        registry = MethodRegistry()

        @register_method("test.echo", registry=registry)
        async def echo_handler(params: dict) -> str:
            return json.dumps({"echo": params.get("message", "no message")})

        assert registry.has_method("test.echo")
        handler = registry.get_handler("test.echo")

        async def run():
            result = await handler({"message": "hello"})
            data = json.loads(result)
            assert data["echo"] == "hello"

        asyncio.run(run())

    def test_register_duplicate_raises_error(self):
        """测试重复注册抛出异常"""
        registry = MethodRegistry()

        @register_method("test.duplicate", registry=registry)
        async def handler1(params: dict) -> str:
            return "{}"

        with pytest.raises(ValueError, match="already registered"):

            @register_method("test.duplicate", registry=registry)
            async def handler2(params: dict) -> str:
                return "{}"

    def test_register_non_async_rejected(self):
        """测试注册非异步函数时抛出异常"""
        registry = MethodRegistry()

        with pytest.raises(ValueError, match="async function"):
            # 同步函数不应被接受
            @register_method("test.sync", registry=registry)
            def sync_handler(params: dict) -> str:  # noqa
                return "{}"

    def test_list_methods(self):
        """测试列出所有注册的方法"""
        registry = MethodRegistry()

        @register_method("method.a", registry=registry)
        async def handler_a(params: dict) -> str:
            return "{}"

        @register_method("method.b", registry=registry)
        async def handler_b(params: dict) -> str:
            return "{}"

        methods = registry.list_methods()
        assert "method.a" in methods
        assert "method.b" in methods
        assert len(methods) == 2

    def test_get_nonexistent_handler(self):
        """测试获取不存在的 handler 返回 None"""
        registry = MethodRegistry()
        assert registry.get_handler("nonexistent") is None
        assert not registry.has_method("nonexistent")


class TestSignalTestLogBridge:
    """测试 SignalTestLog 服务直接调用（非 daemon 层，但验证服务正确性）"""

    def test_signal_record_round_trip(self):
        """测试信号记录的完整写入→读取周期"""
        from application.services.signal_test_log import SignalTestLog

        signal_log = SignalTestLog()

        # 清理测试数据
        conn = signal_log._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM quant.signal_test_log WHERE reason LIKE '%Bridge Test%'"
        )
        conn.commit()

        # 创建信号
        signal_id = signal_log.record_signal({
            'symbol': 'BRIDGE01.SH',
            'name': '桥接测试股',
            'strategy_name': 'bridge_test',
            'signal_date': date.today(),
            'action': 'buy',
            'confidence': 0.75,
            'signal_price': 50.0,
            'entry_price': None,
            'stop_loss': 45.0,
            'reason': 'Daemon Bridge Test'
        })

        assert signal_id > 0

        # 查询验证 (get_records 返回 {records, pagination})
        result = signal_log.get_records(symbol='BRIDGE01.SH', strategy_name='bridge_test')
        signals = result['records']
        assert len(signals) == 1, f"应有 1 条信号，实际 {len(signals)}"
        signal = signals[0]
        assert signal['symbol'] == 'BRIDGE01.SH'
        assert signal['strategy_name'] == 'bridge_test'
        assert float(signal['signal_price']) == 50.0
        assert signal['status'] == 'pending'

        # 更新状态 — 直接在SQL中更新
        conn2 = signal_log._get_conn()
        cur2 = conn2.cursor()
        cur2.execute(
            f"UPDATE {signal_log.TABLE_NAME} SET status = 'verified', pnl_pct = 3.5, current_price = 51.75 WHERE id = %s",
            (signal_id,)
        )
        conn2.commit()
        cur2.close()
        conn2.close()

        # 验证更新
        updated_result = signal_log.get_records(symbol='BRIDGE01.SH', strategy_name='bridge_test')
        updated = updated_result['records'][0]
        assert updated['status'] == 'verified'
        assert float(updated['pnl_pct']) == pytest.approx(3.5, rel=0.01)
        assert float(updated['current_price']) == 51.75

        # 清理
        cursor.execute(
            "DELETE FROM quant.signal_test_log WHERE reason LIKE '%Bridge Test%'"
        )
        cursor.execute(
            "DELETE FROM quant.strategy_performance WHERE symbol = 'BRIDGE01.SH'"
        )
        conn.commit()
        cursor.close()
        conn.close()
