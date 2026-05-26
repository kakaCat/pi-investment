"""
Tests for ProgressTracker class.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from quantsys.data.progress_tracker import ProgressTracker


class TestProgressTracker:
    """Test suite for ProgressTracker."""

    @pytest.fixture
    def temp_state_file(self):
        """Create a temporary state file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        # Also cleanup temp file if exists
        temp_tmp = temp_path + '.tmp'
        if os.path.exists(temp_tmp):
            os.unlink(temp_tmp)

    def test_init_creates_empty_state(self, temp_state_file):
        """Test that initialization creates empty state."""
        tracker = ProgressTracker(temp_state_file)
        assert tracker.state_file == temp_state_file
        assert tracker.state == {}

    def test_load_nonexistent_file(self, temp_state_file):
        """Test loading when file doesn't exist."""
        os.unlink(temp_state_file)  # Ensure file doesn't exist
        tracker = ProgressTracker(temp_state_file)
        tracker.load()
        assert tracker.state == {}

    def test_load_existing_file(self, temp_state_file):
        """Test loading existing progress file."""
        test_data = {
            "600519.SH": {
                "daily": ["2024-01-01", "2024-01-02"],
                "minute": ["2024-01-01"]
            }
        }
        with open(temp_state_file, 'w') as f:
            json.dump(test_data, f)

        tracker = ProgressTracker(temp_state_file)
        tracker.load()
        assert tracker.state == test_data

    def test_load_invalid_json(self, temp_state_file):
        """Test loading file with invalid JSON."""
        with open(temp_state_file, 'w') as f:
            f.write("invalid json {")

        tracker = ProgressTracker(temp_state_file)
        tracker.load()  # Should not raise, should initialize empty state
        assert tracker.state == {}

    def test_save_creates_file(self, temp_state_file):
        """Test that save creates the file."""
        os.unlink(temp_state_file)  # Ensure file doesn't exist
        tracker = ProgressTracker(temp_state_file)
        tracker.state = {"test": "data"}
        tracker.save()

        assert os.path.exists(temp_state_file)
        with open(temp_state_file, 'r') as f:
            data = json.load(f)
        assert data == {"test": "data"}

    def test_save_creates_parent_directory(self):
        """Test that save creates parent directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "subdir", "progress.json")
            tracker = ProgressTracker(state_file)
            tracker.state = {"test": "data"}
            tracker.save()

            assert os.path.exists(state_file)
            with open(state_file, 'r') as f:
                data = json.load(f)
            assert data == {"test": "data"}

    def test_mark_completed_new_symbol(self, temp_state_file):
        """Test marking completion for a new symbol."""
        tracker = ProgressTracker(temp_state_file)
        tracker.mark_completed("600519.SH", "daily", "2024-01-01")

        assert "600519.SH" in tracker.state
        assert "daily" in tracker.state["600519.SH"]
        assert "2024-01-01" in tracker.state["600519.SH"]["daily"]

    def test_mark_completed_existing_symbol(self, temp_state_file):
        """Test marking completion for existing symbol."""
        tracker = ProgressTracker(temp_state_file)
        tracker.mark_completed("600519.SH", "daily", "2024-01-01")
        tracker.mark_completed("600519.SH", "daily", "2024-01-02")
        tracker.mark_completed("600519.SH", "minute", "2024-01-01")

        assert len(tracker.state["600519.SH"]["daily"]) == 2
        assert len(tracker.state["600519.SH"]["minute"]) == 1

    def test_mark_completed_duplicate(self, temp_state_file):
        """Test marking same date twice doesn't duplicate."""
        tracker = ProgressTracker(temp_state_file)
        tracker.mark_completed("600519.SH", "daily", "2024-01-01")
        tracker.mark_completed("600519.SH", "daily", "2024-01-01")

        assert tracker.state["600519.SH"]["daily"].count("2024-01-01") == 1

    def test_is_completed_true(self, temp_state_file):
        """Test is_completed returns True for completed date."""
        tracker = ProgressTracker(temp_state_file)
        tracker.mark_completed("600519.SH", "daily", "2024-01-01")

        assert tracker.is_completed("600519.SH", "daily", "2024-01-01") is True

    def test_is_completed_false(self, temp_state_file):
        """Test is_completed returns False for non-completed date."""
        tracker = ProgressTracker(temp_state_file)
        tracker.mark_completed("600519.SH", "daily", "2024-01-01")

        assert tracker.is_completed("600519.SH", "daily", "2024-01-02") is False

    def test_is_completed_missing_symbol(self, temp_state_file):
        """Test is_completed returns False for missing symbol."""
        tracker = ProgressTracker(temp_state_file)
        assert tracker.is_completed("600519.SH", "daily", "2024-01-01") is False

    def test_is_completed_missing_data_type(self, temp_state_file):
        """Test is_completed returns False for missing data type."""
        tracker = ProgressTracker(temp_state_file)
        tracker.mark_completed("600519.SH", "daily", "2024-01-01")

        assert tracker.is_completed("600519.SH", "minute", "2024-01-01") is False

    def test_get_pending_dates_all_pending(self, temp_state_file):
        """Test get_pending_dates when all dates are pending."""
        tracker = ProgressTracker(temp_state_file)
        all_dates = ["2024-01-01", "2024-01-02", "2024-01-03"]

        pending = tracker.get_pending_dates("600519.SH", "daily", all_dates)
        assert pending == all_dates

    def test_get_pending_dates_some_completed(self, temp_state_file):
        """Test get_pending_dates with some completed dates."""
        tracker = ProgressTracker(temp_state_file)
        tracker.mark_completed("600519.SH", "daily", "2024-01-01")
        tracker.mark_completed("600519.SH", "daily", "2024-01-03")

        all_dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        pending = tracker.get_pending_dates("600519.SH", "daily", all_dates)
        assert pending == ["2024-01-02"]

    def test_get_pending_dates_all_completed(self, temp_state_file):
        """Test get_pending_dates when all dates are completed."""
        tracker = ProgressTracker(temp_state_file)
        all_dates = ["2024-01-01", "2024-01-02"]
        for date in all_dates:
            tracker.mark_completed("600519.SH", "daily", date)

        pending = tracker.get_pending_dates("600519.SH", "daily", all_dates)
        assert pending == []

    def test_clear_symbol(self, temp_state_file):
        """Test clearing all progress for a symbol."""
        tracker = ProgressTracker(temp_state_file)
        tracker.mark_completed("600519.SH", "daily", "2024-01-01")
        tracker.mark_completed("600519.SH", "minute", "2024-01-01")
        tracker.mark_completed("000001.SZ", "daily", "2024-01-01")

        tracker.clear_symbol("600519.SH")

        assert "600519.SH" not in tracker.state
        assert "000001.SZ" in tracker.state

    def test_clear_symbol_nonexistent(self, temp_state_file):
        """Test clearing non-existent symbol doesn't raise."""
        tracker = ProgressTracker(temp_state_file)
        tracker.clear_symbol("600519.SH")  # Should not raise
        assert "600519.SH" not in tracker.state

    def test_save_and_load_roundtrip(self, temp_state_file):
        """Test that save and load preserve data."""
        tracker1 = ProgressTracker(temp_state_file)
        tracker1.mark_completed("600519.SH", "daily", "2024-01-01")
        tracker1.mark_completed("600519.SH", "minute", "2024-01-02")
        tracker1.save()

        tracker2 = ProgressTracker(temp_state_file)
        tracker2.load()

        assert tracker2.state == tracker1.state
        assert tracker2.is_completed("600519.SH", "daily", "2024-01-01")
        assert tracker2.is_completed("600519.SH", "minute", "2024-01-02")

    def test_atomic_write(self, temp_state_file):
        """Test that save uses atomic write pattern."""
        tracker = ProgressTracker(temp_state_file)
        tracker.state = {"test": "data"}
        tracker.save()

        # Verify temp file is cleaned up
        temp_tmp = temp_state_file + '.tmp'
        assert not os.path.exists(temp_tmp)

        # Verify final file exists and is valid
        assert os.path.exists(temp_state_file)
        with open(temp_state_file, 'r') as f:
            data = json.load(f)
        assert data == {"test": "data"}
