# tests/domain/test_service_factory.py
import pytest
from unittest.mock import Mock
from domain.service_factory import DomainServiceFactory

class TestDomainServiceFactory:
    """DomainServiceFactory 单元测试"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置工厂"""
        DomainServiceFactory._instance = None
        yield
        DomainServiceFactory._instance = None
    
    def test_singleton(self):
        """测试单例模式"""
        factory1 = DomainServiceFactory()
        factory2 = DomainServiceFactory()
        assert factory1 is factory2
    
    def test_initialize(self):
        """测试初始化"""
        # Arrange
        mock_account_repo = Mock()
        mock_position_repo = Mock()
        mock_order_repo = Mock()
        
        factory = DomainServiceFactory()
        
        # Act
        factory.initialize(
            account_repo=mock_account_repo,
            position_repo=mock_position_repo,
            order_repo=mock_order_repo,
        )
        
        # Assert
        assert factory.account_service is not None
        assert factory.position_service is not None
        assert factory.order_service is not None
    
    def test_not_initialized_raises_error(self):
        """测试未初始化时访问服务抛出错误"""
        # Arrange
        factory = DomainServiceFactory()
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="DomainServiceFactory not initialized"):
            _ = factory.account_service
        
        with pytest.raises(RuntimeError, match="DomainServiceFactory not initialized"):
            _ = factory.position_service
        
        with pytest.raises(RuntimeError, match="DomainServiceFactory not initialized"):
            _ = factory.order_service
    
    def test_reset(self):
        """测试重置工厂"""
        # Arrange
        mock_account_repo = Mock()
        mock_position_repo = Mock()
        mock_order_repo = Mock()
        
        factory = DomainServiceFactory()
        factory.initialize(
            account_repo=mock_account_repo,
            position_repo=mock_position_repo,
            order_repo=mock_order_repo,
        )
        
        # Act
        factory.reset()
        
        # Assert
        with pytest.raises(RuntimeError, match="DomainServiceFactory not initialized"):
            _ = factory.account_service
