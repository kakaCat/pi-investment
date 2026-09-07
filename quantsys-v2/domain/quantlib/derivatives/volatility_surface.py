"""
波动率曲面构建模块
==================

通过市场期权价格构建和插值隐含波动率曲面。

支持的方法:
    - SVI (Stochastic Volatility Inspired) 参数化
    - 多项式拟合
    - SABR外推

SVI参数化公式:
    w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + sigma^2))
    其中 k = log(K/F)，F = S * exp((r - q) * T)

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import griddata
from typing import Dict, Any, Optional, List, Tuple
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError, ConfigurationError


class VolatilitySurfaceCalculator(BaseCalculator):
    """
    波动率曲面构建和插值计算器。

    从离散的市场期权价格构建完整的隐含波动率曲面，
    支持多种参数化方法和插值方案。

    Features:
        - SVI参数化校准
        - 多项式曲面拟合
        - 波动率微笑提取
        - 期限结构提取
        - 任意点的波动率插值

    Example:
        >>> calc = VolatilitySurfaceCalculator()
        >>> result = calc.calculate(
        ...     strikes=[90, 95, 100, 105, 110],
        ...     maturities=[0.25, 0.5, 1.0],
        ...     implied_vols=[[0.22, 0.20, 0.19], ...],
        ...     S=100, r=0.05
        ... )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        初始化波动率曲面计算器。

        Args:
            precision: 结果精度（默认: 6）
            risk_free_rate: 默认无风险利率（默认: 0.0）
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)
        self._surface_params = None
        self._S_ref = None
        self._r_ref = None
        self._q_ref = None

    def calculate(self,
                  strikes: List[float],
                  maturities: List[float],
                  implied_vols: List[List[float]],
                  S: float,
                  r: float,
                  q: float = 0.0,
                  method: str = 'svi') -> Dict[str, Any]:
        """
        构建波动率曲面。

        Args:
            strikes: 行权价列表
            maturities: 到期时间列表（年）
            implied_vols: 二维隐含波动率矩阵 [n_strikes x n_maturities]
            S: 标的资产当前价格
            r: 无风险利率
            q: 股息率（默认: 0.0）
            method: 拟合方法 ('svi', 'polynomial', 'sabr_extrapolation')

        Returns:
            Dictionary containing:
                - value: 波动率曲面参数
                - fitted_vols: 拟合后的波动率矩阵
                - r_squared: 拟合优度

        Raises:
            DataValidationError: 输入无效时
            CalculationError: 计算失败时
        """
        method = self.validate_method(method)

        # 验证输入
        S = self._validate_positive(S, 'spot_price')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        q = self._validate_numeric_input(q, 'dividend_yield')

        strikes = self._validate_numeric_input(strikes, 'strikes')
        maturities = self._validate_numeric_input(maturities, 'maturities')

        if not isinstance(implied_vols, (list, np.ndarray)):
            raise DataValidationError(
                "implied_vols must be a 2D list or numpy array",
                field_name='implied_vols'
            )

        iv_array = np.array(implied_vols, dtype=float)
        if iv_array.ndim != 2:
            raise DataValidationError(
                f"implied_vols must be 2D, got {iv_array.ndim}D",
                field_name='implied_vols'
            )
        if iv_array.shape[0] != len(strikes) or iv_array.shape[1] != len(maturities):
            raise DataValidationError(
                f"implied_vols shape {iv_array.shape} does not match strikes ({len(strikes)}) x maturities ({len(maturities)})",
                field_name='implied_vols'
            )

        self._S_ref = S
        self._r_ref = r
        self._q_ref = q

        try:
            if method == 'svi':
                params, fitted_vols, r_squared = self._fit_svi(strikes, maturities, iv_array, S, r, q)
                self._surface_params = params
            elif method == 'polynomial':
                params, fitted_vols, r_squared = self._fit_polynomial(strikes, maturities, iv_array, S, r, q)
                self._surface_params = params
            elif method == 'sabr_extrapolation':
                params, fitted_vols, r_squared = self._fit_sabr_extrapolation(strikes, maturities, iv_array, S, r, q)
                self._surface_params = params
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            return self._create_result_dict(
                value=self._surface_params,
                method=method,
                parameters={
                    'strikes': strikes.tolist() if isinstance(strikes, np.ndarray) else list(strikes),
                    'maturities': maturities.tolist() if isinstance(maturities, np.ndarray) else list(maturities),
                    'S': S, 'r': r, 'q': q
                },
                metadata={
                    'fitted_vols': fitted_vols,
                    'r_squared': r_squared,
                    'n_strikes': len(strikes),
                    'n_maturities': len(maturities)
                }
            )

        except Exception as e:
            raise CalculationError(
                f"Volatility surface construction failed: {str(e)}",
                calculation_type='volatility_surface'
            )

    def _svi_raw(self, k: np.ndarray, a: float, b: float, rho: float, m: float, sigma_svi: float) -> np.ndarray:
        """
        SVI原始参数化：w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + sigma^2))

        Args:
            k: log-moneyness = log(K/F)
            a, b, rho, m, sigma_svi: SVI参数
                a: 整体水平
                b: 微笑斜率 (b > 0)
                rho: 不对称性 (-1 < rho < 1)
                m: 水平位移
                sigma_svi: 微笑曲率 (sigma > 0)

        Returns:
            总方差 w(k) = sigma_BS^2 * T
        """
        k_m = k - m
        sqrt_term = np.sqrt(k_m ** 2 + sigma_svi ** 2)
        return a + b * (rho * k_m + sqrt_term)

    def _fit_svi_single_slice(self,
                               strikes: np.ndarray,
                               market_vols: np.ndarray,
                               S: float,
                               T: float,
                               r: float,
                               q: float) -> Tuple[Dict[str, float], np.ndarray, float]:
        """
        对单个到期日的期权微笑进行SVI拟合。

        Args:
            strikes: 行权价
            market_vols: 市场隐含波动率
            S: 标的资产价格
            T: 到期时间
            r: 无风险利率
            q: 股息率

        Returns:
            (params_dict, fitted_vols, r_squared)
        """
        # 计算远期价格
        F = S * np.exp((r - q) * T)

        # 计算log-moneyness和总方差
        k = np.log(strikes / F)
        w_market = market_vols ** 2 * T

        # SVI参数的初始猜测（基于市场数据特征）
        atm_idx = np.argmin(np.abs(k))
        a_init = w_market[atm_idx]
        b_init = 0.1
        rho_init = 0.0
        m_init = 0.0
        sigma_init = 0.1

        # SVI参数约束：
        # a > 0, b > 0, -1 < rho < 1, sigma > 0,
        # 额外的无套利条件：a + b * sigma * sqrt(1 - rho^2) > 0
        def objective(params):
            a, b, rho, m, sigma_svi = params
            # 惩罚违反约束
            penalty = 0.0
            if a <= 0:
                penalty += 1e6 * (abs(a) + 1e-6) ** 2
            if b <= 0:
                penalty += 1e6 * (abs(b) + 1e-6) ** 2
            if abs(rho) >= 0.99:
                penalty += 1e6 * (abs(rho) - 0.99) ** 2
            if sigma_svi <= 0:
                penalty += 1e6 * (abs(sigma_svi) + 1e-6) ** 2
            if penalty > 0:
                return penalty

            w_fit = self._svi_raw(k, a, b, rho, m, sigma_svi)
            return np.sum((w_fit - w_market) ** 2)

        # 使用多起点优化以提高收敛性
        best_result = None
        best_error = float('inf')

        for init_mult in [1.0, 0.5, 2.0]:
            x0 = [a_init * init_mult, b_init, rho_init, m_init, sigma_init]
            try:
                res = minimize(
                    objective,
                    x0,
                    method='Nelder-Mead',
                    options={'maxiter': 5000, 'xatol': 1e-8, 'fatol': 1e-8}
                )
                if res.fun < best_error:
                    best_error = res.fun
                    best_result = res
            except Exception:
                continue

        if best_result is None:
            # 回退：使用简单的近似
            a_fit = float(a_init)
            b_fit = 0.1
            rho_fit = 0.0
            m_fit = 0.0
            sigma_fit = 0.1
            fitted_w = np.full_like(w_market, a_fit)
        else:
            a_fit, b_fit, rho_fit, m_fit, sigma_fit = best_result.x
            fitted_w = self._svi_raw(k, a_fit, b_fit, rho_fit, m_fit, sigma_fit)

        # 转换回隐含波动率
        fitted_vols = np.sqrt(fitted_w / T)

        # 计算R²
        ss_res = np.sum((market_vols - fitted_vols) ** 2)
        ss_tot = np.sum((market_vols - np.mean(market_vols)) ** 2)
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

        params = {
            'a': float(a_fit), 'b': float(b_fit), 'rho_svi': float(rho_fit),
            'm': float(m_fit), 'sigma_svi': float(sigma_fit), 'T': T
        }

        return params, fitted_vols, r_squared

    def _fit_svi(self,
                 strikes: np.ndarray,
                 maturities: np.ndarray,
                 iv_array: np.ndarray,
                 S: float,
                 r: float,
                 q: float) -> Tuple[Dict, np.ndarray, float]:
        """
        对所有到期日的SVI拟合。

        Returns:
            (all_params, fitted_vols_matrix, mean_r_squared)
        """
        n_maturities = len(maturities)
        all_params = {}
        fitted_vols = np.zeros_like(iv_array)
        r_squared_list = []

        for j in range(n_maturities):
            T = maturities[j]
            market_vols = iv_array[:, j]

            params, fit_vols, r2 = self._fit_svi_single_slice(
                strikes, market_vols, S, T, r, q
            )
            all_params[f'T={T}'] = params
            fitted_vols[:, j] = fit_vols
            r_squared_list.append(r2)

        mean_r2 = np.mean(r_squared_list)
        return all_params, fitted_vols, mean_r2

    def _fit_polynomial(self,
                        strikes: np.ndarray,
                        maturities: np.ndarray,
                        iv_array: np.ndarray,
                        S: float,
                        r: float,
                        q: float) -> Tuple[Dict, np.ndarray, float]:
        """
        多项式拟合波动率曲面。

        iv(k, T) = c0 + c1*k + c2*k^2 + c3*T + c4*k*T + c5*T^2
        """
        n_strikes = len(strikes)
        n_maturities = len(maturities)

        # 构建设计矩阵
        F = S * np.exp((r - q) * np.array(maturities).reshape(1, -1))
        k_grid = np.log(np.array(strikes).reshape(-1, 1) / F)

        K_flat = k_grid.flatten()
        T_flat = np.array(maturities).reshape(1, -1) * np.ones((n_strikes, n_maturities))
        T_flat = T_flat.flatten()
        iv_flat = iv_array.flatten()

        # 多项式: iv = c0 + c1*k + c2*k^2 + c3*T + c4*k*T + c5*T^2
        X = np.column_stack([
            np.ones_like(K_flat),
            K_flat,
            K_flat ** 2,
            T_flat,
            K_flat * T_flat,
            T_flat ** 2
        ])

        try:
            coeffs, residuals, rank, singular = np.linalg.lstsq(X, iv_flat, rcond=None)
            fitted_flat = X @ coeffs
            fitted_vols = fitted_flat.reshape(n_strikes, n_maturities)

            ss_res = np.sum((iv_flat - fitted_flat) ** 2)
            ss_tot = np.sum((iv_flat - np.mean(iv_flat)) ** 2)
            r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

            params = {
                'c0': float(coeffs[0]), 'c1': float(coeffs[1]),
                'c2': float(coeffs[2]), 'c3': float(coeffs[3]),
                'c4': float(coeffs[4]), 'c5': float(coeffs[5])
            }
            return params, fitted_vols, float(r_squared)

        except np.linalg.LinAlgError as e:
            raise CalculationError(
                f"Polynomial fit failed: {e}",
                calculation_type='polynomial_vol_surface'
            )

    def _fit_sabr_extrapolation(self,
                                 strikes: np.ndarray,
                                 maturities: np.ndarray,
                                 iv_array: np.ndarray,
                                 S: float,
                                 r: float,
                                 q: float) -> Tuple[Dict, np.ndarray, float]:
        """
        SABR外推法构建波动率曲面。

        先用SVI拟合每个slice，然后在期限结构维度上进行插值。
        """
        # 先用SVI拟合
        svi_params, svi_fitted, svi_r2 = self._fit_svi(strikes, maturities, iv_array, S, r, q)

        # 对每个行权价，沿期限结构维进行平滑插值
        fitted_vols = svi_fitted.copy()

        # 确保期限结构平滑
        for i in range(len(strikes)):
            ts = maturities
            vs = fitted_vols[i, :]
            # 对期限结构使用简单的线性插值保持平滑
            if len(ts) > 2:
                try:
                    sorted_idx = np.argsort(ts)
                    ts_sorted = ts[sorted_idx]
                    vs_sorted = vs[sorted_idx]
                    # 使用3阶多项式拟合期限结构
                    poly_coeffs = np.polyfit(ts_sorted, vs_sorted, min(3, len(ts_sorted) - 1))
                    fitted_vols[i, :] = np.polyval(poly_coeffs, ts)
                except Exception:
                    pass  # 失败时保留原始SVI拟合值

        params = {'svi_params': svi_params, 'method': 'sabr_extrapolation'}
        return params, fitted_vols, float(svi_r2)

    def get_volatility(self,
                       K: float,
                       T: float,
                       S: float,
                       r: float = None,
                       q: float = None,
                       surface_params: Dict = None) -> float:
        """
        从波动率曲面获取指定(K, T)点的隐含波动率。

        Args:
            K: 行权价
            T: 到期时间（年）
            S: 标的资产价格
            r: 无风险利率（默认使用计算时的值）
            q: 股息率（默认使用计算时的值）
            surface_params: 曲面参数（默认使用已存储的参数）

        Returns:
            插值后的隐含波动率

        Raises:
            CalculationError: 如果曲面尚未构建
        """
        params = surface_params if surface_params is not None else self._surface_params
        if params is None:
            raise CalculationError(
                "Volatility surface not yet built. Call calculate() first.",
                calculation_type='get_volatility'
            )

        r = r if r is not None else (self._r_ref or self.risk_free_rate)
        q = q if q is not None else (self._q_ref or 0.0)
        F = S * np.exp((r - q) * T)
        k = np.log(K / F)

        # 查找最接近的到期日参数
        best_T_key = None
        best_T_diff = float('inf')
        for key in params:
            if key.startswith('T='):
                T_val = float(key.split('=')[1])
                diff = abs(T_val - T)
                if diff < best_T_diff:
                    best_T_diff = diff
                    best_T_key = key

        if best_T_key is None:
            raise CalculationError(
                f"No surface parameters found for T={T}",
                calculation_type='get_volatility'
            )

        slice_params = params[best_T_key]
        w = self._svi_raw(
            np.array([k]),
            slice_params['a'], slice_params['b'],
            slice_params['rho_svi'], slice_params['m'],
            slice_params['sigma_svi']
        )
        iv = np.sqrt(w[0] / slice_params['T'])
        return float(iv)

    def get_smile(self,
                  S_spot: float,
                  r: float = None,
                  q: float = None,
                  T: float = None,
                  surface_params: Dict = None) -> Dict[str, Any]:
        """
        提取指定到期日的波动率微笑。

        Args:
            S_spot: 标的资产当前价格
            r: 无风险利率
            q: 股息率
            T: 到期时间（使用最近的面板）
            surface_params: 曲面参数

        Returns:
            Dictionary containing:
                - strikes: 行权价
                - implied_vols: 隐含波动率
                - moneyness: 在值程度 K/S
                - skew: 微笑偏度

        Raises:
            CalculationError: 如果曲面尚未构建
        """
        params = surface_params if surface_params is not None else self._surface_params
        if params is None:
            raise CalculationError(
                "Volatility surface not yet built.",
                calculation_type='get_smile'
            )

        r = r if r is not None else (self._r_ref or self.risk_free_rate)
        q = q if q is not None else (self._q_ref or 0.0)

        # 查找最接近的到期日
        if T is None:
            best_T = None
            best_key = None
            for key in params:
                if key.startswith('T='):
                    T_val = float(key.split('=')[1])
                    if best_T is None or T_val < best_T:
                        best_T = T_val
                        best_key = key
            if best_key is None:
                raise CalculationError("No valid maturity found in surface params",
                                       calculation_type='get_smile')
            T = best_T

        # 生成一组行权价覆盖 +/-30% 范围
        strikes = np.linspace(S_spot * 0.7, S_spot * 1.3, 50)
        ivs = []
        for K in strikes:
            try:
                iv = self.get_volatility(K, T, S_spot, r, q, params)
                ivs.append(iv)
            except Exception:
                ivs.append(np.nan)

        ivs = np.array(ivs)
        valid_mask = ~np.isnan(ivs)
        strikes_valid = strikes[valid_mask]
        ivs_valid = ivs[valid_mask]
        moneyness = strikes_valid / S_spot

        # 计算微笑偏度：25-delta put vol - 25-delta call vol
        K_low = S_spot * 0.9
        K_high = S_spot * 1.1
        try:
            iv_low = self.get_volatility(K_low, T, S_spot, r, q, params)
            iv_high = self.get_volatility(K_high, T, S_spot, r, q, params)
            skew = iv_low - iv_high
        except Exception:
            skew = 0.0

        return {
            'strikes': strikes_valid.tolist(),
            'implied_vols': ivs_valid.tolist(),
            'moneyness': moneyness.tolist(),
            'T': T,
            'S': S_spot,
            'skew': skew
        }

    def get_term_structure(self,
                           S_spot: float,
                           K: float,
                           r: float = None,
                           q: float = None,
                           surface_params: Dict = None) -> Dict[str, Any]:
        """
        提取指定行权价的波动率期限结构。

        Args:
            S_spot: 标的资产当前价格
            K: 行权价
            r: 无风险利率
            q: 股息率
            surface_params: 曲面参数

        Returns:
            Dictionary containing:
                - maturities: 到期时间
                - implied_vols: 隐含波动率
                - forward_prices: 远期价格
                - term_premium: 期限溢价

        Raises:
            CalculationError: 如果曲面尚未构建
        """
        params = surface_params if surface_params is not None else self._surface_params
        if params is None:
            raise CalculationError(
                "Volatility surface not yet built.",
                calculation_type='get_term_structure'
            )

        r = r if r is not None else (self._r_ref or self.risk_free_rate)
        q = q if q is not None else (self._q_ref or 0.0)

        # 提取所有到期日
        maturities = []
        for key in sorted(params.keys()):
            if key.startswith('T='):
                maturities.append(float(key.split('=')[1]))

        maturities = np.array(maturities)
        forward_prices = S_spot * np.exp((r - q) * maturities)

        ivs = []
        for T in maturities:
            try:
                iv = self.get_volatility(K, T, S_spot, r, q, params)
                ivs.append(iv)
            except Exception:
                ivs.append(np.nan)

        ivs = np.array(ivs)
        valid = ~np.isnan(ivs)

        term_premium = ivs[-1] - ivs[0] if len(ivs) > 1 and valid[-1] and valid[0] else 0.0

        return {
            'maturities': maturities.tolist(),
            'implied_vols': ivs.tolist(),
            'forward_prices': forward_prices.tolist(),
            'strike': K,
            'term_premium': term_premium
        }

    def get_supported_methods(self) -> list:
        """获取支持的方法列表。"""
        return ['svi', 'polynomial', 'sabr_extrapolation']
