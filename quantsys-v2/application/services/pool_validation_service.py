"""Pool validation service - batch backtest strategies against a stock pool."""
import structlog
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from infrastructure.events.progress_emitter import ProgressEmitter

logger = structlog.get_logger(__name__)

BACKTEST_API_URL = "http://127.0.0.1:5001/api/backtest/batch"
BACKTEST_TIMEOUT = 300  # 5 minutes


class PoolValidationService:
    """Orchestrates multi-strategy validation against a stock pool.

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(self, pool_repo=None, strategy_repo=None):
        """初始化服务

        Args:
            pool_repo: 股票池仓库（可选）
            strategy_repo: 策略仓库（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        from domain.ports import IStockPoolRepository, IStrategyRepository
        self._pool_repo = pool_repo
        self._strategy_repo = strategy_repo

    def validate_pool(self, pool_id: int, strategy_ids: List[int] = None,
                      start_date: str = None, end_date: str = None,
                      progress_emitter: Optional[ProgressEmitter] = None) -> Dict:
        """
        Run batch backtest: strategies × pool symbols, aggregate, rank, recommend.

        Args:
            pool_id: Target pool ID
            strategy_ids: Specific strategies to test (None = all active)
            start_date: Backtest start (default: 6 months ago)
            end_date: Backtest end (default: today)

        Returns:
            Dict with rankings, best_strategy, recommended_pairs
        """
        # 1. Load pool
        if progress_emitter:
            progress_emitter.update(1, f"正在加载股票池 #{pool_id}")

        pool = self._pool_repo.get_pool(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        symbols = pool.get('symbols', [])
        if not symbols:
            raise ValueError(f"Pool {pool_id} is empty (no symbols)")

        # 2. Resolve strategies
        if progress_emitter:
            progress_emitter.update(1, "正在加载策略列表")

        raw_strategies = self._strategy_repo.get_all()
        if strategy_ids:
            strategies = [
                s for s in raw_strategies
                if s.get('id') in strategy_ids
            ]
        else:
            strategies = [s for s in raw_strategies if s.get('is_active', True)]

        if not strategies:
            raise ValueError("No strategies available for validation")

        # Validate strategy dicts and log warnings for any missing fields
        for s in strategies:
            if not s.get('id'):
                logger.warning(f"Skipping strategy with missing id: {s}")
            if not s.get('name'):
                logger.warning(f"Strategy {s.get('id', 'unknown')} has no name field")

        # 3. Resolve date range
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

        # 4. Build jobs: strategy × symbol cartesian product
        jobs = []
        for strategy in strategies:
            sid = strategy.get('id')
            if not sid:
                logger.warning(f"Skipping strategy with missing id: {strategy}")
                continue
            for symbol in symbols:
                jobs.append({
                    'strategy_id': sid,
                    'symbol': symbol,
                    'start_date': start_date,
                    'end_date': end_date,
                })

        logger.info(f"Pool validation: {len(strategies)} strategies × "
                     f"{len(symbols)} symbols = {len(jobs)} jobs")

        if progress_emitter:
            progress_emitter.update(1, f"开始批量回测：{len(jobs)} 个任务")

        # 5. Call batch backtest API
        backtest_results = self._call_batch_backtest(jobs, progress_emitter)

        # 6. Aggregate by strategy
        if progress_emitter:
            progress_emitter.update(1, "正在汇总策略结果")

        # Build strategy name map, with fallbacks for missing id/name
        strategy_map = {}
        for s in strategies:
            sid = s.get('id')
            if sid is None:
                continue
            name = s.get('name') or s.get('strategy_name') or f"Strategy {sid}"
            strategy_map[sid] = name
        rankings = self._aggregate_by_strategy(backtest_results, strategy_map)

        # 7. Build result
        rankings.sort(key=lambda r: r['score'], reverse=True)
        best = rankings[0] if rankings else None

        # 8. Build recommended_pairs from best strategy's individual results
        recommended_pairs = []
        if best:
            best_results = [
                r for r in backtest_results
                if r.get('strategy_id') == best['strategy_id']
            ]
            best_results.sort(
                key=lambda r: self._calculate_score(r), reverse=True
            )
            for r in best_results[:5]:
                symbol = r.get('symbol', 'unknown')
                if symbol == 'unknown':
                    logger.warning(f"Backtest result missing symbol: {r}")
                recommended_pairs.append({
                    'strategy_id': best['strategy_id'],
                    'strategy_name': best.get('name', best.get('strategy_name', f"Strategy {best['strategy_id']}")),
                    'symbol': symbol,
                    'expected_return': round(r.get('annual_return', 0) * 100, 2),
                    'win_rate': round(r.get('win_rate', 0) * 100, 2),
                    'sharpe': round(r.get('sharpe_ratio', 0), 2),
                })

        validation_result = {
            'pool_id': pool_id,
            'pool_name': pool.get('name', f'Pool {pool_id}'),
            'period': {'start': start_date, 'end': end_date},
            'strategies_tested': len(strategies),
            'stocks_in_pool': len(symbols),
            'best_strategy': best,
            'rankings': rankings,
            'recommended_pairs': recommended_pairs,
            'validated_at': datetime.now().isoformat(),
        }

        # 9. Save to pool
        self._pool_repo.update_validation(pool_id, validation_result)

        return validation_result

    def _call_batch_backtest(self, jobs: List[Dict], progress_emitter: Optional[ProgressEmitter] = None) -> List[Dict]:
        """Call POST /api/backtest/batch and return results list."""
        try:
            if progress_emitter:
                progress_emitter.update(0, f"正在执行 {len(jobs)} 个回测任务...")

            resp = requests.post(
                BACKTEST_API_URL,
                json={'jobs': jobs, 'initial_capital': 100000.0},
                timeout=BACKTEST_TIMEOUT,
            )
            if resp.status_code != 200:
                logger.error(f"Batch backtest failed: HTTP {resp.status_code}")
                return []

            data = resp.json()
            if not data.get('success'):
                logger.error(f"Batch backtest error: {data.get('error')}")
                return []

            results = data.get('data', {}).get('results', [])
            errors = data.get('data', {}).get('errors', [])
            if errors:
                logger.warning(f"Batch backtest had {len(errors)} errors")

            # Convert camelCase to snake_case
            normalized_results = []
            for r in results:
                normalized_results.append({
                    'strategy_id': r.get('strategyId'),
                    'symbol': r.get('symbol'),
                    'annual_return': r.get('annualReturn', 0),
                    'sharpe_ratio': r.get('sharpeRatio', 0),
                    'max_drawdown': r.get('maxDrawdown', 0),
                    'win_rate': r.get('winRate', 0),
                    'profit_factor': r.get('profitFactor', 0),
                })

            return normalized_results
        except requests.RequestException as e:
            logger.error(f"Batch backtest request failed: {e}")
            return []

    def _aggregate_by_strategy(self, results: List[Dict],
                                strategy_map: Dict[int, str]) -> List[Dict]:
        """Group results by strategy_id, compute averages and score."""
        grouped = defaultdict(list)
        for r in results:
            grouped[r.get('strategy_id')].append(r)

        rankings = []
        for strategy_id, items in grouped.items():
            n = len(items)
            avg_return = sum(i.get('annual_return', 0) for i in items) / n
            avg_sharpe = sum(i.get('sharpe_ratio', 0) for i in items) / n
            avg_drawdown = sum(i.get('max_drawdown', 0) for i in items) / n
            avg_win_rate = sum(i.get('win_rate', 0) for i in items) / n
            avg_profit_factor = sum(i.get('profit_factor', 0) for i in items) / n

            score = self._calculate_score({
                'annual_return': avg_return,
                'sharpe_ratio': avg_sharpe,
                'max_drawdown': avg_drawdown,
                'win_rate': avg_win_rate,
                'profit_factor': avg_profit_factor,
            })

            rankings.append({
                'strategy_id': strategy_id,
                'name': strategy_map.get(strategy_id, f'Strategy {strategy_id}'),
                'score': round(score, 2),
                'avg_return': round(avg_return * 100, 2),
                'avg_sharpe': round(avg_sharpe, 2),
                'avg_drawdown': round(avg_drawdown * 100, 2),
                'avg_win_rate': round(avg_win_rate * 100, 2),
                'avg_profit_factor': round(avg_profit_factor, 2),
                'stocks_tested': n,
            })

        return rankings

    def _calculate_score(self, metrics: Dict) -> float:
        """
        Comprehensive score (0-100). Same formula as StrategyValidationService.

        Weights: return 40%, sharpe 20%, drawdown 15%, win_rate 15%, profit_factor 10%
        """
        def normalize(value, low, high, reverse=False):
            clamped = max(low, min(high, value))
            ratio = (clamped - low) / (high - low) if high != low else 0.5
            return (1 - ratio) if reverse else ratio

        annual_return = metrics.get('annual_return', 0)
        sharpe = metrics.get('sharpe_ratio', 0)
        drawdown = metrics.get('max_drawdown', 0)
        win_rate = metrics.get('win_rate', 0)
        profit_factor = metrics.get('profit_factor', 0)

        score = (
            normalize(annual_return, -0.5, 0.5) * 0.40
            + normalize(sharpe, -2, 3) * 0.20
            + normalize(drawdown, -0.5, 0.0, reverse=True) * 0.15
            + normalize(win_rate, 0, 1) * 0.15
            + normalize(profit_factor, 0, 3) * 0.10
        ) * 100

        return max(0, min(100, score))
