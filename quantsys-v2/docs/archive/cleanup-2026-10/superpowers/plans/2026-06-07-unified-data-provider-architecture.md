# Unified Data Provider Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all direct `akshare` imports to a unified `DataProviderManager` in `infrastructure/data_providers/`, consolidating multi-source failover patterns across all data domains.

**Architecture:** Create unified infrastructure layer coordinating 5 provider domains (quote, financial, dividend, market, stock) with automatic failover, health tracking, and source attribution. Pattern inspired by existing `RealtimeQuoteService`.

**Tech Stack:** Python 3.13, dataclasses, ABC, pytest, existing providers

**Spec Reference:** `docs/superpowers/specs/2026-06-07-unified-data-provider-architecture-design.md`

---

## Implementation Phases

This plan is divided into 4 phases matching the spec:
1. **Phase 1:** Create base infrastructure (models, interfaces, manager)
2. **Phase 2:** Migrate existing providers to new structure
3. **Phase 3:** Refactor 9 service files (21 methods)
4. **Phase 4:** Cleanup old code

Each phase can be executed by a separate subagent for parallel work.

---

## Phase 1: Foundation - Base Infrastructure

### Task 1.1: Create Data Models and Base Classes

**Files:**
- Create: `infrastructure/data_providers/models.py`
- Create: `infrastructure/data_providers/base.py`
- Create: `tests/infrastructure/data_providers/test_models.py`
- Create: `tests/infrastructure/data_providers/test_base.py`

**Reference:** Spec sections "Data Models" and "Provider Interface"

- [ ] **Step 1: Create directory structure**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
mkdir -p infrastructure/data_providers/providers/{quote,financial,dividend,market,stock}
mkdir -p tests/infrastructure/data_providers/providers
touch infrastructure/data_providers/__init__.py
touch infrastructure/data_providers/providers/__init__.py
touch infrastructure/data_providers/providers/{quote,financial,dividend,market,stock}/__init__.py
```

- [ ] **Step 2: Copy models.py from spec**

Create `infrastructure/data_providers/models.py` with 5 dataclass models:
- QuoteData (keep existing from quote_providers)
- FinancialData
- DividendData  
- MarketData
- StockData

All must have `source` and `timestamp` fields.

- [ ] **Step 3: Copy base.py from spec**

Create `infrastructure/data_providers/base.py` with abstract base classes:
- BaseDataProvider (generic)
- QuoteProvider
- FinancialProvider
- DividendProvider
- MarketProvider
- StockProvider

- [ ] **Step 4: Write unit tests**

Create test files validating:
- Data model validation (price > 0, symbol not empty)
- Abstract classes cannot be instantiated
- Concrete implementations work

- [ ] **Step 5: Run tests**

Run: `pytest tests/infrastructure/data_providers/test_models.py tests/infrastructure/data_providers/test_base.py -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add infrastructure/data_providers/{models.py,base.py,__init__.py}
git add infrastructure/data_providers/providers/
git add tests/infrastructure/data_providers/
git commit -m "feat(data-providers): add models and base classes for 5 domains"
```

---

### Task 1.2: Create DataProviderManager

**Files:**
- Create: `infrastructure/data_providers/manager.py`
- Create: `tests/infrastructure/data_providers/test_manager.py`

**Reference:** Spec section "DataProviderManager", existing `services/realtime_quote_service.py`

- [ ] **Step 1: Study existing RealtimeQuoteService**

Read `services/realtime_quote_service.py` to understand:
- Hardcoded provider list initialization
- `_try_providers()` failover logic
- Provider stats tracking (`_record_success`, `_record_failure`)
- Health stats API (`get_stats()`)

- [ ] **Step 2: Write failing test for manager**

```python
# tests/infrastructure/data_providers/test_manager.py
from infrastructure.data_providers.manager import DataProviderManager

def test_manager_initialization():
    """Test manager initializes with hardcoded providers"""
    manager = DataProviderManager()
    assert len(manager.quote_providers) > 0
    assert len(manager.provider_stats) > 0

def test_manager_singleton():
    """Test get_data_provider_manager returns singleton"""
    from infrastructure.data_providers import get_data_provider_manager
    m1 = get_data_provider_manager()
    m2 = get_data_provider_manager()
    assert m1 is m2
```

- [ ] **Step 3: Implement DataProviderManager skeleton**

```python
# infrastructure/data_providers/manager.py
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DataProviderManager:
    """Unified data provider manager with automatic failover."""
    
    def __init__(self):
        # Hardcoded provider priorities (populated in Phase 2)
        self.quote_providers = []
        self.financial_providers = []
        self.dividend_providers = []
        self.market_providers = []
        self.stock_providers = []
        
        # Health tracking
        self.provider_stats: Dict[str, Dict[str, int]] = {}
        self._init_stats()
    
    def _init_stats(self):
        """Initialize provider statistics"""
        all_providers = (
            self.quote_providers +
            self.financial_providers +
            self.dividend_providers +
            self.market_providers +
            self.stock_providers
        )
        for provider in all_providers:
            self.provider_stats[provider.name] = {
                'success': 0,
                'failure': 0,
            }
    
    def _try_providers(self, providers: List, method_name: str, *args, **kwargs) -> dict:
        """Generic failover logic (inspired by RealtimeQuoteService)"""
        for provider in providers:
            try:
                method = getattr(provider, method_name)
                result = method(*args, **kwargs)
                
                if result and self._is_valid(result):
                    self._record_success(provider.name)
                    return {
                        'success': True,
                        'data': result,
                        'source': provider.name
                    }
                
                self._record_failure(provider.name)
            
            except Exception as e:
                logger.warning(f"Provider {provider.name}.{method_name} failed: {e}")
                self._record_failure(provider.name)
        
        return {
            'success': False,
            'error': 'All data providers failed',
            'attempted_sources': [p.name for p in providers]
        }
    
    def _is_valid(self, data) -> bool:
        """Validate data completeness"""
        if hasattr(data, 'source') and hasattr(data, 'timestamp'):
            return bool(data.source and data.timestamp)
        if isinstance(data, list) and len(data) > 0:
            return hasattr(data[0], 'source')
        return False
    
    def _record_success(self, provider_name: str):
        if provider_name in self.provider_stats:
            self.provider_stats[provider_name]['success'] += 1
    
    def _record_failure(self, provider_name: str):
        if provider_name in self.provider_stats:
            self.provider_stats[provider_name]['failure'] += 1
    
    def get_provider_health(self) -> Dict[str, Dict[str, int]]:
        """Get provider health status"""
        return self.provider_stats
    
    # API methods (implemented in Phase 2 after providers exist)
    def get_quote(self, symbol: str) -> dict:
        """Get realtime quote"""
        return self._try_providers(self.quote_providers, 'get_quote', symbol)
    
    def get_announcements(self, symbol: str) -> dict:
        """Get stock announcements"""
        return self._try_providers(self.stock_providers, 'get_announcements', symbol)
    
    # ... (other methods added in Phase 3 as needed)


# Singleton instance
_manager_instance = None

def get_data_provider_manager() -> DataProviderManager:
    """Get singleton DataProviderManager instance"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = DataProviderManager()
    return _manager_instance
```

- [ ] **Step 4: Update __init__.py exports**

```python
# infrastructure/data_providers/__init__.py
"""Unified data provider infrastructure."""
from infrastructure.data_providers.manager import (
    DataProviderManager,
    get_data_provider_manager
)
from infrastructure.data_providers.models import (
    QuoteData,
    FinancialData,
    DividendData,
    MarketData,
    StockData
)
from infrastructure.data_providers.base import (
    QuoteProvider,
    FinancialProvider,
    DividendProvider,
    MarketProvider,
    StockProvider
)

__all__ = [
    'DataProviderManager',
    'get_data_provider_manager',
    'QuoteData',
    'FinancialData',
    'DividendData',
    'MarketData',
    'StockData',
    'QuoteProvider',
    'FinancialProvider',
    'DividendProvider',
    'MarketProvider',
    'StockProvider',
]
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/infrastructure/data_providers/test_manager.py -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add infrastructure/data_providers/manager.py
git add infrastructure/data_providers/__init__.py
git add tests/infrastructure/data_providers/test_manager.py
git commit -m "feat(data-providers): add DataProviderManager with failover logic"
```

---

## Phase 2: Migrate Existing Providers

### Task 2.1: Move Quote Providers

**Files:**
- Move: `services/quote_providers/*.py` → `infrastructure/data_providers/providers/quote/`
- Modify: Update imports and base class inheritance
- Test: `tests/infrastructure/data_providers/providers/test_quote_providers.py`

- [ ] **Step 1: Copy quote provider files**

```bash
cp services/quote_providers/sina.py infrastructure/data_providers/providers/quote/
cp services/quote_providers/eastmoney.py infrastructure/data_providers/providers/quote/
cp services/quote_providers/akshare.py infrastructure/data_providers/providers/quote/
cp services/quote_providers/tencent.py infrastructure/data_providers/providers/quote/
cp services/quote_providers/netease.py infrastructure/data_providers/providers/quote/
```

- [ ] **Step 2: Update imports in each provider**

Change:
```python
from services.quote_providers.base import QuoteProvider, QuoteData
```

To:
```python
from infrastructure.data_providers.base import QuoteProvider
from infrastructure.data_providers.models import QuoteData
```

- [ ] **Step 3: Register providers in manager**

Update `infrastructure/data_providers/manager.py`:

```python
# Add imports at top
from infrastructure.data_providers.providers.quote import (
    SinaQuoteProvider,
    EastmoneyQuoteProvider,
    AkshareQuoteProvider,
    TencentQuoteProvider,
    NeteaseQuoteProvider
)

# Update __init__
def __init__(self):
    self.quote_providers = [
        SinaQuoteProvider(),
        EastmoneyQuoteProvider(),
        AkshareQuoteProvider(),
        TencentQuoteProvider(),
        NeteaseQuoteProvider(),
    ]
    # ... rest unchanged
```

- [ ] **Step 4: Create provider __init__.py**

```python
# infrastructure/data_providers/providers/quote/__init__.py
from infrastructure.data_providers.providers.quote.sina import SinaQuoteProvider
from infrastructure.data_providers.providers.quote.eastmoney import EastmoneyQuoteProvider
from infrastructure.data_providers.providers.quote.akshare import AkshareQuoteProvider
from infrastructure.data_providers.providers.quote.tencent import TencentQuoteProvider
from infrastructure.data_providers.providers.quote.netease import NeteaseQuoteProvider

__all__ = [
    'SinaQuoteProvider',
    'EastmoneyQuoteProvider',
    'AkshareQuoteProvider',
    'TencentQuoteProvider',
    'NeteaseQuoteProvider',
]
```

- [ ] **Step 5: Write integration test**

```python
# tests/infrastructure/data_providers/providers/test_quote_providers.py
from infrastructure.data_providers import get_data_provider_manager

def test_quote_providers_registered():
    """Test quote providers are registered in manager"""
    manager = get_data_provider_manager()
    assert len(manager.quote_providers) == 5
    provider_names = [p.name for p in manager.quote_providers]
    assert 'sina' in provider_names
    assert 'eastmoney' in provider_names
    assert 'akshare' in provider_names

def test_get_quote_failover():
    """Test get_quote uses failover mechanism"""
    manager = get_data_provider_manager()
    result = manager.get_quote('600519.SH')
    
    if result['success']:
        assert 'data' in result
        assert 'source' in result
        assert result['data'].symbol == '600519.SH'
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/infrastructure/data_providers/providers/test_quote_providers.py -v`

Expected: Tests PASS

- [ ] **Step 7: Commit**

```bash
git add infrastructure/data_providers/providers/quote/
git add tests/infrastructure/data_providers/providers/test_quote_providers.py
git commit -m "feat(data-providers): migrate quote providers from services/"
```

---

### Task 2.2: Move Financial Providers

**Files:**
- Move: `services/financial_providers/*.py` → `infrastructure/data_providers/providers/financial/`
- Modify: Update imports and base class inheritance

**Note:** Follow same pattern as Task 2.1:
1. Copy files
2. Update imports (`services.financial_providers.base` → `infrastructure.data_providers.base`)
3. Register in manager's `self.financial_providers` list
4. Create `__init__.py`
5. Write integration test
6. Commit

---

### Task 2.3: Create New Providers (Dividend, Market, Stock)

**Files:**
- Create: `infrastructure/data_providers/providers/dividend/akshare.py`
- Create: `infrastructure/data_providers/providers/market/akshare.py`
- Create: `infrastructure/data_providers/providers/stock/akshare.py`

**Strategy:** Extract existing akshare code from service files, wrap in provider interface.

**Example for DividendProvider:**

- [ ] **Step 1: Read existing dividend code**

Read `services/dividend_data_source.py` and `services/dividend_service.py` to understand akshare calls.

- [ ] **Step 2: Create AkshareDividendProvider**

```python
# infrastructure/data_providers/providers/dividend/akshare.py
import logging
from typing import Optional, List
from datetime import datetime
from infrastructure.data_providers.base import DividendProvider
from infrastructure.data_providers.models import DividendData

logger = logging.getLogger(__name__)

class AkshareDividendProvider(DividendProvider):
    """Akshare dividend data provider"""
    
    @property
    def name(self) -> str:
        return 'akshare'
    
    def get_dividends(self, symbol: str, years: int = 5) -> Optional[List[DividendData]]:
        """Get dividend history"""
        try:
            import akshare as ak
            
            # Extract code without suffix
            code = symbol.split('.')[0]
            df = ak.stock_dividend_cninfo(symbol=code)
            
            if df is None or df.empty:
                return None
            
            # Convert to DividendData list
            result = []
            for _, row in df.head(years).iterrows():
                result.append(DividendData(
                    symbol=symbol,
                    dividend_per_share=float(row.get('每股派息', 0)),
                    dividend_yield=float(row.get('股息率', 0)) if '股息率' in row else None,
                    ex_dividend_date=str(row.get('除权除息日', '')) if '除权除息日' in row else None,
                    source=self.name,
                    timestamp=datetime.now().isoformat()
                ))
            
            return result if result else None
        
        except Exception as e:
            logger.warning(f"{self.name} get_dividends failed: {e}")
            return None
    
    def get_dividend_calendar(self, start_date: str, end_date: str) -> Optional[List[DividendData]]:
        """Get dividend calendar (stub - implement based on services/dividend_service.py)"""
        # TODO: Extract logic from services/dividend_service.py
        return None
    
    def screen_high_dividend(self, min_yield: float = 3.0, min_years: int = 5) -> Optional[List[DividendData]]:
        """Screen high dividend stocks (stub - implement based on services/dividend_service.py)"""
        # TODO: Extract logic from services/dividend_service.py
        return None
```

- [ ] **Step 3: Register in manager**

Update `infrastructure/data_providers/manager.py`:

```python
from infrastructure.data_providers.providers.dividend import AkshareDividendProvider

def __init__(self):
    # ... existing code
    self.dividend_providers = [
        AkshareDividendProvider(),
    ]
```

- [ ] **Step 4: Add get_dividends method to manager**

```python
def get_dividends(self, symbol: str, years: int = 5) -> dict:
    """Get dividend history"""
    return self._try_providers(self.dividend_providers, 'get_dividends', symbol, years=years)
```

- [ ] **Step 5: Test**

Create simple test in `tests/infrastructure/data_providers/providers/test_dividend_providers.py`

- [ ] **Step 6: Commit**

```bash
git add infrastructure/data_providers/providers/dividend/
git commit -m "feat(data-providers): add akshare dividend provider"
```

**Repeat similar steps for MarketProvider and StockProvider.**

---

## Phase 3: Refactor Services

### Task 3.1: Refactor stock_data_service.py

**Files:**
- Modify: `services/stock_data_service.py` (3 methods)
- Test: Update `tests/services/test_stock_data_service.py`

**Methods to refactor:**
1. `get_announcements(symbol)`
2. `get_news(symbol, num)`
3. `get_batch_quotes(symbols)`

- [ ] **Step 1: Add manager to service __init__**

```python
# services/stock_data_service.py
from infrastructure.data_providers import get_data_provider_manager

class StockDataService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.provider_manager = get_data_provider_manager()  # ADD THIS
```

- [ ] **Step 2: Refactor get_announcements**

**Before:**
```python
def get_announcements(self, symbol: str) -> Dict[str, Any]:
    try:
        import akshare as ak
        df = ak.stock_notice_report(symbol=symbol)
        # ... rest of logic
```

**After:**
```python
def get_announcements(self, symbol: str) -> Dict[str, Any]:
    """Get stock announcements (via DataProviderManager)"""
    result = self.provider_manager.get_announcements(symbol)
    
    if result['success']:
        stock_data = result['data']
        return {
            'success': True,
            'data': {
                'symbol': stock_data.symbol,
                'announcements': stock_data.data,
                'total': stock_data.total,
                'source': stock_data.source,  # NEW FIELD
                'update_time': stock_data.timestamp
            }
        }
    
    return {
        'success': False,
        'error': result.get('error', 'Failed to get announcements'),
        'data': None
    }
```

- [ ] **Step 3: Refactor get_news (similar pattern)**

- [ ] **Step 4: Refactor get_batch_quotes**

Note: `get_batch_quotes` calls `get_quote` for each symbol in a loop. Update to use `provider_manager.get_quote()`.

- [ ] **Step 5: Update tests to verify `source` field**

```python
# tests/services/test_stock_data_service.py
def test_get_announcements_includes_source():
    service = StockDataService()
    result = service.get_announcements('600519')
    
    if result['success']:
        assert 'source' in result['data']
        assert result['data']['source'] in ['akshare', 'sina', 'eastmoney']
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/services/test_stock_data_service.py -v`

- [ ] **Step 7: Verify no direct akshare imports remain**

```bash
grep -n "import akshare" services/stock_data_service.py
```

Expected: No matches

- [ ] **Step 8: Commit**

```bash
git add services/stock_data_service.py
git add tests/services/test_stock_data_service.py
git commit -m "refactor(services): migrate stock_data_service to DataProviderManager"
```

---

### Task 3.2-3.9: Refactor Remaining 8 Services

**Files to refactor (follow Task 3.1 pattern):**
- `services/dividend_data_source.py` (1 method)
- `services/dividend_service.py` (3 methods)
- `services/valuation_data_service.py` (1 method)
- `services/lhb_data_source.py` (2 methods)
- `services/market_data_service.py` (5 methods)
- `services/trading_calendar_service.py` (1 method)
- `services/strategy_code_service.py` (2 methods)
- `services/financial_analysis_service.py` (3 methods)

**For each service:**
1. Add `self.provider_manager = get_data_provider_manager()` to `__init__`
2. Replace `import akshare as ak` + `ak.xxx()` with `provider_manager.get_xxx()`
3. Update return format to include `source` field
4. Update tests to verify `source` field
5. Verify no direct akshare imports remain
6. Commit

---

## Phase 4: Cleanup

### Task 4.1: Delete Old Code

**Files to delete:**
- `services/quote_providers/` (moved to infrastructure)
- `services/financial_providers/` (moved to infrastructure)
- `data_sources/` (replaced by new architecture)
- `services/realtime_quote_service.py` (merged into DataProviderManager)

- [ ] **Step 1: Verify all migrations complete**

Check that no code still imports from old locations:

```bash
grep -r "from services.quote_providers" services/ api/
grep -r "from services.financial_providers" services/ api/
grep -r "from data_sources" services/ api/
grep -r "from services.realtime_quote_service" services/ api/
```

Expected: No matches

- [ ] **Step 2: Delete directories**

```bash
rm -rf services/quote_providers
rm -rf services/financial_providers
rm -rf data_sources
rm -f services/realtime_quote_service.py
```

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old provider directories and realtime_quote_service"
```

---

## Final Verification

### Task 5.1: End-to-End Testing

- [ ] **Step 1: Test all API endpoints**

Verify API responses include `source` field:

```bash
curl http://127.0.0.1:5001/api/stock/600519/announcements
# Verify response has data.source field

curl http://127.0.0.1:5001/api/stock/600519/news  
# Verify response has data.source field
```

- [ ] **Step 2: Test provider health stats**

```python
from infrastructure.data_providers import get_data_provider_manager

manager = get_data_provider_manager()
stats = manager.get_provider_health()
print(stats)
# Should show success/failure counts for all providers
```

- [ ] **Step 3: Verify test coverage**

```bash
pytest --cov=infrastructure.data_providers --cov-report=html
```

Check coverage meets targets:
- Providers: 90%+
- Manager: 95%+

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete unified data provider architecture migration"
```

---

## Success Criteria Checklist

Verify all criteria from spec are met:

- [ ] All 9 service files migrated (no direct `import akshare`)
- [ ] All 21 methods refactored to use DataProviderManager
- [ ] All tests passing (unit, integration, e2e)
- [ ] Test coverage targets met (90%+ providers, 95%+ manager)
- [ ] Old directories deleted
- [ ] API responses include `source` field
- [ ] Provider health stats accessible via `get_provider_health()`
- [ ] Zero regressions (all existing functionality works)

---

## Notes for Implementer

**TDD Discipline:**
- Write tests first for each new provider
- Run tests to ensure they fail before implementing
- Implement minimal code to make tests pass
- Commit after each task completion

**Common Pitfalls:**
- Don't forget to update `__init__.py` exports when adding new files
- Ensure all providers return `None` on failure (not raise exceptions)
- Remember to add `source` and `timestamp` fields to all data models
- Test failover by mocking provider failures

**Testing Strategy:**
- Unit tests: Individual provider methods
- Integration tests: Manager failover logic
- E2E tests: Service → API → response format

**Commit Frequency:**
- After each task (not each step)
- Tasks are designed to be atomic and testable

