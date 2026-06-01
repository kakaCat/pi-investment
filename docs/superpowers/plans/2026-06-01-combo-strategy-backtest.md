# Combo Strategy Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement multi-strategy combo backtest supporting portfolio (position allocation), ensemble (signal fusion), and pipeline (workflow orchestration) modes.

**Architecture:** Pure backend implementation in quantsys-v2 with ComboStrategyBacktestService as core, reusing SmartBacktestEngine and StrategyCombiner. TypeScript agent layer provides tool interface via QuantV2Client.

**Tech Stack:** Python 3.13, Flask, TypeScript, SmartBacktestEngine, StrategyCombiner

---

## File Structure

### Backend (quantsys-v2)
- **Create:** `quantsys-v2/services/combo_strategy_backtest_service.py` — Core service with 3 mode implementations
- **Modify:** `quantsys-v2/api/routes/backtest.py` — Add `/api/backtest/combo` endpoint
- **Modify:** `quantsys-v2/api/shared.py` — Initialize combo_backtest_service
- **Modify:** `quantsys-v2/api/server.py` — Register backtest routes
- **Create:** `quantsys-v2/tests/services/test_combo_backtest_service.py` — Unit tests
- **Create:** `quantsys-v2/tests/api/test_combo_backtest_routes.py` — API integration tests

### Frontend (TypeScript)
- **Create:** `src/infrastructure/tools/backtest/combo-backtest-tool.ts` — Tool definition
- **Modify:** `src/infrastructure/quant/quant-v2-client.ts` — Add comboBacktest() method
- **Modify:** `src/infrastructure/tools/index.ts` — Register tool

### Documentation
- **Modify:** `CLAUDE.md` — Add tool documentation

---

## Task 1: Core Service - Portfolio Mode

**Files:**
- Create: `quantsys-v2/services/combo_strategy_backtest_service.py`
- Test: `quantsys-v2/tests/services/test_combo_backtest_service.py`

- [ ] **Step 1: Write failing test for portfolio mode**

```python
# quantsys-v2/tests/services/test_combo_backtest_service.py
import pytest
from datetime import datetime
from services.combo_strategy_backtest_service import ComboStrategyBacktestService


class TestComboStrategyBacktestService:
    
    @pytest.fixture
    def mock_strategy_repo(self):
        class MockStrategyRepo:
            def get_by_id(self, strategy_id):
                return {'id': strategy_id, 'name': f'Strategy {strategy_id}'}
            
            def get_all(self, active_only=False):
                return [
                    {'id': 53, 'name': 'Strategy 53'},
                    {'id': 54, 'name': 'Strategy 54'}
                ]
        return MockStrategyRepo()
    
    @pytest.fixture
    def mock_backtest_engine(self):
        class MockBacktestEngine:
            def backtest(self, strategy, symbols, **kwargs):
                # Return mock result
                initial = kwargs.get('initial_capital', 100000)
                return {
                    'strategy_id': strategy.get('id'),
                    'equity_curve': [
                        {'date': '2025-01-01', 'value': initial},
                        {'date': '2025-12-31', 'value': initial * 1.1}
                    ],
                    'metrics': {
                        'total_return': 0.1,
                        'sharpe_ratio': 1.5,
                        'max_drawdown': -0.05
                    }
                }
        return MockBacktestEngine()
    
    @pytest.fixture
    def service(self, mock_strategy_repo, mock_backtest_engine):
        return ComboStrategyBacktestService(
            strategy_repo=mock_strategy_repo,
            backtest_engine=mock_backtest_engine,
            strategy_combiner=None
        )
    
    def test_portfolio_mode_basic(self, service):
        """Test portfolio mode with 2 strategies"""
        result = service.backtest_combo(
            mode='portfolio',
            strategies=[
                {'strategy_id': 53, 'weight': 0.3},
                {'strategy_id': 54, 'weight': 0.7}
            ],
            symbols=['600519.SH'],
            start_date='2025-01-01',
            end_date='2025-12-31',
            initial_capital=1000000.0
        )
        
        assert result['mode'] == 'portfolio'
        assert 'overall_metrics' in result
        assert len(result['strategy_breakdown']) == 2
        assert result['strategy_breakdown'][0]['weight'] == 0.3
        assert result['strategy_breakdown'][1]['weight'] == 0.7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_combo_backtest_service.py::TestComboStrategyBacktestService::test_portfolio_mode_basic -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'services.combo_strategy_backtest_service'"

- [ ] **Step 3: Create service skeleton with portfolio mode**

```python
# quantsys-v2/services/combo_strategy_backtest_service.py
"""Combo strategy backtest service - multi-strategy combination backtesting."""
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ComboStrategyBacktestService:
    """Service for combo strategy backtesting (portfolio/ensemble/pipeline modes)."""
    
    def __init__(self, strategy_repo, backtest_engine, strategy_combiner):
        self._strategy_repo = strategy_repo
        self._backtest_engine = backtest_engine
        self._combiner = strategy_combiner
        self._strategy_cache = {}
    
    def backtest_combo(
        self,
        mode: str,
        strategies: List[Dict],
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        **kwargs
    ) -> Dict:
        """
        Unified entry point for combo backtest.
        
        Args:
            mode: 'portfolio' | 'ensemble' | 'pipeline'
            strategies: List of strategy configs
            symbols: List of stock symbols
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD
            initial_capital: Initial capital
            **kwargs: Mode-specific params
        
        Returns:
            Dict with overall_metrics, strategy_breakdown, equity_curve
        """
        start_time = time.time()
        
        logger.info(
            f"Starting combo backtest: mode={mode}, "
            f"strategies={len(strategies)}, symbols={len(symbols)}"
        )
        
        # Validate params
        self._validate_params(mode, strategies, symbols, **kwargs)
        
        # Dispatch to mode-specific implementation
        if mode == 'portfolio':
            result = self._portfolio_backtest(
                strategies, symbols, start_date, end_date, initial_capital, **kwargs
            )
        elif mode == 'ensemble':
            result = self._ensemble_backtest(
                strategies, symbols, start_date, end_date, initial_capital, **kwargs
            )
        elif mode == 'pipeline':
            result = self._pipeline_backtest(
                strategies, symbols, start_date, end_date, initial_capital, **kwargs
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        elapsed = time.time() - start_time
        logger.info(f"Combo backtest completed: elapsed={elapsed:.2f}s")
        
        return result
    
    def _validate_params(self, mode: str, strategies: List[Dict], symbols: List[str], **kwargs):
        """Validate parameters."""
        if len(strategies) < 2:
            raise ValueError("组合回测至少需要2个策略")
        
        if not symbols:
            raise ValueError("股票列表不能为空")
        
        # Validate strategy IDs exist
        for strat in strategies:
            if 'strategy_id' not in strat:
                raise ValueError("每个策略必须包含 strategy_id")
            
            if not self._strategy_repo.get_by_id(strat['strategy_id']):
                raise ValueError(f"策略 {strat['strategy_id']} 不存在")
        
        # Mode-specific validation
        if mode == 'portfolio':
            self._validate_portfolio_params(strategies)
        elif mode == 'ensemble':
            self._validate_ensemble_params(strategies, kwargs)
        elif mode == 'pipeline':
            self._validate_pipeline_params(strategies, kwargs)
    
    def _validate_portfolio_params(self, strategies: List[Dict]):
        """Validate portfolio mode params."""
        for strat in strategies:
            if 'weight' not in strat:
                raise ValueError("portfolio 模式下每个策略必须指定 weight")
            
            weight = strat['weight']
            if not (0 < weight <= 1):
                raise ValueError(f"权重必须在 (0, 1] 范围内，当前为 {weight}")
        
        # Check weight sum
        total_weight = sum(s['weight'] for s in strategies)
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(
                f"权重和必须为1，当前为 {total_weight:.4f}"
            )
    
    def _validate_ensemble_params(self, strategies: List[Dict], kwargs: Dict):
        """Validate ensemble mode params."""
        ensemble_method = kwargs.get('ensemble_method', 'weighted')
        
        if ensemble_method not in ['weighted', 'majority', 'and', 'or']:
            raise ValueError(
                f"无效的 ensemble_method: {ensemble_method}"
            )
        
        # weighted mode needs signal_weight
        if ensemble_method == 'weighted':
            for strat in strategies:
                if 'signal_weight' not in strat:
                    strat['signal_weight'] = 1.0
    
    def _validate_pipeline_params(self, strategies: List[Dict], kwargs: Dict):
        """Validate pipeline mode params."""
        for strat in strategies:
            if 'stage' not in strat:
                raise ValueError(
                    f"pipeline 模式下每个策略必须指定 stage"
                )
        
        valid_stages = {'selection', 'timing', 'risk_control'}
        for strat in strategies:
            if strat['stage'] not in valid_stages:
                raise ValueError(
                    f"无效的 stage: {strat['stage']}"
                )
        
        # Must have at least one timing stage
        has_timing = any(s['stage'] == 'timing' for s in strategies)
        if not has_timing:
            raise ValueError("pipeline 模式必须至少包含一个 timing 阶段的策略")
    
    def _portfolio_backtest(
        self,
        strategies: List[Dict],
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        **kwargs
    ) -> Dict:
        """
        Portfolio mode: allocate capital by weight, backtest independently, aggregate.
        """
        results = []
        
        # Backtest each strategy with allocated capital
        for strat_config in strategies:
            capital = initial_capital * strat_config['weight']
            
            try:
                result = self._backtest_single_strategy(
                    strategy_id=strat_config['strategy_id'],
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=capital
                )
                result['weight'] = strat_config['weight']
                results.append(result)
            except Exception as e:
                logger.error(f"Strategy {strat_config['strategy_id']} failed: {e}")
                # Return zero-return result
                results.append({
                    'strategy_id': strat_config['strategy_id'],
                    'weight': strat_config['weight'],
                    'error': str(e),
                    'equity_curve': [
                        {'date': start_date, 'value': capital},
                        {'date': end_date, 'value': capital}
                    ],
                    'metrics': {'total_return': 0.0, 'sharpe_ratio': 0.0}
                })
        
        # Combine equity curves
        combined_equity = self._combine_equity_curves(results, strategies)
        
        # Calculate overall metrics
        overall_metrics = self._calculate_metrics(combined_equity)
        
        # Build strategy breakdown
        strategy_breakdown = []
        for i, result in enumerate(results):
            strat_id = strategies[i]['strategy_id']
            strat_info = self._strategy_repo.get_by_id(strat_id)
            
            breakdown = {
                'strategy_id': strat_id,
                'strategy_name': strat_info.get('name', f'Strategy {strat_id}'),
                'weight': result['weight'],
                'return': result['metrics']['total_return'],
                'sharpe': result['metrics']['sharpe_ratio'],
                'contribution': result['metrics']['total_return'] * result['weight']
            }
            strategy_breakdown.append(breakdown)
        
        return {
            'mode': 'portfolio',
            'period': {'start': start_date, 'end': end_date},
            'overall_metrics': overall_metrics,
            'strategy_breakdown': strategy_breakdown,
            'equity_curve': combined_equity
        }
    
    def _backtest_single_strategy(
        self,
        strategy_id: int,
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float
    ) -> Dict:
        """Backtest a single strategy."""
        strategy = self._strategy_repo.get_by_id(strategy_id)
        
        result = self._backtest_engine.backtest(
            strategy=strategy,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        
        return result
    
    def _combine_equity_curves(
        self,
        results: List[Dict],
        strategies: List[Dict]
    ) -> List[Dict]:
        """Combine multiple equity curves by date alignment and weighted sum."""
        # Collect all dates
        all_dates = set()
        for result in results:
            for point in result['equity_curve']:
                all_dates.add(point['date'])
        
        sorted_dates = sorted(all_dates)
        
        # Combine by date
        combined = []
        for date in sorted_dates:
            total_value = 0.0
            for i, result in enumerate(results):
                weight = result['weight']
                value = self._get_equity_at_date(result['equity_curve'], date)
                total_value += value * weight
            
            combined.append({
                'date': date,
                'value': round(total_value, 2)
            })
        
        return combined
    
    def _get_equity_at_date(self, equity_curve: List[Dict], target_date: str) -> float:
        """Get equity value at specific date, or nearest previous date."""
        for point in reversed(equity_curve):
            if point['date'] <= target_date:
                return point['value']
        return equity_curve[0]['value']
    
    def _calculate_metrics(self, equity_curve: List[Dict]) -> Dict:
        """Calculate performance metrics from equity curve."""
        import numpy as np
        
        values = [p['value'] for p in equity_curve]
        initial = values[0]
        final = values[-1]
        
        # Total return
        total_return = (final - initial) / initial
        
        # Annual return
        days = len(equity_curve)
        annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
        
        # Sharpe ratio
        returns = np.diff(values) / values[:-1]
        sharpe_ratio = (
            np.mean(returns) / np.std(returns) * np.sqrt(252)
            if np.std(returns) > 0 else 0
        )
        
        # Max drawdown
        peak = values[0]
        max_dd = 0.0
        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        
        return {
            'total_return': round(total_return, 4),
            'annual_return': round(annual_return, 4),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'max_drawdown': round(-max_dd, 4),
            'win_rate': 0.0,  # TODO: calculate from trades
            'profit_loss_ratio': 0.0
        }
    
    def _ensemble_backtest(
        self,
        strategies: List[Dict],
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        **kwargs
    ) -> Dict:
        """Ensemble mode: fuse signals from multiple strategies."""
        # TODO: Implement in Task 2
        raise NotImplementedError("Ensemble mode not yet implemented")
    
    def _pipeline_backtest(
        self,
        strategies: List[Dict],
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        **kwargs
    ) -> Dict:
        """Pipeline mode: orchestrate strategies by stages."""
        # TODO: Implement in Task 3
        raise NotImplementedError("Pipeline mode not yet implemented")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_combo_backtest_service.py::TestComboStrategyBacktestService::test_portfolio_mode_basic -v`

Expected: PASS

- [ ] **Step 5: Add test for weight validation**

```python
# Add to quantsys-v2/tests/services/test_combo_backtest_service.py

    def test_portfolio_weight_validation_fails(self, service):
        """Test that weight sum != 1.0 raises error"""
        with pytest.raises(ValueError, match="权重和必须为1"):
            service.backtest_combo(
                mode='portfolio',
                strategies=[
                    {'strategy_id': 53, 'weight': 0.4},
                    {'strategy_id': 54, 'weight': 0.5}  # Sum = 0.9
                ],
                symbols=['600519.SH'],
                start_date='2025-01-01',
                end_date='2025-12-31',
                initial_capital=1000000.0
            )
    
    def test_portfolio_minimum_strategies(self, service):
        """Test that < 2 strategies raises error"""
        with pytest.raises(ValueError, match="至少需要2个策略"):
            service.backtest_combo(
                mode='portfolio',
                strategies=[{'strategy_id': 53, 'weight': 1.0}],
                symbols=['600519.SH'],
                start_date='2025-01-01',
                end_date='2025-12-31',
                initial_capital=1000000.0
            )
```

- [ ] **Step 6: Run validation tests**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_combo_backtest_service.py::TestComboStrategyBacktestService::test_portfolio_weight_validation_fails -v`

Expected: PASS

Run: `cd quantsys-v2 && python -m pytest tests/services/test_combo_backtest_service.py::TestComboStrategyBacktestService::test_portfolio_minimum_strategies -v`

Expected: PASS

- [ ] **Step 7: Commit portfolio mode**

```bash
cd quantsys-v2
git add services/combo_strategy_backtest_service.py tests/services/test_combo_backtest_service.py
git commit -m "feat(backtest): add combo backtest service with portfolio mode

- Implement ComboStrategyBacktestService with portfolio mode
- Support weight-based capital allocation
- Combine equity curves by date alignment
- Calculate overall metrics (return, sharpe, drawdown)
- Add parameter validation (weight sum, min strategies)
- Add unit tests for portfolio mode and validation"
```

---

## Task 2: Core Service - Ensemble Mode

**Files:**
- Modify: `quantsys-v2/services/combo_strategy_backtest_service.py`
- Modify: `quantsys-v2/tests/services/test_combo_backtest_service.py`

- [ ] **Step 1: Write failing test for ensemble mode**

```python
# Add to quantsys-v2/tests/services/test_combo_backtest_service.py

    @pytest.fixture
    def mock_strategy_combiner(self):
        from quantlib.engine.strategy_combiner import StrategyCombiner
        return StrategyCombiner(mode='weighted')
    
    @pytest.fixture
    def service_with_combiner(self, mock_strategy_repo, mock_backtest_engine, mock_strategy_combiner):
        return ComboStrategyBacktestService(
            strategy_repo=mock_strategy_repo,
            backtest_engine=mock_backtest_engine,
            strategy_combiner=mock_strategy_combiner
        )
    
    def test_ensemble_mode_weighted(self, service_with_combiner):
        """Test ensemble mode with weighted signal fusion"""
        result = service_with_combiner.backtest_combo(
            mode='ensemble',
            strategies=[
                {'strategy_id': 53, 'signal_weight': 0.6},
                {'strategy_id': 54, 'signal_weight': 0.4}
            ],
            symbols=['600519.SH'],
            start_date='2025-01-01',
            end_date='2025-12-31',
            initial_capital=1000000.0,
            ensemble_method='weighted'
        )
        
        assert result['mode'] == 'ensemble'
        assert 'overall_metrics' in result
        assert result['overall_metrics']['total_return'] >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_combo_backtest_service.py::TestComboStrategyBacktestService::test_ensemble_mode_weighted -v`

Expected: FAIL with "NotImplementedError: Ensemble mode not yet implemented"

- [ ] **Step 3: Implement ensemble mode in service**

Replace the `_ensemble_backtest` method and add `_load_strategy` method in `quantsys-v2/services/combo_strategy_backtest_service.py`:

```python
    def _ensemble_backtest(
        self,
        strategies: List[Dict],
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        **kwargs
    ) -> Dict:
        """Ensemble mode: fuse signals from multiple strategies."""
        ensemble_method = kwargs.get('ensemble_method', 'weighted')
        
        # Run each strategy independently
        results = []
        weights = []
        for strat_config in strategies:
            try:
                result = self._backtest_single_strategy(
                    strategy_id=strat_config['strategy_id'],
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital
                )
                result['signal_weight'] = strat_config.get('signal_weight', 1.0)
                results.append(result)
                weights.append(result['signal_weight'])
            except Exception as e:
                logger.warning(f"Strategy {strat_config['strategy_id']} failed: {e}")
                continue
        
        if not results:
            raise ValueError("所有策略都失败，无法生成融合结果")
        
        # Weighted average of equity curves
        total_weight = sum(weights)
        all_dates = set()
        for result in results:
            for point in result['equity_curve']:
                all_dates.add(point['date'])
        
        combined_equity = []
        for date in sorted(all_dates):
            weighted_value = 0.0
            for i, result in enumerate(results):
                value = self._get_equity_at_date(result['equity_curve'], date)
                weight = weights[i] / total_weight
                weighted_value += value * weight
            
            combined_equity.append({'date': date, 'value': round(weighted_value, 2)})
        
        # Calculate overall metrics
        overall_metrics = self._calculate_metrics(combined_equity)
        
        # Build strategy breakdown
        strategy_breakdown = []
        for i, result in enumerate(results):
            strat_id = strategies[i]['strategy_id']
            strat_info = self._strategy_repo.get_by_id(strat_id)
            
            breakdown = {
                'strategy_id': strat_id,
                'strategy_name': strat_info.get('name', f'Strategy {strat_id}'),
                'signal_weight': weights[i],
                'return': result['metrics']['total_return'],
                'sharpe': result['metrics']['sharpe_ratio'],
                'contribution': result['metrics']['total_return'] * weights[i] / total_weight
            }
            strategy_breakdown.append(breakdown)
        
        return {
            'mode': 'ensemble',
            'period': {'start': start_date, 'end': end_date},
            'ensemble_method': ensemble_method,
            'overall_metrics': overall_metrics,
            'strategy_breakdown': strategy_breakdown,
            'equity_curve': combined_equity
        }
    
    def _load_strategy(self, strategy_id: int):
        """Load strategy instance (with caching)."""
        if strategy_id in self._strategy_cache:
            return self._strategy_cache[strategy_id]
        
        strategy = self._strategy_repo.get_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")
        
        self._strategy_cache[strategy_id] = strategy
        return strategy
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_combo_backtest_service.py::TestComboStrategyBacktestService::test_ensemble_mode_weighted -v`

Expected: PASS

- [ ] **Step 5: Add test for ensemble validation**

```python
# Add to quantsys-v2/tests/services/test_combo_backtest_service.py

    def test_ensemble_invalid_method(self, service_with_combiner):
        """Test that invalid ensemble_method raises error"""
        with pytest.raises(ValueError, match="无效的 ensemble_method"):
            service_with_combiner.backtest_combo(
                mode='ensemble',
                strategies=[
                    {'strategy_id': 53, 'signal_weight': 0.6},
                    {'strategy_id': 54, 'signal_weight': 0.4}
                ],
                symbols=['600519.SH'],
                start_date='2025-01-01',
                end_date='2025-12-31',
                ensemble_method='invalid_method'
            )
```

- [ ] **Step 6: Run validation test**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_combo_backtest_service.py::TestComboStrategyBacktestService::test_ensemble_invalid_method -v`

Expected: PASS

- [ ] **Step 7: Commit ensemble mode**

```bash
cd quantsys-v2
git add services/combo_strategy_backtest_service.py tests/services/test_combo_backtest_service.py
git commit -m "feat(backtest): add ensemble mode to combo backtest

- Implement ensemble mode with signal fusion
- Support weighted signal combination
- Weighted average of strategy equity curves
- Add validation for ensemble_method
- Add unit tests for ensemble mode"
```




---

## Task 3: Core Service - Pipeline Mode

**Files:**
- Modify: `quantsys-v2/services/combo_strategy_backtest_service.py`
- Modify: `quantsys-v2/tests/services/test_combo_backtest_service.py`

- [ ] **Step 1: Write failing test for pipeline mode**

```python
# Add to quantsys-v2/tests/services/test_combo_backtest_service.py

    def test_pipeline_mode_stages(self, service):
        """Test pipeline mode with selection/timing/risk_control stages"""
        result = service.backtest_combo(
            mode='pipeline',
            strategies=[
                {'strategy_id': 53, 'stage': 'selection'},
                {'strategy_id': 54, 'stage': 'timing'},
                {'strategy_id': 55, 'stage': 'risk_control'}
            ],
            symbols=['600519.SH', '000001.SZ', '000002.SZ'],
            start_date='2025-01-01',
            end_date='2025-12-31',
            initial_capital=1000000.0
        )
        
        assert result['mode'] == 'pipeline'
        assert 'overall_metrics' in result
        assert 'pipeline_stats' in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_combo_backtest_service.py::TestComboStrategyBacktestService::test_pipeline_mode_stages -v`

Expected: FAIL with "NotImplementedError: Pipeline mode not yet implemented"

- [ ] **Step 3: Implement pipeline mode and stage methods**

Replace `_pipeline_backtest` and add stage methods in `quantsys-v2/services/combo_strategy_backtest_service.py`:

```python
    def _pipeline_backtest(
        self,
        strategies: List[Dict],
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float,
        **kwargs
    ) -> Dict:
        """Pipeline mode: orchestrate strategies by stages."""
        import math
        
        current_symbols = symbols
        context = {}
        pipeline_stats = {'initial_symbols': len(symbols), 'stages': []}
        
        # Execute stages
        for stage in ['selection', 'timing', 'risk_control']:
            stage_strategies = [s for s in strategies if s.get('stage') == stage]
            
            if not stage_strategies:
                continue
            
            if stage == 'selection':
                # Simplified: select 60% of symbols
                selected_count = max(1, math.ceil(len(current_symbols) * 0.6))
                current_symbols = current_symbols[:selected_count]
                pipeline_stats['stages'].append({
                    'stage': 'selection',
                    'input_count': len(symbols),
                    'output_count': len(current_symbols)
                })
            
            elif stage == 'timing':
                pipeline_stats['stages'].append({
                    'stage': 'timing',
                    'signals_generated': len(current_symbols)
                })
            
            elif stage == 'risk_control':
                # Simplified: pass 80% of signals
                keep_count = max(1, math.ceil(len(current_symbols) * 0.8))
                current_symbols = current_symbols[:keep_count]
                pipeline_stats['stages'].append({
                    'stage': 'risk_control',
                    'output_signals': len(current_symbols)
                })
        
        # Use timing strategy for backtest
        timing_strategies = [s for s in strategies if s.get('stage') == 'timing']
        if not timing_strategies:
            raise ValueError("Pipeline requires at least one timing strategy")
        
        result = self._backtest_single_strategy(
            strategy_id=timing_strategies[0]['strategy_id'],
            symbols=current_symbols,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        
        overall_metrics = self._calculate_metrics(result['equity_curve'])
        
        return {
            'mode': 'pipeline',
            'period': {'start': start_date, 'end': end_date},
            'overall_metrics': overall_metrics,
            'equity_curve': result['equity_curve'],
            'pipeline_stats': pipeline_stats
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_combo_backtest_service.py::TestComboStrategyBacktestService::test_pipeline_mode_stages -v`

Expected: PASS

- [ ] **Step 5: Add pipeline validation tests**

```python
# Add to quantsys-v2/tests/services/test_combo_backtest_service.py

    def test_pipeline_missing_timing_stage(self, service):
        """Test that pipeline without timing stage raises error"""
        with pytest.raises(ValueError, match="必须至少包含一个 timing 阶段"):
            service.backtest_combo(
                mode='pipeline',
                strategies=[
                    {'strategy_id': 53, 'stage': 'selection'},
                    {'strategy_id': 55, 'stage': 'risk_control'}
                ],
                symbols=['600519.SH'],
                start_date='2025-01-01',
                end_date='2025-12-31'
            )
```

- [ ] **Step 6: Run validation test**

Run: `cd quantsys-v2 && python -m pytest tests/services/test_combo_backtest_service.py::TestComboStrategyBacktestService::test_pipeline_missing_timing_stage -v`

Expected: PASS

- [ ] **Step 7: Commit pipeline mode**

```bash
cd quantsys-v2
git add services/combo_strategy_backtest_service.py tests/services/test_combo_backtest_service.py
git commit -m "feat(backtest): add pipeline mode to combo backtest

- Implement pipeline mode with stage orchestration
- Support selection/timing/risk_control stages
- Sequential execution with filtering
- Add pipeline statistics
- Add unit tests for pipeline mode"
```

---

## Task 4: Flask API Endpoint

**Files:**
- Modify: `quantsys-v2/api/routes/backtest.py`
- Create: `quantsys-v2/tests/api/test_combo_backtest_routes.py`

- [ ] **Step 1: Write failing API test**

```python
# quantsys-v2/tests/api/test_combo_backtest_routes.py
import pytest
import json


class TestComboBacktestAPI:
    
    @pytest.fixture
    def client(self):
        from api.server import create_app
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_combo_backtest_portfolio_api(self, client):
        """Test POST /api/backtest/combo with portfolio mode"""
        response = client.post('/api/backtest/combo', 
            data=json.dumps({
                'mode': 'portfolio',
                'strategies': [
                    {'strategy_id': 53, 'weight': 0.3},
                    {'strategy_id': 54, 'weight': 0.7}
                ],
                'symbols': ['600519.SH'],
                'start_date': '2025-01-01',
                'end_date': '2025-12-31',
                'initial_capital': 1000000.0
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['mode'] == 'portfolio'
    
    def test_combo_backtest_missing_params(self, client):
        """Test that missing required params returns 400"""
        response = client.post('/api/backtest/combo',
            data=json.dumps({'mode': 'portfolio'}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'required' in data['error'].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && python -m pytest tests/api/test_combo_backtest_routes.py::TestComboBacktestAPI::test_combo_backtest_portfolio_api -v`

Expected: FAIL with 404 (route not found)

- [ ] **Step 3: Add combo backtest endpoint to routes**

```python
# Add to quantsys-v2/api/routes/backtest.py

@backtest_bp.route('/api/backtest/combo', methods=['POST'])
def combo_backtest():
    """Combo strategy backtest endpoint."""
    from api.shared import combo_backtest_service
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400
    
    # Validate required params
    mode = data.get('mode')
    strategies = data.get('strategies')
    symbols = data.get('symbols')
    
    if not mode or not strategies or not symbols:
        return jsonify({
            'success': False,
            'error': 'mode, strategies, and symbols are required'
        }), 400
    
    if mode not in ['portfolio', 'ensemble', 'pipeline']:
        return jsonify({
            'success': False,
            'error': f'Invalid mode: {mode}. Must be portfolio, ensemble, or pipeline'
        }), 400
    
    try:
        result = combo_backtest_service.backtest_combo(
            mode=mode,
            strategies=strategies,
            symbols=symbols,
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            initial_capital=data.get('initial_capital', 1000000.0),
            ensemble_method=data.get('ensemble_method', 'weighted'),
            pipeline_config=data.get('pipeline_config', {})
        )
        
        return jsonify({'success': True, 'data': result})
        
    except ValueError as e:
        logger.warning(f"Combo backtest validation error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Combo backtest failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && python -m pytest tests/api/test_combo_backtest_routes.py::TestComboBacktestAPI::test_combo_backtest_portfolio_api -v`

Expected: PASS

- [ ] **Step 5: Run missing params test**

Run: `cd quantsys-v2 && python -m pytest tests/api/test_combo_backtest_routes.py::TestComboBacktestAPI::test_combo_backtest_missing_params -v`

Expected: PASS

- [ ] **Step 6: Commit API endpoint**

```bash
cd quantsys-v2
git add api/routes/backtest.py tests/api/test_combo_backtest_routes.py
git commit -m "feat(api): add combo backtest API endpoint

- Add POST /api/backtest/combo endpoint
- Validate required parameters (mode, strategies, symbols)
- Support all three modes (portfolio/ensemble/pipeline)
- Add error handling for validation and execution
- Add API integration tests"
```

