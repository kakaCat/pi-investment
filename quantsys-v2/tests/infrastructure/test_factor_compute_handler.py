"""_handle_factor_compute 修复测试（2026-08-04）

根因：get_daily_klines 自 ORM 重构后返回 polars DataFrame，handler 按 list-of-dicts
写（`if not klines` 对 DataFrame 抛 TypeError）→ 5528 只全 error 却报 success（假成功）。
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from infrastructure.scheduler.scheduler import SchedulerService


def _fake_klines_df(days=30):
    base = date(2026, 7, 1)
    return pl.DataFrame({
        'trade_date': [base + timedelta(days=i) for i in range(days)],
        'open': [10.0 + i * 0.1 for i in range(days)],
        'high': [10.2 + i * 0.1 for i in range(days)],
        'low': [9.8 + i * 0.1 for i in range(days)],
        'close': [10.1 + i * 0.1 for i in range(days)],
        'volume': [1000000] * days,
        'amount': [1e7] * days,
    })


class TestFactorComputeHandler:
    @patch('domain.backtest.stages.factor_stage.FactorStage')
    @patch('infrastructure.scheduler.scheduler.FactorORMRepository')
    @patch('infrastructure.scheduler.scheduler.KlineORMRepository')
    def test_polars_dataframe_input_computes_factors(self, mock_kline_repo, mock_factor_repo, mock_stage):
        mock_kline_repo.return_value.get_daily_klines.return_value = _fake_klines_df()
        mock_factor_repo.return_value.save_factors.return_value = None
        mock_stage.return_value.process.return_value = {'factors': {'rsi14': 55.0, 'ma5': 10.5}}

        svc = SchedulerService(repo=MagicMock())
        result = svc._handle_factor_compute({'symbols': ['600000', '000001']})

        assert result['symbols_computed'] == 2
        assert result['errors'] == 0
        assert result['factor_count'] == 4
        assert result['status'] == 'success'
        mock_factor_repo.return_value.save_factors.assert_called()

    @patch('domain.backtest.stages.factor_stage.FactorStage')
    @patch('infrastructure.scheduler.scheduler.FactorORMRepository')
    @patch('infrastructure.scheduler.scheduler.KlineORMRepository')
    def test_list_input_still_works(self, mock_kline_repo, mock_factor_repo, mock_stage):
        klines = [{'trade_date': date(2026, 7, 31), 'close': 10.0, 'open': 9.9,
                   'high': 10.2, 'low': 9.8, 'volume': 1000}] * 25
        mock_kline_repo.return_value.get_daily_klines.return_value = klines
        mock_factor_repo.return_value.save_factors.return_value = None
        mock_stage.return_value.process.return_value = {'factors': {'rsi14': 55.0}}

        svc = SchedulerService(repo=MagicMock())
        result = svc._handle_factor_compute({'symbols': ['600000']})

        assert result['symbols_computed'] == 1
        assert result['errors'] == 0

    @patch('domain.backtest.stages.factor_stage.FactorStage')
    @patch('infrastructure.scheduler.scheduler.FactorORMRepository')
    @patch('infrastructure.scheduler.scheduler.KlineORMRepository')
    def test_total_failure_marks_status_failed(self, mock_kline_repo, mock_factor_repo, mock_stage):
        mock_kline_repo.return_value.get_daily_klines.side_effect = RuntimeError('boom')

        svc = SchedulerService(repo=MagicMock())
        result = svc._handle_factor_compute({'symbols': ['600000', '000001']})

        assert result['symbols_computed'] == 0
        assert result['errors'] == 2
        assert result['status'] == 'failed'

    @patch('infrastructure.scheduler.scheduler.KlineORMRepository')
    def test_insufficient_klines_not_error(self, mock_kline_repo):
        mock_kline_repo.return_value.get_daily_klines.return_value = _fake_klines_df(days=5)

        svc = SchedulerService(repo=MagicMock())
        result = svc._handle_factor_compute({'symbols': ['600000']})

        assert result['symbols_computed'] == 0
        assert result['errors'] == 0
        assert result['status'] == 'success'


class TestDataServiceFactory:
    def test_injected_repo_is_reused(self):
        repo = MagicMock()
        svc = SchedulerService(repo=repo)
        assert svc.repo is repo

    def test_default_repo_is_lazy_initialized(self):
        svc = SchedulerService()
        assert svc._repo is None
        with patch('adapters.outbound.repositories.scheduler_repository.SchedulerRepository') as MockRepo:
            mock_instance = MagicMock()
            MockRepo.return_value = mock_instance
            repo = svc.repo
            assert repo is mock_instance
            assert svc._repo is mock_instance
