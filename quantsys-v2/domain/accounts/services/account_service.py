# domain/accounts/services/account_service.py
from typing import Optional, List
import structlog
from domain.accounts.models.account import Account
from domain.accounts.models.balance import Balance
from domain.accounts.ports.IAccountRepository import IAccountRepository

logger = structlog.get_logger(__name__)

class AccountService:
    """账户服务 - 管理账户信息和资金"""
    
    def __init__(self, account_repo: IAccountRepository):
        self.account_repo = account_repo
    
    def get_account(self, account_name: str) -> Optional[Account]:
        """获取账户信息"""
        return self.account_repo.get_account(account_name)
    
    def get_balance(self, account_name: str) -> Optional[Balance]:
        """获取资金余额"""
        return self.account_repo.get_balance(account_name)
    
    def get_all_accounts(self, status: str = 'active') -> List[Account]:
        """获取所有账户"""
        return self.account_repo.get_all_accounts(status)
    
    def create_account(
        self,
        account_name: str,
        initial_capital: float,
        display_name: Optional[str] = None,
        strategy_name: Optional[str] = None,
    ) -> Account:
        """创建账户"""
        existing = self.account_repo.get_account(account_name)
        if existing:
            raise ValueError(f"账户已存在: {account_name}")
        
        return self.account_repo.create_account(
            account_name=account_name,
            initial_capital=initial_capital,
            display_name=display_name,
            strategy_name=strategy_name,
        )
    
    def validate_buy_balance(
        self,
        account_name: str,
        required_amount: float,
    ) -> bool:
        """验证买入资金是否充足
        
        Args:
            account_name: 账户名称
            required_amount: 需要的资金总额（含手续费）
        
        Returns:
            True if balance is sufficient
        """
        balance = self.account_repo.get_balance(account_name)
        if not balance:
            logger.warning(f"账户余额不存在: {account_name}")
            return False
        
        is_sufficient = balance.available_cash >= required_amount
        if not is_sufficient:
            logger.warning(
                f"资金不足: {account_name} "
                f"需要 ¥{required_amount:,.2f}, "
                f"可用 ¥{balance.available_cash:,.2f}"
            )
        return is_sufficient
    
    def validate_sell_position(
        self,
        account_name: str,
        symbol: str,
        required_shares: int,
        available_shares: int,
    ) -> bool:
        """验证卖出持仓是否充足
        
        Args:
            account_name: 账户名称
            symbol: 股票代码
            required_shares: 需要卖出的股数
            available_shares: 可卖股数（T+1后）
        
        Returns:
            True if position is sufficient
        """
        if available_shares < required_shares:
            logger.warning(
                f"持仓不足: {account_name} {symbol} "
                f"可卖 {available_shares} 股, "
                f"需要 {required_shares} 股"
            )
            return False
        return True
    
    def execute_deduct_cash(
        self,
        account_name: str,
        amount: float,
    ) -> bool:
        """执行扣减资金（交易时调用）"""
        return self.account_repo.deduct_cash(account_name, amount)
    
    def execute_add_cash(
        self,
        account_name: str,
        amount: float,
    ) -> bool:
        """执行增加资金（卖出时调用）"""
        return self.account_repo.add_cash(account_name, amount)
