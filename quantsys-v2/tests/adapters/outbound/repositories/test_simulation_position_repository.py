# tests/adapters/outbound/repositories/test_simulation_position_repository.py
import pytest
from unittest.mock import Mock
from adapters.outbound.repositories.simulation_position_repository import SimulationPositionRepository
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

class TestSimulationPositionRepository:
    """SimulationPositionRepository 集成测试"""
    
    @pytest.fixture
    def mock_sim_repo(self):
        return Mock(spec=SimulationORMRepository)
    
    @pytest.fixture
    def repo(self, mock_sim_repo):
        return SimulationPositionRepository(sim_repo=mock_sim_repo)
    
    def test_get_position(self, repo, mock_sim_repo):
        """测试获取持仓"""
        # Arrange
        orm_position = Mock()
        orm_position.account_name = "test_account"
        orm_position.symbol = "600000"
        orm_position.shares_total = 100
        orm_position.shares_available = 100
        orm_position.avg_cost = 10.0
        orm_position.current_price = 12.0
        orm_position.market_value = 1200.0
        orm_position.unrealized_pnl = 200.0
        orm_position.unrealized_pnl_rate = 0.2
        orm_position.created_at = None
        orm_position.updated_at = None
        mock_sim_repo.get_position.return_value = orm_position
        
        # Act
        position = repo.get_position("test_account", "600000")
        
        # Assert
        assert position is not None
        assert position.shares_total == 100
        assert position.avg_cost == 10.0
    
    def test_get_position_not_found(self, repo, mock_sim_repo):
        """测试获取持仓不存在"""
        # Arrange
        mock_sim_repo.get_position.return_value = None
        
        # Act
        position = repo.get_position("test_account", "600000")
        
        # Assert
        assert position is None
    
    def test_get_all_positions(self, repo, mock_sim_repo):
        """测试获取所有持仓"""
        # Arrange
        orm_position1 = Mock()
        orm_position1.account_name = "test_account"
        orm_position1.symbol = "600000"
        orm_position1.shares_total = 100
        orm_position1.shares_available = 100
        orm_position1.avg_cost = 10.0
        orm_position1.current_price = 12.0
        orm_position1.market_value = 1200.0
        orm_position1.unrealized_pnl = 200.0
        orm_position1.unrealized_pnl_rate = 0.2
        orm_position1.created_at = None
        orm_position1.updated_at = None
        
        orm_position2 = Mock()
        orm_position2.account_name = "test_account"
        orm_position2.symbol = "000001"
        orm_position2.shares_total = 200
        orm_position2.shares_available = 200
        orm_position2.avg_cost = 15.0
        orm_position2.current_price = 16.0
        orm_position2.market_value = 3200.0
        orm_position2.unrealized_pnl = 200.0
        orm_position2.unrealized_pnl_rate = 0.067
        orm_position2.created_at = None
        orm_position2.updated_at = None
        
        mock_sim_repo.get_all_positions.return_value = [orm_position1, orm_position2]
        
        # Act
        positions = repo.get_all_positions("test_account")
        
        # Assert
        assert len(positions) == 2
        assert positions[0].symbol == "600000"
        assert positions[1].symbol == "000001"
    
    def test_upsert_position(self, repo, mock_sim_repo):
        """测试创建或更新持仓"""
        # Arrange
        mock_sim_repo.upsert_position.return_value = True
        
        # Act
        result = repo.upsert_position(
            account_name="test_account",
            symbol="600000",
            shares_total=100,
            avg_cost=10.0,
            shares_available=100,
            current_price=12.0,
        )
        
        # Assert
        assert result is True
        mock_sim_repo.upsert_position.assert_called_once()
    
    def test_delete_position(self, repo, mock_sim_repo):
        """测试删除持仓"""
        # Arrange
        mock_sim_repo.delete_position.return_value = True
        
        # Act
        result = repo.delete_position("test_account", "600000")
        
        # Assert
        assert result is True
        mock_sim_repo.delete_position.assert_called_once()
