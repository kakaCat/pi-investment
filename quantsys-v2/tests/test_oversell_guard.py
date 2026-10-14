"""账本超卖拦截与现金重放对账器测试（REQ-261004154902-a7cd · t-900179 / FR-10）

覆盖验收标准：

① 净持仓不足时卖出 → **被拒**（``TradingError``，reason=``oversell_blocked``）且 ``report_failure`` 被调用；
② 净持仓足够时卖出 → 正常放行（走到写路径）；
③ **流水读不到**（抛异常 / 返回 None / 类型不对）→ **放行**且留痕外发（既不静默，也不误杀）；
④ V13 自己那两条卖出路径（``_execute_stop_loss`` / ``_execute_trades_with_risk_control``）同样被拦；
⑤ 对账器的超卖清单在给定假数据下能报出那 4 只，并算出虚增 ≈¥49,425；
⑥ 现金重放差额可解释 = 退出码 0，有超卖或差额无法解释 = 退出码 2。

**零 DB、零外发**：repo 全打桩（``FakeRepo``），失败出口 ``report_failure`` 被替换成记录器
（真实外发会被 tests/notify_guard.py 判为"漏桩"而红），全程不连库、不写库。
"""
from __future__ import annotations

import pathlib
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from application.services.account_trading_service import (
    AccountTradingService,
    REASON_OVERSELL_BLOCKED,
    TradingError,
    check_sellable,
    net_traded_shares,
    read_net_traded_shares,
)
from domain.trading.services.trade_guard_service import TradeGuardService
from live_trading.simulation_trader import SimulationTrader
import tools.reconcile_sim_account as reconcile
from tools.reconcile_sim_account import EXIT_INCONSISTENT, EXIT_OK, build_report

REASON = '测试卖出：净持仓不足时应当被超卖护栏拦下'

# 服务层读流水 / 外发失败，全部经本模块被观测（零真实外发）
SERVICE_MODULE = 'application.services.account_trading_service'


# ---------------------------------------------------------------------------
# 打桩：失败出口 + 假 repo
# ---------------------------------------------------------------------------

@pytest.fixture()
def failures(monkeypatch):
    """替换失败外发出口（记录每次外发，不触碰真实通道）。"""
    recorded: list = []

    def fake_report_failure(source, reason, error=None, severity='normal', context=None):
        recorded.append({'source': source, 'reason': reason, 'error': error,
                         'severity': severity, 'context': context})
        return True

    monkeypatch.setattr(f'{SERVICE_MODULE}.report_failure', fake_report_failure)
    return recorded


@pytest.fixture()
def guard(monkeypatch):
    """打桩领域层护栏：本文件的被测对象是**超卖校验**，不是 TradeGuardService 的规则。"""
    fees = {'trade_amount': 1000.0, 'commission': 5.0, 'stamp_duty': 0.5,
            'transfer_fee': 0.01, 'total_cost': 1005.01,
            'realized_pnl': 0.0, 'realized_pnl_rate': 0.0}
    monkeypatch.setattr(
        TradeGuardService, 'validate_trade_request',
        lambda self, **kwargs: dict(fees),
    )


#: 区分"没传"与"显式传 None"（None 也是一种"读不到流水"的形态，必须可注入）
_UNSET = object()


class _FakeSession:
    def __init__(self):
        self.committed = 0
        self.rolled_back = 0
        self.expired = 0

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def expire_all(self):
        self.expired += 1


class FakeRepo:
    """够用的假仓储：只读方法按注入值返回，写方法只记账不落库。"""

    def __init__(self, trades=(), positions=(), *, raise_on_trades=None,
                 raw_trades=_UNSET, account=None):
        self.trades = list(trades)
        self.positions = list(positions)
        self.raise_on_trades = raise_on_trades
        self.raw_trades = raw_trades
        self.account = account or _account()
        # 观测点
        self.trades_reads = 0
        self.added_trades: list = []
        self.orders: list = []
        self.positions_written: list = []
        self.deleted_positions: list = []
        self.pending_status_updates: list = []
        self.session = _FakeSession()

    # ---- 读 ----
    def get_account(self, account_name):
        return self.account

    def get_account_for_update(self, account_name):
        return self.account

    def get_all_positions(self, account_name):
        return self.positions

    def get_pending_orders(self, **kwargs):
        return []

    def get_trades_by_account(self, account_name, **kwargs):
        self.trades_reads += 1
        if self.raise_on_trades is not None:
            raise self.raise_on_trades
        if self.raw_trades is not _UNSET:
            return self.raw_trades
        return self.trades

    # ---- 写（只记账） ----
    def create_order(self, **kwargs):
        self.orders.append(kwargs)
        return SimpleNamespace(id=101, status='pending', filled_shares=0, avg_filled_price=0)

    def add_trade(self, **kwargs):
        self.added_trades.append(kwargs)
        return 7

    def upsert_position(self, *args, **kwargs):
        self.positions_written.append((args, kwargs))
        return True

    def delete_position(self, account_name, symbol, **kwargs):
        self.deleted_positions.append(symbol)
        return True

    def upsert_equity_snapshot(self, *args, **kwargs):
        return True

    def update_pending_order_status(self, *args, **kwargs):
        self.pending_status_updates.append((args, kwargs))
        return True


def _account(**overrides):
    defaults = dict(
        account_name='v13_simulation', status='active',
        cash_available=100000.0, cash_frozen=0.0,
        position_value=0.0, total_value=100000.0, peak_value=100000.0,
        initial_capital=100000.0, cumulative_return=0.0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _position(symbol, shares_total, shares_available=None, avg_cost=10.0, price=12.0):
    return SimpleNamespace(
        symbol=symbol, shares_total=shares_total,
        shares_available=shares_total if shares_available is None else shares_available,
        avg_cost=avg_cost, current_price=price,
        market_value=shares_total * price,
    )


def _trade(symbol, action, shares):
    return SimpleNamespace(symbol=symbol, action=action, shares=shares)


def _service(repo, monkeypatch, now=datetime(2026, 10, 6, 10, 0)):
    svc = AccountTradingService(repo=repo, calendar=Mock(is_trading_day=lambda _d: True),
                                now_fn=lambda: now)
    monkeypatch.setattr(svc, '_get_price', lambda symbol: 12.0)  # 不碰真实行情
    return svc


def _sell(svc, symbol='300045', shares=300):
    return svc.execute_trade(
        account_name='v13_simulation', action='sell', symbol=symbol,
        shares=shares, reason=REASON,
    )


# ---------------------------------------------------------------------------
# ① 净持仓不足 → 拒绝 + 外发
# ---------------------------------------------------------------------------

class TestSellBlockedWhenNetPositionInsufficient:

    def test_sell_beyond_trades_net_is_rejected_and_alerted(self, failures, guard, monkeypatch):
        """买 1000 / 卖 1800（净 -800），本次卖 300 → 拒绝，且不产生任何成交。"""
        repo = FakeRepo(
            trades=[_trade('300045', 'BUY', 1000), _trade('300045', 'SELL', 1800)],
            positions=[_position('300045', 1000, 1000)],
        )
        svc = _service(repo, monkeypatch)

        with pytest.raises(TradingError) as exc:
            _sell(svc, shares=300)

        assert exc.value.status_code == 422
        assert '超卖拦截' in str(exc.value)
        assert '-800' in str(exc.value) and '300' in str(exc.value)
        assert exc.value.details['reason'] == REASON_OVERSELL_BLOCKED
        assert exc.value.details['net_shares'] == -800
        assert exc.value.details['requested_shares'] == 300
        # 下单/成交/资金全都没发生
        assert repo.orders == [] and repo.added_trades == []
        assert repo.session.rolled_back == 1 and repo.session.committed == 0
        # 外发一次（source/reason 是本卡的受控口径）
        assert len(failures) == 1, failures
        assert failures[0]['source'] == 'account_trading.oversell_check'
        assert failures[0]['reason'] == REASON_OVERSELL_BLOCKED
        assert failures[0]['context']['decision'] == 'rejected'

    def test_zero_net_position_cannot_be_sold(self, failures, guard, monkeypatch):
        """净持仓 0（全部卖光后又卖一次）→ 拒绝（这就是历史虚增的形态）。"""
        repo = FakeRepo(
            trades=[_trade('300765', 'BUY', 300), _trade('300765', 'SELL', 300)],
            positions=[_position('300765', 300, 300)],
        )
        svc = _service(repo, monkeypatch)

        with pytest.raises(TradingError) as exc:
            _sell(svc, symbol='300765', shares=300)

        assert '净持仓 0 股' in str(exc.value)
        assert repo.added_trades == []
        assert failures and failures[0]['reason'] == REASON_OVERSELL_BLOCKED


# ---------------------------------------------------------------------------
# ② 净持仓足够 → 放行
# ---------------------------------------------------------------------------

class TestSellPassesWhenNetPositionSufficient:

    def test_sell_within_trades_net_goes_through(self, failures, guard, monkeypatch):
        repo = FakeRepo(
            trades=[_trade('300109', 'BUY', 1400)],
            positions=[_position('300109', 1400, 1400)],
        )
        svc = _service(repo, monkeypatch)

        result = _sell(svc, symbol='300109', shares=1000)

        assert result['order_status'] == 'filled'
        assert result['shares'] == 1000
        assert len(repo.added_trades) == 1
        assert repo.session.committed == 1
        assert failures == [], '净持仓足够时不许外发'

    def test_exact_net_position_is_allowed(self, failures, guard, monkeypatch):
        """边界：ΣBUY - ΣSELL == 本次卖出量 → 放行（判据是 >=，不是 >）。"""
        repo = FakeRepo(
            trades=[_trade('300109', 'BUY', 1400), _trade('300109', 'SELL', 400)],
            positions=[_position('300109', 1000, 1000)],
        )
        svc = _service(repo, monkeypatch)

        result = _sell(svc, symbol='300109', shares=1000)

        assert result['order_status'] == 'filled'
        assert failures == []

    def test_buy_is_not_touched_by_the_guard(self, failures, guard, monkeypatch):
        """买入不经过卖前校验（不读流水、不外发、行为不变）。"""
        repo = FakeRepo(trades=[_trade('300109', 'BUY', 1400)])
        svc = _service(repo, monkeypatch)

        svc.execute_trade(account_name='v13_simulation', action='buy', symbol='300109',
                          shares=100, reason='测试买入：买入路径不受卖前校验影响')

        assert repo.trades_reads == 0
        assert failures == []


# ---------------------------------------------------------------------------
# ③ 流水读不到 → 放行 + 留痕外发（不许静默、也不许误杀）
# ---------------------------------------------------------------------------

class TestUnreadableTradesPassThroughLoudly:

    @pytest.mark.parametrize('shape, repo_kwargs', [
        ('raise', {'raise_on_trades': RuntimeError('connection reset by peer')}),
        ('none', {'raw_trades': None}),
        ('wrong_type', {'raw_trades': Mock()}),      # 类型不对（非流水序列）
        ('unparsable_row', {'trades': [SimpleNamespace(symbol='300045', action='BUY',
                                                       shares='not-a-number')]}),
    ])
    def test_sell_is_allowed_but_loudly_noted(self, failures, guard, monkeypatch,
                                              shape, repo_kwargs):
        repo = FakeRepo(positions=[_position('300045', 1000, 1000)], **repo_kwargs)
        svc = _service(repo, monkeypatch)

        result = _sell(svc, shares=300)          # 取数失败 ≠ 超卖：必须放行

        assert result['order_status'] == 'filled', shape
        assert len(repo.added_trades) == 1, shape
        assert len(failures) == 1, (shape, failures)
        assert failures[0]['source'] == 'account_trading.oversell_check'
        assert failures[0]['reason'] == REASON_OVERSELL_BLOCKED
        assert failures[0]['context']['decision'] == 'passed_through_unchecked'
        assert failures[0]['severity'] == 'high'

    def test_read_helper_returns_none_instead_of_guessing(self):
        class _Boom:
            def get_trades_by_account(self, account_name, **kwargs):
                raise RuntimeError('db down')

        assert read_net_traded_shares(_Boom(), 'v13_simulation', '300045') is None
        assert read_net_traded_shares(FakeRepo(raw_trades=None), 'acc', '300045') is None
        assert read_net_traded_shares(FakeRepo(raw_trades=Mock()), 'acc', '300045') is None

    def test_check_sellable_does_not_raise_on_unreadable(self, failures):
        """直接调唯一实现：取数失败不抛（放行语义在函数体里，不靠调用方兜）。"""
        class _Boom:
            def get_trades_by_account(self, account_name, **kwargs):
                raise RuntimeError('db down')

        check_sellable(_Boom(), 'v13_simulation', '300045', 300)   # 不抛
        assert len(failures) == 1


# ---------------------------------------------------------------------------
# 净额口径本身（与 _rebuild_portfolio_from_trades 的 SQL 对齐）
# ---------------------------------------------------------------------------

class TestNetTradedShares:
    def test_case_insensitive_and_symbol_scoped(self):
        trades = [_trade('300045', 'buy', 1000), _trade('300045', 'SELL', 400),
                  _trade('999999', 'BUY', 5000)]
        assert net_traded_shares(trades, '300045') == 600
        assert net_traded_shares(trades, '999999') == 5000
        assert net_traded_shares(trades, '000000') == 0

    def test_unknown_action_counts_zero(self):
        """既非 BUY 也非 SELL 的行按 0 计（等同 SQL 的 ELSE 0），不误判成超卖。"""
        assert net_traded_shares([_trade('300045', 'HOLD', 999)], '300045') == 0

    def test_bad_row_type_raises_instead_of_silently_zero(self):
        with pytest.raises(TypeError):
            net_traded_shares([SimpleNamespace(symbol='300045', action='BUY', shares='x')],
                              '300045')


# ---------------------------------------------------------------------------
# ④ V13 自己的两条卖出路径
# ---------------------------------------------------------------------------

def _bare_trader(repo, portfolio, broker):
    trader = SimulationTrader.__new__(SimulationTrader)
    trader.account_name = 'v13_simulation'
    trader.repo = repo
    trader.portfolio = dict(portfolio)
    trader.cash = 1000.0
    trader.broker = broker
    trader.config = {'trading': {'commission_rate': 0.00025}}
    return trader


class TestTraderSellPathsGuarded:

    def test_stop_loss_blocked_keeps_position(self, failures):
        """止损卖出净持仓不足 → 跳过该标的（持仓保留），且外发留痕。"""
        sells: list = []
        broker = SimpleNamespace(
            sell=lambda symbol, shares, price: sells.append((symbol, shares, price)))
        repo = FakeRepo(trades=[_trade('300045', 'BUY', 1000),
                                _trade('300045', 'SELL', 2000)])
        trader = _bare_trader(repo, {'300045': {'shares': 1000, 'avg_price': 12.0}}, broker)

        trader._execute_stop_loss(['300045'], {'300045': 12.74}, '2026-10-06')

        assert sells == [], '被拦截的止损不许下单'
        assert '300045' in trader.portfolio, '被拦截的持仓必须保留（不许凭空消失）'
        assert repo.added_trades == []
        assert len(failures) == 1 and failures[0]['source'] == 'account_trading.oversell_check'
        assert failures[0]['context']['path'] == 'stop_loss'

    def test_rebalance_exit_sell_blocked(self, failures):
        """调仓清仓卖出净持仓不足 → 跳过，继续处理别的标的。"""
        sells: list = []
        broker = SimpleNamespace(
            sell=lambda symbol, shares, price: sells.append((symbol, shares, price)))
        repo = FakeRepo(trades=[_trade('300045', 'BUY', 100),
                                _trade('300045', 'SELL', 200)])
        trader = _bare_trader(repo, {'300045': {'shares': 500, 'avg_price': 12.0}}, broker)
        trader._get_current_prices = lambda symbols, date: {'300045': 12.0}

        trader._execute_trades_with_risk_control([], {}, 1.0, '2026-10-06')

        assert sells == []
        assert '300045' in trader.portfolio
        assert repo.added_trades == []
        assert len(failures) == 1
        assert failures[0]['context']['path'] == 'rebalance_exit'

    def test_stop_loss_passes_when_net_position_is_enough(self, failures):
        sells: list = []
        broker = SimpleNamespace(sell=lambda symbol, shares, price: {
            'total_revenue': 12000.0, 'filled_price': price, 'amount': shares * price,
            'commission': 5.0, 'stamp_duty': 12.0,
            **({'__sold__': sells.append((symbol, shares))} or {})})
        repo = FakeRepo(trades=[_trade('300045', 'BUY', 1000)])
        trader = _bare_trader(repo, {'300045': {'shares': 1000, 'avg_price': 12.0}}, broker)

        trader._execute_stop_loss(['300045'], {'300045': 12.74}, '2026-10-06')

        assert sells == [('300045', 1000)]
        assert '300045' not in trader.portfolio
        assert len(repo.added_trades) == 1
        assert failures == []


# ---------------------------------------------------------------------------
# ⑤⑥ 对账器：超卖清单 / 现金重放 / 退出码
# ---------------------------------------------------------------------------

def _row(symbol, action, shares, amount, *, commission=5.0, stamp_duty=0.0,
         transfer_fee=0.0, date='2026-07-28', tid=1, revenue=None):
    """按库内实测形态造一行流水：BUY 用负 total_revenue（total_cost 为空），
    SELL 用净收入。``revenue`` 可显式给出库内记录的净收入（成交额与费用的分位
    取整会差 1 分，测试要钉住真实数字）。"""
    fees = commission + stamp_duty + transfer_fee
    if revenue is None:
        revenue = (-round(amount + fees, 2) if action == 'BUY'
                   else round(amount - fees, 2))
    return {'id': tid, 'symbol': symbol, 'action': action, 'shares': shares,
            'filled_price': round(amount / shares, 2), 'amount': amount,
            'commission': commission, 'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee, 'total_cost': None,
            'total_revenue': revenue, 'trade_date': date}


#: 4 只超卖标的的**真实**成交流水（取自 quant.simulation_trades，2026-10-04；
#: SELL 行的 total_revenue 用库内记录值，含分位取整差异）
OVERSOLD_TRADES = [
    _row('300045', 'BUY', 1000, 12252.24, date='2026-07-28', tid=1),
    _row('300045', 'SELL', 1000, 13400.00, commission=5.0, stamp_duty=6.70,
         transfer_fee=0.13, date='2026-08-05', tid=2, revenue=13388.17),
    _row('300045', 'SELL', 1000, 12737.25, commission=5.0, stamp_duty=12.74,
         date='2026-08-21', tid=3, revenue=12719.51),
    _row('300469', 'BUY', 200, 9851.84, date='2026-07-28', tid=4),
    _row('300469', 'SELL', 200, 11096.00, commission=5.0, stamp_duty=5.55,
         transfer_fee=0.11, date='2026-08-05', tid=5, revenue=11085.34),
    _row('300469', 'SELL', 200, 11386.60, commission=5.0, stamp_duty=11.39,
         date='2026-08-21', tid=6, revenue=11370.22),
    _row('300561', 'BUY', 700, 11974.96, date='2026-07-28', tid=7),
    _row('300561', 'SELL', 700, 13097.00, commission=5.0, stamp_duty=6.55,
         transfer_fee=0.13, date='2026-08-05', tid=8, revenue=13085.32),
    _row('300561', 'SELL', 700, 10685.30, commission=5.0, stamp_duty=10.69,
         date='2026-08-21', tid=9, revenue=10669.62),
    _row('300765', 'BUY', 300, 11681.67, date='2026-07-28', tid=10),
    _row('300765', 'SELL', 200, 8640.00, commission=5.0, stamp_duty=4.32,
         transfer_fee=0.09, date='2026-08-07', tid=11, revenue=8630.59),
    _row('300765', 'SELL', 100, 3953.00, commission=5.0, stamp_duty=1.98,
         transfer_fee=0.04, date='2026-08-11', tid=12, revenue=3945.98),
    _row('300765', 'SELL', 300, 14685.30, commission=5.0, stamp_duty=14.69,
         date='2026-08-21', tid=13, revenue=14665.61),
]

NORMAL_TRADES = [
    _row('300109', 'BUY', 1400, 20139.16, date='2026-07-28', tid=90),
]


def _account_for(trades, initial=100000.0, cash_delta=0.0):
    cash = initial + sum(t['total_revenue'] for t in trades) + cash_delta
    return {'cash_available': cash, 'cash_frozen': 0.0, 'position_value': 0.0,
            'total_value': cash, 'initial_capital': initial, 'cumulative_return': 0.0,
            'last_rebalance_date': '2026-08-31', 'status': 'active'}


class TestReconcileReport:

    def test_oversold_list_reports_the_four_symbols(self):
        trades = OVERSOLD_TRADES + NORMAL_TRADES
        report = build_report('v13_simulation', trades, _account_for(trades))

        assert [s['symbol'] for s in report['oversold']] == \
            ['300045', '300469', '300561', '300765']
        assert report['oversold_phantom_revenue_total'] == pytest.approx(49424.96, abs=0.01)
        # 逐项：凭空卖出股数 = Σ卖出 - Σ买入
        by_symbol = {s['symbol']: s for s in report['oversold']}
        assert by_symbol['300045']['phantom_sell_shares'] == 1000
        assert by_symbol['300469']['phantom_sell_shares'] == 200
        assert by_symbol['300561']['phantom_sell_shares'] == 700
        assert by_symbol['300765']['phantom_sell_shares'] == 300
        assert all(s['first_over_sell_date'] == '2026-08-21'
                   for s in report['oversold'])
        # 净持仓为负 = 账本自相矛盾
        assert by_symbol['300045']['net_shares'] == -1000
        assert report['cash_replay']['explained'] is True

        # 2026-10-04（REQ-261004154902-a7cd t-174c1d · 用户裁定「标记为脏并从统计排除」）：
        # 这四只已在 config/known_dirty_simulation_data.json 里登记 → 仍然**可见**，
        # 但不再计入「不自洽」。判定口径变了，证据反而更强：两种口径都要能被验证。
        assert report['exit_code'] == EXIT_OK
        assert report['oversold_unexpected'] == []
        assert {s['symbol'] for s in report['oversold_known_dirty']} == \
            {'300045', '300469', '300561', '300765'}

    def test_without_dirty_manifest_oversold_is_inconsistent(self, monkeypatch):
        """反证：清单不在（或未启用）时，同样的数据必须判「不自洽」（退出码 2）。"""
        monkeypatch.setattr(reconcile, 'DIRTY_MANIFEST',
                            pathlib.Path('/nonexistent/known_dirty.json'))
        trades = OVERSOLD_TRADES + NORMAL_TRADES
        report = build_report('v13_simulation', trades, _account_for(trades))

        assert report['exit_code'] == EXIT_INCONSISTENT
        assert report['oversold_known_dirty'] == []
        assert {s['symbol'] for s in report['oversold_unexpected']} == \
            {'300045', '300469', '300561', '300765'}

    def test_self_consistent_ledger_exits_zero(self):
        trades = [_row('600000.SH', 'BUY', 100, 1000.0, date='2026-07-28', tid=1),
                  _row('600000.SH', 'SELL', 100, 1100.0, commission=5.0,
                       stamp_duty=1.1, transfer_fee=0.01, date='2026-08-05', tid=2)]
        report = build_report('acc', trades, _account_for(trades))

        assert report['oversold'] == []
        assert report['cash_replay']['diff'] == pytest.approx(0.0, abs=0.001)
        assert report['exit_code'] == EXIT_OK

    def test_unexplained_cash_difference_exits_two(self):
        trades = [_row('600000.SH', 'BUY', 100, 1000.0, tid=1)]
        report = build_report('acc', trades, _account_for(trades, cash_delta=5000.0))

        assert report['oversold'] == []
        assert report['cash_replay']['explained'] is False
        assert report['cash_replay']['diff'] == pytest.approx(5000.0, abs=0.01)
        assert report['exit_code'] == EXIT_INCONSISTENT

    def test_rounding_residual_is_explained(self):
        trades = [_row('600000.SH', 'BUY', 100, 1000.0, tid=1)]
        report = build_report('acc', trades, _account_for(trades, cash_delta=0.01))

        assert report['cash_replay']['explained'] is True
        assert report['exit_code'] == EXIT_OK

    def test_position_table_mismatch_is_reported(self):
        trades = [_row('600000.SH', 'BUY', 1000, 10000.0, tid=1)]
        positions = [{'symbol': '600000.SH', 'shares_total': 400}]
        report = build_report('acc', trades, _account_for(trades), positions)

        assert report['position_mismatch'] == [
            {'symbol': '600000.SH', 'position_shares': 400,
             'trades_net_shares': 1000, 'delta': -600}
        ]
        assert report['symbols'][0]['position_matches_trades'] is False

    def test_absent_position_row_with_zero_net_is_not_noise(self):
        """两边都"没有这只票"不算矛盾（否则每只清仓过的标的都会刷一行）。"""
        trades = [_row('600000.SH', 'BUY', 100, 1000.0, tid=1),
                  _row('600000.SH', 'SELL', 100, 1100.0, commission=5.0, tid=2)]
        report = build_report('acc', trades, _account_for(trades), [])

        assert report['position_mismatch'] == []
        assert report['symbols'][0]['position_matches_trades'] is True

    def test_oversold_symbol_missing_from_position_table_is_a_mismatch(self):
        report = build_report('acc', OVERSOLD_TRADES, _account_for(OVERSOLD_TRADES), [])
        assert sorted(m['symbol'] for m in report['position_mismatch']) == \
            ['300045', '300469', '300561', '300765']
