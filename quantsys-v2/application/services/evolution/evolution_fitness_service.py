"""双侧捕获适应度装配服务：快照 + 基准 → 纯函数 → 落库（每日调度调用）"""
from datetime import date, timedelta
from typing import Any, Callable, Dict, Mapping, Optional

import structlog

from application.services.benchmark_comparison import (
    _benchmark_daily_returns, fetch_benchmark_klines,
)
from application.services.evolution.fitness_calculator import compute_capture

logger = structlog.get_logger(__name__)

BENCHMARK_SYMBOL = 'sh000300'
LOOKBACK_BUFFER_DAYS = 45  # 20 交易日窗口的自然日上界（含周末/长假缓冲）


class EvolutionFitnessService:
    """每日收盘后计算全活跃模拟账户的滚动窗口双侧捕获适应度并落库。"""

    def __init__(
        self,
        sim_repo=None,
        fitness_repo=None,
        bench_returns_provider: Optional[Callable[[date, date], Mapping[str, float]]] = None,
        trade_counter: Optional[Callable[[str, date, date], int]] = None,
    ):
        if sim_repo is None:
            from domain.ports import ISimulationRepository
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            sim_repo = EnhancedServiceFactory.resolve(ISimulationRepository)
        if fitness_repo is None:
            from domain.ports.repository_ports_extended import (
                EvolutionFitnessORMRepository,
            )
            fitness_repo = EvolutionFitnessORMRepository()
        self.sim_repo = sim_repo
        self.fitness_repo = fitness_repo
        self._bench_provider = bench_returns_provider or self._default_bench_provider
        self._trade_counter = trade_counter or self._default_trade_counter

    @staticmethod
    def _default_bench_provider(start: date, end: date) -> Mapping[str, float]:
        klines = fetch_benchmark_klines(
            symbol=BENCHMARK_SYMBOL, start_date=start.isoformat(), end_date=end.isoformat())
        return _benchmark_daily_returns(klines)

    def _default_trade_counter(self, account_name: str, start: date, end: date) -> int:
        from infrastructure.persistence.orm.models.simulation import SimulationTrade
        return (
            self.sim_repo.session.query(SimulationTrade)
            .filter(SimulationTrade.account_name == account_name,
                    SimulationTrade.trade_date >= start,
                    SimulationTrade.trade_date <= end)
            .count()
        )

    def compute_all_accounts(self, window_end: Optional[date] = None,
                             window_days: int = 20) -> Dict[str, Any]:
        """对全部 active 模拟账户计算 window_end 截止的滚动窗口适应度并 upsert。

        幂等：重复运行按 (account_name, window_end, window_days) 覆盖。
        """
        window_end = window_end or date.today()
        start = window_end - timedelta(days=LOOKBACK_BUFFER_DAYS)
        bench_all = dict(self._bench_provider(start, window_end))
        computed = 0
        for account in self.sim_repo.list_accounts(status='active'):
            account_name = account.account_name
            snaps = self.sim_repo.get_equity_snapshots(
                account_name, limit=LOOKBACK_BUFFER_DAYS)
            acct_returns = {
                s.snapshot_date.isoformat(): float(s.daily_return or 0)
                for s in snaps
                if s.snapshot_date is not None and start <= s.snapshot_date <= window_end
            }
            # 窗口内对齐日 = 账户 ∩ 基准；基准按交易日给，取最近 window_days 个
            aligned_dates = sorted(d for d in bench_all if d in acct_returns)[-window_days:]
            if not aligned_dates:
                result = {'up_capture': None, 'down_capture': None, 'fitness': None,
                          'up_days': 0, 'down_days': 0, 'status': 'data_gap'}
            else:
                bench_window = {d: bench_all[d] for d in aligned_dates}
                acct_window = {d: acct_returns[d] for d in aligned_dates}
                win_start = date.fromisoformat(min(aligned_dates))
                trades = self._trade_counter(account_name, win_start, window_end)
                result = compute_capture(acct_window, bench_window, has_trades=trades > 0)
            self.fitness_repo.upsert_fitness(
                account_name=account_name, window_end=window_end,
                window_days=window_days, **result)
            computed += 1
        logger.info('evolution_fitness computed', window_end=str(window_end),
                    computed=computed)
        return {'computed': computed, 'skipped': 0, 'window_end': str(window_end)}
