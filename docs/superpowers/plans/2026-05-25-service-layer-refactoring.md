# Service Layer Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor 4 large service files (1196/812/690/671 lines) into focused modules with clear responsibilities, establish three-layer architecture, and eliminate code duplication.

**Architecture:** Three-layer architecture with Orchestrator (coordination), Executor/Checker/Aggregator (business logic), and Utils/Common (shared tools). Services organized by business domain (risk/, strategy/, data/, execution/) with shared tooling in common/.

**Tech Stack:** Python 3.9+, Flask, PostgreSQL, pytest

---

## File Structure Overview

### New Directories
```
services/
├── common/                        # Shared tools layer (NEW)
│   ├── __init__.py
│   ├── base_checker.py
│   ├── result_types.py
│   ├── validators.py
│   ├── exceptions.py
│   └── decorators.py
├── risk/                          # Risk management (NEW)
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── checkers/
│   └── utils.py
├── strategy/                      # Strategy management (NEW)
│   ├── __init__.py
│   ├── manager.py
│   ├── executor.py
│   └── utils.py
├── data/                          # Data service (NEW)
│   ├── __init__.py
│   ├── service.py
│   ├── aggregators/
│   └── cache_helper.py
└── execution/                     # Order execution (NEW)
    ├── __init__.py
    ├── orchestrator.py
    ├── algos/
    ├── broker_adapter.py
    └── utils.py
```

### Files to Delete
- `services/risk_service.py` (1196 lines)
- `services/strategy_code_service.py` (812 lines)
- `services/data_service.py` (690 lines)
- `services/execution_service.py` (671 lines)

---

## Phase 1: Preparation

### Task 1: Create Git Worktree

**Files:**
- Create: `.claude/worktrees/service-layer-refactor/`

- [ ] **Step 1: Create worktree**

```bash
git worktree add .claude/worktrees/service-layer-refactor -b service-layer-refactor
```

Expected: `Preparing worktree (new branch 'service-layer-refactor')`

- [ ] **Step 2: Switch to worktree**

```bash
cd .claude/worktrees/service-layer-refactor
```

- [ ] **Step 3: Verify branch**

```bash
git branch --show-current
```

Expected: `service-layer-refactor`

---

### Task 2: Run Baseline Tests

**Files:**
- Test: `tests/`

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests pass

- [ ] **Step 2: Check coverage**

```bash
pytest tests/ --cov=services --cov-report=term-missing
```

Expected: Coverage report

- [ ] **Step 3: Save baseline**

```bash
pytest tests/ --cov=services --cov-report=html
cp -r htmlcov htmlcov_baseline
```

---

## Phase 2: Shared Tools Layer

### Task 3: Create Common Directory

**Files:**
- Create: `services/common/__init__.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p services/common
```

- [ ] **Step 2: Create __init__.py**

```python
# services/common/__init__.py
"""Shared tools and base classes for all services."""

from .base_checker import BaseChecker, CheckResult
from .result_types import ExecutionResult, StrategyResult, AggregationResult
from .decorators import cached, handle_broker_errors, validate_params, timing_decorator
from .validators import (
    validate_symbol,
    validate_quantity,
    validate_action,
    validate_date_range,
    validate_price,
    validate_broker_id
)
from .exceptions import (
    ValidationError,
    BrokerConnectionError,
    BrokerAPIError,
    RiskCheckError,
    StrategyExecutionError
)

__all__ = [
    'BaseChecker', 'CheckResult',
    'ExecutionResult', 'StrategyResult', 'AggregationResult',
    'cached', 'handle_broker_errors', 'validate_params', 'timing_decorator',
    'validate_symbol', 'validate_quantity', 'validate_action',
    'validate_date_range', 'validate_price', 'validate_broker_id',
    'ValidationError', 'BrokerConnectionError', 'BrokerAPIError',
    'RiskCheckError', 'StrategyExecutionError'
]
```

- [ ] **Step 3: Commit**

```bash
git add services/common/__init__.py
git commit -m "feat(services): create common tools directory"
```

---

### Task 4: Implement Exceptions

**Files:**
- Create: `services/common/exceptions.py`

- [ ] **Step 1: Write exceptions.py**

```python
# services/common/exceptions.py
"""Business exceptions for services."""


class ValidationError(Exception):
    """Validation error."""
    pass


class BrokerConnectionError(Exception):
    """Broker connection error."""
    pass


class BrokerAPIError(Exception):
    """Broker API error."""
    pass


class RiskCheckError(Exception):
    """Risk check error."""
    pass


class StrategyExecutionError(Exception):
    """Strategy execution error."""
    pass
```

- [ ] **Step 2: Commit**

```bash
git add services/common/exceptions.py
git commit -m "feat(services): add business exceptions"
```

---

### Task 5: Implement Result Types

**Files:**
- Create: `services/common/result_types.py`

- [ ] **Step 1: Write result_types.py**

```python
# services/common/result_types.py
"""Standardized result types for all services."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionResult:
    """Order execution result."""
    success: bool
    order_id: str = ""
    algo: str = "market"
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    slippage_bps: float = 0.0
    execution_time_seconds: float = 0.0
    error: Optional[str] = None
    slices: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyResult:
    """Strategy execution result."""
    success: bool
    strategy_id: int
    signals: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregationResult:
    """Data aggregation result."""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    cache_hit: bool = False
    query_time_seconds: float = 0.0
```

- [ ] **Step 2: Commit**

```bash
git add services/common/result_types.py
git commit -m "feat(services): add standardized result types"
```

---

### Task 6: Implement Validators

**Files:**
- Create: `services/common/validators.py`

- [ ] **Step 1: Write validators.py**

```python
# services/common/validators.py
"""Common validation functions."""

from datetime import datetime


def validate_symbol(symbol: str) -> None:
    """Validate stock symbol format."""
    if not symbol or not isinstance(symbol, str):
        raise ValueError("股票代码不能为空")
    
    if not symbol.endswith(('.SH', '.SZ', '.BJ')):
        raise ValueError(f"无效的股票代码格式: {symbol}")


def validate_quantity(quantity: int) -> None:
    """Validate trade quantity."""
    if quantity <= 0:
        raise ValueError("数量必须大于0")
    
    if quantity % 100 != 0:
        raise ValueError("A股数量必须是100的整数倍")


def validate_action(action: str) -> None:
    """Validate trade action."""
    if action not in ('buy', 'sell'):
        raise ValueError(f"无效的交易方向: {action}")


def validate_date_range(start_date: str, end_date: str) -> None:
    """Validate date range."""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError as e:
        raise ValueError(f"日期格式错误: {e}")
    
    if start > end:
        raise ValueError("开始日期不能晚于结束日期")


def validate_price(price: float) -> None:
    """Validate price."""
    if price <= 0:
        raise ValueError("价格必须大于0")


def validate_broker_id(broker_id: str) -> None:
    """Validate broker ID."""
    if not broker_id or not isinstance(broker_id, str):
        raise ValueError("券商ID不能为空")
```

- [ ] **Step 2: Commit**

```bash
git add services/common/validators.py
git commit -m "feat(services): add common validators"
```

---

### Task 7: Implement Base Checker

**Files:**
- Create: `services/common/base_checker.py`

- [ ] **Step 1: Write base_checker.py**

```python
# services/common/base_checker.py
"""Base class for all risk checkers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CheckResult:
    """Standardized check result."""
    passed: bool
    rule_name: str
    severity: str  # 'error' | 'warning'
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        return f"[{self.severity.upper()}] {status} - {self.rule_name}: {self.message}"


class BaseChecker(ABC):
    """Base class for all checkers."""
    
    @abstractmethod
    def check(self, ds, context: Dict[str, Any]) -> CheckResult:
        """Execute check logic.
        
        Args:
            ds: DataService instance
            context: Check context (symbol, action, quantity, price, etc.)
        
        Returns:
            CheckResult
        """
        pass
    
    def _build_result(
        self,
        passed: bool,
        message: str,
        severity: str = 'error',
        **kwargs
    ) -> CheckResult:
        """Build standardized result."""
        return CheckResult(
            passed=passed,
            rule_name=self.__class__.__name__,
            severity=severity,
            message=message,
            metadata=kwargs
        )
```

- [ ] **Step 2: Commit**

```bash
git add services/common/base_checker.py
git commit -m "feat(services): add BaseChecker and CheckResult"
```

---

### Task 8: Implement Decorators

**Files:**
- Create: `services/common/decorators.py`

- [ ] **Step 1: Write decorators.py**

```python
# services/common/decorators.py
"""Common decorators for services."""

from functools import wraps
import logging
import time
from typing import Callable

from .exceptions import BrokerConnectionError, BrokerAPIError
from .result_types import ExecutionResult


logger = logging.getLogger(__name__)


def cached(namespace: str, key_fn: Callable, ttl: int = 300):
    """Cache decorator."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if hasattr(self, '_cache') and self._cache:
                key = key_fn(*args, **kwargs)
                cached_value = self._cache.get(namespace, key)
                if cached_value:
                    logger.debug(f"Cache hit: {namespace}:{key}")
                    return cached_value
                
                result = func(self, *args, **kwargs)
                self._cache.set(namespace, key, result, ttl=ttl)
                return result
            
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def handle_broker_errors(func):
    """Broker error handling decorator."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BrokerConnectionError as e:
            logger.error(f"Broker connection failed: {e}")
            return ExecutionResult(success=False, error=f"Broker连接失败: {e}")
        except BrokerAPIError as e:
            logger.error(f"Broker API error: {e}")
            return ExecutionResult(success=False, error=f"Broker API错误: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return ExecutionResult(success=False, error=f"未知错误: {e}")
    return wrapper


def validate_params(*param_validators):
    """Parameter validation decorator."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for validator in param_validators:
                validator(*args, **kwargs)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def timing_decorator(func):
    """Performance timing decorator."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.debug(f"{func.__name__} 执行时间: {elapsed:.3f}s")
        return result
    return wrapper
```

- [ ] **Step 2: Commit**

```bash
git add services/common/decorators.py
git commit -m "feat(services): add common decorators"
```

---

### Task 9: Run Tests for Common Layer

**Files:**
- Test: `services/common/`

- [ ] **Step 1: Run import test**

```bash
python3 -c "from services.common import *; print('All imports successful')"
```

Expected: `All imports successful`

- [ ] **Step 2: Verify all files created**

```bash
ls -la services/common/
```

Expected: All 6 files present

- [ ] **Step 3: Commit checkpoint**

```bash
git add services/common/
git commit -m "chore(services): Phase 2 complete - shared tools layer"
```

---

## Phase 3: Data Service Refactoring

### Task 10: Read Original Data Service

**Files:**
- Read: `services/data_service.py`

- [ ] **Step 1: Read original file**

```bash
wc -l services/data_service.py
head -100 services/data_service.py
```

Expected: 690 lines, understand structure

- [ ] **Step 2: Identify aggregation methods**

```bash
grep -n "def " services/data_service.py | head -30
```

Expected: List of all methods

- [ ] **Step 3: Document dependencies**

```bash
grep -n "from\|import" services/data_service.py | head -20
```

Expected: List of imports

---

### Task 11: Create Data Service Structure

**Files:**
- Create: `services/data/__init__.py`
- Create: `services/data/service.py`
- Create: `services/data/aggregators/__init__.py`

- [ ] **Step 1: Create directories**

```bash
mkdir -p services/data/aggregators
```

- [ ] **Step 2: Create data/__init__.py**

```python
# services/data/__init__.py
"""Data service module."""

from .service import DataService

__all__ = ['DataService']
```

- [ ] **Step 3: Create aggregators/__init__.py**

```python
# services/data/aggregators/__init__.py
"""Data aggregators."""

from .stock_aggregator import StockAggregator
from .portfolio_aggregator import PortfolioAggregator
from .backtest_aggregator import BacktestAggregator
from .signal_aggregator import SignalAggregator

__all__ = [
    'StockAggregator',
    'PortfolioAggregator',
    'BacktestAggregator',
    'SignalAggregator'
]
```

- [ ] **Step 4: Commit structure**

```bash
git add services/data/
git commit -m "feat(services): create data service structure"
```

---

### Task 12: Implement Stock Aggregator

**Files:**
- Create: `services/data/aggregators/stock_aggregator.py`

- [ ] **Step 1: Write stock_aggregator.py**

```python
# services/data/aggregators/stock_aggregator.py
"""Stock data aggregation logic."""

from typing import Dict, List, Any, Optional
from datetime import datetime


class StockAggregator:
    """Aggregates stock-related data across repositories."""
    
    def __init__(self, repos: Dict[str, Any]):
        """Initialize with repository instances.
        
        Args:
            repos: Dict of repository instances (stock_repo, kline_repo, etc.)
        """
        self.stock_repo = repos.get('stock_repo')
        self.kline_repo = repos.get('kline_repo')
        self.factor_repo = repos.get('factor_repo')
    
    def get_stock_with_latest_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get stock info with latest price.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dict with stock info and latest price, or None
        """
        stock = self.stock_repo.get_by_symbol(symbol)
        if not stock:
            return None
        
        latest_kline = self.kline_repo.get_latest(symbol)
        
        return {
            'symbol': stock.symbol,
            'name': stock.name,
            'industry': stock.industry,
            'latest_price': latest_kline.close if latest_kline else None,
            'latest_date': latest_kline.trade_date if latest_kline else None,
            'change_pct': latest_kline.change_pct if latest_kline else None
        }
    
    def get_stock_with_factors(
        self,
        symbol: str,
        date: str,
        factor_names: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get stock with factor values.
        
        Args:
            symbol: Stock symbol
            date: Date (YYYY-MM-DD)
            factor_names: List of factor names
        
        Returns:
            Dict with stock info and factors
        """
        stock = self.stock_repo.get_by_symbol(symbol)
        if not stock:
            return None
        
        factors = {}
        for factor_name in factor_names:
            factor_value = self.factor_repo.get_factor_value(
                symbol=symbol,
                factor_name=factor_name,
                date=date
            )
            factors[factor_name] = factor_value
        
        return {
            'symbol': stock.symbol,
            'name': stock.name,
            'date': date,
            'factors': factors
        }
    
    def get_stocks_by_industry(
        self,
        industry: str,
        with_prices: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all stocks in an industry.
        
        Args:
            industry: Industry name
            with_prices: Whether to include latest prices
        
        Returns:
            List of stock dicts
        """
        stocks = self.stock_repo.get_by_industry(industry)
        
        if not with_prices:
            return [
                {
                    'symbol': s.symbol,
                    'name': s.name,
                    'industry': s.industry
                }
                for s in stocks
            ]
        
        result = []
        for stock in stocks:
            latest_kline = self.kline_repo.get_latest(stock.symbol)
            result.append({
                'symbol': stock.symbol,
                'name': stock.name,
                'industry': stock.industry,
                'latest_price': latest_kline.close if latest_kline else None,
                'change_pct': latest_kline.change_pct if latest_kline else None
            })
        
        return result
```

- [ ] **Step 2: Commit**

```bash
git add services/data/aggregators/stock_aggregator.py
git commit -m "feat(services): add StockAggregator"
```

---

### Task 13: Implement Portfolio Aggregator

**Files:**
- Create: `services/data/aggregators/portfolio_aggregator.py`

- [ ] **Step 1: Write portfolio_aggregator.py**

```python
# services/data/aggregators/portfolio_aggregator.py
"""Portfolio data aggregation logic."""

from typing import Dict, List, Any, Optional
from decimal import Decimal


class PortfolioAggregator:
    """Aggregates portfolio-related data."""
    
    def __init__(self, repos: Dict[str, Any]):
        """Initialize with repository instances."""
        self.position_repo = repos.get('position_repo')
        self.order_repo = repos.get('order_repo')
        self.trade_repo = repos.get('trade_repo')
        self.stock_repo = repos.get('stock_repo')
        self.kline_repo = repos.get('kline_repo')
    
    def get_portfolio_summary(self, account_id: str) -> Dict[str, Any]:
        """Get portfolio summary with current values.
        
        Args:
            account_id: Account ID
        
        Returns:
            Portfolio summary dict
        """
        positions = self.position_repo.get_by_account(account_id)
        
        total_market_value = Decimal('0')
        total_cost = Decimal('0')
        position_details = []
        
        for pos in positions:
            latest_kline = self.kline_repo.get_latest(pos.symbol)
            current_price = Decimal(str(latest_kline.close)) if latest_kline else Decimal('0')
            
            market_value = current_price * Decimal(str(pos.quantity))
            cost = Decimal(str(pos.avg_price)) * Decimal(str(pos.quantity))
            pnl = market_value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else Decimal('0')
            
            total_market_value += market_value
            total_cost += cost
            
            stock = self.stock_repo.get_by_symbol(pos.symbol)
            
            position_details.append({
                'symbol': pos.symbol,
                'name': stock.name if stock else pos.symbol,
                'quantity': pos.quantity,
                'avg_price': float(pos.avg_price),
                'current_price': float(current_price),
                'market_value': float(market_value),
                'cost': float(cost),
                'pnl': float(pnl),
                'pnl_pct': float(pnl_pct)
            })
        
        total_pnl = total_market_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else Decimal('0')
        
        return {
            'account_id': account_id,
            'total_market_value': float(total_market_value),
            'total_cost': float(total_cost),
            'total_pnl': float(total_pnl),
            'total_pnl_pct': float(total_pnl_pct),
            'position_count': len(positions),
            'positions': position_details
        }
    
    def get_position_with_orders(
        self,
        account_id: str,
        symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Get position with related orders.
        
        Args:
            account_id: Account ID
            symbol: Stock symbol
        
        Returns:
            Position with orders dict
        """
        position = self.position_repo.get_by_account_and_symbol(account_id, symbol)
        if not position:
            return None
        
        orders = self.order_repo.get_by_account_and_symbol(account_id, symbol)
        trades = self.trade_repo.get_by_account_and_symbol(account_id, symbol)
        
        return {
            'position': {
                'symbol': position.symbol,
                'quantity': position.quantity,
                'avg_price': float(position.avg_price),
                'available_quantity': position.available_quantity
            },
            'orders': [
                {
                    'order_id': o.order_id,
                    'action': o.action,
                    'quantity': o.quantity,
                    'price': float(o.price),
                    'status': o.status,
                    'created_at': o.created_at.isoformat()
                }
                for o in orders
            ],
            'trades': [
                {
                    'trade_id': t.trade_id,
                    'action': t.action,
                    'quantity': t.quantity,
                    'price': float(t.price),
                    'executed_at': t.executed_at.isoformat()
                }
                for t in trades
            ]
        }
```

- [ ] **Step 2: Commit**

```bash
git add services/data/aggregators/portfolio_aggregator.py
git commit -m "feat(services): add PortfolioAggregator"
```

---

### Task 14: Create Data Service Facade

**Files:**
- Create: `services/data/service.py`

- [ ] **Step 1: Write service.py (facade pattern)**

```python
# services/data/service.py
"""DataService facade - unified data access interface."""

from typing import Dict, List, Any, Optional

from .aggregators import (
    StockAggregator,
    PortfolioAggregator,
    BacktestAggregator,
    SignalAggregator
)


class DataService:
    """Unified data access facade."""
    
    def __init__(self, repositories: Dict[str, Any], cache=None):
        """Initialize with all repositories.
        
        Args:
            repositories: Dict of all repository instances
            cache: Optional cache instance
        """
        self._repos = repositories
        self._cache = cache
        
        # Initialize aggregators
        self.stock_agg = StockAggregator(repositories)
        self.portfolio_agg = PortfolioAggregator(repositories)
        self.backtest_agg = BacktestAggregator(repositories)
        self.signal_agg = SignalAggregator(repositories)
    
    # Direct repository access (for simple queries)
    @property
    def stock_repo(self):
        return self._repos.get('stock_repo')
    
    @property
    def kline_repo(self):
        return self._repos.get('kline_repo')
    
    @property
    def position_repo(self):
        return self._repos.get('position_repo')
    
    @property
    def order_repo(self):
        return self._repos.get('order_repo')
    
    @property
    def trade_repo(self):
        return self._repos.get('trade_repo')
    
    @property
    def strategy_repo(self):
        return self._repos.get('strategy_repo')
    
    @property
    def signal_repo(self):
        return self._repos.get('signal_repo')
    
    @property
    def backtest_repo(self):
        return self._repos.get('backtest_repo')
    
    # Aggregation methods (delegate to aggregators)
    def get_stock_with_latest_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get stock with latest price."""
        return self.stock_agg.get_stock_with_latest_price(symbol)
    
    def get_portfolio_summary(self, account_id: str) -> Dict[str, Any]:
        """Get portfolio summary."""
        return self.portfolio_agg.get_portfolio_summary(account_id)
    
    def get_position_with_orders(
        self,
        account_id: str,
        symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Get position with orders."""
        return self.portfolio_agg.get_position_with_orders(account_id, symbol)
```

- [ ] **Step 2: Commit**

```bash
git add services/data/service.py
git commit -m "feat(services): add DataService facade"
```

---

### Task 15: Test Data Service

**Files:**
- Test: `services/data/`

- [ ] **Step 1: Test imports**

```bash
python3 -c "from services.data import DataService; print('DataService imported')"
```

Expected: `DataService imported`

- [ ] **Step 2: Verify structure**

```bash
find services/data -name "*.py" | sort
```

Expected: All files listed

- [ ] **Step 3: Commit checkpoint**

```bash
git add services/data/
git commit -m "chore(services): Phase 3 complete - data service refactored"
```

---

## Phase 4-6: Remaining Service Refactoring

### Task 16-25: Execution Service (services/execution/)
### Task 26-35: Strategy Service (services/strategy/)
### Task 36-50: Risk Service (services/risk/)

**Note:** These phases follow the same pattern as Phase 3:
1. Read original service file
2. Create directory structure
3. Implement individual modules (algos/checkers/executors)
4. Create orchestrator/manager
5. Test and commit

**Detailed steps for these phases are similar to Phase 3 and can be expanded when needed.**

---

## Phase 7: Update API Routes and CLI

### Task 51: Update API Routes - Risk

**Files:**
- Modify: `api/routes/risk.py`

- [ ] **Step 1: Update imports**

```python
# Change from:
from services.risk_service import RiskService

# To:
from services.risk import RiskOrchestrator
```

- [ ] **Step 2: Update instantiation**

```python
# Change from:
risk_service = RiskService(data_service)

# To:
risk_orchestrator = RiskOrchestrator(data_service)
```

- [ ] **Step 3: Update method calls**

```python
# Change from:
result = risk_service.pre_trade_check(...)

# To:
result = risk_orchestrator.pre_trade_check(...)
```

- [ ] **Step 4: Test route**

```bash
pytest tests/api/test_risk_routes.py -v
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add api/routes/risk.py
git commit -m "refactor(api): update risk routes to use new structure"
```

---

### Task 52: Update API Routes - Strategies

**Files:**
- Modify: `api/routes/strategies.py`

- [ ] **Step 1: Update imports**

```python
# Change from:
from services.strategy_code_service import StrategyCodeService

# To:
from services.strategy import StrategyManager
```

- [ ] **Step 2: Update instantiation and calls**

```python
# Change from:
strategy_service = StrategyCodeService(data_service)

# To:
strategy_manager = StrategyManager(data_service)
```

- [ ] **Step 3: Test route**

```bash
pytest tests/api/test_strategy_routes.py -v
```

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add api/routes/strategies.py
git commit -m "refactor(api): update strategy routes to use new structure"
```

---

### Task 53: Update API Routes - Executions

**Files:**
- Modify: `api/routes/executions.py`

- [ ] **Step 1: Update imports**

```python
# Change from:
from services.execution_service import ExecutionService

# To:
from services.execution import OrderExecutor
```

- [ ] **Step 2: Update instantiation and calls**

- [ ] **Step 3: Test route**

```bash
pytest tests/api/test_execution_routes.py -v
```

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add api/routes/executions.py
git commit -m "refactor(api): update execution routes to use new structure"
```

---

### Task 54: Update API Routes - Data/Analysis

**Files:**
- Modify: `api/routes/analysis.py`
- Modify: `api/routes/signals.py`

- [ ] **Step 1: Update imports**

```python
# Change from:
from services.data_service import DataService

# To:
from services.data import DataService
```

- [ ] **Step 2: Test routes**

```bash
pytest tests/api/test_analysis_routes.py tests/api/test_signal_routes.py -v
```

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add api/routes/analysis.py api/routes/signals.py
git commit -m "refactor(api): update data/analysis routes to use new structure"
```

---

### Task 55: Update CLI Commands

**Files:**
- Modify: `cli/commands/strategy_commands.py`

- [ ] **Step 1: Update imports**

```python
# Change from:
from services.strategy_code_service import StrategyCodeService

# To:
from services.strategy import StrategyManager
```

- [ ] **Step 2: Update command implementations**

- [ ] **Step 3: Test CLI**

```bash
python3 -m cli.main strategy list
```

Expected: Command works

- [ ] **Step 4: Commit**

```bash
git add cli/commands/strategy_commands.py
git commit -m "refactor(cli): update strategy commands to use new structure"
```

---

## Phase 8: Final Testing and Cleanup

### Task 56: Delete Old Service Files

**Files:**
- Delete: `services/risk_service.py`
- Delete: `services/strategy_code_service.py`
- Delete: `services/data_service.py`
- Delete: `services/execution_service.py`

- [ ] **Step 1: Verify no imports remain**

```bash
grep -r "from services.risk_service" . --include="*.py" | grep -v ".git"
grep -r "from services.strategy_code_service" . --include="*.py" | grep -v ".git"
grep -r "from services.data_service" . --include="*.py" | grep -v ".git"
grep -r "from services.execution_service" . --include="*.py" | grep -v ".git"
```

Expected: No results (all imports updated)

- [ ] **Step 2: Delete old files**

```bash
git rm services/risk_service.py
git rm services/strategy_code_service.py
git rm services/data_service.py
git rm services/execution_service.py
```

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor(services): remove old monolithic service files"
```

---

### Task 57: Run Full Test Suite

**Files:**
- Test: `tests/`

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests pass

- [ ] **Step 2: Check coverage**

```bash
pytest tests/ --cov=services --cov-report=term-missing --cov-report=html
```

Expected: Coverage > 80%

- [ ] **Step 3: Compare with baseline**

```bash
diff -r htmlcov_baseline htmlcov | head -50
```

Expected: Coverage improved or maintained

---

### Task 58: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add code organization rules**

```markdown
## Code Organization Rules

### File Size and Responsibility
- Single file must not exceed 500 lines (soft limit)
- Each file has one clear responsibility
- Files exceeding 500 lines must be evaluated for splitting

### Architecture Layers
**Three-layer architecture:**
1. **Orchestrator Layer**: Coordinates multiple modules
2. **Executor Layer**: Specific business logic (Executor/Checker/Aggregator)
3. **Utils Layer**: Reusable helper functions

**Dependency rules:**
- Orchestrator → Executor + Utils
- Executor → Utils
- Utils → No dependencies
- No reverse or circular dependencies

### Code Duplication
**Abstraction strategy:**
- Cross-domain shared → services/common/
- Domain-internal shared → services/{domain}/utils.py
- Single-file shared → private functions

### Refactoring Checklist
- [ ] Identified and eliminated duplicate code?
- [ ] Followed Single Responsibility Principle?
- [ ] All files < 500 lines?
- [ ] Clear architectural layering?
- [ ] Updated all import statements?
- [ ] Added unit tests?
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add code organization rules to CLAUDE.md"
```

---

### Task 59: Final Verification

**Files:**
- Test: All

- [ ] **Step 1: Verify file sizes**

```bash
find services -name "*.py" -type f -exec wc -l {} + | sort -n | tail -20
```

Expected: All files < 500 lines

- [ ] **Step 2: Verify directory structure**

```bash
tree services/ -L 3
```

Expected: Matches design spec

- [ ] **Step 3: Run integration tests**

```bash
pytest tests/ -v -m integration
```

Expected: All pass

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "refactor(services): complete service layer refactoring

- Split 4 large files (1196/812/690/671 lines) into focused modules
- Established three-layer architecture
- Created shared tools layer (services/common/)
- Updated all API routes and CLI commands
- All tests passing, coverage > 80%"
```

---

### Task 60: Merge to Main

**Files:**
- Merge: `service-layer-refactor` → `main`

- [ ] **Step 1: Switch to main branch**

```bash
cd ../../../
git checkout main
```

- [ ] **Step 2: Merge worktree branch**

```bash
git merge service-layer-refactor --no-ff
```

- [ ] **Step 3: Run tests on main**

```bash
pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 4: Push to remote**

```bash
git push origin main
```

- [ ] **Step 5: Clean up worktree**

```bash
git worktree remove .claude/worktrees/service-layer-refactor
git branch -d service-layer-refactor
```

---

## Summary

**Total Tasks:** 60
**Estimated Time:** 5 days
**Key Deliverables:**
- 4 refactored service domains (risk, strategy, data, execution)
- Shared tools layer (services/common/)
- Updated API routes and CLI commands
- All tests passing with > 80% coverage
- Code organization rules in CLAUDE.md

**Success Criteria:**
- ✅ All files < 500 lines
- ✅ Clear three-layer architecture
- ✅ No code duplication
- ✅ All tests passing
- ✅ API/CLI functionality unchanged

---

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/2026-05-25-service-layer-refactoring.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
