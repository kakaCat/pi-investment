# Accounts & Trading Domain Refactoring Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the混乱 in accounts and trading domains by establishing clear domain boundaries, eliminating duplicate logic, and consolidating the two parallel systems (old PortfolioRepository vs new SimulationORMRepository).

**Architecture:** Restructure into three distinct domains: accounts (账户/资金), trading (订单/成交), and portfolio (持仓). Each domain has its own models, ports (interfaces), and services. Dependencies flow: trading → accounts + portfolio, but accounts and portfolio know nothing about trading.

**Tech Stack:** Python 3.13, SQLAlchemy ORM, PostgreSQL, structlog, pytest

---

## Current Problems

1. **Two parallel systems**: Old `PortfolioRepository` (holdings table) vs new `SimulationORMRepository` (simulation_* tables) with if/else fallback logic everywhere
2. **Blurred domain boundaries**: `order_service.py` (1169 lines) mixes order creation, position updates, fund validation, and signal tracking
3. **Duplicated responsibilities**: Fund validation, position updates, and fee calculations exist in multiple services

## Target State

```
domain/accounts/          # 账户、资金、余额
domain/trading/           # 订单、成交、费用
domain/portfolio/         # 持仓、资产配置
```

---

## Phase 1: Foundation - Create Domain Structure (Tasks 1-4)

### Task 1: Create accounts domain models and ports

**Files:**
- Create: `domain/accounts/__init__.py`
- Create: `domain/accounts/models/__init__.py`
- Create: `domain/accounts/models/account.py`
- Create: `domain/accounts/models/balance.py`
- Create: `domain/accounts/ports/__init__.py`
- Create: `domain/accounts/ports/IAccountRepository.py`
- Create: `domain/accounts/services/__init__.py`
- Create: `domain/accounts/services/account_service.py`

- [ ] **Step 1: Create domain directory structure**

```bash
mkdir -p domain/accounts/models
mkdir -p domain/accounts/ports
mkdir -p domain/accounts/services
```

- [ ] **Step 2: Create Account model**

```python
# domain/accounts/models/account.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from enum import Enum

class AccountStatus(Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    ARCHIVED = "archived"

@dataclass
class Account:
    """账户模型 - 表示用户在系统中的交易账户"""
    account_name: str
    display_name: str
    status: AccountStatus
    initial_capital: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    strategy_name: Optional[str] = None
```

- [ ] **Step 3: Create Balance model**

```python
# domain/accounts/models/balance.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Balance:
    """资金模型 - 表示账户的资金状态"""
    account_name: str
    available_cash: float      # 可用资金
    frozen_cash: float = 0.0   # 冻结资金
    total_value: float = 0.0   # 总资产
    position_value: float = 0.0  # 持仓市值
    peak_value: float = 0.0    # 历史峰值
    cumulative_return: float = 0.0  # 累计收益率
    max_drawdown: float = 0.0  # 最大回撤
    updated_at: Optional[datetime] = None
```

- [ ] **Step 4: Create IAccountRepository port**

```python
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
```

- [ ] **Step 5: Create AccountService**

```python
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
```

- [ ] **Step 6: Create __init__.py files**

```python
# domain/accounts/__init__.py
from .models.account import Account, AccountStatus
from .models.balance import Balance
from .ports.IAccountRepository import IAccountRepository
from .services.account_service import AccountService

__all__ = [
    'Account',
    'AccountStatus',
    'Balance',
    'IAccountRepository',
    'AccountService',
]
```

```python
# domain/accounts/models/__init__.py
from .account import Account, AccountStatus
from .balance import Balance

__all__ = ['Account', 'AccountStatus', 'Balance']
```

```python
# domain/accounts/ports/__init__.py
from .IAccountRepository import IAccountRepository

__all__ = ['IAccountRepository']
```

```python
# domain/accounts/services/__init__.py
from .account_service import AccountService

__all__ = ['AccountService']
```

- [ ] **Step 7: Write tests for AccountService**

```python
# tests/domain/accounts/test_account_service.py
import pytest
from unittest.mock import Mock, MagicMock
from domain.accounts.models.account import Account, AccountStatus
from domain.accounts.models.balance import Balance
from domain.accounts.services.account_service import AccountService

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
    
    def test_execute_deduct_cash(self, service, mock_repo):
        """测试扣减资金"""
        # Arrange
        mock_repo.deduct_cash.return_value = True
        
        # Act
        result = service.execute_deduct_cash("test_account", 10000.0)
        
        # Assert
        assert result is True
        mock_repo.deduct_cash.assert_called_once_with("test_account", 10000.0)
```

- [ ] **Step 8: Run tests**

```bash
pytest tests/domain/accounts/test_account_service.py -v
```

Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add domain/accounts/ tests/domain/accounts/
git commit -m "feat(accounts): add domain models, ports, and AccountService"
```

---

### Task 2: Create trading domain models and ports

**Files:**
- Create: `domain/trading/__init__.py`
- Create: `domain/trading/models/__init__.py`
- Create: `domain/trading/models/order.py`
- Create: `domain/trading/models/trade.py`
- Create: `domain/trading/ports/__init__.py`
- Create: `domain/trading/ports/IOrderRepository.py`
- Create: `domain/trading/ports/ITradeRepository.py`
- Create: `domain/trading/services/__init__.py`

- [ ] **Step 1: Create domain directory structure**

```bash
mkdir -p domain/trading/models
mkdir -p domain/trading/ports
mkdir -p domain/trading/services
```

- [ ] **Step 2: Create Order model**

```python
# domain/trading/models/order.py
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from enum import Enum

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"

class OrderStatus(Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"

@dataclass
class Order:
    """订单模型 - 表示一个交易订单"""
    id: Optional[int] = None
    account_name: str = ""
    symbol: str = ""
    name: str = ""
    action: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.LIMIT
    quantity: int = 0
    price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    avg_filled_price: float = 0.0
    reason: Optional[str] = None
    signal_id: Optional[int] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    parent_order_id: Optional[int] = None
    order_group: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
```

- [ ] **Step 3: Create Trade model**

```python
# domain/trading/models/trade.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Trade:
    """成交记录模型 - 表示一笔已成交的交易"""
    id: Optional[int] = None
    account_name: str = ""
    order_id: Optional[int] = None
    symbol: str = ""
    name: str = ""
    action: str = ""  # "buy" or "sell"
    shares: int = 0
    price: float = 0.0
    filled_price: float = 0.0
    amount: float = 0.0
    commission: float = 0.0
    stamp_duty: float = 0.0
    transfer_fee: float = 0.0
    realized_pnl: Optional[float] = None
    realized_pnl_rate: Optional[float] = None
    reason: Optional[str] = None
    trade_date: Optional[str] = None
    created_at: Optional[datetime] = None
```

- [ ] **Step 4: Create IOrderRepository port**

```python
# domain/trading/ports/IOrderRepository.py
from abc import ABC, abstractmethod
from typing import Optional, List
from domain.trading.models.order import Order, OrderStatus

class IOrderRepository(ABC):
    """订单仓储接口 - 定义订单数据访问契约"""
    
    @abstractmethod
    def get_order(self, order_id: int) -> Optional[Order]:
        """获取订单"""
        pass
    
    @abstractmethod
    def get_orders(
        self,
        account_name: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 50,
    ) -> List[Order]:
        """获取订单列表"""
        pass
    
    @abstractmethod
    def get_pending_orders(self, account_name: Optional[str] = None) -> List[Order]:
        """获取待处理订单"""
        pass
    
    @abstractmethod
    def create_order(self, order: Order) -> int:
        """创建订单，返回订单ID"""
        pass
    
    @abstractmethod
    def update_order_status(
        self,
        order_id: int,
        status: OrderStatus,
        filled_quantity: Optional[int] = None,
        avg_filled_price: Optional[float] = None,
    ) -> bool:
        """更新订单状态"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: int) -> bool:
        """取消订单"""
        pass
```

- [ ] **Step 5: Create ITradeRepository port**

```python
# domain/trading/ports/ITradeRepository.py
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from domain.trading.models.trade import Trade

class ITradeRepository(ABC):
    """成交记录仓储接口"""
    
    @abstractmethod
    def create_trade(self, trade: Trade) -> int:
        """创建成交记录，返回交易ID"""
        pass
    
    @abstractmethod
    def get_trade(self, trade_id: int) -> Optional[Trade]:
        """获取成交记录"""
        pass
    
    @abstractmethod
    def get_trades_by_order(self, order_id: int) -> List[Trade]:
        """按订单获取成交记录"""
        pass
    
    @abstractmethod
    def get_trades_by_symbol(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Trade]:
        """按股票获取成交记录"""
        pass
    
    @abstractmethod
    def get_trade_stats(
        self,
        account_name: Optional[str] = None,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        """获取交易统计"""
        pass
```

- [ ] **Step 6: Create __init__.py files**

```python
# domain/trading/__init__.py
from .models.order import Order, OrderSide, OrderType, OrderStatus
from .models.trade import Trade
from .ports.IOrderRepository import IOrderRepository
from .ports.ITradeRepository import ITradeRepository

__all__ = [
    'Order',
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'Trade',
    'IOrderRepository',
    'ITradeRepository',
]
```

```python
# domain/trading/models/__init__.py
from .order import Order, OrderSide, OrderType, OrderStatus
from .trade import Trade

__all__ = ['Order', 'OrderSide', 'OrderType', 'OrderStatus', 'Trade']
```

```python
# domain/trading/ports/__init__.py
from .IOrderRepository import IOrderRepository
from .ITradeRepository import ITradeRepository

__all__ = ['IOrderRepository', 'ITradeRepository']
```

```python
# domain/trading/services/__init__.py
```

- [ ] **Step 7: Commit**

```bash
git add domain/trading/
git commit -m "feat(trading): add domain models and ports for Order and Trade"
```

---

### Task 3: Create portfolio domain models and ports

**Files:**
- Create: `domain/portfolio/__init__.py`
- Create: `domain/portfolio/models/__init__.py`
- Create: `domain/portfolio/models/position.py`
- Create: `domain/portfolio/ports/__init__.py`
- Create: `domain/portfolio/ports/IPositionRepository.py`
- Create: `domain/portfolio/services/__init__.py`
- Create: `domain/portfolio/services/position_service.py`

- [ ] **Step 1: Create domain directory structure**

```bash
mkdir -p domain/portfolio/models
mkdir -p domain/portfolio/ports
mkdir -p domain/portfolio/services
```

- [ ] **Step 2: Create Position model**

```python
# domain/portfolio/models/position.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Position:
    """持仓模型 - 表示账户中某只股票的持仓"""
    account_name: str = ""
    symbol: str = ""
    shares_total: int = 0          # 总持仓数量
    shares_available: int = 0      # 可卖数量（T+1后）
    avg_cost: float = 0.0          # 平均成本
    current_price: float = 0.0     # 当前价格
    market_value: float = 0.0      # 市值
    unrealized_pnl: float = 0.0    # 浮动盈亏
    unrealized_pnl_rate: float = 0.0  # 浮动盈亏率
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

- [ ] **Step 3: Create IPositionRepository port**

```python
# domain/portfolio/ports/IPositionRepository.py
from abc import ABC, abstractmethod
from typing import Optional, List
from domain.portfolio.models.position import Position

class IPositionRepository(ABC):
    """持仓仓储接口"""
    
    @abstractmethod
    def get_position(
        self,
        account_name: str,
        symbol: str,
    ) -> Optional[Position]:
        """获取单只股票持仓"""
        pass
    
    @abstractmethod
    def get_all_positions(self, account_name: str) -> List[Position]:
        """获取账户所有持仓"""
        pass
    
    @abstractmethod
    def upsert_position(
        self,
        account_name: str,
        symbol: str,
        shares_total: int,
        avg_cost: float,
        shares_available: int,
        current_price: float,
    ) -> bool:
        """创建或更新持仓"""
        pass
    
    @abstractmethod
    def delete_position(
        self,
        account_name: str,
        symbol: str,
    ) -> bool:
        """删除持仓（清仓时）"""
        pass
```

- [ ] **Step 4: Create PositionService**

```python
# domain/portfolio/services/position_service.py
from typing import Optional, List
import structlog
from domain.portfolio.models.position import Position
from domain.portfolio.ports.IPositionRepository import IPositionRepository

logger = structlog.get_logger(__name__)

class PositionService:
    """持仓服务 - 管理股票持仓"""
    
    def __init__(self, position_repo: IPositionRepository):
        self.position_repo = position_repo
    
    def get_position(
        self,
        account_name: str,
        symbol: str,
    ) -> Optional[Position]:
        """获取单只股票持仓"""
        return self.position_repo.get_position(account_name, symbol)
    
    def get_all_positions(self, account_name: str) -> List[Position]:
        """获取账户所有持仓"""
        return self.position_repo.get_all_positions(account_name)
    
    def get_available_shares(
        self,
        account_name: str,
        symbol: str,
    ) -> int:
        """获取可卖股数（T+1规则）"""
        position = self.get_position(account_name, symbol)
        if not position:
            return 0
        return position.shares_available
    
    def update_on_buy(
        self,
        account_name: str,
        symbol: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        transfer_fee: float = 0.0,
    ) -> bool:
        """买入后更新持仓
        
        T+1规则：当日买入的 shares_available 不变（仍为0或原值），
        次日结算后才增加。
        """
        existing = self.get_position(account_name, symbol)
        
        if existing:
            # 加仓：计算新的移动加权平均成本
            old_qty = existing.shares_total
            old_cost = existing.avg_cost * old_qty
            new_qty = old_qty + quantity
            # 成本 = 旧成本 + 新买入金额 + 手续费
            new_cost = old_cost + price * quantity + commission + transfer_fee
            avg_cost = new_cost / new_qty if new_qty > 0 else 0
            
            # T+1: shares_available 不变
            shares_available = existing.shares_available
        else:
            # 建仓
            new_qty = quantity
            avg_cost = (price * quantity + commission + transfer_fee) / quantity
            # T+1: 当日买入不可卖
            shares_available = 0
        
        success = self.position_repo.upsert_position(
            account_name=account_name,
            symbol=symbol,
            shares_total=new_qty,
            avg_cost=avg_cost,
            shares_available=shares_available,
            current_price=price,
        )
        
        if success:
            action = "加仓" if existing else "建仓"
            logger.info(
                f"持仓已更新: {account_name} {symbol} "
                f"{action} {quantity}股 @ {price}, "
                f"total={new_qty}, available={shares_available} (T+1)"
            )
        
        return success
    
    def update_on_sell(
        self,
        account_name: str,
        symbol: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        stamp_duty: float = 0.0,
        transfer_fee: float = 0.0,
    ) -> bool:
        """卖出后更新持仓"""
        existing = self.get_position(account_name, symbol)
        
        if not existing:
            logger.warning(f"卖出但无持仓: {account_name} {symbol}")
            return False
        
        remaining = existing.shares_total - quantity
        
        if remaining <= 0:
            # 清仓
            success = self.position_repo.delete_position(account_name, symbol)
            if success:
                logger.info(
                    f"持仓已清仓: {account_name} {symbol} "
                    f"卖出 {quantity}股 @ {price}"
                )
            return success
        else:
            # 减仓：保持 avg_cost 不变
            new_available = max(0, existing.shares_available - quantity)
            success = self.position_repo.upsert_position(
                account_name=account_name,
                symbol=symbol,
                shares_total=remaining,
                avg_cost=existing.avg_cost,
                shares_available=new_available,
                current_price=price,
            )
            if success:
                logger.info(
                    f"持仓已减仓: {account_name} {symbol} "
                    f"卖出 {quantity}股 @ {price}, "
                    f"剩余 total={remaining}, available={new_available}"
                )
            return success
```

- [ ] **Step 5: Create __init__.py files**

```python
# domain/portfolio/__init__.py
from .models.position import Position
from .ports.IPositionRepository import IPositionRepository
from .services.position_service import PositionService

__all__ = [
    'Position',
    'IPositionRepository',
    'PositionService',
]
```

```python
# domain/portfolio/models/__init__.py
from .position import Position

__all__ = ['Position']
```

```python
# domain/portfolio/ports/__init__.py
from .IPositionRepository import IPositionRepository

__all__ = ['IPositionRepository']
```

```python
# domain/portfolio/services/__init__.py
from .position_service import PositionService

__all__ = ['PositionService']
```

- [ ] **Step 6: Write tests for PositionService**

```python
# tests/domain/portfolio/test_position_service.py
import pytest
from unittest.mock import Mock
from domain.portfolio.models.position import Position
from domain.portfolio.services.position_service import PositionService

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
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/domain/portfolio/test_position_service.py -v
```

Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add domain/portfolio/ tests/domain/portfolio/
git commit -m "feat(portfolio): add Position model, IPositionRepository, and PositionService"
```

---

### Task 4: Create trading OrderService (core logic)

**Files:**
- Create: `domain/trading/services/order_service.py`
- Modify: `domain/trading/services/__init__.py`

- [ ] **Step 1: Create OrderService**

```python
# domain/trading/services/order_service.py
from typing import Optional, List
from datetime import datetime, timedelta
import structlog
import uuid

from domain.accounts.services.account_service import AccountService
from domain.portfolio.services.position_service import PositionService
from domain.trading.models.order import Order, OrderSide, OrderType, OrderStatus
from domain.trading.models.trade import Trade
from domain.trading.ports.IOrderRepository import IOrderRepository

logger = structlog.get_logger(__name__)

# A股交易规则
COMMISSION_RATE = 0.00025      # 佣金万2.5
COMMISSION_MIN = 5.0           # 最低5元
STAMP_DUTY_RATE = 0.0005       # 印花税(卖出)
TRANSFER_FEE_RATE = 0.00001    # 过户费

# Valid state transitions
VALID_TRANSITIONS = {
    (OrderStatus.PENDING, OrderStatus.PARTIAL): True,
    (OrderStatus.PENDING, OrderStatus.CANCELLED): True,
    (OrderStatus.PENDING, OrderStatus.EXPIRED): True,
    (OrderStatus.PENDING, OrderStatus.REJECTED): True,
    (OrderStatus.PARTIAL, OrderStatus.FILLED): True,
    (OrderStatus.PARTIAL, OrderStatus.CANCELLED): True,
    (OrderStatus.PARTIAL, OrderStatus.EXPIRED): True,
    (OrderStatus.PARTIAL, OrderStatus.REJECTED): True,
}


class OrderService:
    """订单服务 - 管理订单生命周期"""
    
    def __init__(
        self,
        account_service: AccountService,
        position_service: PositionService,
        order_repo: IOrderRepository,
    ):
        self.account_service = account_service
        self.position_service = position_service
        self.order_repo = order_repo
    
    def validate_order(
        self,
        account_name: str,
        symbol: str,
        action: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: Optional[float] = None,
    ) -> None:
        """校验订单参数"""
        # 基础校验
        if quantity <= 0:
            raise ValueError(f"委托数量必须大于0: {quantity}")
        
        if quantity % 100 != 0:
            raise ValueError(f"A股交易数量必须是100股的整数倍: {quantity}")
        
        if order_type in (OrderType.LIMIT, OrderType.STOP) and price is None:
            raise ValueError(f"{order_type.value} 订单必须提供价格")
        
        if price is not None and price <= 0:
            raise ValueError(f"价格必须大于0: {price}")
        
        # 买入校验：资金
        if action == OrderSide.BUY:
            if price is None:
                raise ValueError("买入订单必须使用限价单")
            
            # 计算总成本
            stock_amount = price * quantity
            commission = max(stock_amount * COMMISSION_RATE, COMMISSION_MIN)
            transfer_fee = stock_amount * TRANSFER_FEE_RATE
            total_cost = stock_amount + commission + transfer_fee
            
            if not self.account_service.validate_buy_balance(account_name, total_cost):
                raise ValueError(
                    f"可用资金不足: 需要 ¥{total_cost:,.2f}, "
                    f"请检查账户 {account_name}"
                )
        
        # 卖出校验：持仓
        elif action == OrderSide.SELL:
            available_shares = self.position_service.get_available_shares(account_name, symbol)
            if available_shares < quantity:
                raise ValueError(
                    f"可卖数量不足: {symbol} 可卖 {available_shares} 股, "
                    f"委托 {quantity} 股"
                )
    
    def create_order(
        self,
        account_name: str,
        symbol: str,
        name: str,
        action: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: float,
        reason: Optional[str] = None,
        signal_id: Optional[int] = None,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
    ) -> Order:
        """创建新订单"""
        # 校验订单
        self.validate_order(account_name, symbol, action, order_type, quantity, price)
        
        # 创建订单对象
        order = Order(
            account_name=account_name,
            symbol=symbol,
            name=name,
            action=action,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,
            reason=reason,
            signal_id=signal_id,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            expires_at=datetime.now() + timedelta(days=7),
        )
        
        # 保存订单
        order_id = self.order_repo.create_order(order)
        order.id = order_id
        
        logger.info(
            f"订单已创建: {account_name} {symbol} "
            f"{action.value} {order_type.value} "
            f"qty={quantity} price={price}"
        )
        
        return order
    
    def fill_order(
        self,
        order_id: int,
        fill_price: float,
        fill_quantity: Optional[int] = None,
    ) -> Trade:
        """成交订单
        
        Args:
            order_id: 订单ID
            fill_price: 成交价格
            fill_quantity: 成交数量（None表示全部成交）
        
        Returns:
            成交记录
        """
        # 获取订单
        order = self.order_repo.get_order(order_id)
        if not order:
            raise ValueError(f"订单不存在: {order_id}")
        
        # 校验状态
        if order.status not in (OrderStatus.PENDING, OrderStatus.PARTIAL):
            raise ValueError(
                f"订单状态不允许成交: {order.status.value} "
                f"(order_id={order_id})"
            )
        
        # 计算成交数量
        remaining_qty = order.quantity - order.filled_quantity
        if fill_quantity is None:
            fill_quantity = remaining_qty
        
        if fill_quantity > remaining_qty:
            raise ValueError(
                f"成交数量超过剩余数量: {fill_quantity} > {remaining_qty}"
            )
        
        # 计算加权平均成交价
        old_filled_qty = order.filled_quantity
        old_avg_price = order.avg_filled_price
        
        new_filled_qty = old_filled_qty + fill_quantity
        if old_filled_qty == 0:
            new_avg_price = fill_price
        else:
            total_cost = old_filled_qty * old_avg_price + fill_quantity * fill_price
            new_avg_price = total_cost / new_filled_qty
        
        # 判断新状态
        if new_filled_qty >= order.quantity:
            new_status = OrderStatus.FILLED
        else:
            new_status = OrderStatus.PARTIAL
        
        # 更新订单状态
        self.order_repo.update_order_status(
            order_id=order_id,
            status=new_status,
            filled_quantity=new_filled_qty,
            avg_filled_price=round(new_avg_price, 4),
        )
        
        # 计算费用
        amount = fill_price * fill_quantity
        commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
        stamp_duty = amount * STAMP_DUTY_RATE if order.action == OrderSide.SELL else 0.0
        transfer_fee = amount * TRANSFER_FEE_RATE
        
        # 计算已实现盈亏（仅卖出时）
        realized_pnl = None
        realized_pnl_rate = None
        if order.action == OrderSide.SELL:
            position = self.position_service.get_position(
                order.account_name, order.symbol
            )
            if position:
                cost_basis = fill_quantity * position.avg_cost
                realized_pnl = round(
                    amount - cost_basis - commission - stamp_duty - transfer_fee, 2
                )
                realized_pnl_rate = round(realized_pnl / cost_basis, 4) if cost_basis else 0.0
        
        # 创建成交记录
        trade = Trade(
            account_name=order.account_name,
            order_id=order_id,
            symbol=order.symbol,
            name=order.name,
            action=order.action.value,
            shares=fill_quantity,
            price=order.price,
            filled_price=fill_price,
            amount=round(amount, 2),
            commission=round(commission, 2),
            stamp_duty=round(stamp_duty, 2),
            transfer_fee=round(transfer_fee, 2),
            realized_pnl=realized_pnl,
            realized_pnl_rate=realized_pnl_rate,
            reason=order.reason,
            trade_date=datetime.now().strftime('%Y-%m-%d'),
        )
        
        # 保存成交记录 (这里暂时返回trade对象，实际应由TradeService保存)
        # TODO: 注入TradeService并在那里保存
        
        logger.info(
            f"订单已成交: order_id={order_id} "
            f"{order.symbol} {order.action.value} "
            f"qty={fill_quantity} price={fill_price}"
        )
        
        return trade
    
    def cancel_order(self, order_id: int) -> bool:
        """取消订单"""
        order = self.order_repo.get_order(order_id)
        if not order:
            raise ValueError(f"订单不存在: {order_id}")
        
        if order.status != OrderStatus.PENDING:
            raise ValueError(
                f"只能取消 pending 状态的订单，当前状态: {order.status.value}"
            )
        
        return self.order_repo.cancel_order(order_id)
    
    def expire_orders(self) -> int:
        """过期所有超过 expires_at 的 pending 订单"""
        pending_orders = self.order_repo.get_pending_orders()
        now = datetime.now()
        expired_count = 0
        
        for order in pending_orders:
            if order.expires_at and order.expires_at < now:
                try:
                    self.order_repo.update_order_status(
                        order_id=order.id,
                        status=OrderStatus.EXPIRED,
                    )
                    expired_count += 1
                    logger.info(f"订单已过期: order_id={order.id}")
                except Exception as e:
                    logger.error(f"过期订单失败 order_id={order.id}: {e}")
        
        return expired_count
    
    def get_order(self, order_id: int) -> Optional[Order]:
        """获取订单详情"""
        return self.order_repo.get_order(order_id)
    
    def list_orders(
        self,
        account_name: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 50,
    ) -> List[Order]:
        """获取订单列表"""
        return self.order_repo.get_orders(
            account_name=account_name,
            symbol=symbol,
            status=status,
            limit=limit,
        )
```

- [ ] **Step 2: Update __init__.py**

```python
# domain/trading/services/__init__.py
from .order_service import OrderService

__all__ = ['OrderService']
```

- [ ] **Step 3: Write tests for OrderService**

```python
# tests/domain/trading/test_order_service.py
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
from domain.accounts.services.account_service import AccountService
from domain.portfolio.services.position_service import PositionService
from domain.trading.models.order import Order, OrderSide, OrderType, OrderStatus
from domain.trading.services.order_service import OrderService

class TestOrderService:
    """OrderService 单元测试"""
    
    @pytest.fixture
    def mock_account_service(self):
        return Mock(spec=AccountService)
    
    @pytest.fixture
    def mock_position_service(self):
        return Mock(spec=PositionService)
    
    @pytest.fixture
    def mock_order_repo(self):
        return Mock(spec=IOrderRepository)
    
    @pytest.fixture
    def service(self, mock_account_service, mock_position_service, mock_order_repo):
        return OrderService(
            account_service=mock_account_service,
            position_service=mock_position_service,
            order_repo=mock_order_repo,
        )
    
    def test_create_order_buy_success(self, service, mock_account_service, mock_order_repo):
        """测试创建买入订单成功"""
        # Arrange
        mock_account_service.validate_buy_balance.return_value = True
        mock_order_repo.create_order.return_value = 1
        
        # Act
        order = service.create_order(
            account_name="test_account",
            symbol="600000",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=10.0,
        )
        
        # Assert
        assert order is not None
        assert order.id == 1
        assert order.status == OrderStatus.PENDING
        mock_order_repo.create_order.assert_called_once()
    
    def test_create_order_buy_insufficient_balance(
        self, service, mock_account_service
    ):
        """测试创建买入订单资金不足"""
        # Arrange
        mock_account_service.validate_buy_balance.return_value = False
        
        # Act & Assert
        with pytest.raises(ValueError, match="可用资金不足"):
            service.create_order(
                account_name="test_account",
                symbol="600000",
                name="浦发银行",
                action=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=10.0,
            )
    
    def test_create_order_sell_success(
        self, service, mock_position_service, mock_order_repo
    ):
        """测试创建卖出订单成功"""
        # Arrange
        mock_position_service.get_available_shares.return_value = 100
        mock_order_repo.create_order.return_value = 1
        
        # Act
        order = service.create_order(
            account_name="test_account",
            symbol="600000",
            name="浦发银行",
            action=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=12.0,
        )
        
        # Assert
        assert order is not None
        assert order.id == 1
    
    def test_create_order_sell_insufficient_shares(
        self, service, mock_position_service
    ):
        """测试创建卖出订单持仓不足"""
        # Arrange
        mock_position_service.get_available_shares.return_value = 50
        
        # Act & Assert
        with pytest.raises(ValueError, match="可卖数量不足"):
            service.create_order(
                account_name="test_account",
                symbol="600000",
                name="浦发银行",
                action=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=12.0,
            )
    
    def test_create_order_invalid_quantity(self, service):
        """测试创建订单数量无效"""
        # Act & Assert
        with pytest.raises(ValueError, match="必须是100股的整数倍"):
            service.create_order(
                account_name="test_account",
                symbol="600000",
                name="浦发银行",
                action=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=150,  # 不是100的整数倍
                price=10.0,
            )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/domain/trading/test_order_service.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add domain/trading/services/ tests/domain/trading/
git commit -m "feat(trading): add OrderService with order lifecycle management"
```

---

## Phase 2: Integration - Connect Domains (Tasks 5-7)

### Task 5: Create SimulationRepository adapter implementing IAccountRepository

**Files:**
- Create: `adapters/outbound/repositories/simulation_account_repository.py`
- Create: `tests/adapters/outbound/repositories/test_simulation_account_repository.py`

- [ ] **Step 1: Create adapter**

```python
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
```

- [ ] **Step 2: Write tests**

```python
# tests/adapters/outbound/repositories/test_simulation_account_repository.py
import pytest
from unittest.mock import Mock, MagicMock
from adapters.outbound.repositories.simulation_account_repository import SimulationAccountRepository

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
        mock_sim_repo.get_account.return_value = orm_account
        
        # Act
        account = repo.get_account("test_account")
        
        # Assert
        assert account is not None
        assert account.account_name == "test_account"
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/adapters/outbound/repositories/test_simulation_account_repository.py -v
```

- [ ] **Step 4: Commit**

```bash
git add adapters/outbound/repositories/simulation_account_repository.py
git add tests/adapters/outbound/repositories/test_simulation_account_repository.py
git commit -m "feat(accounts): add SimulationAccountRepository adapter"
```

---

### Task 6: Create SimulationPositionRepository adapter implementing IPositionRepository

**Files:**
- Create: `adapters/outbound/repositories/simulation_position_repository.py`
- Create: `tests/adapters/outbound/repositories/test_simulation_position_repository.py`

- [ ] **Step 1: Create adapter**

```python
# adapters/outbound/repositories/simulation_position_repository.py
"""
SimulationPositionRepository - 适配 SimulationORMRepository 到 IPositionRepository 接口
"""
from typing import Optional, List
import structlog

from domain.portfolio.models.position import Position
from domain.portfolio.ports.IPositionRepository import IPositionRepository
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

logger = structlog.get_logger(__name__)


class SimulationPositionRepository(IPositionRepository):
    """基于 SimulationORMRepository 的 IPositionRepository 实现"""
    
    def __init__(self, sim_repo: Optional[SimulationORMRepository] = None):
        self.sim_repo = sim_repo or SimulationORMRepository()
    
    def get_position(
        self,
        account_name: str,
        symbol: str,
    ) -> Optional[Position]:
        """获取单只股票持仓"""
        orm_position = self.sim_repo.get_position(account_name, symbol)
        if not orm_position:
            return None
        
        return Position(
            account_name=orm_position.account_name,
            symbol=orm_position.symbol,
            shares_total=int(orm_position.shares_total or 0),
            shares_available=int(orm_position.shares_available or 0),
            avg_cost=float(orm_position.avg_cost or 0),
            current_price=float(orm_position.current_price or 0),
            market_value=float(orm_position.market_value or 0),
            unrealized_pnl=float(orm_position.unrealized_pnl or 0),
            unrealized_pnl_rate=float(orm_position.unrealized_pnl_rate or 0),
            created_at=orm_position.created_at,
            updated_at=orm_position.updated_at,
        )
    
    def get_all_positions(self, account_name: str) -> List[Position]:
        """获取账户所有持仓"""
        orm_positions = self.sim_repo.get_all_positions(account_name)
        return [
            Position(
                account_name=p.account_name,
                symbol=p.symbol,
                shares_total=int(p.shares_total or 0),
                shares_available=int(p.shares_available or 0),
                avg_cost=float(p.avg_cost or 0),
                current_price=float(p.current_price or 0),
                market_value=float(p.market_value or 0),
                unrealized_pnl=float(p.unrealized_pnl or 0),
                unrealized_pnl_rate=float(p.unrealized_pnl_rate or 0),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in orm_positions
        ]
    
    def upsert_position(
        self,
        account_name: str,
        symbol: str,
        shares_total: int,
        avg_cost: float,
        shares_available: int,
        current_price: float,
    ) -> bool:
        """创建或更新持仓"""
        return self.sim_repo.upsert_position(
            account_name=account_name,
            symbol=symbol,
            shares_total=shares_total,
            avg_cost=avg_cost,
            shares_available=shares_available,
            current_price=current_price,
            commit=True,
        )
    
    def delete_position(
        self,
        account_name: str,
        symbol: str,
    ) -> bool:
        """删除持仓（清仓时）"""
        return self.sim_repo.delete_position(
            account_name=account_name,
            symbol=symbol,
            commit=True,
        )
```

- [ ] **Step 2: Write tests**

```python
# tests/adapters/outbound/repositories/test_simulation_position_repository.py
import pytest
from unittest.mock import Mock
from adapters.outbound.repositories.simulation_position_repository import SimulationPositionRepository

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
        mock_sim_repo.get_position.return_value = orm_position
        
        # Act
        position = repo.get_position("test_account", "600000")
        
        # Assert
        assert position is not None
        assert position.shares_total == 100
        assert position.avg_cost == 10.0
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/adapters/outbound/repositories/test_simulation_position_repository.py -v
```

- [ ] **Step 4: Commit**

```bash
git add adapters/outbound/repositories/simulation_position_repository.py
git add tests/adapters/outbound/repositories/test_simulation_position_repository.py
git commit -m "feat(portfolio): add SimulationPositionRepository adapter"
```

---

### Task 7: Create domain service factory

**Files:**
- Create: `domain/service_factory.py`
- Create: `tests/domain/test_service_factory.py`

- [ ] **Step 1: Create service factory**

```python
# domain/service_factory.py
"""
领域服务工厂 - 创建和组装领域服务

负责创建领域服务实例并注入依赖。
"""
from typing import Optional
import structlog

from domain.accounts.services.account_service import AccountService
from domain.portfolio.services.position_service import PositionService
from domain.trading.services.order_service import OrderService

logger = structlog.get_logger(__name__)


class DomainServiceFactory:
    """领域服务工厂 - 单例模式"""
    
    _instance = None
    _account_service: Optional[AccountService] = None
    _position_service: Optional[PositionService] = None
    _order_service: Optional[OrderService] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(
        self,
        account_repo,
        position_repo,
        order_repo,
    ) -> None:
        """初始化领域服务
        
        Args:
            account_repo: IAccountRepository 实现
            position_repo: IPositionRepository 实现
            order_repo: IOrderRepository 实现
        """
        # 创建服务（按依赖顺序）
        self._account_service = AccountService(account_repo=account_repo)
        self._position_service = PositionService(position_repo=position_repo)
        self._order_service = OrderService(
            account_service=self._account_service,
            position_service=self._position_service,
            order_repo=order_repo,
        )
        
        logger.info("DomainServiceFactory initialized")
    
    @property
    def account_service(self) -> AccountService:
        """获取账户服务"""
        if self._account_service is None:
            raise RuntimeError("DomainServiceFactory not initialized. Call initialize() first.")
        return self._account_service
    
    @property
    def position_service(self) -> PositionService:
        """获取持仓服务"""
        if self._position_service is None:
            raise RuntimeError("DomainServiceFactory not initialized. Call initialize() first.")
        return self._position_service
    
    @property
    def order_service(self) -> OrderService:
        """获取订单服务"""
        if self._order_service is None:
            raise RuntimeError("DomainServiceFactory not initialized. Call initialize() first.")
        return self._order_service
    
    def reset(self) -> None:
        """重置工厂（用于测试）"""
        self._account_service = None
        self._position_service = None
        self._order_service = None
        DomainServiceFactory._instance = None


# 全局单例
domain_service_factory = DomainServiceFactory()
```

- [ ] **Step 2: Write tests**

```python
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
    
    def test_get_service_before_initialize_raises(self):
        """测试未初始化时获取服务抛出异常"""
        factory = DomainServiceFactory()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = factory.account_service
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/domain/test_service_factory.py -v
```

- [ ] **Step 4: Commit**

```bash
git add domain/service_factory.py tests/domain/test_service_factory.py
git commit -m "feat(domain): add DomainServiceFactory for service assembly"
```

---

## Phase 3: Migration - Replace Old Logic (Tasks 8-10)

### Task 8: Create legacy adapter for backward compatibility

**Files:**
- Create: `domain/legacy/legacy_order_adapter.py`
- Create: `tests/domain/legacy/test_legacy_order_adapter.py`

- [ ] **Step 1: Create legacy adapter**

```python
# domain/legacy/legacy_order_adapter.py
"""
Legacy Order Adapter - 适配旧的 order_service.py 到新的 OrderService

提供向后兼容，允许旧代码逐步迁移到新的领域服务。
"""
from typing import Optional, Dict, List
import structlog

from domain.trading.services.order_service import OrderService
from domain.trading.models.order import OrderSide, OrderType

logger = structlog.get_logger(__name__)


class LegacyOrderAdapter:
    """旧版订单接口适配器
    
    将旧的函数式接口适配到新的 OrderService 类接口。
    """
    
    def __init__(self, order_service: OrderService):
        self.order_service = order_service
    
    def create_order(
        self,
        symbol: str,
        action: str,
        order_type: str,
        quantity: int,
        price: float = None,
        reason: str = None,
        signal_id: int = None,
        account_name: str = None,
    ) -> int:
        """创建订单（兼容旧接口）
        
        Args:
            symbol: 股票代码
            action: 'buy' or 'sell'
            order_type: 'limit', 'market', or 'stop'
            quantity: 数量
            price: 价格
            reason: 原因
            signal_id: 信号ID
            account_name: 账户名称
            
        Returns:
            订单ID
        """
        # 转换参数
        order_side = OrderSide.BUY if action == 'buy' else OrderSide.SELL
        order_type_enum = OrderType(order_type)
        
        # 获取股票名称（需要从 stock_repo 获取）
        # TODO: 注入 stock_repo
        name = symbol  # 临时使用 symbol 作为 name
        
        order = self.order_service.create_order(
            account_name=account_name or "default",
            symbol=symbol,
            name=name,
            action=order_side,
            order_type=order_type_enum,
            quantity=quantity,
            price=price,
            reason=reason,
            signal_id=signal_id,
        )
        
        return order.id
    
    def fill_order(
        self,
        order_id: int,
        fill_price: float,
        fill_quantity: int = None,
    ) -> Dict:
        """成交订单（兼容旧接口）
        
        Returns:
            {
                'order': 更新后的订单,
                'trade_id': 成交记录ID,
                'filled_quantity': 成交数量,
                'is_full_fill': 是否全部成交,
            }
        """
        trade = self.order_service.fill_order(
            order_id=order_id,
            fill_price=fill_price,
            fill_quantity=fill_quantity,
        )
        
        order = self.order_service.get_order(order_id)
        
        return {
            'order': order.__dict__ if order else None,
            'trade_id': trade.id,
            'filled_quantity': trade.shares,
            'is_full_fill': order.status.value == 'filled' if order else False,
        }
    
    def cancel_order(self, order_id: int) -> bool:
        """取消订单（兼容旧接口）"""
        return self.order_service.cancel_order(order_id)
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        """获取订单（兼容旧接口）"""
        order = self.order_service.get_order(order_id)
        return order.__dict__ if order else None
    
    def list_orders(
        self,
        symbol: str = None,
        status: str = None,
        limit: int = 50,
    ) -> List[Dict]:
        """获取订单列表（兼容旧接口）"""
        from domain.trading.models.order import OrderStatus
        
        status_enum = OrderStatus(status) if status else None
        orders = self.order_service.list_orders(
            symbol=symbol,
            status=status_enum,
            limit=limit,
        )
        return [o.__dict__ for o in orders]
```

- [ ] **Step 2: Write tests**

```python
# tests/domain/legacy/test_legacy_order_adapter.py
import pytest
from unittest.mock import Mock
from domain.legacy.legacy_order_adapter import LegacyOrderAdapter

class TestLegacyOrderAdapter:
    """LegacyOrderAdapter 测试"""
    
    @pytest.fixture
    def mock_order_service(self):
        return Mock(spec=OrderService)
    
    @pytest.fixture
    def adapter(self, mock_order_service):
        return LegacyOrderAdapter(order_service=mock_order_service)
    
    def test_create_order(self, adapter, mock_order_service):
        """测试创建订单"""
        # Arrange
        mock_order = Mock()
        mock_order.id = 1
        mock_order_service.create_order.return_value = mock_order
        
        # Act
        order_id = adapter.create_order(
            symbol="600000",
            action="buy",
            order_type="limit",
            quantity=100,
            price=10.0,
            account_name="test_account",
        )
        
        # Assert
        assert order_id == 1
        mock_order_service.create_order.assert_called_once()
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/domain/legacy/test_legacy_order_adapter.py -v
```

- [ ] **Step 4: Commit**

```bash
git add domain/legacy/ tests/domain/legacy/
git commit -m "feat(legacy): add LegacyOrderAdapter for backward compatibility"
```

---

### Task 9: Update application layer to use new domain services

**Files:**
- Modify: `application/services/order_service.py` (逐步迁移)
- Create: `application/services/new_order_service.py` (新实现)

- [ ] **Step 1: Create new order service wrapper**

```python
# application/services/new_order_service.py
"""
新订单服务 - 使用领域服务实现

替代旧的 order_service.py，提供相同的公共接口但使用新的领域层。
"""
from typing import Optional, Dict, List
import structlog

from domain.service_factory import domain_service_factory
from domain.trading.models.order import OrderSide, OrderType, OrderStatus

logger = structlog.get_logger(__name__)


def create_order(
    symbol: str,
    action: str,
    order_type: str,
    quantity: int,
    price: float = None,
    reason: str = None,
    signal_id: int = None,
    account_name: str = None,
) -> int:
    """创建新订单
    
    这是新的实现，使用领域服务。
    """
    # 转换参数
    order_side = OrderSide.BUY if action == 'buy' else OrderSide.SELL
    order_type_enum = OrderType(order_type)
    
    # 获取股票名称
    # TODO: 从 stock_repo 获取
    name = symbol
    
    order = domain_service_factory.order_service.create_order(
        account_name=account_name or "default",
        symbol=symbol,
        name=name,
        action=order_side,
        order_type=order_type_enum,
        quantity=quantity,
        price=price,
        reason=reason,
        signal_id=signal_id,
    )
    
    return order.id


def fill_order(
    order_id: int,
    fill_price: float,
    fill_quantity: int = None,
) -> Dict:
    """成交订单"""
    trade = domain_service_factory.order_service.fill_order(
        order_id=order_id,
        fill_price=fill_price,
        fill_quantity=fill_quantity,
    )
    
    order = domain_service_factory.order_service.get_order(order_id)
    
    return {
        'order': order.__dict__ if order else None,
        'trade_id': trade.id,
        'filled_quantity': trade.shares,
        'is_full_fill': order.status == OrderStatus.FILLED if order else False,
    }


def cancel_order(order_id: int) -> bool:
    """取消订单"""
    return domain_service_factory.order_service.cancel_order(order_id)


def get_order(order_id: int) -> Optional[Dict]:
    """获取订单"""
    order = domain_service_factory.order_service.get_order(order_id)
    return order.__dict__ if order else None


def list_orders(
    symbol: str = None,
    status: str = None,
    limit: int = 50,
) -> List[Dict]:
    """获取订单列表"""
    status_enum = OrderStatus(status) if status else None
    orders = domain_service_factory.order_service.list_orders(
        symbol=symbol,
        status=status_enum,
        limit=limit,
    )
    return [o.__dict__ for o in orders]
```

- [ ] **Step 2: Write tests**

```python
# tests/application/services/test_new_order_service.py
import pytest
from unittest.mock import Mock, patch
from application.services.new_order_service import create_order, fill_order

class TestNewOrderService:
    """新订单服务测试"""
    
    @patch('application.services.new_order_service.domain_service_factory')
    def test_create_order(self, mock_factory):
        """测试创建订单"""
        # Arrange
        mock_order = Mock()
        mock_order.id = 1
        mock_factory.order_service.create_order.return_value = mock_order
        
        # Act
        order_id = create_order(
            symbol="600000",
            action="buy",
            order_type="limit",
            quantity=100,
            price=10.0,
            account_name="test_account",
        )
        
        # Assert
        assert order_id == 1
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/application/services/test_new_order_service.py -v
```

- [ ] **Step 4: Commit**

```bash
git add application/services/new_order_service.py
git add tests/application/services/test_new_order_service.py
git commit -m "feat(application): add new_order_service using domain services"
```

---

### Task 10: Create migration guide and deprecation plan

**Files:**
- Create: `docs/MIGRATION_GUIDE_ACCOUNTS_TRADING.md`

- [ ] **Step 1: Create migration guide**

```markdown
# Accounts & Trading Domain Migration Guide

## Overview

This guide documents the migration from the old monolithic `order_service.py` to the new domain-driven architecture.

## Architecture Changes

### Before (Old)
```
application/services/
├── order_service.py (1169 lines) - Orders + Positions + Funds
├── account_trading_service.py (427 lines) - Trading + Account
└── trade_service.py (289 lines) - Trades + Positions
```

### After (New)
```
domain/
├── accounts/         # Account + Balance
├── trading/          # Order + Trade
└── portfolio/        # Position

application/services/
├── new_order_service.py  # Uses domain services
└── ...
```

## Migration Steps

### Step 1: Initialize Domain Services

In your application startup (e.g., `start_all.py`):

```python
from domain.service_factory import domain_service_factory
from adapters.outbound.repositories.simulation_account_repository import SimulationAccountRepository
from adapters.outbound.repositories.simulation_position_repository import SimulationPositionRepository
from adapters.outbound.repositories.simulation_order_repository import SimulationOrderRepository

# Initialize domain services
domain_service_factory.initialize(
    account_repo=SimulationAccountRepository(),
    position_repo=SimulationPositionRepository(),
    order_repo=SimulationOrderRepository(),
)
```

### Step 2: Replace Old Imports

**Before:**
```python
from application.services.order_service import create_order, fill_order
```

**After:**
```python
from application.services.new_order_service import create_order, fill_order
```

### Step 3: Update Tests

Replace mocks of old services with mocks of domain services:

**Before:**
```python
@patch('application.services.order_service.ServiceFactory')
def test_create_order(mock_factory):
    mock_factory.get_portfolio_repository.return_value = Mock()
    ...
```

**After:**
```python
@patch('application.services.new_order_service.domain_service_factory')
def test_create_order(mock_factory):
    mock_factory.order_service.create_order.return_value = Mock(id=1)
    ...
```

## Deprecation Timeline

| Phase | Date | Action |
|-------|------|--------|
| 1 | Now | New domain services available |
| 2 | +2 weeks | Old order_service.py marked as deprecated |
| 3 | +1 month | Old order_service.py removed |

## Rollback Plan

If issues occur, revert to old imports:

```python
# Rollback to old service
from application.services.order_service import create_order, fill_order
```

## Testing

Run both old and new tests to ensure compatibility:

```bash
# Old tests (should still pass)
pytest tests/application/services/test_order_service.py -v

# New tests
pytest tests/domain/ tests/application/services/test_new_order_service.py -v
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/MIGRATION_GUIDE_ACCOUNTS_TRADING.md
git commit -m "docs: add migration guide for accounts and trading domains"
```

---

## Phase 4: Verification (Tasks 11-12)

### Task 11: Run all tests and verify

- [ ] **Step 1: Run domain tests**

```bash
pytest tests/domain/ -v
```

Expected: All tests PASS

- [ ] **Step 2: Run adapter tests**

```bash
pytest tests/adapters/outbound/repositories/ -v
```

Expected: All tests PASS

- [ ] **Step 3: Run application tests**

```bash
pytest tests/application/services/ -v
```

Expected: All tests PASS (old and new)

- [ ] **Step 4: Run full test suite**

```bash
pytest --tb=short
```

Expected: No regressions

- [ ] **Step 5: Commit verification results**

```bash
git add -A
git commit -m "test: verify all tests pass after domain refactoring"
```

---

### Task 12: Update documentation

- [ ] **Step 1: Update CLAUDE.md**

Add section about new domain architecture:

```markdown
## Domain Architecture

### accounts (账户领域)
- Models: Account, Balance
- Services: AccountService
- Location: `domain/accounts/`

### trading (交易领域)
- Models: Order, Trade
- Services: OrderService
- Location: `domain/trading/`

### portfolio (持仓领域)
- Models: Position
- Services: PositionService
- Location: `domain/portfolio/`
```

- [ ] **Step 2: Update README.md**

Add architecture diagram showing new domain structure.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update documentation with new domain architecture"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-4 | Create domain models, ports, and services |
| 2 | 5-7 | Create adapters and service factory |
| 3 | 8-10 | Migrate old code and create compatibility layer |
| 4 | 11-12 | Verify and document |

**Total Files Created:** ~30
**Total Files Modified:** ~5
**Estimated Time:** 4-6 hours
