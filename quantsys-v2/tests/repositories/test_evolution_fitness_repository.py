"""EvolutionFitness ORM Repository 测试——evolution_fitness 表 upsert/排行"""
from datetime import date

import pytest

from adapters.outbound.repositories.evolution_fitness_repository import (
    EvolutionFitnessORMRepository,
)

_TEST_ACCOUNTS = ('test_evo_acct_a', 'test_evo_acct_b', 'test_evo_idle',
                  # REQ-261005210015-1603 t-89b1f4：只读聚合口径用例用的账户
                  'test_evo_win_a', 'test_evo_win_b', 'test_evo_win_c', 'test_evo_win_d')
_TEST_DATE = date(2026, 8, 5)


@pytest.fixture
def repo():
    r = EvolutionFitnessORMRepository()
    yield r
    r.delete_by_accounts(_TEST_ACCOUNTS)


class TestEvolutionFitnessRepository:
    def test_upsert_and_leaderboard(self, repo):
        repo.upsert_fitness(
            account_name='test_evo_acct_a', window_end=_TEST_DATE,
            up_capture=1.2, down_capture=0.5, fitness=0.7,
            up_days=10, down_days=7, status='ok',
        )
        repo.upsert_fitness(
            account_name='test_evo_acct_b', window_end=_TEST_DATE,
            up_capture=0.8, down_capture=1.5, fitness=-0.7,
            up_days=10, down_days=7, status='ok',
        )
        board = [r for r in repo.get_leaderboard(window_end=_TEST_DATE)
                 if r['account_name'] in _TEST_ACCOUNTS]
        assert [r['account_name'] for r in board] == ['test_evo_acct_a', 'test_evo_acct_b']
        assert board[0]['fitness'] == pytest.approx(0.7)

    def test_upsert_idempotent(self, repo):
        for fitness in (0.7, 0.9):
            repo.upsert_fitness(
                account_name='test_evo_acct_a', window_end=_TEST_DATE,
                up_capture=1.2, down_capture=0.3, fitness=fitness,
                up_days=10, down_days=7, status='ok',
            )
        board = [r for r in repo.get_leaderboard(window_end=_TEST_DATE, include_non_ok=True)
                 if r['account_name'] == 'test_evo_acct_a']
        assert len(board) == 1
        assert board[0]['fitness'] == pytest.approx(0.9)

    def test_leaderboard_skips_non_ok_status(self, repo):
        repo.upsert_fitness(
            account_name='test_evo_idle', window_end=_TEST_DATE,
            up_capture=None, down_capture=None, fitness=None,
            up_days=0, down_days=0, status='no_trades',
        )
        board = [r for r in repo.get_leaderboard(window_end=_TEST_DATE)
                 if r['account_name'] == 'test_evo_idle']
        assert board == []
        all_rows = [r for r in repo.get_leaderboard(window_end=_TEST_DATE, include_non_ok=True)
                    if r['account_name'] == 'test_evo_idle']
        assert all_rows[0]['status'] == 'no_trades'


class TestReadOnlyAggregates:
    """空转读数的只读口径（REQ-261005210015-1603 t-89b1f4，FR-5）。

    这两个方法供宿主消息层算出「连续几次没算出东西」。它们是**只读**的
    （无 add / commit / update），且不依赖新列。

    注：「表内一条 ok 都没有 → None」这条分支依赖空表，共享测试库下无法构造，
    故用「更新的非 ok 行不得顶掉最近 ok 日」锁住同一语义（max 聚合天然跳过非 ok）。
    """

    def test_recent_window_ok_counts_groups_desc(self, repo):
        rows_to_insert = (
            (date(2026, 8, 5), 'test_evo_win_a', 'ok'),
            (date(2026, 8, 5), 'test_evo_win_b', 'ok'),
            (date(2026, 8, 6), 'test_evo_win_c', 'no_trades'),
            (date(2026, 8, 7), 'test_evo_win_d', 'ok'),
        )
        for wd, acct, status in rows_to_insert:
            repo.upsert_fitness(
                account_name=acct, window_end=wd,
                up_capture=None, down_capture=None, fitness=None,
                up_days=0, down_days=0, status=status,
            )
        rows = repo.list_recent_window_ok_counts(limit=200)
        by_date = dict(rows)
        assert by_date[date(2026, 8, 5)] == 2      # 两条 ok
        assert by_date[date(2026, 8, 6)] == 0      # 一条 no_trades
        assert by_date[date(2026, 8, 7)] == 1      # 一条 ok
        dates = [d for d, _ in rows]
        assert dates == sorted(dates, reverse=True)

    def test_last_ok_window_end_ignores_newer_non_ok(self, repo):
        repo.upsert_fitness(account_name='test_evo_win_a', window_end=date(2027, 1, 1),
                            up_capture=1.0, down_capture=0.5, fitness=0.5,
                            up_days=10, down_days=7, status='ok')
        repo.upsert_fitness(account_name='test_evo_win_b', window_end=date(2027, 1, 2),
                            up_capture=None, down_capture=None, fitness=None,
                            up_days=1, down_days=0, status='insufficient_sample')
        assert repo.get_last_ok_window_end() == date(2027, 1, 1)
