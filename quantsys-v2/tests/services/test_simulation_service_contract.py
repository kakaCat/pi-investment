"""SimulationService 数据契约测试（A线：days_held / last_updated / price_stale）

不依赖数据库：通过 __new__ 跳过 __init__，repo 用 Mock 替换。
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from application.services.simulation_service import SimulationService


def _make_service():
    svc = SimulationService.__new__(SimulationService)
    svc.logger = logging.getLogger("test.simulation_service")
    svc.repo = MagicMock()
    return svc


def _make_position(created_days_ago=3):
    p = MagicMock()
    p.symbol = "600519"
    p.shares_total = 100
    p.shares_available = 100
    p.avg_cost = Decimal("1500.00")
    p.current_price = Decimal("1520.00")
    p.market_value = Decimal("152000.00")
    p.profit_total = Decimal("2000.00")
    p.profit_total_rate = Decimal("0.0133")
    p.profit_today = Decimal("500.00")
    p.created_at = datetime.now() - timedelta(days=created_days_ago)
    p.updated_at = datetime.now()
    return p


class TestPositionToDict:
    def test_days_held_from_created_at(self):
        svc = _make_service()
        d = svc._position_to_dict(_make_position(created_days_ago=3))
        assert d["days_held"] == 3

    def test_created_at_exposed(self):
        svc = _make_service()
        d = svc._position_to_dict(_make_position())
        assert d["created_at"] is not None

    def test_dict_position_passthrough(self):
        svc = _make_service()
        raw = {"symbol": "600519", "days_held": 7}
        assert svc._position_to_dict(raw) is raw


class TestGetAccountStatus:
    def _setup_repo(self, svc, positions):
        account = MagicMock()
        account.display_name = "测试账户"
        account.strategy_name = "v13"
        account.cash_available = Decimal("40000")
        account.cash_frozen = Decimal("0")
        account.position_value = Decimal("60000")
        account.total_value = Decimal("100000")
        account.initial_capital = Decimal("100000")
        account.cumulative_return = Decimal("0.0")
        account.last_rebalance_date = None
        svc.repo.get_account.return_value = account
        svc.repo.get_all_positions.return_value = positions
        return account

    def test_response_has_last_updated(self):
        svc = _make_service()
        self._setup_repo(svc, [])
        result = svc.get_account_status("test_account")
        assert result["last_updated"] is not None

    def test_price_stale_true_when_no_prices_fetched(self):
        svc = _make_service()
        self._setup_repo(svc, [_make_position()])
        svc._fetch_current_prices = MagicMock(return_value={})
        result = svc.get_account_status("test_account")
        assert result["price_stale"] is True

    def test_price_stale_false_when_prices_fetched(self):
        svc = _make_service()
        self._setup_repo(svc, [_make_position()])
        svc._fetch_current_prices = MagicMock(return_value={"600519": 1520.0})
        result = svc.get_account_status("test_account")
        assert result["price_stale"] is False

    def test_price_timestamps_exposed_when_available(self):
        svc = _make_service()
        self._setup_repo(svc, [_make_position()])

        def fake_fetch(symbols):
            # 契约：_fetch_current_prices 拉价时同时记录 quote 时间戳
            svc._price_timestamps = {"600519": "2026-07-28T09:31:00"}
            return {"600519": 1520.0}

        svc._fetch_current_prices = fake_fetch
        result = svc.get_account_status("test_account")
        assert result["positions"][0]["price_updated_at"] == "2026-07-28T09:31:00"
