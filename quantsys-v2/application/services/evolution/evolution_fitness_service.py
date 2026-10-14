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
            from infrastructure.services.service_factory import ServiceFactory
            sim_repo = ServiceFactory.resolve(ISimulationRepository)
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

        返回体口径（REQ-261005210015-1603 t-c0941a，FR-4）：
        `computed` 是**遍历到的账户数**（兼容键，别读成"算出了几条"）；
        `computed_ok` 才是 status == 'ok' 的有效条数；
        四类状态计数 + `other` 之和恒等于 `accounts_total`。
        """
        from infrastructure.monitoring.business_metrics import (
            evolution_fitness_computed_total,
            evolution_fitness_score,
        )
        
        window_end = window_end or date.today()
        start = window_end - timedelta(days=LOOKBACK_BUFFER_DAYS)
        bench_all = dict(self._bench_provider(start, window_end))
        # REQ-261005210015-1603 t-c0941a（FR-4）：计数必须诚实。
        # 取证：`computed` 原是"遍历到的账户数"，NULL 行也 +1 —— 现场 5 行全 NULL
        # （2 条 insufficient_sample + 3 条 no_trades）却报 computed=5，并据此发出 ✅。
        # 现在按 status 分类计数，唯一可称"算出来了"的数是 computed_ok。
        states: Dict[str, int] = {}
        accounts_total = 0
        aligned_days = 0
        for account in self.sim_repo.list_accounts(status='active'):
            account_name = account.account_name
            snaps = self.sim_repo.get_equity_snapshots(
                account_name, limit=LOOKBACK_BUFFER_DAYS)
            acct_returns = {
                s.snapshot_date.isoformat(): float(s.daily_return or 0)
                for s in snaps
                if s.snapshot_date is not None and start <= s.snapshot_date <= window_end
            }
            aligned_dates = sorted(d for d in bench_all if d in acct_returns)[-window_days:]
            aligned_days = max(aligned_days, len(aligned_dates))
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
            
            if result.get('up_capture') is not None:
                evolution_fitness_score.labels(account=account_name, type='up_capture').set(result['up_capture'])
            if result.get('down_capture') is not None:
                evolution_fitness_score.labels(account=account_name, type='down_capture').set(result['down_capture'])

            status = str(result.get('status') or 'other')
            states[status] = states.get(status, 0) + 1
            accounts_total += 1

        known = ('ok', 'insufficient_sample', 'no_trades', 'data_gap')
        computed_ok = states.get('ok', 0)
        # 指标口径与 computed_ok 一致（不再把"遍历到几条"当产出数计进计数器）
        evolution_fitness_computed_total.labels(account='all').inc(computed_ok)
        logger.info('evolution_fitness computed', window_end=str(window_end),
                    accounts_total=accounts_total, computed_ok=computed_ok, states=states)
        return {
            'window_end': str(window_end),
            'accounts_total': accounts_total,
            # 兼容键：**遍历到的账户数**，不是有效条数。两处旧调用方依赖它：
            #   tests/e2e/test_evolution_pipeline.py 的 result['computed'] >= 1
            #   daily_orchestrator 复核阶段的日志行
            'computed': accounts_total,
            # 唯一可称"算出来了"的数（status == 'ok'）
            'computed_ok': computed_ok,
            'insufficient_sample': states.get('insufficient_sample', 0),
            'no_trades': states.get('no_trades', 0),
            'data_gap': states.get('data_gap', 0),
            # 未预期 status 的兜底桶：保证"四类 + other == accounts_total"这条不变式不被悄悄破坏
            'other': sum(v for k, v in states.items() if k not in known),
            'aligned_days': aligned_days,
        }
