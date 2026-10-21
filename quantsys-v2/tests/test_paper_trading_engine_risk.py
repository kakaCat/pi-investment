"""PaperTradingEngine 批量风控回归测试（2026-10-20 修复）

覆盖三处历史漏洞：
1. 每日买入笔数上限在批量执行中被穿透（过滤时 _daily_buy_count 恒为 0）
2. 现金/总仓位预算在批内不扣减，每条信号都看到全额预算
3. 过滤层算的股数上限（approved_shares）在执行层被丢弃
"""
from unittest.mock import MagicMock

from application.trading.paper_trading_engine import PaperTradingEngine
from domain.trading.models.signal import Signal


def _make_engine(cash=1_000_000, total_value=1_000_000, position_value=0,
                 positions=None, max_daily_buys=3):
    engine = PaperTradingEngine.__new__(PaperTradingEngine)
    engine.account_name = 'test_acct'
    engine.initial_capital = 1_000_000
    engine.risk_config = dict(PaperTradingEngine.__init__.__defaults__ and {} or {})
    from application.trading.paper_trading_engine import DEFAULT_RISK_CONFIG
    engine.risk_config = {**DEFAULT_RISK_CONFIG, 'max_daily_buys': max_daily_buys}
    engine.broker = MagicMock()
    engine.repo = MagicMock()
    account = MagicMock()
    account.cash_available = cash
    account.total_value = total_value
    account.position_value = position_value
    account.peak_value = total_value
    account.cumulative_return = 0
    account.max_drawdown = 0
    engine.repo.get_account.return_value = account
    engine.repo.get_all_positions.return_value = positions or []
    engine.market_style = 'default'
    engine._daily_buy_count = 0
    engine._daily_buy_date = None
    return engine


def _buy(symbol, strength=1.0, price=10.0):
    return Signal(symbol=symbol, action='BUY', strength=strength, price=price)


class TestBatchDailyBuyCap:
    def test_batch_respects_daily_cap_and_prefers_strongest(self):
        engine = _make_engine(max_daily_buys=3)
        # 5 个信号，强度最低的在最前面（验证先排序再限额）
        signals = [
            _buy('600005', strength=0.5),
            _buy('600004', strength=0.6),
            _buy('600003', strength=0.7),
            _buy('600002', strength=0.8),
            _buy('600001', strength=0.9),
        ]
        approved = engine._filter_buy_signals(signals, {s.symbol: 10.0 for s in signals})

        assert len(approved) == 3
        assert [s.symbol for s in approved] == ['600001', '600002', '600003']


class TestBatchBudgetReservation:
    def test_position_budget_reserved_within_batch(self):
        # 总资产 100 万，default 总仓位上限 60% → 预算 60 万；
        # 单票上限 20% = 20 万/只 → 批内最多 3 只（第 4 只预算不足被拒）
        engine = _make_engine(cash=10_000_000, total_value=1_000_000)
        prices = {f'60000{i}': 10.0 for i in range(6)}
        signals = [_buy(sym, strength=1.0, price=10.0) for sym in prices]

        approved = engine._filter_buy_signals(signals, prices)

        # max_daily_buys=3 与预算上限同量级：两者都不许穿透
        assert len(approved) <= 3
        total_reserved = sum(s.approved_shares * 10.0 for s in approved)
        assert total_reserved <= 1_000_000 * 0.60 + 1  # 60% 预算（含取整误差）

    def test_cash_reserved_within_batch(self):
        # 现金只有 25 万：第 1 只按单票上限买 20 万，第 2 只应被裁到仅剩的 5 万
        # （批内现金扣减生效；旧逻辑两条都看到全额 25 万，会各批 20 万）
        engine = _make_engine(cash=250_000, total_value=1_000_000, max_daily_buys=10)
        prices = {'600001': 10.0, '600002': 10.0}
        signals = [_buy('600001', strength=1.0, price=10.0),
                   _buy('600002', strength=1.0, price=10.0)]

        approved = engine._filter_buy_signals(signals, prices)

        assert len(approved) == 2
        assert approved[0].approved_shares * 10.0 == 200_000
        assert approved[1].approved_shares * 10.0 == 50_000
        total = sum(s.approved_shares * 10.0 for s in approved)
        assert total <= 250_000


class TestApprovedSharesEnforcedAtExecution:
    def test_execute_buy_respects_approved_shares_cap(self):
        engine = _make_engine(cash=1_000_000, total_value=1_000_000)
        engine.broker.buy.return_value = {
            'filled_price': 10.0, 'commission': 6.0,
            'amount': 20_000.0, 'total_cost': 20_006.0,
        }
        engine.repo.get_position.return_value = None

        # 过滤层只批了 2000 股，但按强度口径执行层自己算会买 16000 股
        signal = _buy('600001', strength=0.8, price=10.0)
        signal.approved_shares = 2000

        result = engine._execute_buy(signal, 10.0)

        assert result.success is True
        assert result.shares == 2000
        # 账户市值口径：新仓市值必须计入 position_value/total_value
        update_kwargs = engine.repo.update_account.call_args.kwargs
        assert update_kwargs['position_value'] == 2000 * 10.0
        assert abs(update_kwargs['total_value'] - (1_000_000 - 6.0)) < 0.01

    def test_execute_buy_without_cap_unchanged(self):
        # 未经过滤层的直连调用（无 approved_shares 属性）保持原行为
        engine = _make_engine(cash=1_000_000, total_value=1_000_000)
        engine.broker.buy.return_value = {
            'filled_price': 10.0, 'commission': 48.0,
            'amount': 160_000.0, 'total_cost': 160_048.0,
        }
        engine.repo.get_position.return_value = None

        signal = _buy('600001', strength=0.8, price=10.0)
        result = engine._execute_buy(signal, 10.0)

        assert result.success is True
        assert result.shares == 16000  # 1M × 20% × 0.8 / 10 = 16000
