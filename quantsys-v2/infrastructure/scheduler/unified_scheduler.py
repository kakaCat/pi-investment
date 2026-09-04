"""
Unified Scheduler — YAML-config-driven task orchestration.

Consolidates the three-layer scheduling architecture:
  Layer 1: FastAPI lifespan (startup/shutdown)
  Layer 2: daily_jobs_bootstrap.py (APScheduler registration)
  Layer 3: DailyOrchestrator (7-phase state machine)

Into a single declarative config + execution engine.
"""
from __future__ import annotations

import importlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "scheduler_jobs.yml"


class JobStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DISABLED = "disabled"


@dataclass
class RetryConfig:
    max_attempts: int = 3
    backoff: str = "exponential"

    @classmethod
    def from_dict(cls, d: Optional[Dict]) -> Optional["RetryConfig"]:
        if not d:
            return None
        return cls(max_attempts=d.get("max_attempts", 3), backoff=d.get("backoff", "exponential"))


@dataclass
class AlertConfig:
    on_failure: bool = True
    channels: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Optional[Dict]) -> Optional["AlertConfig"]:
        if not d:
            return None
        return cls(on_failure=d.get("on_failure", True), channels=d.get("channels", []))


@dataclass
class JobConfig:
    id: str
    name: str
    enabled: bool = True
    schedule: Dict[str, Any] = field(default_factory=dict)
    executor: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 3600
    retry: Optional[RetryConfig] = None
    dependencies: Optional[List[str]] = None
    alerts: Optional[AlertConfig] = None

    @classmethod
    def from_dict(cls, d: Dict) -> "JobConfig":
        return cls(
            id=d["id"],
            name=d.get("name", d["id"]),
            enabled=d.get("enabled", True),
            schedule=d.get("schedule", {}),
            executor=d.get("executor", {}),
            timeout=d.get("timeout", 3600),
            retry=RetryConfig.from_dict(d.get("retry")),
            dependencies=d.get("dependencies"),
            alerts=AlertConfig.from_dict(d.get("alerts")),
        )


@dataclass
class JobRunResult:
    job_id: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class UnifiedScheduler:
    """YAML-config-driven unified scheduler.

    Usage::

        scheduler = UnifiedScheduler()
        scheduler.start()
        # ... later
        scheduler.run_job("kline_update")
        scheduler.stop()
    """

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        self.jobs: Dict[str, JobConfig] = {}
        self.job_states: Dict[str, JobStatus] = {}
        self.job_history: List[JobRunResult] = []
        self._running = False
        self._load_config()

    def _load_config(self):
        import yaml
        if not self._config_path.exists():
            logger.warning("Config not found: %s — starting with empty job registry", self._config_path)
            return
        with open(self._config_path) as f:
            config = yaml.safe_load(f) or {}
        for job_data in config.get("jobs", []):
            job = JobConfig.from_dict(job_data)
            self.jobs[job.id] = job
            self.job_states[job.id] = JobStatus.DISABLED if not job.enabled else JobStatus.IDLE
        logger.info("Loaded %d jobs from %s", len(self.jobs), self._config_path)

    def reload_config(self):
        self._load_config()

    def register_job(self, job: JobConfig):
        self.jobs[job.id] = job
        self.job_states[job.id] = JobStatus.DISABLED if not job.enabled else JobStatus.IDLE

    def get_job_status(self, job_id: str) -> Optional[str]:
        state = self.job_states.get(job_id, None)
        return state.value if state else None

    def list_jobs(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": job.id,
                "name": job.name,
                "enabled": job.enabled,
                "status": self.job_states.get(job.id, JobStatus.IDLE).value,
                "schedule": job.schedule,
                "timeout": job.timeout,
                "dependencies": job.dependencies or [],
            }
            for job in self.jobs.values()
        ]

    def run_job(self, job_id: str, **kwargs) -> JobRunResult:
        job = self.jobs.get(job_id)
        if job is None:
            return JobRunResult(job_id=job_id, status="failed", error=f"Job not found: {job_id}")

        if not job.enabled:
            return JobRunResult(job_id=job_id, status="skipped", error="Job is disabled")

        if job.dependencies:
            for dep_id in job.dependencies:
                dep_state = self.job_states.get(dep_id)
                if dep_state != JobStatus.SUCCESS:
                    return JobRunResult(
                        job_id=job_id, status="skipped",
                        error=f"Dependency '{dep_id}' not satisfied (state={dep_state.value if dep_state else 'unknown'})",
                    )

        self.job_states[job_id] = JobStatus.RUNNING
        started = datetime.now(timezone.utc)
        result = JobRunResult(job_id=job_id, status="running", started_at=started)

        try:
            exec_result = self._execute_job(job, **kwargs)
            self.job_states[job_id] = JobStatus.SUCCESS
            finished = datetime.now(timezone.utc)
            result.status = "success"
            result.finished_at = finished
            result.result = exec_result
            logger.info("Job %s completed in %.1fs", job_id, (finished - started).total_seconds())
        except TimeoutError:
            self.job_states[job_id] = JobStatus.TIMEOUT
            finished = datetime.now(timezone.utc)
            result.status = "timeout"
            result.finished_at = finished
            result.error = f"Timed out after {job.timeout}s"
            logger.error("Job %s timed out after %ds", job_id, job.timeout)
        except Exception as exc:
            self.job_states[job_id] = JobStatus.FAILED
            finished = datetime.now(timezone.utc)
            result.status = "failed"
            result.finished_at = finished
            result.error = f"{type(exc).__name__}: {exc}"
            logger.error("Job %s failed: %s", job_id, exc)

        self.job_history.append(result)
        return result

    def _execute_job(self, job: JobConfig, **kwargs) -> Dict[str, Any]:
        executor = job.executor
        exec_type = executor.get("type", "service")

        if exec_type == "service":
            return self._execute_service(job, executor, **kwargs)
        elif exec_type == "composite":
            return self._execute_composite(job, executor, **kwargs)
        elif exec_type == "callable":
            return self._execute_callable(job, executor, **kwargs)
        else:
            raise ValueError(f"Unknown executor type: {exec_type}")

    def _execute_service(self, job: JobConfig, executor: Dict, **kwargs) -> Dict[str, Any]:
        module_path = executor.get("module")
        class_name = executor.get("class")
        method_name = executor.get("method", "run")

        if not module_path or not class_name:
            raise ValueError(f"Job {job.id} executor missing 'module' or 'class'")

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        instance = cls()
        method = getattr(instance, method_name)

        start_time = time.monotonic()
        raw = method(**kwargs)
        elapsed = time.monotonic() - start_time
        if elapsed > job.timeout:
            raise TimeoutError(f"Exceeded {job.timeout}s")

        if isinstance(raw, dict):
            return raw
        return {"result": raw, "elapsed_seconds": round(elapsed, 2)}

    def _execute_composite(self, job: JobConfig, executor: Dict, **kwargs) -> Dict[str, Any]:
        stages = executor.get("stages", [])
        results = []
        for stage in stages:
            module_path = stage.get("service")
            method_name = stage.get("method")
            if not module_path or not method_name:
                continue
            module = importlib.import_module(module_path)
            parts = module_path.rsplit(".", 1)
            if len(parts) == 2:
                cls = getattr(module, parts[1])
                instance = cls()
            else:
                instance = module
            method = getattr(instance, method_name)
            stage_result = method(**kwargs)
            results.append({"stage": f"{module_path}.{method_name}", "result": stage_result})
        return {"stages": results}

    def _execute_callable(self, job: JobConfig, executor: Dict, **kwargs) -> Dict[str, Any]:
        callable_path = executor.get("callable")
        if not callable_path:
            raise ValueError(f"Job {job.id} callable executor missing 'callable'")
        module_path, func_name = callable_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        try:
            raw = func(**kwargs)
        except TypeError as exc:
            if "missing" in str(exc) and "required positional argument" in str(exc):
                raw = func()
            else:
                raise
        return raw if isinstance(raw, dict) else {"result": raw}

    def get_history(self, job_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        items = self.job_history
        if job_id:
            items = [h for h in items if h.job_id == job_id]
        items = items[-limit:]
        return [
            {
                "job_id": h.job_id,
                "status": h.status,
                "started_at": h.started_at.isoformat() if h.started_at else None,
                "finished_at": h.finished_at.isoformat() if h.finished_at else None,
                "result": h.result,
                "error": h.error,
            }
            for h in items
        ]

    def start(self):
        self._running = True
        logger.info("UnifiedScheduler started with %d jobs", len(self.jobs))

    def stop(self):
        self._running = False
        logger.info("UnifiedScheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running


_scheduler_instance: Optional[UnifiedScheduler] = None


def get_scheduler(config_path: Optional[str] = None) -> UnifiedScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = UnifiedScheduler(config_path)
    return _scheduler_instance
