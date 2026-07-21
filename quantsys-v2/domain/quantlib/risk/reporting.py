"""
Risk Report Calculator
=======================

Risk report generation with summary, detailed, and regulatory report
formats. Provides structured output suitable for front-end display
and regulatory compliance reporting.

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional
from datetime import datetime

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    DataValidationError,
    InsufficientDataError,
    ConfigurationError,
)


class RiskReportCalculator(BaseCalculator):
    """
    Risk report generation calculator.

    Produces structured risk reports in multiple formats:
    - Summary: Key metrics at-a-glance
    - Detailed: Full breakdown by asset/sector/factor
    - Regulatory: Basel/FRTB formatted output

    Example:
        calculator = RiskReportCalculator(precision=4)
        portfolio_data = {
            'total_value': 1000000,
            'assets': [...],
            'returns': [...],
        }
        risk_metrics = {
            'var_95': 25000,
            'cvar_95': 35000,
            'volatility': 0.15,
            ...
        }
        result = calculator.calculate(portfolio_data, risk_metrics, method='summary')
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize risk report calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate for report metrics
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  portfolio_data: Dict[str, Any],
                  risk_metrics: Dict[str, Any],
                  method: str = 'summary') -> Dict[str, Any]:
        """
        Generate risk report.

        Args:
            portfolio_data: Portfolio data dictionary
                Required keys: 'total_value' or 'positions'
                Optional: 'assets', 'sectors', 'returns', 'benchmark'
            risk_metrics: Pre-computed risk metrics dictionary
                Common keys: 'var_95', 'var_99', 'cvar_95', 'cvar_99',
                'volatility', 'sharpe_ratio', 'max_drawdown', 'beta',
                'tracking_error', 'information_ratio'
            method: 'summary', 'detailed', or 'regulatory'

        Returns:
            Dictionary with formatted risk report

        Raises:
            DataValidationError: If required portfolio data is missing
            ConfigurationError: If method is unsupported
            CalculationError: If report generation fails
        """
        method = self.validate_method(method)

        if not portfolio_data:
            raise DataValidationError(
                "Portfolio data cannot be empty",
                field_name='portfolio_data'
            )

        if not risk_metrics:
            raise DataValidationError(
                "Risk metrics cannot be empty",
                field_name='risk_metrics'
            )

        try:
            if method == 'summary':
                report = self._generate_summary_report(portfolio_data, risk_metrics)
            elif method == 'detailed':
                report = self._generate_detailed_report(portfolio_data, risk_metrics)
            elif method == 'regulatory':
                report = self._generate_regulatory_report(portfolio_data, risk_metrics)
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            # Add common report metadata
            report['report_metadata'] = {
                'generated_at': datetime.now().isoformat(),
                'calculator': self.__class__.__name__,
                'report_type': method,
                'precision': self.precision,
            }

            return self._create_result_dict(
                value=report,
                method=f'risk_report_{method}',
                parameters={
                    'method': method,
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                },
                metadata={
                    'sections': list(report.keys())
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError)):
                raise
            raise CalculationError(str(e), calculation_type='RiskReport')

    def _generate_summary_report(self,
                                  portfolio: Dict[str, Any],
                                  metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a summary risk report with key metrics at-a-glance.

        Args:
            portfolio: Portfolio data
            metrics: Risk metrics

        Returns:
            Summary report dictionary
        """
        total_value = portfolio.get('total_value', 0.0)
        if total_value == 0.0 and 'positions' in portfolio:
            positions = portfolio['positions']
            if isinstance(positions, dict):
                total_value = sum(abs(v) for v in positions.values())

        report = {
            'portfolio_summary': {
                'total_value': float(self._round_result(total_value)),
                'n_assets': portfolio.get('n_assets', len(portfolio.get('assets', []))),
                'currency': portfolio.get('currency', 'USD'),
            },
            'risk_summary': {
                'var_95': float(self._round_result(metrics.get('var_95', 0.0))),
                'var_99': float(self._round_result(metrics.get('var_99', 0.0))),
                'cvar_95': float(self._round_result(metrics.get('cvar_95', 0.0))),
                'cvar_99': float(self._round_result(metrics.get('cvar_99', 0.0))),
                'volatility_annual': float(self._round_result(metrics.get('volatility', 0.0))),
                'max_drawdown': float(self._round_result(metrics.get('max_drawdown', 0.0))),
            },
            'performance_summary': {
                'sharpe_ratio': float(self._round_result(metrics.get('sharpe_ratio', 0.0))),
                'sortino_ratio': float(self._round_result(metrics.get('sortino_ratio', 0.0))),
                'information_ratio': float(self._round_result(metrics.get('information_ratio', 0.0))),
                'calmar_ratio': float(self._round_result(metrics.get('calmar_ratio', 0.0))),
                'annual_return': float(self._round_result(metrics.get('annual_return', 0.0))),
            },
            'market_risk': {
                'beta': float(self._round_result(metrics.get('beta', 0.0))),
                'alpha': float(self._round_result(metrics.get('alpha', 0.0))),
                'tracking_error': float(self._round_result(metrics.get('tracking_error', 0.0))),
                'correlation': float(self._round_result(metrics.get('correlation', 0.0))),
            },
            'risk_assessment': self._assess_risk_level(metrics),
        }

        return report

    def _assess_risk_level(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess overall risk level based on key metrics.

        Args:
            metrics: Risk metrics dictionary

        Returns:
            Risk assessment with level and flags
        """
        flags = []
        risk_score = 0

        # Volatility assessment (annualized)
        vol = abs(metrics.get('volatility', 0.0))
        if vol > 0.40:
            flags.append('EXTREME volatility (>40% annual)')
            risk_score += 4
        elif vol > 0.25:
            flags.append('HIGH volatility (>25% annual)')
            risk_score += 3
        elif vol > 0.15:
            flags.append('MODERATE volatility (>15% annual)')
            risk_score += 2
        elif vol > 0.05:
            flags.append('LOW volatility')
            risk_score += 1

        # Drawdown assessment
        max_dd = abs(metrics.get('max_drawdown', 0.0))
        if max_dd > 0.50:
            flags.append('EXTREME maximum drawdown (>50%)')
            risk_score += 4
        elif max_dd > 0.30:
            flags.append('HIGH maximum drawdown (>30%)')
            risk_score += 3
        elif max_dd > 0.15:
            flags.append('MODERATE maximum drawdown (>15%)')
            risk_score += 2
        elif max_dd > 0.05:
            flags.append('LOW maximum drawdown')
            risk_score += 1

        # VaR assessment
        var_99 = abs(metrics.get('var_99', 0.0))
        total_value = metrics.get('total_value', 1.0)  # Used for scaling context
        var_ratio = var_99 / total_value if total_value > 0 else 0.0

        if var_ratio > 0.10:
            flags.append('HIGH VaR relative to portfolio value (>10%)')
            risk_score += 3
        elif var_ratio > 0.05:
            flags.append('MODERATE VaR (>5%)')
            risk_score += 2
        elif var_ratio > 0.01:
            risk_score += 1

        # Sharpe ratio assessment
        sharpe = metrics.get('sharpe_ratio', 0.0)
        if sharpe < 0:
            flags.append('NEGATIVE Sharpe ratio')
            risk_score += 2
        elif sharpe < 0.5:
            flags.append('LOW Sharpe ratio (<0.5)')
            risk_score += 1

        # Determine overall risk level
        if risk_score >= 8:
            level = 'CRITICAL'
            color = 'red'
        elif risk_score >= 5:
            level = 'HIGH'
            color = 'orange'
        elif risk_score >= 3:
            level = 'MODERATE'
            color = 'yellow'
        else:
            level = 'LOW'
            color = 'green'

        return {
            'risk_level': level,
            'risk_score': risk_score,
            'color_code': color,
            'flags': flags,
            'recommendation': (
                'Immediate risk review required' if level == 'CRITICAL' else
                'Active risk monitoring recommended' if level == 'HIGH' else
                'Regular risk monitoring sufficient' if level == 'MODERATE' else
                'Standard risk controls adequate'
            )
        }

    def _generate_detailed_report(self,
                                    portfolio: Dict[str, Any],
                                    metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a detailed risk report with breakdowns by asset/sector/factor.

        Args:
            portfolio: Portfolio data with asset/sector breakdowns
            metrics: Risk metrics

        Returns:
            Detailed report dictionary
        """
        report = {}

        # Start with summary
        summary = self._generate_summary_report(portfolio, metrics)
        report.update(summary)

        # Asset-level risk contribution
        assets = portfolio.get('assets', [])
        if assets:
            asset_risk = []
            for asset in assets:
                if isinstance(asset, dict):
                    asset_risk.append({
                        'name': asset.get('name', 'Unknown'),
                        'weight': float(self._round_result(asset.get('weight', 0.0))),
                        'var_contribution': float(self._round_result(asset.get('var_contribution', 0.0))),
                        'volatility': float(self._round_result(asset.get('volatility', 0.0))),
                        'beta': float(self._round_result(asset.get('beta', 0.0))),
                        'risk_category': asset.get('risk_category', 'N/A'),
                    })
            if asset_risk:
                report['asset_level_risk'] = asset_risk

        # Sector allocation and risk
        sectors = portfolio.get('sectors', [])
        if sectors:
            sector_risk = []
            for sector in sectors:
                if isinstance(sector, dict):
                    sector_risk.append({
                        'sector': sector.get('name', 'Unknown'),
                        'allocation': float(self._round_result(sector.get('allocation', 0.0))),
                        'var_contribution': float(self._round_result(sector.get('var_contribution', 0.0))),
                        'sector_beta': float(self._round_result(sector.get('beta', 0.0))),
                    })
            if sector_risk:
                report['sector_allocation'] = sector_risk

        # Factor exposure analysis
        factors = portfolio.get('factor_exposures', {})
        if factors:
            report['factor_exposures'] = {
                factor: float(self._round_result(exposure))
                for factor, exposure in factors.items()
            }

        # Stress test results
        stress_tests = metrics.get('stress_tests', [])
        if stress_tests:
            report['stress_test_results'] = stress_tests

        # Concentration risk
        concentration_metrics = self._calculate_concentration_risk(portfolio)
        if concentration_metrics:
            report['concentration_risk'] = concentration_metrics

        # Liquidity risk
        liquidity = metrics.get('liquidity_risk', {})
        if liquidity:
            report['liquidity_risk'] = liquidity

        # Tail risk
        tail_risk = {
            'var_99': float(self._round_result(metrics.get('var_99', 0.0))),
            'cvar_99': float(self._round_result(metrics.get('cvar_99', 0.0))),
            'max_drawdown': float(self._round_result(metrics.get('max_drawdown', 0.0))),
            'expected_shortfall': float(self._round_result(metrics.get('expected_shortfall', 0.0))),
            'tail_ratio': float(self._round_result(metrics.get('tail_ratio', 0.0))),
        }
        report['tail_risk'] = tail_risk

        return report

    def _calculate_concentration_risk(self,
                                        portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate concentration risk metrics.

        Herfindahl-Hirschman Index (HHI) and top-N concentration.

        Args:
            portfolio: Portfolio data with asset weights

        Returns:
            Concentration risk metrics
        """
        assets = portfolio.get('assets', [])
        weights = []

        for asset in assets:
            if isinstance(asset, dict):
                w = asset.get('weight', 0.0)
            elif isinstance(asset, (int, float)):
                w = float(asset)
            else:
                continue
            weights.append(abs(w))

        if not weights:
            return {}

        # Normalize weights
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]

        # HHI: sum of squared weights
        hhi = sum(w * w for w in weights)

        # Top-N concentration
        sorted_weights = sorted(weights, reverse=True)
        top3 = sum(sorted_weights[:3]) if len(sorted_weights) >= 3 else sum(sorted_weights)
        top5 = sum(sorted_weights[:5]) if len(sorted_weights) >= 5 else sum(sorted_weights)
        top10 = sum(sorted_weights[:10]) if len(sorted_weights) >= 10 else sum(sorted_weights)

        # Effective N = 1 / HHI
        effective_n = 1.0 / hhi if hhi > 0 else float('inf')

        # Concentration level assessment
        if hhi > 0.25:
            concentration_level = 'HIGH'
        elif hhi > 0.10:
            concentration_level = 'MODERATE'
        else:
            concentration_level = 'LOW'

        return {
            'hhi_index': float(self._round_result(hhi)),
            'effective_n_assets': float(self._round_result(effective_n)),
            'top3_concentration': float(self._round_result(top3)),
            'top5_concentration': float(self._round_result(top5)),
            'top10_concentration': float(self._round_result(top10)),
            'concentration_level': concentration_level,
            'n_assets': len(weights),
        }

    def _generate_regulatory_report(self,
                                      portfolio: Dict[str, Any],
                                      metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a regulatory risk report (Basel/FRTB format).

        Args:
            portfolio: Portfolio data
            metrics: Risk metrics

        Returns:
            Regulatory report dictionary
        """
        report = {}

        # FirFirm and portfolio identifiers
        report['firm_identifiers'] = {
            'report_date': datetime.now().strftime('%Y-%m-%d'),
            'reporting_currency': portfolio.get('currency', 'USD'),
            'portfolio_type': portfolio.get('portfolio_type', 'Trading Book'),
        }

        # Market Risk - Standardised Approach summary
        report['market_risk_standardised'] = {
            'interest_rate_risk': float(self._round_result(metrics.get('interest_rate_charge', 0.0))),
            'equity_position_risk': float(self._round_result(metrics.get('equity_charge', 0.0))),
            'foreign_exchange_risk': float(self._round_result(metrics.get('fx_charge', 0.0))),
            'commodity_risk': float(self._round_result(metrics.get('commodity_charge', 0.0))),
            'total_market_risk_capital': float(self._round_result(metrics.get('total_market_risk_capital', 0.0))),
        }

        # Counterparty Credit Risk
        report['counterparty_credit_risk'] = {
            'cva_capital_charge': float(self._round_result(metrics.get('cva_capital_charge', 0.0))),
            'cva': float(self._round_result(metrics.get('cva', 0.0))),
            'netting_benefit': float(self._round_result(metrics.get('netting_benefit', 0.0))),
        }

        # Capital Adequacy
        report['capital_adequacy'] = {
            'tier1_capital': float(self._round_result(metrics.get('tier1_capital', 0.0))),
            'tier2_capital': float(self._round_result(metrics.get('tier2_capital', 0.0))),
            'total_capital': float(self._round_result(metrics.get('total_capital', 0.0))),
            'risk_weighted_assets': float(self._round_result(metrics.get('rwa', 0.0))),
            'total_car': float(self._round_result(metrics.get('total_car', 0.0))),
            'tier1_ratio': float(self._round_result(metrics.get('tier1_ratio', 0.0))),
            'cet1_ratio': float(self._round_result(metrics.get('cet1_ratio', 0.0))),
            'car_compliant': metrics.get('car_compliant', False),
        }

        # Leverage Ratio
        report['leverage_ratio'] = {
            'tier1_capital': float(self._round_result(metrics.get('tier1_capital', 0.0))),
            'exposure_measure': float(self._round_result(metrics.get('exposure_measure', 0.0))),
            'leverage_ratio': float(self._round_result(metrics.get('leverage_ratio', 0.0))),
            'minimum_required': 0.03,
            'compliant': metrics.get('leverage_compliant', False),
        }

        # VaR Backtesting (for IMA)
        report['var_backtesting'] = {
            'n_exceptions_250d': metrics.get('n_exceptions_250d', 0),
            'traffic_light_zone': metrics.get('traffic_light_zone', 'green'),
            'k_multiplier': float(self._round_result(metrics.get('k_multiplier', 0.0))),
        }

        # Stress Testing
        report['stress_testing'] = {
            'scenarios_run': metrics.get('n_scenarios', 0),
            'worst_case_loss': float(self._round_result(metrics.get('worst_case_loss', 0.0))),
            'scenario_results': metrics.get('stress_test_results', []),
        }

        # Regulatory compliance summary
        report['compliance_summary'] = {
            'car_compliant': metrics.get('car_compliant', False),
            'leverage_compliant': metrics.get('leverage_compliant', False),
            'backtesting_compliant': metrics.get('traffic_light_zone', 'green') == 'green',
            'overall_compliant': (
                metrics.get('car_compliant', False) and
                metrics.get('leverage_compliant', False) and
                metrics.get('traffic_light_zone', 'green') == 'green'
            ),
        }

        return report

    def export_to_dataframe(self, report_dict: Dict[str, Any]) -> pd.DataFrame:
        """
        Export risk report to a flat pandas DataFrame.

        Args:
            report_dict: Report dictionary from calculate()

        Returns:
            Flattened DataFrame with risk metrics
        """
        records = []

        # Extract the value from the result dict if present
        report_value = report_dict.get('value', report_dict)

        # Flatten report sections
        for section, section_data in report_value.items():
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    if not isinstance(value, (dict, list)):
                        records.append({
                            'section': section,
                            'metric': key,
                            'value': value
                        })
                    elif isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict):
                            for i, item in enumerate(value):
                                for k, v in item.items():
                                    records.append({
                                        'section': f'{section}_{key}',
                                        'metric': f'{k}[{i}]',
                                        'value': v
                                    })
                        else:
                            records.append({
                                'section': section,
                                'metric': key,
                                'value': str(value)
                            })

        if not records:
            return pd.DataFrame()

        return pd.DataFrame(records)

    def get_supported_methods(self) -> List[str]:
        """Return list of supported report methods."""
        return ['summary', 'detailed', 'regulatory']
