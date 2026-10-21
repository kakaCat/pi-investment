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

## New Domain Structure

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

## Dependencies

```
trading → accounts + portfolio
accounts ←→ portfolio (no dependency)
```

## Key Benefits

1. **Clear Domain Boundaries**: Each domain has its own models and services
2. **Testability**: Services can be tested in isolation with mocked repositories
3. **Maintainability**: Code is organized by business domain, not technical layer
4. **Flexibility**: Easy to swap implementations (e.g., different database backends)
5. **Type Safety**: Domain models are strongly typed with enums
