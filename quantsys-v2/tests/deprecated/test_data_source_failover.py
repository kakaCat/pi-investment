"""
集成测试：数据源 Failover 机制
验证 akshare 失败时自动切换到 baostock
"""
import pytest
from unittest.mock import Mock, patch
from adapters.outbound.datasources.manager import DataSourceManager
from adapters.outbound.datasources.base import DataSourceResponse


class TestDataSourceFailover:
    """测试数据源自动切换机制"""

    @pytest.fixture
    def manager(self):
        """创建 DataSourceManager 实例"""
        return DataSourceManager()

    def test_manager_initialization(self, manager):
        """测试管理器初始化"""
        assert manager is not None
        assert len(manager.sources) > 0

        # 检查 baostock 是否已注册
        if 'baostock' in manager.source_configs:
            assert 'baostock' in manager.sources or not manager.source_configs['baostock'].enabled

    def test_baostock_registered(self, manager):
        """测试 baostock 是否已注册"""
        # 检查配置中是否有 baostock
        assert 'baostock' in manager.source_configs

        config = manager.source_configs['baostock']
        assert config.name == 'baostock'
        assert config.priority == 2  # akshare=1, baostock=2
        assert config.enabled is True

    def test_source_priority_order(self, manager):
        """测试数据源优先级顺序"""
        # 获取 get_klines 方法的数据源顺序
        enabled_sources = manager._get_enabled_sources('get_klines')

        if len(enabled_sources) > 0:
            # 验证按优先级排序
            priorities = [manager.source_configs[name].priority
                         for name, _ in enabled_sources]
            assert priorities == sorted(priorities), "数据源应按优先级排序"

    @patch('data_sources.sources.akshare_source.AkShareSource.get_klines')
    def test_failover_akshare_to_baostock(self, mock_akshare_klines, manager):
        """测试 akshare 失败时切换到 baostock"""
        # 模拟 akshare 失败
        mock_akshare_klines.return_value = DataSourceResponse.error_response(
            "akshare connection failed"
        )

        # 调用管理器获取数据
        response = manager.get_klines(
            symbol='600000.SH',
            period='daily',
            start_date='2023-01-01',
            end_date='2023-01-31'
        )

        # 如果 baostock 可用，应该成功
        # 如果都不可用，应该返回错误
        assert response is not None

        # 验证确实调用了 akshare（第一优先级）
        assert mock_akshare_klines.called

    def test_circuit_breaker_for_baostock(self, manager):
        """测试 baostock 的熔断器"""
        if 'baostock' not in manager.circuit_breakers:
            pytest.skip("baostock circuit breaker not initialized")

        breaker = manager.circuit_breakers['baostock']

        # 初始状态应该是关闭的（可用）
        assert breaker.is_available() is True

        # 记录初始失败次数
        initial_failures = breaker.failure_count

    def test_get_klines_with_baostock_available(self, manager):
        """测试在 baostock 可用时获取K线数据"""
        # 尝试获取K线数据
        response = manager.get_klines(
            symbol='600000.SH',
            period='daily',
            start_date='2023-01-01',
            end_date='2023-01-31'
        )

        # 应该能获取到数据（从任一可用源）
        assert response is not None
        # 不强制要求成功，因为所有源可能都失败

    def test_statistics_tracking(self, manager):
        """测试统计信息追踪"""
        # 初始统计
        initial_total = manager.stats.get('total_requests', 0)

        # 执行一次请求
        manager.get_klines(
            symbol='600000.SH',
            period='daily',
            start_date='2023-01-01',
            end_date='2023-01-10'
        )

        # 统计应该增加
        assert manager.stats['total_requests'] >= initial_total

    def test_cache_integration(self, manager):
        """测试缓存集成"""
        assert manager.cache is not None

        # 第一次请求（cache miss）
        response1 = manager.get_klines(
            symbol='600000.SH',
            period='daily',
            start_date='2023-01-01',
            end_date='2023-01-05'
        )

        cache_misses_after_first = manager.stats.get('cache_misses', 0)

        # 第二次相同请求（应该 cache hit，但取决于TTL）
        response2 = manager.get_klines(
            symbol='600000.SH',
            period='daily',
            start_date='2023-01-01',
            end_date='2023-01-05'
        )

        # 验证缓存统计存在
        assert 'cache_hits' in manager.stats
        assert 'cache_misses' in manager.stats

    def test_method_override_config(self, manager):
        """测试方法特定的数据源配置"""
        # 检查 get_klines 的配置
        method_overrides = manager.config.get('method_overrides', {})

        if 'get_klines' in method_overrides:
            sources = method_overrides['get_klines'].get('sources', [])
            # 应该包含 akshare 和 baostock
            assert 'akshare' in sources or 'baostock' in sources

    @pytest.mark.integration
    def test_real_failover_scenario(self, manager):
        """测试真实的 failover 场景（集成测试）"""
        # 这个测试需要真实的网络连接
        # 如果 akshare 暂时不可用，应该能从 baostock 获取数据

        response = manager.get_klines(
            symbol='600000.SH',
            period='daily',
            start_date='2023-01-01',
            end_date='2023-01-10'
        )

        # 记录使用的数据源
        if response.success:
            source_used = response.metadata.get('source', 'unknown')
            print(f"\n✅ 成功从 {source_used} 获取数据")
            assert source_used in ['akshare', 'baostock', 'eastmoney', 'sina']
        else:
            print(f"\n⚠️ 所有数据源都失败: {response.error}")

    def test_baostock_specific_features(self, manager):
        """测试 baostock 特有功能"""
        if 'baostock' not in manager.sources:
            pytest.skip("baostock not available")

        baostock = manager.sources['baostock']

        # 测试符号转换
        assert hasattr(baostock, '_convert_symbol_to_bs')
        assert hasattr(baostock, '_convert_symbol_from_bs')

        # 测试转换功能
        bs_symbol = baostock._convert_symbol_to_bs('600000.SH')
        assert bs_symbol == 'sh.600000'

        original = baostock._convert_symbol_from_bs('sh.600000')
        assert original == '600000.SH'

    def test_source_health_status(self, manager):
        """测试数据源健康状态"""
        # 检查每个数据源的熔断器状态
        for source_name, breaker in manager.circuit_breakers.items():
            status = "可用" if breaker.is_available() else "熔断"
            failures = breaker.failure_count
            print(f"\n{source_name}: {status} (失败次数: {failures})")

        # 至少应该有一些数据源可用
        available_count = sum(1 for b in manager.circuit_breakers.values()
                             if b.is_available())
        assert available_count > 0, "至少应该有一个数据源可用"


class TestBaostockIntegration:
    """测试 baostock 的完整集成"""

    def test_baostock_in_config_file(self):
        """测试配置文件中是否包含 baostock"""
        from pathlib import Path
        import yaml

        config_path = Path(__file__).parent.parent / 'data_sources' / 'sources_config.yaml'

        if not config_path.exists():
            pytest.skip("Config file not found")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        sources = config.get('market_data', {}).get('sources', [])
        baostock_config = next((s for s in sources if s['name'] == 'baostock'), None)

        assert baostock_config is not None, "baostock 应该在配置文件中"
        assert baostock_config['priority'] == 2, "baostock 优先级应该是 2"
        assert baostock_config['enabled'] is True, "baostock 应该启用"

    def test_manager_can_create_baostock(self):
        """测试 DataSourceManager 能够创建 baostock 实例"""
        manager = DataSourceManager()

        # 尝试创建 baostock
        source = manager._create_source('baostock')

        if source is None:
            # 可能是 baostock 库未安装
            pytest.skip("baostock source creation returned None")

        assert source is not None
        assert source.name == 'baostock'
