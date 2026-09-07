"""
Tests for SignalExecutionLogORMRepository

Following TDD approach - tests written before implementation
"""
import pytest
from datetime import datetime, date
from adapters.outbound.repositories import SignalExecutionLogORMRepository


class TestSignalExecutionLogORMRepository:
    """Test suite for SignalExecutionLogORMRepository"""

    @pytest.fixture
    def repo(self):
        """Create repository instance for testing"""
        return SignalExecutionLogORMRepository()

    @pytest.fixture
    def sample_log_data(self):
        """Sample log data for testing"""
        return {
            "execution_date": "2026-05-28",
            "start_time": "2026-05-28 09:30:00",
            "status": "running"
        }

    def test_create_execution_log(self, repo, sample_log_data):
        """Test creating a new execution log"""
        # Act
        log_id = repo.create_execution_log(sample_log_data)

        # Assert
        assert log_id is not None
        assert isinstance(log_id, int)
        assert log_id > 0

    def test_create_execution_log_with_full_data(self, repo):
        """Test creating log with all fields"""
        # Arrange
        full_data = {
            "execution_date": "2026-05-28",
            "start_time": "2026-05-28 09:30:00",
            "end_time": "2026-05-28 09:35:00",
            "duration_ms": 300000,
            "strategies_run": 5,
            "signals_generated": 10,
            "signals_approved": 8,
            "signals_rejected": 2,
            "orders_created": 8,
            "errors_count": 0,
            "execution_details": {"test": "data"},
            "status": "completed",
            "error_message": None
        }

        # Act
        log_id = repo.create_execution_log(full_data)

        # Assert
        assert log_id > 0

    def test_update_execution_log(self, repo, sample_log_data):
        """Test updating an existing execution log"""
        # Arrange - create a log first
        log_id = repo.create_execution_log(sample_log_data)

        # Act - update the log
        update_data = {
            "end_time": "2026-05-28 09:35:00",
            "duration_ms": 300000,
            "status": "completed",
            "signals_generated": 5
        }
        result = repo.update_execution_log(log_id, update_data)

        # Assert
        assert result is True

    def test_update_nonexistent_log(self, repo):
        """Test updating a log that doesn't exist"""
        # Act
        result = repo.update_execution_log(999999, {"status": "completed"})

        # Assert
        assert result is False

    def test_get_log(self, repo, sample_log_data):
        """Test retrieving a single log by ID"""
        # Arrange - create a log
        log_id = repo.create_execution_log(sample_log_data)

        # Act
        log = repo.get_log(log_id)

        # Assert
        assert log is not None
        assert log["id"] == log_id
        assert log["execution_date"] == "2026-05-28"  # ORM 序列化为 ISO 字符串（对齐 HTTP 契约）
        assert log["status"] == "running"

    def test_get_nonexistent_log(self, repo):
        """Test retrieving a log that doesn't exist"""
        # Act
        log = repo.get_log(999999)

        # Assert
        assert log is None

    def test_get_logs_by_date_range(self, repo):
        """Test querying logs by date range"""
        # Arrange - create multiple logs
        repo.create_execution_log({
            "execution_date": "2026-05-26",
            "start_time": "2026-05-26 09:30:00",
            "status": "completed"
        })
        repo.create_execution_log({
            "execution_date": "2026-05-27",
            "start_time": "2026-05-27 09:30:00",
            "status": "completed"
        })
        repo.create_execution_log({
            "execution_date": "2026-05-28",
            "start_time": "2026-05-28 09:30:00",
            "status": "running"
        })

        # Act
        logs = repo.get_logs_by_date_range("2026-05-26", "2026-05-27")

        # Assert
        assert len(logs) >= 2
        for log in logs:
            assert log["execution_date"] >= "2026-05-26"  # ISO 字符串字典序即日期序
            assert log["execution_date"] <= "2026-05-27"

    def test_get_logs_by_date_range_empty(self, repo):
        """Test querying logs with no results"""
        # Act
        logs = repo.get_logs_by_date_range("2020-01-01", "2020-01-02")

        # Assert
        assert logs == []

    def test_get_logs_by_date_range_ordering(self, repo):
        """Test that logs are returned in descending date order"""
        # Arrange
        repo.create_execution_log({
            "execution_date": "2026-05-26",
            "start_time": "2026-05-26 09:30:00",
            "status": "completed"
        })
        repo.create_execution_log({
            "execution_date": "2026-05-28",
            "start_time": "2026-05-28 09:30:00",
            "status": "completed"
        })
        repo.create_execution_log({
            "execution_date": "2026-05-27",
            "start_time": "2026-05-27 09:30:00",
            "status": "completed"
        })

        # Act
        logs = repo.get_logs_by_date_range("2026-05-26", "2026-05-28")

        # Assert
        assert len(logs) >= 3
        # Should be in descending order (newest first)
        for i in range(len(logs) - 1):
            assert logs[i]["execution_date"] >= logs[i + 1]["execution_date"]
