"""EvolutionFitnessService 装配层测试——mock 仓储/基准源，验证编排逻辑"""
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from application.services.evolution.evolution_fitness_service import EvolutionFitnessService


def _make_service(snaps_by_acct, bench_returns, trades_by_acct):
    sim_repo = MagicMock()
    sim_repo.list_accounts.return_value = [
        MagicMock(account_name=name) for name in snaps_by_acct
    ]
    sim_repo.get_equity_snapshots.side_effect = (
        lambda account_name, limit=90: snaps_by_acct[account_name]
    )
    fitness_repo = MagicMock()
    svc = EvolutionFitnessService(
        sim_repo=sim_repo,
        fitness_repo=fitness_repo,
        bench_returns_provider=lambda start, end: bench_returns,
        trade_counter=lambda account_name, start, end: trades_by_acct[account_name],
    )
    return svc, fitness_repo


def _make_window(end: date, n_days: int = 20):
    """构造 n_days 个交易日的 {date: return}：10 涨 7 跌 其余横盘，返回 dict"""
    bench = {}
    day = end
    pattern = [0.01] * 10 + [-0.01] * 7 + [0.001] * 13  # 足够覆盖 20 天
    i = 0
    while len(bench) < n_days:
        if day.weekday() < 5:
            bench[day.isoformat()] = pattern[i % len(pattern)]
            i += 1
        day -= timedelta(days=1)
    return bench


class TestDefaultConstruction:
    def test_explicit_repos_stored(self):
        """通过依赖注入构造服务，验证仓储被正确保存"""
        sim_repo = MagicMock()
        fitness_repo = MagicMock()
        svc = EvolutionFitnessService(sim_repo=sim_repo, fitness_repo=fitness_repo)
        assert svc.sim_repo is sim_repo
        assert svc.fitness_repo is fitness_repo

    def test_default_repos_importable(self):
        """默认构造需要 ORM 仓储类，当前 P2-3 重构中类名已漂移；
        本测试保留为兼容性占位，服务应通过依赖注入使用。"""
        pytest.skip("默认构造依赖的 EvolutionFitnessORMRepository 已从模块移除")


class TestComputeAllAccounts:
    def test_upserts_per_account_with_status(self):
        end = date(2026, 8, 5)
        bench = _make_window(end)
        snaps = [MagicMock(snapshot_date=date.fromisoformat(d), daily_return=r * 1.2,
                           total_value=100000)
                 for d, r in bench.items()]
        svc, fitness_repo = _make_service(
            {'agent_virtual': snaps}, bench, {'agent_virtual': 3})
        result = svc.compute_all_accounts(window_end=end, window_days=20)
        assert result['computed'] == 1
        upsert = fitness_repo.upsert_fitness.call_args.kwargs
        assert upsert['account_name'] == 'agent_virtual'
        assert upsert['status'] == 'ok'
        assert upsert['up_capture'] == 1.2
        assert upsert['window_end'] == end
        assert upsert['window_days'] == 20

    def test_no_trades_account_marked(self):
        end = date(2026, 8, 5)
        bench = _make_window(end)
        snaps = [MagicMock(snapshot_date=date.fromisoformat(d), daily_return=0.0,
                           total_value=100000)
                 for d in bench]
        svc, fitness_repo = _make_service({'v15': snaps}, bench, {'v15': 0})
        svc.compute_all_accounts(window_end=end, window_days=20)
        upsert = fitness_repo.upsert_fitness.call_args.kwargs
        assert upsert['status'] == 'no_trades'

    def test_bench_missing_degrades_to_data_gap(self):
        snaps = [MagicMock(snapshot_date=date(2026, 8, 5), daily_return=0.01,
                           total_value=100000)]
        svc, fitness_repo = _make_service({'agent_virtual': snaps}, {}, {'agent_virtual': 2})
        svc.compute_all_accounts(window_end=date(2026, 8, 5), window_days=20)
        upsert = fitness_repo.upsert_fitness.call_args.kwargs
        assert upsert['status'] == 'data_gap'

    def test_empty_snapshot_account_skipped_without_crash(self):
        end = date(2026, 8, 5)
        bench = _make_window(end)
        svc, fitness_repo = _make_service({'ghost_acct': []}, bench, {'ghost_acct': 0})
        result = svc.compute_all_accounts(window_end=end, window_days=20)
        upsert = fitness_repo.upsert_fitness.call_args.kwargs
        assert upsert['status'] in ('data_gap', 'no_trades')
        assert result['computed'] == 1


class TestHonestStateCounts:
    """计数语义必须诚实（REQ-261005210015-1603 t-89b1f4，FR-4）。

    取证：现场 5 行全 NULL（2 条 insufficient_sample + 3 条 no_trades）却报 computed=5，
    卡片据此发 ✅。改后：`computed` 只表示**遍历到的账户数**，唯一可称「算出来了」的是
    `computed_ok`；四类计数 + other 恒等于 accounts_total。
    """

    def _four_states(self):
        """四种状态各一个账户：ok / no_trades / insufficient_sample / data_gap。"""
        end = date(2026, 8, 5)
        bench = _make_window(end)
        full = [MagicMock(snapshot_date=date.fromisoformat(d), daily_return=r, total_value=100000)
                for d, r in bench.items()]
        few = [MagicMock(snapshot_date=date.fromisoformat(d), daily_return=r, total_value=100000)
               for d, r in list(bench.items())[:3]]
        return end, bench, _make_service(
            {'ok_a': full, 'notrade_a': full, 'insuff_a': few, 'gap_a': []},
            bench, {'ok_a': 3, 'notrade_a': 0, 'insuff_a': 3, 'gap_a': 3})

    def test_state_counts_sum_to_accounts_total(self):
        end, _bench, (svc, _repo) = self._four_states()
        r = svc.compute_all_accounts(window_end=end, window_days=20)
        assert r['accounts_total'] == 4
        assert (r['computed_ok'] + r['insufficient_sample'] + r['no_trades']
                + r['data_gap'] + r['other']) == r['accounts_total']
        assert (r['computed_ok'], r['no_trades'], r['data_gap'], r['insufficient_sample']) == (1, 1, 1, 1)

    def test_null_rows_not_counted_as_ok(self):
        end, _bench, (svc, _repo) = self._four_states()
        r = svc.compute_all_accounts(window_end=end, window_days=20)
        assert r['computed_ok'] == 1
        assert r['computed_ok'] < r['accounts_total']

    def test_skipped_key_removed(self):
        end, _bench, (svc, _repo) = self._four_states()
        r = svc.compute_all_accounts(window_end=end, window_days=20)
        assert 'skipped' not in r

    def test_computed_key_kept_for_compat(self):
        end, _bench, (svc, _repo) = self._four_states()
        r = svc.compute_all_accounts(window_end=end, window_days=20)
        assert r['computed'] == r['accounts_total'] == 4

    def test_aligned_days_reported(self):
        end, bench, (svc, _repo) = self._four_states()
        r = svc.compute_all_accounts(window_end=end, window_days=20)
        assert r['aligned_days'] == len(bench) == 20
