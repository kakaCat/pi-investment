# tests/domain/accounts/test_account_service.py
import pytest
from unittest.mock import Mock, MagicMock
from domain.accounts.models.account import Account, AccountStatus
from domain.accounts.models.balance import Balance
from domain.accounts.services.account_service import AccountService
from domain.accounts.ports.IAccountRepository import IAccountRepository

class TestAccountService:
    """AccountService 单元测试"""
    
    @pytest.fixture
    def mock_repo(self):
        return Mock(spec=IAccountRepository)
    
    @pytest.fixture
    def service(self, mock_repo):
        return AccountService(account_repo=mock_repo)
    
    def test_get_account_success(self, service, mock_repo):
        """测试获取账户成功"""
        # Arrange
        account = Account(
            account_name="test_account",
            display_name="Test Account",
            status=AccountStatus.ACTIVE,
            initial_capital=1000000.0,
        )
        mock_repo.get_account.return_value = account
        
        # Act
        result = service.get_account("test_account")
        
        # Assert
        assert result is not None
        assert result.account_name == "test_account"
        mock_repo.get_account.assert_called_once_with("test_account")
    
    def test_get_account_not_found(self, service, mock_repo):
        """测试获取账户不存在"""
        # Arrange
        mock_repo.get_account.return_value = None
        
        # Act
        result = service.get_account("nonexistent")
        
        # Assert
        assert result is None
    
    def test_validate_buy_balance_sufficient(self, service, mock_repo):
        """测试验证买入资金充足"""
        # Arrange
        balance = Balance(
            account_name="test_account",
            available_cash=100000.0,
        )
        mock_repo.get_balance.return_value = balance
        
        # Act
        result = service.validate_buy_balance("test_account", 50000.0)
        
        # Assert
        assert result is True
    
    def test_validate_buy_balance_insufficient(self, service, mock_repo):
        """测试验证买入资金不足"""
        # Arrange
        balance = Balance(
            account_name="test_account",
            available_cash=10000.0,
        )
        mock_repo.get_balance.return_value = balance
        
        # Act
        result = service.validate_buy_balance("test_account", 50000.0)
        
        # Assert
        assert result is False
    
    def test_validate_buy_balance_no_balance(self, service, mock_repo):
        """测试验证买入资金账户不存在"""
        # Arrange
        mock_repo.get_balance.return_value = None
        
        # Act
        result = service.validate_buy_balance("nonexistent", 50000.0)
        
        # Assert
        assert result is False
    
    def test_execute_deduct_cash(self, service, mock_repo):
        """测试扣减资金"""
        # Arrange
        mock_repo.deduct_cash.return_value = True
        
        # Act
        result = service.execute_deduct_cash("test_account", 10000.0)
        
        # Assert
        assert result is True
        mock_repo.deduct_cash.assert_called_once_with("test_account", 10000.0)
    
    def test_execute_add_cash(self, service, mock_repo):
        """测试增加资金"""
        # Arrange
        mock_repo.add_cash.return_value = True
        
        # Act
        result = service.execute_add_cash("test_account", 20000.0)
        
        # Assert
        assert result is True
        mock_repo.add_cash.assert_called_once_with("test_account", 20000.0)
    
    def test_create_account_success(self, service, mock_repo):
        """测试创建账户成功"""
        # Arrange
        mock_repo.get_account.return_value = None
        new_account = Account(
            account_name="new_account",
            display_name="New Account",
            status=AccountStatus.ACTIVE,
            initial_capital=500000.0,
        )
        mock_repo.create_account.return_value = new_account
        
        # Act
        result = service.create_account(
            account_name="new_account",
            initial_capital=500000.0,
            display_name="New Account",
        )
        
        # Assert
        assert result is not None
        assert result.account_name == "new_account"
        mock_repo.create_account.assert_called_once()
    
    def test_create_account_already_exists(self, service, mock_repo):
        """测试创建账户已存在"""
        # Arrange
        existing_account = Account(
            account_name="existing_account",
            display_name="Existing Account",
            status=AccountStatus.ACTIVE,
            initial_capital=1000000.0,
        )
        mock_repo.get_account.return_value = existing_account
        
        # Act & Assert
        with pytest.raises(ValueError, match="账户已存在"):
            service.create_account(
                account_name="existing_account",
                initial_capital=500000.0,
            )
