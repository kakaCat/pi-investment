"""SchedulerService._execute_command 分发修复测试（2026-08-02 kline_update 接管）

背景：scheduler_tasks 表的 gem-kline-update（command='kline_update'）每个工作日 16:00
失败「Unknown scheduler command」——静态 handler map 缺 kline_update，且应用层
_TASK_HANDLERS 里的命令（如 pool_refresh_daily）没有 fallback 通路。
"""
from unittest.mock import patch

import pytest

from infrastructure.scheduler.scheduler import SchedulerService


@pytest.fixture
def svc():
    return SchedulerService()


class TestKlineUpdateDispatch:
    def test_kline_update_dispatches_to_job_execute(self, svc):
        with patch('infrastructure.jobs.kline_update_job.execute') as mock_exec:
            mock_exec.return_value = {'action': 'kline_update', 'status': 'success'}
            result = svc._execute_command('kline_update', {'days': 5})
        mock_exec.assert_called_once_with(days=5)
        assert result['status'] == 'success'

    def test_kline_update_empty_params(self, svc):
        with patch('infrastructure.jobs.kline_update_job.execute') as mock_exec:
            mock_exec.return_value = {'action': 'kline_update', 'status': 'success'}
            svc._execute_command('kline_update', {})
        mock_exec.assert_called_once_with()


class TestApplicationHandlerFallback:
    def test_pool_refresh_daily_falls_back_to_task_handlers(self, svc):
        # 注意：_TASK_HANDLERS 在模块导入时已绑定函数对象，patch 模块属性无效，需 patch 映射项
        from unittest.mock import MagicMock
        mock_h = MagicMock(return_value={'action': 'pool_refresh_daily', 'status': 'success'})
        with patch.dict('application.services.scheduler_tasks._TASK_HANDLERS', {'pool_refresh_daily': mock_h}):
            result = svc._execute_command('pool_refresh_daily', {})
        mock_h.assert_called_once_with({})
        assert result['status'] == 'success'

    def test_unknown_command_still_raises(self, svc):
        with pytest.raises(ValueError, match="Unknown scheduler command"):
            svc._execute_command('definitely_not_a_command', {})
