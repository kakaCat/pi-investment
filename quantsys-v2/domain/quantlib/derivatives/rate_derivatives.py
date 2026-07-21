"""
利率衍生品定价模块
==================

使用Black-76和简化CDS模型对利率衍生品进行定价。

支持的产品:
    - Caplet / Floorlet (利率上限/下限单元)
    - Cap / Floor (利率上限/下限组合)
    - Swaption (互换期权, Black-76)
    - CDS (信用违约互换, 简化模型)

Black-76 公式:
    Caplet = DF * tau * [F*N(d1) - K*N(d2)]
    Floorlet = DF * tau * [K*N(-d2) - F*N(-d1)]

CDS 定价:
    Premium Leg = S * sum(DF_i * tau_i * (1 - PD_i))
    Protection Leg = (1 - R) * sum(DF_i * PD_i_conditional)

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, Any, List, Tuple
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError, ConfigurationError


class RateDerivativesCalculator(BaseCalculator):
    """
    利率衍生品定价计算器。

    使用Black-76模型对利率上限/下限、互换期权和
    简化CDS模型进行定价。

    Features:
        - Caplet/Floorlet 定价 (Black-76)
        - Cap/Floor 组合定价
        - Swaption 定价 (Black-76)
        - CDS 简化模型定价
        - 年金因子计算

    Example:
        >>> calc = RateDerivativesCalculator()
        >>> result = calc.calculate(
        ...     notional=1000000, forward_rate_or_rates=[0.05],
        ...     strike=0.05, T=1.0, sigma=0.2, r=0.04, method='caplet'
        ... )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        初始化利率衍生品定价计算器。

        Args:
            precision: 结果精度（默认: 6）
            risk_free_rate: 默认无风险利率（默认: 0.0）
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  notional: float,
                  forward_rate_or_rates: Any,
                  strike: float,
                  T: float,
                  sigma: float,
                  r: float,
                  method: str = 'caplet',
                  payment_frequency: float = 0.25) -> Dict[str, Any]:
        """
        利率衍生品定价主入口。

        Args:
            notional: 名义本金
            forward_rate_or_rates: 远期利率
                - caplet/floorlet: 单个float
                - cap/floor/swaption: float列表或单个float
            strike: 执行利率
            T: 到期时间（年）
            sigma: 波动率
            r: 无风险利率/贴现率
            method: 定价方法
                - 'caplet': 单个利率上限单元
                - 'floorlet': 单个利率下限单元
                - 'cap': 利率上限组合
                - 'floor': 利率下限组合
                - 'swaption': 互换期权
                - 'cds': 信用违约互换
            payment_frequency: 支付频率（年化，默认: 0.25 = 每季度）

        Returns:
            Dictionary containing:
                - value: 衍生品价格
                - premium: 期权费
                - method: 定价方法

        Raises:
            DataValidationError: 输入无效时
            CalculationError: 计算失败时
        """
        method = self.validate_method(method)

        notional = self._validate_positive(notional, 'notional')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'discount_rate')
        strike = self._validate_numeric_input(strike, 'strike_rate')
        payment_frequency = self._validate_positive(payment_frequency, 'payment_frequency')

        # sigma is not needed for CDS
        if method != 'cds':
            sigma = self._validate_positive(sigma, 'volatility')

        try:
            if method == 'caplet':
                forward_rate = self._validate_numeric_input(forward_rate_or_rates, 'forward_rate')
                price = self._price_caplet(notional, float(forward_rate), strike,
                                           T, sigma, r, payment_frequency, is_cap=True)
            elif method == 'floorlet':
                forward_rate = self._validate_numeric_input(forward_rate_or_rates, 'forward_rate')
                price = self._price_floorlet(notional, float(forward_rate), strike,
                                              T, sigma, r, payment_frequency, is_floor=True)
            elif method == 'cap':
                forward_rates = self._validate_numeric_input(forward_rate_or_rates, 'forward_rates')
                price = self._price_cap(notional, forward_rates, strike,
                                         T, sigma, r, payment_frequency)
            elif method == 'floor':
                forward_rates = self._validate_numeric_input(forward_rate_or_rates, 'forward_rates')
                price = self._price_floor(notional, forward_rates, strike,
                                           T, sigma, r, payment_frequency)
            elif method == 'swaption':
                forward_rate = self._validate_numeric_input(forward_rate_or_rates, 'forward_swap_rate')
                price = self._price_swaption(notional, float(forward_rate), strike,
                                              T, sigma, r, payment_frequency)
            elif method == 'cds':
                price = self._price_cds(notional, forward_rate_or_rates, strike,
                                         T, sigma, r)
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            return self._create_result_dict(
                value=float(price),
                method=method,
                parameters={
                    'notional': notional,
                    'strike': strike,
                    'T': T,
                    'sigma': sigma,
                    'r': r,
                    'payment_frequency': payment_frequency
                },
                metadata={
                    'price': float(price),
                    'price_bps': float(price / notional * 10000.0) if notional > 0 else 0.0
                }
            )

        except Exception as e:
            raise CalculationError(
                f"Rate derivative calculation failed: {str(e)}",
                calculation_type=f'rate_derivative_{method}'
            )

    def _price_caplet(self,
                      notional: float,
                      forward_rate: float,
                      strike: float,
                      T: float,
                      sigma: float,
                      r: float,
                      tau: float,
                      is_cap: bool = True) -> float:
        """
        使用Black-76公式为Caplet/Floorlet定价。

        Black-76:
            Caplet = DF * tau * [F*N(d1) - K*N(d2)]
            Floorlet = DF * tau * [K*N(-d2) - F*N(-d1)]

        其中:
            d1 = [ln(F/K) + sigma^2*T/2] / (sigma*sqrt(T))
            d2 = d1 - sigma*sqrt(T)
            DF = exp(-r*T)
            tau = 应计期间（支付频率）
            F = 远期利率
            K = 执行利率

        Args:
            notional: 名义本金
            forward_rate: 远期利率 (F)
            strike: 执行利率 (K)
            T: 到期时间
            sigma: 波动率
            r: 无风险利率（贴现率）
            tau: 应计期间
            is_cap: True for caplet, False for floorlet

        Returns:
            Caplet/Floorlet 价格
        """
        if T <= 0:
            # 到期：立即行权
            if is_cap:
                return notional * tau * max(forward_rate - strike, 0.0)
            else:
                return notional * tau * max(strike - forward_rate, 0.0)

        if sigma <= 0 or forward_rate <= 0 or strike <= 0:
            # 确定型支付
            if is_cap:
                payoff = notional * tau * max(forward_rate - strike, 0.0)
            else:
                payoff = notional * tau * max(strike - forward_rate, 0.0)
            return payoff * np.exp(-r * T)

        d1 = (np.log(forward_rate / strike) + 0.5 * sigma ** 2 * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        # 贴现因子
        df = np.exp(-r * T)

        if is_cap:
            price = df * tau * notional * (forward_rate * norm.cdf(d1) - strike * norm.cdf(d2))
        else:
            price = df * tau * notional * (strike * norm.cdf(-d2) - forward_rate * norm.cdf(-d1))

        return float(price)

    def _price_floorlet(self,
                         notional: float,
                         forward_rate: float,
                         strike: float,
                         T: float,
                         sigma: float,
                         r: float,
                         tau: float,
                         is_floor: bool = True) -> float:
        """Floorlet定价（委托给_price_caplet）。"""
        return self._price_caplet(notional, forward_rate, strike, T, sigma, r, tau, is_cap=False)

    def _price_cap(self,
                    notional: float,
                    forward_rates: np.ndarray,
                    strike: float,
                    T: float,
                    sigma: float,
                    r: float,
                    tau: float) -> float:
        """
        Cap组合定价（多个Caplet的加总）。

        一个Cap由多个Caplet组成，每个Caplet覆盖不同的利率重置期。

        Args:
            notional: 名义本金
            forward_rates: 各期远期利率数组
            strike: 执行利率
            T: 最后一个Caplet的到期时间
            sigma: 波动率
            r: 贴现率
            tau: 支付频率

        Returns:
            Cap总价格
        """
        if isinstance(forward_rates, (float, int)):
            forward_rates = np.array([float(forward_rates)])

        forward_rates = np.atleast_1d(np.array(forward_rates, dtype=float))
        n_periods = len(forward_rates)

        total_price = 0.0
        for i in range(n_periods):
            # 每个caplet的到期时间
            Ti = T * (i + 1) / n_periods
            caplet_price = self._price_caplet(
                notional, forward_rates[i], strike, Ti, sigma, r, tau, is_cap=True
            )
            total_price += caplet_price

        return total_price

    def _price_floor(self,
                      notional: float,
                      forward_rates: np.ndarray,
                      strike: float,
                      T: float,
                      sigma: float,
                      r: float,
                      tau: float) -> float:
        """
        Floor组合定价（多个Floorlet的加总）。
        """
        if isinstance(forward_rates, (float, int)):
            forward_rates = np.array([float(forward_rates)])

        forward_rates = np.atleast_1d(np.array(forward_rates, dtype=float))
        n_periods = len(forward_rates)

        total_price = 0.0
        for i in range(n_periods):
            Ti = T * (i + 1) / n_periods
            floorlet_price = self._price_floorlet(
                notional, forward_rates[i], strike, Ti, sigma, r, tau, is_floor=True
            )
            total_price += floorlet_price

        return total_price

    def _price_swaption(self,
                         notional: float,
                         forward_swap_rate: float,
                         strike: float,
                         T: float,
                         sigma: float,
                         r: float,
                         freq: float) -> float:
        """
        使用Black-76公式为互换期权（Swaption）定价。

        支付方互换期权（Payer Swaption）：
            Swaption = A * [F*N(d1) - K*N(d2)]

        其中 A 为年金因子。

        Args:
            notional: 名义本金
            forward_swap_rate: 远期互换利率 (F)
            strike: 执行互换利率 (K)
            T: 期权到期时间
            sigma: 波动率
            r: 贴现率
            freq: 互换支付频率

        Returns:
            Swaption价格（支付方互换期权）
        """
        if T <= 0:
            return notional * max(forward_swap_rate - strike, 0.0)

        # 计算年金因子
        annuity_factor = self._calculate_annuity_factor(T, freq, r)

        if sigma <= 0 or forward_swap_rate <= 0:
            payoff = max(forward_swap_rate - strike, 0.0)
            return notional * annuity_factor * payoff * np.exp(-r * T)

        d1 = (np.log(forward_swap_rate / strike) + 0.5 * sigma ** 2 * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        df = np.exp(-r * T)
        price = notional * annuity_factor * df * (
            forward_swap_rate * norm.cdf(d1) - strike * norm.cdf(d2)
        )

        return float(price)

    def _calculate_annuity_factor(self,
                                    T: float,
                                    freq: float,
                                    r: float) -> float:
        """
        计算互换年金因子。

        A = sum_{i=1}^{n} freq * exp(-r * T_i)

        其中:
            T_i = T + i * freq  (远期开始的互换)
            n = 总期数（假设互换期限等于一个常见期限）

        Args:
            T: 期权到期时间
            freq: 支付频率（年化）
            r: 贴现率

        Returns:
            年金因子
        """
        # 标准互换：10年期（可根据需要调整）
        swap_tenor = 10.0
        n_periods = int(swap_tenor / freq)

        annuity = 0.0
        for i in range(1, n_periods + 1):
            Ti = T + i * freq
            annuity += freq * np.exp(-r * Ti)

        return float(annuity)

    def _price_cds(self,
                    notional: float,
                    spread_or_rates: Any,
                    recovery: float = None,
                    T: float = None,
                    hazard_rate: float = None,
                    r: float = None) -> float:
        """
        使用简化模型为信用违约互换（CDS）定价。

        Premium Leg = S * sum(DF_i * tau_i * (1 - PD_i))
        Protection Leg = (1 - R) * sum(DF_i * PD_i_conditional)

        其中:
            PD_i = 1 - exp(-lambda * t_i)  (累积违约概率)
            PD_conditional_i = PD_i - PD_{i-1}  (条件违约概率)

        Args:
            notional: 名义本金
            spread_or_rates: CDS利差（年化bps或decimal）
                - 如果是标量float，作为CDS利差
                - 如果是dict，可包含 'spread', 'recovery', 'hazard_rate', 'T', 'r'
            recovery: 回收率（如未提供，默认0.4）
            T: CDS期限（年，如未提供，默认5年）
            hazard_rate: 风险率（如未提供，从利差推导）
            r: 无风险利率

        Returns:
            CDS公允价值（现值）
        """
        # 参数解析
        if isinstance(spread_or_rates, dict):
            params = spread_or_rates
            cds_spread = params.get('spread', 0.01)
            recovery = params.get('recovery', recovery if recovery is not None else 0.4)
            T = params.get('T', T if T is not None else 5.0)
            hazard_rate_input = params.get('hazard_rate', hazard_rate)
            r = params.get('r', r if r is not None else self.risk_free_rate)
        else:
            cds_spread = float(spread_or_rates) if isinstance(spread_or_rates, (int, float)) else 0.01
            recovery = recovery if recovery is not None else 0.4
            T = T if T is not None else 5.0
            hazard_rate_input = hazard_rate
            r = r if r is not None else self.risk_free_rate

        # 从CDS利差近似推导风险率
        # lambda ≈ S / (1 - R)
        if hazard_rate_input is not None:
            lam = hazard_rate_input
        else:
            lam = cds_spread / (1.0 - recovery) if recovery < 1.0 else cds_spread / 0.6

        # 支付频率：季度
        freq = 0.25
        n_periods = max(int(T / freq), 1)

        # === Premium Leg ===
        premium_leg = 0.0
        for i in range(1, n_periods + 1):
            ti = i * freq
            df = np.exp(-r * ti)
            survival_prob = np.exp(-lam * ti)
            premium_leg += df * freq * survival_prob

        premium_leg *= cds_spread * notional

        # === Protection Leg ===
        protection_leg = 0.0
        prev_survival = 1.0
        for i in range(1, n_periods + 1):
            ti = i * freq
            df = np.exp(-r * ti)
            survival_prob = np.exp(-lam * ti)
            default_prob_conditional = prev_survival - survival_prob
            protection_leg += df * default_prob_conditional
            prev_survival = survival_prob

        protection_leg *= (1.0 - recovery) * notional

        # CDS价值 = Protection Leg - Premium Leg（对保护买方而言）
        cds_value = protection_leg - premium_leg

        return float(cds_value)

    def get_supported_methods(self) -> list:
        """获取支持的方法列表。"""
        return ['caplet', 'floorlet', 'cap', 'floor', 'swaption', 'cds']
