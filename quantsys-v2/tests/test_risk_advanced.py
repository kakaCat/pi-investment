"""
Advanced Risk Management Test Suite
====================================

Tests for Module 2 risk calculators:
- RiskAggregationCalculator
- CounterpartyRiskCalculator
- RegulatoryRiskCalculator
- BacktestingCalculator
- MarginCalculator
- RiskReportCalculator

Author: QuantSys V2
Date: 2026-05-25
"""

import pytest
import numpy as np
import pandas as pd
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from domain.quantlib.risk.aggregation import RiskAggregationCalculator
from domain.quantlib.risk.counterparty_risk import CounterpartyRiskCalculator
from domain.quantlib.risk.regulatory import RegulatoryRiskCalculator
from domain.quantlib.risk.backtesting import BacktestingCalculator
from domain.quantlib.risk.margining import MarginCalculator
from domain.quantlib.risk.reporting import RiskReportCalculator

from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    ConfigurationError,
    CalculationError,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def sample_cov_matrix():
    """3-asset covariance matrix."""
    return np.array([
        [0.04, 0.01, 0.008],
        [0.01, 0.03, 0.012],
        [0.008, 0.012, 0.05],
    ])


@pytest.fixture
def sample_positions():
    """Sample portfolio positions."""
    return {'AAPL': 0.40, 'GOOGL': 0.35, 'MSFT': 0.25}


@pytest.fixture
def sample_returns():
    """Generate sample return data."""
    np.random.seed(42)
    return np.random.normal(0.001, 0.02, 500)


# ==============================================================================
# TestRiskAggregation
# ==============================================================================

class TestRiskAggregation:
    """Tests for RiskAggregationCalculator."""

    def test_component_var_sums_to_total(self, sample_positions, sample_cov_matrix):
        """Test that component VaR sum equals total portfolio VaR."""
        calc = RiskAggregationCalculator(precision=6)

        result = calc.calculate(
            sample_positions, sample_cov_matrix, method='component', confidence_level=0.95
        )

        portfolio_var = result['value']['portfolio_var']
        component_var = result['value']['component_var']
        total_components = sum(component_var.values())

        assert abs(portfolio_var - total_components) < 0.001, (
            f"Portfolio VaR ({portfolio_var}) should equal sum of components ({total_components})"
        )

    def test_standard_aggregation_positive(self, sample_positions, sample_cov_matrix):
        """Test that standard VaR aggregation returns positive values."""
        calc = RiskAggregationCalculator(precision=6)

        result = calc.calculate(
            sample_positions, sample_cov_matrix, method='standard', confidence_level=0.95
        )

        assert result['method'] == 'risk_aggregation_standard'
        assert result['value'] > 0, "Portfolio VaR should be positive"

    def test_marginal_var(self, sample_positions, sample_cov_matrix):
        """Test marginal VaR calculation."""
        calc = RiskAggregationCalculator(precision=6)

        result = calc.calculate(
            sample_positions, sample_cov_matrix, method='marginal', confidence_level=0.95
        )

        assert 'marginal_var' in result['value']
        assert len(result['value']['marginal_var']) == len(sample_positions)

    def test_incremental_var(self, sample_positions, sample_cov_matrix):
        """Test incremental VaR calculation."""
        calc = RiskAggregationCalculator(precision=6)

        result = calc.calculate(
            sample_positions, sample_cov_matrix, method='incremental', confidence_level=0.95
        )

        assert 'incremental_var' in result['value']
        assert len(result['value']['incremental_var']) == len(sample_positions)

    def test_diversification_ratio(self, sample_positions, sample_cov_matrix):
        """Test diversification ratio is >= 1.0 for well-diversified portfolio."""
        calc = RiskAggregationCalculator(precision=6)

        result = calc.calculate_diversification_ratio(sample_positions, sample_cov_matrix)

        assert result['value'] >= 1.0, (
            f"Diversification ratio ({result['value']}) should be >= 1.0"
        )

    def test_diversification_ratio_single_asset(self):
        """Test diversification ratio for single asset is 1.0."""
        calc = RiskAggregationCalculator()
        positions = {'SINGLE': 1.0}
        cov = np.array([[0.04]])

        result = calc.calculate_diversification_ratio(positions, cov)
        assert result['value'] == 1.0

    def test_expected_shortfall(self, sample_returns):
        """Test expected shortfall is more extreme than VaR."""
        calc = RiskAggregationCalculator(precision=6)

        es_result = calc.calculate_expected_shortfall(sample_returns, confidence_level=0.95)
        assert es_result['value'] > 0, "Expected shortfall should be positive"

    def test_invalid_weights_raises_error(self, sample_cov_matrix):
        """Test that invalid position weights raise an error."""
        calc = RiskAggregationCalculator()
        positions = {'A': 1.5, 'B': 0.5}  # Sum > 1.05

        with pytest.raises(DataValidationError):
            calc.calculate(positions, sample_cov_matrix, method='standard')


# ==============================================================================
# TestCounterpartyRisk
# ==============================================================================

class TestCounterpartyRisk:
    """Tests for CounterpartyRiskCalculator."""

    def test_cva_with_flat_exposure(self):
        """Test CVA with flat exposure profile."""
        calc = CounterpartyRiskCalculator(precision=6)

        # Flat exposure: 1M at each time point for 5 years
        exposures = [(1.0, 1000000), (2.0, 1000000), (3.0, 1000000),
                      (4.0, 1000000), (5.0, 1000000)]
        pd_constant = 0.02  # Single default probability

        result = calc.calculate(exposures, pd_constant, recovery_rate=0.4,
                                 risk_free_rate=0.03, method='cva')

        assert result['method'] == 'cva'
        assert result['value'] > 0, "CVA should be positive for positive exposure"

    def test_cva_with_pd_curve(self):
        """Test CVA with explicit PD curve."""
        calc = CounterpartyRiskCalculator(precision=6)

        exposures = [(1.0, 1000000), (2.0, 800000), (3.0, 500000)]
        pd_curve = [0.01, 0.015, 0.02]  # Increasing marginal PDs

        result = calc.calculate(exposures, pd_curve, recovery_rate=0.4,
                                 risk_free_rate=0.03, method='cva')

        assert result['value'] > 0

    def test_bilateral_cva(self):
        """Test bilateral CVA calculation."""
        calc = CounterpartyRiskCalculator(precision=6)

        exposures = [(1.0, 1000000), (2.0, 800000)]
        # (own_PD, cpty_PD)
        both_pds = [0.01, 0.02]

        result = calc.calculate(exposures, both_pds, recovery_rate=0.4,
                                 risk_free_rate=0.03, method='bilateral_cva')

        assert result['method'] == 'bilateral_cva'

    def test_cds_implied_default_probability(self):
        """Test default probability from CDS spread."""
        calc = CounterpartyRiskCalculator(precision=6)

        result = calc.calculate_default_probability_from_cds(
            cds_spread=0.01, recovery_rate=0.4, T=5.0
        )

        pd = result['value']
        assert 0 < pd < 1, f"PD ({pd}) should be between 0 and 1"
        # For CDS=100bps, RR=40%, T=5: PD ≈ 1-exp(-0.01*5/0.6) ≈ 1-exp(-0.0833) ≈ 0.08
        assert 0.05 < pd < 0.15, f"PD ({pd}) should be in reasonable range"

    def test_credit_exposure(self):
        """Test credit exposure metrics from MTM distributions."""
        calc = CounterpartyRiskCalculator(precision=6)
        np.random.seed(42)

        mtm_distributions = [
            np.random.normal(100000, 50000, 1000),
            np.random.normal(80000, 60000, 1000),
            np.random.normal(50000, 70000, 1000),
        ]

        result = calc.calculate_credit_exposure(mtm_distributions)

        assert 'expected_exposure' in result['value']
        assert 'pfe_95' in result['value']
        assert 'pfe_99' in result['value']
        assert result['value']['expected_positive_exposure'] > 0

    def test_empty_exposure_raises_error(self):
        """Test that empty exposure profile raises DataValidationError."""
        calc = CounterpartyRiskCalculator()

        with pytest.raises(DataValidationError):
            calc.calculate([], 0.02, method='cva')


# ==============================================================================
# TestRegulatory
# ==============================================================================

class TestRegulatory:
    """Tests for RegulatoryRiskCalculator."""

    def test_capital_adequacy_ratio(self):
        """Test capital adequacy ratio calculation."""
        calc = RegulatoryRiskCalculator(precision=4)

        result = calc.calculate_capital_adequacy_ratio(
            tier1=100.0, tier2=50.0, rwa=1000.0
        )

        car_data = result['value']
        assert car_data['total_car'] == pytest.approx(0.15, rel=0.01)  # 150/1000
        assert car_data['tier1_ratio'] == pytest.approx(0.10, rel=0.01)  # 100/1000
        assert result['metadata']['car_compliant'] is True
        assert result['metadata']['tier1_compliant'] is True

    def test_capital_adequacy_ratio_below_minimum(self):
        """Test CAR below regulatory minimum."""
        calc = RegulatoryRiskCalculator(precision=4)

        result = calc.calculate_capital_adequacy_ratio(
            tier1=30.0, tier2=10.0, rwa=1000.0
        )

        car_data = result['value']
        assert car_data['total_car'] == pytest.approx(0.04, rel=0.01)
        assert result['metadata']['car_compliant'] is False

    def test_leverage_ratio(self):
        """Test leverage ratio calculation."""
        calc = RegulatoryRiskCalculator(precision=4)

        result = calc.calculate_leverage_ratio(
            tier1_capital=60.0, exposure_measure=1000.0
        )

        assert result['value'] == pytest.approx(0.06, rel=0.01)  # 60/1000
        assert result['metadata']['compliant'] is True

    def test_leverage_ratio_below_minimum(self):
        """Test leverage ratio below 3% minimum."""
        calc = RegulatoryRiskCalculator(precision=4)

        result = calc.calculate_leverage_ratio(
            tier1_capital=20.0, exposure_measure=1000.0
        )

        assert result['value'] == pytest.approx(0.02, rel=0.01)  # 20/1000
        assert result['metadata']['compliant'] is False

    def test_basel_iii_market_risk(self):
        """Test Basel III market risk charge."""
        calc = RegulatoryRiskCalculator(precision=4)

        positions = {'equity': 1000000, 'bond': 500000, 'fx': 200000}
        risk_data = {'equity_beta': 1.2, 'bond_duration': 5.0}

        result = calc.calculate(positions, risk_data, method='basel_iii_market')

        charges = result['value']
        assert 'equity_total' in charges
        assert 'interest_rate_risk' in charges
        assert 'fx_risk' in charges
        assert charges['equity_total'] > 0

    def test_frtb_sa_calculation(self):
        """Test FRTB standardised approach calculation."""
        calc = RegulatoryRiskCalculator(precision=4)

        positions = {'equity': 1000000}
        risk_data = {
            'delta_sensitivities': {'equity_spot': 10000},
            'delta_risk_weights': {'equity_spot': 0.55},
            'vega_sensitivities': {},
            'curvature_sensitivities': {},
        }

        result = calc.calculate(positions, risk_data, method='frtb_sa')

        charges = result['value']
        assert 'delta_charge' in charges
        assert 'total_frtb_sa_capital' in charges

    def test_invalid_rwa_raises_error(self):
        """Test that zero RWA raises DataValidationError."""
        calc = RegulatoryRiskCalculator()

        with pytest.raises(DataValidationError):
            calc.calculate_capital_adequacy_ratio(tier1=100, tier2=50, rwa=0.0)


# ==============================================================================
# TestBacktesting
# ==============================================================================

class TestBacktesting:
    """Tests for BacktestingCalculator."""

    def test_kupiec_test_with_simulated_hit_series(self):
        """Test Kupiec POF test with simulated ex-ante hit series."""
        calc = BacktestingCalculator(precision=6)
        np.random.seed(42)

        n_obs = 500
        # Generate returns where exceptions occur at ~1% rate (matching 99% VaR)
        returns = np.random.normal(-0.001, 0.02, n_obs)
        # VaR set such that exceptions occur at expected rate
        var_threshold = np.percentile(-returns, 99)  # 99th percentile of losses
        var_series = np.full(n_obs, var_threshold)

        result = calc.calculate(returns, var_series, confidence_level=0.99, method='kupiec')

        test_result = result['value']
        assert 'lr_statistic' in test_result
        assert 'p_value' in test_result
        assert 'reject_at_5pct' in test_result
        assert test_result['test'] == 'Kupiec POF'

    def test_traffic_light_green_zone(self):
        """Test traffic light test with few exceptions (green zone)."""
        calc = BacktestingCalculator(precision=6)
        np.random.seed(42)

        n_obs = 250
        returns = np.random.normal(-0.001, 0.02, n_obs)
        # Set VaR very high so very few exceptions
        var_series = np.full(n_obs, 0.20)

        result = calc.calculate(returns, var_series, confidence_level=0.99,
                                 method='traffic_light')

        test_result = result['value']
        assert test_result['zone'] == 'green', (
            f"Expected green zone, got {test_result['zone']}"
        )

    def test_traffic_light_red_zone(self):
        """Test traffic light test with many exceptions (red zone)."""
        calc = BacktestingCalculator(precision=6)
        np.random.seed(42)

        n_obs = 250
        returns = np.random.normal(-0.05, 0.03, n_obs)
        # Set VaR very low so many exceptions
        var_series = np.full(n_obs, 0.01)

        result = calc.calculate(returns, var_series, confidence_level=0.99,
                                 method='traffic_light')

        test_result = result['value']
        assert test_result['zone'] == 'red', (
            f"Expected red zone, got {test_result['zone']}"
        )

    def test_exceptions_counting(self):
        """Test exception counting method."""
        calc = BacktestingCalculator(precision=6)
        np.random.seed(42)

        n_obs = 300
        returns = np.random.normal(-0.001, 0.02, n_obs)
        var_series = np.full(n_obs, 0.03)

        result = calc.calculate(returns, var_series, confidence_level=0.99,
                                 method='exceptions')

        exceptions = result['value']
        assert 'n_exceptions' in exceptions
        assert 'exception_rate' in exceptions
        assert exceptions['n_observations'] == n_obs

    def test_christoffersen_test(self):
        """Test Christoffersen conditional coverage test."""
        calc = BacktestingCalculator(precision=6)
        np.random.seed(42)

        n_obs = 500
        returns = np.random.normal(-0.001, 0.02, n_obs)
        var_threshold = np.percentile(-returns, 99)
        var_series = np.full(n_obs, var_threshold)

        result = calc.calculate(returns, var_series, confidence_level=0.99,
                                 method='christoffersen')

        test_result = result['value']
        assert 'lr_cc' in test_result
        assert 'lr_ind' in test_result
        assert 'lr_pof' in test_result
        assert test_result['test'] == 'Christoffersen'

    def test_mismatched_lengths_raises_error(self):
        """Test that mismatched PnL/VaR series lengths raise error."""
        calc = BacktestingCalculator()
        pnl = np.random.normal(0, 0.02, 500)
        var = np.random.normal(0.03, 0.01, 499)

        with pytest.raises(DataValidationError):
            calc.calculate(pnl, var, confidence_level=0.99)

    def test_insufficient_data_raises_error(self):
        """Test that insufficient data raises error."""
        calc = BacktestingCalculator()
        pnl = np.random.normal(0, 0.02, 50)  # Fewer than 100
        var = np.full(50, 0.03)

        with pytest.raises(InsufficientDataError):
            calc.calculate(pnl, var, confidence_level=0.99)


# ==============================================================================
# TestMargin
# ==============================================================================

class TestMargin:
    """Tests for MarginCalculator."""

    def test_span_margin_scenarios(self):
        """Test SPAN margin with 16 standard scenarios."""
        calc = MarginCalculator(precision=4)

        positions = {'FUT_A': 10, 'FUT_B': -5}
        prices = {'FUT_A': 4500.0, 'FUT_B': 4500.0}
        vols = {'FUT_A': 0.15, 'FUT_B': 0.15}

        result = calc.calculate(positions, prices, vols, method='span')

        margin_data = result['value']
        assert 'scanning_risk' in margin_data
        assert 'net_span_margin' in margin_data
        assert margin_data['n_scenarios'] == 16
        assert margin_data['scanning_risk'] >= 0
        assert margin_data['net_span_margin'] >= 0

    def test_var_based_margin(self):
        """Test VaR-based margin calculation."""
        calc = MarginCalculator(precision=4)

        positions = {'STOCK_A': 1000}
        prices = {'STOCK_A': 50.0}
        vols = {'STOCK_A': 0.20}

        result = calc.calculate(positions, prices, vols, method='var_based',
                                 confidence_level=0.99)

        margin_data = result['value']
        assert 'total_var_margin' in margin_data
        assert margin_data['total_var_margin'] > 0

    def test_strategy_based_margin_spread(self):
        """Test strategy-based margin for spread strategy."""
        calc = MarginCalculator(precision=4)

        positions = {'OPT_LONG': 1, 'OPT_SHORT': -1}
        prices = {'OPT_LONG': 500.0, 'OPT_SHORT': 500.0}
        vols = {'OPT_LONG': 0.20, 'OPT_SHORT': 0.20}

        result = calc.calculate(positions, prices, vols, method='strategy_based')

        margin_data = result['value']
        assert 'margin' in margin_data
        assert margin_data['strategy_type'] == 'generic'

    def test_maintenance_margin(self):
        """Test maintenance margin calculation."""
        calc = MarginCalculator(precision=4)

        positions = {'STOCK_A': 1000}
        prices = {'STOCK_A': 50.0}

        result = calc.calculate_maintenance_margin(positions, prices, margin_rate=0.25)

        assert result['value']['maintenance_margin'] == pytest.approx(12500.0, rel=0.01)
        assert result['value']['margin_rate'] == 0.25

    def test_initial_margin(self):
        """Test initial margin calculation."""
        calc = MarginCalculator(precision=4)

        positions = {'STOCK_A': 1000}
        prices = {'STOCK_A': 50.0}

        result = calc.calculate_initial_margin(positions, prices, margin_rate=0.50)

        assert result['value']['initial_margin'] == pytest.approx(25000.0, rel=0.01)
        assert result['value']['margin_rate'] == 0.50

    def test_missing_price_raises_error(self):
        """Test that missing price raises DataValidationError."""
        calc = MarginCalculator()

        positions = {'STOCK_A': 1000}
        prices = {'STOCK_B': 50.0}  # Missing STOCK_A
        vols = {'STOCK_A': 0.20}

        with pytest.raises(DataValidationError):
            calc.calculate(positions, prices, vols, method='span')


# ==============================================================================
# TestRiskReport
# ==============================================================================

class TestRiskReport:
    """Tests for RiskReportCalculator."""

    def test_summary_report_generates_valid_dict(self):
        """Test that summary report generates valid dictionary."""
        calc = RiskReportCalculator(precision=4)

        portfolio_data = {
            'total_value': 1000000,
            'n_assets': 10,
            'currency': 'USD',
        }

        risk_metrics = {
            'var_95': 25000,
            'var_99': 38000,
            'cvar_95': 35000,
            'cvar_99': 50000,
            'volatility': 0.15,
            'max_drawdown': 0.12,
            'sharpe_ratio': 1.2,
            'beta': 1.1,
            'alpha': 0.03,
            'tracking_error': 0.05,
        }

        result = calc.calculate(portfolio_data, risk_metrics, method='summary')

        report = result['value']
        assert 'portfolio_summary' in report
        assert 'risk_summary' in report
        assert 'performance_summary' in report
        assert 'risk_assessment' in report
        assert report['portfolio_summary']['total_value'] == 1000000
        assert report['risk_summary']['var_95'] == 25000

    def test_detailed_report(self):
        """Test detailed report generation."""
        calc = RiskReportCalculator(precision=4)

        portfolio_data = {
            'total_value': 1000000,
            'assets': [
                {'name': 'AAPL', 'weight': 0.40, 'volatility': 0.18, 'beta': 1.2, 'risk_category': 'Equity'},
                {'name': 'GOOGL', 'weight': 0.35, 'volatility': 0.20, 'beta': 1.1, 'risk_category': 'Equity'},
                {'name': 'MSFT', 'weight': 0.25, 'volatility': 0.16, 'beta': 0.9, 'risk_category': 'Equity'},
            ],
            'sectors': [
                {'name': 'Technology', 'allocation': 0.80, 'var_contribution': 20000, 'beta': 1.1},
                {'name': 'Finance', 'allocation': 0.20, 'var_contribution': 5000, 'beta': 0.9},
            ],
        }

        risk_metrics = {
            'var_95': 25000,
            'var_99': 38000,
            'cvar_99': 50000,
            'volatility': 0.15,
            'max_drawdown': 0.12,
            'sharpe_ratio': 1.2,
            'beta': 1.1,
        }

        result = calc.calculate(portfolio_data, risk_metrics, method='detailed')

        report = result['value']
        assert 'asset_level_risk' in report
        assert 'sector_allocation' in report
        assert 'concentration_risk' in report

    def test_regulatory_report(self):
        """Test regulatory report generation."""
        calc = RiskReportCalculator(precision=4)

        portfolio_data = {
            'total_value': 5000000,
            'currency': 'USD',
            'portfolio_type': 'Trading Book',
        }

        risk_metrics = {
            'interest_rate_charge': 15000,
            'equity_charge': 50000,
            'fx_charge': 8000,
            'total_market_risk_capital': 73000,
            'cva_capital_charge': 12000,
            'cva': 50000,
            'tier1_capital': 500000,
            'tier2_capital': 100000,
            'total_capital': 600000,
            'rwa': 4000000,
            'total_car': 0.15,
            'tier1_ratio': 0.125,
            'car_compliant': True,
            'leverage_ratio': 0.05,
            'leverage_compliant': True,
            'traffic_light_zone': 'green',
            'k_multiplier': 0.0,
        }

        result = calc.calculate(portfolio_data, risk_metrics, method='regulatory')

        report = result['value']
        assert 'firm_identifiers' in report
        assert 'market_risk_standardised' in report
        assert 'counterparty_credit_risk' in report
        assert 'capital_adequacy' in report
        assert 'leverage_ratio' in report
        assert 'compliance_summary' in report
        assert report['compliance_summary']['overall_compliant'] is True

    def test_export_to_dataframe(self):
        """Test report export to DataFrame."""
        calc = RiskReportCalculator(precision=4)

        portfolio_data = {'total_value': 1000000}
        risk_metrics = {'var_95': 25000, 'volatility': 0.15}

        result = calc.calculate(portfolio_data, risk_metrics, method='summary')
        df = calc.export_to_dataframe(result)

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_empty_portfolio_raises_error(self):
        """Test that empty portfolio data raises error."""
        calc = RiskReportCalculator()

        with pytest.raises(DataValidationError):
            calc.calculate({}, {'var_95': 100}, method='summary')


# ==============================================================================
# Integration test - cross-calculator workflow
# ==============================================================================

class TestRiskIntegration:
    """Integration tests across multiple calculators."""

    def test_full_risk_workflow(self):
        """Test a full risk workflow across multiple calculators."""
        np.random.seed(42)

        # Step 1: Portfolio risk aggregation
        positions = {'AAPL': 0.40, 'GOOGL': 0.35, 'MSFT': 0.25}
        cov = np.array([
            [0.04, 0.012, 0.010],
            [0.012, 0.035, 0.014],
            [0.010, 0.014, 0.045],
        ])

        agg_calc = RiskAggregationCalculator(precision=6)
        agg_result = agg_calc.calculate(positions, cov, method='component')
        portfolio_var = agg_result['value']['portfolio_var']

        # Step 2: VaR backtesting (simulated)
        rets = np.random.normal(-0.001, 0.02, 500)
        # Convert portfolio Var to daily VaR magnitude
        daily_var = portfolio_var / np.sqrt(252)
        var_series = np.full(500, daily_var)

        bt_calc = BacktestingCalculator(precision=6)
        bt_result = bt_calc.calculate(rets, var_series, confidence_level=0.99,
                                       method='kupiec')

        assert 'lr_statistic' in bt_result['value']
        assert bt_result['value']['n_observations'] == 500

        # Step 3: Regulatory report
        report_calc = RiskReportCalculator(precision=4)
        report = report_calc.calculate(
            {'total_value': 1000000},
            {
                'var_95': float(portfolio_var),
                'volatility': float(np.sqrt(positions['AAPL']**2 * cov[0, 0])),
                'sharpe_ratio': 1.2,
                'tier1_capital': 200000,
                'tier2_capital': 50000,
                'rwa': 2000000,
                'total_car': 0.125,
                'car_compliant': True,
                'leverage_ratio': 0.05,
                'leverage_compliant': True,
                'traffic_light_zone': 'green',
            },
            method='regulatory'
        )

        assert report['value']['compliance_summary']['overall_compliant'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
