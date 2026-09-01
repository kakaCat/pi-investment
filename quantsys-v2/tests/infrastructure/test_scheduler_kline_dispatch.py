"""SchedulerService._execute_command 分发测试

背景：_execute_command 已迁移到 job_registry.execute() 统一调度。
本测试验证 SchedulerService 正确委托给 JobRegistry。
"""
from unittest.mock import patch, AsyncMock

import pytest

from infrastructure.scheduler.scheduler import SchedulerService
from application.jobs.job_protocol import JobResult


@pytest.fixture
def svc():
    return SchedulerService()


def _ok_result(name="test", details=None):
    return JobResult.ok(name, message="ok", details=details or {})


def _fail_result(name="test", error="boom"):
    return JobResult.fail(name, error)


class TestExecuteCommandDelegatesToJobRegistry:
    """_execute_command 应委托给 job_registry.execute"""

    @patch('application.jobs.job_registry.job_registry')
    def test_kline_update_dispatches(self, mock_registry, svc):
        mock_registry.execute = AsyncMock(return_value=_ok_result("kline_update"))
        result = svc._execute_command('kline_update', {'days': 5})

        mock_registry.execute.assert_called_once_with('kline_update', {'days': 5})
        assert result['status'] == 'success'

    @patch('application.jobs.job_registry.job_registry')
    def test_kline_update_empty_params(self, mock_registry, svc):
        mock_registry.execute = AsyncMock(return_value=_ok_result("kline_update"))
        svc._execute_command('kline_update', {})

        mock_registry.execute.assert_called_once_with('kline_update', {})

    @patch('application.jobs.job_registry.job_registry')
    def test_pool_refresh_daily_dispatches(self, mock_registry, svc):
        mock_registry.execute = AsyncMock(return_value=_ok_result("pool_refresh_daily"))
        result = svc._execute_command('pool_refresh_daily', {})

        mock_registry.execute.assert_called_once_with('pool_refresh_daily', {})
        assert result['status'] == 'success'

    @patch('application.jobs.job_registry.job_registry')
    def test_chip_distribution_dispatches(self, mock_registry, svc):
        mock_registry.execute = AsyncMock(return_value=_ok_result("chip_distribution_update"))
        result = svc._execute_command('chip_distribution_update', {})

        mock_registry.execute.assert_called_once_with('chip_distribution_update', {})
        assert result['status'] == 'success'

    @patch('application.jobs.job_registry.job_registry')
    def test_unknown_command_returns_failed(self, mock_registry, svc):
        mock_registry.execute = AsyncMock(
            return_value=_fail_result("unknown", "Unknown job: unknown"))
        result = svc._execute_command('definitely_not_a_command', {})

        assert result['status'] == 'failed'
        assert 'Unknown job' in (result.get('error') or '')

    @patch('application.jobs.job_registry.job_registry')
    def test_failed_job_returns_failed_status(self, mock_registry, svc):
        mock_registry.execute = AsyncMock(
            return_value=_fail_result("factor_compute", "db down"))
        result = svc._execute_command('factor_compute', {})

        assert result['status'] == 'failed'
        assert result['error'] == 'db down'
