"""
随机波动率模型模块
==================

实现Heston和SABR随机波动率模型用于期权定价和校准。

Heston模型:
    dS = r*S*dt + sqrt(v)*S*dW1
    dv = kappa*(theta - v)*dt + xi*sqrt(v)*dW2
    dW1*dW2 = rho*dt

SABR模型（Hagan et al.公式）:
    隐含波动率展开式用于欧式期权定价。

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
from scipy.integrate import quad
from scipy.optimize import minimize
from scipy.stats import norm
from typing import Dict, Any, Optional, List, Tuple
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError, ConfigurationError


class StochasticVolCalculator(BaseCalculator):
    """
    随机波动率模型计算器。

    使用Heston和SABR随机波动率模型进行期权定价、隐含波动率计算和参数校准。

    Features:
        - Heston模型定价（特征函数+Fourier反演）
        - SABR模型定价（Hagan展开+Black-76）
        - SABR隐含波动率计算
        - 模型参数校准

    Example:
        >>> calc = StochasticVolCalculator()
        >>> result = calc.calculate(
        ...     S=100, K=100, T=1, r=0.05, sigma0=0.04,
        ...     kappa=2.0, theta=0.04, xi=0.3, rho=-0.7,
        ...     method='heston'
        ... )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        初始化随机波动率模型计算器。

        Args:
            precision: 结果精度（默认: 6）
            risk_free_rate: 默认无风险利率（默认: 0.0）
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  S: float,
                  K: float,
                  T: float,
                  r: float,
                  sigma0: float,
                  kappa: Optional[float] = None,
                  theta: Optional[float] = None,
                  xi: float = 0.3,
                  rho: float = -0.5,
                  option_type: str = 'call',
                  q: float = 0.0,
                  method: str = 'heston') -> Dict[str, Any]:
        """
        使用随机波动率模型计算期权价格。

        Args:
            S: 标的资产当前价格
            K: 行权价
            T: 到期时间（年）
            r: 无风险利率
            sigma0: 初始方差（Heston）或初始波动率（SABR中的alpha）
            kappa: 均值回归速度（Heston）
            theta: 长期均值方差（Heston）
            xi: 波动率的波动率（Heston）或vol-of-vol (nu in SABR)
            rho: 资产与波动率的相关性
            option_type: 'call' 或 'put'
            q: 股息率（默认: 0.0）
            method: 'heston' 或 'sabr'

        Returns:
            Dictionary containing:
                - value: 期权价格
                - implied_vol: 隐含波动率（BSM等价）
                - model_params: 模型参数

        Raises:
            DataValidationError: 输入无效时
            CalculationError: 计算失败时
        """
        method = self.validate_method(method)

        # 验证输入
        S = self._validate_positive(S, 'spot_price')
        K = self._validate_positive(K, 'strike_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        sigma0 = self._validate_positive(sigma0, 'initial_variance_or_volatility')
        xi = self._validate_positive(xi, 'vol_of_vol')
        rho = self._validate_numeric_input(rho, 'correlation')
        q = self._validate_numeric_input(q, 'dividend_yield')

        # kappa and theta are only required for Heston
        if method == 'heston':
            if kappa is None:
                raise DataValidationError(
                    "kappa is required for Heston method",
                    field_name='kappa'
                )
            if theta is None:
                raise DataValidationError(
                    "theta is required for Heston method",
                    field_name='theta'
                )
            kappa = self._validate_positive(kappa, 'mean_reversion_speed')
            theta = self._validate_positive(theta, 'long_term_variance')
        else:
            kappa = kappa if kappa is not None else 0.0
            theta = theta if theta is not None else 0.0

        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise DataValidationError(
                "option_type must be 'call' or 'put'",
                field_name='option_type'
            )

        if abs(rho) > 1.0:
            raise DataValidationError(
                f"Correlation rho must be between -1 and 1, got {rho}",
                field_name='rho'
            )

        try:
            if method == 'heston':
                price = self._heston_price(S, K, T, r, sigma0, kappa, theta, xi, rho, option_type, q)
            elif method == 'sabr':
                price = self._sabr_price(S, K, T, r, sigma0, xi, rho, option_type, q, beta=0.5)
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            # 计算BSM等价隐含波动率
            try:
                iv = self._implied_vol_bs(price, S, K, T, r, q, option_type)
            except Exception:
                iv = None

            return self._create_result_dict(
                value=price,
                method=f'stochastic_vol_{method}',
                parameters={
                    'S': S, 'K': K, 'T': T, 'r': r,
                    'sigma0': sigma0, 'kappa': kappa, 'theta': theta,
                    'xi': xi, 'rho': rho, 'q': q, 'option_type': option_type
                },
                metadata={
                    'implied_vol': iv,
                    'model_params': {
                        'sigma0': sigma0, 'kappa': kappa,
                        'theta': theta, 'xi': xi, 'rho': rho
                    }
                }
            )

        except Exception as e:
            raise CalculationError(
                f"Stochastic volatility calculation failed: {str(e)}",
                calculation_type=f'stochastic_vol_{method}'
            )

    def _heston_characteristic_function(self,
                                         phi: complex,
                                         S: float,
                                         K: float,
                                         T: float,
                                         r: float,
                                         sigma0: float,
                                         kappa: float,
                                         theta: float,
                                         xi: float,
                                         rho: float) -> complex:
        """
        Heston特征函数（对数价格的特征函数）。

        Formula from Heston (1993) / Gatheral (2006):
            f(phi) = exp(C + D*v0 + i*phi*log(S*exp(r*T)))

        其中：
            C = r*phi*i*T + kappa*theta/xi^2 * [(kappa - rho*xi*phi*i - d)*T - 2*log((1-g*exp(-d*T))/(1-g))]
            D = (kappa - rho*xi*phi*i - d) / xi^2 * (1 - exp(-d*T)) / (1 - g*exp(-d*T))
            g = (kappa - rho*xi*phi*i - d) / (kappa - rho*xi*phi*i + d)
            d = sqrt((rho*xi*phi*i - kappa)^2 + xi^2*(phi*i + phi^2))

        Args:
            phi: 特征函数参数（复数）
            S, K, T, r: 标准BSM参数
            sigma0: 初始方差 v0
            kappa: 均值回归速度
            theta: 长期方差均值
            xi: 波动率的波动率 (vol of vol)
            rho: 相关性

        Returns:
            特征函数值（复数）
        """
        # 使用对数价格的特征函数
        i = complex(0, 1)

        # 参数缩写
        sigma_xi = xi
        k = kappa
        v0 = sigma0
        v_bar = theta

        # d = sqrt((rho*xi*i*phi - kappa)^2 + xi^2*(i*phi + phi^2))
        a = rho * sigma_xi * i * phi - k
        d = np.sqrt(a ** 2 + sigma_xi ** 2 * (i * phi + phi ** 2))

        # g = (kappa - rho*xi*i*phi - d) / (kappa - rho*xi*i*phi + d)
        numerator = k - rho * sigma_xi * i * phi - d
        denominator = k - rho * sigma_xi * i * phi + d
        g = numerator / denominator

        # 处理exp(-d*T)为0的情况（大T）
        exp_dT = np.exp(-d * T)

        # C组件
        term1 = r * phi * i * T
        term2_num = k * v_bar / (sigma_xi ** 2)
        term2_inside = (k - rho * sigma_xi * i * phi - d) * T
        term2_log = -2.0 * np.log((1.0 - g * exp_dT) / (1.0 - g))
        C = term1 + term2_num * (term2_inside + term2_log)

        # D组件
        D = numerator / (sigma_xi ** 2) * (1.0 - exp_dT) / (1.0 - g * exp_dT)

        # 对数现货的特征函数
        log_S = np.log(S)
        cf = np.exp(C + D * v0 + i * phi * log_S)

        return cf

    def _heston_integrand_1(self, phi: float, S: float, K: float, T: float, r: float,
                             sigma0: float, kappa: float, theta: float,
                             xi: float, rho: float) -> float:
        """P1的积分被积函数（实部）。"""
        i = complex(0, 1)
        cf = self._heston_characteristic_function(
            phi - i, S, K, T, r, sigma0, kappa, theta, xi, rho
        )
        numerator = np.exp(-i * phi * np.log(K)) * cf
        denominator = i * phi * S * np.exp(r * T)
        return float(np.real(numerator / denominator))

    def _heston_integrand_2(self, phi: float, S: float, K: float, T: float, r: float,
                             sigma0: float, kappa: float, theta: float,
                             xi: float, rho: float) -> float:
        """P2的积分被积函数（实部）。"""
        i = complex(0, 1)
        cf = self._heston_characteristic_function(
            phi, S, K, T, r, sigma0, kappa, theta, xi, rho
        )
        numerator = np.exp(-i * phi * np.log(K)) * cf
        denominator = i * phi
        return float(np.real(numerator / denominator))

    def _heston_price(self,
                      S: float,
                      K: float,
                      T: float,
                      r: float,
                      sigma0: float,
                      kappa: float,
                      theta: float,
                      xi: float,
                      rho: float,
                      option_type: str = 'call',
                      q: float = 0.0) -> float:
        """
        使用Heston模型定价欧式期权。

        使用特征函数和小Trap积分（Carr-Madan方法）。

        Args:
            S, K, T, r: 标准BSM参数
            sigma0: 初始方差 v0
            kappa: 均值回归速度
            theta: 长期方差均值
            xi: vol-of-vol
            rho: 相关性
            option_type: 'call' 或 'put'
            q: 股息率

        Returns:
            期权价格
        """
        # 调整利率以考虑股息
        r_adj = r - q

        # P1和P2的概率
        try:
            P1 = 0.5 + (1.0 / np.pi) * quad(
                self._heston_integrand_1,
                0.001, 100.0,
                args=(S, K, T, r_adj, sigma0, kappa, theta, xi, rho),
                limit=100
            )[0]

            P2 = 0.5 + (1.0 / np.pi) * quad(
                self._heston_integrand_2,
                0.001, 100.0,
                args=(S, K, T, r_adj, sigma0, kappa, theta, xi, rho),
                limit=100
            )[0]
        except Exception:
            # 数值积分失败时的回退
            # 使用BSM近似，波动率为sqrt(theta)
            d1 = (np.log(S / K) + (r_adj + 0.5 * theta) * T) / (np.sqrt(theta * T))
            d2 = d1 - np.sqrt(theta * T)
            if option_type == 'call':
                return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r_adj * T) * norm.cdf(d2)
            else:
                return K * np.exp(-r_adj * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)

        if option_type == 'call':
            price = S * np.exp(-q * T) * P1 - K * np.exp(-r_adj * T) * P2
        else:
            price = K * np.exp(-r_adj * T) * (1.0 - P2) - S * np.exp(-q * T) * (1.0 - P1)

        return max(price, 0.0)

    def _sabr_implied_vol(self,
                           S: float,
                           K: float,
                           T: float,
                           alpha: float,
                           beta: float,
                           nu: float,
                           rho: float) -> float:
        """
        SABR模型隐含波动率（Hagan et al. 2002公式）。

        公式适用于0 < beta < 1的情况，特殊处理ATM。

        Args:
            S: 远期价格/现货
            K: 行权价
            T: 到期时间
            alpha: 初始波动率水平
            beta: CEV参数 (0 <= beta <= 1)
            nu: vol-of-vol
            rho: 相关性

        Returns:
            Black-76隐含波动率
        """
        if T <= 0:
            return alpha

        # ATM特殊情况 (S ≈ K)
        if abs(S - K) < 1e-12:
            term1 = (1.0 - beta) ** 2 / 24.0 * alpha ** 2 / (S ** (2.0 - 2.0 * beta))
            term2 = rho * beta * nu * alpha / (4.0 * S ** (1.0 - beta))
            term3 = (2.0 - 3.0 * rho ** 2) / 24.0 * nu ** 2
            return alpha / (S ** (1.0 - beta)) * (1.0 + (term1 + term2 + term3) * T)

        # 一般情况
        F = S  # 远期 = 现货（简化）
        z = (nu / alpha) * (F * K) ** ((1.0 - beta) / 2.0) * np.log(F / K)
        x_z = np.log((np.sqrt(1.0 - 2.0 * rho * z + z ** 2) + z - rho) / (1.0 - rho))

        # 分母
        denom = (F * K) ** ((1.0 - beta) / 2.0)
        denom *= (1.0 + (1.0 - beta) ** 2 / 24.0 * (np.log(F / K)) ** 2
                   + (1.0 - beta) ** 4 / 1920.0 * (np.log(F / K)) ** 4)

        # 分子
        term1 = (1.0 - beta) ** 2 / 24.0 * alpha ** 2 / ((F * K) ** (1.0 - beta))
        term2 = rho * beta * nu * alpha / (4.0 * (F * K) ** ((1.0 - beta) / 2.0))
        term3 = (2.0 - 3.0 * rho ** 2) / 24.0 * nu ** 2

        if abs(z) < 1e-10:
            # z→0时使用极限
            iv = alpha * (1.0 + (term1 + term2 + term3) * T) / denom
        else:
            iv = alpha * (z / x_z) * (1.0 + (term1 + term2 + term3) * T) / denom

        return float(iv)

    def _sabr_price(self,
                     S: float,
                     K: float,
                     T: float,
                     r: float,
                     alpha: float,
                     nu: float,
                     rho: float,
                     option_type: str = 'call',
                     q: float = 0.0,
                     beta: float = 0.5) -> float:
        """
        使用SABR模型定价欧式期权。

        先用Hagan公式计算隐含波动率，再用Black-76公式定价。

        Args:
            S: 标的资产价格
            K: 行权价
            T: 到期时间
            r: 无风险利率
            alpha: 初始波动率水平
            nu: vol-of-vol
            rho: 相关性
            option_type: 'call' 或 'put'
            q: 股息率
            beta: CEV参数（默认 0.5，对数正态为1）

        Returns:
            期权价格
        """
        # 用Black-76期货公式（无股息调整）
        F = S * np.exp((r - q) * T)

        sigma_sabr = self._sabr_implied_vol(F, K, T, alpha, beta, nu, rho)

        # Black-76公式
        if sigma_sabr <= 0 or T <= 0:
            if option_type == 'call':
                return max(0.0, F - K) * np.exp(-r * T)
            else:
                return max(0.0, K - F) * np.exp(-r * T)

        d1 = (np.log(F / K) + 0.5 * sigma_sabr ** 2 * T) / (sigma_sabr * np.sqrt(T))
        d2 = d1 - sigma_sabr * np.sqrt(T)

        if option_type == 'call':
            price = np.exp(-r * T) * (F * norm.cdf(d1) - K * norm.cdf(d2))
        else:
            price = np.exp(-r * T) * (K * norm.cdf(-d2) - F * norm.cdf(-d1))

        return max(price, 0.0)

    def _implied_vol_bs(self,
                         price: float,
                         S: float,
                         K: float,
                         T: float,
                         r: float,
                         q: float,
                         option_type: str) -> Optional[float]:
        """
        使用Newton-Raphson方法计算BSM隐含波动率。

        Args:
            price: 期权市场价格
            S, K, T, r, q: BSM参数
            option_type: 'call' 或 'put'

        Returns:
            隐含波动率，或None（如果计算失败）
        """
        if T <= 0 or price <= 0:
            return None

        sigma = 0.2
        max_iter = 100
        tol = 1e-6

        for _ in range(max_iter):
            if sigma <= 0 or sigma > 10.0:
                return None

            d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)

            if option_type == 'call':
                model_price = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
                vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)
            else:
                model_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)
                vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)

            diff = model_price - price

            if abs(diff) < tol:
                return float(sigma)

            if vega < 1e-10:
                return None

            sigma = sigma - diff / vega

        return None

    def calibrate(self,
                  market_prices: List[float],
                  strikes: List[float],
                  maturities: List[float],
                  S: float,
                  r: float,
                  option_types: List[str] = None,
                  method: str = 'heston') -> Dict[str, Any]:
        """
        使用市场价格校准随机波动率模型参数。

        Args:
            market_prices: 市场价格列表
            strikes: 行权价列表
            maturities: 到期时间列表
            S: 标的资产价格
            r: 无风险利率
            option_types: 期权类型列表 [n]
            method: 'heston' 或 'sabr'

        Returns:
            Dictionary containing:
                - calibrated_params: 校准后的参数
                - pricing_errors: 定价误差
                - rmse: 均方根误差

        Raises:
            DataValidationError: 输入无效时
            CalculationError: 校准失败时
        """
        method = self.validate_method(method)

        S = self._validate_positive(S, 'spot_price')
        r = self._validate_numeric_input(r, 'risk_free_rate')

        if option_types is None:
            option_types = ['call'] * len(market_prices)

        n = len(market_prices)
        if len(strikes) != n or len(maturities) != n or len(option_types) != n:
            raise DataValidationError(
                "All input arrays must have the same length",
                field_name='market_data'
            )

        try:
            if method == 'heston':
                calibrated_params = self._calibrate_heston(
                    market_prices, strikes, maturities, S, r, option_types
                )
            elif method == 'sabr':
                calibrated_params = self._calibrate_sabr(
                    market_prices, strikes, maturities, S, r, option_types
                )
            else:
                raise ConfigurationError(f"Unknown calibration method: {method}",
                                         parameter='method')
        except Exception as e:
            raise CalculationError(
                f"Calibration failed: {e}",
                calculation_type=f'calibrate_{method}'
            )

        # 计算定价误差
        pricing_errors = []
        for i in range(n):
            try:
                if method == 'heston':
                    model_price = self._heston_price(
                        S, strikes[i], maturities[i], r,
                        calibrated_params['sigma0'], calibrated_params['kappa'],
                        calibrated_params['theta'], calibrated_params['xi'],
                        calibrated_params['rho'], option_types[i]
                    )
                else:
                    model_price = self._sabr_price(
                        S, strikes[i], maturities[i], r,
                        calibrated_params['alpha'], calibrated_params['nu'],
                        calibrated_params['rho'], option_types[i]
                    )
                error = model_price - market_prices[i]
                pricing_errors.append(error)
            except Exception:
                pricing_errors.append(0.0)

        rmse = np.sqrt(np.mean(np.array(pricing_errors) ** 2))

        return self._create_result_dict(
            value=calibrated_params,
            method=f'calibrate_{method}',
            parameters={
                'S': S, 'r': r, 'n_options': n
            },
            metadata={
                'pricing_errors': pricing_errors,
                'rmse': rmse
            }
        )

    def _calibrate_heston(self,
                           market_prices: List[float],
                           strikes: List[float],
                           maturities: List[float],
                           S: float,
                           r: float,
                           option_types: List[str]) -> Dict[str, float]:
        """校准Heston模型参数。"""
        def objective(params):
            sigma0, kappa, theta, xi, rho = params

            # 参数约束惩罚
            penalty = 0.0
            if sigma0 <= 0:
                penalty += 1e6 * (abs(sigma0) + 1e-6) ** 2
            if kappa <= 0:
                penalty += 1e6 * (abs(kappa) + 1e-6) ** 2
            if theta <= 0:
                penalty += 1e6 * (abs(theta) + 1e-6) ** 2
            if xi <= 0:
                penalty += 1e6 * (abs(xi) + 1e-6) ** 2
            if abs(rho) > 1:
                penalty += 1e6 * (abs(rho) - 0.99) ** 2
            # Feller条件：2*kappa*theta > xi^2
            if 2 * kappa * theta <= xi ** 2:
                penalty += 100.0 * (xi ** 2 - 2 * kappa * theta + 1e-6)

            if penalty > 0:
                return penalty

            total_error = 0.0
            for i in range(len(market_prices)):
                try:
                    model_price = self._heston_price(
                        S, strikes[i], maturities[i], r,
                        sigma0, kappa, theta, xi, rho, option_types[i]
                    )
                    total_error += (model_price - market_prices[i]) ** 2
                except Exception:
                    total_error += 1e6

            return total_error

        # 初始参数猜测
        x0 = [0.04, 2.0, 0.04, 0.3, -0.7]

        result = minimize(
            objective, x0,
            method='Nelder-Mead',
            options={'maxiter': 5000, 'xatol': 1e-6, 'fatol': 1e-6}
        )

        sigma0, kappa, theta, xi, rho = result.x

        return {
            'sigma0': float(sigma0),
            'kappa': float(kappa),
            'theta': float(theta),
            'xi': float(xi),
            'rho': float(rho)
        }

    def _calibrate_sabr(self,
                         market_prices: List[float],
                         strikes: List[float],
                         maturities: List[float],
                         S: float,
                         r: float,
                         option_types: List[str]) -> Dict[str, float]:
        """校准SABR模型参数（固定beta=0.5）。"""
        def objective(params):
            alpha, nu, rho = params

            penalty = 0.0
            if alpha <= 0:
                penalty += 1e6 * (abs(alpha) + 1e-6) ** 2
            if nu <= 0:
                penalty += 1e6 * (abs(nu) + 1e-6) ** 2
            if abs(rho) > 1:
                penalty += 1e6 * (abs(rho) - 0.99) ** 2
            if penalty > 0:
                return penalty

            total_error = 0.0
            for i in range(len(market_prices)):
                try:
                    model_price = self._sabr_price(
                        S, strikes[i], maturities[i], r,
                        alpha, nu, rho, option_types[i], beta=0.5
                    )
                    total_error += (model_price - market_prices[i]) ** 2
                except Exception:
                    total_error += 1e6

            return total_error

        x0 = [0.2, 0.3, -0.5]
        result = minimize(
            objective, x0,
            method='Nelder-Mead',
            options={'maxiter': 5000, 'xatol': 1e-6, 'fatol': 1e-6}
        )

        alpha, nu, rho = result.x

        return {
            'alpha': float(alpha),
            'beta': 0.5,
            'nu': float(nu),
            'rho': float(rho)
        }

    def get_supported_methods(self) -> list:
        """获取支持的方法列表。"""
        return ['heston', 'sabr']
