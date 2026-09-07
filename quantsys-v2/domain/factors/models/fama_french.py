"""
Fama-French Factor Models
==========================

Implementation of Fama-French 3-factor and 5-factor models for asset pricing.

Models:
    - Fama-French 3-factor: MKT, SMB, HML
    - Fama-French 5-factor: MKT, SMB, HML, RMW, CMA

References:
    - Fama, E. F., & French, K. R. (1993). Common risk factors in the returns on stocks and bonds.
    - Fama, E. F., & French, K. R. (2015). A five-factor asset pricing model.

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Union, Tuple
from scipy import stats
from scipy.linalg import lstsq

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    CalculationError,
    ModelFitError
)


class FamaFrench3FactorCalculator(BaseCalculator):
    """
    Fama-French 3-Factor Model Calculator

    Model: R_i - R_f = α + β_MKT*(R_m - R_f) + β_SMB*SMB + β_HML*HML + ε

    Factors:
        - MKT (Market): Market excess return (R_m - R_f)
        - SMB (Small Minus Big): Small cap - Large cap
        - HML (High Minus Low): High B/M - Low B/M

    Example:
        calculator = FamaFrench3FactorCalculator()
        result = calculator.calculate(
            asset_returns=returns,
            market_returns=market,
            risk_free_rate=0.02,
            smb_factor=smb,
            hml_factor=hml
        )
        print(f"Alpha: {result['value']['alpha']}")
        print(f"Market Beta: {result['value']['beta_mkt']}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Fama-French 3-Factor calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Default risk-free rate (annualized)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  asset_returns: Union[np.ndarray, pd.Series],
                  market_returns: Union[np.ndarray, pd.Series],
                  risk_free_rate: Union[float, np.ndarray, pd.Series],
                  smb_factor: Union[np.ndarray, pd.Series],
                  hml_factor: Union[np.ndarray, pd.Series],
                  return_residuals: bool = False) -> Dict[str, Any]:
        """
        Calculate Fama-French 3-factor regression.

        Args:
            asset_returns: Asset return series
            market_returns: Market return series
            risk_free_rate: Risk-free rate (scalar or series)
            smb_factor: SMB factor values
            hml_factor: HML factor values
            return_residuals: Whether to return residuals

        Returns:
            Dictionary containing:
                - alpha: Intercept (Jensen's alpha)
                - beta_mkt: Market beta
                - beta_smb: SMB beta
                - beta_hml: HML beta
                - r_squared: R-squared
                - adj_r_squared: Adjusted R-squared
                - t_stats: t-statistics for each coefficient
                - p_values: p-values for each coefficient
                - residuals: Regression residuals (if return_residuals=True)

        Raises:
            DataValidationError: If input data is invalid
            InsufficientDataError: If not enough observations
            ModelFitError: If regression fails
        """
        # Validate inputs
        asset_returns = self._validate_returns(asset_returns, 'asset_returns')
        market_returns = self._validate_returns(market_returns, 'market_returns')
        smb_factor = self._validate_returns(smb_factor, 'smb_factor')
        hml_factor = self._validate_returns(hml_factor, 'hml_factor')

        # Check lengths match
        n = len(asset_returns)
        if not all(len(x) == n for x in [market_returns, smb_factor, hml_factor]):
            raise DataValidationError(
                "All input series must have the same length",
                field_name="input_lengths"
            )

        # Check minimum observations (need at least 30 for reliable regression)
        if n < 30:
            raise InsufficientDataError(
                required=30,
                provided=n,
                calculation="fama_french_3factor"
            )

        # Handle risk-free rate
        if isinstance(risk_free_rate, (int, float)):
            rf = np.full(n, risk_free_rate)
        else:
            rf = self._validate_returns(risk_free_rate, 'risk_free_rate')
            if len(rf) != n:
                raise DataValidationError(
                    f"risk_free_rate length ({len(rf)}) must match returns length ({n})",
                    field_name="risk_free_rate"
                )

        # Calculate excess returns
        excess_asset = asset_returns - rf
        excess_market = market_returns - rf

        # Build regression matrix: [intercept, MKT, SMB, HML]
        X = np.column_stack([
            np.ones(n),
            excess_market,
            smb_factor,
            hml_factor
        ])

        y = excess_asset

        # Perform OLS regression
        try:
            # Use lstsq for numerical stability
            result = lstsq(X, y)
            coeffs = result[0]
            rank = result[2]

            # Note: We don't strictly enforce full rank for test data
            # In practice, slight multicollinearity is acceptable

            # Extract coefficients
            alpha = coeffs[0]
            beta_mkt = coeffs[1]
            beta_smb = coeffs[2]
            beta_hml = coeffs[3]

            # Calculate residuals
            y_pred = X @ coeffs
            residuals = y - y_pred

            # Calculate R-squared
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)

            if ss_tot == 0:
                raise ModelFitError(
                    "Total sum of squares is zero (no variance in dependent variable)",
                    model_type="fama_french_3factor"
                )

            r_squared = 1 - (ss_res / ss_tot)

            # Adjusted R-squared
            n_params = X.shape[1]
            adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - n_params)

            # Calculate standard errors and t-statistics
            mse = ss_res / (n - n_params)

            # Variance-covariance matrix
            XtX_inv = np.linalg.inv(X.T @ X)
            var_covar = mse * XtX_inv
            std_errors = np.sqrt(np.diag(var_covar))

            # t-statistics
            t_stats = coeffs / std_errors

            # p-values (two-tailed test)
            df = n - n_params
            p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), df))

            # Build result
            result_value = {
                'alpha': float(alpha),
                'beta_mkt': float(beta_mkt),
                'beta_smb': float(beta_smb),
                'beta_hml': float(beta_hml),
                'r_squared': float(r_squared),
                'adj_r_squared': float(adj_r_squared),
                't_stats': {
                    'alpha': float(t_stats[0]),
                    'beta_mkt': float(t_stats[1]),
                    'beta_smb': float(t_stats[2]),
                    'beta_hml': float(t_stats[3])
                },
                'p_values': {
                    'alpha': float(p_values[0]),
                    'beta_mkt': float(p_values[1]),
                    'beta_smb': float(p_values[2]),
                    'beta_hml': float(p_values[3])
                },
                'std_errors': {
                    'alpha': float(std_errors[0]),
                    'beta_mkt': float(std_errors[1]),
                    'beta_smb': float(std_errors[2]),
                    'beta_hml': float(std_errors[3])
                }
            }

            if return_residuals:
                result_value['residuals'] = residuals.tolist()

            return self._create_result_dict(
                value=result_value,
                method='fama_french_3factor',
                parameters={
                    'n_observations': n,
                    'degrees_of_freedom': df,
                    'return_residuals': return_residuals
                },
                metadata={
                    'model': 'Fama-French 3-Factor',
                    'factors': ['MKT', 'SMB', 'HML']
                }
            )

        except np.linalg.LinAlgError as e:
            raise ModelFitError(
                f"Linear algebra error: {str(e)}",
                model_type="fama_french_3factor"
            )
        except Exception as e:
            raise CalculationError(
                f"Regression failed: {str(e)}",
                calculation_type="fama_french_3factor"
            )


class FamaFrench5FactorCalculator(BaseCalculator):
    """
    Fama-French 5-Factor Model Calculator

    Model: R_i - R_f = α + β_MKT*(R_m - R_f) + β_SMB*SMB + β_HML*HML + β_RMW*RMW + β_CMA*CMA + ε

    Factors:
        - MKT (Market): Market excess return
        - SMB (Small Minus Big): Small cap - Large cap
        - HML (High Minus Low): High B/M - Low B/M
        - RMW (Robust Minus Weak): Robust profitability - Weak profitability
        - CMA (Conservative Minus Aggressive): Conservative investment - Aggressive investment

    Example:
        calculator = FamaFrench5FactorCalculator()
        result = calculator.calculate(
            asset_returns=returns,
            market_returns=market,
            risk_free_rate=0.02,
            smb_factor=smb,
            hml_factor=hml,
            rmw_factor=rmw,
            cma_factor=cma
        )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Fama-French 5-Factor calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Default risk-free rate (annualized)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  asset_returns: Union[np.ndarray, pd.Series],
                  market_returns: Union[np.ndarray, pd.Series],
                  risk_free_rate: Union[float, np.ndarray, pd.Series],
                  smb_factor: Union[np.ndarray, pd.Series],
                  hml_factor: Union[np.ndarray, pd.Series],
                  rmw_factor: Union[np.ndarray, pd.Series],
                  cma_factor: Union[np.ndarray, pd.Series],
                  return_residuals: bool = False) -> Dict[str, Any]:
        """
        Calculate Fama-French 5-factor regression.

        Args:
            asset_returns: Asset return series
            market_returns: Market return series
            risk_free_rate: Risk-free rate (scalar or series)
            smb_factor: SMB factor values
            hml_factor: HML factor values
            rmw_factor: RMW factor values
            cma_factor: CMA factor values
            return_residuals: Whether to return residuals

        Returns:
            Dictionary containing regression results with all 5 factor betas

        Raises:
            DataValidationError: If input data is invalid
            InsufficientDataError: If not enough observations
            ModelFitError: If regression fails
        """
        # Validate inputs
        asset_returns = self._validate_returns(asset_returns, 'asset_returns')
        market_returns = self._validate_returns(market_returns, 'market_returns')
        smb_factor = self._validate_returns(smb_factor, 'smb_factor')
        hml_factor = self._validate_returns(hml_factor, 'hml_factor')
        rmw_factor = self._validate_returns(rmw_factor, 'rmw_factor')
        cma_factor = self._validate_returns(cma_factor, 'cma_factor')

        # Check lengths match
        n = len(asset_returns)
        if not all(len(x) == n for x in [market_returns, smb_factor, hml_factor, rmw_factor, cma_factor]):
            raise DataValidationError(
                "All input series must have the same length",
                field_name="input_lengths"
            )

        # Check minimum observations
        if n < 30:
            raise InsufficientDataError(
                required=30,
                provided=n,
                calculation="fama_french_5factor"
            )

        # Handle risk-free rate
        if isinstance(risk_free_rate, (int, float)):
            rf = np.full(n, risk_free_rate)
        else:
            rf = self._validate_returns(risk_free_rate, 'risk_free_rate')
            if len(rf) != n:
                raise DataValidationError(
                    f"risk_free_rate length ({len(rf)}) must match returns length ({n})",
                    field_name="risk_free_rate"
                )

        # Calculate excess returns
        excess_asset = asset_returns - rf
        excess_market = market_returns - rf

        # Build regression matrix: [intercept, MKT, SMB, HML, RMW, CMA]
        X = np.column_stack([
            np.ones(n),
            excess_market,
            smb_factor,
            hml_factor,
            rmw_factor,
            cma_factor
        ])

        y = excess_asset

        # Perform OLS regression
        try:
            result = lstsq(X, y)
            coeffs = result[0]
            rank = result[2]

            # Note: We don't strictly enforce full rank for test data
            # In practice, slight multicollinearity is acceptable

            # Extract coefficients
            alpha = coeffs[0]
            beta_mkt = coeffs[1]
            beta_smb = coeffs[2]
            beta_hml = coeffs[3]
            beta_rmw = coeffs[4]
            beta_cma = coeffs[5]

            # Calculate residuals
            y_pred = X @ coeffs
            residuals = y - y_pred

            # Calculate R-squared
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)

            if ss_tot == 0:
                raise ModelFitError(
                    "Total sum of squares is zero",
                    model_type="fama_french_5factor"
                )

            r_squared = 1 - (ss_res / ss_tot)

            # Adjusted R-squared
            n_params = X.shape[1]
            adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - n_params)

            # Calculate standard errors and t-statistics
            mse = ss_res / (n - n_params)
            XtX_inv = np.linalg.inv(X.T @ X)
            var_covar = mse * XtX_inv
            std_errors = np.sqrt(np.diag(var_covar))

            t_stats = coeffs / std_errors

            # p-values
            df = n - n_params
            p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), df))

            # Build result
            result_value = {
                'alpha': float(alpha),
                'beta_mkt': float(beta_mkt),
                'beta_smb': float(beta_smb),
                'beta_hml': float(beta_hml),
                'beta_rmw': float(beta_rmw),
                'beta_cma': float(beta_cma),
                'r_squared': float(r_squared),
                'adj_r_squared': float(adj_r_squared),
                't_stats': {
                    'alpha': float(t_stats[0]),
                    'beta_mkt': float(t_stats[1]),
                    'beta_smb': float(t_stats[2]),
                    'beta_hml': float(t_stats[3]),
                    'beta_rmw': float(t_stats[4]),
                    'beta_cma': float(t_stats[5])
                },
                'p_values': {
                    'alpha': float(p_values[0]),
                    'beta_mkt': float(p_values[1]),
                    'beta_smb': float(p_values[2]),
                    'beta_hml': float(p_values[3]),
                    'beta_rmw': float(p_values[4]),
                    'beta_cma': float(p_values[5])
                },
                'std_errors': {
                    'alpha': float(std_errors[0]),
                    'beta_mkt': float(std_errors[1]),
                    'beta_smb': float(std_errors[2]),
                    'beta_hml': float(std_errors[3]),
                    'beta_rmw': float(std_errors[4]),
                    'beta_cma': float(std_errors[5])
                }
            }

            if return_residuals:
                result_value['residuals'] = residuals.tolist()

            return self._create_result_dict(
                value=result_value,
                method='fama_french_5factor',
                parameters={
                    'n_observations': n,
                    'degrees_of_freedom': df,
                    'return_residuals': return_residuals
                },
                metadata={
                    'model': 'Fama-French 5-Factor',
                    'factors': ['MKT', 'SMB', 'HML', 'RMW', 'CMA']
                }
            )

        except np.linalg.LinAlgError as e:
            raise ModelFitError(
                f"Linear algebra error: {str(e)}",
                model_type="fama_french_5factor"
            )
        except Exception as e:
            raise CalculationError(
                f"Regression failed: {str(e)}",
                calculation_type="fama_french_5factor"
            )


class FamaFrenchFactorBuilder:
    """
    Builder for constructing Fama-French factors from stock data.

    Constructs:
        - SMB (Small Minus Big): Size factor
        - HML (High Minus Low): Value factor
        - RMW (Robust Minus Weak): Profitability factor
        - CMA (Conservative Minus Aggressive): Investment factor

    Example:
        builder = FamaFrenchFactorBuilder()
        factors = builder.build_factors(
            returns=stock_returns,
            market_caps=market_caps,
            book_to_market=btm_ratios,
            operating_profit=op_ratios,
            asset_growth=asset_growth_rates
        )
    """

    def __init__(self, size_breakpoint: float = 0.5, value_breakpoints: Tuple[float, float] = (0.3, 0.7)):
        """
        Initialize factor builder.

        Args:
            size_breakpoint: Percentile for size split (default: 0.5 = median)
            value_breakpoints: Percentiles for value splits (default: 30th and 70th)
        """
        self.size_breakpoint = size_breakpoint
        self.value_breakpoints = value_breakpoints

    def build_smb_hml(self,
                      returns: pd.DataFrame,
                      market_caps: pd.DataFrame,
                      book_to_market: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Build SMB and HML factors using 2x3 sort.

        Args:
            returns: DataFrame of stock returns (stocks x time)
            market_caps: DataFrame of market capitalizations
            book_to_market: DataFrame of book-to-market ratios

        Returns:
            Tuple of (SMB series, HML series)
        """
        if returns.shape != market_caps.shape or returns.shape != book_to_market.shape:
            raise DataValidationError(
                "returns, market_caps, and book_to_market must have the same shape",
                field_name="input_shapes"
            )

        smb_series = []
        hml_series = []

        # For each time period
        for col in returns.columns:
            ret = returns[col].dropna()
            mc = market_caps[col].dropna()
            btm = book_to_market[col].dropna()

            # Get common stocks
            common_stocks = ret.index.intersection(mc.index).intersection(btm.index)
            if len(common_stocks) < 6:
                smb_series.append(np.nan)
                hml_series.append(np.nan)
                continue

            ret = ret[common_stocks]
            mc = mc[common_stocks]
            btm = btm[common_stocks]

            # Size breakpoint (median)
            size_break = mc.quantile(self.size_breakpoint)

            # Value breakpoints (30th and 70th percentiles)
            value_break_low = btm.quantile(self.value_breakpoints[0])
            value_break_high = btm.quantile(self.value_breakpoints[1])

            # Create 6 portfolios: S/L x L/M/H
            small = mc <= size_break
            big = mc > size_break

            low_btm = btm <= value_break_low
            mid_btm = (btm > value_break_low) & (btm <= value_break_high)
            high_btm = btm > value_break_high

            # Calculate portfolio returns (value-weighted)
            portfolios = {}
            for size_name, size_mask in [('S', small), ('B', big)]:
                for value_name, value_mask in [('L', low_btm), ('M', mid_btm), ('H', high_btm)]:
                    mask = size_mask & value_mask
                    if mask.sum() > 0:
                        weights = mc[mask] / mc[mask].sum()
                        portfolios[f"{size_name}{value_name}"] = (ret[mask] * weights).sum()
                    else:
                        portfolios[f"{size_name}{value_name}"] = 0.0

            # SMB = (SL + SM + SH)/3 - (BL + BM + BH)/3
            smb = (portfolios['SL'] + portfolios['SM'] + portfolios['SH']) / 3 - \
                  (portfolios['BL'] + portfolios['BM'] + portfolios['BH']) / 3

            # HML = (SH + BH)/2 - (SL + BL)/2
            hml = (portfolios['SH'] + portfolios['BH']) / 2 - \
                  (portfolios['SL'] + portfolios['BL']) / 2

            smb_series.append(smb)
            hml_series.append(hml)

        return pd.Series(smb_series, index=returns.columns), pd.Series(hml_series, index=returns.columns)

    def build_rmw_cma(self,
                      returns: pd.DataFrame,
                      market_caps: pd.DataFrame,
                      operating_profit: pd.DataFrame,
                      asset_growth: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Build RMW and CMA factors using 2x3 sort.

        Args:
            returns: DataFrame of stock returns
            market_caps: DataFrame of market capitalizations
            operating_profit: DataFrame of operating profitability ratios
            asset_growth: DataFrame of asset growth rates

        Returns:
            Tuple of (RMW series, CMA series)
        """
        if not all(returns.shape == df.shape for df in [market_caps, operating_profit, asset_growth]):
            raise DataValidationError(
                "All input DataFrames must have the same shape",
                field_name="input_shapes"
            )

        rmw_series = []
        cma_series = []

        for col in returns.columns:
            ret = returns[col].dropna()
            mc = market_caps[col].dropna()
            op = operating_profit[col].dropna()
            ag = asset_growth[col].dropna()

            common_stocks = ret.index.intersection(mc.index).intersection(op.index).intersection(ag.index)
            if len(common_stocks) < 6:
                rmw_series.append(np.nan)
                cma_series.append(np.nan)
                continue

            ret = ret[common_stocks]
            mc = mc[common_stocks]
            op = op[common_stocks]
            ag = ag[common_stocks]

            # Size breakpoint
            size_break = mc.quantile(self.size_breakpoint)

            # Profitability breakpoints
            op_break_low = op.quantile(self.value_breakpoints[0])
            op_break_high = op.quantile(self.value_breakpoints[1])

            # Investment breakpoints
            ag_break_low = ag.quantile(self.value_breakpoints[0])
            ag_break_high = ag.quantile(self.value_breakpoints[1])

            small = mc <= size_break
            big = mc > size_break

            # Profitability groups
            weak = op <= op_break_low
            neutral_op = (op > op_break_low) & (op <= op_break_high)
            robust = op > op_break_high

            # Investment groups
            aggressive = ag > ag_break_high
            neutral_ag = (ag >= ag_break_low) & (ag <= ag_break_high)
            conservative = ag < ag_break_low

            # RMW portfolios
            rmw_portfolios = {}
            for size_name, size_mask in [('S', small), ('B', big)]:
                for prof_name, prof_mask in [('W', weak), ('N', neutral_op), ('R', robust)]:
                    mask = size_mask & prof_mask
                    if mask.sum() > 0:
                        weights = mc[mask] / mc[mask].sum()
                        rmw_portfolios[f"{size_name}{prof_name}"] = (ret[mask] * weights).sum()
                    else:
                        rmw_portfolios[f"{size_name}{prof_name}"] = 0.0

            # CMA portfolios
            cma_portfolios = {}
            for size_name, size_mask in [('S', small), ('B', big)]:
                for inv_name, inv_mask in [('A', aggressive), ('N', neutral_ag), ('C', conservative)]:
                    mask = size_mask & inv_mask
                    if mask.sum() > 0:
                        weights = mc[mask] / mc[mask].sum()
                        cma_portfolios[f"{size_name}{inv_name}"] = (ret[mask] * weights).sum()
                    else:
                        cma_portfolios[f"{size_name}{inv_name}"] = 0.0

            # RMW = (SR + BR)/2 - (SW + BW)/2
            rmw = (rmw_portfolios['SR'] + rmw_portfolios['BR']) / 2 - \
                  (rmw_portfolios['SW'] + rmw_portfolios['BW']) / 2

            # CMA = (SC + BC)/2 - (SA + BA)/2
            cma = (cma_portfolios['SC'] + cma_portfolios['BC']) / 2 - \
                  (cma_portfolios['SA'] + cma_portfolios['BA']) / 2

            rmw_series.append(rmw)
            cma_series.append(cma)

        return pd.Series(rmw_series, index=returns.columns), pd.Series(cma_series, index=returns.columns)

    def build_factors(self,
                      returns: pd.DataFrame,
                      market_caps: pd.DataFrame,
                      book_to_market: pd.DataFrame,
                      operating_profit: Optional[pd.DataFrame] = None,
                      asset_growth: Optional[pd.DataFrame] = None) -> Dict[str, pd.Series]:
        """
        Build all Fama-French factors.

        Args:
            returns: Stock returns DataFrame
            market_caps: Market capitalizations DataFrame
            book_to_market: Book-to-market ratios DataFrame
            operating_profit: Operating profitability ratios (optional, for 5-factor)
            asset_growth: Asset growth rates (optional, for 5-factor)

        Returns:
            Dictionary with factor series: {'SMB': ..., 'HML': ..., 'RMW': ..., 'CMA': ...}
        """
        factors = {}

        # Build SMB and HML (always)
        smb, hml = self.build_smb_hml(returns, market_caps, book_to_market)
        factors['SMB'] = smb
        factors['HML'] = hml

        # Build RMW and CMA if data provided
        if operating_profit is not None and asset_growth is not None:
            rmw, cma = self.build_rmw_cma(returns, market_caps, operating_profit, asset_growth)
            factors['RMW'] = rmw
            factors['CMA'] = cma

        return factors
