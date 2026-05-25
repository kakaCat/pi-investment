import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = PROJECT_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

os.environ["QUANT_DB_PROVIDER"] = "sqlite"

from api import server  # noqa: E402


def test_pipeline_run_api_creates_persisted_run_and_lists_newest_first(tmp_path, monkeypatch):
    runs_dir = tmp_path / "pipeline-runs"
    jobs_dir = tmp_path / "jobs"
    runs_dir.mkdir()
    jobs_dir.mkdir()
    started_jobs = []

    monkeypatch.setattr(server, "_pipeline_runs_dir", runs_dir)
    monkeypatch.setattr(server, "_jobs_dir", jobs_dir)
    monkeypatch.setattr(
        server.threading,
        "Thread",
        lambda target, daemon=True: type("InlineThread", (), {"start": lambda self: target()})(),
    )
    monkeypatch.setattr(
        server,
        "_start_job_for_type",
        lambda job_type, params: started_jobs.append((job_type, params)) or f"{job_type}_job",
    )
    monkeypatch.setattr(
        server,
        "_get_job",
        lambda job_id: {
            "job_id": job_id,
            "type": job_id.removesuffix("_job"),
            "status": "completed",
            "created_at": 1,
            "started_at": 1,
            "completed_at": 2,
            "params": {},
            "logs": [],
        },
    )
    monkeypatch.setattr(
        server,
        "_resolve_symbols_for_pipeline",
        lambda symbols, required_days: {
            "stocks": [{"symbol": symbol, "source": "local"} for symbol in symbols],
            "valid": [{"symbol": symbol, "source": "local"} for symbol in symbols],
            "invalid": [],
        },
    )

    client = server.app.test_client()
    first = client.post("/api/pipeline/runs", json={"symbols": ["000001"], "days": 180})
    second = client.post("/api/pipeline/runs", json={"symbols": ["600036"], "days": 180})

    assert first.status_code == 202
    assert second.status_code == 202

    first_run = first.get_json()["data"]
    second_run = second.get_json()["data"]
    assert first_run["status"] in {"queued", "running", "success"}
    assert first_run["symbols"] == ["000001"]
    assert first_run["steps"][0]["key"] == "resolve"
    assert started_jobs

    list_response = client.get("/api/pipeline/runs?page=1&pageSize=1")
    assert list_response.status_code == 200
    list_payload = list_response.get_json()
    assert list_payload["success"] is True
    assert list_payload["data"]["total"] == 2
    assert list_payload["data"]["items"][0]["id"] == second_run["id"]

    detail_response = client.get(f"/api/pipeline/runs/{first_run['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.get_json()["data"]
    assert detail["id"] == first_run["id"]
    assert detail["steps"]
