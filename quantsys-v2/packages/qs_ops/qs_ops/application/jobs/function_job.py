"""Callable-backed Job adapter for migrating legacy in-process schedulers.

The adapter contains no business logic. It only:
- invokes one existing callable in the APScheduler worker thread;
- converts its return value to the common ``JobResult`` contract;
- detects inner failure markers with the same authority used by scheduler runs;
- optionally emits the legacy start/success/failure notifications.

Keeping this in ``qs_ops.application.jobs`` lets the composition root inject
adapter-layer handlers without making the application package import inbound
code.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Optional

from qs_ops.application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


class FunctionJob(Job):
    """A Job whose implementation is an injected synchronous callable."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        handler: Callable[..., Any],
        timeout_seconds: int = 3600,
        accept_params: bool = False,
        on_start: Optional[Callable[[], None]] = None,
        on_success: Optional[Callable[[Any, float], None]] = None,
        on_failure: Optional[Callable[[str, Any, float], None]] = None,
    ) -> None:
        self._name = name
        self._description = description
        self._handler = handler
        self._timeout_seconds = timeout_seconds
        self._accept_params = accept_params
        self._on_start = on_start
        self._on_success = on_success
        self._on_failure = on_failure

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def timeout_seconds(self) -> int:
        return self._timeout_seconds

    def _invoke(self, callback, *args) -> None:
        if callback is None:
            return
        try:
            callback(*args)
        except Exception:  # noqa: BLE001 - notifications must never change job outcome
            logger.exception("function_job_callback_failed job=%s", self._name)

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        self._invoke(self._on_start)
        started = time.monotonic()
        try:
            result = self._handler(params or {}) if self._accept_params else self._handler()
        except Exception as exc:  # noqa: BLE001 - handlers use both raise and return conventions
            elapsed = time.monotonic() - started
            error = f"{type(exc).__name__}: {exc}"
            logger.exception("function_job_failed job=%s", self._name)
            self._invoke(self._on_failure, error, None, elapsed)
            return JobResult(
                success=False,
                action=self._name,
                error=error,
                details={"exception": error},
            )

        elapsed = time.monotonic() - started
        details = result if isinstance(result, dict) else {"result": result}

        # Single failure classifier shared with the scheduler run ledger.
        from infrastructure.scheduler.job_executor import find_result_failure

        error = find_result_failure(result)
        if error:
            self._invoke(self._on_failure, error, result, elapsed)
            return JobResult(
                success=False,
                action=self._name,
                error=error,
                details=details,
            )

        self._invoke(self._on_success, result, elapsed)
        return JobResult(
            success=True,
            action=self._name,
            message=f"{self._name} completed",
            details=details,
        )
