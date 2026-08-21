"""
测试 DataService 依赖注入重构

P2-1 Phase 2: 验证 DataService 支持依赖注入且保持向后兼容
"""
import pytest
from unittest.mock import Mock, MagicMock
from application.services.data_service import DataService
from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
from infrastructure.services.service_registry import register_all_services


class TestDataServiceDependencyInjection:
    """测试 DataService 依赖注入"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """每个测试前后重置工厂"""
        EnhancedServiceFactory.reset()
        yield
        EnhancedServiceFactory.reset()

    def test_data_service_backward_compatibility(self):
        """测试向后兼容 - 无参数构造仍然工作"""
        # 不传任何参数，应该自动实例化所有依赖
        service = DataService()

        # 验证所有 Repository 都已初始化
        assert service.stock is not None
        assert service.kline is not None
        assert service.signal is not None
        assert service.simulation is not None
        assert service.portfolio is not None
        assert service.factor is not None
        assert service.backtest is not None
        assert service.risk is not None
        assert service.strategy is not None
        assert service.execution is not None
        assert service.financial_service is not None

    def test_data_service_with_mock_repositories(self):
        """测试使用 Mock Repository 进行依赖注入"""
        # 创建 Mock Repository
        mock_stock_repo = Mock()
        mock_stock_repo.get_by_symbol.return_value = None

        mock_kline_repo = Mock()
        mock_signal_repo = Mock()

        # 使用依赖注入
        service = DataService(
            stock_repo=mock_stock_repo,
            kline_repo=mock_kline_repo,
            signal_repo=mock_signal_repo,
        )

        # 验证 Mock 被正确注入
        assert service.stock is mock_stock_repo
        assert service.kline is mock_kline_repo
        assert service.signal is mock_signal_repo

        # 验证未传入的依赖被自动实例化
        assert service.simulation is not None
        assert service.portfolio is not None

    def test_data_service_from_enhanced_factory(self):
        """测试从 EnhancedServiceFactory 获取 DataService"""
        # 注册所有服务
        register_all_services()

        # 从 EnhancedServiceFactory 解析
        service = EnhancedServiceFactory.resolve(DataService)

        # 验证服务正确初始化
        assert isinstance(service, DataService)
        assert service.stock is not None
        assert service.kline is not None

    def test_data_service_singleton_behavior(self):
        """测试 DataService 的单例行为"""
        # 注册所有服务
        register_all_services()

        # 多次解析应该返回同一个实例
        service1 = EnhancedServiceFactory.resolve(DataService)
        service2 = EnhancedServiceFactory.resolve(DataService)

        assert service1 is service2

    def test_data_service_mixed_injection(self):
        """测试混合注入 - 部分 Mock，部分自动实例化"""
        mock_stock_repo = Mock()
        mock_stock_repo.get_by_symbol.return_value = Mock(to_dict=lambda: {"symbol": "000001"})

        # 只注入 stock_repo
        service = DataService(stock_repo=mock_stock_repo)

        # 验证 stock_repo 是 Mock
        assert service.stock is mock_stock_repo

        # 验证其他依赖自动实例化
        assert service.kline is not None
        assert service.signal is not None

        # 验证 Mock 可以正常调用
        result = service.stock.get_by_symbol("000001")
        assert result.to_dict()["symbol"] == "000001"


class TestDataServiceIntegration:
    """测试 DataService 集成功能"""

    @pytest.fixture(autouse=True)
    def setup_factory(self):
        """设置 EnhancedServiceFactory"""
        EnhancedServiceFactory.reset()
        register_all_services()
        yield
        EnhancedServiceFactory.reset()

    def test_data_service_cleanup_method(self):
        """测试 cleanup 方法"""
        service = EnhancedServiceFactory.resolve(DataService)

        # cleanup 不应该抛异常
        service.cleanup()

    def test_data_service_cache_manager(self):
        """测试缓存管理器参数"""
        mock_cache = Mock()

        service = DataService(cache_manager=mock_cache)

        assert service._cache is mock_cache
