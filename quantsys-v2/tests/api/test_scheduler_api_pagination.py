"""
Scheduler API pagination tests.
"""
from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask

from adapters.inbound.api.routes import scheduler as scheduler_routes
from adapters.inbound.api.routes.scheduler import scheduler_bp


class FakeScheduler:
    def __init__(self):
        now = datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc)
        self.tasks = [
            {
                "id": i,
                "name": f"task-{i}",
                "is_enabled": True,
                "cron_expression": "0 9 * * 1-5",
                "command": "risk_check",
                "params": {},
                "next_run_at": now + timedelta(days=i),
                "created_at": now,
                "updated_at": now,
            }
            for i in range(1, 6)
        ]
        self.tasks.insert(1, {
            "id": 99,
            "name": "deleted-task",
            "is_enabled": False,
            "cron_expression": "0 9 * * 1-5",
            "command": "risk_check",
            "params": {"_deleted_at": "2026-06-01T00:00:00"},
            "next_run_at": now,
            "created_at": now,
            "updated_at": now,
        })
        self.runs = [
            {
                "id": i,
                "task_id": 1,
                "status": "failed" if i % 2 == 0 else "success",
                "started_at": now - timedelta(minutes=i),
                "completed_at": now - timedelta(minutes=i) + timedelta(seconds=1),
                "duration_ms": 1000,
                "result": {"index": i},
                "error": "boom" if i % 2 == 0 else None,
            }
            for i in range(1, 8)
        ]

    def list_tasks(self, enabled_only=False, limit=None, offset=0):
        tasks = [task for task in self.tasks if not enabled_only or task["is_enabled"]]
        if limit is None:
            return tasks[offset:]
        return tasks[offset:offset + limit]

    def count_tasks(self, enabled_only=False):
        return len([task for task in self.tasks if not enabled_only or task["is_enabled"]])

    def get_task(self, task_id):
        for task in self.tasks:
            if task["id"] == task_id:
                return task
        return None

    def list_runs(self, task_id=None, limit=50, offset=0, statuses=None, date_filter=None):
        runs = self.runs
        if task_id is not None:
            runs = [run for run in runs if run["task_id"] == task_id]
        if statuses:
            runs = [run for run in runs if run["status"] in statuses]
        if date_filter:
            runs = [run for run in runs if run["started_at"].date().isoformat() == date_filter]
        return runs[offset:offset + limit]

    def count_runs(self, task_id=None, statuses=None, date_filter=None):
        return len(self.list_runs(
            task_id=task_id,
            limit=len(self.runs),
            offset=0,
            statuses=statuses,
            date_filter=date_filter,
        ))


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    monkeypatch.setattr(scheduler_routes, "_scheduler", FakeScheduler())
    app.register_blueprint(scheduler_bp)
    return app.test_client()


def test_tasks_endpoint_returns_paginated_visible_tasks(client):
    response = client.get("/api/scheduler/tasks?page=1&pageSize=2")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 5
    assert data["pagination"]["total"] == 5
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["pageSize"] == 2
    assert [task["id"] for task in data["tasks"]] == ["1", "2"]


def test_runs_endpoint_returns_paginated_runs(client):
    response = client.get("/api/scheduler/runs?page=2&pageSize=3")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["total"] == 7
    assert data["pagination"]["total_pages"] == 3
    assert data["page"] == 2
    assert len(data["runs"]) == 3
    assert [run["id"] for run in data["runs"]] == [4, 5, 6]


def test_failed_runs_endpoint_paginates_after_status_filter(client):
    response = client.get("/api/scheduler/runs/failed?page=1&pageSize=2")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 3
    assert data["pagination"]["total"] == 3
    assert [run["status"] for run in data["runs"]] == ["failed", "failed"]
