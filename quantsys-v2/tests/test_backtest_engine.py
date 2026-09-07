"""
Tests for Backtest Engine Components

Tests slippage, commission, position sizing, and report generation.
"""
import pytest
from domain.quantlib.engine.slippage import (
    FixedSlippage, ProportionalSlippage, MarketImpactSlippage,
    NoSlippage, create_slippage_model
)
from domain.quantlib.engine.commission import (
    AShareCommission, HKStockCommission, FixedCommission,
    ZeroCommission, TieredCommission, create_commission_model
)
from domain.quantlib.engine.position_sizing import (
    FixedPositionSizer, FixedPercentSizer, KellyPositionSizer,
    RiskParitySizer, VolatilityTargetSizer, create_position_sizer
)
from domain.quantlib.engine.backtest_report import BacktestReportGenerator


# ==================== Slippage Tests ====================

class TestSlippageModels:
    """Test slippage models"""

    def test_fixed_slippage(self):
        """Test fixed slippage model"""
        model = FixedSlippage(slippage_pct=0.001)

        # Buy side
        buy_price = model.apply_slippage(100.0, 1000, 'buy')
        assert buy_price == 100.1  # 100 * (1 + 0.001)

        # Sell side
        sell_price = model.apply_slippage(100.0, 1000, 'sell')
        assert sell_price == 99.9  # 100 * (1 - 0.001)

    def test_proportional_slippage(self):
        """Test proportional slippage model"""
        model = ProportionalSlippage(base_slippage_pct=0.0005, volume_factor=0.1)

        # Without volume data
        price1 = model.apply_slippage(100.0, 1000, 'buy')
        assert price1 == 100.05  # Base slippage only

        # With volume data
        market_data = {'volume': 10000}
        price2 = model.apply_slippage(100.0, 1000, 'buy', market_data)
        # Base + volume impact: 100 * 0.0005 + 100 * 0.1 * (1000/10000)
        # = 0.05 + 1.0 = 1.05
        assert price2 == 101.05

    def test_market_impact_slippage(self):
        """Test market impact slippage model"""
        model = MarketImpactSlippage(
            base_slippage_pct=0.0003,
            impact_coefficient=0.05,
            min_slippage_pct=0.0001,
            max_slippage_pct=0.02
        )

        # With volume data
        market_data = {'volume': 10000, 'volatility': 1.0}
        price = model.apply_slippage(100.0, 1000, 'buy', market_data)

        # Should be between min and max bounds
        assert 100.01 <= price <= 102.0

    def test_no_slippage(self):
        """Test no slippage model"""
        model = NoSlippage()

        price = model.apply_slippage(100.0, 1000, 'buy')
        assert price == 100.0

    def test_slippage_factory(self):
        """Test slippage factory function"""
        model1 = create_slippage_model('fixed', slippage_pct=0.001)
        assert isinstance(model1, FixedSlippage)

        model2 = create_slippage_model('proportional')
        assert isinstance(model2, ProportionalSlippage)

        model3 = create_slippage_model('market_impact')
        assert isinstance(model3, MarketImpactSlippage)

        model4 = create_slippage_model('none')
        assert isinstance(model4, NoSlippage)

        with pytest.raises(ValueError):
            create_slippage_model('invalid')


# ==================== Commission Tests ====================

class TestCommissionModels:
    """Test commission models"""

    def test_ashare_commission_buy(self):
        """Test A-share commission for buy"""
        model = AShareCommission()

        fees = model.calculate_commission(10.0, 10000, 'buy')

        # Trade value: 100,000
        # Commission: max(100000 * 0.0003, 5) = 30
        # Stamp tax: 0 (buy only)
        # Transfer fee: 100000 * 0.00001 = 1
        # Total: 31
        assert fees['commission'] == 30.0
        assert fees['stamp_tax'] == 0.0
        assert fees['transfer_fee'] == 1.0
        assert fees['total'] == 31.0

    def test_ashare_commission_sell(self):
        """Test A-share commission for sell"""
        model = AShareCommission()

        fees = model.calculate_commission(10.0, 10000, 'sell')

        # Trade value: 100,000
        # Commission: 30
        # Stamp tax: 100000 * 0.001 = 100
        # Transfer fee: 1
        # Total: 131
        assert fees['commission'] == 30.0
        assert fees['stamp_tax'] == 100.0
        assert fees['transfer_fee'] == 1.0
        assert fees['total'] == 131.0

    def test_ashare_commission_minimum(self):
        """Test A-share commission minimum"""
        model = AShareCommission()

        # Small trade: 100 shares at 1 yuan = 100 yuan
        fees = model.calculate_commission(1.0, 100, 'buy')

        # Commission should be minimum 5
        assert fees['commission'] == 5.0

    def test_hkstock_commission(self):
        """Test HK stock commission"""
        model = HKStockCommission()

        fees = model.calculate_commission(100.0, 1000, 'buy')

        # Trade value: 100,000 HKD
        # Commission: max(100000 * 0.0025, 100) = 250
        # Trading fee: 100000 * 0.0000565 = 5.65
        # Transaction levy: 100000 * 0.000027 = 2.7
        # Stamp duty: max(100000 * 0.0013, 1) = 130
        assert fees['commission'] == 250.0
        assert fees['trading_fee'] == 5.65
        assert fees['transaction_levy'] == 2.7
        assert fees['stamp_duty'] == 130.0
        assert fees['total'] == 388.35

    def test_fixed_commission(self):
        """Test fixed commission model"""
        model = FixedCommission(commission_rate=0.001, min_commission=5.0)

        fees = model.calculate_commission(10.0, 1000, 'buy')

        # Trade value: 10,000
        # Commission: 10000 * 0.001 = 10
        assert fees['commission'] == 10.0
        assert fees['total'] == 10.0

    def test_zero_commission(self):
        """Test zero commission model"""
        model = ZeroCommission()

        fees = model.calculate_commission(100.0, 1000, 'buy')

        assert fees['total'] == 0.0

    def test_tiered_commission(self):
        """Test tiered commission model"""
        tiers = [
            (0, 0.0003),
            (100000, 0.0002),
            (1000000, 0.0001)
        ]
        model = TieredCommission(tiers=tiers, min_commission=5.0)

        # Small trade: tier 1
        fees1 = model.calculate_commission(10.0, 1000, 'buy')
        assert fees1['commission'] == 5.0  # Minimum

        # Medium trade: tier 2
        fees2 = model.calculate_commission(10.0, 20000, 'buy')
        # 200,000 * 0.0002 = 40
        assert fees2['commission'] == 40.0

        # Large trade: tier 3
        fees3 = model.calculate_commission(10.0, 200000, 'buy')
        # 2,000,000 * 0.0001 = 200
        assert fees3['commission'] == 200.0

    def test_commission_factory(self):
        """Test commission factory function"""
        model1 = create_commission_model('ashare')
        assert isinstance(model1, AShareCommission)

        model2 = create_commission_model('hkstock')
        assert isinstance(model2, HKStockCommission)

        model3 = create_commission_model('fixed')
        assert isinstance(model3, FixedCommission)

        with pytest.raises(ValueError):
            create_commission_model('invalid')


# ==================== Position Sizing Tests ====================

class TestPositionSizers:
    """Test position sizing strategies"""

    def test_fixed_position_sizer(self):
        """Test fixed position sizer"""
        sizer = FixedPositionSizer(fixed_amount=100000, lot_size=100)

        shares = sizer.calculate_position_size(
            price=10.0,
            available_capital=500000,
            total_equity=1000000
        )

        # 100000 / 10 = 10000 shares
        assert shares == 10000

    def test_fixed_position_sizer_limited_capital(self):
        """Test fixed position sizer with limited capital"""
        sizer = FixedPositionSizer(fixed_amount=100000, lot_size=100)

        shares = sizer.calculate_position_size(
            price=10.0,
            available_capital=50000,
            total_equity=1000000
        )

        # Limited by available capital: 50000 / 10 = 5000 shares
        assert shares == 5000

    def test_fixed_percent_sizer(self):
        """Test fixed percent sizer"""
        sizer = FixedPercentSizer(percent=0.1, lot_size=100)

        shares = sizer.calculate_position_size(
            price=10.0,
            available_capital=500000,
            total_equity=1000000
        )

        # 10% of 1M = 100k, 100k / 10 = 10000 shares
        assert shares == 10000

    def test_fixed_percent_sizer_max_cap(self):
        """Test fixed percent sizer with max cap"""
        sizer = FixedPercentSizer(percent=0.5, lot_size=100, max_percent=0.3)

        shares = sizer.calculate_position_size(
            price=10.0,
            available_capital=500000,
            total_equity=1000000
        )

        # Capped at 30%: 300k / 10 = 30000 shares
        assert shares == 30000

    def test_kelly_position_sizer(self):
        """Test Kelly position sizer"""
        sizer = KellyPositionSizer(
            win_rate=0.6,
            profit_loss_ratio=2.0,
            kelly_fraction=0.25,
            lot_size=100
        )

        shares = sizer.calculate_position_size(
            price=10.0,
            available_capital=500000,
            total_equity=1000000
        )

        # Kelly = (0.6 * 2 - 0.4) / 2 = 0.4
        # Quarter Kelly = 0.1
        # Position = 1M * 0.1 = 100k, 100k / 10 = 10000 shares (approximately)
        assert 9900 <= shares <= 10100

    def test_kelly_with_confidence(self):
        """Test Kelly sizer with signal confidence"""
        sizer = KellyPositionSizer(
            win_rate=0.6,
            profit_loss_ratio=2.0,
            kelly_fraction=0.25,
            lot_size=100
        )

        signal_data = {'confidence': 0.5}

        shares = sizer.calculate_position_size(
            price=10.0,
            available_capital=500000,
            total_equity=1000000,
            signal_data=signal_data
        )

        # Kelly scaled by confidence: 0.1 * 0.5 = 0.05
        # Position = 1M * 0.05 = 50k, 50k / 10 = 5000 shares (approximately)
        assert 4900 <= shares <= 5100

    def test_risk_parity_sizer(self):
        """Test risk parity sizer"""
        sizer = RiskParitySizer(
            target_risk_percent=0.02,
            lot_size=100,
            default_volatility=0.02
        )

        shares = sizer.calculate_position_size(
            price=10.0,
            available_capital=500000,
            total_equity=1000000
        )

        # Target risk = 1M * 0.02 = 20k
        # Position value = 20k / 0.02 = 1M
        # But capped at max_percent (30%) = 300k
        # 300k / 10 = 30000 shares
        assert shares == 30000

    def test_risk_parity_with_volatility(self):
        """Test risk parity with custom volatility"""
        sizer = RiskParitySizer(
            target_risk_percent=0.02,
            lot_size=100,
            default_volatility=0.02
        )

        signal_data = {'volatility': 0.04}  # Higher volatility

        shares = sizer.calculate_position_size(
            price=10.0,
            available_capital=500000,
            total_equity=1000000,
            signal_data=signal_data
        )

        # Target risk = 20k
        # Position value = 20k / 0.04 = 500k
        # But capped at 300k
        # 300k / 10 = 30000 shares
        assert shares == 30000

    def test_volatility_target_sizer(self):
        """Test volatility target sizer"""
        sizer = VolatilityTargetSizer(
            target_volatility=0.15,
            lot_size=100,
            default_volatility=0.02
        )

        shares = sizer.calculate_position_size(
            price=10.0,
            available_capital=500000,
            total_equity=1000000
        )

        # Position weight = 0.15 / 0.02 = 7.5
        # But capped at max_percent (30%)
        # Position = 1M * 0.3 = 300k
        # 300k / 10 = 30000 shares
        assert shares == 30000

    def test_position_sizer_factory(self):
        """Test position sizer factory"""
        sizer1 = create_position_sizer('fixed', fixed_amount=100000)
        assert isinstance(sizer1, FixedPositionSizer)

        sizer2 = create_position_sizer('percent', percent=0.1)
        assert isinstance(sizer2, FixedPercentSizer)

        sizer3 = create_position_sizer('kelly', win_rate=0.6, profit_loss_ratio=2.0)
        assert isinstance(sizer3, KellyPositionSizer)

        with pytest.raises(ValueError):
            create_position_sizer('invalid')


# ==================== Report Generator Tests ====================

class TestBacktestReportGenerator:
    """Test backtest report generator"""

    def test_generate_report_basic(self):
        """Test basic report generation"""
        generator = BacktestReportGenerator(risk_free_rate=0.03)

        equity_curve = [
            {'date': '2024-01-01', 'total_equity': 1000000, 'cash': 1000000, 'position_value': 0, 'return_pct': 0.0, 'drawdown': 0.0},
            {'date': '2024-01-02', 'total_equity': 1010000, 'cash': 500000, 'position_value': 510000, 'return_pct': 0.01, 'drawdown': 0.0},
            {'date': '2024-01-03', 'total_equity': 1020000, 'cash': 500000, 'position_value': 520000, 'return_pct': 0.02, 'drawdown': 0.0},
        ]

        trades = [
            {
                'symbol': '000001',
                'entry_date': '2024-01-01',
                'entry_price': 10.0,
                'exit_date': '2024-01-03',
                'exit_price': 10.5,
                'shares': 10000,
                'profit': 5000,
                'profit_pct': 0.05,
                'holding_days': 2,
                'entry_reason': 'signal',
                'exit_reason': 'signal'
            }
        ]

        report = generator.generate_report(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1000000,
            start_date='2024-01-01',
            end_date='2024-01-03',
            strategy_name='TestStrategy'
        )

        assert report['strategy_name'] == 'TestStrategy'
        assert 'metrics' in report
        assert 'equity_curve' in report
        assert 'trades' in report
        assert 'summary' in report

        metrics = report['metrics']
        assert metrics['total_return'] == 0.02
        assert metrics['total_trades'] == 1
        assert metrics['win_rate'] == 1.0
        assert metrics['initial_capital'] == 1000000
        assert metrics['final_capital'] == 1020000

    def test_calculate_drawdown(self):
        """Test drawdown calculation"""
        generator = BacktestReportGenerator()

        equity_curve = [
            {'date': '2024-01-01', 'total_equity': 1000000, 'cash': 1000000, 'position_value': 0, 'return_pct': 0.0, 'drawdown': 0.0},
            {'date': '2024-01-02', 'total_equity': 1100000, 'cash': 500000, 'position_value': 600000, 'return_pct': 0.1, 'drawdown': 0.0},
            {'date': '2024-01-03', 'total_equity': 1050000, 'cash': 500000, 'position_value': 550000, 'return_pct': 0.05, 'drawdown': -0.045},
            {'date': '2024-01-04', 'total_equity': 1000000, 'cash': 500000, 'position_value': 500000, 'return_pct': 0.0, 'drawdown': -0.091},
        ]

        report = generator.generate_report(
            equity_curve=equity_curve,
            trades=[],
            initial_capital=1000000,
            start_date='2024-01-01',
            end_date='2024-01-04',
            strategy_name='TestStrategy'
        )

        metrics = report['metrics']
        # Max drawdown from peak 1.1M to 1M = -9.09%
        assert metrics['max_drawdown'] < -0.09
        assert metrics['max_drawdown'] > -0.1

    def test_trade_statistics(self):
        """Test trade statistics calculation"""
        generator = BacktestReportGenerator()

        trades = [
            {'profit': 1000, 'holding_days': 5},
            {'profit': 2000, 'holding_days': 3},
            {'profit': -500, 'holding_days': 2},
            {'profit': 1500, 'holding_days': 4},
            {'profit': -300, 'holding_days': 1},
        ]

        equity_curve = [
            {'date': '2024-01-01', 'total_equity': 1000000, 'cash': 1000000, 'position_value': 0, 'return_pct': 0.0, 'drawdown': 0.0},
            {'date': '2024-01-10', 'total_equity': 1003700, 'cash': 1003700, 'position_value': 0, 'return_pct': 0.0037, 'drawdown': 0.0},
        ]

        report = generator.generate_report(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=1000000,
            start_date='2024-01-01',
            end_date='2024-01-10',
            strategy_name='TestStrategy'
        )

        metrics = report['metrics']
        assert metrics['total_trades'] == 5
        assert metrics['winning_trades'] == 3
        assert metrics['losing_trades'] == 2
        assert metrics['win_rate'] == 0.6
        assert metrics['avg_win'] == pytest.approx(1500.0, rel=0.01)
        assert metrics['avg_loss'] == pytest.approx(-400.0, rel=0.01)
        assert metrics['avg_holding_days'] == 3.0

    def test_empty_report(self):
        """Test report with no data"""
        generator = BacktestReportGenerator()

        report = generator.generate_report(
            equity_curve=[],
            trades=[],
            initial_capital=1000000,
            start_date='2024-01-01',
            end_date='2024-01-10',
            strategy_name='TestStrategy'
        )

        metrics = report['metrics']
        assert metrics['total_return'] == 0.0
        assert metrics['total_trades'] == 0
        assert metrics['sharpe_ratio'] == 0.0
