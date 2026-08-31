# tests/domain/portfolio/test_position_service.py
import pytest
from unittest.mock import Mock
from domain.portfolio.models.position import Position
from domain.portfolio.services.position_service import PositionService
from domain.portfolio.ports.IPositionRepository import IPositionRepository

class TestPositionService:
    """PositionService 单元测试"""
    
    @pytest.fixture
    def mock_repo(self):
        return Mock(spec=IPositionRepository)
    
    @pytest.fixture
    def service(self, mock_repo):
        return PositionService(position_repo=mock_repo)
    
    def test_update_on_buy_new_position(self, service, mock_repo):
        """测试买入建仓"""
        # Arrange
        mock_repo.get_position.return_value = None
        mock_repo.upsert_position.return_value = True
        
        # Act
        result = service.update_on_buy(
            account_name="test_account",
            symbol="600000",
            quantity=100,
            price=10.0,
            commission=0.25,
            transfer_fee=0.01,
        )
        
        # Assert
        assert result is True
        mock_repo.upsert_position.assert_called_once()
        call_args = mock_repo.upsert_position.call_args
        assert call_args[1]['shares_total'] == 100
        assert call_args[1]['shares_available'] == 0  # T+1
    
    def test_update_on_buy_add_position(self, service, mock_repo):
        """测试加仓"""
        # Arrange
        existing = Position(
            account_name="test_account",
            symbol="600000",
            shares_total=100,
            shares_available=100,
            avg_cost=10.0,
        )
        mock_repo.get_position.return_value = existing
        mock_repo.upsert_position.return_value = True
        
        # Act
        result = service.update_on_buy(
            account_name="test_account",
            symbol="600000",
            quantity=100,
            price=12.0,
        )
        
        # Assert
        assert result is True
        call_args = mock_repo.upsert_position.call_args
        assert call_args[1]['shares_total'] == 200
        # shares_available should not change (T+1)
        assert call_args[1]['shares_available'] == 100
    
    def test_update_on_sell_partial(self, service, mock_repo):
        """测试减仓"""
        # Arrange
        existing = Position(
            account_name="test_account",
            symbol="600000",
            shares_total=200,
            shares_available=200,
            avg_cost=10.0,
        )
        mock_repo.get_position.return_value = existing
        mock_repo.upsert_position.return_value = True
        
        # Act
        result = service.update_on_sell(
            account_name="test_account",
            symbol="600000",
            quantity=100,
            price=12.0,
        )
        
        # Assert
        assert result is True
        call_args = mock_repo.upsert_position.call_args
        assert call_args[1]['shares_total'] == 100
        assert call_args[1]['shares_available'] == 100
    
    def test_update_on_sell_full(self, service, mock_repo):
        """测试清仓"""
        # Arrange
        existing = Position(
            account_name="test_account",
            symbol="600000",
            shares_total=100,
            shares_available=100,
            avg_cost=10.0,
        )
        mock_repo.get_position.return_value = existing
        mock_repo.delete_position.return_value = True
        
        # Act
        result = service.update_on_sell(
            account_name="test_account",
            symbol="600000",
            quantity=100,
            price=12.0,
        )
        
        # Assert
        assert result is True
        mock_repo.delete_position.assert_called_once()
    
    def test_get_available_shares(self, service, mock_repo):
        """测试获取可卖股数"""
        # Arrange
        position = Position(
            account_name="test_account",
            symbol="600000",
            shares_total=200,
            shares_available=150,
            avg_cost=10.0,
        )
        mock_repo.get_position.return_value = position
        
        # Act
        result = service.get_available_shares("test_account", "600000")
        
        # Assert
        assert result == 150
    
    def test_get_available_shares_no_position(self, service, mock_repo):
        """测试获取可卖股数无持仓"""
        # Arrange
        mock_repo.get_position.return_value = None
        
        # Act
        result = service.get_available_shares("test_account", "600000")
        
        # Assert
        assert result == 0
