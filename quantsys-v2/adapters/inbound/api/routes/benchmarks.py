"""
Benchmark routes.
"""
import threading
import uuid

from flask import Blueprint, jsonify, request
from typing import Dict, List, Optional, Any, Tuple, Union

from adapters.inbound.api.shared import acquire_task, handle_api_error, release_task, sanitize_for_json
from application.services.benchmark_service import BenchmarkService
from infrastructure.scheduler import SchedulerService


benchmarks_bp = Blueprint("benchmarks", __name__)

_benchmark_service = BenchmarkService()
_scheduler = SchedulerService()


def _run_benchmark_task(task_id: int, run_token: str):
    scheduler = SchedulerService()
    try:
        scheduler.run_task(task_id)
    finally:
        scheduler.close()
        release_task("benchmark_run")


@benchmarks_bp.route("/api/benchmarks", methods=["GET"])
@handle_api_error
def list_benchmarks():
    """List available benchmark definitions."""
    return jsonify(
        {
            "success": True,
            "benchmarks": sanitize_for_json(_benchmark_service.list_benchmarks()),
        }
    )


@benchmarks_bp.route("/api/benchmarks/results/latest", methods=["GET"])
@handle_api_error
def get_latest_benchmark_results():
    """Return the latest benchmark result artifact summary."""
    return jsonify(
        {
            "success": True,
            "data": sanitize_for_json(_benchmark_service.get_latest_results()),
        }
    )


@benchmarks_bp.route("/api/benchmarks/report", methods=["GET"])
@handle_api_error
def get_latest_benchmark_report():
    """Return the latest benchmark markdown report."""
    report = _benchmark_service.read_report()
    if report is None:
        return jsonify({"success": False, "error": "Benchmark report not found"}), 404
    return jsonify({"success": True, "report": report})


@benchmarks_bp.route("/api/benchmarks/runs", methods=["POST"])
@handle_api_error
def create_benchmark_run():
    """Create and immediately run a scheduler-backed benchmark task."""
    data = request.get_json(silent=True) or {}
    benchmark_ids = data.get("benchmarks")
    timeout_seconds = int(data.get("timeout_seconds", data.get("timeoutSeconds", 600)))
    name = data.get("name") or "benchmark-manual"
    run_token = str(uuid.uuid4())

    if not acquire_task("benchmark_run", run_token):
        return jsonify({"success": False, "error": "Benchmark run already in progress"}), 409

    try:
        existing = _scheduler.get_task_by_name(name)
        params = {
            "benchmarks": benchmark_ids,
            "timeout_seconds": timeout_seconds,
        }

        if existing:
            task_id = existing["id"]
            _scheduler.update_task(
                task_id,
                command="benchmark_run",
                params=params,
                is_enabled=False,
            )
        else:
            task_id = _scheduler.add_task(
                name=name,
                cron_expression="0 0 1 1 *",
                command="benchmark_run",
                params=params,
                description="Manual benchmark run",
            )
            _scheduler.disable_task(task_id)
    except Exception:
        release_task("benchmark_run")
        raise

    thread = threading.Thread(
        target=_run_benchmark_task,
        args=(task_id, run_token),
        daemon=True,
    )
    thread.start()

    return jsonify(
        {
            "success": True,
            "data": {
                "taskId": task_id,
                "taskName": name,
                "status": "queued",
                "runToken": run_token,
            },
        }
    ), 202


@benchmarks_bp.route("/api/benchmarks/runs", methods=["GET"])
@handle_api_error
def list_benchmark_runs():
    """List recent scheduler runs for benchmark tasks."""
    limit = request.args.get("limit", 50, type=int)
    runs = _scheduler.list_runs(limit=max(limit * 3, 150))
    benchmark_runs = []

    for run in runs:
        task_id = run.get("task_id")
        if not task_id:
            continue
        task = _scheduler.get_task(task_id)
        if not task or task.get("command") != "benchmark_run":
            continue
        item = dict(run)
        item["task_name"] = task.get("name")
        benchmark_runs.append(item)
        if len(benchmark_runs) >= limit:
            break

    return jsonify({"success": True, "runs": sanitize_for_json(benchmark_runs)})


@benchmarks_bp.route("/api/benchmarks/runs/<int:run_id>", methods=["GET"])
@handle_api_error
def get_benchmark_run(run_id: int):
    """Return a scheduler run that contains benchmark results."""
    run = _scheduler.get_run(run_id)
    if run is None:
        return jsonify({"success": False, "error": "Benchmark run not found"}), 404
    return jsonify({"success": True, "data": sanitize_for_json(run)})
