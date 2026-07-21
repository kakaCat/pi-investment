"""
Risk Management Module
======================

Comprehensive risk management and analysis tools for QuantSys V2.

Basic Modules:
    - var: Value at Risk calculations (historical, parametric, Monte Carlo)
    - cvar: Conditional Value at Risk (Expected Shortfall)
    - attribution: Risk attribution and decomposition
    - stress_test: Stress testing and scenario analysis
    - drawdown: Drawdown analysis and metrics
    - market_risk: Market risk measures (Beta, correlation, tracking error)

Advanced Modules:
    - stress_testing: Advanced stress testing (multi-factor, reverse stress)
    - scenario_analysis: Comprehensive scenario analysis
    - extreme_value: Extreme Value Theory for tail risk
    - copula: Copula models for dependence structure
    - liquidity_risk: Liquidity risk and liquidation cost analysis

Risk Management Module 2 (Advanced):
    - aggregation: Portfolio risk aggregation (component, marginal, incremental VaR)
    - counterparty_risk: Counterparty risk and XVA (CVA, DVA, BCVA, FVA)
    - regulatory: Basel III / FRTB regulatory capital calculations
    - backtesting: VaR backtesting statistical tests (Kupiec, Christoffersen, traffic light)
    - margining: Margin calculations (SPAN, VaR-based, strategy-based)
    - reporting: Risk report generation (summary, detailed, regulatory)

Usage:
    # Basic risk metrics
    from domain.quantlib.risk import VaRCalculator, CVaRCalculator
    from domain.quantlib.risk import DrawdownCalculator, MarketRiskCalculator

    # Advanced risk analytics
    from domain.quantlib.risk import AdvancedStressTestCalculator, ScenarioAnalysisCalculator
    from domain.quantlib.risk import ExtremeValueCalculator, CopulaCalculator
    from domain.quantlib.risk import LiquidityRiskCalculator

    # Risk Management Module 2
    from domain.quantlib.risk import RiskAggregationCalculator, CounterpartyRiskCalculator
    from domain.quantlib.risk import RegulatoryRiskCalculator, BacktestingCalculator
    from domain.quantlib.risk import MarginCalculator, RiskReportCalculator
"""

from .var import VaRCalculator
from .cvar import CVaRCalculator
from .attribution import RiskAttributionCalculator
from .stress_test import StressTestCalculator
from .drawdown import DrawdownCalculator
from .market_risk import MarketRiskCalculator

# Advanced risk modules
from .stress_testing import AdvancedStressTestCalculator, StressScenario
from .scenario_analysis import ScenarioAnalysisCalculator, MarketScenario
from .extreme_value import ExtremeValueCalculator
from .copula import CopulaCalculator
from .liquidity_risk import LiquidityRiskCalculator

# Risk Management Module 2
from .aggregation import RiskAggregationCalculator
from .counterparty_risk import CounterpartyRiskCalculator
from .regulatory import RegulatoryRiskCalculator
from .backtesting import BacktestingCalculator
from .margining import MarginCalculator
from .reporting import RiskReportCalculator

__all__ = [
    # Basic modules
    'VaRCalculator',
    'CVaRCalculator',
    'RiskAttributionCalculator',
    'StressTestCalculator',
    'DrawdownCalculator',
    'MarketRiskCalculator',
    # Advanced modules
    'AdvancedStressTestCalculator',
    'StressScenario',
    'ScenarioAnalysisCalculator',
    'MarketScenario',
    'ExtremeValueCalculator',
    'CopulaCalculator',
    'LiquidityRiskCalculator',
    # Risk Management Module 2
    'RiskAggregationCalculator',
    'CounterpartyRiskCalculator',
    'RegulatoryRiskCalculator',
    'BacktestingCalculator',
    'MarginCalculator',
    'RiskReportCalculator',
]
