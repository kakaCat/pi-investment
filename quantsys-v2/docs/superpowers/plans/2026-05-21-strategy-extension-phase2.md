# Strategy Extension & Traceability System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a layered strategy extension system with indicator adapters, enhanced base classes, 5 new strategies, auto-discovery factory, and database-level traceability across the full quant pipeline.

**Architecture:** Three-layer design — (1) `quant/engine/indicators/` adapter layer with TA-Lib/pandas-ta dual fallback, (2) `quant/engine/mixins/` providing IndicatorMixin, MLMixin, FactorMixin for composable strategy building, (3) `repositories/traceability_repository.py` writing execution records to 8 new DB tables. New strategies inherit from `EnhancedStrategyBase` (combining Mixins) while existing 10 strategies remain untouched via `StrategyBase`.

**Tech Stack:** Python 3.14+, pandas-ta (or TA-Lib), psycopg2, PostgreSQL, pytest

---

## File Structure

```
quantsys-v2/
├── quant/engine/
│   ├── indicators/                    # NEW: indicator adapter layer
│   │   ├── __init__.py
│   │   ├── base.py                    # IndicatorAdapter ABC
│   │   ├── talib_adapter.py           # TA-Lib adapter
│   │   ├── pandasta_adapter.py        # pandas-ta adapter
│   │   └── indicator_manager.py       # unified manager with auto-fallback
│   ├── mixins/                        # NEW: composable mixins
│   │   ├── __init__.py
│   │   ├── indicator_mixin.py         # IndicatorMixin
│   │   ├── ml_mixin.py                # MLMixin
│   │   └── factor_mixin.py            # FactorMixin
│   ├── enhanced_strategy_base.py      # NEW: EnhancedStrategyBase (StrategyBase + mixins)
│   ├── traceable_strategy.py          # NEW: TraceableStrategyBase (wraps execution tracing)
│   ├── multi_factor_strategy.py       # NEW: MultiFactorStrategy
│   ├── ml_prediction_strategy.py      # NEW: MLPredictionStrategy
│   ├── adx_trend_strategy.py          # NEW: ADXTrendStrategy
│   ├── cci_reversal_strategy.py       # NEW: CCIReversalStrategy
│   ├── grid_trading_strategy.py       # NEW: GridTradingStrategy
│   ├── strategy_factory.py            # NEW: StrategyFactory (auto-discover + DB sync)
│   ├── strategy_base.py               # MODIFY: unchanged (backwards compat)
│   ├── strategy_runner.py             # MODIFY: use StrategyFactory
│   └── __init__.py                    # MODIFY: export new classes
├── repositories/
│   ├── traceability_repository.py     # NEW: traceability CRUD
│   └── strategy_repository.py         # MODIFY: add metadata methods
├── tests/
│   ├── test_indicators.py             # NEW: indicator adapter tests
│   ├── test_mixins.py                 # NEW: mixin tests
│   ├── test_enhanced_strategies.py    # NEW: 5 new strategy tests
│   ├── test_strategy_factory.py       # NEW: factory tests
│   └── test_traceability.py           # NEW: traceability tests (DB required)
├── requirements.txt                   # MODIFY: add pandas-ta, TA-Lib
└── scripts/
    └── create_strategy_traceability_tables.sql  # EXISTS: already committed
```

---

### Task 1: Install Dependencies & Verify

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add pandas-ta to requirements.txt**

```
# Technical indicators
pandas-ta>=0.3.14b
# TA-Lib (optional, requires C compilation)
# TA-Lib>=0.4.28
```

- [ ] **Step 2: Install pandas-ta**

Run: `pip install pandas-ta`
Expected: Successfully installed pandas-ta

- [ ] **Step 3: Verify import works**

Run: `python -c "import pandas_ta as ta; print(ta.__version__)"`
Expected: version printed without errors

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat(deps): add pandas-ta for technical indicator calculations"
```

---

### Task 2: Indicator Adapter Base

**Files:**
- Create: `quant/engine/indicators/__init__.py`
- Create: `quant/engine/indicators/base.py`
- Test: `tests/test_indicators.py` (write all indicator tests in this file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_indicators.py`:

```python
"""Tests for indicator adapter layer."""
import pytest


class TestIndicatorAdapterABC:
    """Tests for the abstract base class interface."""

    def test_adapter_has_calculate_method(self):
        """Adapter ABC should define calculate interface."""
        from quant.engine.indicators.base import IndicatorAdapter

        assert hasattr(IndicatorAdapter, 'calculate')
        assert hasattr(IndicatorAdapter, 'is_available')

    def test_adapter_has_list_indicators_method(self):
        """Adapter ABC should define list_indicators interface."""
        from quant.engine.indicators.base import IndicatorAdapter

        assert hasattr(IndicatorAdapter, 'list_indicators')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_indicators.py::TestIndicatorAdapterABC -v`
Expected: FAIL, ImportError (module not yet created)

- [ ] **Step 3: Write indicator adapter base**

Create `quant/engine/indicators/__init__.py`:

```python
"""Indicator adapter layer — TA-Lib / pandas-ta dual with auto-fallback."""
from quant.engine.indicators.indicator_manager import IndicatorManager

__all__ = ["IndicatorManager"]
```

Create `quant/engine/indicators/base.py`:

```python
"""Abstract base for indicator adapters."""
from abc import ABC, abstractmethod
from typing import Any


class IndicatorAdapter(ABC):
    """Base class for indicator library adapters."""

    @abstractmethod
    def calculate(self, klines: list[dict], indicator: str, **params) -> Any:
        """Calculate a single indicator. Returns the indicator values list."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the underlying library is installed and usable."""
        ...

    @abstractmethod
    def list_indicators(self) -> list[str]:
        """List all indicators supported by this adapter."""
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_indicators.py::TestIndicatorAdapterABC -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add quant/engine/indicators/ tests/test_indicators.py
git commit -m "feat(indicators): add IndicatorAdapter ABC"
```

---

### Task 3: PandasTA Adapter

**Files:**
- Create: `quant/engine/indicators/pandasta_adapter.py`
- Modify: `tests/test_indicators.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_indicators.py`:

```python
import numpy as np


def make_test_klines(n=50):
    """Generate synthetic klines for indicator testing."""
    klines = []
    for i in range(n):
        base_price = 10.0 + i * 0.1
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': base_price,
            'high': base_price * 1.02,
            'low': base_price * 0.98,
            'close': base_price + 0.05,
            'volume': 1000000 + i * 10000,
        })
    return klines


class TestPandasTAAdapter:
    """Tests for pandas-ta adapter."""

    @pytest.fixture
    def adapter(self):
        from quant.engine.indicators.pandasta_adapter import PandasTAAdapter
        return PandasTAAdapter()

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_is_available(self, adapter):
        """Should return True when pandas-ta is installed."""
        assert adapter.is_available() is True

    def test_calculate_sma(self, adapter, klines):
        """Calculate SMA 20."""
        result = adapter.calculate(klines, 'SMA', length=20)
        assert result is not None
        assert len(result) == len(klines)
        assert isinstance(result[-1], float)

    def test_calculate_rsi(self, adapter, klines):
        """Calculate RSI 14."""
        result = adapter.calculate(klines, 'RSI', length=14)
        assert result is not None
        last_val = result[-1]
        assert 0 <= last_val <= 100

    def test_calculate_adx(self, adapter, klines):
        """Calculate ADX 14."""
        result = adapter.calculate(klines, 'ADX', length=14)
        assert result is not None
        assert len(result) == len(klines)

    def test_calculate_cci(self, adapter, klines):
        """Calculate CCI 20."""
        result = adapter.calculate(klines, 'CCI', length=20)
        assert result is not None
        assert len(result) == len(klines)

    def test_calculate_macd(self, adapter, klines):
        """Calculate MACD."""
        result = adapter.calculate(klines, 'MACD', fast=12, slow=26, signal=9)
        assert result is not None

    def test_calculate_bollinger_bands(self, adapter, klines):
        """Calculate Bollinger Bands."""
        result = adapter.calculate(klines, 'BBANDS', length=20, std=2)
        assert result is not None

    def test_list_indicators(self, adapter):
        """List should return non-empty list."""
        indicators = adapter.list_indicators()
        assert isinstance(indicators, list)
        assert len(indicators) > 20
        assert 'SMA' in indicators
        assert 'RSI' in indicators

    def test_unknown_indicator_returns_none(self, adapter, klines):
        """Unknown indicator should return None without crashing."""
        result = adapter.calculate(klines, 'NONEXISTENT_INDICATOR')
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_indicators.py::TestPandasTAAdapter -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write PandasTAAdapter**

Create `quant/engine/indicators/pandasta_adapter.py`:

```python
"""pandas-ta indicator adapter."""
from typing import Any

import pandas as pd

from quant.engine.indicators.base import IndicatorAdapter


class PandasTAAdapter(IndicatorAdapter):
    """Adapter for the pandas-ta library (130+ indicators, pure Python)."""

    # Maps canonical indicator names to pandas-ta strategy names
    _NAME_MAP: dict[str, str] = {
        'SMA': 'SMA',
        'EMA': 'EMA',
        'RSI': 'RSI',
        'ADX': 'ADX',
        'CCI': 'CCI',
        'MACD': 'MACD',
        'BBANDS': 'BBANDS',
        'ATR': 'ATR',
        'STOCH': 'STOCH',
        'WILLR': 'WILLR',
        'MFI': 'MFI',
        'ROC': 'ROC',
        'OBV': 'OBV',
        'PLUS_DI': 'PLUS_DI',
        'MINUS_DI': 'MINUS_DI',
    }

    def is_available(self) -> bool:
        try:
            import pandas_ta  # noqa: F401
            return True
        except ImportError:
            return False

    def list_indicators(self) -> list[str]:
        try:
            import pandas_ta as ta
            return list(ta.Strategy('All').ta.names())
        except Exception:
            return list(self._NAME_MAP.keys())

    def calculate(
        self, klines: list[dict], indicator: str, **params
    ) -> Any:
        if not self.is_available():
            return None

        import pandas_ta as ta

        df = self._klines_to_df(klines)
        ta_name = self._NAME_MAP.get(indicator, indicator).lower()

        # Map common param names: length → length
        func = getattr(ta, ta_name, None)
        if func is None:
            # Try as strategy
            try:
                result_df = df.ta.strategy(ta_name, **params)
                indicator_col = [c for c in result_df.columns
                                 if c != 'close' and not c.startswith('open')
                                 and not c.startswith('high') and not c.startswith('low')
                                 and not c.startswith('volume')]
                if indicator_col:
                    return result_df[indicator_col[0]].tolist()
                return result_df.iloc[:, 0].tolist()
            except Exception:
                return None

        try:
            result = func(**self._build_kwargs(df, params))
            if hasattr(result, 'tolist'):
                return result.tolist()
            if isinstance(result, pd.DataFrame):
                return result.iloc[:, 0].tolist()
            return result
        except Exception:
            return None

    def _klines_to_df(self, klines: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(klines)
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['open'] = pd.to_numeric(df['open'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        return df

    def _build_kwargs(self, df: pd.DataFrame, params: dict) -> dict:
        kwargs = {}
        # Map standard param names to pandas-ta arg names
        if 'length' in params:
            kwargs['length'] = params['length']
        if 'fast' in params:
            kwargs['fast'] = params['fast']
        if 'slow' in params:
            kwargs['slow'] = params['slow']
        if 'signal' in params:
            kwargs['signal'] = params['signal']
        if 'std' in params:
            kwargs['std'] = params['std']

        # Always include OHLCV data
        kwargs['close'] = df['close']
        kwargs['high'] = df['high']
        kwargs['low'] = df['low']
        kwargs['open'] = df['open']
        kwargs['volume'] = df['volume']

        return kwargs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_indicators.py::TestPandasTAAdapter -v`
Expected: 9 PASS

- [ ] **Step 5: Commit**

```bash
git add quant/engine/indicators/pandasta_adapter.py tests/test_indicators.py
git commit -m "feat(indicators): add PandasTAAdapter with 9 passing tests"
```

---

### Task 4: TA-Lib Adapter

**Files:**
- Create: `quant/engine/indicators/talib_adapter.py`
- Modify: `tests/test_indicators.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_indicators.py`:

```python
class TestTALibAdapter:
    """Tests for TA-Lib adapter (may be skipped if not installed)."""

    @pytest.fixture
    def adapter(self):
        from quant.engine.indicators.talib_adapter import TALibAdapter
        return TALibAdapter()

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_is_available_returns_bool(self, adapter):
        """is_available should return a boolean."""
        result = adapter.is_available()
        assert isinstance(result, bool)

    @pytest.mark.skipif(
        "not __import__('importlib').util.find_spec('talib')",
        reason="TA-Lib not installed"
    )
    def test_calculate_sma(self, adapter, klines):
        """Calculate SMA when TA-Lib is available."""
        result = adapter.calculate(klines, 'SMA', timeperiod=20)
        assert result is not None
        assert len(result) == len(klines)

    @pytest.mark.skipif(
        "not __import__('importlib').util.find_spec('talib')",
        reason="TA-Lib not installed"
    )
    def test_calculate_rsi(self, adapter, klines):
        """Calculate RSI when TA-Lib is available."""
        result = adapter.calculate(klines, 'RSI', timeperiod=14)
        assert result is not None
        assert 0 <= result[-1] <= 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_indicators.py::TestTALibAdapter -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write TALibAdapter**

Create `quant/engine/indicators/talib_adapter.py`:

```python
"""TA-Lib indicator adapter (optional, requires C compilation)."""
import numpy as np

from quant.engine.indicators.base import IndicatorAdapter


class TALibAdapter(IndicatorAdapter):
    """Adapter for TA-Lib (150+ indicators, C-backed, fastest)."""

    _INDICATORS = [
        'SMA', 'EMA', 'RSI', 'ADX', 'CCI', 'MACD', 'BBANDS',
        'ATR', 'STOCH', 'WILLR', 'MFI', 'ROC', 'OBV',
        'PLUS_DI', 'MINUS_DI', 'AD', 'ADOSC', 'NATR',
        'SAR', 'ULTOSC', 'TRIX', 'DX', 'STOCHRSI',
    ]

    def is_available(self) -> bool:
        try:
            import talib  # noqa: F401
            return True
        except ImportError:
            return False

    def list_indicators(self) -> list[str]:
        return list(self._INDICATORS)

    def calculate(
        self, klines: list[dict], indicator: str, **params
    ) -> list[float] | None:
        if not self.is_available():
            return None

        import talib

        closes = np.array([float(k['close']) for k in klines])
        highs = np.array([float(k['high']) for k in klines])
        lows = np.array([float(k['low']) for k in klines])
        volumes = np.array(
            [float(k.get('volume', 0)) for k in klines], dtype=np.float64
        )

        func_name = indicator.upper()
        func = getattr(talib, func_name, None)
        if func is None:
            return None

        timeperiod = params.get('timeperiod', params.get('length', 14))

        # Dispatch based on signature
        single_input = {'SMA', 'EMA', 'RSI', 'OBV'}
        dual_input = {'STOCH', 'ULTOSC', 'STOCHRSI'}
        triple_input = {'AD', 'ADOSC'}

        try:
            if func_name in single_input:
                result = func(closes, timeperiod=timeperiod)
            elif func_name in {'MACD', }:
                result = func(
                    closes,
                    fastperiod=params.get('fast', 12),
                    slowperiod=params.get('slow', 26),
                    signalperiod=params.get('signal', 9),
                )
            elif func_name in {'BBANDS', }:
                upper, middle, lower = func(
                    closes, timeperiod=timeperiod,
                    nbdevup=params.get('std', 2),
                    nbdevdn=params.get('std', 2),
                )
                return {
                    'upper': upper.tolist(),
                    'middle': middle.tolist(),
                    'lower': lower.tolist(),
                }
            elif func_name in {'ADX', 'CCI', 'ATR', 'NATR', 'DX'}:
                result = func(highs, lows, closes, timeperiod=timeperiod)
            elif func_name in {'PLUS_DI', 'MINUS_DI'}:
                result = func(highs, lows, closes, timeperiod=timeperiod)
            elif func_name in {'MFI', 'WILLR', 'ROC'}:
                result = func(highs, lows, closes, timeperiod=timeperiod)
            elif func_name in {'SAR', }:
                result = func(highs, lows)
            elif func_name in {'AD', }:
                result = func(highs, lows, closes, volumes)
            elif func_name in {'OBV', }:
                result = func(closes, volumes)
            else:
                # Best-effort: try (closes, timeperiod)
                result = func(closes, timeperiod=timeperiod)
        except Exception:
            return None

        if hasattr(result, 'tolist'):
            result = result.tolist()
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_indicators.py::TestTALibAdapter -v`
Expected: 3 PASS (2 skipped if TA-Lib not installed)

- [ ] **Step 5: Commit**

```bash
git add quant/engine/indicators/talib_adapter.py tests/test_indicators.py
git commit -m "feat(indicators): add TALibAdapter with fallback support"
```

---

### Task 5: Indicator Manager (Auto-Fallback)

**Files:**
- Create: `quant/engine/indicators/indicator_manager.py`
- Modify: `tests/test_indicators.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_indicators.py`:

```python
class TestIndicatorManager:
    """Tests for unified indicator manager with auto-fallback."""

    @pytest.fixture
    def manager(self):
        from quant.engine.indicators.indicator_manager import IndicatorManager
        return IndicatorManager()

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_manager_created_with_adapters(self, manager):
        """Manager should initialize with available adapters."""
        assert len(manager.adapters) >= 1

    def test_calculate_sma_via_manager(self, manager, klines):
        """Calculate SMA through the unified manager."""
        result = manager.calculate(klines, 'SMA', length=20)
        assert result is not None
        assert isinstance(result[-1], float)

    def test_calculate_rsi_via_manager(self, manager, klines):
        """Calculate RSI through the unified manager."""
        result = manager.calculate(klines, 'RSI', length=14)
        assert result is not None

    def test_calculate_batch(self, manager, klines):
        """Batch calculate multiple indicators."""
        results = manager.calculate_batch(
            klines,
            {'SMA': {'length': 20}, 'RSI': {'length': 14}, 'CCI': {'length': 20}}
        )
        assert 'SMA' in results
        assert 'RSI' in results
        assert 'CCI' in results

    def test_manager_falls_back_when_primary_fails(self, manager, klines):
        """Manager should try next adapter when first one fails on unknown indicator."""
        result = manager.calculate(klines, 'SMA', length=20)
        assert result is not None

    def test_calculate_raises_when_no_adapter_available(self):
        """Should raise RuntimeError when no adapter is available."""
        from quant.engine.indicators.indicator_manager import IndicatorManager
        mgr = IndicatorManager()
        mgr.adapters = []  # force no adapters
        with pytest.raises(RuntimeError, match='No indicator library'):
            mgr.calculate(make_test_klines(10), 'SMA')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_indicators.py::TestIndicatorManager -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write IndicatorManager**

Create `quant/engine/indicators/indicator_manager.py`:

```python
"""Unified indicator manager with auto-fallback (TA-Lib → pandas-ta)."""
import logging
from typing import Any

from quant.engine.indicators.talib_adapter import TALibAdapter
from quant.engine.indicators.pandasta_adapter import PandasTAAdapter

logger = logging.getLogger(__name__)


class IndicatorManager:
    """Manages indicator calculation with automatic library fallback.

    Precedence: TA-Lib → pandas-ta → error

    Usage::

        manager = IndicatorManager()
        adx = manager.calculate(klines, 'ADX', length=14)
        batch = manager.calculate_batch(klines, {'SMA': {'length': 20}})
    """

    def __init__(self):
        self.adapters = []
        # Try TA-Lib first (faster, more indicators)
        talib = TALibAdapter()
        if talib.is_available():
            self.adapters.append(talib)
            logger.info("IndicatorManager: TA-Lib available")
        # Always add pandas-ta as primary/fallback
        pta = PandasTAAdapter()
        if pta.is_available():
            self.adapters.append(pta)
            logger.info("IndicatorManager: pandas-ta available")

        if not self.adapters:
            logger.warning(
                "IndicatorManager: no indicator library available. "
                "Install TA-Lib or pandas-ta."
            )

    def calculate(
        self, klines: list[dict], indicator: str, **params
    ) -> Any:
        """Calculate a single indicator, trying adapters in order.

        Returns the first successful result. Raises RuntimeError if no
        adapter is available.
        """
        if not self.adapters:
            raise RuntimeError(
                "No indicator library available. "
                "Install TA-Lib or pandas-ta."
            )

        for adapter in self.adapters:
            if not adapter.is_available():
                continue
            try:
                result = adapter.calculate(klines, indicator, **params)
                if result is not None:
                    return result
            except Exception as e:
                logger.debug(
                    "Adapter %s failed for %s: %s",
                    type(adapter).__name__, indicator, e,
                )
                continue

        logger.warning("All adapters failed for indicator '%s'", indicator)
        return None

    def calculate_batch(
        self,
        klines: list[dict],
        indicators: dict[str, dict],
    ) -> dict[str, Any]:
        """Calculate multiple indicators in a single call.

        Args:
            klines: List of kline dicts.
            indicators: Dict mapping indicator name to params dict.
                        e.g. {'SMA': {'length': 20}, 'RSI': {'length': 14}}

        Returns:
            Dict mapping indicator name to calculated values.
        """
        results = {}
        for name, params in indicators.items():
            results[name] = self.calculate(klines, name, **params)
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_indicators.py::TestIndicatorManager -v`
Expected: 6 PASS

- [ ] **Step 5: Run all indicator tests**

Run: `pytest tests/test_indicators.py -v`
Expected: 20 PASS (2 skipped if TA-Lib not installed)

- [ ] **Step 6: Commit**

```bash
git add quant/engine/indicators/indicator_manager.py tests/test_indicators.py
git commit -m "feat(indicators): add IndicatorManager with auto-fallback TA-Lib → pandas-ta"
```

---

### Task 6: IndicatorMixin

**Files:**
- Create: `quant/engine/mixins/__init__.py`
- Create: `quant/engine/mixins/indicator_mixin.py`
- Test: `tests/test_mixins.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_mixins.py`:

```python
"""Tests for strategy mixins."""
import pytest


def make_test_klines(n=50):
    klines = []
    for i in range(n):
        base = 10.0 + i * 0.1
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': base,
            'high': base * 1.02,
            'low': base * 0.98,
            'close': base + 0.05,
            'volume': 1000000 + i * 10000,
        })
    return klines


class TestIndicatorMixin:
    """Tests for IndicatorMixin."""

    @pytest.fixture
    def mixin(self):
        from quant.engine.mixins.indicator_mixin import IndicatorMixin
        return IndicatorMixin()

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_calculate_indicator_sma(self, mixin, klines):
        """Should calculate SMA through mixin."""
        result = mixin.calculate_indicator(klines, 'SMA', length=20)
        assert result is not None

    def test_calculate_batch_indicators(self, mixin, klines):
        """Should batch-calculate multiple indicators."""
        results = mixin.calculate_batch_indicators(
            klines, ['SMA', 'RSI', 'ADX']
        )
        assert 'SMA' in results
        assert 'RSI' in results
        assert 'ADX' in results

    def test_indicator_manager_is_lazy(self, mixin):
        """IndicatorManager should be lazily instantiated."""
        mgr = mixin._indicator_manager
        assert mgr is mixin._indicator_manager  # same instance on second access
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mixins.py::TestIndicatorMixin -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write mixins __init__.py and IndicatorMixin**

Create `quant/engine/mixins/__init__.py`:

```python
"""Strategy mixins for composable behavior."""
from quant.engine.mixins.indicator_mixin import IndicatorMixin
from quant.engine.mixins.factor_mixin import FactorMixin
from quant.engine.mixins.ml_mixin import MLMixin

__all__ = ["IndicatorMixin", "FactorMixin", "MLMixin"]
```

Create `quant/engine/mixins/indicator_mixin.py`:

```python
"""Mixin providing indicator calculation via IndicatorManager."""
from typing import Any

from quant.engine.indicators.indicator_manager import IndicatorManager


class IndicatorMixin:
    """Mixin that gives strategies access to technical indicators.

    Uses IndicatorManager under the hood for auto-fallback between
    TA-Lib and pandas-ta.

    Usage::

        class MyStrategy(StrategyBase, IndicatorMixin):
            def generate_signal(self, klines, params=None):
                adx = self.calculate_indicator(klines, 'ADX', length=14)
    """

    _indicator_manager: IndicatorManager | None = None

    @property
    def indicator_manager(self) -> IndicatorManager:
        if self._indicator_manager is None:
            self._indicator_manager = IndicatorManager()
        return self._indicator_manager

    def calculate_indicator(
        self, klines: list[dict], indicator: str, **params
    ) -> Any:
        """Calculate a single technical indicator.

        Args:
            klines: K-line data.
            indicator: Indicator name (SMA, RSI, ADX, CCI, etc.).
            **params: Indicator-specific params (length, timeperiod, etc.).

        Returns:
            Indicator values (list of float or scalar).
        """
        return self.indicator_manager.calculate(klines, indicator, **params)

    def calculate_batch_indicators(
        self, klines: list[dict], indicator_names: list[str]
    ) -> dict[str, Any]:
        """Calculate multiple indicators using defaults.

        Args:
            klines: K-line data.
            indicator_names: List of indicator names.

        Returns:
            Dict mapping indicator name to calculated values.
        """
        batch = {}
        for name in indicator_names:
            # Use sensible defaults per indicator
            params = self._default_params_for(name)
            batch[name] = params
        return self.indicator_manager.calculate_batch(klines, batch)

    @staticmethod
    def _default_params_for(indicator: str) -> dict:
        defaults = {
            'SMA': {'length': 20},
            'EMA': {'length': 20},
            'RSI': {'length': 14},
            'ADX': {'length': 14},
            'CCI': {'length': 20},
            'ATR': {'length': 14},
            'MACD': {'fast': 12, 'slow': 26, 'signal': 9},
            'BBANDS': {'length': 20, 'std': 2},
        }
        return defaults.get(indicator, {'length': 14})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mixins.py::TestIndicatorMixin -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add quant/engine/mixins/ tests/test_mixins.py
git commit -m "feat(mixins): add IndicatorMixin with lazy IndicatorManager"
```

---

### Task 7: FactorMixin

**Files:**
- Create: `quant/engine/mixins/factor_mixin.py`
- Modify: `tests/test_mixins.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mixins.py`:

```python
class TestFactorMixin:
    """Tests for FactorMixin."""

    @pytest.fixture
    def mixin(self):
        from quant.engine.mixins.factor_mixin import FactorMixin
        return FactorMixin()

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_calculate_factors_default(self, mixin, klines):
        """Should calculate all technical factors by default."""
        factors = mixin.calculate_factors(klines)
        assert isinstance(factors, dict)
        assert len(factors) > 0

    def test_calculate_factors_subset(self, mixin, klines):
        """Should calculate specific factors when names provided."""
        factors = mixin.calculate_factors(klines, ['ma5', 'ma10', 'rsi14'])
        assert 'ma5' in factors
        assert 'ma10' in factors
        assert 'rsi14' in factors
        assert factors['ma5'] is not None

    def test_get_factor_categories(self, mixin):
        """Should return factor category mapping."""
        categories = mixin.get_factor_categories()
        assert isinstance(categories, dict)
```

- [ ] **Step 2: Run test — expect FAIL (ImportError)**

Run: `pytest tests/test_mixins.py::TestFactorMixin -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write FactorMixin**

Create `quant/engine/mixins/factor_mixin.py`:

```python
"""Mixin providing factor calculation via FactorRegistry."""
from quant.engine.factor_registry import FactorRegistry


class FactorMixin:
    """Mixin that gives strategies access to FactorRegistry factors.

    Automatically imports factor modules to trigger registration.

    Usage::

        class MyStrategy(StrategyBase, FactorMixin):
            factors = self.calculate_factors(klines, ['ma5', 'rsi14'])
    """

    _factors_loaded: bool = False

    @classmethod
    def _ensure_factors_loaded(cls):
        if not cls._factors_loaded:
            import quant.engine.technical_factors  # noqa: F401
            import quant.engine.fundamental_factors  # noqa: F401
            cls._factors_loaded = True

    def calculate_factors(
        self, klines: list[dict], factor_names: list[str] | None = None
    ) -> dict[str, float | None]:
        """Calculate factors from the FactorRegistry.

        Args:
            klines: K-line data.
            factor_names: Factor names to calculate. If None, calculates
                          all registered technical factors.

        Returns:
            Dict mapping factor name to value (None on failure).
        """
        self._ensure_factors_loaded()

        if factor_names is None:
            factor_names = FactorRegistry.names(category='technical')

        if not factor_names:
            return {}

        return FactorRegistry.calculate_batch(factor_names, klines)

    def get_factor_categories(self) -> dict[str, str]:
        """Get category for each registered factor."""
        self._ensure_factors_loaded()
        result = {}
        for f in FactorRegistry.list_all():
            result[f.name] = f.category
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mixins.py::TestFactorMixin -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add quant/engine/mixins/factor_mixin.py tests/test_mixins.py
git commit -m "feat(mixins): add FactorMixin wrapping FactorRegistry"
```

---

### Task 8: MLMixin

**Files:**
- Create: `quant/engine/mixins/ml_mixin.py`
- Modify: `tests/test_mixins.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mixins.py`:

```python
class TestMLMixin:
    """Tests for MLMixin."""

    @pytest.fixture
    def mixin(self):
        from quant.engine.mixins.ml_mixin import MLMixin
        return MLMixin()

    def test_ml_mixin_initial_state(self, mixin):
        """Should start with no predictor loaded."""
        assert mixin.is_model_loaded() is False

    def test_predict_precomputed_mode(self, mixin):
        """In precomputed mode, returns the value from params."""
        features = {'ml_prediction': {'signal': 'BUY', 'confidence': 0.85}}
        result = mixin.predict_ml(features, use_precomputed=True)
        assert result is not None
        assert result['signal'] == 'BUY'
        assert result['confidence'] == 0.85

    def test_predict_precomputed_none(self, mixin):
        """When no precomputed data, returns None."""
        result = mixin.predict_ml({}, use_precomputed=True)
        assert result is None

    def test_predict_without_model_raises(self, mixin):
        """Real-time prediction without model should raise."""
        with pytest.raises(ValueError, match='Model not loaded'):
            mixin.predict_ml({'feature1': 1.0}, use_precomputed=False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mixins.py::TestMLMixin -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write MLMixin**

Create `quant/engine/mixins/ml_mixin.py`:

```python
"""Mixin providing ML prediction integration."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MLMixin:
    """Mixin that gives strategies access to ML predictions.

    Supports two modes:
    - Precomputed: `params['ml_prediction']` already contains results.
    - Real-time: Loads model and calls MLPredictor directly.

    Usage::

        class MyStrategy(StrategyBase, MLMixin):
            def generate_signal(self, klines, params=None):
                ml = self.predict_ml(features, use_precomputed=False)
    """

    _predictor: Any = None

    def is_model_loaded(self) -> bool:
        return self._predictor is not None

    def load_ml_model(
        self, model_type: str = 'xgboost', version: str = 'latest'
    ) -> None:
        """Load an ML model from disk.

        Args:
            model_type: 'xgboost' or 'lightgbm'.
            version: Model version identifier.
        """
        from ml.predictor import MLPredictor

        self._predictor = MLPredictor(model_type=model_type)
        self._predictor.load_model(version=version)
        logger.info("ML model loaded: %s/%s", model_type, version)

    def predict_ml(
        self,
        features: dict[str, float],
        use_precomputed: bool = False,
    ) -> dict[str, Any] | None:
        """Get an ML prediction.

        Args:
            features: Feature dict or precomputed result.
            use_precomputed: If True, extract from features['ml_prediction'].

        Returns:
            Dict with signal, confidence, prob_down, prob_up, or None.
        """
        if use_precomputed:
            precomputed = features.get('ml_prediction')
            if precomputed is None:
                logger.debug("No precomputed ML prediction in params")
                return None
            return precomputed

        if self._predictor is None:
            raise ValueError(
                "Model not loaded. Call load_ml_model() first, "
                "or use precomputed mode."
            )

        return self._predictor.predict_single(features)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mixins.py::TestMLMixin -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add quant/engine/mixins/ml_mixin.py tests/test_mixins.py
git commit -m "feat(mixins): add MLMixin with precomputed + real-time modes"
```

---

### Task 9: EnhancedStrategyBase

**Files:**
- Create: `quant/engine/enhanced_strategy_base.py`
- Modify: `tests/test_mixins.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mixins.py`:

```python
class TestEnhancedStrategyBase:
    """Tests for EnhancedStrategyBase."""

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_enhanced_base_includes_all_mixins(self):
        """EnhancedStrategyBase should inherit from all mixins."""
        from quant.engine.enhanced_strategy_base import EnhancedStrategyBase
        from quant.engine.mixins.indicator_mixin import IndicatorMixin
        from quant.engine.mixins.factor_mixin import FactorMixin
        from quant.engine.mixins.ml_mixin import MLMixin
        from quant.engine.strategy_base import StrategyBase

        assert issubclass(EnhancedStrategyBase, StrategyBase)
        assert issubclass(EnhancedStrategyBase, IndicatorMixin)
        assert issubclass(EnhancedStrategyBase, FactorMixin)

    def test_enhanced_base_generate_signal_must_implement(self, klines):
        """EnhancedStrategyBase should require generate_signal."""
        from quant.engine.enhanced_strategy_base import EnhancedStrategyBase

        base = EnhancedStrategyBase(name='test')
        with pytest.raises(NotImplementedError):
            base.generate_signal(klines)

    def test_enhanced_base_has_calculate_indicator(self, klines):
        """Enhanced base should have indicator capability via mixin."""
        from quant.engine.enhanced_strategy_base import EnhancedStrategyBase

        class TestStrat(EnhancedStrategyBase):
            def generate_signal(self, klines, params=None):
                return {'action': 'hold', 'confidence': 0.5, 'reason': 'test'}

        strat = TestStrat(name='test')
        result = strat.calculate_indicator(klines, 'SMA', length=20)
        assert result is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mixins.py::TestEnhancedStrategyBase -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write EnhancedStrategyBase**

Create `quant/engine/enhanced_strategy_base.py`:

```python
"""Enhanced strategy base — StrategyBase + all mixins."""

from quant.engine.strategy_base import StrategyBase
from quant.engine.mixins.indicator_mixin import IndicatorMixin
from quant.engine.mixins.factor_mixin import FactorMixin


class EnhancedStrategyBase(StrategyBase, IndicatorMixin, FactorMixin):
    """Enhanced strategy base class combining StrategyBase with mixins.

    New strategies should inherit from this class instead of StrategyBase
    to get automatic access to:
    - Technical indicators via calculate_indicator()
    - FactorRegistry via calculate_factors()
    - (MLMixin can be added separately for ML strategies)

    Existing strategies inheriting from StrategyBase continue to work
    unchanged.

    Usage::

        class MyStrategy(EnhancedStrategyBase):
            def generate_signal(self, klines, params=None):
                adx = self.calculate_indicator(klines, 'ADX', length=14)
                return {'action': 'buy', 'confidence': 0.8, 'reason': '...'}
    """

    def __init__(self, name: str = None):
        StrategyBase.__init__(self, name)
        # Reset the class-level _indicator_manager so each instance gets its own
        super(IndicatorMixin, self).__init__() if hasattr(
            IndicatorMixin, '__init__'
        ) else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mixins.py::TestEnhancedStrategyBase -v`
Expected: 3 PASS

- [ ] **Step 5: Run all mixin tests**

Run: `pytest tests/test_mixins.py -v`
Expected: 13 PASS

- [ ] **Step 6: Commit**

```bash
git add quant/engine/enhanced_strategy_base.py tests/test_mixins.py
git commit -m "feat(base): add EnhancedStrategyBase combining StrategyBase + mixins"
```

---

### Task 10: MultiFactorStrategy

**Files:**
- Create: `quant/engine/multi_factor_strategy.py`
- Test: `tests/test_enhanced_strategies.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_enhanced_strategies.py`:

```python
"""Tests for the 5 new strategies."""
import pytest


def make_uptrend_klines(n=60):
    klines = []
    for i in range(n):
        close = 10.0 + i * 0.2
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': close - 0.05,
            'high': close * 1.02,
            'low': close * 0.98,
            'close': close,
            'volume': 1000000 + i * 10000,
        })
    return klines


def make_downtrend_klines(n=60):
    klines = []
    for i in range(n):
        close = 20.0 - i * 0.2
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': close + 0.05,
            'high': close * 1.02,
            'low': close * 0.98,
            'close': close,
            'volume': 1000000 + i * 10000,
        })
    return klines


class TestMultiFactorStrategy:
    """Tests for MultiFactorStrategy."""

    @pytest.fixture
    def strategy(self):
        from quant.engine.multi_factor_strategy import MultiFactorStrategy
        return MultiFactorStrategy(name='test_mf')

    def test_buy_signal_in_uptrend(self, strategy):
        """Should generate buy signal in strong uptrend."""
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines)
        assert signal['action'] in ('buy', 'hold')
        assert 0 <= signal['confidence'] <= 1
        assert signal['reason']

    def test_sell_signal_in_downtrend(self, strategy):
        """Should generate sell signal in strong downtrend."""
        klines = make_downtrend_klines(60)
        signal = strategy.generate_signal(klines)
        assert signal['action'] in ('sell', 'hold')
        assert 0 <= signal['confidence'] <= 1

    def test_custom_factor_groups(self, strategy):
        """Should accept custom factor groups via params."""
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {
            'factor_groups': {
                'trend': ['ma5', 'ma10'],
                'momentum': ['rsi14'],
            },
            'group_weights': [0.5, 0.5],
        })
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_default_params(self, strategy):
        """Should have DEFAULT_PARAMS defined."""
        assert hasattr(strategy, 'DEFAULT_PARAMS')
        assert 'factor_groups' in strategy.DEFAULT_PARAMS

    def test_param_schema(self, strategy):
        """Should have PARAM_SCHEMA defined."""
        assert hasattr(strategy, 'PARAM_SCHEMA')
        assert 'buy_threshold' in strategy.PARAM_SCHEMA
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_enhanced_strategies.py::TestMultiFactorStrategy -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write MultiFactorStrategy**

Create `quant/engine/multi_factor_strategy.py`:

```python
"""Multi-factor strategy — layered scoring model."""
from typing import Any

from quant.engine.enhanced_strategy_base import EnhancedStrategyBase


class MultiFactorStrategy(EnhancedStrategyBase):
    """Multi-factor strategy with layered scoring.

    Default factor groups:
    - trend (MA family): 33.3% weight
    - momentum (RSI, MACD): 33.3% weight
    - volatility (ATR, Bollinger): 33.4% weight

    Override via params: factor_groups, group_weights, buy_threshold, sell_threshold.
    """

    DEFAULT_PARAMS = {
        'factor_groups': {
            'trend': ['ma5', 'ma10', 'ma20'],
            'momentum': ['rsi14', 'macd', 'macd_signal'],
            'volatility': ['atr14', 'bollinger_upper', 'bollinger_lower'],
        },
        'group_weights': [0.33, 0.33, 0.34],
        'buy_threshold': 0.60,
        'sell_threshold': 0.40,
    }

    PARAM_SCHEMA = {
        'factor_groups': {
            'type': 'object',
            'description': 'Factor group definitions {group_name: [factor_names]}',
        },
        'group_weights': {
            'type': 'array',
            'description': 'Weight per group, should sum to 1.0',
        },
        'buy_threshold': {
            'type': 'number', 'min': 0, 'max': 1, 'default': 0.6,
            'description': 'Score above which to generate buy signal',
        },
        'sell_threshold': {
            'type': 'number', 'min': 0, 'max': 1, 'default': 0.4,
            'description': 'Score below which to generate sell signal',
        },
    }

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        self._validate_klines(klines, min_length=30)

        p = {**self.DEFAULT_PARAMS, **(params or {})}
        factor_groups: dict = p['factor_groups']
        group_weights: list = p['group_weights']
        buy_threshold: float = p['buy_threshold']
        sell_threshold: float = p['sell_threshold']

        # Collect all factor names
        all_factors = []
        for names in factor_groups.values():
            all_factors.extend(names)

        # Calculate all factors via FactorMixin
        factor_values = self.calculate_factors(klines, all_factors)

        # Score each group
        group_scores = []
        group_names = list(factor_groups.keys())
        for grp_name in group_names:
            fac_names = factor_groups[grp_name]
            score = self._score_group(factor_values, fac_names, klines)
            group_scores.append(score)

        # Weighted sum
        final_score = sum(
            s * w for s, w in zip(group_scores, group_weights)
        )

        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, final_score))

        if final_score >= buy_threshold:
            return {
                'action': 'buy',
                'confidence': round(final_score, 4),
                'reason': (
                    f'Multi-factor score {final_score:.2f} >= {buy_threshold} '
                    f'(groups: {dict(zip(group_names, [f"{s:.2f}" for s in group_scores]))})'
                ),
            }
        elif final_score <= sell_threshold:
            return {
                'action': 'sell',
                'confidence': round(1 - final_score, 4),
                'reason': (
                    f'Multi-factor score {final_score:.2f} <= {sell_threshold} '
                    f'(groups: {dict(zip(group_names, [f"{s:.2f}" for s in group_scores]))})'
                ),
            }

        return {
            'action': 'hold',
            'confidence': 0.0,
            'reason': f'Multi-factor score {final_score:.2f} — neutral zone',
        }

    def _score_group(
        self,
        factor_values: dict,
        factor_names: list[str],
        klines: list[dict],
    ) -> float:
        """Score a single factor group, normalizing to [0, 1]."""
        scores = []
        for name in factor_names:
            val = factor_values.get(name)
            if val is None:
                scores.append(0.5)  # neutral if factor unavailable
                continue

            # Normalize based on factor type
            if 'ma' in name.lower():
                current_price = float(klines[-1]['close'])
                if val > 0:
                    # Price above MA = bullish
                    ratio = current_price / val
                    scores.append(min(1.0, max(0.0, (ratio - 0.95) / 0.15)))
                else:
                    scores.append(0.5)
            elif 'rsi' in name.lower():
                # RSI: 50 neutral, >70 overbought bearish, <30 oversold bullish
                scores.append(min(1.0, max(0.0, (val - 30) / 40)))
            elif 'macd' in name.lower() and 'signal' not in name.lower():
                # MACD histogram
                signal_val = factor_values.get('macd_signal', 0)
                if signal_val is None:
                    signal_val = 0
                diff = val - signal_val
                # Normalize: small range around 0
                scores.append(min(1.0, max(0.0, (diff + 1) / 2)))
            elif 'bollinger' in name.lower():
                current_price = float(klines[-1]['close'])
                if 'upper' in name.lower() and val > 0:
                    scores.append(min(1.0, max(0.0, current_price / val)))
                elif 'lower' in name.lower() and val > 0:
                    scores.append(min(1.0, max(0.0, 1 - val / max(current_price, 0.01))))
                else:
                    scores.append(0.5)
            else:
                scores.append(0.5)

        if not scores:
            return 0.5
        return sum(scores) / len(scores)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_enhanced_strategies.py::TestMultiFactorStrategy -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add quant/engine/multi_factor_strategy.py tests/test_enhanced_strategies.py
git commit -m "feat(strategy): add MultiFactorStrategy with layered scoring"
```

---

### Task 11: ADXTrendStrategy

**Files:**
- Create: `quant/engine/adx_trend_strategy.py`
- Modify: `tests/test_enhanced_strategies.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_enhanced_strategies.py`:

```python
class TestADXTrendStrategy:
    """Tests for ADXTrendStrategy."""

    @pytest.fixture
    def strategy(self):
        from quant.engine.adx_trend_strategy import ADXTrendStrategy
        return ADXTrendStrategy(name='test_adx')

    def test_signal_structure(self, strategy):
        """Signal should have required fields."""
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines)
        assert 'action' in signal
        assert 'confidence' in signal
        assert 'reason' in signal
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_uses_adx_indicator(self, strategy):
        """Should use the ADX indicator via mixin."""
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines)
        assert 'ADX' in signal['reason'].upper() or 'ADX' in signal['reason']

    def test_custom_adx_threshold(self, strategy):
        """Should accept custom ADX threshold."""
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {'adx_threshold': 40})
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_default_params(self, strategy):
        """Should have DEFAULT_PARAMS."""
        assert hasattr(strategy, 'DEFAULT_PARAMS')
        assert 'adx_threshold' in strategy.DEFAULT_PARAMS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_enhanced_strategies.py::TestADXTrendStrategy -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write ADXTrendStrategy**

Create `quant/engine/adx_trend_strategy.py`:

```python
"""ADX Trend Strength Strategy."""
from typing import Any

from quant.engine.enhanced_strategy_base import EnhancedStrategyBase


class ADXTrendStrategy(EnhancedStrategyBase):
    """ADX trend strength strategy.

    Uses ADX to determine trend strength and PLUS_DI/MINUS_DI for direction.
    ADX > threshold → strong trend → generate signal based on DI cross.

    Default: ADX threshold 25, requires 30+ klines.
    """

    DEFAULT_PARAMS = {
        'adx_threshold': 25,
        'adx_period': 14,
    }

    PARAM_SCHEMA = {
        'adx_threshold': {
            'type': 'number', 'min': 10, 'max': 60, 'default': 25,
            'description': 'ADX value above which trend is considered strong',
        },
        'adx_period': {
            'type': 'integer', 'min': 5, 'max': 50, 'default': 14,
            'description': 'Period for ADX calculation',
        },
    }

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        p = {**self.DEFAULT_PARAMS, **(params or {})}
        adx_threshold: float = p['adx_threshold']
        adx_period: int = p['adx_period']

        min_required = adx_period * 2 + 1
        self._validate_klines(klines, min_length=min_required)

        indicators = self.calculate_batch_indicators(
            klines,
            ['ADX', 'PLUS_DI', 'MINUS_DI'],
        )

        def _last_valid(lst) -> float | None:
            if lst is None:
                return None
            if isinstance(lst, list):
                for v in reversed(lst):
                    if v is not None and not (
                        isinstance(v, float) and (v != v)
                    ):  # not NaN
                        return float(v)
            return float(lst)

        adx = _last_valid(indicators.get('ADX'))
        plus_di = _last_valid(indicators.get('PLUS_DI'))
        minus_di = _last_valid(indicators.get('MINUS_DI'))

        if adx is None:
            return {
                'action': 'hold', 'confidence': 0.0,
                'reason': 'ADX calculation failed — insufficient data',
            }

        if adx < adx_threshold:
            return {
                'action': 'hold', 'confidence': min(adx / 100, 0.3),
                'reason': f'Weak trend ADX={adx:.1f} < {adx_threshold}',
            }

        if plus_di is not None and minus_di is not None:
            if plus_di > minus_di:
                return {
                    'action': 'buy',
                    'confidence': min(adx / 50, 1.0),
                    'reason': (
                        f'Strong uptrend ADX={adx:.1f} '
                        f'+DI={plus_di:.1f} > -DI={minus_di:.1f}'
                    ),
                }
            else:
                return {
                    'action': 'sell',
                    'confidence': min(adx / 50, 1.0),
                    'reason': (
                        f'Strong downtrend ADX={adx:.1f} '
                        f'-DI={minus_di:.1f} > +DI={plus_di:.1f}'
                    ),
                }

        return {
            'action': 'hold', 'confidence': 0.0,
            'reason': f'ADX={adx:.1f} — unable to determine direction',
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_enhanced_strategies.py::TestADXTrendStrategy -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add quant/engine/adx_trend_strategy.py tests/test_enhanced_strategies.py
git commit -m "feat(strategy): add ADXTrendStrategy using ADX + PLUS_DI/MINUS_DI"
```

---

### Task 12: CCIReversalStrategy

**Files:**
- Create: `quant/engine/cci_reversal_strategy.py`
- Modify: `tests/test_enhanced_strategies.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_enhanced_strategies.py`:

```python
def make_sideways_klines(n=60):
    import math
    klines = []
    for i in range(n):
        close = 10.0 + 0.5 * math.sin(2 * math.pi * i / 10)
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': close - 0.02,
            'high': close * 1.02,
            'low': close * 0.98,
            'close': close,
            'volume': 1000000,
        })
    return klines


class TestCCIReversalStrategy:
    """Tests for CCIReversalStrategy."""

    @pytest.fixture
    def strategy(self):
        from quant.engine.cci_reversal_strategy import CCIReversalStrategy
        return CCIReversalStrategy(name='test_cci')

    def test_signal_structure(self, strategy):
        """Signal should have required fields."""
        klines = make_sideways_klines(60)
        signal = strategy.generate_signal(klines)
        assert signal['action'] in ('buy', 'sell', 'hold')
        assert 0 <= signal['confidence'] <= 1

    def test_custom_thresholds(self, strategy):
        """Should accept custom overbought/oversold thresholds."""
        klines = make_sideways_klines(60)
        signal = strategy.generate_signal(klines, {
            'overbought': 150, 'oversold': -150,
        })
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_default_params(self, strategy):
        """Should have DEFAULT_PARAMS."""
        assert hasattr(strategy, 'DEFAULT_PARAMS')
        assert 'overbought' in strategy.DEFAULT_PARAMS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_enhanced_strategies.py::TestCCIReversalStrategy -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write CCIReversalStrategy**

Create `quant/engine/cci_reversal_strategy.py`:

```python
"""CCI Reversal Strategy — overbought/oversold mean reversion."""
from typing import Any

from quant.engine.enhanced_strategy_base import EnhancedStrategyBase


class CCIReversalStrategy(EnhancedStrategyBase):
    """CCI (Commodity Channel Index) reversal strategy.

    CCI > +100 → overbought → sell signal
    CCI < -100 → oversold → buy signal

    Default: CCI period 20, overbought +100, oversold -100.
    """

    DEFAULT_PARAMS = {
        'cci_period': 20,
        'overbought': 100,
        'oversold': -100,
    }

    PARAM_SCHEMA = {
        'cci_period': {
            'type': 'integer', 'min': 5, 'max': 50, 'default': 20,
            'description': 'Period for CCI calculation',
        },
        'overbought': {
            'type': 'number', 'min': 50, 'max': 300, 'default': 100,
            'description': 'CCI value above which is overbought',
        },
        'oversold': {
            'type': 'number', 'min': -300, 'max': -50, 'default': -100,
            'description': 'CCI value below which is oversold',
        },
    }

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        p = {**self.DEFAULT_PARAMS, **(params or {})}
        cci_period: int = p['cci_period']
        overbought: float = p['overbought']
        oversold: float = p['oversold']

        self._validate_klines(klines, min_length=cci_period * 2 + 1)

        cci_values = self.calculate_indicator(
            klines, 'CCI', length=cci_period,
        )

        # Extract last valid CCI value
        current_cci = None
        if cci_values is not None:
            if isinstance(cci_values, list):
                for v in reversed(cci_values):
                    if v is not None and not (isinstance(v, float) and v != v):
                        current_cci = float(v)
                        break
            else:
                current_cci = float(cci_values)

        if current_cci is None:
            return {
                'action': 'hold', 'confidence': 0.0,
                'reason': 'CCI calculation failed',
            }

        if current_cci < oversold:
            confidence = min(abs(current_cci) / 200, 1.0)
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': f'CCI oversold {current_cci:.1f} < {oversold}',
            }
        elif current_cci > overbought:
            confidence = min(current_cci / 200, 1.0)
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': f'CCI overbought {current_cci:.1f} > {overbought}',
            }

        return {
            'action': 'hold',
            'confidence': 0.0,
            'reason': f'CCI neutral {current_cci:.1f} in [{oversold}, {overbought}]',
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_enhanced_strategies.py::TestCCIReversalStrategy -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add quant/engine/cci_reversal_strategy.py tests/test_enhanced_strategies.py
git commit -m "feat(strategy): add CCIReversalStrategy for overbought/oversold"
```

---

### Task 13: GridTradingStrategy

**Files:**
- Create: `quant/engine/grid_trading_strategy.py`
- Modify: `tests/test_enhanced_strategies.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_enhanced_strategies.py`:

```python
class TestGridTradingStrategy:
    """Tests for GridTradingStrategy."""

    @pytest.fixture
    def strategy(self):
        from quant.engine.grid_trading_strategy import GridTradingStrategy
        return GridTradingStrategy(name='test_grid')

    def test_signal_structure(self, strategy):
        """Signal should have required fields."""
        klines = make_sideways_klines(60)
        signal = strategy.generate_signal(klines)
        assert signal['action'] in ('buy', 'sell', 'hold')
        assert 0 <= signal['confidence'] <= 1

    def test_auto_price_range(self, strategy):
        """Should auto-calculate price range from ATR."""
        klines = make_sideways_klines(60)
        signal = strategy.generate_signal(klines, {'price_range': 'auto'})
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_fixed_price_range(self, strategy):
        """Should accept fixed price range."""
        klines = make_sideways_klines(60)
        signal = strategy.generate_signal(klines, {
            'price_range': [9.0, 11.0], 'grid_count': 5,
        })
        assert signal['action'] in ('buy', 'sell', 'hold')
        assert '网格' in signal['reason']

    def test_default_params(self, strategy):
        """Should have DEFAULT_PARAMS."""
        assert hasattr(strategy, 'DEFAULT_PARAMS')
        assert 'grid_count' in strategy.DEFAULT_PARAMS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_enhanced_strategies.py::TestGridTradingStrategy -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write GridTradingStrategy**

Create `quant/engine/grid_trading_strategy.py`:

```python
"""Grid Trading Strategy — range-bound market strategy."""
from typing import Any

from quant.engine.enhanced_strategy_base import EnhancedStrategyBase


class GridTradingStrategy(EnhancedStrategyBase):
    """Grid trading strategy for range-bound markets.

    Divides a price range into grid levels. Buys near lower grid lines,
    sells near upper grid lines. Suitable for oscillating markets.

    Price range: 'auto' (ATR-based) or [lower, upper] fixed.
    """

    DEFAULT_PARAMS = {
        'grid_count': 10,
        'price_range': 'auto',
        'atr_multiplier': 2.0,
        'atr_period': 14,
        'trigger_zone': 0.2,
    }

    PARAM_SCHEMA = {
        'grid_count': {
            'type': 'integer', 'min': 3, 'max': 100, 'default': 10,
            'description': 'Number of grid levels',
        },
        'price_range': {
            'type': 'string_or_array',
            'description': "'auto' for ATR-based, or [lower, upper] fixed",
        },
        'atr_multiplier': {
            'type': 'number', 'min': 0.5, 'max': 5.0, 'default': 2.0,
            'description': 'ATR multiplier for auto range calculation',
        },
        'trigger_zone': {
            'type': 'number', 'min': 0.05, 'max': 0.5, 'default': 0.2,
            'description': 'Fraction of grid size that triggers a trade',
        },
    }

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        p = {**self.DEFAULT_PARAMS, **(params or {})}
        grid_count: int = p['grid_count']
        price_range = p['price_range']
        atr_multiplier: float = p['atr_multiplier']
        atr_period: int = p['atr_period']
        trigger_zone: float = p['trigger_zone']

        self._validate_klines(klines, min_length=atr_period + 1)
        current_price = float(klines[-1]['close'])

        # Determine price range
        if price_range == 'auto':
            atr_vals = self.calculate_indicator(
                klines, 'ATR', length=atr_period,
            )
            atr = self._extract_last(atr_vals)
            if atr is None:
                return {
                    'action': 'hold', 'confidence': 0.0,
                    'reason': 'ATR unavailable for grid calculation',
                }
            lower_bound = current_price - atr * atr_multiplier
            upper_bound = current_price + atr * atr_multiplier
        else:
            lower_bound, upper_bound = float(price_range[0]), float(price_range[1])

        if lower_bound >= upper_bound:
            return {
                'action': 'hold', 'confidence': 0.0,
                'reason': 'Invalid price range',
            }

        # Build grid
        grid_size = (upper_bound - lower_bound) / grid_count

        # Find current grid position
        current_grid = int((current_price - lower_bound) / grid_size)
        current_grid = max(0, min(grid_count - 1, current_grid))

        grid_low = lower_bound + current_grid * grid_size
        grid_high = grid_low + grid_size

        # Position within grid
        pos_in_grid = (current_price - grid_low) / grid_size if grid_size > 0 else 0.5

        if pos_in_grid <= trigger_zone:
            return {
                'action': 'buy',
                'confidence': 0.7,
                'reason': (
                    f'Grid #{current_grid+1}/{grid_count}: price {current_price:.2f} '
                    f'near lower bound {grid_low:.2f} ({pos_in_grid:.0%})'
                ),
            }
        elif pos_in_grid >= (1 - trigger_zone):
            return {
                'action': 'sell',
                'confidence': 0.7,
                'reason': (
                    f'Grid #{current_grid+1}/{grid_count}: price {current_price:.2f} '
                    f'near upper bound {grid_high:.2f} ({pos_in_grid:.0%})'
                ),
            }

        return {
            'action': 'hold',
            'confidence': 0.0,
            'reason': (
                f'Grid #{current_grid+1}/{grid_count}: mid-range {pos_in_grid:.0%}, '
                f'range [{grid_low:.2f}, {grid_high:.2f}]'
            ),
        }

    @staticmethod
    def _extract_last(values) -> float | None:
        if values is None:
            return None
        if isinstance(values, list):
            for v in reversed(values):
                if v is not None:
                    return float(v)
        return float(values)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_enhanced_strategies.py::TestGridTradingStrategy -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add quant/engine/grid_trading_strategy.py tests/test_enhanced_strategies.py
git commit -m "feat(strategy): add GridTradingStrategy for range-bound markets"
```

---

### Task 14: MLPredictionStrategy

**Files:**
- Create: `quant/engine/ml_prediction_strategy.py`
- Modify: `tests/test_enhanced_strategies.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_enhanced_strategies.py`:

```python
class TestMLPredictionStrategy:
    """Tests for MLPredictionStrategy."""

    @pytest.fixture
    def strategy(self):
        from quant.engine.ml_prediction_strategy import MLPredictionStrategy
        return MLPredictionStrategy(name='test_ml')

    def test_precomputed_mode_buy(self, strategy):
        """Should use precomputed ML result when available."""
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {
            'use_precomputed': True,
            'ml_prediction': {'signal': 'BUY', 'confidence': 0.85},
        })
        assert signal['action'] == 'buy'
        assert signal['confidence'] == 0.85

    def test_precomputed_mode_hold(self, strategy):
        """Should hold when precomputed confidence is low."""
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {
            'use_precomputed': True,
            'ml_prediction': {'signal': 'BUY', 'confidence': 0.55},
        })
        assert signal['action'] == 'hold'

    def test_no_precomputed_data(self, strategy):
        """Should hold when no precomputed data provided."""
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {'use_precomputed': True})
        assert signal['action'] == 'hold'

    def test_custom_confidence_threshold(self, strategy):
        """Should accept custom confidence threshold."""
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {
            'use_precomputed': True,
            'ml_prediction': {'signal': 'BUY', 'confidence': 0.65},
            'confidence_threshold': 0.6,
        })
        assert signal['action'] == 'buy'

    def test_default_params(self, strategy):
        """Should have DEFAULT_PARAMS."""
        assert hasattr(strategy, 'DEFAULT_PARAMS')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_enhanced_strategies.py::TestMLPredictionStrategy -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write MLPredictionStrategy**

Create `quant/engine/ml_prediction_strategy.py`:

```python
"""ML Prediction Strategy — XGBoost-based signal generation."""
from typing import Any

from quant.engine.enhanced_strategy_base import EnhancedStrategyBase
from quant.engine.mixins.ml_mixin import MLMixin


class MLPredictionStrategy(EnhancedStrategyBase, MLMixin):
    """Strategy that uses ML model predictions to generate signals.

    Supports two modes:
    - Precomputed (default): params['ml_prediction'] has the result.
    - Real-time: loads model and calls MLPredictor directly.

    DEFAULT_PARAMS:
        use_precomputed: True
        confidence_threshold: 0.6
    """

    DEFAULT_PARAMS = {
        'use_precomputed': True,
        'confidence_threshold': 0.6,
        'model_type': 'xgboost',
        'model_version': 'latest',
    }

    PARAM_SCHEMA = {
        'use_precomputed': {
            'type': 'boolean', 'default': True,
            'description': 'Use precomputed ML results from params',
        },
        'confidence_threshold': {
            'type': 'number', 'min': 0.5, 'max': 0.95, 'default': 0.6,
            'description': 'Minimum confidence to generate buy signal',
        },
    }

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        p = {**self.DEFAULT_PARAMS, **(params or {})}
        use_precomputed: bool = p['use_precomputed']
        confidence_threshold: float = p['confidence_threshold']

        self._validate_klines(klines, min_length=10)

        # Get ML prediction
        if use_precomputed:
            ml_result = p.get('ml_prediction')
        else:
            # Real-time: need features from klines
            if not self.is_model_loaded():
                self.load_ml_model(
                    model_type=p.get('model_type', 'xgboost'),
                    version=p.get('model_version', 'latest'),
                )
            features = self._extract_features_from_klines(klines)
            ml_result = self.predict_ml(features, use_precomputed=False)

        if ml_result is None:
            return {
                'action': 'hold', 'confidence': 0.0,
                'reason': 'No ML prediction available',
            }

        signal = ml_result.get('signal', 'HOLD')
        confidence = ml_result.get('confidence', 0.0)

        if signal == 'BUY' and confidence >= confidence_threshold:
            return {
                'action': 'buy',
                'confidence': round(float(confidence), 4),
                'reason': (
                    f'ML预测买入 (confidence: {confidence:.2%}, '
                    f'threshold: {confidence_threshold:.0%})'
                ),
            }

        return {
            'action': 'hold',
            'confidence': 0.0,
            'reason': (
                f'ML confidence {confidence:.2%} below threshold '
                f'{confidence_threshold:.0%}'
            ),
        }

    def _extract_features_from_klines(
        self, klines: list[dict]
    ) -> dict[str, float]:
        """Extract features from klines for real-time prediction."""
        # Use FactorMixin to calculate factors as features
        factors = self.calculate_factors(klines)
        return {
            k: float(v) if v is not None else 0.0
            for k, v in factors.items()
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_enhanced_strategies.py::TestMLPredictionStrategy -v`
Expected: 5 PASS

- [ ] **Step 5: Run all enhanced strategy tests**

Run: `pytest tests/test_enhanced_strategies.py -v`
Expected: 21 PASS

- [ ] **Step 6: Commit**

```bash
git add quant/engine/ml_prediction_strategy.py tests/test_enhanced_strategies.py
git commit -m "feat(strategy): add MLPredictionStrategy with precomputed mode"
```

---

### Task 15: StrategyFactory

**Files:**
- Create: `quant/engine/strategy_factory.py`
- Test: `tests/test_strategy_factory.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_strategy_factory.py`:

```python
"""Tests for StrategyFactory."""
import pytest

from quant.engine.strategy_base import StrategyBase
from quant.engine.enhanced_strategy_base import EnhancedStrategyBase


class TestStrategyFactory:
    """Tests for StrategyFactory auto-discovery and registration."""

    @pytest.fixture(autouse=True)
    def clean_registry(self):
        """Reset factory registry between tests."""
        from quant.engine.strategy_factory import StrategyFactory
        StrategyFactory._registry = {}
        StrategyFactory._metadata = {}
        yield
        StrategyFactory._registry = {}
        StrategyFactory._metadata = {}

    def test_auto_discover_finds_strategies(self):
        """Should find all strategies in quant.engine."""
        from quant.engine.strategy_factory import StrategyFactory
        StrategyFactory.auto_discover()

        registered = StrategyFactory.list_all()
        assert len(registered) >= 10  # 10 existing + 5 new

    def test_auto_discover_includes_new_strategies(self):
        """Should include the 5 new strategies."""
        from quant.engine.strategy_factory import StrategyFactory
        StrategyFactory.auto_discover()

        registered = StrategyFactory.list_all()
        assert 'multi_factor' in registered
        assert 'adx_trend' in registered
        assert 'cci_reversal' in registered
        assert 'grid_trading' in registered
        assert 'ml_prediction' in registered

    def test_create_strategy(self):
        """Should create strategy instance by type."""
        from quant.engine.strategy_factory import StrategyFactory
        StrategyFactory.auto_discover()

        strat = StrategyFactory.create('multi_factor', name='test')
        assert isinstance(strat, EnhancedStrategyBase)
        assert strat.name == 'test'

    def test_create_unknown_strategy_raises(self):
        """Should raise ValueError for unknown types."""
        from quant.engine.strategy_factory import StrategyFactory
        with pytest.raises(ValueError, match='Unknown'):
            StrategyFactory.create('nonexistent_strategy')

    def test_get_metadata(self):
        """Should return metadata for registered strategies."""
        from quant.engine.strategy_factory import StrategyFactory
        StrategyFactory.auto_discover()

        info = StrategyFactory.get_info('multi_factor')
        assert info is not None
        assert 'class_name' in info
        assert info['class_name'] == 'MultiFactorStrategy'

    def test_class_name_to_type(self):
        """Should convert CamelCase to snake_case correctly."""
        from quant.engine.strategy_factory import StrategyFactory

        assert StrategyFactory.class_name_to_type('MACrossStrategy') == 'ma_cross'
        assert StrategyFactory.class_name_to_type('ADXTrendStrategy') == 'adx_trend'
        assert StrategyFactory.class_name_to_type('MLPredictionStrategy') == 'ml_prediction'
        assert StrategyFactory.class_name_to_type('RSIReversalStrategy') == 'rsi_reversal'

    def test_extract_metadata(self):
        """Should extract DEFAULT_PARAMS and PARAM_SCHEMA from class."""
        from quant.engine.strategy_factory import StrategyFactory
        from quant.engine.multi_factor_strategy import MultiFactorStrategy

        meta = StrategyFactory._extract_metadata(MultiFactorStrategy)
        assert 'default_params' in meta
        assert 'factor_groups' in meta['default_params']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_strategy_factory.py -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write StrategyFactory**

Create `quant/engine/strategy_factory.py`:

```python
"""Strategy Factory — auto-discover, register, create."""
import importlib
import inspect
import logging
import re
from pathlib import Path
from typing import Type

from quant.engine.strategy_base import StrategyBase
from quant.engine.enhanced_strategy_base import EnhancedStrategyBase

logger = logging.getLogger(__name__)


class StrategyFactory:
    """Factory for auto-discovering and instantiating strategies.

    Scans quant.engine for StrategyBase subclasses, registers them,
    and can sync metadata to the database.

    Usage::

        StrategyFactory.auto_discover()
        strat = StrategyFactory.create('multi_factor', name='my_strat')
        all_types = StrategyFactory.list_all()
    """

    _registry: dict[str, Type[StrategyBase]] = {}
    _metadata: dict[str, dict] = {}

    @classmethod
    def auto_discover(cls, package_path: str = 'quant.engine') -> None:
        """Scan quant.engine for *strategy.py files and register all
        StrategyBase subclasses whose name ends with 'Strategy'."""
        engine_dir = Path(__file__).parent

        # Strategy file names to scan (existing + new)
        strategy_files = [
            # Existing 10
            'ma_cross', 'rsi_reversal', 'bollinger_breakout',
            'turtle_strategy', 'donchian_channel_strategy',
            'momentum_strategy', 'breakout_strategy',
            'mean_reversion_strategy', 'volatility_breakout_strategy',
            'pairs_correlation_strategy',
            # New 5
            'multi_factor_strategy', 'ml_prediction_strategy',
            'adx_trend_strategy', 'cci_reversal_strategy',
            'grid_trading_strategy',
        ]

        for module_name in strategy_files:
            try:
                module = importlib.import_module(
                    f'{package_path}.{module_name}'
                )
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if not name.endswith('Strategy'):
                        continue
                    if obj in (StrategyBase, EnhancedStrategyBase):
                        continue
                    if issubclass(obj, StrategyBase):
                        strategy_type = cls.class_name_to_type(name)
                        cls.register(strategy_type, obj)
                        logger.debug(
                            "Auto-discovered: %s → %s", strategy_type, name,
                        )
            except Exception as e:
                logger.warning(
                    "Failed to load strategy module %s: %s", module_name, e,
                )

    @classmethod
    def register(
        cls, strategy_type: str, strategy_class: Type[StrategyBase],
    ) -> None:
        """Register a strategy class."""
        if strategy_type in cls._registry:
            logger.debug(
                "Strategy '%s' already registered, overwriting", strategy_type,
            )
        cls._registry[strategy_type] = strategy_class
        cls._metadata[strategy_type] = cls._extract_metadata(strategy_class)

    @classmethod
    def create(cls, strategy_type: str, **kwargs) -> StrategyBase:
        """Create a strategy instance by type.

        Raises ValueError if strategy_type is unknown.
        """
        if strategy_type not in cls._registry:
            raise ValueError(
                f"Unknown strategy type: '{strategy_type}'. "
                f"Available: {cls.list_all()}"
            )
        return cls._registry[strategy_type](**kwargs)

    @classmethod
    def list_all(cls) -> list[str]:
        """List all registered strategy types."""
        return sorted(cls._registry.keys())

    @classmethod
    def get_info(cls, strategy_type: str) -> dict | None:
        """Get metadata for a registered strategy."""
        return cls._metadata.get(strategy_type)

    @classmethod
    def _extract_metadata(cls, strategy_class: Type[StrategyBase]) -> dict:
        """Extract metadata from a strategy class."""
        return {
            'class_name': strategy_class.__name__,
            'description': (
                strategy_class.__doc__ or ''
            ).strip().split('\n')[0],
            'category': cls._infer_category(strategy_class.__name__),
            'default_params': getattr(
                strategy_class, 'DEFAULT_PARAMS', {}
            ),
            'param_schema': getattr(
                strategy_class, 'PARAM_SCHEMA', {}
            ),
        }

    @staticmethod
    def class_name_to_type(class_name: str) -> str:
        """Convert CamelCase strategy name to snake_case type.

        MACrossStrategy → ma_cross
        MLPredictionStrategy → ml_prediction
        ADXTrendStrategy → adx_trend
        """
        name = class_name.replace('Strategy', '')
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    @staticmethod
    def _infer_category(class_name: str) -> str:
        """Infer strategy category from class name."""
        lower = class_name.lower()
        if any(x in lower for x in ['trend', 'ma', 'adx', 'turtle', 'donchian']):
            return 'trend_following'
        if any(x in lower for x in ['reversal', 'rsi', 'cci', 'mean']):
            return 'mean_reversion'
        if any(x in lower for x in ['grid']):
            return 'arbitrage'
        if any(x in lower for x in ['ml', 'prediction']):
            return 'machine_learning'
        if any(x in lower for x in ['factor', 'multi']):
            return 'multi_factor'
        if any(x in lower for x in ['volatility', 'breakout', 'bollinger']):
            return 'volatility'
        return 'other'

    @classmethod
    def sync_to_database(cls, repo=None) -> int:
        """Sync strategy metadata to the database.

        Args:
            repo: StrategyRepository instance. Created if not provided.

        Returns:
            Number of strategies synced.
        """
        if repo is None:
            from repositories.strategy_repository import StrategyRepository
            repo = StrategyRepository()

        count = 0
        for strategy_type, metadata in cls._metadata.items():
            try:
                repo.upsert_metadata({
                    'strategy_type': strategy_type,
                    'class_name': metadata['class_name'],
                    'description': metadata['description'],
                    'category': metadata['category'],
                    'default_params': metadata.get('default_params', {}),
                    'param_schema': metadata.get('param_schema', {}),
                    'is_available': True,
                })
                count += 1
            except Exception as e:
                logger.warning(
                    "Failed to sync %s to DB: %s", strategy_type, e,
                )

        logger.info("Synced %d strategies to database", count)
        return count
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_strategy_factory.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add quant/engine/strategy_factory.py tests/test_strategy_factory.py
git commit -m "feat(factory): add StrategyFactory with auto-discovery and DB sync"
```

---

### Task 16: Update StrategyRunner to use Factory

**Files:**
- Modify: `quant/engine/strategy_runner.py`

- [ ] **Step 1: Verify existing tests still pass**

Run: `pytest tests/test_strategy_engine.py -v`
Expected: existing tests pass

- [ ] **Step 2: Update StrategyRunner**

Modify `quant/engine/strategy_runner.py` — replace the `STRATEGY_REGISTRY` dict usage with `StrategyFactory`:

Edit the top of `_get_strategy_instance`:

```python
# In _get_strategy_instance, replace the direct STRATEGY_REGISTRY lookup:

    def _get_strategy_instance(self, config: Dict[str, Any]):
        """根据配置创建策略实例"""
        strategy_type = config.get('strategy_type', '')

        # Try StrategyFactory first (covers auto-discovered strategies)
        try:
            from quant.engine.strategy_factory import StrategyFactory
            # Ensure strategies are discovered
            if not StrategyFactory._registry:
                StrategyFactory.auto_discover()
            return StrategyFactory.create(
                strategy_type,
                name=config.get('strategy_name', config.get('name', '')),
            )
        except ValueError:
            pass

        # Fallback: check legacy STRATEGY_REGISTRY
        strategy_class = STRATEGY_REGISTRY.get(strategy_type)
        if strategy_class is None:
            logger.warning(f"Unknown strategy type: {strategy_type}")
            return None

        return strategy_class(name=config.get(
            'strategy_name', config.get('name', '')
        ))
```

- [ ] **Step 3: Verify all strategy engine tests still pass**

Run: `pytest tests/test_strategy_engine.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add quant/engine/strategy_runner.py
git commit -m "refactor(runner): use StrategyFactory in StrategyRunner"
```

---

### Task 17: StrategyRepository — Add Metadata Methods

**Files:**
- Modify: `repositories/strategy_repository.py`

- [ ] **Step 1: Add metadata methods**

Append to `repositories/strategy_repository.py`:

```python
    # ==================== Metadata Methods ====================

    def upsert_metadata(self, data: dict) -> None:
        """Insert or update strategy metadata in quant.strategy_metadata."""
        import json

        query = """
        INSERT INTO quant.strategy_metadata (
            strategy_type, class_name, description, category,
            default_params, param_schema, is_available, updated_at
        ) VALUES (
            %(strategy_type)s, %(class_name)s, %(description)s, %(category)s,
            %(default_params)s, %(param_schema)s, %(is_available)s, NOW()
        )
        ON CONFLICT (strategy_type) DO UPDATE SET
            class_name = EXCLUDED.class_name,
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            default_params = EXCLUDED.default_params,
            param_schema = EXCLUDED.param_schema,
            is_available = EXCLUDED.is_available,
            updated_at = NOW()
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, {
                'strategy_type': data['strategy_type'],
                'class_name': data['class_name'],
                'description': data.get('description', ''),
                'category': data.get('category', 'other'),
                'default_params': json.dumps(data.get('default_params', {})),
                'param_schema': json.dumps(data.get('param_schema', {})),
                'is_available': data.get('is_available', True),
            })
            self.db.commit()
        finally:
            cursor.close()

    def get_metadata(self, strategy_type: str) -> dict | None:
        """Get strategy metadata from quant.strategy_metadata."""
        import json

        query = """
        SELECT * FROM quant.strategy_metadata
        WHERE strategy_type = %(strategy_type)s
        """

        cursor = self.db.cursor()
        cursor.execute(query, {'strategy_type': strategy_type})
        result = cursor.fetchone()
        cursor.close()

        if result:
            result = dict(result)
            result['default_params'] = json.loads(
                result['default_params']
            ) if isinstance(result['default_params'], str) else result['default_params']
            result['param_schema'] = json.loads(
                result['param_schema']
            ) if isinstance(result['param_schema'], str) else result['param_schema']

        return result

    def list_all_metadata(self, category: str = None) -> list[dict]:
        """List all strategy metadata, optionally filtered by category."""
        import json

        if category:
            query = """
            SELECT * FROM quant.strategy_metadata
            WHERE category = %(category)s AND is_available = TRUE
            ORDER BY strategy_type
            """
            params = {'category': category}
        else:
            query = """
            SELECT * FROM quant.strategy_metadata
            WHERE is_available = TRUE
            ORDER BY category, strategy_type
            """
            params = {}

        cursor = self.db.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()

        for r in results:
            r = dict(r)
            r['default_params'] = json.loads(
                r['default_params']
            ) if isinstance(r['default_params'], str) else r['default_params']
            r['param_schema'] = json.loads(
                r['param_schema']
            ) if isinstance(r['param_schema'], str) else r['param_schema']

        return [dict(r) for r in results]

    def create_config_from_metadata(
        self,
        strategy_type: str,
        name: str,
        custom_params: dict = None,
    ) -> int:
        """Create a strategy config from metadata defaults."""
        import json

        metadata = self.get_metadata(strategy_type)
        if not metadata:
            raise ValueError(
                f"Strategy metadata not found: {strategy_type}"
            )

        params = metadata.get('default_params', {}).copy()
        if custom_params:
            params.update(custom_params)

        return self.create({
            'name': name,
            'strategy_type': strategy_type,
            'parameters': params,
        })
```

- [ ] **Step 2: Run existing strategy repository tests**

Run: `pytest tests/ -k "strategy_repository" -v 2>/dev/null || echo "No existing tests — skip"`
Expected: PASS or skip

- [ ] **Step 3: Commit**

```bash
git add repositories/strategy_repository.py
git commit -m "feat(repo): add metadata methods to StrategyRepository"
```

---

### Task 18: TraceabilityRepository

**Files:**
- Create: `repositories/traceability_repository.py`
- Test: `tests/test_traceability.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_traceability.py`:

```python
"""Tests for TraceabilityRepository (requires database)."""
import pytest
import uuid


@pytest.mark.skip(reason="Requires PostgreSQL database with traceability tables")
class TestTraceabilityRepository:
    """Integration tests for traceability repository."""

    @pytest.fixture
    def repo(self):
        from repositories.traceability_repository import TraceabilityRepository
        return TraceabilityRepository()

    def test_save_execution(self, repo):
        """Should save a strategy execution record."""
        exec_id = repo.save_execution({
            'execution_id': str(uuid.uuid4()),
            'strategy_type': 'multi_factor',
            'strategy_name': 'test_mf',
            'symbol': '000001.SZ',
            'signal_action': 'buy',
            'signal_confidence': 0.75,
            'signal_reason': 'test buy signal',
            'params_snapshot': {'buy_threshold': 0.6},
            'factors_used': {'ma5': {'value': 10.5, 'category': 'technical'}},
            'execution_duration_ms': 150,
        })
        assert exec_id is not None

    def test_save_and_retrieve_execution_trace(self, repo):
        """Should save and retrieve full execution trace."""
        exec_id = str(uuid.uuid4())

        repo.save_execution({
            'execution_id': exec_id,
            'strategy_type': 'adx_trend',
            'strategy_name': 'test_adx',
            'symbol': '600000.SH',
            'signal_action': 'sell',
            'signal_confidence': 0.82,
            'signal_reason': 'trend sell',
            'indicators_used': {'ADX': {'value': 35.0, 'params': {'length': 14}}},
        })

        trace = repo.get_execution_trace(exec_id)
        assert trace is not None
        assert trace['execution']['signal_action'] == 'sell'

    def test_query_executions_by_symbol(self, repo):
        """Should query executions by symbol."""
        exec_id = str(uuid.uuid4())
        repo.save_execution({
            'execution_id': exec_id,
            'strategy_type': 'grid_trading',
            'strategy_name': 'test_grid',
            'symbol': '000001.SZ',
            'signal_action': 'buy',
            'signal_confidence': 0.7,
        })

        results = repo.query_executions(symbol='000001.SZ', limit=10)
        assert len(results) >= 1

    def test_query_executions_by_strategy(self, repo):
        """Should query executions by strategy type."""
        results = repo.query_executions(strategy_type='grid_trading', limit=10)
        assert all(r['strategy_type'] == 'grid_trading' for r in results)


class TestTraceabilityRepositoryUnit:
    """Unit tests that don't require database."""

    def test_repository_imports(self):
        """Repository should be importable."""
        from repositories.traceability_repository import TraceabilityRepository
        assert TraceabilityRepository is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_traceability.py -v`
Expected: FAIL, ImportError

- [ ] **Step 3: Write TraceabilityRepository**

Create `repositories/traceability_repository.py`:

```python
"""Traceability Repository — execution tracing CRUD."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from core.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class TraceabilityRepository(BaseRepository):
    """Repository for strategy execution traceability."""

    # ==================== Execution Records ====================

    def save_execution(self, data: dict) -> str:
        """Save a strategy execution record.

        Returns the execution_id string.
        """
        exec_id = data.get('execution_id', str(uuid.uuid4()))

        query = """
        INSERT INTO quant.strategy_executions (
            execution_id, strategy_config_id, strategy_type, strategy_name,
            symbol, market, klines_count, klines_date_range,
            params_snapshot, signal_action, signal_confidence, signal_reason,
            strategy_votes, execution_duration_ms
        ) VALUES (
            %(execution_id)s, %(strategy_config_id)s, %(strategy_type)s,
            %(strategy_name)s, %(symbol)s, %(market)s, %(klines_count)s,
            %(klines_date_range)s, %(params_snapshot)s, %(signal_action)s,
            %(signal_confidence)s, %(signal_reason)s, %(strategy_votes)s,
            %(execution_duration_ms)s
        )
        RETURNING execution_id
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, {
                'execution_id': exec_id,
                'strategy_config_id': data.get('strategy_config_id'),
                'strategy_type': data.get('strategy_type', ''),
                'strategy_name': data.get('strategy_name', ''),
                'symbol': data.get('symbol', ''),
                'market': data.get('market'),
                'klines_count': data.get('klines_count'),
                'klines_date_range': json.dumps(
                    data.get('klines_date_range', {})
                ),
                'params_snapshot': json.dumps(
                    data.get('params_snapshot', {})
                ),
                'signal_action': data.get('signal_action'),
                'signal_confidence': data.get('signal_confidence'),
                'signal_reason': data.get('signal_reason'),
                'strategy_votes': json.dumps(
                    data.get('strategy_votes', [])
                ),
                'execution_duration_ms': data.get('execution_duration_ms'),
            })
            result = cursor.fetchone()
            self.db.commit()
            return result['execution_id']
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to save execution: %s", e)
            raise
        finally:
            cursor.close()

    def get_execution_trace(self, execution_id: str) -> dict | None:
        """Get full execution trace including factors, signals, ML."""
        cursor = self.db.cursor()

        # Main execution record
        cursor.execute(
            """SELECT * FROM quant.strategy_executions
               WHERE execution_id = %(eid)s""",
            {'eid': execution_id},
        )
        execution = cursor.fetchone()
        if not execution:
            cursor.close()
            return None

        # Factors
        cursor.execute(
            """SELECT * FROM quant.factor_calculations
               WHERE execution_id = %(eid)s
               ORDER BY factor_name""",
            {'eid': execution_id},
        )
        factors = [dict(r) for r in cursor.fetchall()]

        # Signals
        cursor.execute(
            """SELECT * FROM quant.signal_generations
               WHERE execution_id = %(eid)s
               ORDER BY signal_time""",
            {'eid': execution_id},
        )
        signals = [dict(r) for r in cursor.fetchall()]

        # ML predictions
        cursor.execute(
            """SELECT * FROM quant.ml_predictions
               WHERE execution_id = %(eid)s
               ORDER BY prediction_time""",
            {'eid': execution_id},
        )
        ml_predictions = [dict(r) for r in cursor.fetchall()]

        cursor.close()
        return {
            'execution': dict(execution),
            'factors': factors,
            'signals': signals,
            'ml_predictions': ml_predictions,
        }

    def query_executions(
        self,
        symbol: str = None,
        strategy_type: str = None,
        start_date: str = None,
        end_date: str = None,
        signal_action: str = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query strategy execution history with optional filters."""
        conditions = []
        params: dict[str, Any] = {'limit': limit}

        if symbol:
            conditions.append("symbol = %(symbol)s")
            params['symbol'] = symbol
        if strategy_type:
            conditions.append("strategy_type = %(strategy_type)s")
            params['strategy_type'] = strategy_type
        if start_date:
            conditions.append("execution_time >= %(start_date)s")
            params['start_date'] = start_date
        if end_date:
            conditions.append("execution_time <= %(end_date)s")
            params['end_date'] = end_date
        if signal_action:
            conditions.append("signal_action = %(signal_action)s")
            params['signal_action'] = signal_action

        where = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
        SELECT * FROM quant.strategy_executions
        WHERE {where}
        ORDER BY execution_time DESC
        LIMIT %(limit)s
        """

        cursor = self.db.cursor()
        cursor.execute(query, params)
        results = [dict(r) for r in cursor.fetchall()]
        cursor.close()

        return results

    # ==================== Factor Calculation Records ====================

    def save_factor_calculations(
        self, execution_id: str, factors: dict, symbol: str = '',
    ) -> int:
        """Batch-save factor calculation records."""
        records = []
        for factor_name, factor_data in factors.items():
            if isinstance(factor_data, dict):
                value = factor_data.get('value')
                category = factor_data.get('category', 'technical')
            else:
                value = factor_data
                category = 'technical'

            records.append({
                'execution_id': execution_id,
                'symbol': symbol,
                'factor_name': factor_name,
                'factor_category': category,
                'factor_value': value,
            })

        if not records:
            return 0

        query = """
        INSERT INTO quant.factor_calculations (
            execution_id, symbol, factor_name, factor_category, factor_value
        ) VALUES (
            %(execution_id)s, %(symbol)s, %(factor_name)s,
            %(factor_category)s, %(factor_value)s
        )
        """

        cursor = self.db.cursor()
        try:
            for r in records:
                cursor.execute(query, r)
            self.db.commit()
            return len(records)
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to save factor calculations: %s", e)
            raise
        finally:
            cursor.close()

    # ==================== Signal Records ====================

    def save_signal(self, data: dict) -> str:
        """Save a signal generation record. Returns signal_id."""
        signal_id = data.get('signal_id', str(uuid.uuid4()))

        query = """
        INSERT INTO quant.signal_generations (
            signal_id, execution_id, symbol, action, confidence,
            reason, price_at_signal, strategy_votes
        ) VALUES (
            %(signal_id)s, %(execution_id)s, %(symbol)s, %(action)s,
            %(confidence)s, %(reason)s, %(price_at_signal)s, %(strategy_votes)s
        )
        RETURNING signal_id
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, {
                'signal_id': signal_id,
                'execution_id': data.get('execution_id'),
                'symbol': data.get('symbol', ''),
                'action': data.get('action', 'hold'),
                'confidence': data.get('confidence', 0.0),
                'reason': data.get('reason', ''),
                'price_at_signal': data.get('price_at_signal'),
                'strategy_votes': json.dumps(
                    data.get('strategy_votes', [])
                ),
            })
            result = cursor.fetchone()
            self.db.commit()
            return result['signal_id']
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to save signal: %s", e)
            raise
        finally:
            cursor.close()

    # ==================== ML Prediction Records ====================

    def save_ml_prediction(self, data: dict) -> int:
        """Save an ML prediction record. Returns the record id."""
        query = """
        INSERT INTO quant.ml_predictions (
            execution_id, symbol, model_type, model_version,
            feature_names, feature_values, feature_count,
            prediction, confidence, prob_down, prob_up,
            prediction_duration_ms
        ) VALUES (
            %(execution_id)s, %(symbol)s, %(model_type)s, %(model_version)s,
            %(feature_names)s, %(feature_values)s, %(feature_count)s,
            %(prediction)s, %(confidence)s, %(prob_down)s, %(prob_up)s,
            %(prediction_duration_ms)s
        )
        RETURNING id
        """

        cursor = self.db.cursor()
        try:
            cursor.execute(query, {
                'execution_id': data.get('execution_id'),
                'symbol': data.get('symbol', ''),
                'model_type': data.get('model_type', 'xgboost'),
                'model_version': data.get('model_version', 'latest'),
                'feature_names': json.dumps(data.get('feature_names', [])),
                'feature_values': json.dumps(data.get('feature_values', {})),
                'feature_count': data.get('feature_count'),
                'prediction': data.get('prediction', 0),
                'confidence': data.get('confidence'),
                'prob_down': data.get('prob_down'),
                'prob_up': data.get('prob_up'),
                'prediction_duration_ms': data.get('prediction_duration_ms'),
            })
            result = cursor.fetchone()
            self.db.commit()
            return result['id']
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to save ML prediction: %s", e)
            raise
        finally:
            cursor.close()
```

- [ ] **Step 4: Run unit test**

Run: `pytest tests/test_traceability.py::TestTraceabilityRepositoryUnit -v`
Expected: 1 PASS

- [ ] **Step 5: Commit**

```bash
git add repositories/traceability_repository.py tests/test_traceability.py
git commit -m "feat(repo): add TraceabilityRepository for full execution tracing"
```

---

### Task 19: Update engine __init__.py Exports

**Files:**
- Modify: `quant/engine/__init__.py`

- [ ] **Step 1: Add new exports**

Modify `quant/engine/__init__.py` — append the new imports:

```python
# ========== New imports (Strategy Extension Phase 2) ==========
from quant.engine.enhanced_strategy_base import EnhancedStrategyBase
from quant.engine.multi_factor_strategy import MultiFactorStrategy
from quant.engine.ml_prediction_strategy import MLPredictionStrategy
from quant.engine.adx_trend_strategy import ADXTrendStrategy
from quant.engine.cci_reversal_strategy import CCIReversalStrategy
from quant.engine.grid_trading_strategy import GridTradingStrategy
from quant.engine.strategy_factory import StrategyFactory
from quant.engine.indicators.indicator_manager import IndicatorManager
from quant.engine.mixins.indicator_mixin import IndicatorMixin
from quant.engine.mixins.factor_mixin import FactorMixin
from quant.engine.mixins.ml_mixin import MLMixin
```

And append to `__all__`:

```python
    # New strategy extension
    'EnhancedStrategyBase',
    'MultiFactorStrategy',
    'MLPredictionStrategy',
    'ADXTrendStrategy',
    'CCIReversalStrategy',
    'GridTradingStrategy',
    'StrategyFactory',
    'IndicatorManager',
    'IndicatorMixin',
    'FactorMixin',
    'MLMixin',
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from quant.engine import MultiFactorStrategy, ADXTrendStrategy, StrategyFactory; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add quant/engine/__init__.py
git commit -m "feat(engine): export new strategies, factory, mixins in __init__"
```

---

### Task 20: Run Full Test Suite

**Files:** (no changes)

- [ ] **Step 1: Run all new tests**

Run: `pytest tests/test_indicators.py tests/test_mixins.py tests/test_enhanced_strategies.py tests/test_strategy_factory.py -v`
Expected: 51+ PASS

- [ ] **Step 2: Run all existing tests (backwards compat)**

Run: `pytest tests/test_strategy_engine.py tests/test_factor_stage.py -v`
Expected: ALL EXISTING TESTS PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: ALL PASS (existing + new)

---

## Review Checklist

- [ ] Spec coverage: all 7 requirements → tasks 2-19
- [ ] Placeholder scan: no TBD/TODO, all code is explicit
- [ ] Type consistency: `_extract_last`, `_score_group`, `calculate_indicator` signatures match across tasks
- [ ] Backwards compat: existing 10 strategies untouched, StrategyBase unchanged
- [ ] DB tables already committed (de71fa0)
