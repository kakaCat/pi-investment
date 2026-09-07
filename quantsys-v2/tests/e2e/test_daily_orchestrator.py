import pytest
import threading
from datetime import datetime, time as dtime, timedelta

from tests.e2e.p2_fixtures import get_test_db_conn, cleanup_test_job_runs
from adapters.inbound.fastapi_app.daily_jobs_bootstrap import (
    JobDef, is_due, list_today_runs, trigger_job, start_daily_jobs,
    _mark_running, _mark_done, _get_run, _jobs_loop,
)


TEST_PREFIX = "E2E_SCHEDULER"


@pytest.fixture(scope="module")
def db_conn():
    conn = get_test_db_conn()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def cleanup(db_conn):
    cleanup_test_job_runs(db_conn, TEST_PREFIX)
    yield
    cleanup_test_job_runs(db_conn, TEST_PREFIX)


class TestJobScheduling:

    def test_is_due_returns_true_when_past_time(self):
        job = JobDef(
            job_id="test_job", run_at=dtime(10, 0),
            weekdays=(0, 1, 2, 3, 4), handler=lambda: {},
            description="test")
        now = datetime(2026, 9, 3, 10, 30)
        assert is_due(job, now, None) is True

    def test_is_due_returns_false_before_time(self):
        job = JobDef(
            job_id="test_job", run_at=dtime(10, 0),
            weekdays=(0, 1, 2, 3, 4), handler=lambda: {},
            description="test")
        now = datetime(2026, 9, 3, 9, 30)
        assert is_due(job, now, None) is False

    def test_is_due_returns_false_after_success(self):
        job = JobDef(
            job_id="test_job", run_at=dtime(10, 0),
            weekdays=(0, 1, 2, 3, 4), handler=lambda: {},
            description="test")
        now = datetime(2026, 9, 3, 10, 30)
        last_run = {'status': 'success', 'started_at': datetime.now()}
        assert is_due(job, now, last_run) is False

    def test_is_due_weekend_returns_false(self):
        job = JobDef(
            job_id="test_job", run_at=dtime(10, 0),
            weekdays=(0, 1, 2, 3, 4), handler=lambda: {},
            description="test")
        now = datetime(2026, 9, 6, 10, 30)
        assert is_due(job, now, None) is False

    def test_is_due_failed_retry_after_cooldown(self):
        job = JobDef(
            job_id="test_job", run_at=dtime(10, 0),
            weekdays=(0, 1, 2, 3, 4), handler=lambda: {},
            description="test")
        now = datetime(2026, 9, 3, 13, 0)
        last_run = {'status': 'failed', 'started_at': datetime(2026, 9, 3, 10, 0)}
        assert is_due(job, now, last_run) is True


class TestJobExecutionTracking:

    def test_mark_running_updates_db(self):
        job_id = f"{TEST_PREFIX}_RUNNING"
        today = datetime.now().strftime('%Y-%m-%d')
        _mark_running(job_id, today)
        result = _get_run(job_id, today)
        assert result is not None
        assert result['status'] == 'running'

    def test_mark_done_updates_db(self):
        job_id = f"{TEST_PREFIX}_DONE"
        today = datetime.now().strftime('%Y-%m-%d')
        _mark_running(job_id, today)
        _mark_done(job_id, today, 'success', result={'count': 10})
        result = _get_run(job_id, today)
        assert result is not None
        assert result['status'] == 'success'

    def test_mark_failed_records_error(self):
        job_id = f"{TEST_PREFIX}_FAILED"
        today = datetime.now().strftime('%Y-%m-%d')
        _mark_running(job_id, today)
        _mark_done(job_id, today, 'failed', error="Test error")
        result = _get_run(job_id, today)
        assert result is not None
        assert result['status'] == 'failed'


class TestJobIdempotency:

    def test_same_job_overwrites_on_rerun(self):
        job_id = f"{TEST_PREFIX}_IDEMPOTENT"
        today = datetime.now().strftime('%Y-%m-%d')
        _mark_running(job_id, today)
        _mark_running(job_id, today)
        result = _get_run(job_id, today)
        assert result['status'] == 'running'


class TestJobListQuery:

    def test_list_today_runs_returns_list(self):
        runs = list_today_runs()
        assert isinstance(runs, list)
        for run in runs:
            assert 'job_id' in run
            assert 'status' in run
            assert 'scheduled_at' in run

    def test_list_runs_shows_all_jobs(self):
        from adapters.inbound.fastapi_app.daily_jobs_bootstrap import JOBS
        runs = list_today_runs()
        assert len(runs) == len(JOBS)


class TestManualTrigger:

    def test_trigger_unknown_job_returns_error(self):
        result = trigger_job("unknown_job_id")
        assert result['success'] is False
        assert 'error' in result
        assert '未知任务' in result['error']

    def test_trigger_known_job_returns_success(self):
        from adapters.inbound.fastapi_app.daily_jobs_bootstrap import JOBS
        if len(JOBS) > 0:
            job_id = JOBS[0].job_id
            result = trigger_job(job_id, force=True)
            assert result['success'] is True


class TestSchedulerLifecycle:

    def test_start_daily_jobs_skip_returns_none(self):
        stop_event = start_daily_jobs(skip=True)
        assert stop_event is None

    def test_jobs_loop_exits_on_stop(self):
        stop_event = threading.Event()
        stop_event.set()
        _jobs_loop(stop_event)
