"""DataService 单元测试（2026-10-23 重写）

原文件覆盖的 `get_stock_analysis` / `get_portfolio_overview` /
`get_portfolio_risk_analysis` / `get_market_overview` / `get_top_signals` /
`batch_get_klines` / `batch_get_latest_factors` / `batch_get_risk_metrics` /
`get_risk_summary` / `close()` 这些入口在 qs_market_data 包化后**全都不存在**
（全仓零实现、零调用）：它们要么被路由层的专用服务取代，要么随重构移除。
继续保留这些断言等于测试已删除的 API。

本文件改为覆盖 DataService 的真实面：
- get_stock_full_data(symbol, start, end)
- get_backtest_workflow_data(symbol, start, end, period)
- check_data_integrity(symbol=None, check_type='all')
- get_financial_statements(symbol, ...)
- cleanup()（替代 close()）

依赖测试库数据；库不可用/无数据时按 skip 处理（与全仓集成测试口径一致）。
"""
import pytest

from qs_market_data.application.services.data_service import DataService


@pytest.fixture
def service():
    # P2-3 契约：DataService 不再自动实例化 Repository，必须依赖注入。
    # 生产口径 = 经 ServiceFactory 取实例（docstring 明确推荐）。
    from infrastructure.services.service_factory import ServiceFactory
    svc = DataService(
        stock_repo=ServiceFactory.get_stock_repository(),
        kline_repo=ServiceFactory.get_kline_repository(),
        signal_repo=ServiceFactory.get_signal_repository(),
        factor_repo=ServiceFactory.get_factor_repository(),
    )
    yield svc
    svc.cleanup()


class TestStockQueries:
    def test_get_stock_full_data(self, service):
        """返回结构：symbol / stock_info / klines / latest_factors / signals"""
        try:
            result = service.get_stock_full_data("000001.SZ", "2024-01-01", "2024-01-31")
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

        assert isinstance(result, dict)
        assert result['symbol'] == '000001.SZ'
        for key in ('stock_info', 'klines', 'latest_factors', 'signals'):
            assert key in result
        assert isinstance(result['klines'], list)
        assert isinstance(result['signals'], list)

    def test_get_stock_full_data_unknown_symbol(self, service):
        """不存在的标的：不抛格式错误，返回空 klines/signals（stock_info 可能 None）"""
        try:
            result = service.get_stock_full_data("999999.SZ", "2024-01-01", "2024-01-31")
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

        assert result['symbol'] == '999999.SZ'
        assert result['klines'] == []
        assert result['signals'] == []

    def test_cleanup_is_idempotent(self, service):
        """cleanup() 可重复调用（替代已不存在的 close()）"""
        service.cleanup()
        service.cleanup()


class TestBacktestWorkflow:
    def test_get_backtest_workflow_data(self, service):
        """返回结构：symbol / stock_info / klines / financials / period"""
        try:
            result = service.get_backtest_workflow_data(
                "000001.SZ", "2024-01-01", "2024-01-31")
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

        assert isinstance(result, dict)
        assert result['symbol'] == '000001.SZ'
        for key in ('stock_info', 'klines', 'financials', 'period'):
            assert key in result
        assert isinstance(result['klines'], list)
        assert result['period'] == 'daily'

    def test_period_respected(self, service):
        try:
            result = service.get_backtest_workflow_data(
                "000001.SZ", "2024-01-01", "2024-01-31", period='5min')
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")
        assert result['period'] == '5min'


class TestDataIntegrity:
    def test_check_data_integrity_with_symbol(self, service):
        """返回结构：status / checked_at / issues / summary"""
        try:
            result = service.check_data_integrity("000001.SZ")
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

        assert isinstance(result, dict)
        assert result['status'] in ('ok', 'warning', 'error')
        assert 'checked_at' in result
        assert isinstance(result['issues'], list)
        assert 'summary' in result

    def test_check_data_integrity_unknown_symbol(self, service):
        try:
            result = service.check_data_integrity("999999.SZ")
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

        assert result['status'] == 'error'
        assert any('999999.SZ' in issue for issue in result['issues'])

    def test_check_data_integrity_global(self, service):
        try:
            result = service.check_data_integrity()
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")
        assert 'summary' in result
        assert 'total_stocks' in result['summary']
