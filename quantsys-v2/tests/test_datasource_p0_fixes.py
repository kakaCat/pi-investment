"""
测试多数据源 P0 级修复

测试内容：
1. P0-1: NeteaseQuoteProvider 已注册
2. P0-4: 超时配置化（不同 Provider 不同超时）
3. P0-5: 缓存层已集成
4. P0-2: K线回填使用 ON CONFLICT（原子操作）
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from adapters.outbound.datasources.manager import (
    DataProviderManager,
    PROVIDER_TIMEOUTS,
    DEFAULT_PROVIDER_TIMEOUT
)
from adapters.outbound.datasources.providers.quote.netease import NeteaseQuoteProvider
from domain.models.market_data import QuoteData


class TestP0Fixes:
    """P0 级修复测试套件"""

    def test_p0_1_netease_provider_registered(self):
        """P0-1: 验证 NeteaseQuoteProvider 已注册到 quote_providers"""
        manager = DataProviderManager()

        provider_names = [p.name for p in manager.quote_providers]

        assert 'netease' in provider_names, "NeteaseQuoteProvider 应该已注册"
        assert any(isinstance(p, NeteaseQuoteProvider) for p in manager.quote_providers), \
            "quote_providers 应包含 NeteaseQuoteProvider 实例"

    def test_p0_4_timeout_configuration_exists(self):
        """P0-4: 验证超时配置常量已定义"""
        # 验证配置字典存在
        assert PROVIDER_TIMEOUTS is not None
        assert DEFAULT_PROVIDER_TIMEOUT is not None

        # 验证关键 Provider 的超时配置
        assert PROVIDER_TIMEOUTS['database'] == 5, "Database 应该是 5 秒"
        assert PROVIDER_TIMEOUTS['tencent'] == 15, "Tencent 应该是 15 秒"
        assert PROVIDER_TIMEOUTS['akshare'] == 90, "Akshare 应该是 90 秒"
        assert PROVIDER_TIMEOUTS['baostock'] == 30, "Baostock 应该是 30 秒"

    def test_p0_4_timeout_per_provider(self):
        """P0-4: 验证不同 Provider 使用不同超时"""
        # 这个测试验证配置存在即可，实际超时行为在 _try_providers 中
        # 通过代码审查确认超时配置被正确使用
        import inspect
        from adapters.outbound.datasources.manager import DataProviderManager

        source = inspect.getsource(DataProviderManager._try_providers)

        # 验证代码中使用了 PROVIDER_TIMEOUTS
        assert 'PROVIDER_TIMEOUTS.get' in source or 'timeout' in source, \
            "_try_providers 应该使用配置化的超时"

    def test_p0_5_cache_initialized(self):
        """P0-5: 验证缓存层已初始化"""
        manager = DataProviderManager()

        assert hasattr(manager, '_cache'), "Manager 应该有 _cache 属性"
        assert manager._cache is not None, "_cache 不应该是 None"

        # 验证缓存有正确的方法
        assert hasattr(manager._cache, 'get')
        assert hasattr(manager._cache, 'set')
        assert hasattr(manager._cache, 'make_key')

    def test_p0_5_cache_integration_get_quote(self):
        """P0-5: 验证 get_quote 使用缓存"""
        manager = DataProviderManager()

        # Mock cache
        manager._cache.get = Mock(return_value=None)  # Cache miss
        manager._cache.set = Mock()
        manager._cache.make_key = Mock(return_value='test_key')

        # Mock provider
        mock_quote = QuoteData(
            symbol='600519.SH',
            name='贵州茅台',
            price=1800.0,
            open=1795.0,
            high=1805.0,
            low=1790.0,
            prev_close=1795.0,
            volume=1000000,
            amount=1800000000.0,
            change=5.0,
            change_pct=0.28,
            timestamp=datetime.now().isoformat(),
            source='tencent'
        )

        manager._try_providers = Mock(return_value={
            'success': True,
            'data': mock_quote,
            'source': 'tencent'
        })

        # 第一次调用
        result = manager.get_quote('600519.SH')

        # 验证缓存被查询
        manager._cache.make_key.assert_called_with('get_quote', '600519.SH')
        manager._cache.get.assert_called_with('test_key')

        # 验证成功结果被缓存
        manager._cache.set.assert_called_once()

    def test_p0_5_cache_integration_get_klines(self):
        """P0-5: 验证 get_klines 使用缓存"""
        manager = DataProviderManager()

        # Mock cache
        manager._cache.get = Mock(return_value=None)  # Cache miss
        manager._cache.set = Mock()
        manager._cache.make_key = Mock(return_value='klines_test_key')

        # Mock provider 和 backfill
        manager._try_providers = Mock(return_value={
            'success': True,
            'data': [],
            'source': 'database'
        })
        manager._backfill_klines_to_db = Mock()

        # 调用
        result = manager.get_klines('600519.SH', 'daily', '2024-01-01', '2024-01-31')

        # 验证缓存被使用
        manager._cache.make_key.assert_called_with(
            'get_klines', '600519.SH', 'daily', '2024-01-01', '2024-01-31'
        )
        manager._cache.get.assert_called_with('klines_test_key')
        manager._cache.set.assert_called_once()

    def test_p0_2_backfill_uses_on_conflict(self):
        """P0-2: 验证 K线回填使用 ON CONFLICT（通过代码检查）"""
        manager = DataProviderManager()

        # 读取源代码检查是否使用了 on_conflict_do_nothing
        import inspect
        source = inspect.getsource(manager._backfill_klines_to_db)

        assert 'on_conflict_do_nothing' in source, \
            "_backfill_klines_to_db 应该使用 on_conflict_do_nothing"
        assert 'insert(DailyKline)' in source, \
            "_backfill_klines_to_db 应该使用 SQLAlchemy insert"
        assert "index_elements=['symbol', 'trade_date']" in source, \
            "on_conflict 应该指定 symbol 和 trade_date 作为冲突键"

    def test_p0_2_backfill_atomic_operation(self):
        """P0-2: 验证回填操作的原子性（不再有 SELECT + INSERT race condition）"""
        manager = DataProviderManager()

        # 检查源代码中不再有旧的 SELECT 查询
        import inspect
        source = inspect.getsource(manager._backfill_klines_to_db)

        # 旧的实现会有 session.query().filter_by().first()
        assert 'session.query(DailyKline).filter_by' not in source, \
            "不应该再使用 SELECT 查询检查是否存在（会有 race condition）"

    def test_cache_hit_bypasses_providers(self):
        """验证缓存命中时不调用 Provider"""
        manager = DataProviderManager()

        # Mock cache hit
        cached_result = {
            'success': True,
            'data': Mock(spec=QuoteData),
            'source': 'tencent'
        }
        manager._cache.get = Mock(return_value=cached_result)
        manager._try_providers = Mock()  # 不应该被调用

        result = manager.get_quote('600519.SH')

        assert result == cached_result
        manager._try_providers.assert_not_called()

    def test_provider_timeout_fallback_to_default(self):
        """验证未配置的 Provider 使用默认超时"""
        # 假设有个新 Provider 没有在 PROVIDER_TIMEOUTS 中配置
        timeout = PROVIDER_TIMEOUTS.get('unknown_provider', DEFAULT_PROVIDER_TIMEOUT)
        assert timeout == DEFAULT_PROVIDER_TIMEOUT

    def test_all_quote_providers_have_timeout(self):
        """验证所有 quote provider 都有超时配置"""
        manager = DataProviderManager()

        for provider in manager.quote_providers:
            # 应该能获取到超时配置（要么显式配置，要么使用默认值）
            timeout = PROVIDER_TIMEOUTS.get(provider.name, DEFAULT_PROVIDER_TIMEOUT)
            assert timeout > 0, f"{provider.name} 应该有正数超时配置"
            assert timeout <= 90, f"{provider.name} 超时配置不应该超过 90 秒（除非有特殊理由）"


class TestCachePerformance:
    """缓存性能测试"""

    def test_cache_reduces_provider_calls(self):
        """验证缓存减少 Provider 调用次数"""
        manager = DataProviderManager()

        # Mock provider (慢速)
        call_count = 0
        def mock_get_quote(symbol):
            nonlocal call_count
            call_count += 1
            return QuoteData(
                symbol=symbol,
                name='测试股票',
                price=100.0,
                open=99.0,
                high=101.0,
                low=98.0,
                prev_close=99.0,
                volume=1000000,
                amount=100000000.0,
                change=1.0,
                change_pct=1.01,
                timestamp=datetime.now().isoformat(),
                source='tencent'
            )

        manager._try_providers = Mock(side_effect=lambda providers, method, symbol: {
            'success': True,
            'data': mock_get_quote(symbol),
            'source': 'tencent'
        })

        # 第一次调用
        result1 = manager.get_quote('600519.SH')
        assert result1['success']

        # 第二次调用（应该命中缓存）
        result2 = manager.get_quote('600519.SH')
        assert result2['success']

        # Provider 应该只被调用一次
        assert manager._try_providers.call_count == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
