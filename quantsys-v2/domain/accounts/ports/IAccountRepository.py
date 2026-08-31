# domain/accounts/ports/IAccountRepository.py
from abc import ABC, abstractmethod
from typing import Optional, List
from domain.accounts.models.account import Account
from domain.accounts.models.balance import Balance

class IAccountRepository(ABC):
    """账户仓储接口 - 定义账户数据访问契约"""
    
    @abstractmethod
    def get_account(self, account_name: str) -> Optional[Account]:
        """获取账户信息"""
        pass
    
    @abstractmethod
    def get_balance(self, account_name: str) -> Optional[Balance]:
        """获取资金余额"""
        pass
    
    @abstractmethod
    def get_all_accounts(self, status: str = 'active') -> List[Account]:
        """获取所有账户"""
        pass
    
    @abstractmethod
    def create_account(
        self,
        account_name: str,
        initial_capital: float,
        display_name: Optional[str] = None,
        strategy_name: Optional[str] = None,
    ) -> Account:
        """创建账户"""
        pass
    
    @abstractmethod
    def update_balance(
        self,
        account_name: str,
        available_cash: float,
        frozen_cash: float = None,
    ) -> bool:
        """更新资金余额"""
        pass
    
    @abstractmethod
    def deduct_cash(self, account_name: str, amount: float) -> bool:
        """扣减可用资金"""
        pass
    
    @abstractmethod
    def add_cash(self, account_name: str, amount: float) -> bool:
        """增加可用资金"""
        pass
