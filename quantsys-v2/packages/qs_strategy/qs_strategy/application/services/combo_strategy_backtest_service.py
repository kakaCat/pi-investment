"""Combo strategy backtest service - multi-strategy combination backtesting."""
import structlog
import time
from typing import Dict, List, Optional

logger = structlog.get_logger(__name__)


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
