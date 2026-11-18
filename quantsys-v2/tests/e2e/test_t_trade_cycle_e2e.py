from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.t_trade_async import router
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from adapters.outbound.repositories.watch_rule_repository import WatchRule, WatchRuleRepository
from infrastructure.persistence.orm.models import (
    SimulationAccount,
    SimulationCashFlow,
    SimulationEquitySnapshot,
    SimulationOrder,
    SimulationPosition,
    SimulationTrade,
)
from infrastructure.persistence.orm.models.t_trade import TTradeCycle
from qs_trading.application.services.account_trading_service import AccountTradingService


@pytest.fixture
def e2e_env(monkeypatch):
    repo = SimulationORMRepository()
    assert repo.get_account("agent_brain") is None
    assert repo.get_account("user_main_simulation") is None
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "infrastructure" / "persistence" / "migrations" / "20261102_t_trade_cycles.py"
    spec = importlib.util.spec_from_file_location("t_trade_migration_e2e", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.apply_migration(repo.session.connection())
    repo.session.commit()
    repo.create_account("agent_brain", 1_000_000)
    repo.create_account("user_main_simulation", 1_000_000)
    repo.upsert_position("agent_brain", "999998", 300, 12.5, shares_available=300, current_price=12.5)
    repo.upsert_position("user_main_simulation", "999997", 300, 12.5, shares_available=300, current_price=12.5)

    fixed_now = datetime(2026, 11, 2, 10, 0)
    original_init = AccountTradingService.__init__

    def init_fixed(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.now_fn = lambda: fixed_now

    monkeypatch.setattr(AccountTradingService, "__init__", init_fixed)
    monkeypatch.setattr(AccountTradingService, "_record_strategy_performance", lambda *args, **kwargs: None)
    monkeypatch.setattr(AccountTradingService, "_auto_record_decision", lambda *args, **kwargs: None)
    monkeypatch.setattr(AccountTradingService, "_emit_fill_notification", lambda *args, **kwargs: None)
    prices = iter([13.60, 12.18, 13.60, 12.18])
    monkeypatch.setattr(AccountTradingService, "_get_price", lambda self, symbol: next(prices))

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    yield client, repo

    cleanup = SimulationORMRepository()
    cleanup.session.rollback()
    for symbol in ("999998", "999997"):
        cleanup.session.query(TTradeCycle).filter_by(symbol=symbol).delete()
        cleanup.session.query(WatchRule).filter_by(symbol=symbol).delete()
        trade_ids = [row[0] for row in cleanup.session.query(SimulationTrade.id).filter_by(symbol=symbol)]
        if trade_ids:
            cleanup.session.query(SimulationCashFlow).filter(
                SimulationCashFlow.ref_trade_id.in_(trade_ids)
            ).delete(synchronize_session=False)
        cleanup.session.query(SimulationTrade).filter_by(symbol=symbol).delete()
        cleanup.session.query(SimulationOrder).filter_by(symbol=symbol).delete()
        cleanup.session.query(SimulationPosition).filter_by(symbol=symbol).delete()
    for account in ("agent_brain", "user_main_simulation"):
        cleanup.session.query(SimulationEquitySnapshot).filter_by(account_name=account).delete()
        cleanup.session.query(SimulationAccount).filter_by(account_name=account).delete()
    cleanup.session.commit()


def test_auto_and_remind_only_cycles_end_to_end(e2e_env):
    client, repo = e2e_env
    stop_rule = WatchRuleRepository().create_rule(
        symbol="999998",
        conditions=[{"type": "price_break", "params": {"price": 11.0, "direction": "below"}}],
        account="agent_brain", intent="exit_stop", position_state="holding",
    )

    created = client.post("/api/t-trades", json={
        "account": "agent_brain", "symbol": "999998", "upper_price": 13.55,
        "lower_price": 12.19, "shares": 100, "reason": "测试库完整验证反向区间T闭环",
        "invalidation": "止损优先",
    })
    assert created.status_code == 201, created.text
    cycle_id = created.json()["data"]["cycle"]["id"]
    assert created.json()["data"]["rule_sync"]["status"] == "ok"

    sold = client.post(f"/api/t-trades/{cycle_id}/execute", json={})
    assert sold.status_code == 200, sold.text
    assert sold.json()["data"]["cycle"]["status"] == "waiting_buyback"
    assert sold.json()["data"]["rule_sync"]["status"] == "ok"
    assert repo.get_position("agent_brain", "999998").shares_total == 200

    bought = client.post(f"/api/t-trades/{cycle_id}/execute", json={})
    assert bought.status_code == 200, bought.text
    completed = bought.json()["data"]["cycle"]
    assert completed["status"] == "completed"
    assert completed["net_pnl"] == pytest.approx(131.30)
    assert completed["total_fees"] == pytest.approx(10.70)
    assert repo.get_position("agent_brain", "999998").shares_total == 300
    assert WatchRuleRepository().get_by_id(stop_rule.id).enabled is True
    duplicate = client.post(f"/api/t-trades/{cycle_id}/execute", json={})
    assert duplicate.status_code == 409

    reminded = client.post("/api/t-trades", json={
        "account": "user_main_simulation", "symbol": "999997", "upper_price": 13.55,
        "lower_price": 12.19, "shares": 100, "reason": "提醒账户验证不得代下单",
    })
    assert reminded.status_code == 201, reminded.text
    remind_id = reminded.json()["data"]["cycle"]["id"]
    forbidden = client.post(f"/api/t-trades/{remind_id}/execute", json={})
    assert forbidden.status_code == 403

    manual = AccountTradingService(repo=SimulationORMRepository())
    sell = manual.execute_trade(
        "user_main_simulation", "SELL", "999997", shares=100,
        price_limit=13.55, reason="用户人工执行区间T卖出",
    )
    assert client.post(
        f"/api/t-trades/{remind_id}/record-fill", json={"trade_id": sell["trade_id"]}
    ).status_code == 200
    buy = manual.execute_trade(
        "user_main_simulation", "BUY", "999997", shares=100,
        price_limit=12.19, reason="用户人工执行区间T回补",
    )
    response = client.post(
        f"/api/t-trades/{remind_id}/record-fill", json={"trade_id": buy["trade_id"]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["cycle"]["status"] == "completed"
    assert response.json()["data"]["cycle"]["net_pnl"] == pytest.approx(131.30)
