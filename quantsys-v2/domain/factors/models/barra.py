"""
Barra Risk Model
================

Implementation of Barra-style multi-factor risk model for portfolio risk analysis.

Components:
    - Industry factors
    - Style factors (size, value, momentum, volatility, etc.)
    - Factor covariance matrix
    - Specific risk (idiosyncratic risk)

Reference:
    Barra Risk Model Handbook (MSCI Barra)

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Union, Tuple
from scipy import stats
from scipy.linalg import lstsq

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    CalculationError,
    ModelFitError
)


class BarraRiskModelCalculator(BaseCalculator):
    """
    Barra Risk Model Calculator

    Multi-factor risk model that decomposes portfolio risk into:
        - Factor risk (systematic risk from industry and style factors)
        - Specific risk (idiosyncratic risk)

    Total Risk² = X' * F * X + Δ

    Where:
        - X: Factor exposures
        - F: Factor covariance matrix
        - Δ: Specific risk variance

    Example:
        calculator = BarraRiskModelCalculator()
        result = calculator.calculate(
            returns=stock_returns,
            factor_exposures=exposures,
            industry_exposures=industries
        )
        print(f"Factor Risk: {result['value']['factor_risk']}")
        print(f"Specific Risk: {result['value']['specific_risk']}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Barra risk model calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Default risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  returns: pd.DataFrame,
                  factor_exposures: pd.DataFrame,
                  industry_exposures: Optional[pd.DataFrame] = None,
                  portfolio_weights: Optional[pd.Series] = None,
                  return_factor_returns: bool = False) -> Dict[str, Any]:
        """
        Calculate Barra risk model decomposition.

        Args:
            returns: DataFrame of stock returns (stocks x time)
            factor_exposures: DataFrame of style factor exposures (stocks x factors)
            industry_exposures: DataFrame of industry exposures (stocks x industries)
            portfolio_weights: Portfolio weights (if None, equal-weighted)
            return_factor_returns: Whether to return factor return series

        Returns:
            Dictionary containing:
                - factor_risk: Factor contribution to risk
                - specific_risk: Specific (idiosyncratic) risk
                - total_risk: Total portfolio risk
                - factor_covariance: Factor covariance matrix
                - specific_variance: Specific variance for each stock
                - factor_returns: Factor return series (if return_factor_returns=True)

        Raises:
            DataValidationError: If input data is invalid
            InsufficientDataError: If not enough observations
            ModelFitError: If model fitting fails
        """
        # Validate inputs
        if returns.empty:
            raise DataValidationError("returns DataFrame is empty", field_name="returns")

        if factor_exposures.empty:
            raise DataValidationError("factor_exposures DataFrame is empty", field_name="factor_exposures")

        # Check stock alignment
        common_stocks = returns.index.intersection(factor_exposures.index)
        if len(common_stocks) == 0:
            raise DataValidationError(
                "No common stocks between returns and factor_exposures",
                field_name="stock_alignment"
            )

        returns = returns.loc[common_stocks]
        factor_exposures = factor_exposures.loc[common_stocks]

        if industry_exposures is not None:
            industry_exposures = industry_exposures.loc[common_stocks]

        # Check minimum observations
        n_periods = returns.shape[1]
        if n_periods < 30:
            raise InsufficientDataError(
                required=30,
                provided=n_periods,
                calculation="barra_risk_model"
            )

        # Combine style and industry factors
        if industry_exposures is not None:
            all_exposures = pd.concat([factor_exposures, industry_exposures], axis=1)
        else:
            all_exposures = factor_exposures

        # Standardize factor exposures (cross-sectional z-score)
        exposures_standardized = all_exposures.copy()
        for col in exposures_standardized.columns:
            mean = exposures_standardized[col].mean()
            std = exposures_standardized[col].std()
            if std > 0:
                exposures_standardized[col] = (exposures_standardized[col] - mean) / std

        # Estimate factor returns using cross-sectional regression
        factor_returns_list = []

        for period in returns.columns:
            period_returns = returns[period].dropna()
            common = period_returns.index.intersection(exposures_standardized.index)

            if len(common) < len(all_exposures.columns) + 5:
                factor_returns_list.append(pd.Series(np.nan, index=all_exposures.columns))
                continue

            y = period_returns[common].values
            X = exposures_standardized.loc[common].values

            try:
                # Cross-sectional regression: r_i = X_i * f + ε_i
                coeffs, _, _, _ = lstsq(X, y)
                factor_returns_list.append(pd.Series(coeffs, index=all_exposures.columns))
            except Exception:
                factor_returns_list.append(pd.Series(np.nan, index=all_exposures.columns))

        factor_returns_df = pd.DataFrame(factor_returns_list, index=returns.columns)

        # Calculate factor covariance matrix
        factor_cov = factor_returns_df.cov()

        # Calculate specific returns (residuals)
        specific_returns = pd.DataFrame(index=returns.index, columns=returns.columns)

        for period in returns.columns:
            period_returns = returns[period]
            factor_ret = factor_returns_df.loc[period]

            if factor_ret.isna().any():
                specific_returns[period] = np.nan
                continue

            # Predicted returns from factors
            predicted = exposures_standardized @ factor_ret

            # Specific returns = actual - predicted
            specific_returns[period] = period_returns - predicted

        # Calculate specific variance for each stock
        specific_variance = specific_returns.var(axis=1)

        # Portfolio risk calculation
        if portfolio_weights is None:
            # Equal-weighted portfolio
            portfolio_weights = pd.Series(1.0 / len(common_stocks), index=common_stocks)
        else:
            portfolio_weights = portfolio_weights.loc[common_stocks]
            # Normalize weights
            portfolio_weights = portfolio_weights / portfolio_weights.sum()

        # Portfolio factor exposures
        portfolio_exposures = exposures_standardized.T @ portfolio_weights

        # Factor risk: sqrt(X' * F * X)
        factor_variance = portfolio_exposures.T @ factor_cov @ portfolio_exposures
        factor_risk = np.sqrt(factor_variance)

        # Specific risk: sqrt(w' * Δ * w)
        specific_variance_portfolio = (portfolio_weights ** 2) @ specific_variance
        specific_risk = np.sqrt(specific_variance_portfolio)

        # Total risk
        total_variance = factor_variance + specific_variance_portfolio
        total_risk = np.sqrt(total_variance)

        # Build result
        result_value = {
            'factor_risk': float(factor_risk),
            'specific_risk': float(specific_risk),
            'total_risk': float(total_risk),
            'factor_variance': float(factor_variance),
            'specific_variance': float(specific_variance_portfolio),
            'total_variance': float(total_variance),
            'factor_contribution_pct': float(factor_variance / total_variance * 100),
            'specific_contribution_pct': float(specific_variance_portfolio / total_variance * 100),
            'factor_covariance': factor_cov.to_dict(),
            'portfolio_exposures': portfolio_exposures.to_dict(),
            'n_factors': len(all_exposures.columns),
            'n_stocks': len(common_stocks)
        }

        if return_factor_returns:
            result_value['factor_returns'] = factor_returns_df.to_dict()

        return self._create_result_dict(
            value=result_value,
            method='barra_risk_model',
            parameters={
                'n_observations': n_periods,
                'n_stocks': len(common_stocks),
                'n_style_factors': len(factor_exposures.columns),
                'n_industry_factors': len(industry_exposures.columns) if industry_exposures is not None else 0,
                'return_factor_returns': return_factor_returns
            },
            metadata={
                'model': 'Barra Risk Model',
                'style_factors': list(factor_exposures.columns),
                'industry_factors': list(industry_exposures.columns) if industry_exposures is not None else []
            }
        )

    def calculate_marginal_risk(self,
                                 returns: pd.DataFrame,
                                 factor_exposures: pd.DataFrame,
                                 portfolio_weights: pd.Series,
                                 industry_exposures: Optional[pd.DataFrame] = None) -> pd.Series:
        """
        Calculate marginal contribution to risk for each stock.

        Args:
            returns: Stock returns DataFrame
            factor_exposures: Style factor exposures
            portfolio_weights: Current portfolio weights
            industry_exposures: Industry exposures (optional)

        Returns:
            Series of marginal risk contributions
        """
        # Get base risk calculation
        base_result = self.calculate(
            returns=returns,
            factor_exposures=factor_exposures,
            industry_exposures=industry_exposures,
            portfolio_weights=portfolio_weights
        )

        base_risk = base_result['value']['total_risk']

        # Calculate marginal risk for each stock
        marginal_risks = {}

        for stock in portfolio_weights.index:
            # Create perturbed weights (small increase in this stock)
            epsilon = 0.0001
            perturbed_weights = portfolio_weights.copy()
            perturbed_weights[stock] += epsilon

            # Renormalize
            perturbed_weights = perturbed_weights / perturbed_weights.sum()

            # Calculate risk with perturbed weights
            perturbed_result = self.calculate(
                returns=returns,
                factor_exposures=factor_exposures,
                industry_exposures=industry_exposures,
                portfolio_weights=perturbed_weights
            )

            perturbed_risk = perturbed_result['value']['total_risk']

            # Marginal risk = (perturbed_risk - base_risk) / epsilon
            marginal_risk = (perturbed_risk - base_risk) / epsilon
            marginal_risks[stock] = marginal_risk

        return pd.Series(marginal_risks)


class BarraFactorBuilder:
    """
    Builder for constructing Barra-style factors.

    Style Factors:
        - Size: Log of market capitalization
        - Value: Book-to-market ratio
        - Momentum: Past 12-month return (skipping most recent month)
        - Volatility: Historical volatility
        - Liquidity: Trading volume / shares outstanding
        - Growth: Earnings growth rate
        - Leverage: Debt-to-equity ratio

    Example:
        builder = BarraFactorBuilder()
        factors = builder.build_style_factors(
            market_caps=market_caps,
            book_values=book_values,
            returns=returns,
            volumes=volumes
        )
    """

    def __init__(self):
        """Initialize Barra factor builder."""
        pass

    def build_size_factor(self, market_caps: pd.Series) -> pd.Series:
        """
        Build size factor (log market cap).

        Args:
            market_caps: Market capitalizations

        Returns:
            Size factor values
        """
        return np.log(market_caps)

    def build_value_factor(self,
                           book_values: pd.Series,
                           market_caps: pd.Series) -> pd.Series:
        """
        Build value factor (book-to-market).

        Args:
            book_values: Book values
            market_caps: Market capitalizations

        Returns:
            Value factor values
        """
        return book_values / market_caps

    def build_momentum_factor(self,
                               returns: pd.DataFrame,
                               lookback_months: int = 12,
                               skip_months: int = 1) -> pd.Series:
        """
        Build momentum factor (cumulative past returns).

        Args:
            returns: Returns DataFrame (stocks x time)
            lookback_months: Number of months to look back
            skip_months: Number of recent months to skip

        Returns:
            Momentum factor values
        """
        if returns.shape[1] < lookback_months + skip_months:
            raise InsufficientDataError(
                required=lookback_months + skip_months,
                provided=returns.shape[1],
                calculation="momentum_factor"
            )

        # Use returns from [t-lookback-skip] to [t-skip]
        momentum_returns = returns.iloc[:, -(lookback_months + skip_months):-skip_months]

        # Calculate cumulative returns
        cum_returns = (1 + momentum_returns).prod(axis=1) - 1

        return cum_returns

    def build_volatility_factor(self,
                                 returns: pd.DataFrame,
                                 lookback_months: int = 12) -> pd.Series:
        """
        Build volatility factor (historical volatility).

        Args:
            returns: Returns DataFrame
            lookback_months: Number of months for volatility calculation

        Returns:
            Volatility factor values
        """
        if returns.shape[1] < lookback_months:
            raise InsufficientDataError(
                required=lookback_months,
                provided=returns.shape[1],
                calculation="volatility_factor"
            )

        # Use most recent lookback_months
        recent_returns = returns.iloc[:, -lookback_months:]

        # Calculate standard deviation
        volatility = recent_returns.std(axis=1)

        return volatility

    def build_liquidity_factor(self,
                                volumes: pd.DataFrame,
                                shares_outstanding: pd.Series) -> pd.Series:
        """
        Build liquidity factor (turnover ratio).

        Args:
            volumes: Trading volumes DataFrame
            shares_outstanding: Shares outstanding

        Returns:
            Liquidity factor values
        """
        # Average daily turnover
        avg_volume = volumes.mean(axis=1)
        turnover = avg_volume / shares_outstanding

        return turnover

    def build_growth_factor(self,
                            earnings: pd.DataFrame,
                            lookback_periods: int = 4) -> pd.Series:
        """
        Build growth factor (earnings growth rate).

        Args:
            earnings: Earnings DataFrame (stocks x time)
            lookback_periods: Number of periods for growth calculation

        Returns:
            Growth factor values
        """
        if earnings.shape[1] < lookback_periods + 1:
            raise InsufficientDataError(
                required=lookback_periods + 1,
                provided=earnings.shape[1],
                calculation="growth_factor"
            )

        # Current earnings
        current = earnings.iloc[:, -1]

        # Past earnings
        past = earnings.iloc[:, -(lookback_periods + 1)]

        # Growth rate
        growth = (current - past) / past.abs()

        return growth

    def build_leverage_factor(self,
                               total_debt: pd.Series,
                               total_equity: pd.Series) -> pd.Series:
        """
        Build leverage factor (debt-to-equity).

        Args:
            total_debt: Total debt
            total_equity: Total equity

        Returns:
            Leverage factor values
        """
        leverage = total_debt / total_equity
        return leverage

    def build_style_factors(self,
                            market_caps: pd.Series,
                            book_values: pd.Series,
                            returns: pd.DataFrame,
                            volumes: Optional[pd.DataFrame] = None,
                            shares_outstanding: Optional[pd.Series] = None,
                            earnings: Optional[pd.DataFrame] = None,
                            total_debt: Optional[pd.Series] = None,
                            total_equity: Optional[pd.Series] = None) -> pd.DataFrame:
        """
        Build all available style factors.

        Args:
            market_caps: Market capitalizations
            book_values: Book values
            returns: Returns DataFrame
            volumes: Trading volumes (optional)
            shares_outstanding: Shares outstanding (optional)
            earnings: Earnings DataFrame (optional)
            total_debt: Total debt (optional)
            total_equity: Total equity (optional)

        Returns:
            DataFrame of style factors
        """
        factors = {}

        # Always available factors
        factors['Size'] = self.build_size_factor(market_caps)
        factors['Value'] = self.build_value_factor(book_values, market_caps)
        factors['Momentum'] = self.build_momentum_factor(returns)
        factors['Volatility'] = self.build_volatility_factor(returns)

        # Optional factors
        if volumes is not None and shares_outstanding is not None:
            factors['Liquidity'] = self.build_liquidity_factor(volumes, shares_outstanding)

        if earnings is not None:
            factors['Growth'] = self.build_growth_factor(earnings)

        if total_debt is not None and total_equity is not None:
            factors['Leverage'] = self.build_leverage_factor(total_debt, total_equity)

        return pd.DataFrame(factors)

    def build_industry_factors(self,
                                industry_classifications: pd.Series,
                                industry_list: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Build industry dummy variables.

        Args:
            industry_classifications: Series mapping stocks to industries
            industry_list: List of industries to include (if None, use all)

        Returns:
            DataFrame of industry dummy variables
        """
        if industry_list is None:
            industry_list = industry_classifications.unique().tolist()

        # Create dummy variables
        industry_dummies = pd.DataFrame(0, index=industry_classifications.index, columns=industry_list)

        for stock, industry in industry_classifications.items():
            if industry in industry_list:
                industry_dummies.loc[stock, industry] = 1

        return industry_dummies
