"""EvolutionFitness ORM Repository 测试——evolution_fitness 表 upsert/排行"""
from datetime import date

import pytest

from adapters.outbound.repositories.evolution_fitness_repository import (
    EvolutionFitnessORMRepository,
)

_TEST_ACCOUNTS = ('test_evo_acct_a', 'test_evo_acct_b', 'test_evo_idle')
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
