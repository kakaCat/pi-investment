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
│   ├── base_checker.py           # Base class for all checkers
│   ├── base_aggregator.py        # Base class for aggregators
│   ├── base_algo.py              # Base class for algorithms
│   ├── result_types.py           # CheckResult, ExecutionResult, etc.
│   ├── decorators.py             # @cached, @handle_broker_errors, etc.
│   ├── validators.py             # validate_symbol, validate_quantity, etc.
│   └── exceptions.py             # Business exceptions
├── risk/                          # Risk management domain (NEW)
│   ├── __init__.py
│   ├── orchestrator.py           # RiskOrchestrator
│   ├── checkers/
│   │   ├── __init__.py
│   │   ├── position_checker.py
│   │   ├── portfolio_checker.py
│   │   ├── market_checker.py
│   │   ├── trading_checker.py
│   │   ├── margin_checker.py
│   │   └── compliance_checker.py
│   └── utils.py
├── strategy/                      # Strategy management domain (NEW)
│   ├── __init__.py
│   ├── manager.py                # StrategyManager
│   ├── executor.py               # StrategyExecutor
│   ├── validator.py              # CodeValidator wrapper
│   ├── backtest_runner.py        # Backtest execution
│   └── utils.py
├── data/                          # Data service domain (NEW)
│   ├── __init__.py
│   ├── service.py                # DataService facade
│   ├── aggregators/
│   │   ├── __init__.py
│   │   ├── stock_aggregator.py
│   │   ├── portfolio_aggregator.py
│   │   ├── backtest_aggregator.py
│   │   └── signal_aggregator.py
│   └── cache_helper.py
└── execution/                     # Order execution domain (NEW)
    ├── __init__.py
    ├── orchestrator.py           # OrderExecutor
    ├── algos/
    │   ├── __init__.py
    │   ├── twap.py
    │   ├── vwap.py
    │   └── iceberg.py
    ├── broker_adapter.py
    └── utils.py
```

### Files to Delete
- `services/risk_service.py` (1196 lines)
- `services/strategy_code_service.py` (812 lines)
- `services/data_service.py` (690 lines)
- `services/execution_service.py` (671 lines)

### Files to Modify
- `api/routes/risk.py` - Update imports
- `api/routes/strategies.py` - Update imports
- `api/routes/signals.py` - Update imports
- `api/routes/executions.py` - Update imports
- `api/routes/analysis.py` - Update imports
- `cli/commands/strategy_commands.py` - Update imports
- Multiple test files - Update imports

---

## Phase 1: Preparation

### Task 1: Create Git Worktree

**Files:**
- Create: `.git/worktrees/service-layer-refactor/`

- [ ] **Step 1: Create worktree branch**

```bash
git worktree add .claude/worktrees/service-layer-refactor -b service-layer-refactor
```

Expected: `Preparing worktree (new branch 'service-layer-refactor')`

- [ ] **Step 2: Switch to worktree**

```bash
cd .claude/worktrees/service-layer-refactor
```

- [ ] **Step 3: Verify worktree**

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

Expected: All tests pass (baseline)

- [ ] **Step 2: Check test coverage**

```bash
pytest tests/ --cov=services --cov-report=term-missing
```

Expected: Coverage report showing current coverage

- [ ] **Step 3: Save coverage baseline**

```bash
pytest tests/ --cov=services --cov-report=html
cp -r htmlcov htmlcov_baseline
```

---

## Phase 2: Shared Tools Layer

### Task 3: Create Common Directory Structure

**Files:**
- Create: `services/common/__init__.py`

- [ ] **Step 1: Create common directory**

```bash
mkdir -p services/common
```

- [ ] **Step 2: Create __init__.py**

```python
# services/common/__init__.py
"""Shared tools and base classes for all services."""

from .base_checker import BaseChecker, CheckResult
from .base_aggregator import BaseAggregator
from .base_algo import BaseAlgo
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
    'BaseAggregator',
    'BaseAlgo',
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
git commit -m "feat(services): create common tools directory structure"
```

---

### Task 4: Implement Base Checker

**Files:**
- Create: `services/common/base_checker.py`

- [ ] **Step 1: Write base_checker.py**

```python
# services/common/base_checker.py
"""Base class for all risk checkers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


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
            CheckResult: Check result
        """
        pass
    
    def _build_result(
        self,
        passed: bool,
        message: str,
        severity: str = 'error',
        **kwargs
    ) -> CheckResult:
        """Build standardized result.
        
        Args:
            passed: Whether check passed
            message: Human-readable message
            severity: 'error' or 'warning'
            **kwargs: Additional metadata
        
        Returns:
            CheckResult
        """
        return CheckResult(
            passed=passed,
            rule_name=self.__class__.__name__,
            severity=severity,
            message=message,
            metadata=kwargs
        )
```

- [ ] **Step 2: Write test for BaseChecker**

```python
# tests/services/common/test_base_checker.py
"""Tests for BaseChecker."""

import pytest
from services.common.base_checker import BaseChecker, CheckResult


class DummyChecker(BaseChecker):
    """Test checker implementation."""
    
    def check(self, ds, context):
        if context.get('should_pass'):
            return self._build_result(True, "Check passed", severity='info')
        return self._build_result(False, "Check failed", severity='error')


def test_check_result_creation():
    """Test CheckResult dataclass."""
    result = CheckResult(
        passed=True,
        rule_name="TestRule",
        severity="warning",
        message="Test message",
        metadata={'key': 'value'}
    )
    
    assert result.passed is True
    assert result.rule_name == "TestRule"
    assert result.severity == "warning"
    assert result.message == "Test message"
    assert result.metadata == {'key': 'value'}


def test_check_result_str():
    """Test CheckResult string representation."""
    result = CheckResult(
        passed=False,
        rule_name="TestRule",
        severity="error",
        message="Failed"
    )
    
    assert "✗ FAIL" in str(result)
    assert "ERROR" in str(result)
    assert "TestRule" in str(result)


def test_base_checker_build_result():
    """Test _build_result helper."""
    checker = DummyChecker()
    result = checker._build_result(
        passed=True,
        message="Success",
        severity="info",
        extra_data="test"
    )
    
    assert result.passed is True
    assert result.rule_name == "DummyChecker"
    assert result.severity == "info"
    assert result.message == "Success"
    assert result.metadata['extra_data'] == "test"


def test_base_checker_check_pass():
    """Test checker passing."""
    checker = DummyChecker()
    result = checker.check(None, {'should_pass': True})
    
    assert result.passed is True
    assert result.severity == "info"


def test_base_checker_check_fail():
    """Test checker failing."""
    checker = DummyChecker()
    result = checker.check(None, {'should_pass': False})
    
    assert result.passed is False
    assert result.severity == "error"
```

- [ ] **Step 3: Create test directory**

```bash
mkdir -p tests/services/common
touch tests/services/common/__init__.py
```

- [ ] **Step 4: Run test**

```bash
pytest tests/services/common/test_base_checker.py -v
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add services/common/base_checker.py tests/services/common/
git commit -m "feat(services): add BaseChecker and CheckResult"
```

---

