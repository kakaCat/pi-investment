"""
Unit tests for scheduler duplicate submission prevention.
"""
from datetime import datetime, timedelta, timezone

import pytest
from unittest.mock import MagicMock, patch
from infrastructure.scheduler.scheduler import SchedulerService


class TestSchedulerDuplicatePrevention:
    """Test duplicate task submission prevention."""

    @pytest.fixture
    def mock_scheduler(self):
        """Create a scheduler with mocked database."""
        scheduler = SchedulerService()
        scheduler._conn = MagicMock()
        return scheduler

    def test_run_task_prevents_duplicate_submission(self, mock_scheduler):
        """Test that run_task raises ValueError when task is already running."""
        task_id = 123

        # Mock task exists
        mock_scheduler.get_task = MagicMock(return_value={
            'id': task_id,
            'name': 'test_task',
            'command': 'data_update',
            'params': {}
        })

        # Mock a recently-started running task (not a zombie)
        recent_start = datetime.now(timezone.utc) - timedelta(minutes=30)
        mock_scheduler.list_runs = MagicMock(return_value=[{
            'id': 456,
            'task_id': task_id,
            'status': 'running',
            'started_at': recent_start,
        }])

        # Attempt to run task should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            mock_scheduler.run_task(task_id)

        # Verify error message
        error_msg = str(exc_info.value)
        assert 'already running' in error_msg
        assert 'run_id=456' in error_msg

        # Verify list_runs was called to check running status
        mock_scheduler.list_runs.assert_called_once_with(
            task_id=task_id,
            statuses=['running'],
            limit=1
        )

    def test_run_task_allows_execution_when_not_running(self, mock_scheduler):
        """Test that run_task proceeds when no running instance exists."""
        task_id = 123
        
        # Mock task exists
        mock_scheduler.get_task = MagicMock(return_value={
            'id': task_id,
            'name': 'test_task',
            'command': 'data_update',
            'params': {}
        })
        
        # Mock no running tasks
        mock_scheduler.list_runs = MagicMock(return_value=[])
        
        # Mock other methods
        mock_scheduler.create_run = MagicMock(return_value=789)
        mock_scheduler.complete_run = MagicMock()
        mock_scheduler._execute_command = MagicMock(return_value={'success': True})
        
        # Should execute without error
        result = mock_scheduler.run_task(task_id)
        
        # Verify execution proceeded
        assert result['status'] == 'success'
        assert result['run_id'] == 789
        mock_scheduler.create_run.assert_called_once_with(task_id)
        mock_scheduler.complete_run.assert_called_once()

    def test_run_task_allows_execution_after_previous_completed(self, mock_scheduler):
        """Test that run_task allows re-execution after previous run completed."""
        task_id = 123
        
        # Mock task exists
        mock_scheduler.get_task = MagicMock(return_value={
            'id': task_id,
            'name': 'test_task',
            'command': 'data_update',
            'params': {}
        })
        
        # Mock only completed/failed runs exist (no running)
        mock_scheduler.list_runs = MagicMock(return_value=[])
        
        # Mock other methods
        mock_scheduler.create_run = MagicMock(return_value=999)
        mock_scheduler.complete_run = MagicMock()
        mock_scheduler._execute_command = MagicMock(return_value={'success': True})
        
        # Should execute without error
        result = mock_scheduler.run_task(task_id)
        
        # Verify execution proceeded
        assert result['status'] == 'success'
        assert result['run_id'] == 999


class TestZombieRunReaping:
    """running 超过超时阈值的 run 视为僵尸（进程被杀残留），自动判死后放行。

    事故背景：2026-08-02 与 08-04 两次进程被 kill 导致 scheduler_runs
    滞留 running 记录，任务被重复执行防护永久阻塞（run 1666 / 2035）。
    """

    @pytest.fixture
    def mock_scheduler(self):
        scheduler = SchedulerService()
        scheduler._conn = MagicMock()
        return scheduler

    def _setup_task(self, mock_scheduler, task_id=123):
        mock_scheduler.get_task = MagicMock(return_value={
            'id': task_id,
            'name': 'test_task',
            'command': 'data_update',
            'params': {}
        })
        mock_scheduler.create_run = MagicMock(return_value=789)
        mock_scheduler.complete_run = MagicMock()
        mock_scheduler._execute_command = MagicMock(return_value={'success': True})

    def test_zombie_run_reaped_and_task_proceeds(self, mock_scheduler):
        """running 超过 6h 的 run 被判死（failed），任务照常执行"""
        task_id = 123
        self._setup_task(mock_scheduler, task_id)

        zombie_start = datetime.now(timezone.utc) - timedelta(hours=7)
        mock_scheduler.list_runs = MagicMock(return_value=[{
            'id': 456,
            'task_id': task_id,
            'status': 'running',
            'started_at': zombie_start,
        }])

        result = mock_scheduler.run_task(task_id)

        # 任务放行执行
        assert result['status'] == 'success'
        assert result['run_id'] == 789
        # 僵尸 run 被标记 failed
        reap_calls = [c for c in mock_scheduler.complete_run.call_args_list
                      if c.args[0] == 456]
        assert len(reap_calls) == 1
        assert reap_calls[0].kwargs.get('success') is False
        assert 'zombie' in (reap_calls[0].kwargs.get('error') or '')

    def test_zombie_run_with_string_started_at(self, mock_scheduler):
        """started_at 为 ISO 字符串（旧数据形态）也能判死"""
        task_id = 123
        self._setup_task(mock_scheduler, task_id)

        zombie_start = (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat()
        mock_scheduler.list_runs = MagicMock(return_value=[{
            'id': 456,
            'task_id': task_id,
            'status': 'running',
            'started_at': zombie_start,
        }])

        result = mock_scheduler.run_task(task_id)
        assert result['status'] == 'success'

    def test_fresh_running_task_not_reaped(self, mock_scheduler):
        """刚启动 1 小时的正常长任务不误杀"""
        task_id = 123
        self._setup_task(mock_scheduler, task_id)

        fresh_start = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_scheduler.list_runs = MagicMock(return_value=[{
            'id': 456,
            'task_id': task_id,
            'status': 'running',
            'started_at': fresh_start,
        }])

        with pytest.raises(ValueError) as exc_info:
            mock_scheduler.run_task(task_id)
        assert 'already running' in str(exc_info.value)
        # 不创建新 run、不判死旧 run
        mock_scheduler.create_run.assert_not_called()
        mock_scheduler.complete_run.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
