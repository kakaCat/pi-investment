"""DailySnapshotService 测试——每日净值快照（全账户稠密化地基）与历史回放回填

mock 仓储与价格源，验证估值数学、日收益、幂等与回放逻辑。
"""
from datetime import date
from unittest.mock import MagicMock

import pytest

from application.services.evolution.daily_snapshot_service import DailySnapshotService


def _account(name='agent_virtual', cash=90000.0, frozen=0.0, initial=100000.0, peak=105000.0):
    return MagicMock(account_name=name, cash_available=cash, cash_frozen=frozen,
                     initial_capital=initial, peak_value=peak)


def _position(symbol='600519.SH', shares=1000):
    return MagicMock(symbol=symbol, shares_total=shares)


def _prev_snap(total_value, snap_date=date(2026, 8, 4)):
    return MagicMock(total_value=total_value, snapshot_date=snap_date)


def _make_service(accounts, positions_by_acct, trades_by_acct, prev_snaps, prices):
    sim_repo = MagicMock()
    sim_repo.list_accounts.return_value = accounts
    sim_repo.get_account.side_effect = (
        lambda account_name: next(
            (a for a in accounts if a.account_name == account_name), None))
    sim_repo.get_all_positions.side_effect = (
        lambda account_name, only_nonzero=True: positions_by_acct.get(account_name, []))
    sim_repo.get_trades_by_account.side_effect = (
        lambda account_name, start_date=None, end_date=None: trades_by_acct.get(account_name, []))
    sim_repo.get_equity_snapshots.side_effect = (
        lambda account_name, limit=90: prev_snaps.get(account_name, []))
    svc = DailySnapshotService(
        sim_repo=sim_repo,
        price_provider=lambda symbols, start, end: {
            s: prices.get(s, {}) for s in symbols},
    )
    return svc, sim_repo


class TestDailySnapshot:
    def test_values_positions_at_close_and_computes_daily_return(self):
        # 持仓 1000 股，当日收盘 11 元 → 总资产 90000+11000=101000
        # 前快照 100000 → daily_return = 0.01
        svc, sim_repo = _make_service(
            [_account()], {'agent_virtual': [_position()]}, {},
            {'agent_virtual': [_prev_snap(100000.0)]},
            {'600519.SH': {'2026-08-05': 11.0}},
        )
        svc.snapshot_all_accounts(target_date=date(2026, 8, 5))
        kw = sim_repo.upsert_equity_snapshot.call_args.kwargs
        assert kw['account_name'] == 'agent_virtual'
        assert kw['snapshot_date'] == date(2026, 8, 5)
        assert kw['position_value'] == pytest.approx(11000.0)
        assert kw['total_value'] == pytest.approx(101000.0)
        assert kw['daily_return'] == pytest.approx(0.01)
        # cumulative = 101000/100000-1 = 0.01；peak 105000 → drawdown = (101000-105000)/105000
        assert kw['cumulative_return'] == pytest.approx(0.01)
        assert kw['drawdown'] == pytest.approx(-4000 / 105000)

    def test_missing_price_falls_back_to_latest_known_close(self):
        # 当日无K线（停牌/缺口）→ 用最近可得收盘价
        svc, sim_repo = _make_service(
            [_account()], {'agent_virtual': [_position()]}, {},
            {'agent_virtual': [_prev_snap(100000.0)]},
            {'600519.SH': {'2026-08-03': 10.5}},
        )
        svc.snapshot_all_accounts(target_date=date(2026, 8, 5))
        kw = sim_repo.upsert_equity_snapshot.call_args.kwargs
        assert kw['position_value'] == pytest.approx(10500.0)

    def test_no_prev_snapshot_daily_return_zero(self):
        svc, sim_repo = _make_service(
            [_account()], {'agent_virtual': [_position()]}, {},
            {'agent_virtual': []},
            {'600519.SH': {'2026-08-05': 11.0}},
        )
        svc.snapshot_all_accounts(target_date=date(2026, 8, 5))
        kw = sim_repo.upsert_equity_snapshot.call_args.kwargs
        assert kw['daily_return'] == 0.0


class TestBackfill:
    def _trade(self, symbol, action, shares, price, trade_date, total_cost=None, total_revenue=None):
        return MagicMock(symbol=symbol, action=action, shares=shares, price=price,
                         filled_price=price, total_cost=total_cost, total_revenue=total_revenue,
                         trade_date=trade_date)

    def test_replay_trades_and_mark_to_market(self):
        # 初始 10 万；07-30 买 1000 股 @10（total_cost 10000）；
        # 07-30 收盘 10 → 100000（ret 0）；07-31 收盘 11 → 101000（ret +1%）
        acct = _account(cash=90000.0)
        trades = [self._trade('600519.SH', 'buy', 1000, 10.0, date(2026, 7, 30),
                              total_cost=10000.0)]
        svc, sim_repo = _make_service(
            [acct], {}, {'agent_virtual': trades}, {'agent_virtual': []},
            {'600519.SH': {'2026-07-30': 10.0, '2026-07-31': 11.0}},
        )
        written = svc.backfill_account('agent_virtual', date(2026, 7, 30), date(2026, 7, 31))
        calls = sim_repo.upsert_equity_snapshot.call_args_list
        assert len(calls) == 2
        d0, d1 = calls[0].kwargs, calls[1].kwargs
        assert d0['snapshot_date'] == date(2026, 7, 30)
        assert d0['total_value'] == pytest.approx(100000.0)
        assert d0['daily_return'] == 0.0
        assert d1['snapshot_date'] == date(2026, 7, 31)
        assert d1['total_value'] == pytest.approx(101000.0)
        assert d1['daily_return'] == pytest.approx(0.01)

    def test_sell_trade_releases_cash(self):
        # 买后次日卖出：07-31 卖 1000 股 @11（total_revenue 11000）→ 全现金 101000
        acct = _account(cash=101000.0)
        trades = [
            self._trade('600519.SH', 'buy', 1000, 10.0, date(2026, 7, 30), total_cost=10000.0),
            self._trade('600519.SH', 'sell', 1000, 11.0, date(2026, 7, 31),
                        total_revenue=11000.0),
        ]
        svc, sim_repo = _make_service(
            [acct], {}, {'agent_virtual': trades}, {'agent_virtual': []},
            {'600519.SH': {'2026-07-30': 10.0, '2026-07-31': 11.0}},
        )
        svc.backfill_account('agent_virtual', date(2026, 7, 30), date(2026, 7, 31))
        d1 = sim_repo.upsert_equity_snapshot.call_args_list[1].kwargs
        assert d1['position_value'] == pytest.approx(0.0)
        assert d1['total_value'] == pytest.approx(101000.0)

    def test_skips_existing_snapshot_dates_by_default(self):
        existing = [_prev_snap(100000.0, date(2026, 7, 30))]
        trades = [self._trade('600519.SH', 'buy', 1000, 10.0, date(2026, 7, 30),
                              total_cost=10000.0)]
        svc, sim_repo = _make_service(
            [_account()], {}, {'agent_virtual': trades}, {'agent_virtual': existing},
            {'600519.SH': {'2026-07-30': 10.0, '2026-07-31': 11.0}},
        )
        svc.backfill_account('agent_virtual', date(2026, 7, 30), date(2026, 7, 31))
        dates = [c.kwargs['snapshot_date']
                 for c in sim_repo.upsert_equity_snapshot.call_args_list]
        assert dates == [date(2026, 7, 31)]

    def test_no_trades_account_skipped(self):
        svc, sim_repo = _make_service([_account()], {}, {'agent_virtual': []},
                                      {'agent_virtual': []}, {})
        result = svc.backfill_account('agent_virtual', date(2026, 7, 30), date(2026, 7, 31))
        sim_repo.upsert_equity_snapshot.assert_not_called()
        assert result['written'] == 0
