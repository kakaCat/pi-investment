import pytest
from datetime import date
from unittest.mock import Mock, patch
from domain.quantlib.core.portfolio_calculator import PortfolioCalculator


def make_calculator(**kwargs):
    """构造注入 mock 仓储的 PortfolioCalculator。"""
    kwargs.setdefault('portfolio_repo', Mock())
    kwargs.setdefault('kline_repo', Mock())
    kwargs.setdefault('risk_repo', Mock())
    return PortfolioCalculator(**kwargs)


class TestPortfolioCalculator:

    def test_calculator_initialization(self):
        """Test calculator initializes with default initial cash"""
        calculator = make_calculator()

        assert calculator.initial_cash == 1000000.0

    def test_calculator_initialization_with_custom_cash(self):
        """Test calculator initializes with custom initial cash"""
        calculator = make_calculator(initial_cash=500000.0)

        assert calculator.initial_cash == 500000.0

    def test_calculate_cash_balance_no_trades(self):
        """Test cash balance equals initial cash when no trades"""
        calculator = make_calculator(initial_cash=1000000.0)

        # Mock portfolio_repo to return empty trades
        calculator.portfolio_repo.get_trades_by_date = Mock(return_value=[])

        cash = calculator.calculate_cash_balance(date(2026, 5, 23))

        assert cash == 1000000.0

    def test_calculate_cash_balance_with_buy_trade(self):
        """Test cash balance decreases after buy trade"""
        calculator = make_calculator(initial_cash=1000000.0)

        # Mock a buy trade
        mock_trades = [
            {
                'action': 'buy',
                'amount': 100000.0,
                'fee': 50.0,
                'stamp_duty': 0.0
            }
        ]
        calculator.portfolio_repo.get_trades_by_date = Mock(return_value=mock_trades)

        cash = calculator.calculate_cash_balance(date(2026, 5, 23))

        # 1000000 - 100000 - 50 = 899950
        assert cash == 899950.0

    def test_calculate_cash_balance_with_sell_trade(self):
        """Test cash balance increases after sell trade"""
        calculator = make_calculator(initial_cash=1000000.0)

        # Mock buy and sell trades
        mock_trades = [
            {
                'action': 'buy',
                'amount': 100000.0,
                'fee': 50.0,
                'stamp_duty': 0.0
            },
            {
                'action': 'sell',
                'amount': 110000.0,
                'fee': 55.0,
                'stamp_duty': 110.0
            }
        ]
        calculator.portfolio_repo.get_trades_by_date = Mock(return_value=mock_trades)

        cash = calculator.calculate_cash_balance(date(2026, 5, 23))

        # 1000000 - 100000 - 50 + 110000 - 55 - 110 = 1009785
        assert cash == 1009785.0

    def test_calculate_market_value_no_holdings(self):
        """Test market value is zero when no holdings"""
        calculator = make_calculator()

        calculator.portfolio_repo.get_holdings_as_of = Mock(return_value=[])

        market_value = calculator.calculate_market_value(date(2026, 5, 23))

        assert market_value == 0.0

    def test_calculate_market_value_with_holdings(self):
        """Test market value calculation with holdings reconstructed from trades"""
        calculator = make_calculator()

        mock_holdings = [
            {'symbol': '000001.SH', 'name': '浦发银行', 'quantity': 100},
            {'symbol': '000858.SZ', 'name': '五粮液', 'quantity': 500}
        ]
        calculator.portfolio_repo.get_holdings_as_of = Mock(return_value=mock_holdings)

        def mock_get_close_price(symbol, trade_date):
            prices = {'000001.SH': 1680.0, '000858.SZ': 152.0}
            return prices.get(symbol)

        calculator.kline_repo.get_close_price = Mock(side_effect=mock_get_close_price)

        market_value = calculator.calculate_market_value(date(2026, 5, 23))

        # 100 * 1680 + 500 * 152 = 168000 + 76000 = 244000
        assert market_value == 244000.0

    def test_calculate_snapshot(self):
        """Test complete snapshot calculation"""
        calculator = make_calculator(initial_cash=1000000.0)

        # Mock cash balance
        calculator.calculate_cash_balance = Mock(return_value=900000.0)

        # Mock market value
        calculator.calculate_market_value = Mock(return_value=244000.0)

        # Mock position count
        calculator.get_position_count = Mock(return_value=2)

        # Mock previous balance (for daily return calculation)
        calculator.risk_repo.get_balance_by_date = Mock(return_value={
            'total_assets': 1100000.0
        })

        snapshot = calculator.calculate_snapshot('2026-05-23')

        assert snapshot['balance_date'] == '2026-05-23'
        assert snapshot['cash'] == 900000.0
        assert snapshot['market_value'] == 244000.0
        assert snapshot['total_assets'] == 1144000.0  # 900000 + 244000
        assert snapshot['position_count'] == 2
        assert snapshot['total_pnl'] == 144000.0  # 1144000 - 1000000
        assert abs(snapshot['total_return'] - 14.4) < 0.01  # (144000 / 1000000) * 100
        assert snapshot['daily_pnl'] == 44000.0  # 1144000 - 1100000
        assert abs(snapshot['daily_return'] - 4.0) < 0.01  # (44000 / 1100000) * 100
