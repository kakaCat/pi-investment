# adapters/outbound/repositories/simulation_account_repository.py
"""
SimulationAccountRepository - 适配 SimulationORMRepository 到 IAccountRepository 接口

这是领域适配器，将现有的 SimulationORMRepository 适配到新的 IAccountRepository 接口。
"""
from typing import Optional, List
import structlog

from domain.accounts.models.account import Account, AccountStatus
from domain.accounts.models.balance import Balance
from domain.accounts.ports.IAccountRepository import IAccountRepository
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

logger = structlog.get_logger(__name__)


class SimulationAccountRepository(IAccountRepository):
    """基于 SimulationORMRepository 的 IAccountRepository 实现"""
    
    def __init__(self, sim_repo: Optional[SimulationORMRepository] = None):
        self.sim_repo = sim_repo or SimulationORMRepository()
    
    def get_account(self, account_name: str) -> Optional[Account]:
        """获取账户信息"""
        orm_account = self.sim_repo.get_account(account_name)
        if not orm_account:
            return None
        
        return Account(
            account_name=orm_account.account_name,
            display_name=orm_account.display_name,
            status=AccountStatus(orm_account.status),
            initial_capital=float(orm_account.initial_capital),
            created_at=orm_account.created_at,
            updated_at=orm_account.updated_at,
            strategy_name=orm_account.strategy_name,
        )
    
    def get_balance(self, account_name: str) -> Optional[Balance]:
        """获取资金余额"""
        orm_account = self.sim_repo.get_account(account_name)
        if not orm_account:
            return None
        
        return Balance(
            account_name=orm_account.account_name,
            available_cash=float(orm_account.cash_available or 0),
            frozen_cash=float(orm_account.cash_frozen or 0),
            total_value=float(orm_account.total_value or 0),
            position_value=float(orm_account.position_value or 0),
            peak_value=float(orm_account.peak_value or 0),
            cumulative_return=float(orm_account.cumulative_return or 0),
            max_drawdown=float(orm_account.max_drawdown or 0),
            updated_at=orm_account.updated_at,
        )
    
    def get_all_accounts(self, status: str = 'active') -> List[Account]:
        """获取所有账户"""
        orm_accounts = self.sim_repo.list_accounts(status)
        return [
            Account(
                account_name=a.account_name,
                display_name=a.display_name,
                status=AccountStatus(a.status),
                initial_capital=float(a.initial_capital),
                created_at=a.created_at,
                updated_at=a.updated_at,
                strategy_name=a.strategy_name,
            )
            for a in orm_accounts
        ]
    
    def create_account(
        self,
        account_name: str,
        initial_capital: float,
        display_name: Optional[str] = None,
        strategy_name: Optional[str] = None,
    ) -> Account:
        """创建账户"""
        orm_account = self.sim_repo.create_account(
            account_name=account_name,
            initial_capital=initial_capital,
            display_name=display_name,
            strategy_name=strategy_name,
        )
        
        if not orm_account:
            raise RuntimeError(f"创建账户失败: {account_name}")
        
        return Account(
            account_name=orm_account.account_name,
            display_name=orm_account.display_name,
            status=AccountStatus(orm_account.status),
            initial_capital=float(orm_account.initial_capital),
            created_at=orm_account.created_at,
            strategy_name=orm_account.strategy_name,
        )
    
    def update_balance(
        self,
        account_name: str,
        available_cash: float,
        frozen_cash: float = None,
    ) -> bool:
        """更新资金余额"""
        account = self.sim_repo.get_account(account_name)
        if not account:
            return False
        
        account.cash_available = available_cash
        if frozen_cash is not None:
            account.cash_frozen = frozen_cash
        
        self.sim_repo.session.commit()
        return True
    
    def deduct_cash(self, account_name: str, amount: float) -> bool:
        """扣减可用资金"""
        account = self.sim_repo.get_account(account_name)
        if not account:
            return False
        
        if float(account.cash_available) < amount:
            logger.warning(
                f"扣减资金失败: {account_name} "
                f"需要 ¥{amount:,.2f}, "
                f"可用 ¥{float(account.cash_available):,.2f}"
            )
            return False
        
        account.cash_available = float(account.cash_available) - amount
        self.sim_repo.session.commit()
        return True
    
    def add_cash(self, account_name: str, amount: float) -> bool:
        """增加可用资金"""
        account = self.sim_repo.get_account(account_name)
        if not account:
            return False
        
        account.cash_available = float(account.cash_available) + amount
        self.sim_repo.session.commit()
        return True
