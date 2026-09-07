"""
高阶Greeks计算模块
===================

计算期权的高阶Greeks（三阶及更高阶的风险指标），用于高级风险管理和对冲策略。

Greeks:
    - Speed: Gamma对标的资产价格的变化率（三阶导数）
    - Zomma: Gamma对波动率的变化率
    - Color: Gamma对时间的变化率（Gamma衰减）
    - Ultima: Vega对波动率的变化率（三阶Vega）

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, Any
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError


class AdvancedGreeksCalculator(BaseCalculator):
    """
    高阶Greeks计算器。

    计算期权的高阶风险指标（三阶及以上），适用于：
        - 大型组合的风险分解
        - 波动率曲面套利
        - 高精度对冲策略

    Features:
        - Speed (Gamma sensitivity to spot)
        - Zomma (Gamma sensitivity to volatility)
        - Color (Gamma decay over time)
        - Ultima (Vega sensitivity to volatility, 3rd-order vega)

    Example:
        >>> calc = AdvancedGreeksCalculator()
        >>> result = calc.calculate(S=100, K=100, T=1, r=0.05, sigma=0.2, option_type='call')
        >>> print(result['value']['speed'])
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        初始化高阶Greeks计算器。

        Args:
            precision: 结果精度（小数位数）（默认: 6）
            risk_free_rate: 默认无风险利率（默认: 0.0）
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  S: float,
                  K: float,
                  T: float,
                  r: float,
                  sigma: float,
                  option_type: str = 'call',
                  q: float = 0.0) -> Dict[str, Any]:
        """
        计算所有一阶、二阶和三阶Greeks。

        Args:
            S: 标的资产当前价格
            K: 行权价
            T: 到期时间（年）
            r: 无风险利率（年化）
            sigma: 波动率（年化）
            option_type: 'call' 或 'put'（默认: 'call'）
            q: 股息率（默认: 0.0）

        Returns:
            Dictionary containing:
                - delta, gamma, theta, vega, rho (一阶Greeks)
                - vanna, volga, charm (二阶Greeks)
                - speed, zomma, color, ultima (三阶Greeks)

        Raises:
            DataValidationError: 输入无效时
            CalculationError: 计算失败时
        """
        # 验证输入
        S = self._validate_positive(S, 'spot_price')
        K = self._validate_positive(K, 'strike_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        sigma = self._validate_positive(sigma, 'volatility')
        q = self._validate_numeric_input(q, 'dividend_yield')

        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise DataValidationError(
                "option_type must be 'call' or 'put'",
                field_name='option_type'
            )

        try:
            # 计算d1和d2
            d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)

            n_d1 = norm.pdf(d1)  # φ(d1)
            N_d1 = norm.cdf(d1)  # Φ(d1)
            N_d2 = norm.cdf(d2)  # Φ(d2)

            # === 一阶Greeks ===
            greeks = {}

            # Delta
            if option_type == 'call':
                greeks['delta'] = np.exp(-q * T) * N_d1
            else:
                greeks['delta'] = -np.exp(-q * T) * norm.cdf(-d1)

            # Gamma
            gamma = (n_d1 * np.exp(-q * T)) / (S * sigma * np.sqrt(T))
            greeks['gamma'] = gamma

            # Theta (per day)
            term1 = -(S * n_d1 * sigma * np.exp(-q * T)) / (2 * np.sqrt(T))
            if option_type == 'call':
                term2 = -r * K * np.exp(-r * T) * N_d2
                term3 = q * S * np.exp(-q * T) * N_d1
                greeks['theta'] = (term1 + term2 + term3) / 365
            else:
                term2 = r * K * np.exp(-r * T) * norm.cdf(-d2)
                term3 = -q * S * np.exp(-q * T) * norm.cdf(-d1)
                greeks['theta'] = (term1 + term2 + term3) / 365

            # Vega (per 1% change)
            vega = (S * n_d1 * np.sqrt(T) * np.exp(-q * T)) / 100
            greeks['vega'] = vega

            # Rho (per 1% change)
            if option_type == 'call':
                greeks['rho'] = (K * T * np.exp(-r * T) * N_d2) / 100
            else:
                greeks['rho'] = -(K * T * np.exp(-r * T) * norm.cdf(-d2)) / 100

            # === 二阶Greeks ===
            # Vanna
            greeks['vanna'] = -(vega * 100 * d2) / sigma

            # Volga (Vomma)
            greeks['volga'] = (vega * 100 * d1 * d2) / sigma

            # Charm
            if option_type == 'call':
                charm_term1 = q * np.exp(-q * T) * N_d1
                charm_term2 = np.exp(-q * T) * n_d1 * (2 * (r - q) * T - d2 * sigma * np.sqrt(T))
                charm_term2 /= (2 * T * sigma * np.sqrt(T))
                greeks['charm'] = (charm_term1 - charm_term2) / 365
            else:
                charm_term1 = -q * np.exp(-q * T) * norm.cdf(-d1)
                charm_term2 = np.exp(-q * T) * n_d1 * (2 * (r - q) * T - d2 * sigma * np.sqrt(T))
                charm_term2 /= (2 * T * sigma * np.sqrt(T))
                greeks['charm'] = (charm_term1 - charm_term2) / 365

            # === 三阶Greeks ===
            greeks['speed'] = self._calculate_speed(S, gamma, d1, sigma, T)
            greeks['zomma'] = self._calculate_zomma(gamma, d1, d2, sigma)
            greeks['color'] = self._calculate_color(S, n_d1, sigma, T, r, d1, d2, q)
            greeks['ultima'] = self._calculate_ultima(vega, sigma, d1, d2)

            return self._create_result_dict(
                value=greeks,
                method='advanced_greeks',
                parameters={
                    'S': S, 'K': K, 'T': T, 'r': r,
                    'sigma': sigma, 'q': q, 'option_type': option_type
                },
                metadata={
                    'd1': d1, 'd2': d2,
                    'n_d1': n_d1, 'N_d1': N_d1, 'N_d2': N_d2
                }
            )

        except Exception as e:
            raise CalculationError(
                f"Advanced Greeks calculation failed: {str(e)}",
                calculation_type='advanced_greeks'
            )

    def _calculate_speed(self,
                          S: float,
                          gamma: float,
                          d1: float,
                          sigma: float,
                          T: float) -> float:
        """
        计算Speed（Gamma对标的资产价格的变化率）。

        speed = -gamma/S * (1 + d1/(sigma*sqrt(T)))

        Speed衡量Gamma随标的资产价格变化的速度，是期权价格对标的资产的三阶导数。
        当Speed较大时，Gamma对冲需要更频繁地再平衡。

        Args:
            S: 标的资产价格
            gamma: Gamma值
            d1: d1参数
            sigma: 波动率
            T: 到期时间

        Returns:
            Speed值
        """
        if S <= 0 or sigma <= 0 or T <= 0:
            return 0.0
        return -gamma / S * (1.0 + d1 / (sigma * np.sqrt(T)))

    def _calculate_zomma(self,
                          gamma: float,
                          d1: float,
                          d2: float,
                          sigma: float) -> float:
        """
        计算Zomma（Gamma对波动率的变化率）。

        zomma = gamma * (d1*d2 - 1) / sigma

        Zomma衡量Gamma随隐含波动率变化的速度。
        正值表示Gamma随波动率上升而上升，负值反之。

        Args:
            gamma: Gamma值
            d1: d1参数
            d2: d2参数
            sigma: 波动率

        Returns:
            Zomma值
        """
        if sigma <= 0:
            return 0.0
        return gamma * (d1 * d2 - 1.0) / sigma

    def _calculate_color(self,
                          S: float,
                          n_d1: float,
                          sigma: float,
                          T: float,
                          r: float,
                          d1: float,
                          d2: float,
                          q: float = 0.0) -> float:
        """
        计算Color（Gamma随时间的变化率，Gamma衰减速度）。

        color = -e^(-qT) * φ(d1) / (2*S*sigma*sqrt(T)) * [2*r*T - 1 - d2*sigma*sqrt(T)/(2*T)]

        Color是期权价格对标的资产的三阶导数（对资产两次、对时间一次）。
        它衡量Gamma随时间的衰减速度。

        Args:
            S: 标的资产价格
            n_d1: 标准正态分布在d1处的概率密度 φ(d1)
            sigma: 波动率
            T: 到期时间
            r: 无风险利率
            d1: d1参数
            d2: d2参数
            q: 股息率

        Returns:
            Color值（每日）
        """
        if S <= 0 or sigma <= 0 or T <= 0:
            return 0.0

        sqrt_T = np.sqrt(T)
        term_inside = 2.0 * (r - q) * T - d2 * sigma * sqrt_T

        color = -np.exp(-q * T) * n_d1 / (2.0 * S * T * sigma * sqrt_T)
        color *= (2.0 * q * T + 1.0 + d1 / (sigma * sqrt_T) * term_inside)

        # 转换为每日值
        return color / 365.0

    def _calculate_ultima(self,
                           vega: float,
                           sigma: float,
                           d1: float,
                           d2: float) -> float:
        """
        计算Ultima（Vega对波动率的三阶导数）。

        ultima = vega/(sigma) * (d1*d2*(1-d1*d2) + d1**2 + d2**2)

        Ultima是Vega对波动率的敏感度，即Vega的二阶导数。
        它衡量Vega曲率——在极端波动率情况下Vega的变化模式。

        Args:
            vega: Vega值（每1%变化，需要转换为原始值）
            sigma: 波动率
            d1: d1参数
            d2: d2参数

        Returns:
            Ultima值（每1%波动率变化的Vega敏感度）
        """
        if sigma <= 0:
            return 0.0

        # vega存储为每1%变化的值，需要转换为原始vega用于公式
        vega_raw = vega * 100.0  # 还原为原始vega

        d1_sq = d1 ** 2
        d2_sq = d2 ** 2
        d1d2 = d1 * d2

        ultima_raw = vega_raw / sigma * (d1d2 * (1.0 - d1d2) + d1_sq + d2_sq)

        # 转换为每1%变化的格式以保持一致性
        return ultima_raw / 100.0

    def get_supported_methods(self) -> list:
        """获取支持的计算方法列表。"""
        return ['advanced_greeks', 'speed', 'zomma', 'color', 'ultima']
