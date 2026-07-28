"""weekly_report_job 修复回归测试：run() 用现有 repo 接口跑通"""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from infrastructure.jobs.weekly_report_job import WeeklyReportJob


def _make_job():
    job = WeeklyReportJob.__new__(WeeklyReportJob)
    job.config = {
        'strategy': {'rebalance_days': 7},
        'feishu': {'observation_period': {'cycles': 3}},
    }
    job.feishu_notifier = None

    repo = MagicMock()
    repo.get_account.return_value = SimpleNamespace(
        total_value=86644.52,
        cash_available=49068.52,
        initial_capital=99993.81,
        last_rebalance_date=date(2026, 7, 17),
        created_at=datetime(2026, 6, 22),
    )
    repo.get_trades_by_account.return_value = []
    repo.get_all_positions.return_value = []
    job.repo = repo

    job._calculate_position_returns = MagicMock(return_value=[])
    job._get_index_return = MagicMock(return_value=0.01)
    return job


def test_run_completes_with_existing_repo_methods():
    job = _make_job()
    job.run()  # 不抛 AttributeError 即通过

    # 账户查询使用 v13_simulation 而非 default
    assert job.repo.get_account.call_args_list[0][1]['account_name'] == 'v13_simulation'
    # 交易查询走现有接口
    job.repo.get_trades_by_account.assert_called()
