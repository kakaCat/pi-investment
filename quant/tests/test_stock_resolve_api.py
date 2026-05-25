import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = PROJECT_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

from api import server  # noqa: E402


class FakeDatabase:
    def __init__(self):
        self.stocks = {
            "000001": {"symbol": "000001", "name": "平安银行", "market": "A"}
        }
        self.coverage = {
            "000001": {"existing_days": 20, "last_date": "2026-05-20"}
        }
        self.upserted = []

    def get_stock_identity_rows(self, market=None):
        return [{"symbol": row["symbol"], "name": row["name"]} for row in self.stocks.values()]

    def get_market(self, symbol):
        return self.stocks.get(symbol, {}).get("market")

    def get_kline_coverage(self, symbol):
        return self.coverage.get(symbol, {"existing_days": 0, "last_date": None})

    def upsert_stocks(self, stocks):
        self.upserted.extend(stocks)
        for stock in stocks:
            self.stocks[stock["symbol"]] = stock
        return len(stocks)

    def close(self):
        pass


def test_stocks_resolve_adds_external_stock_and_reports_kline_coverage(tmp_path, monkeypatch):
    db = FakeDatabase()

    def fake_lookup(symbol):
        if symbol == "600036":
            return {
                "symbol": symbol,
                "name": "招商银行",
                "sector": "银行",
                "pe_ttm": 6.1,
                "pb": 0.9,
                "market_cap_billion": 9800,
                "listed_date": "2002-04-09",
            }
        return {"error": "not found", "symbol": symbol}

    monkeypatch.setattr(server, "_quant_database", lambda: db)
    monkeypatch.setattr(server, "_lookup_external_stock", fake_lookup)

    client = server.app.test_client()
    response = client.post("/api/stocks/resolve", json={
        "symbols": ["sz000001", "600036", "999999"],
        "requiredDays": 180,
    })

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert [stock["symbol"] for stock in payload["data"]["valid"]] == ["000001", "600036"]
    assert payload["data"]["valid"][0]["source"] == "local"
    assert payload["data"]["valid"][0]["klineCount"] == 20
    assert payload["data"]["valid"][1]["source"] == "external_added"
    assert payload["data"]["invalid"] == [
        {"symbol": "999999", "reason": "外部接口未找到该股票"}
    ]

    assert db.upserted[0]["symbol"] == "600036"
    assert db.upserted[0]["name"] == "招商银行"


def test_web_jobs_pass_symbols_to_scoped_python_scripts(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    calls = []
    monkeypatch.setattr(server, "_jobs_dir", jobs_dir)
    monkeypatch.setattr(
        server,
        "_run_script_async",
        lambda job_id, script_name, extra_args=None: calls.append((job_id, script_name, extra_args)),
    )

    client = server.app.test_client()
    response = client.post("/api/jobs/factor_compute/run", json={"symbols": ["000001", "600036"]})

    assert response.status_code == 202
    assert calls[-1][1:] == ("calculate_factors.py", ["--symbols", "000001,600036"])

    response = client.post("/api/jobs/signal_generate/run", json={"symbols": ["000001", "600036"]})

    assert response.status_code == 202
    assert calls[-1][1:] == ("generate_signals.py", ["--symbols", "000001,600036"])

    response = client.post("/api/jobs/backtest_run/run", json={"symbols": ["000001", "600036"], "days": 120})

    assert response.status_code == 202
    assert calls[-1][1:] == ("weekly_backtest.py", ["--symbols", "000001,600036", "--days", "120"])


def test_data_update_job_uses_explicit_symbols_instead_of_source_universe(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    captured = {}
    monkeypatch.setattr(server, "_jobs_dir", jobs_dir)

    def fake_execute(source, days, force, symbols=None):
        captured.update({"source": source, "days": days, "force": force, "symbols": symbols})
        return {"success": True, "total": len(symbols or [])}

    monkeypatch.setattr(server, "_execute_data_update", fake_execute)

    job_id = server._create_job("data_update", {"symbols": ["000001", "600036"], "days": 180, "force": True})
    server._run_data_update_job(job_id, {"symbols": ["000001", "600036"], "days": 180, "force": True})

    assert captured == {
        "source": "symbols",
        "days": 180,
        "force": True,
        "symbols": ["000001", "600036"],
    }
