"""SimulationService 数据契约测试（A线：days_held / last_updated / price_stale）

不依赖数据库：通过 __new__ 跳过 __init__，repo 用 Mock 替换。
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from qs_trading.application.services.simulation_service import SimulationService


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
        svc._fetch_current_prices = MagicMock(return_value=({}, {}))
        result = svc.get_account_status("test_account")
        assert result["price_stale"] is True

    def test_price_stale_false_when_prices_fetched(self):
        svc = _make_service()
        self._setup_repo(svc, [_make_position()])
        svc._fetch_current_prices = MagicMock(return_value=({"600519": 1520.0}, {}))
        result = svc.get_account_status("test_account")
        assert result["price_stale"] is False

    def test_price_timestamps_exposed_when_available(self):
        svc = _make_service()
        self._setup_repo(svc, [_make_position()])

        def fake_fetch(symbols):
            # 契约（2026-10-27，RFC 017 P0）：时间戳随返回值传递 (prices, timestamps)
            return {"600519": 1520.0}, {"600519": "2026-07-28T09:31:00"}

        svc._fetch_current_prices = fake_fetch
        result = svc.get_account_status("test_account")
        assert result["positions"][0]["price_updated_at"] == "2026-07-28T09:31:00"

    def test_price_timestamps_not_stored_on_self(self):
        """契约（RFC 017 P0）：请求级状态不得留在共享单例上。

        旧实现把本次拉价时间戳写入 self._price_timestamps，线程池并发下两个账户
        请求会互相覆盖（get_account_status 已迁线程池执行，竞态窗口真实存在）。
        """
        svc = _make_service()
        self._setup_repo(svc, [_make_position()])
        svc._fetch_current_prices = lambda symbols: ({"600519": 1520.0}, {"600519": "2026-07-28T09:31:00"})
        svc.get_account_status("test_account")
        assert getattr(svc, "_price_timestamps", None) is None

    def test_concurrent_calls_keep_timestamps_isolated(self):
        """并发回归：两个账户同时查状态，各自的时间戳不得串。

        fake_fetch 休眠放大竞态窗口；旧实现（self 字段）下本测试必然失败。
        """
        import threading
        import time as time_module

        svc = _make_service()
        self._setup_repo(svc, [])
        pos_a = _make_position()
        pos_a.symbol = "600519"
        pos_b = _make_position()
        pos_b.symbol = "000858"
        svc.repo.get_all_positions.side_effect = lambda name: [pos_a] if name == "acct_a" else [pos_b]

        def fake_fetch(symbols):
            time_module.sleep(0.05)
            return {s: 1.0 for s in symbols}, {s: f"ts-{s}" for s in symbols}

        svc._fetch_current_prices = fake_fetch

        results: dict = {}

        def run(name):
            results[name] = svc.get_account_status(name)

        threads = [threading.Thread(target=run, args=(n,)) for n in ("acct_a", "acct_b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results["acct_a"]["positions"][0]["price_updated_at"] == "ts-600519"
        assert results["acct_b"]["positions"][0]["price_updated_at"] == "ts-000858"

    def test_account_status_emits_phase_timing(self, caplog):
        """可观测性（RFC 017 P0）：分阶段耗时日志必须存在，慢请求可归因。"""
        svc = _make_service()
        self._setup_repo(svc, [_make_position()])
        svc._fetch_current_prices = MagicMock(return_value=({"600519": 1520.0}, {}))
        with caplog.at_level(logging.INFO, logger="test.simulation_service"):
            svc.get_account_status("test_account")
        assert any("account_status_timing" in r.message for r in caplog.records), \
            "必须输出 account_status_timing 分阶段耗时日志（db/quote/benchmark/total）"


class TestBenchmarkBlock:
    def _setup_snapshots(self, svc):
        from datetime import date as _date
        snaps = []
        for d, r, v in [(1, 0.01, 101000.0), (2, 0.0, 101000.0), (3, -0.01, 99990.0)]:
            s = MagicMock()
            s.snapshot_date = _date(2026, 7, d)
            s.daily_return = Decimal(str(r))
            s.total_value = Decimal(str(v))
            snaps.append(s)
        # repo 按日期倒序返回
        svc.repo.get_equity_snapshots.return_value = list(reversed(snaps))

    def test_benchmark_included_when_data_available(self):
        svc = _make_service()
        TestGetAccountStatus()._setup_repo(svc, [])
        self._setup_snapshots(svc)
        svc._fetch_benchmark_klines = lambda symbol, start, end: [
            {"date": "2026-07-01", "close": 100.0},
            {"date": "2026-07-02", "close": 101.0},
            {"date": "2026-07-03", "close": 100.0},
        ]
        result = svc.get_account_status("test_account")
        assert result["benchmark"] is not None
        assert result["benchmark"]["benchmark_return_1m"] == 0.0
        assert abs(result["benchmark"]["account_return_1m"] - (-0.0001)) < 1e-6

    def test_benchmark_none_when_fetch_fails(self):
        svc = _make_service()
        TestGetAccountStatus()._setup_repo(svc, [])
        self._setup_snapshots(svc)
        svc._fetch_benchmark_klines = lambda symbol, start, end: []
        result = svc.get_account_status("test_account")
        assert result["benchmark"] is None

    def test_benchmark_none_when_no_snapshots(self):
        svc = _make_service()
        TestGetAccountStatus()._setup_repo(svc, [])
        svc.repo.get_equity_snapshots.return_value = []
        result = svc.get_account_status("test_account")
        assert result["benchmark"] is None


class TestGetAccountOverview:
    """RFC 017 P2：overview 是纯 DB 快照——不拉行情、不写库、不计算基准。"""

    def test_pure_db_snapshot_no_provider_and_no_write(self):
        svc = _make_service()
        TestGetAccountStatus()._setup_repo(svc, [_make_position()])
        svc._fetch_current_prices = MagicMock(side_effect=AssertionError('overview 不得拉行情'))
        svc._fetch_benchmark_klines = MagicMock(side_effect=AssertionError('overview 不得算基准'))
        result = svc.get_account_overview("acct")
        assert result["benchmark"] is None
        assert result["positions_count"] == 1
        assert result["positions"][0]["price_updated_at"] is not None
        assert result["total_value"] == 100000
        svc.repo.update_position_prices.assert_not_called()

    def test_price_stale_true_when_old_snapshot_in_trading(self, monkeypatch):
        from qs_trading.application.services.simulation_service import SimulationService
        svc = _make_service()
        pos = _make_position()
        pos.updated_at = datetime.now() - timedelta(seconds=3600)
        TestGetAccountStatus()._setup_repo(svc, [pos])
        monkeypatch.setattr(SimulationService, '_is_trading_time', staticmethod(lambda now: True))
        result = svc.get_account_overview("acct")
        assert result["price_stale"] is True

    def test_price_stale_false_when_fresh_snapshot(self, monkeypatch):
        from qs_trading.application.services.simulation_service import SimulationService
        svc = _make_service()
        TestGetAccountStatus()._setup_repo(svc, [_make_position()])
        monkeypatch.setattr(SimulationService, '_is_trading_time', staticmethod(lambda now: True))
        result = svc.get_account_overview("acct")
        assert result["price_stale"] is False

    def test_empty_positions_not_stale(self):
        svc = _make_service()
        TestGetAccountStatus()._setup_repo(svc, [])
        result = svc.get_account_overview("acct")
        assert result["positions"] == []
        assert result["price_stale"] is False
        assert result["price_as_of"] is None

    def test_unknown_account_raises(self):
        svc = _make_service()
        svc.repo.get_account.return_value = None
        try:
            svc.get_account_overview("nope")
            assert False, '必须抛 ValueError'
        except ValueError:
            pass
