"""Integration tests for DataProviderManager failover logic.

Tests:
1. Provider timeout → failover to backup
2. Empty DataFrame → failover
3. All-NaN data → failover
4. All providers fail → error response
5. Circuit breaker mechanism
6. Health score dynamic adjustment
"""
import pytest
import pandas as pd
import time
from unittest.mock import MagicMock, patch
from concurrent.futures import TimeoutError as FuturesTimeoutError

from adapters.outbound.datasources.manager import DataProviderManager
from domain.models.market_data import QuoteData


class TestProviderFailover:
    """测试provider降级逻辑"""

    @pytest.fixture
    def manager(self):
        """创建DataProviderManager实例（不传入ds，避免数据库依赖）"""
        return DataProviderManager(ds=None)

    def test_timeout_triggers_failover(self, manager):
        """测试：主provider超时 → 降级到备用provider"""
        # Mock两个quote providers
        provider1 = MagicMock()
        provider1.name = "SlowProvider"
        provider1.get_quote = MagicMock(side_effect=lambda symbol: time.sleep(100))  # 模拟超时

        provider2 = MagicMock()
        provider2.name = "FastProvider"
        provider2.get_quote = MagicMock(return_value=QuoteData(
            symbol="000001",
            name="平安银行",
            price=10.5,
            source="FastProvider",
            timestamp="2024-01-01 10:00:00"
        ))

        manager.quote_providers = [provider1, provider2]
        manager._init_stats()

        # 执行查询
        result = manager.get_quote("000001")

        # 验证结果
        assert result['success'] is True
        assert result['source'] == "FastProvider"  # 降级成功
        assert result['data'].price == 10.5

    def test_empty_dataframe_triggers_failover(self, manager):
        """测试：空DataFrame → 降级到备用provider"""
        # Mock kline provider返回空DataFrame
        provider1 = MagicMock()
        provider1.name = "EmptyProvider"
        empty_df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close'])
        empty_df.source = "EmptyProvider"
        provider1.get_kline = MagicMock(return_value=empty_df)

        # Mock备用provider返回有效数据
        provider2 = MagicMock()
        provider2.name = "GoodProvider"
        good_df = pd.DataFrame({
            'date': ['2024-01-01'],
            'open': [10.0],
            'high': [11.0],
            'low': [9.5],
            'close': [10.5]
        })
        good_df.source = "GoodProvider"
        provider2.get_kline = MagicMock(return_value=good_df)

        manager.kline_providers = [provider1, provider2]
        manager._init_stats()

        # 执行查询（通过_try_providers测试）
        result = manager._try_providers(
            manager.kline_providers,
            'get_kline',
            '000001', '2024-01-01', '2024-01-31', 'daily'
        )

        # 验证结果
        assert result['success'] is True
        assert result['source'] == "GoodProvider"  # 空DataFrame被拒绝，降级成功

    def test_all_nan_triggers_failover(self, manager):
        """测试：全NaN数据 → 降级到备用provider"""
        # Mock provider返回全NaN DataFrame
        provider1 = MagicMock()
        provider1.name = "NaNProvider"
        nan_df = pd.DataFrame({
            'date': ['2024-01-01'],
            'open': [float('nan')],
            'high': [float('nan')],
            'low': [float('nan')],
            'close': [float('nan')]
        })
        nan_df.source = "NaNProvider"
        provider1.get_kline = MagicMock(return_value=nan_df)

        # Mock备用provider
        provider2 = MagicMock()
        provider2.name = "ValidProvider"
        valid_df = pd.DataFrame({
            'date': ['2024-01-01'],
            'open': [10.0],
            'high': [11.0],
            'low': [9.5],
            'close': [10.5]
        })
        valid_df.source = "ValidProvider"
        provider2.get_kline = MagicMock(return_value=valid_df)

        manager.kline_providers = [provider1, provider2]
        manager._init_stats()

        # 执行查询
        result = manager._try_providers(
            manager.kline_providers,
            'get_kline',
            '000001', '2024-01-01', '2024-01-31', 'daily'
        )

        # 验证结果
        assert result['success'] is True
        assert result['source'] == "ValidProvider"  # 全NaN被拒绝，降级成功

    def test_all_providers_fail_returns_error(self, manager):
        """测试：所有provider失败 → 返回错误信息"""
        # Mock所有providers都失败
        provider1 = MagicMock()
        provider1.name = "FailProvider1"
        provider1.get_quote = MagicMock(side_effect=Exception("Network error"))

        provider2 = MagicMock()
        provider2.name = "FailProvider2"
        provider2.get_quote = MagicMock(return_value=None)

        manager.quote_providers = [provider1, provider2]
        manager._init_stats()

        # 执行查询
        result = manager.get_quote("000001")

        # 验证结果
        assert result['success'] is False
        assert result['error'] == 'All data providers failed'
        assert 'provider_errors' in result
        assert len(result['attempted_sources']) == 2


class TestCircuitBreaker:
    """测试熔断机制"""

    @pytest.fixture
    def manager(self):
        """创建DataProviderManager实例"""
        mgr = DataProviderManager(ds=None)
        # 降低熔断阈值以便快速测试
        mgr._circuit_breaker_threshold = 3
        mgr._circuit_breaker_duration = 2  # 2秒
        return mgr

    def test_circuit_breaker_triggers_after_threshold(self, manager):
        """测试：连续失败达到阈值 → 触发熔断"""
        provider = MagicMock()
        provider.name = "UnstableProvider"
        provider.get_quote = MagicMock(side_effect=Exception("Always fail"))

        manager.quote_providers = [provider]
        manager._init_stats()

        # 连续失败3次
        for i in range(3):
            result = manager.get_quote("000001")
            assert result['success'] is False

        # 验证熔断已触发
        stats = manager.provider_stats["UnstableProvider"]
        assert stats['consecutive_failures'] == 3
        assert stats['circuit_breaker_until'] > time.time()

    def test_circuit_broken_provider_is_skipped(self, manager):
        """测试：熔断中的provider被跳过"""
        # 手动设置provider为熔断状态
        provider1 = MagicMock()
        provider1.name = "BrokenProvider"
        provider1.get_quote = MagicMock(return_value=None)

        provider2 = MagicMock()
        provider2.name = "HealthyProvider"
        provider2.get_quote = MagicMock(return_value=QuoteData(
            symbol="000001",
            name="平安银行",
            price=10.5,
            source="HealthyProvider",
            timestamp="2024-01-01 10:00:00"
        ))

        manager.quote_providers = [provider1, provider2]
        manager._init_stats()

        # 手动触发熔断
        manager.provider_stats["BrokenProvider"]['circuit_breaker_until'] = time.time() + 10

        # 执行查询
        result = manager.get_quote("000001")

        # 验证：BrokenProvider被跳过，直接使用HealthyProvider
        assert result['success'] is True
        assert result['source'] == "HealthyProvider"
        # BrokenProvider的get_quote不应被调用
        provider1.get_quote.assert_not_called()

    def test_circuit_breaker_resets_after_duration(self, manager):
        """测试：熔断窗口过后恢复尝试"""
        provider = MagicMock()
        provider.name = "RecoveredProvider"
        provider.get_quote = MagicMock(return_value=QuoteData(
            symbol="000001",
            name="平安银行",
            price=10.5,
            source="RecoveredProvider",
            timestamp="2024-01-01 10:00:00"
        ))

        manager.quote_providers = [provider]
        manager._init_stats()

        # 设置熔断（但时间已过期）
        manager.provider_stats["RecoveredProvider"]['circuit_breaker_until'] = time.time() - 1

        # 执行查询
        result = manager.get_quote("000001")

        # 验证：熔断已过期，provider被正常调用
        assert result['success'] is True
        assert result['source'] == "RecoveredProvider"
        provider.get_quote.assert_called_once()

    def test_success_clears_circuit_breaker(self, manager):
        """测试：成功调用清除熔断状态"""
        provider = MagicMock()
        provider.name = "TestProvider"
        provider.get_quote = MagicMock(return_value=QuoteData(
            symbol="000001",
            name="平安银行",
            price=10.5,
            source="TestProvider",
            timestamp="2024-01-01 10:00:00"
        ))

        manager.quote_providers = [provider]
        manager._init_stats()

        # 手动设置熔断状态
        manager.provider_stats["TestProvider"]['consecutive_failures'] = 5
        manager.provider_stats["TestProvider"]['circuit_breaker_until'] = time.time() - 1

        # 执行成功调用
        result = manager.get_quote("000001")

        # 验证：熔断被清除
        assert result['success'] is True
        stats = manager.provider_stats["TestProvider"]
        assert stats['consecutive_failures'] == 0
        assert stats['circuit_breaker_until'] == 0


class TestHealthScoreAdjustment:
    """测试健康评分动态调整"""

    @pytest.fixture
    def manager(self):
        """创建DataProviderManager实例"""
        return DataProviderManager(ds=None)

    def test_failing_provider_deprioritized(self, manager):
        """测试：连续失败的provider被降低优先级"""
        # 创建两个providers，provider1总是失败
        provider1 = MagicMock()
        provider1.name = "UnreliableProvider"
        provider1.get_quote = MagicMock(return_value=None)

        provider2 = MagicMock()
        provider2.name = "ReliableProvider"
        provider2.get_quote = MagicMock(return_value=QuoteData(
            symbol="000001",
            name="平安银行",
            price=10.5,
            source="ReliableProvider",
            timestamp="2024-01-01 10:00:00"
        ))

        manager.quote_providers = [provider1, provider2]
        manager._init_stats()

        # 执行多次查询，让provider1累积失败
        for i in range(5):
            result = manager.get_quote("000001")
            assert result['success'] is True  # provider2总是成功

        # 验证健康评分
        sorted_providers = manager._sort_providers_by_health(manager.quote_providers)
        # ReliableProvider应排在前面
        assert sorted_providers[0].name == "ReliableProvider"
        assert sorted_providers[1].name == "UnreliableProvider"

    def test_recovered_provider_regains_priority(self, manager):
        """测试：恢复的provider重新获得优先级"""
        provider = MagicMock()
        provider.name = "RecoveringProvider"

        # 初始返回成功
        provider.get_quote = MagicMock(return_value=QuoteData(
            symbol="000001",
            name="平安银行",
            price=10.5,
            source="RecoveringProvider",
            timestamp="2024-01-01 10:00:00"
        ))

        manager.quote_providers = [provider]
        manager._init_stats()

        # 手动设置为低健康分
        manager.provider_stats["RecoveringProvider"]['consecutive_failures'] = 3

        # 执行成功调用
        result = manager.get_quote("000001")
        assert result['success'] is True

        # 验证：连续失败已重置
        assert manager.provider_stats["RecoveringProvider"]['consecutive_failures'] == 0
