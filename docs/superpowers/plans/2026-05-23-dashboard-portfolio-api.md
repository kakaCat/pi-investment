# Dashboard Portfolio API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build complete portfolio data management system with calculator engine, daily snapshot job, 5 API endpoints, and 90-day historical data backfill for React Dashboard.

**Architecture:** Pre-calculated daily snapshots stored in `account_balance` table, computed by `PortfolioCalculator` engine triggered by scheduled job. APIs read from pre-calculated data for optimal performance. Historical data backfilled via script.

**Tech Stack:** Python 3.x, Flask, PostgreSQL, APScheduler (or cron), pytest

---

## File Structure

### New Files to Create

**Core Engine:**
- `quantsys-v2/core/portfolio_calculator.py` - Asset calculation engine
- `quantsys-v2/tests/test_portfolio_calculator.py` - Unit tests for calculator

**Jobs:**
- `quantsys-v2/jobs/daily_snapshot_job.py` - Daily account snapshot task
- `quantsys-v2/jobs/__init__.py` - Jobs package init

**Scripts:**
- `quantsys-v2/scripts/backfill_portfolio_history.py` - Historical data backfill script
- `quantsys-v2/scripts/validate_backfill.py` - Data validation script

**Tests:**
- `quantsys-v2/tests/test_portfolio_api.py` - API integration tests

### Files to Modify

**API Server:**
- `quantsys-v2/api/server.py` - Add 3 new endpoints, adjust 2 existing

**Repository (if needed):**
- `quantsys-v2/repositories/risk_repository.py` - Add helper methods for account_balance queries

**Configuration:**
- `quantsys-v2/.env.example` - Add INITIAL_CASH configuration
- `quantsys-v2/config/scheduler_config.py` - Register daily snapshot job (if using APScheduler)

---

## Task Overview

1. **Setup & Configuration** - Environment variables, initial cash config
2. **Portfolio Calculator Engine** - Core calculation logic with TDD
3. **Repository Helper Methods** - Database query helpers
4. **Daily Snapshot Job** - Scheduled task implementation
5. **API Endpoints - Part 1** - `/api/portfolio/summary`
6. **API Endpoints - Part 2** - `/api/portfolio/history`
7. **API Endpoints - Part 3** - `/api/portfolio/holdings`
8. **API Endpoints - Part 4** - Adjust `/api/signals` and `/api/backtest/results`
9. **Data Backfill Script** - Historical data population
10. **Integration Testing** - End-to-end API tests
11. **Scheduler Integration** - Register job with scheduler
12. **Frontend Integration** - Update React Dashboard (optional, can be separate)

---


## Task 1: Setup & Configuration

**Files:**
- Modify: `quantsys-v2/.env.example`
- Create: `quantsys-v2/.env` (if not exists)

- [ ] **Step 1: Add INITIAL_CASH to .env.example**

```bash
# Portfolio Configuration
INITIAL_CASH=1000000.0
```

- [ ] **Step 2: Copy to .env if not exists**

```bash
cd quantsys-v2
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env file"
fi
```

- [ ] **Step 3: Verify configuration loads**

Create test file `test_config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

initial_cash = float(os.getenv('INITIAL_CASH', 1000000.0))
print(f"Initial cash: {initial_cash}")
assert initial_cash > 0
```

Run: `python test_config.py`
Expected: "Initial cash: 1000000.0"

- [ ] **Step 4: Clean up test file**

```bash
rm test_config.py
```

- [ ] **Step 5: Commit**

```bash
git add .env.example
git commit -m "config: add INITIAL_CASH configuration for portfolio calculator"
```

---

## Task 2: Portfolio Calculator Engine - Part 1 (Setup & Basic Structure)

**Files:**
- Create: `quantsys-v2/core/portfolio_calculator.py`
- Create: `quantsys-v2/tests/test_portfolio_calculator.py`

- [ ] **Step 1: Write failing test for calculator initialization**

Create `tests/test_portfolio_calculator.py`:

```python
import pytest
from datetime import date
from core.portfolio_calculator import PortfolioCalculator


class TestPortfolioCalculator:
    
    def test_calculator_initialization(self):
        """Test calculator initializes with default initial cash"""
        calculator = PortfolioCalculator()
        
        assert calculator.initial_cash == 1000000.0
    
    def test_calculator_initialization_with_custom_cash(self):
        """Test calculator initializes with custom initial cash"""
        calculator = PortfolioCalculator(initial_cash=500000.0)
        
        assert calculator.initial_cash == 500000.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
pytest tests/test_portfolio_calculator.py::TestPortfolioCalculator::test_calculator_initialization -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'core.portfolio_calculator'"

- [ ] **Step 3: Create calculator class skeleton**

Create `core/portfolio_calculator.py`:

```python
"""
Portfolio Calculator Engine

Calculates portfolio metrics including total assets, P&L, returns, and position statistics.
"""
import os
from datetime import date, timedelta
from typing import Dict, Optional
import logging

from repositories.portfolio_repository import PortfolioRepository
from repositories.kline_repository import KlineRepository
from repositories.risk_repository import RiskRepository

logger = logging.getLogger(__name__)


class PortfolioCalculator:
    """Investment portfolio calculation engine"""
    
    def __init__(self, initial_cash: float = None):
        """
        Initialize calculator
        
        Args:
            initial_cash: Initial capital, defaults to INITIAL_CASH env var or 1000000.0
        """
        if initial_cash is None:
            initial_cash = float(os.getenv('INITIAL_CASH', 1000000.0))
        
        self.initial_cash = initial_cash
        self.portfolio_repo = PortfolioRepository()
        self.kline_repo = KlineRepository()
        self.risk_repo = RiskRepository()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_portfolio_calculator.py::TestPortfolioCalculator::test_calculator_initialization -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/portfolio_calculator.py tests/test_portfolio_calculator.py
git commit -m "feat: add PortfolioCalculator class skeleton with initialization"
```

---

## Task 3: Portfolio Calculator Engine - Part 2 (Cash Balance Calculation)

**Files:**
- Modify: `quantsys-v2/core/portfolio_calculator.py`
- Modify: `quantsys-v2/tests/test_portfolio_calculator.py`

- [ ] **Step 1: Write failing test for cash balance calculation**

Append to `tests/test_portfolio_calculator.py`:

```python
from unittest.mock import Mock, patch


class TestPortfolioCalculator:
    # ... existing tests ...
    
    def test_calculate_cash_balance_no_trades(self):
        """Test cash balance equals initial cash when no trades"""
        calculator = PortfolioCalculator(initial_cash=1000000.0)
        
        # Mock portfolio_repo to return empty trades
        calculator.portfolio_repo.get_trades_by_date = Mock(return_value=[])
        
        cash = calculator.calculate_cash_balance(date(2026, 5, 23))
        
        assert cash == 1000000.0
    
    def test_calculate_cash_balance_with_buy_trade(self):
        """Test cash balance decreases after buy trade"""
        calculator = PortfolioCalculator(initial_cash=1000000.0)
        
        # Mock a buy trade
        mock_trades = [
            {
                'action': 'buy',
                'amount': 100000.0,
                'fee': 50.0,
                'stamp_duty': 0.0
            }
        ]
        calculator.portfolio_repo.get_trades_by_date = Mock(return_value=mock_trades)
        
        cash = calculator.calculate_cash_balance(date(2026, 5, 23))
        
        # 1000000 - 100000 - 50 = 899950
        assert cash == 899950.0
    
    def test_calculate_cash_balance_with_sell_trade(self):
        """Test cash balance increases after sell trade"""
        calculator = PortfolioCalculator(initial_cash=1000000.0)
        
        # Mock buy and sell trades
        mock_trades = [
            {
                'action': 'buy',
                'amount': 100000.0,
                'fee': 50.0,
                'stamp_duty': 0.0
            },
            {
                'action': 'sell',
                'amount': 110000.0,
                'fee': 55.0,
                'stamp_duty': 110.0
            }
        ]
        calculator.portfolio_repo.get_trades_by_date = Mock(return_value=mock_trades)
        
        cash = calculator.calculate_cash_balance(date(2026, 5, 23))
        
        # 1000000 - 100000 - 50 + 110000 - 55 - 110 = 1009785
        assert cash == 1009785.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_portfolio_calculator.py::TestPortfolioCalculator::test_calculate_cash_balance_no_trades -v
```

Expected: FAIL with "AttributeError: 'PortfolioCalculator' object has no attribute 'calculate_cash_balance'"

- [ ] **Step 3: Implement calculate_cash_balance method**

Add to `core/portfolio_calculator.py`:

```python
class PortfolioCalculator:
    # ... existing code ...
    
    def calculate_cash_balance(self, snapshot_date: date) -> float:
        """
        Calculate cash balance up to snapshot date
        
        Cash = Initial Cash - Buy Amount + Sell Amount - Fees
        
        Args:
            snapshot_date: Date to calculate cash balance for
            
        Returns:
            Cash balance
        """
        # Get all trades up to snapshot_date
        trades = self.portfolio_repo.get_trades_by_date(
            start_date='2020-01-01',  # From very early date
            end_date=snapshot_date.strftime('%Y-%m-%d')
        )
        
        cash = self.initial_cash
        
        for trade in trades:
            if trade['action'] == 'buy':
                # Buy: decrease cash
                cash -= trade['amount']
                cash -= trade.get('fee', 0.0)
                cash -= trade.get('stamp_duty', 0.0)
            elif trade['action'] == 'sell':
                # Sell: increase cash
                cash += trade['amount']
                cash -= trade.get('fee', 0.0)
                cash -= trade.get('stamp_duty', 0.0)
        
        return cash
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_portfolio_calculator.py::TestPortfolioCalculator::test_calculate_cash_balance -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/portfolio_calculator.py tests/test_portfolio_calculator.py
git commit -m "feat: implement cash balance calculation in PortfolioCalculator"
```

---


## Task 4: Portfolio Calculator Engine - Part 3 (Market Value & Complete Snapshot)

**Files:**
- Modify: `quantsys-v2/core/portfolio_calculator.py`
- Modify: `quantsys-v2/tests/test_portfolio_calculator.py`

- [ ] **Step 1: Write failing test for market value calculation**

Append to `tests/test_portfolio_calculator.py`:

```python
class TestPortfolioCalculator:
    # ... existing tests ...
    
    def test_calculate_market_value_no_holdings(self):
        """Test market value is zero when no holdings"""
        calculator = PortfolioCalculator()
        
        calculator.portfolio_repo.get_all_holdings = Mock(return_value=[])
        
        market_value = calculator.calculate_market_value(date(2026, 5, 23))
        
        assert market_value == 0.0
    
    def test_calculate_market_value_with_holdings(self):
        """Test market value calculation with holdings"""
        calculator = PortfolioCalculator()
        
        # Mock holdings
        mock_holdings = [
            {'symbol': '600519.SH', 'quantity': 100, 'avg_cost': 1650.0},
            {'symbol': '000858.SZ', 'quantity': 500, 'avg_cost': 150.0}
        ]
        calculator.portfolio_repo.get_all_holdings = Mock(return_value=mock_holdings)
        
        # Mock prices
        def mock_get_close_price(symbol, trade_date):
            prices = {'600519.SH': 1680.0, '000858.SZ': 152.0}
            return prices.get(symbol)
        
        calculator.kline_repo.get_close_price = Mock(side_effect=mock_get_close_price)
        
        market_value = calculator.calculate_market_value(date(2026, 5, 23))
        
        # 100 * 1680 + 500 * 152 = 168000 + 76000 = 244000
        assert market_value == 244000.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_portfolio_calculator.py::TestPortfolioCalculator::test_calculate_market_value_no_holdings -v
```

Expected: FAIL with "AttributeError: 'PortfolioCalculator' object has no attribute 'calculate_market_value'"

- [ ] **Step 3: Implement calculate_market_value method**

Add to `core/portfolio_calculator.py`:

```python
class PortfolioCalculator:
    # ... existing code ...
    
    def calculate_market_value(self, snapshot_date: date) -> float:
        """
        Calculate total market value of holdings
        
        Market Value = Σ(quantity × current_price)
        
        Args:
            snapshot_date: Date to calculate market value for
            
        Returns:
            Total market value
        """
        holdings = self.portfolio_repo.get_all_holdings()
        
        total_market_value = 0.0
        
        for holding in holdings:
            # Get close price for snapshot date
            price = self.kline_repo.get_close_price(
                symbol=holding['symbol'],
                trade_date=snapshot_date
            )
            
            if price is None:
                # Price missing, use avg_cost as fallback
                price = holding['avg_cost']
                logger.warning(
                    f"Price missing for {holding['symbol']} on {snapshot_date}, "
                    f"using avg_cost {price}"
                )
            
            market_value = holding['quantity'] * price
            total_market_value += market_value
        
        return total_market_value
    
    def get_position_count(self) -> int:
        """Get number of positions"""
        holdings = self.portfolio_repo.get_all_holdings()
        return len(holdings)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_portfolio_calculator.py::TestPortfolioCalculator::test_calculate_market_value -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Write failing test for complete snapshot calculation**

Append to `tests/test_portfolio_calculator.py`:

```python
class TestPortfolioCalculator:
    # ... existing tests ...
    
    def test_calculate_snapshot(self):
        """Test complete snapshot calculation"""
        calculator = PortfolioCalculator(initial_cash=1000000.0)
        
        # Mock cash balance
        calculator.calculate_cash_balance = Mock(return_value=900000.0)
        
        # Mock market value
        calculator.calculate_market_value = Mock(return_value=244000.0)
        
        # Mock position count
        calculator.get_position_count = Mock(return_value=2)
        
        # Mock previous balance (for daily return calculation)
        calculator.risk_repo.get_balance_by_date = Mock(return_value={
            'total_assets': 1100000.0
        })
        
        snapshot = calculator.calculate_snapshot(date(2026, 5, 23))
        
        assert snapshot['balance_date'] == date(2026, 5, 23)
        assert snapshot['cash'] == 900000.0
        assert snapshot['market_value'] == 244000.0
        assert snapshot['total_assets'] == 1144000.0  # 900000 + 244000
        assert snapshot['position_count'] == 2
        assert snapshot['total_pnl'] == 144000.0  # 1144000 - 1000000
        assert abs(snapshot['total_return'] - 14.4) < 0.01  # (144000 / 1000000) * 100
        assert snapshot['daily_pnl'] == 44000.0  # 1144000 - 1100000
        assert abs(snapshot['daily_return'] - 4.0) < 0.01  # (44000 / 1100000) * 100
```

- [ ] **Step 6: Run test to verify it fails**

```bash
pytest tests/test_portfolio_calculator.py::TestPortfolioCalculator::test_calculate_snapshot -v
```

Expected: FAIL with "AttributeError: 'PortfolioCalculator' object has no attribute 'calculate_snapshot'"

- [ ] **Step 7: Implement calculate_snapshot method**

Add to `core/portfolio_calculator.py`:

```python
class PortfolioCalculator:
    # ... existing code ...
    
    def calculate_snapshot(self, snapshot_date: date) -> Dict:
        """
        Calculate complete account snapshot for given date
        
        Args:
            snapshot_date: Date to calculate snapshot for
            
        Returns:
            Complete snapshot dictionary
        """
        # 1. Calculate cash and market value
        cash = self.calculate_cash_balance(snapshot_date)
        market_value = self.calculate_market_value(snapshot_date)
        total_assets = cash + market_value
        
        # 2. Get previous day's assets for daily return calculation
        previous_date = snapshot_date - timedelta(days=1)
        previous_balance = self.risk_repo.get_balance_by_date(previous_date)
        
        if previous_balance:
            previous_assets = previous_balance['total_assets']
            daily_pnl = total_assets - previous_assets
            daily_return = (daily_pnl / previous_assets) * 100 if previous_assets > 0 else 0.0
        else:
            daily_pnl = 0.0
            daily_return = 0.0
        
        # 3. Calculate total P&L
        total_pnl = total_assets - self.initial_cash
        total_return = (total_pnl / self.initial_cash) * 100 if self.initial_cash > 0 else 0.0
        
        # 4. Get position count
        position_count = self.get_position_count()
        
        # 5. Assemble snapshot
        snapshot = {
            'balance_date': snapshot_date,
            'cash': cash,
            'market_value': market_value,
            'total_assets': total_assets,
            'daily_pnl': daily_pnl,
            'daily_return': daily_return,
            'total_pnl': total_pnl,
            'total_return': total_return,
            'position_count': position_count
        }
        
        return snapshot
```

- [ ] **Step 8: Run test to verify it passes**

```bash
pytest tests/test_portfolio_calculator.py::TestPortfolioCalculator::test_calculate_snapshot -v
```

Expected: PASS

- [ ] **Step 9: Run all calculator tests**

```bash
pytest tests/test_portfolio_calculator.py -v
```

Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
git add core/portfolio_calculator.py tests/test_portfolio_calculator.py
git commit -m "feat: implement market value and complete snapshot calculation"
```

---

## Task 5: Repository Helper Methods

**Files:**
- Modify: `quantsys-v2/repositories/risk_repository.py`

- [ ] **Step 1: Check if get_balance_by_date exists**

```bash
grep -n "def get_balance_by_date" quantsys-v2/repositories/risk_repository.py
```

If method exists, skip to Step 5. If not, continue.

- [ ] **Step 2: Add get_balance_by_date method**

Add to `repositories/risk_repository.py`:

```python
class RiskRepository(BaseRepository):
    # ... existing code ...
    
    def get_balance_by_date(self, balance_date: date) -> Optional[Dict]:
        """
        Get account balance for specific date
        
        Args:
            balance_date: Date to query
            
        Returns:
            Balance record or None if not found
        """
        query = """
            SELECT *
            FROM quant.account_balance
            WHERE balance_date = %s
        """
        
        cursor = self.db.cursor()
        cursor.execute(query, (balance_date,))
        result = cursor.fetchone()
        cursor.close()
        
        return dict(result) if result else None
    
    def get_latest_balance(self) -> Optional[Dict]:
        """
        Get most recent account balance
        
        Returns:
            Latest balance record or None if table is empty
        """
        query = """
            SELECT *
            FROM quant.account_balance
            ORDER BY balance_date DESC
            LIMIT 1
        """
        
        cursor = self.db.cursor()
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        
        return dict(result) if result else None
    
    def save_balance(self, balance_data: Dict) -> bool:
        """
        Save account balance snapshot
        
        Args:
            balance_data: Balance data dictionary
            
        Returns:
            True if successful
        """
        query = """
            INSERT INTO quant.account_balance (
                balance_date, cash, market_value, total_assets,
                daily_pnl, daily_return, total_pnl, total_return, position_count
            ) VALUES (
                %(balance_date)s, %(cash)s, %(market_value)s, %(total_assets)s,
                %(daily_pnl)s, %(daily_return)s, %(total_pnl)s, %(total_return)s, %(position_count)s
            )
            ON CONFLICT (balance_date)
            DO UPDATE SET
                cash = EXCLUDED.cash,
                market_value = EXCLUDED.market_value,
                total_assets = EXCLUDED.total_assets,
                daily_pnl = EXCLUDED.daily_pnl,
                daily_return = EXCLUDED.daily_return,
                total_pnl = EXCLUDED.total_pnl,
                total_return = EXCLUDED.total_return,
                position_count = EXCLUDED.position_count
        """
        
        cursor = self.db.cursor()
        try:
            cursor.execute(query, balance_data)
            self.db.commit()
            cursor.close()
            return True
        except Exception as e:
            self.db.rollback()
            cursor.close()
            raise Exception(f"Failed to save balance: {str(e)}")
    
    def get_history(self, days: int = 30) -> List[Dict]:
        """
        Get account balance history for recent days
        
        Args:
            days: Number of days to retrieve
            
        Returns:
            List of balance records
        """
        query = """
            SELECT *
            FROM quant.account_balance
            WHERE balance_date >= CURRENT_DATE - INTERVAL '%s days'
            ORDER BY balance_date ASC
        """
        
        cursor = self.db.cursor()
        cursor.execute(query, (days,))
        results = cursor.fetchall()
        cursor.close()
        
        return [dict(row) for row in results]
```

- [ ] **Step 3: Verify methods are added**

```bash
grep -n "def get_balance_by_date\|def get_latest_balance\|def save_balance\|def get_history" quantsys-v2/repositories/risk_repository.py
```

Expected: Should show line numbers for all 4 methods

- [ ] **Step 4: Test methods manually (optional)**

Create test script `test_risk_repo.py`:

```python
from repositories.risk_repository import RiskRepository
from datetime import date

repo = RiskRepository()

# Test get_latest_balance
latest = repo.get_latest_balance()
print(f"Latest balance: {latest}")

# Test get_history
history = repo.get_history(days=7)
print(f"History count: {len(history)}")
```

Run: `python test_risk_repo.py`
Then: `rm test_risk_repo.py`

- [ ] **Step 5: Commit**

```bash
git add repositories/risk_repository.py
git commit -m "feat: add account balance query and save methods to RiskRepository"
```

---

## Task 6: Daily Snapshot Job

**Files:**
- Create: `quantsys-v2/jobs/__init__.py`
- Create: `quantsys-v2/jobs/daily_snapshot_job.py`

- [ ] **Step 1: Create jobs package**

```bash
mkdir -p quantsys-v2/jobs
touch quantsys-v2/jobs/__init__.py
```

- [ ] **Step 2: Create daily snapshot job**

Create `jobs/daily_snapshot_job.py`:

```python
"""
Daily Account Snapshot Job

Calculates and saves daily portfolio snapshot to account_balance table.
Runs every trading day after market close.
"""
from datetime import date
import logging

from core.portfolio_calculator import PortfolioCalculator
from repositories.risk_repository import RiskRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DailySnapshotJob:
    """Daily account snapshot task"""
    
    def __init__(self):
        self.calculator = PortfolioCalculator()
        self.risk_repo = RiskRepository()
    
    def is_trading_day(self, check_date: date) -> bool:
        """
        Check if date is a trading day
        
        Args:
            check_date: Date to check
            
        Returns:
            True if trading day
        """
        # Exclude weekends
        if check_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            return False
        
        # TODO: Add holiday exclusion logic
        
        return True
    
    def run(self):
        """Execute daily snapshot task"""
        try:
            logger.info("Starting daily snapshot job...")
            
            # 1. Check if today is a trading day
            today = date.today()
            if not self.is_trading_day(today):
                logger.info(f"{today} is not a trading day, skipping...")
                return
            
            # 2. Check if snapshot already exists
            existing = self.risk_repo.get_balance_by_date(today)
            if existing:
                logger.warning(f"Snapshot for {today} already exists, skipping...")
                return
            
            # 3. Calculate snapshot
            snapshot = self.calculator.calculate_snapshot(today)
            
            # 4. Save to database
            self.risk_repo.save_balance(snapshot)
            
            logger.info(
                f"Daily snapshot completed: "
                f"total_assets={snapshot['total_assets']:.2f}, "
                f"daily_return={snapshot['daily_return']:.2f}%"
            )
            
        except Exception as e:
            logger.error(f"Daily snapshot job failed: {str(e)}", exc_info=True)
            # TODO: Send error notification
            raise


def main():
    """Entry point for manual execution"""
    job = DailySnapshotJob()
    job.run()


if __name__ == '__main__':
    main()
```

- [ ] **Step 3: Test job manually**

```bash
cd quantsys-v2
python -m jobs.daily_snapshot_job
```

Expected: Job runs and logs output (may skip if not trading day or snapshot exists)

- [ ] **Step 4: Verify snapshot was created (if trading day)**

```bash
python -c "
from repositories.risk_repository import RiskRepository
from datetime import date

repo = RiskRepository()
snapshot = repo.get_balance_by_date(date.today())
print(f'Snapshot: {snapshot}')
"
```

Expected: Shows snapshot data or None

- [ ] **Step 5: Commit**

```bash
git add jobs/__init__.py jobs/daily_snapshot_job.py
git commit -m "feat: add daily account snapshot job"
```

---


## Task 7: API Endpoint - /api/portfolio/summary

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: Add portfolio summary endpoint**

Add to `api/server.py` (after existing endpoints):

```python
@app.route('/api/portfolio/summary', methods=['GET'])
@handle_api_error
def get_portfolio_summary():
    """Get portfolio summary metrics"""
    try:
        # 1. Get latest account balance
        latest_balance = ds.risk.get_latest_balance()
        
        if not latest_balance:
            return jsonify({
                'success': False,
                'error': 'No account balance data found. Please run data initialization.'
            }), 404
        
        # 2. Get all holdings
        holdings = ds.portfolio.get_all_holdings()
        
        # 3. Calculate profit/loss holdings count
        profit_count = 0
        loss_count = 0
        
        for holding in holdings:
            # Get latest price
            latest_kline = ds.kline.get_latest(holding['symbol'])
            if latest_kline:
                current_price = latest_kline['close']
                if current_price > holding['avg_cost']:
                    profit_count += 1
                elif current_price < holding['avg_cost']:
                    loss_count += 1
        
        # 4. Assemble response
        summary = {
            'totalValue': latest_balance['total_assets'],
            'dailyChange': latest_balance['daily_pnl'],
            'dailyChangePercent': latest_balance['daily_return'],
            'holdingsCount': len(holdings),
            'profitCount': profit_count,
            'lossCount': loss_count,
            'availableCash': latest_balance['cash'],
            'totalCost': latest_balance['total_assets'] - latest_balance['total_pnl'],
            'totalProfit': latest_balance['total_pnl'],
            'totalProfitPercent': latest_balance['total_return'],
            'lastUpdated': latest_balance['created_at'].isoformat() if latest_balance.get('created_at') else None
        }
        
        return api_response(summary)
        
    except Exception as e:
        logger.error(f"Failed to get portfolio summary: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 2: Test endpoint manually**

```bash
curl http://localhost:5000/api/portfolio/summary | jq
```

Expected: JSON response with portfolio summary or 404 if no data

- [ ] **Step 3: Commit**

```bash
git add api/server.py
git commit -m "feat: add GET /api/portfolio/summary endpoint"
```

---

## Task 8: API Endpoint - /api/portfolio/history

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: Add portfolio history endpoint**

Add to `api/server.py`:

```python
@app.route('/api/portfolio/history', methods=['GET'])
@handle_api_error
def get_portfolio_history():
    """Get portfolio value history"""
    try:
        # 1. Get query parameters
        days = request.args.get('days', 30, type=int)
        
        # Validate days parameter
        if days not in [7, 30, 90]:
            days = 30
        
        # 2. Get history data
        history = ds.risk.get_history(days=days)
        
        if not history:
            return api_response({
                'period': f'{days}d',
                'startDate': None,
                'endDate': None,
                'history': [],
                'summary': {
                    'totalReturn': 0.0,
                    'maxDrawdown': 0.0,
                    'volatility': 0.0
                }
            })
        
        # 3. Calculate summary metrics
        first_value = history[0]['total_assets']
        last_value = history[-1]['total_assets']
        total_return = ((last_value - first_value) / first_value) * 100 if first_value > 0 else 0.0
        
        # Calculate max drawdown
        max_drawdown = 0.0
        peak = history[0]['total_assets']
        for record in history:
            if record['total_assets'] > peak:
                peak = record['total_assets']
            drawdown = ((record['total_assets'] - peak) / peak) * 100 if peak > 0 else 0.0
            if drawdown < max_drawdown:
                max_drawdown = drawdown
        
        # Calculate volatility (standard deviation of daily returns)
        returns = [r['daily_return'] for r in history if r['daily_return'] is not None]
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = variance ** 0.5
        else:
            volatility = 0.0
        
        # 4. Format history data
        formatted_history = [
            {
                'date': record['balance_date'].isoformat() if hasattr(record['balance_date'], 'isoformat') else str(record['balance_date']),
                'totalAssets': record['total_assets'],
                'dailyReturn': record['daily_return'],
                'cash': record['cash'],
                'marketValue': record['market_value']
            }
            for record in history
        ]
        
        # 5. Assemble response
        response_data = {
            'period': f'{days}d',
            'startDate': formatted_history[0]['date'] if formatted_history else None,
            'endDate': formatted_history[-1]['date'] if formatted_history else None,
            'history': formatted_history,
            'summary': {
                'totalReturn': round(total_return, 2),
                'maxDrawdown': round(max_drawdown, 2),
                'volatility': round(volatility, 2)
            }
        }
        
        return api_response(response_data)
        
    except Exception as e:
        logger.error(f"Failed to get portfolio history: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 2: Test endpoint manually**

```bash
curl "http://localhost:5000/api/portfolio/history?days=30" | jq
```

Expected: JSON response with history data

- [ ] **Step 3: Test different day parameters**

```bash
curl "http://localhost:5000/api/portfolio/history?days=7" | jq
curl "http://localhost:5000/api/portfolio/history?days=90" | jq
```

Expected: Different amounts of history data

- [ ] **Step 4: Commit**

```bash
git add api/server.py
git commit -m "feat: add GET /api/portfolio/history endpoint"
```

---

## Task 9: API Endpoint - /api/portfolio/holdings

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: Add portfolio holdings endpoint**

Add to `api/server.py`:

```python
@app.route('/api/portfolio/holdings', methods=['GET'])
@handle_api_error
def get_portfolio_holdings():
    """Get current portfolio holdings with real-time prices"""
    try:
        # 1. Get all holdings
        holdings = ds.portfolio.get_all_holdings()
        
        if not holdings:
            return api_response({
                'holdings': [],
                'totalCount': 0,
                'totalMarketValue': 0.0,
                'totalCost': 0.0,
                'totalProfit': 0.0,
                'totalProfitPercent': 0.0
            })
        
        # 2. Enrich with current prices and calculations
        enriched_holdings = []
        total_market_value = 0.0
        total_cost = 0.0
        
        for holding in holdings:
            # Get latest price
            latest_kline = ds.kline.get_latest(holding['symbol'])
            
            if latest_kline:
                current_price = latest_kline['close']
            else:
                # Fallback to avg_cost if price not available
                current_price = holding['avg_cost']
                logger.warning(f"Price not available for {holding['symbol']}, using avg_cost")
            
            # Calculate metrics
            market_value = holding['quantity'] * current_price
            cost = holding['quantity'] * holding['avg_cost']
            profit = market_value - cost
            profit_percent = (profit / cost) * 100 if cost > 0 else 0.0
            
            enriched_holdings.append({
                'symbol': holding['symbol'],
                'name': holding['name'],
                'quantity': holding['quantity'],
                'avgCost': holding['avg_cost'],
                'currentPrice': current_price,
                'marketValue': market_value,
                'totalCost': cost,
                'profit': profit,
                'profitPercent': profit_percent,
                'market': holding['market'],
                'sector': holding.get('sector'),
                'addedDate': holding['added_date'].isoformat() if hasattr(holding['added_date'], 'isoformat') else str(holding['added_date'])
            })
            
            total_market_value += market_value
            total_cost += cost
        
        # 3. Calculate weights
        for holding in enriched_holdings:
            holding['weight'] = (holding['marketValue'] / total_market_value) * 100 if total_market_value > 0 else 0.0
        
        # 4. Sort by market value descending
        enriched_holdings.sort(key=lambda x: x['marketValue'], reverse=True)
        
        # 5. Assemble response
        response_data = {
            'holdings': enriched_holdings,
            'totalCount': len(enriched_holdings),
            'totalMarketValue': total_market_value,
            'totalCost': total_cost,
            'totalProfit': total_market_value - total_cost,
            'totalProfitPercent': ((total_market_value - total_cost) / total_cost) * 100 if total_cost > 0 else 0.0
        }
        
        return api_response(response_data)
        
    except Exception as e:
        logger.error(f"Failed to get portfolio holdings: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 2: Test endpoint manually**

```bash
curl http://localhost:5000/api/portfolio/holdings | jq
```

Expected: JSON response with holdings list

- [ ] **Step 3: Verify data structure**

Check that response includes:
- holdings array with symbol, name, quantity, prices, profit
- totalCount, totalMarketValue, totalCost, totalProfit

- [ ] **Step 4: Commit**

```bash
git add api/server.py
git commit -m "feat: add GET /api/portfolio/holdings endpoint"
```

---


## Task 10: API Endpoints - Adjust Existing Endpoints

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: Find existing /api/signals endpoint**

```bash
grep -n "@app.route('/api/signals'" quantsys-v2/api/server.py
```

Note the line number.

- [ ] **Step 2: Add date filter parameter to /api/signals**

Modify the `/api/signals` endpoint to add date filtering:

```python
@app.route('/api/signals', methods=['GET'])
@handle_api_error
def get_signals():
    """Get signals with optional date filtering"""
    try:
        days = request.args.get('days', type=int)
        date_filter = request.args.get('date')
        limit = request.args.get('limit', 100, type=int)
        
        if date_filter == 'today':
            # Query today's signals
            from datetime import datetime
            today = datetime.now().date()
            signals = ds.signal.get_signals_by_date_range(
                start_date=today.strftime('%Y-%m-%d'),
                end_date=today.strftime('%Y-%m-%d')
            )
        elif date_filter:
            # Query specific date
            signals = ds.signal.get_signals_by_date_range(
                start_date=date_filter,
                end_date=date_filter
            )
        elif days:
            # Backward compatible: query by days
            signals = ds.signal.get_latest_signals(days=days)
        else:
            # Default: get recent signals with limit
            signals = ds.signal.get_latest_signals(limit=limit)
        
        return jsonify({
            'success': True,
            'signals': sanitize_for_json(signals),
            'count': len(signals)
        })
        
    except Exception as e:
        logger.error(f"Failed to get signals: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 3: Test signals endpoint with date filter**

```bash
curl "http://localhost:5000/api/signals?date=today" | jq
curl "http://localhost:5000/api/signals?date=2026-05-23" | jq
curl "http://localhost:5000/api/signals?days=30" | jq  # backward compatible
```

Expected: Filtered signals based on date parameter

- [ ] **Step 4: Find existing /api/backtest/results endpoint**

```bash
grep -n "@app.route('/api/backtest/results'" quantsys-v2/api/server.py
```

Note the line number.

- [ ] **Step 5: Add limit parameter to /api/backtest/results**

Modify the `/api/backtest/results` endpoint:

```python
@app.route('/api/backtest/results', methods=['GET'])
@handle_api_error
def get_backtest_results():
    """Get backtest results with optional limit"""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        # Query backtest results with limit
        results = ds.backtest.get_recent_results(limit=limit)
        
        return jsonify({
            'success': True,
            'summary': sanitize_for_json(results),
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"Failed to get backtest results: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 6: Test backtest endpoint with limit**

```bash
curl "http://localhost:5000/api/backtest/results?limit=5" | jq
curl "http://localhost:5000/api/backtest/results?limit=10" | jq
```

Expected: Limited number of backtest results

- [ ] **Step 7: Commit**

```bash
git add api/server.py
git commit -m "feat: add date filter to /api/signals and limit to /api/backtest/results"
```

---

## Task 11: Data Backfill Script

**Files:**
- Create: `quantsys-v2/scripts/backfill_portfolio_history.py`

- [ ] **Step 1: Create backfill script**

Create `scripts/backfill_portfolio_history.py`:

```python
#!/usr/bin/env python3
"""
Backfill Portfolio History

Populates account_balance table with historical data.

Usage:
    python scripts/backfill_portfolio_history.py --days 90
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.portfolio_calculator import PortfolioCalculator
from repositories.risk_repository import RiskRepository
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_trading_day(check_date: date) -> bool:
    """Check if date is a trading day (exclude weekends)"""
    return check_date.weekday() < 5  # Monday=0, Friday=4


def backfill_history(days: int = 90):
    """
    Backfill historical account balance data
    
    Args:
        days: Number of days to backfill
    """
    calculator = PortfolioCalculator()
    risk_repo = RiskRepository()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    logger.info(f"Backfilling portfolio history from {start_date} to {end_date}")
    logger.info("=" * 60)
    
    current_date = start_date
    success_count = 0
    skip_count = 0
    error_count = 0
    
    while current_date <= end_date:
        try:
            # 1. Check if trading day
            if not is_trading_day(current_date):
                logger.debug(f"Skipping weekend: {current_date}")
                current_date += timedelta(days=1)
                skip_count += 1
                continue
            
            # 2. Check if already exists
            existing = risk_repo.get_balance_by_date(current_date)
            if existing:
                logger.debug(f"Snapshot already exists for {current_date}, skipping")
                current_date += timedelta(days=1)
                skip_count += 1
                continue
            
            # 3. Calculate snapshot
            snapshot = calculator.calculate_snapshot(current_date)
            
            # 4. Save to database
            risk_repo.save_balance(snapshot)
            
            logger.info(
                f"✓ {current_date}: "
                f"assets={snapshot['total_assets']:,.2f}, "
                f"return={snapshot['daily_return']:.2f}%"
            )
            success_count += 1
            
        except Exception as e:
            logger.error(f"✗ Failed to backfill {current_date}: {str(e)}")
            error_count += 1
        
        current_date += timedelta(days=1)
    
    # Summary
    logger.info("=" * 60)
    logger.info("Backfill completed:")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Skipped: {skip_count}")
    logger.info(f"  Errors:  {error_count}")
    logger.info("=" * 60)
    
    return success_count, skip_count, error_count


def main():
    parser = argparse.ArgumentParser(description='Backfill portfolio history')
    parser.add_argument(
        '--days',
        type=int,
        default=90,
        help='Number of days to backfill (default: 90)'
    )
    args = parser.parse_args()
    
    success, skipped, errors = backfill_history(args.days)
    
    # Exit with error code if any errors occurred
    sys.exit(1 if errors > 0 else 0)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Make script executable**

```bash
chmod +x quantsys-v2/scripts/backfill_portfolio_history.py
```

- [ ] **Step 3: Test backfill script (dry run with small range)**

```bash
cd quantsys-v2
python scripts/backfill_portfolio_history.py --days 7
```

Expected: Script runs and backfills last 7 days (or reports existing data)

- [ ] **Step 4: Run full backfill**

```bash
python scripts/backfill_portfolio_history.py --days 90
```

Expected: Backfills 90 days of historical data

- [ ] **Step 5: Verify backfilled data**

```bash
python -c "
from repositories.risk_repository import RiskRepository

repo = RiskRepository()
history = repo.get_history(days=90)
print(f'Backfilled records: {len(history)}')
if history:
    print(f'Earliest: {history[0][\"balance_date\"]}')
    print(f'Latest: {history[-1][\"balance_date\"]}')
"
```

Expected: Shows count and date range of backfilled data

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_portfolio_history.py
git commit -m "feat: add portfolio history backfill script"
```

---

## Task 12: Integration Testing

**Files:**
- Create: `quantsys-v2/tests/test_portfolio_api.py`

- [ ] **Step 1: Create API integration tests**

Create `tests/test_portfolio_api.py`:

```python
"""
Integration tests for Portfolio API endpoints
"""
import pytest
from api.server import app


class TestPortfolioAPI:
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_get_portfolio_summary(self, client):
        """Test GET /api/portfolio/summary"""
        response = client.get('/api/portfolio/summary')
        
        assert response.status_code in [200, 404]  # 404 if no data
        data = response.get_json()
        assert 'success' in data
        
        if response.status_code == 200:
            assert data['success'] is True
            assert 'data' in data
            assert 'totalValue' in data['data']
            assert 'holdingsCount' in data['data']
    
    def test_get_portfolio_history(self, client):
        """Test GET /api/portfolio/history"""
        response = client.get('/api/portfolio/history?days=30')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'history' in data['data']
        assert 'summary' in data['data']
    
    def test_get_portfolio_history_different_periods(self, client):
        """Test history with different day parameters"""
        for days in [7, 30, 90]:
            response = client.get(f'/api/portfolio/history?days={days}')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
    
    def test_get_portfolio_holdings(self, client):
        """Test GET /api/portfolio/holdings"""
        response = client.get('/api/portfolio/holdings')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'holdings' in data['data']
        assert 'totalCount' in data['data']
    
    def test_get_signals_with_date_filter(self, client):
        """Test GET /api/signals with date filter"""
        response = client.get('/api/signals?date=today')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'signals' in data
    
    def test_get_backtest_results_with_limit(self, client):
        """Test GET /api/backtest/results with limit"""
        response = client.get('/api/backtest/results?limit=5')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'summary' in data
```

- [ ] **Step 2: Run integration tests**

```bash
cd quantsys-v2
pytest tests/test_portfolio_api.py -v
```

Expected: All tests PASS (or SKIP if no data)

- [ ] **Step 3: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_portfolio_api.py
git commit -m "test: add integration tests for portfolio API endpoints"
```

---

## Final Steps

- [ ] **Step 1: Review all changes**

```bash
git log --oneline -20
```

Expected: Shows all commits from this implementation

- [ ] **Step 2: Run full test suite**

```bash
cd quantsys-v2
pytest tests/ -v --cov=core --cov=api --cov=jobs
```

Expected: All tests pass with good coverage

- [ ] **Step 3: Test all API endpoints manually**

```bash
# Test portfolio endpoints
curl http://localhost:5000/api/portfolio/summary | jq
curl http://localhost:5000/api/portfolio/history?days=30 | jq
curl http://localhost:5000/api/portfolio/holdings | jq

# Test adjusted endpoints
curl "http://localhost:5000/api/signals?date=today" | jq
curl "http://localhost:5000/api/backtest/results?limit=5" | jq
```

Expected: All endpoints return valid JSON responses

- [ ] **Step 4: Verify daily snapshot job works**

```bash
python -m jobs.daily_snapshot_job
```

Expected: Job runs successfully

- [ ] **Step 5: Create final summary commit (optional)**

```bash
git commit --allow-empty -m "feat: complete Dashboard Portfolio API implementation

- PortfolioCalculator engine with TDD
- Daily snapshot job for automated data updates
- 3 new API endpoints: summary, history, holdings
- 2 adjusted endpoints: signals (date filter), backtest (limit)
- 90-day historical data backfill script
- Comprehensive test coverage

Closes #[issue-number]"
```

---

## Scheduler Integration (Optional - Task 13)

**Note:** This task is optional and depends on your scheduler setup.

**If using APScheduler:**

- [ ] **Step 1: Add job to scheduler config**

Modify `config/scheduler_config.py` (or wherever scheduler is configured):

```python
from jobs.daily_snapshot_job import DailySnapshotJob

# Add to scheduler
scheduler.add_job(
    func=DailySnapshotJob().run,
    trigger='cron',
    hour=15,
    minute=30,
    id='daily_snapshot_job',
    name='Daily Account Snapshot',
    replace_existing=True
)
```

- [ ] **Step 2: Test scheduler**

Restart the scheduler and verify job is registered.

**If using cron:**

- [ ] **Step 1: Add crontab entry**

```bash
crontab -e
```

Add line:
```
30 15 * * 1-5 cd /path/to/quantsys-v2 && /path/to/python -m jobs.daily_snapshot_job
```

- [ ] **Step 2: Verify crontab**

```bash
crontab -l | grep daily_snapshot
```

Expected: Shows the cron entry

---

## Implementation Complete! 🎉

All tasks completed. The Dashboard Portfolio API system is now fully implemented with:

✅ Portfolio Calculator Engine (TDD)
✅ Daily Snapshot Job
✅ 5 API Endpoints (3 new + 2 adjusted)
✅ Historical Data Backfill (90 days)
✅ Comprehensive Tests
✅ Production Ready

**Next Steps:**
1. Frontend Integration - Update React Dashboard to use new APIs
2. Monitoring - Set up alerts for job failures
3. Documentation - Update API docs

