import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = PROJECT_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

from api import server  # noqa: E402


class _FactorRouteCursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _FactorRouteConnection:
    def execute(self, query, params=()):
        if "SELECT MAX(date)" in query:
            return _FactorRouteCursor([("20260519",)])
        if "SELECT open, high, low, close" in query:
            return _FactorRouteCursor([(10.0, 11.0, 9.5, 10.8, 1000.0, 10800.0, 1.2)])
        if "SELECT factor_name, factor_value" in query:
            return _FactorRouteCursor([("MA5", 10.6), ("RSI6", 55.0)])
        return _FactorRouteCursor([])

    def close(self):
        pass


class _FactorRouteModel:
    feature_importances_ = [0.1] * 38

    def predict_proba(self, _features):
        return [[0.4, 0.6]]


def test_stock_factors_plural_route_matches_quant_web_contract(monkeypatch):
    monkeypatch.setattr(server, "model", _FactorRouteModel())
    monkeypatch.setattr(server, "get_db", lambda: _FactorRouteConnection())

    client = server.app.test_client()
    response = client.get("/api/stocks/000001/factors")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["symbol"] == "000001"
    assert payload["date"] == "20260519"
    assert payload["prediction"] == "UP"
    assert payload["factors"]["MA5"] == 10.6


def test_platform_status_matches_quant_web_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_project_root", tmp_path)
    monkeypatch.setattr(server, "_jobs_dir", tmp_path / ".pi-invest" / "jobs")
    (tmp_path / ".pi-invest" / "stock-db").mkdir(parents=True)
    (tmp_path / ".pi-invest" / "stock-db" / "stocks.db").write_bytes(b"db")
    (tmp_path / "quant" / ".pi-invest").mkdir(parents=True)
    (tmp_path / "quant" / ".pi-invest" / "signals.json").write_text("[]")
    (tmp_path / "quant" / ".pi-invest" / "daily_report.json").write_text("{}")
    (tmp_path / "quant" / "quantsys" / "ml" / "models").mkdir(parents=True)
    (tmp_path / "quant" / "quantsys" / "ml" / "models" / "training_report_latest.json").write_text("{}")

    client = server.app.test_client()
    response = client.get("/api/platform/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["overall_status"] == "healthy"
    assert {check["name"] for check in payload["data"]["checks"]} == {
        "database",
        "signals",
        "model",
        "daily_report",
    }


def test_jobs_list_matches_quant_web_contract(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    monkeypatch.setattr(server, "_jobs_dir", jobs_dir)
    (jobs_dir / "data_update_abcd.json").write_text(json.dumps({
        "job_id": "data_update_abcd",
        "type": "data_update",
        "status": "completed",
        "params": {"days": 5},
        "created_at": 1000,
        "started_at": 1001,
        "completed_at": 1002,
        "result": {"ok": True},
        "error": None,
    }))

    client = server.app.test_client()
    response = client.get("/api/jobs")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["jobs"][0]["id"] == "data_update_abcd"
    assert payload["jobs"][0]["status"] == "success"
    assert payload["jobs"][0]["createdAt"] == "1970-01-01T00:16:40Z"


def test_job_run_retry_cancel_endpoints_match_quant_web_contract(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    monkeypatch.setattr(server, "_jobs_dir", jobs_dir)

    client = server.app.test_client()
    run_response = client.post("/api/jobs/data_update/run", json={"days": 5})

    assert run_response.status_code == 202
    run_payload = run_response.get_json()
    assert run_payload["success"] is True
    assert run_payload["data"]["type"] == "data_update"
    assert run_payload["data"]["status"] in {"queued", "running", "success", "failed"}

    job_id = run_payload["data"]["id"]
    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")

    assert cancel_response.status_code == 200
    cancel_payload = cancel_response.get_json()
    assert cancel_payload["success"] is True
    assert cancel_payload["data"]["id"] == job_id
    assert cancel_payload["data"]["status"] == "cancelled"

    failed_job_id = server._create_job("risk_check", {})
    server._update_job(failed_job_id, status="failed", completed_at=1002, error="boom")
    retry_response = client.post(f"/api/jobs/{failed_job_id}/retry")

    assert retry_response.status_code == 202
    retry_payload = retry_response.get_json()
    assert retry_payload["success"] is True
    assert retry_payload["data"]["id"] == failed_job_id
    assert retry_payload["data"]["status"] in {"queued", "running", "success", "failed"}


def test_training_reports_and_detail_match_quant_web_contract(tmp_path, monkeypatch):
    models_dir = tmp_path / "quant" / "quantsys" / "ml" / "models"
    models_dir.mkdir(parents=True)
    report = {
        "timestamp": "20260520_101112",
        "model_type": "xgboost",
        "data": {"n_features": 38, "total_samples": 1200, "class_balance": 0.52},
        "cv_results": {"mean_scores": {"accuracy": 0.61, "auc": 0.64}},
        "test_metrics": {"accuracy": 0.6, "auc": 0.63},
        "params": {"days": 90},
    }
    (models_dir / "training_report_20260520_101112.json").write_text(json.dumps(report))
    (models_dir / "training_report_latest.json").write_text(json.dumps(report))
    monkeypatch.setattr(server, "_project_root", tmp_path)

    client = server.app.test_client()
    reports_response = client.get("/api/training/reports")
    detail_response = client.get("/api/training/report/training_report_20260520_101112.json")

    assert reports_response.status_code == 200
    reports_payload = reports_response.get_json()
    assert reports_payload["success"] is True
    assert reports_payload["data"][0]["filename"] == "training_report_20260520_101112.json"
    assert reports_payload["data"][0]["timestamp"] == "20260520_101112"
    assert reports_payload["data"][0]["n_features"] == 38

    assert detail_response.status_code == 200
    detail_payload = detail_response.get_json()
    assert detail_payload["success"] is True
    assert detail_payload["data"]["model_type"] == "xgboost"


def test_training_start_and_status_match_quant_web_contract(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    monkeypatch.setattr(server, "_jobs_dir", jobs_dir)
    monkeypatch.setattr(server, "_run_script_async", lambda job_id, script_name, extra_args=None: None)

    client = server.app.test_client()
    start_response = client.post("/api/training/start", json={
        "days": 90,
        "model": "xgboost",
        "cvSplits": 5,
        "useFeatureEngineering": True,
    })

    assert start_response.status_code == 202
    start_payload = start_response.get_json()
    assert start_payload["success"] is True
    task_id = start_payload["data"]["taskId"]
    assert task_id.startswith("model_train_")

    status_response = client.get(f"/api/training/status/{task_id}")
    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["success"] is True
    assert status_payload["data"]["id"] == task_id
    assert status_payload["data"]["status"] == "running"
    assert status_payload["data"]["params"]["cvSplits"] == 5


def test_scheduler_tasks_and_manual_runs_match_quant_web_contract(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    monkeypatch.setattr(server, "_jobs_dir", jobs_dir)
    monkeypatch.setattr(server, "_complete_job_without_executor", lambda job_id, result=None: None)

    client = server.app.test_client()
    tasks_response = client.get("/api/scheduler/tasks")

    assert tasks_response.status_code == 200
    tasks_payload = tasks_response.get_json()
    assert tasks_payload["success"] is True
    assert isinstance(tasks_payload["tasks"], list)
    assert {task["id"] for task in tasks_payload["tasks"]} >= {"data_update", "model_train"}

    trigger_response = client.post("/api/scheduler/tasks/data_update/trigger")
    assert trigger_response.status_code == 202
    trigger_payload = trigger_response.get_json()
    assert trigger_payload["success"] is True
    assert trigger_payload["data"]["taskId"] == "data_update"
    assert trigger_payload["data"]["triggerType"] == "manual"
    assert trigger_payload["data"]["status"] == "triggered"

    compensate_response = client.post("/api/scheduler/tasks/model_train/compensate")
    assert compensate_response.status_code == 202
    compensate_payload = compensate_response.get_json()
    assert compensate_payload["success"] is True
    assert compensate_payload["data"]["taskId"] == "model_train"
    assert compensate_payload["data"]["triggerType"] == "compensation"


def _strategy_payload(name="测试策略"):
    return {
        "name": name,
        "description": "兼容测试策略",
        "enabled": True,
        "screening": {"filters": {}},
        "entry": {"conditions": [], "logic": "AND"},
        "exit": {"conditions": []},
        "position": {"max_position_pct": 20, "max_stocks": 5},
    }


def test_dashboard_strategy_crud_routes_match_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_project_root", tmp_path)

    client = server.app.test_client()
    create_response = client.post("/api/strategies", json=_strategy_payload())

    assert create_response.status_code == 201
    created = create_response.get_json()["data"]
    strategy_id = created["id"]

    list_response = client.get("/api/strategies")
    assert list_response.status_code == 200
    assert list_response.get_json()["data"][0]["id"] == strategy_id

    disable_response = client.post(f"/api/strategies/{strategy_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.get_json()["data"]["enabled"] is False

    enable_response = client.post(f"/api/strategies/{strategy_id}/enable")
    assert enable_response.status_code == 200
    assert enable_response.get_json()["data"]["enabled"] is True

    update_response = client.put(f"/api/strategies/{strategy_id}", json={"description": "已更新"})
    assert update_response.status_code == 200
    assert update_response.get_json()["data"]["description"] == "已更新"

    get_response = client.get(f"/api/strategies/{strategy_id}")
    assert get_response.status_code == 200
    assert get_response.get_json()["data"]["id"] == strategy_id

    delete_response = client.delete(f"/api/strategies/{strategy_id}")
    assert delete_response.status_code == 200
    assert client.get(f"/api/strategies/{strategy_id}").status_code == 404


def test_dashboard_signal_history_and_scan_routes_match_contract(tmp_path, monkeypatch):
    signals_dir = tmp_path / "quant" / ".pi-invest"
    signals_dir.mkdir(parents=True)
    (signals_dir / "signals.json").write_text(json.dumps({
        "date": "2026-05-20",
        "signals": [{
            "symbol": "000001",
            "name": "平安银行",
            "signal": "BUY",
            "strategy": "均线突破",
            "confidence": 0.8,
            "price": 10.5,
            "timestamp": "2026-05-20T10:00:00",
            "reason": "MA5 > MA20",
        }],
    }))
    monkeypatch.setattr(server, "_project_root", tmp_path)

    client = server.app.test_client()
    history_response = client.get("/api/signals/history?days=7")

    assert history_response.status_code == 200
    history_payload = history_response.get_json()
    assert history_payload["success"] is True
    assert history_payload["data"][0]["signal"] == "buy"
    assert history_payload["data"][0]["strategy_name"] == "均线突破"

    scan_response = client.post("/api/signals/scan", json={
        "strategy_id": "strategy_test",
        "stocks": [{"symbol": "000001", "name": "平安银行"}],
    })
    assert scan_response.status_code == 200
    assert scan_response.get_json()["success"] is True


def test_dashboard_backtest_and_performance_routes_match_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_project_root", tmp_path)
    strategies_dir = tmp_path / ".pi-invest" / "quant" / "strategies"
    strategies_dir.mkdir(parents=True)
    strategy = {**_strategy_payload("回测策略"), "id": "strategy_test", "created_at": "2026-05-20T00:00:00Z"}
    (strategies_dir / "strategy_test.json").write_text(json.dumps(strategy))

    client = server.app.test_client()
    backtest_response = client.post("/api/backtest", json={
        "strategy_id": "strategy_test",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 100000,
    })

    assert backtest_response.status_code == 200
    backtest_payload = backtest_response.get_json()
    assert backtest_payload["success"] is True
    assert "total_return" in backtest_payload["data"]
    assert "daily_equity" in backtest_payload["data"]

    performance_response = client.get("/api/performance/strategy/strategy_test?days=30")
    assert performance_response.status_code == 200
    performance_payload = performance_response.get_json()
    assert performance_payload["success"] is True
    assert performance_payload["data"]["strategy_id"] == "strategy_test"

    compare_response = client.get("/api/performance/compare?strategy_ids=strategy_test&days=30")
    assert compare_response.status_code == 200
    assert compare_response.get_json()["success"] is True


def test_dashboard_chart_routes_match_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_project_root", tmp_path)

    client = server.app.test_client()
    accuracy_response = client.get("/api/charts/accuracy?days=90")
    importance_response = client.get("/api/charts/importance")
    image_response = client.get("/api/charts/image/accuracy_trend")

    assert accuracy_response.status_code == 200
    assert accuracy_response.get_json()["success"] is True
    assert importance_response.status_code == 200
    assert importance_response.get_json()["success"] is True
    assert image_response.status_code == 200
    assert image_response.content_type == "image/png"
