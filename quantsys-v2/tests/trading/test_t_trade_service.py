from datetime import datetime
from types import SimpleNamespace

import pytest

from infrastructure.persistence.orm.models.t_trade import TTradeCycle
from qs_trading.application.services.t_trade_service import TTradeService
from qs_trading.domain.trading.exceptions import TradingError


class FakeRepo:
    def __init__(self):
        self.cycles = {}
        self.trades = {}
        self.commits = 0

    def find_active(self, account, symbol, for_update=False):
        return next((c for c in self.cycles.values() if c.account == account
                     and c.symbol == symbol and c.status in ("waiting_sell", "waiting_buyback")), None)

    def create(self, values):
        cycle = TTradeCycle(**values)
        cycle.id = len(self.cycles) + 1
        cycle.created_at = datetime(2026, 11, 2, 10, 0)
        cycle.updated_at = cycle.created_at
        self.cycles[cycle.id] = cycle
        return cycle

    def get(self, cycle_id, for_update=False):
        return self.cycles.get(int(cycle_id))

    def get_trade(self, trade_id):
        return self.trades.get(int(trade_id))

    def trade_in_use(self, trade_id):
        return any(c.sell_trade_id == trade_id or c.buyback_trade_id == trade_id
                   for c in self.cycles.values())

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class FakeSimulationRepo:
    def __init__(self, available=300):
        self.available = available

    def get_position(self, account, symbol):
        return SimpleNamespace(shares_available=self.available)


def create(service, account="agent_brain", **overrides):
    values = dict(
        account=account, symbol="002007", upper_price=13.55, lower_price=12.19,
        shares=100, reason="明确区间内小仓位验证反向做T闭环",
    )
    values.update(overrides)
    return service.create_cycle(**values)


def trade(trade_id, action, price, account="user_main_simulation"):
    return SimpleNamespace(
        id=trade_id, account_name=account, symbol="002007", action=action,
        shares=100, filled_price=price, commission=5, stamp_duty=0.68 if action == "SELL" else 0,
        transfer_fee=0.01, trade_time=datetime(2026, 11, 2, 10, 5),
    )


def test_create_derives_mode_and_checks_active_cycle():
    repo = FakeRepo()
    service = TTradeService(repo=repo, simulation_repo=FakeSimulationRepo())
    cycle = create(service)
    assert cycle.mode == "auto_sim"
    assert cycle.expected_net_pnl > 0
    with pytest.raises(TradingError) as exc:
        create(service)
    assert exc.value.status_code == 409


def test_remind_only_account_cannot_execute():
    repo = FakeRepo()
    service = TTradeService(repo=repo, simulation_repo=FakeSimulationRepo())
    cycle = create(service, account="user_main_simulation")
    with pytest.raises(TradingError) as exc:
        service.execute(cycle.id)
    assert exc.value.status_code == 403


def test_auto_execute_delegates_to_real_trading_service_with_cycle_context():
    repo = FakeRepo()
    trading = SimpleNamespace(execute_trade=lambda **kwargs: kwargs)
    service = TTradeService(
        repo=repo, simulation_repo=FakeSimulationRepo(), trading_service=trading,
    )
    cycle = create(service)
    result = service.execute(cycle.id, price=13.60)
    call = result["trade"]
    assert call["action"] == "SELL"
    assert call["price_limit"] == 13.55
    assert call["t_trade_id"] == cycle.id
    assert call["t_trade_repo"] is repo


def test_remind_cycle_records_two_real_fills_and_actual_net_pnl():
    repo = FakeRepo()
    service = TTradeService(repo=repo, simulation_repo=FakeSimulationRepo())
    cycle = create(service, account="user_main_simulation")
    repo.trades[1] = trade(1, "SELL", 13.55)
    service.record_fill(cycle.id, 1)
    assert cycle.status == "waiting_buyback"
    repo.trades[2] = trade(2, "BUY", 12.19)
    service.record_fill(cycle.id, 2)
    assert cycle.status == "completed"
    assert float(cycle.net_pnl) == pytest.approx(125.30)
    assert float(cycle.total_fees) == pytest.approx(10.70)


def test_record_fill_rejects_fake_mismatched_or_reused_trade():
    repo = FakeRepo()
    service = TTradeService(repo=repo, simulation_repo=FakeSimulationRepo())
    cycle = create(service, account="user_main_simulation")
    with pytest.raises(TradingError) as exc:
        service.record_fill(cycle.id, None)
    assert exc.value.status_code == 400
    with pytest.raises(TradingError) as exc:
        service.record_fill(cycle.id, 999)
    assert exc.value.status_code == 404
    repo.trades[1] = trade(1, "BUY", 12.19)
    with pytest.raises(TradingError):
        service.record_fill(cycle.id, 1)
    repo.trades[1] = trade(1, "SELL", 13.55)
    service.record_fill(cycle.id, 1)
    other = create(service, account="user_main_simulation", symbol="600519")
    repo.trades[1].symbol = "600519"
    with pytest.raises(TradingError):
        service.record_fill(other.id, 1)


def test_cancel_is_terminal_and_audited():
    repo = FakeRepo()
    service = TTradeService(repo=repo, simulation_repo=FakeSimulationRepo())
    cycle = create(service)
    service.cancel(cycle.id, "触发止损")
    assert cycle.status == "cancelled"
    assert cycle.cancel_reason == "触发止损"
    with pytest.raises(TradingError):
        service.execute(cycle.id)
