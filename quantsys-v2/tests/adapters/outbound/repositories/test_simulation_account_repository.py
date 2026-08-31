# tests/adapters/outbound/repositories/test_simulation_account_repository.py
import pytest
from unittest.mock import Mock, MagicMock
from adapters.outbound.repositories.simulation_account_repository import SimulationAccountRepository
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

class TestSimulationAccountRepository:
    """SimulationAccountRepository 集成测试"""
    
    @pytest.fixture
    def mock_sim_repo(self):
        return Mock(spec=SimulationORMRepository)
    
    @pytest.fixture
    def repo(self, mock_sim_repo):
        return SimulationAccountRepository(sim_repo=mock_sim_repo)
    
    def test_get_account(self, repo, mock_sim_repo):
        """测试获取账户"""
        # Arrange
        orm_account = Mock()
        orm_account.account_name = "test_account"
        orm_account.display_name = "Test Account"
        orm_account.status = "active"
        orm_account.initial_capital = 1000000.0
        orm_account.created_at = None
        orm_account.updated_at = None
        orm_account.strategy_name = "test_strategy"
        mock_sim_repo.get_account.return_value = orm_account
        
        # Act
        account = repo.get_account("test_account")
        
        # Assert
        assert account is not None
        assert account.account_name == "test_account"
        assert account.display_name == "Test Account"
    
    def test_get_account_not_found(self, repo, mock_sim_repo):
        """测试获取账户不存在"""
        # Arrange
        mock_sim_repo.get_account.return_value = None
        
        # Act
        account = repo.get_account("nonexistent")
        
        # Assert
        assert account is None
    
    def test_get_balance(self, repo, mock_sim_repo):
        """测试获取资金余额"""
        # Arrange
        orm_account = Mock()
        orm_account.account_name = "test_account"
        orm_account.cash_available = 500000.0
        orm_account.cash_frozen = 0.0
        orm_account.total_value = 1000000.0
        orm_account.position_value = 500000.0
        orm_account.peak_value = 1100000.0
        orm_account.cumulative_return = 0.1
        orm_account.max_drawdown = 0.05
        orm_account.updated_at = None
        mock_sim_repo.get_account.return_value = orm_account
        
        # Act
        balance = repo.get_balance("test_account")
        
        # Assert
        assert balance is not None
        assert balance.available_cash == 500000.0
        assert balance.total_value == 1000000.0
    
    def test_get_all_accounts(self, repo, mock_sim_repo):
        """测试获取所有账户"""
        # Arrange
        orm_account1 = Mock()
        orm_account1.account_name = "account1"
        orm_account1.display_name = "Account 1"
        orm_account1.status = "active"
        orm_account1.initial_capital = 500000.0
        orm_account1.created_at = None
        orm_account1.updated_at = None
        orm_account1.strategy_name = None
        
        orm_account2 = Mock()
        orm_account2.account_name = "account2"
        orm_account2.display_name = "Account 2"
        orm_account2.status = "active"
        orm_account2.initial_capital = 1000000.0
        orm_account2.created_at = None
        orm_account2.updated_at = None
        orm_account2.strategy_name = None
        
        mock_sim_repo.list_accounts.return_value = [orm_account1, orm_account2]
        
        # Act
        accounts = repo.get_all_accounts()
        
        # Assert
        assert len(accounts) == 2
        assert accounts[0].account_name == "account1"
        assert accounts[1].account_name == "account2"
