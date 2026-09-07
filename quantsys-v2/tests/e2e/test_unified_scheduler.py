"""P2.3 e2e tests for UnifiedScheduler."""
import pytest
from pathlib import Path
from infrastructure.scheduler.unified_scheduler import (
    UnifiedScheduler,
    JobConfig,
    JobStatus,
    RetryConfig,
    AlertConfig,
)


@pytest.fixture
def config_path():
    return str(Path(__file__).resolve().parents[2] / "config" / "scheduler_jobs.yml")


@pytest.fixture
def scheduler(config_path):
    s = UnifiedScheduler(config_path)
    s.start()
    yield s
    s.stop()


@pytest.fixture
def empty_scheduler(tmp_path):
    config_file = tmp_path / "empty_jobs.yml"
    config_file.write_text("version: '1.0'\njobs: []\n")
    s = UnifiedScheduler(str(config_file))
    s.start()
    yield s
    s.stop()


# ── Config Loading ──────────────────────────────────────────

class TestConfigLoading:
    def test_loads_jobs_from_yaml(self, scheduler):
        assert len(scheduler.jobs) == 4
        assert "freshness_guard" in scheduler.jobs
        assert "evening_pipeline" in scheduler.jobs
        assert "chip_distribution" in scheduler.jobs
        assert "financial_statements" in scheduler.jobs

    def test_empty_config(self, empty_scheduler):
        assert len(empty_scheduler.jobs) == 0

    def test_missing_config(self, tmp_path):
        s = UnifiedScheduler(str(tmp_path / "nonexistent.yml"))
        assert len(s.jobs) == 0

    def test_job_config_fields(self, scheduler):
        job = scheduler.jobs["evening_pipeline"]
        assert job.id == "evening_pipeline"
        assert job.name == "晚间数据管线"
        assert job.enabled is True
        assert job.timeout == 7200
        assert job.schedule["type"] == "cron"
        assert job.schedule["hour"] == 20
        assert job.schedule["minute"] == 30
        assert job.schedule["day_of_week"] == "0-4"

    def test_job_status_initial(self, scheduler):
        for job_id in scheduler.jobs:
            assert scheduler.job_states[job_id] == JobStatus.IDLE

    def test_disabled_job_status(self, tmp_path):
        config_file = tmp_path / "disabled.yml"
        config_file.write_text(
            "version: '1.0'\n"
            "jobs:\n"
            "  - id: disabled_job\n"
            "    name: Disabled\n"
            "    enabled: false\n"
            "    executor:\n"
            "      type: callable\n"
            "      callable: json.dumps\n"
            "    timeout: 10\n"
        )
        s = UnifiedScheduler(str(config_file))
        assert s.job_states["disabled_job"] == JobStatus.DISABLED

    def test_retry_config(self, scheduler):
        job = scheduler.jobs["freshness_guard"]
        assert job.retry is None or isinstance(job.retry, RetryConfig)

    def test_alert_config(self, scheduler):
        job = scheduler.jobs["freshness_guard"]
        assert job.alerts is not None
        assert job.alerts.on_failure is True
        assert "feishu" in job.alerts.channels


# ── Job CRUD ────────────────────────────────────────────────

class TestJobCRUD:
    def test_list_jobs(self, scheduler):
        jobs = scheduler.list_jobs()
        assert len(jobs) == 4
        ids = {j["id"] for j in jobs}
        assert ids == {"freshness_guard", "evening_pipeline", "chip_distribution", "financial_statements"}

    def test_get_job_status(self, scheduler):
        assert scheduler.get_job_status("evening_pipeline") == "idle"
        assert scheduler.get_job_status("nonexistent") is None

    def test_register_job(self, empty_scheduler):
        job = JobConfig(
            id="test_job",
            name="Test Job",
            enabled=True,
            executor={"type": "callable", "callable": "json.dumps"},
            timeout=60,
        )
        empty_scheduler.register_job(job)
        assert "test_job" in empty_scheduler.jobs
        assert empty_scheduler.job_states["test_job"] == JobStatus.IDLE

    def test_reload_config(self, scheduler):
        original_count = len(scheduler.jobs)
        scheduler.reload_config()
        assert len(scheduler.jobs) == original_count


# ── Job Execution ───────────────────────────────────────────

class TestJobExecution:
    def test_trigger_nonexistent_job(self, scheduler):
        result = scheduler.run_job("nonexistent")
        assert result.status == "failed"
        assert "not found" in result.error.lower()

    def test_trigger_disabled_job(self, scheduler):
        job = JobConfig(
            id="disabled_test",
            name="Disabled",
            enabled=False,
            executor={"type": "callable", "callable": "json.dumps"},
        )
        scheduler.register_job(job)
        result = scheduler.run_job("disabled_test")
        assert result.status == "skipped"
        assert "disabled" in result.error.lower()

    def test_trigger_callable_job(self, tmp_path):
        config_file = tmp_path / "callable.yml"
        config_file.write_text(
            "version: '1.0'\n"
            "jobs:\n"
            "  - id: callable_test\n"
            "    name: Callable Test\n"
            "    enabled: true\n"
            "    executor:\n"
            "      type: callable\n"
            "      callable: json.dumps\n"
            "    timeout: 10\n"
        )
        s = UnifiedScheduler(str(config_file))
        s.start()
        result = s.run_job("callable_test", obj={"test": True})
        assert result.status == "success"
        assert result.result is not None

    def test_dependency_not_satisfied(self, tmp_path):
        config_file = tmp_path / "deps.yml"
        config_file.write_text(
            "version: '1.0'\n"
            "jobs:\n"
            "  - id: dep_a\n"
            "    name: Dep A\n"
            "    enabled: true\n"
            "    executor:\n"
            "      type: callable\n"
            "      callable: json.dumps\n"
            "    timeout: 10\n"
            "  - id: dep_b\n"
            "    name: Dep B\n"
            "    enabled: true\n"
            "    dependencies: [dep_a]\n"
            "    executor:\n"
            "      type: callable\n"
            "      callable: json.dumps\n"
            "    timeout: 10\n"
        )
        s = UnifiedScheduler(str(config_file))
        s.start()
        result = s.run_job("dep_b")
        assert result.status == "skipped"
        assert "dependency" in result.error.lower()


# ── History ─────────────────────────────────────────────────

class TestHistory:
    def test_empty_history(self, scheduler):
        history = scheduler.get_history()
        assert history == []

    def test_history_after_trigger(self, tmp_path):
        config_file = tmp_path / "hist.yml"
        config_file.write_text(
            "version: '1.0'\n"
            "jobs:\n"
            "  - id: hist_test\n"
            "    name: Hist Test\n"
            "    enabled: true\n"
            "    executor:\n"
            "      type: callable\n"
            "      callable: os.getpid\n"
            "    timeout: 10\n"
        )
        s = UnifiedScheduler(str(config_file))
        s.start()
        s.run_job("hist_test")
        history = s.get_history()
        assert len(history) == 1
        assert history[0]["job_id"] == "hist_test"
        assert history[0]["status"] == "success"

    def test_history_filter_by_job(self, tmp_path):
        config_file = tmp_path / "filter.yml"
        config_file.write_text(
            "version: '1.0'\n"
            "jobs:\n"
            "  - id: filter_a\n"
            "    name: Filter A\n"
            "    enabled: true\n"
            "    executor:\n"
            "      type: callable\n"
            "      callable: json.dumps\n"
            "    timeout: 10\n"
            "  - id: filter_b\n"
            "    name: Filter B\n"
            "    enabled: true\n"
            "    executor:\n"
            "      type: callable\n"
            "      callable: json.dumps\n"
            "    timeout: 10\n"
        )
        s = UnifiedScheduler(str(config_file))
        s.start()
        s.run_job("filter_a")
        s.run_job("filter_b")
        s.run_job("filter_a")
        history_a = s.get_history(job_id="filter_a")
        assert len(history_a) == 2
        assert all(h["job_id"] == "filter_a" for h in history_a)

    def test_history_limit(self, tmp_path):
        config_file = tmp_path / "limit.yml"
        config_file.write_text(
            "version: '1.0'\n"
            "jobs:\n"
            "  - id: limit_test\n"
            "    name: Limit Test\n"
            "    enabled: true\n"
            "    executor:\n"
            "      type: callable\n"
            "      callable: json.dumps\n"
            "    timeout: 10\n"
        )
        s = UnifiedScheduler(str(config_file))
        s.start()
        for _ in range(5):
            s.run_job("limit_test")
        history = s.get_history(limit=3)
        assert len(history) == 3


# ── Health ──────────────────────────────────────────────────

class TestHealth:
    def test_is_running(self, scheduler):
        assert scheduler.is_running is True

    def test_stop(self, config_path):
        s = UnifiedScheduler(config_path)
        s.start()
        assert s.is_running is True
        s.stop()
        assert s.is_running is False

    def test_singleton(self, config_path):
        from infrastructure.scheduler.unified_scheduler import get_scheduler
        s1 = get_scheduler(config_path)
        s2 = get_scheduler(config_path)
        assert s1 is s2
