"""
Unit tests for scheduler duplicate submission prevention.
"""
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
        
        # Mock a running task exists
        mock_scheduler.list_runs = MagicMock(return_value=[{
            'id': 456,
            'task_id': task_id,
            'status': 'running',
            'started_at': '2026-06-04T10:00:00'
        }])
        
        # Attempt to run task should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            mock_scheduler.run_task(task_id)
        
        # Verify error message
        error_msg = str(exc_info.value)
        assert 'already running' in error_msg
        assert 'run_id=456' in error_msg
        assert 'started at 2026-06-04T10:00:00' in error_msg
        
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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
