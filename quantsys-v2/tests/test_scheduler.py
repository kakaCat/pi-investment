"""
Tests for the cron-based scheduler.

Covers:
- Cron expression parsing (unit tests, no DB needed)
- next_run_time calculation
- Task CRUD (requires DB)
- Run lifecycle (requires DB)
- Due-check logic
- Command handlers
"""
import pytest
from datetime import datetime, timedelta, timezone

from infrastructure.scheduler.scheduler import (
    CronSchedule,
    SchedulerService,
    _cron_dow,
    _parse_field,
    next_run_time,
    parse_cron,
)


# ============================================================================
# Cron parsing unit tests (no database required)
# ============================================================================


class TestCronParsing:
    """Unit tests for the 5-field cron parser."""

    def test_parse_simple_weekday(self):
        """0 9 * * 1-5 — every weekday at 09:00."""
        schedule = parse_cron("0 9 * * 1-5")
        assert schedule.minute == {0}
        assert schedule.hour == {9}
        assert schedule.dom == set(range(1, 32))
        assert schedule.month == set(range(1, 13))
        assert schedule.dow == {1, 2, 3, 4, 5}

    def test_parse_all_wildcards(self):
        """* * * * * — every minute."""
        schedule = parse_cron("* * * * *")
        assert schedule.minute == set(range(0, 60))
        assert schedule.hour == set(range(0, 24))
        assert schedule.dom == set(range(1, 32))
        assert schedule.month == set(range(1, 13))
        assert schedule.dow == set(range(0, 8))  # 0-7 (Sunday is 0 and 7)

    def test_parse_step(self):
        """*/15 * * * * — every 15 minutes."""
        schedule = parse_cron("*/15 * * * *")
        assert schedule.minute == {0, 15, 30, 45}

    def test_parse_list(self):
        """0,30 9,17 * * * — at 09:00, 09:30, 17:00, 17:30."""
        schedule = parse_cron("0,30 9,17 * * *")
        assert schedule.minute == {0, 30}
        assert schedule.hour == {9, 17}

    def test_parse_range(self):
        """0 9-17 * * * — every hour from 9 to 17."""
        schedule = parse_cron("0 9-17 * * *")
        assert schedule.hour == set(range(9, 18))

    def test_parse_range_with_step(self):
        """0 9-17/2 * * * — every 2 hours from 9 to 17."""
        schedule = parse_cron("0 9-17/2 * * *")
        assert schedule.hour == {9, 11, 13, 15, 17}

    def test_parse_list_with_range(self):
        """0 9-12,14-17 * * * — morning and afternoon hours."""
        schedule = parse_cron("0 9-12,14-17 * * *")
        assert schedule.hour == {9, 10, 11, 12, 14, 15, 16, 17}

    def test_parse_specific_dom(self):
        """0 0 1 * * — midnight on the 1st of every month."""
        schedule = parse_cron("0 0 1 * *")
        assert schedule.dom == {1}

    def test_parse_specific_month(self):
        """0 0 1 1 * — midnight on Jan 1st."""
        schedule = parse_cron("0 0 1 1 *")
        assert schedule.dom == {1}
        assert schedule.month == {1}

    def test_parse_too_few_fields(self):
        with pytest.raises(ValueError, match="5 fields"):
            parse_cron("0 9 * *")

    def test_parse_too_many_fields(self):
        with pytest.raises(ValueError, match="5 fields"):
            parse_cron("0 9 * * 1-5 extra")

    def test_parse_invalid_minute(self):
        with pytest.raises(ValueError, match="out of bounds"):
            parse_cron("60 9 * * *")

    def test_parse_invalid_hour(self):
        with pytest.raises(ValueError, match="out of bounds"):
            parse_cron("0 25 * * *")

    def test_parse_invalid_dom(self):
        with pytest.raises(ValueError, match="out of bounds"):
            parse_cron("0 9 32 * *")

    def test_parse_invalid_month(self):
        with pytest.raises(ValueError, match="out of bounds"):
            parse_cron("0 9 * 13 *")

    def test_parse_negative_step(self):
        with pytest.raises(ValueError, match="Step must be positive"):
            parse_cron("*/0 * * * *")

    def test_parse_sunday_both_forms(self):
        """Both 0 and 7 mean Sunday in cron DOW field.
        The parser normalises: if 0 is present, 7 is added; if 7 is
        present, 0 is added."""
        s0 = parse_cron("0 9 * * 0")
        s7 = parse_cron("0 9 * * 7")
        # Both forms result in {0, 7} after normalisation
        assert s0.dow == {0, 7}
        assert s7.dow == {0, 7}


# ============================================================================
# CronSchedule.matches() tests
# ============================================================================


class TestCronScheduleMatches:
    """Tests for CronSchedule.matches()."""

    def test_matches_weekday_morning(self):
        schedule = parse_cron("0 9 * * 1-5")
        # Monday 2025-01-06 09:00
        assert schedule.matches(datetime(2025, 1, 6, 9, 0)) is True

    def test_matches_wrong_minute(self):
        schedule = parse_cron("0 9 * * 1-5")
        assert schedule.matches(datetime(2025, 1, 6, 9, 1)) is False

    def test_matches_wrong_hour(self):
        schedule = parse_cron("0 9 * * 1-5")
        assert schedule.matches(datetime(2025, 1, 6, 8, 0)) is False

    def test_matches_saturday(self):
        schedule = parse_cron("0 9 * * 1-5")
        assert schedule.matches(datetime(2025, 1, 4, 9, 0)) is False  # Saturday

    def test_matches_sunday(self):
        schedule = parse_cron("0 9 * * 1-5")
        assert schedule.matches(datetime(2025, 1, 5, 9, 0)) is False  # Sunday

    def test_matches_sunday_with_cron0(self):
        """Sunday DOW=0 should match."""
        schedule = parse_cron("0 9 * * 0")
        # 2025-01-05 is a Sunday
        assert schedule.matches(datetime(2025, 1, 5, 9, 0)) is True

    def test_matches_sunday_with_cron7(self):
        """Sunday DOW=7 should also match."""
        schedule = parse_cron("0 9 * * 7")
        # 2025-01-05 is a Sunday
        assert schedule.matches(datetime(2025, 1, 5, 9, 0)) is True

    def test_matches_specific_date(self):
        schedule = parse_cron("0 0 15 * *")
        assert schedule.matches(datetime(2025, 3, 15, 0, 0)) is True
        assert schedule.matches(datetime(2025, 3, 14, 0, 0)) is False

    def test_matches_every_minute(self):
        schedule = parse_cron("* * * * *")
        assert schedule.matches(datetime(2025, 1, 1, 12, 34)) is True
        assert schedule.matches(datetime(2025, 12, 31, 23, 59)) is True


# ============================================================================
# _cron_dow helper tests
# ============================================================================


class TestCronDow:
    """Tests for the Python-weekday to cron-DOW conversion."""

    def test_monday(self):
        # 2025-01-06 is Monday
        assert _cron_dow(datetime(2025, 1, 6)) == 1

    def test_tuesday(self):
        assert _cron_dow(datetime(2025, 1, 7)) == 2

    def test_wednesday(self):
        assert _cron_dow(datetime(2025, 1, 8)) == 3

    def test_thursday(self):
        assert _cron_dow(datetime(2025, 1, 9)) == 4

    def test_friday(self):
        assert _cron_dow(datetime(2025, 1, 10)) == 5

    def test_saturday(self):
        assert _cron_dow(datetime(2025, 1, 11)) == 6

    def test_sunday(self):
        assert _cron_dow(datetime(2025, 1, 12)) == 0


# ============================================================================
# _parse_field helper tests
# ============================================================================


class TestParseField:
    """Edge-case tests for the low-level field parser."""

    def test_wildcard(self):
        assert _parse_field("*", 0, 5) == {0, 1, 2, 3, 4, 5}

    def test_single_value(self):
        assert _parse_field("3", 0, 5) == {3}

    def test_range(self):
        assert _parse_field("1-3", 0, 5) == {1, 2, 3}

    def test_list(self):
        assert _parse_field("1,3,5", 0, 5) == {1, 3, 5}

    def test_step_from_wildcard(self):
        assert _parse_field("*/2", 0, 5) == {0, 2, 4}

    def test_step_from_range(self):
        assert _parse_field("1-5/2", 0, 5) == {1, 3, 5}

    def test_step_from_single(self):
        assert _parse_field("2/2", 0, 5) == {2, 4}


# ============================================================================
# next_run_time tests
# ============================================================================


class TestNextRunTime:
    """Tests for next_run_time calculation."""

    def test_same_day(self):
        """From 08:00, the next 09:00 is same day."""
        from_time = datetime(2025, 1, 6, 8, 0, tzinfo=timezone.utc)  # Monday
        result = next_run_time("0 9 * * 1-5", from_time)
        assert result == datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc)

    def test_already_passed_today(self):
        """From 10:00, the next 09:00 is Tuesday."""
        from_time = datetime(2025, 1, 6, 10, 0, tzinfo=timezone.utc)  # Monday
        result = next_run_time("0 9 * * 1-5", from_time)
        assert result == datetime(2025, 1, 7, 9, 0, tzinfo=timezone.utc)  # Tuesday

    def test_skip_weekend(self):
        """From Friday 10:00, the next weekday 09:00 is Monday."""
        from_time = datetime(2025, 1, 3, 10, 0, tzinfo=timezone.utc)  # Friday
        result = next_run_time("0 9 * * 1-5", from_time)
        assert result == datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc)  # Monday

    def test_exact_match_is_skipped(self):
        """If from_time matches exactly, we should get the NEXT occurrence."""
        from_time = datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc)  # Monday 09:00
        result = next_run_time("0 9 * * 1-5", from_time)
        # Should be Tuesday 09:00, not Monday 09:00
        assert result == datetime(2025, 1, 7, 9, 0, tzinfo=timezone.utc)

    def test_every_minute(self):
        from_time = datetime(2025, 1, 6, 9, 0, 30, tzinfo=timezone.utc)
        result = next_run_time("* * * * *", from_time)
        assert result == datetime(2025, 1, 6, 9, 1, tzinfo=timezone.utc)

    def test_every_15_minutes(self):
        from_time = datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc)
        result = next_run_time("*/15 * * * *", from_time)
        assert result == datetime(2025, 1, 6, 9, 15, tzinfo=timezone.utc)

    def test_specific_month_day(self):
        """Midnight on the 1st of every month."""
        from_time = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        result = next_run_time("0 0 1 * *", from_time)
        assert result == datetime(2025, 2, 1, 0, 0, tzinfo=timezone.utc)

    def test_default_from_time_is_utc_now(self):
        """Calling without from_time should return a future time."""
        result = next_run_time("* * * * *")
        now = datetime.now(timezone.utc)
        assert result > now

    def test_naive_from_time_treated_as_utc(self):
        """Naive datetimes should be treated as UTC."""
        from_time = datetime(2025, 1, 6, 8, 0)  # naive
        result = next_run_time("0 9 * * 1-5", from_time)
        assert result.tzinfo is not None
        assert result == datetime(2025, 1, 6, 9, 0, tzinfo=timezone.utc)


# ============================================================================
# CronSchedule dataclass tests
# ============================================================================


class TestCronScheduleDataclass:
    """Direct CronSchedule construction and matches()."""

    def test_construction_and_matches(self):
        s = CronSchedule(
            minute={0},
            hour={9},
            dom=set(range(1, 32)),
            month=set(range(1, 13)),
            dow={1, 2, 3, 4, 5},
        )
        assert s.matches(datetime(2025, 1, 6, 9, 0)) is True
        assert s.matches(datetime(2025, 1, 6, 9, 1)) is False
        assert s.matches(datetime(2025, 1, 4, 9, 0)) is False  # Saturday

    def test_feb_29_leap_year(self):
        """Feb 29 in a leap year matches when DOM=29 and MONTH=2."""
        s = CronSchedule(
            minute={0},
            hour={0},
            dom={29},
            month={2},
            dow=set(range(0, 8)),
        )
        # 2024 is a leap year — Python can represent this date
        assert s.matches(datetime(2024, 2, 29, 0, 0)) is True
        # 2025 is not a leap year — Python rejects the date entirely,
        # so this edge case cannot occur at runtime.


# ============================================================================
# Task CRUD tests (requires database)
# ============================================================================


@pytest.mark.integration
class TestSchedulerTaskCRUD:
    """Task CRUD operations — requires a live database connection."""

    def setup_method(self):
        self.scheduler = SchedulerService()
        self._cleanup_ids: list[int] = []

    def teardown_method(self):
        for task_id in self._cleanup_ids:
            try:
                self.scheduler.remove_task(task_id)
            except Exception:
                pass
        self.scheduler.close()

    def _register(self, task_id: int) -> int:
        self._cleanup_ids.append(task_id)
        return task_id

    # --- add / get ---

    def test_add_and_get_task(self):
        task_id = self._register(
            self.scheduler.add_task(
                name="test-crud-add",
                cron_expression="0 9 * * 1-5",
                command="report_daily",
                description="CRUD add test",
            )
        )
        assert isinstance(task_id, int)
        assert task_id > 0

        task = self.scheduler.get_task(task_id)
        assert task is not None
        assert task["name"] == "test-crud-add"
        assert task["command"] == "report_daily"
        assert task["cron_expression"] == "0 9 * * 1-5"
        assert task["description"] == "CRUD add test"
        assert task["is_enabled"] is True
        assert task["next_run_at"] is not None

    def test_add_task_with_params(self):
        task_id = self._register(
            self.scheduler.add_task(
                name="test-crud-params",
                cron_expression="0 9 * * *",
                command="data_update",
                params={"market": "A", "symbols": ["000001.SZ"]},
            )
        )
        task = self.scheduler.get_task(task_id)
        assert task is not None
        # params are stored as JSON string in DB but retrieved as string
        import json
        params = task.get("params")
        if isinstance(params, str):
            params = json.loads(params)
        assert params == {"market": "A", "symbols": ["000001.SZ"]}

    def test_add_duplicate_name_raises(self):
        task_id = self._register(
            self.scheduler.add_task("test-crud-dup", "0 9 * * *", "risk_check")
        )
        with pytest.raises(ValueError, match="already exists"):
            self.scheduler.add_task("test-crud-dup", "0 9 * * *", "risk_check")

    def test_add_invalid_cron_raises(self):
        with pytest.raises(ValueError, match="5 fields"):
            self.scheduler.add_task("test-crud-bad-cron", "bad", "risk_check")

    # --- list ---

    def test_list_tasks(self):
        task_id = self._register(
            self.scheduler.add_task("test-crud-list", "0 9 * * *", "risk_check")
        )
        tasks = self.scheduler.list_tasks()
        assert isinstance(tasks, list)
        names = {t["name"] for t in tasks}
        assert "test-crud-list" in names

    def test_list_tasks_enabled_only(self):
        tid1 = self._register(
            self.scheduler.add_task("test-crud-en1", "0 9 * * *", "risk_check")
        )
        tid2 = self._register(
            self.scheduler.add_task("test-crud-en2", "0 9 * * *", "risk_check")
        )
        self.scheduler.disable_task(tid2)

        tasks = self.scheduler.list_tasks(enabled_only=True)
        names = {t["name"] for t in tasks}
        assert "test-crud-en1" in names
        assert "test-crud-en2" not in names

    # --- enable / disable ---

    def test_enable_disable_task(self):
        task_id = self._register(
            self.scheduler.add_task("test-crud-toggle", "0 9 * * *", "risk_check")
        )

        self.scheduler.disable_task(task_id)
        task = self.scheduler.get_task(task_id)
        assert task is not None
        assert task["is_enabled"] is False

        self.scheduler.enable_task(task_id)
        task = self.scheduler.get_task(task_id)
        assert task is not None
        assert task["is_enabled"] is True
        assert task["next_run_at"] is not None

    def test_enable_nonexistent_task(self):
        with pytest.raises(ValueError, match="not found"):
            self.scheduler.enable_task(999999)

    # --- update ---

    def test_update_task_description(self):
        task_id = self._register(
            self.scheduler.add_task("test-crud-upd", "0 9 * * *", "risk_check")
        )
        self.scheduler.update_task(task_id, description="new description")
        task = self.scheduler.get_task(task_id)
        assert task["description"] == "new description"

    def test_update_task_cron_recalculates_next(self):
        task_id = self._register(
            self.scheduler.add_task(
                "test-crud-upd-cron", "0 9 * * 1-5", "risk_check"
            )
        )
        self.scheduler.update_task(task_id, cron_expression="0 18 * * *")
        task = self.scheduler.get_task(task_id)
        assert task["cron_expression"] == "0 18 * * *"
        assert task["next_run_at"] is not None

    def test_update_task_with_invalid_kwarg_ignored(self):
        task_id = self._register(
            self.scheduler.add_task("test-crud-upd2", "0 9 * * *", "risk_check")
        )
        result = self.scheduler.update_task(
            task_id, description="ok", nonexistent_field="ignored"
        )
        assert result is True

    # --- remove ---

    def test_remove_task(self):
        task_id = self.scheduler.add_task("test-crud-rm", "0 9 * * *", "risk_check")
        assert self.scheduler.remove_task(task_id) is True
        assert self.scheduler.get_task(task_id) is None
        # Second remove should return False
        assert self.scheduler.remove_task(task_id) is False

    # --- get by name ---

    def test_get_task_by_name(self):
        task_id = self._register(
            self.scheduler.add_task("test-crud-byname", "0 9 * * *", "risk_check")
        )
        task = self.scheduler.get_task_by_name("test-crud-byname")
        assert task is not None
        assert task["id"] == task_id

    def test_get_task_by_name_nonexistent(self):
        assert self.scheduler.get_task_by_name("nonexistent-task") is None


# ============================================================================
# Run lifecycle tests (requires database)
# ============================================================================


@pytest.mark.integration
class TestSchedulerRunLifecycle:
    """Run lifecycle — requires a live database connection."""

    def setup_method(self):
        self.scheduler = SchedulerService()
        self.task_id = self.scheduler.add_task(
            "test-run-lifecycle", "0 9 * * *", "risk_check"
        )

    def teardown_method(self):
        try:
            self.scheduler.remove_task(self.task_id)
        except Exception:
            pass
        self.scheduler.close()

    def test_create_and_complete_run_success(self):
        run_id = self.scheduler.create_run(self.task_id)
        assert isinstance(run_id, int)
        assert run_id > 0

        run = self.scheduler.get_run(run_id)
        assert run is not None
        assert run["status"] == "running"
        assert run["task_id"] == self.task_id
        assert run["started_at"] is not None

        self.scheduler.complete_run(run_id, success=True, result={"ok": True})

        run = self.scheduler.get_run(run_id)
        assert run["status"] == "success"
        assert run["completed_at"] is not None
        assert run["duration_ms"] is not None
        assert run["duration_ms"] >= 0

        # Task should have updated status
        task = self.scheduler.get_task(self.task_id)
        assert task is not None
        assert task["last_status"] == "success"
        assert task["next_run_at"] is not None

    def test_create_and_complete_run_failure(self):
        run_id = self.scheduler.create_run(self.task_id)
        self.scheduler.complete_run(
            run_id, success=False, error="Something went wrong"
        )

        run = self.scheduler.get_run(run_id)
        assert run["status"] == "failed"
        assert run["error"] == "Something went wrong"
        assert run["completed_at"] is not None

        task = self.scheduler.get_task(self.task_id)
        assert task is not None
        assert task["last_status"] == "failed"
        assert task["last_error"] == "Something went wrong"

    def test_list_runs(self):
        run_id = self.scheduler.create_run(self.task_id)
        self.scheduler.complete_run(run_id, success=True)

        runs = self.scheduler.list_runs(task_id=self.task_id)
        assert len(runs) >= 1
        run_ids = {r["id"] for r in runs}
        assert run_id in run_ids

    def test_list_runs_with_limit(self):
        runs = self.scheduler.list_runs(limit=10)
        assert len(runs) <= 10

    def test_get_run_nonexistent(self):
        assert self.scheduler.get_run(999999) is None

    def test_run_task_executes_handler(self):
        """run_task should create a run, execute handler, and complete."""
        result = self.scheduler.run_task(self.task_id)
        assert result["task_id"] == self.task_id
        assert result["task_name"] == "test-run-lifecycle"
        assert "run_id" in result
        assert result["status"] in ("success", "failed")

        # Verify a run record exists
        run = self.scheduler.get_run(result["run_id"])
        assert run is not None
        assert run["status"] == result["status"]


# ============================================================================
# Due-check tests
# ============================================================================


class TestDueCheck:
    """Due-check logic (no database required)."""

    def setup_method(self):
        self.scheduler = SchedulerService()

    def teardown_method(self):
        self.scheduler.close()

    def test_is_due_past(self):
        now = datetime.now(timezone.utc)
        task = {"is_enabled": True, "next_run_at": now - timedelta(minutes=5)}
        assert self.scheduler._is_due(task, now=now) is True

    def test_is_due_exactly_now(self):
        now = datetime.now(timezone.utc)
        task = {"is_enabled": True, "next_run_at": now}
        assert self.scheduler._is_due(task, now=now) is True

    def test_is_due_future(self):
        now = datetime.now(timezone.utc)
        task = {"is_enabled": True, "next_run_at": now + timedelta(minutes=5)}
        assert self.scheduler._is_due(task, now=now) is False

    def test_is_due_disabled(self):
        now = datetime.now(timezone.utc)
        task = {"is_enabled": False, "next_run_at": now - timedelta(minutes=5)}
        assert self.scheduler._is_due(task, now=now) is False

    def test_is_due_never_run(self):
        now = datetime.now(timezone.utc)
        task = {"is_enabled": True, "next_run_at": None}
        assert self.scheduler._is_due(task, now=now) is True

    def test_is_due_naive_next_run(self):
        """next_run_at without tzinfo should still compare correctly."""
        now = datetime.now(timezone.utc)
        naive_past = (now - timedelta(minutes=5)).replace(tzinfo=None)
        task = {"is_enabled": True, "next_run_at": naive_past}
        assert self.scheduler._is_due(task, now=now) is True


# ============================================================================
# Command handler tests (requires database)
# ============================================================================


@pytest.mark.integration
class TestCommandHandlers:
    """Command handler execution — requires a live database connection."""

    def setup_method(self):
        self.scheduler = SchedulerService()

    def teardown_method(self):
        self.scheduler.close()

    def test_data_update_handler_returns_structure(self):
        result = self.scheduler._handle_data_update({})
        assert isinstance(result, dict)
        assert result["action"] == "data_update"
        assert "symbols_checked" in result
        assert "symbols_updated" in result
        assert "errors" in result

    def test_data_update_handler_with_symbols(self):
        result = self.scheduler._handle_data_update(
            {"symbols": ["000001.SZ", "000002.SZ"]}
        )
        assert result["symbols_checked"] == 2

    def test_signal_generate_handler_returns_structure(self):
        # 2026-08-04 重写后的契约:universe_size/signals_found/signals_saved
        # (旧 stocks_checked/stocks_with_factors 桩契约已废弃)
        result = self.scheduler._handle_signal_generate({})
        assert isinstance(result, dict)
        assert result["action"] == "signal_generate"
        assert "status" in result
        assert "universe_size" in result
        assert "signals_found" in result
        assert "signals_saved" in result
        assert "date" in result

    def test_risk_check_handler_returns_structure(self):
        result = self.scheduler._handle_risk_check({})
        assert isinstance(result, dict)
        assert result["action"] == "risk_check"
        assert "holdings_count" in result

    def test_report_daily_handler_returns_structure(self):
        # 当前简化契约:total_stocks/top_signal_count/timestamp
        result = self.scheduler._handle_report_daily({})
        assert isinstance(result, dict)
        assert result["action"] == "report_daily"
        assert "total_stocks" in result
        assert "top_signal_count" in result
        assert "timestamp" in result

    def test_backtest_run_handler_returns_structure(self):
        result = self.scheduler._handle_backtest_run(
            {"strategy_name": "ma_cross_test"}
        )
        assert isinstance(result, dict)
        assert result["action"] == "backtest_run"
        assert result["strategy_name"] == "ma_cross_test"
        assert "klines_available" in result
        assert "factors_available" in result

    def test_backtest_run_missing_strategy_raises(self):
        with pytest.raises(ValueError, match="strategy_name"):
            self.scheduler._handle_backtest_run({})

    def test_unknown_command_raises(self):
        with pytest.raises(ValueError, match="Unknown scheduler command"):
            self.scheduler._execute_command("nonexistent", {})

    def test_execute_command_dispatch(self):
        """_execute_command dispatches to correct handler."""
        result = self.scheduler._execute_command("risk_check", {})
        assert result["action"] == "risk_check"


# ============================================================================
# SchedulerService close / connection tests
# ============================================================================


class TestSchedulerConnection:
    """Connection lifecycle tests."""

    def test_close_when_not_connected(self):
        scheduler = SchedulerService()
        # Should not raise even if no connection was opened
        scheduler.close()

    def test_close_after_use(self):
        from infrastructure.persistence.database.base_repository import _resolve_db_dsn

        if _resolve_db_dsn() is None:
            pytest.skip("No database URL configured")

        scheduler = SchedulerService()
        # Force connection
        conn = scheduler._get_conn()
        assert conn is not None
        assert not conn.closed
        scheduler.close()
        assert scheduler._conn is None


# ============================================================================
# stop_loop tests
# ============================================================================


class TestStopLoop:
    """Graceful shutdown tests."""

    def test_stop_loop_sets_flag(self):
        scheduler = SchedulerService()
        assert scheduler._running is False
        scheduler.stop_loop()
        assert scheduler._running is False  # was already False, no-op
        scheduler._running = True
        scheduler.stop_loop()
        assert scheduler._running is False
        scheduler.close()
