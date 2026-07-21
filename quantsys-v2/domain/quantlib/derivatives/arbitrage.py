"""
期权套利检测模块
================

检测期权市场中的无风险套利机会，包括：

套利类型:
    - Put-Call Parity: C - P = S - K*e^(-rT)
    - Box Spread: 使用两个行权价的合成多头/空头
    - Conversion/Reversal: 合成标的与现货的价差
    - Butterfly Arbitrage: 蝶式套利机会检测

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
from typing import Dict, Any, List
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError


class ArbitrageCalculator(BaseCalculator):
    """
    期权套利检测计算器。

    检测期权市场中的常见的无风险套利机会，
    利用期权平价关系和盒式价差等结构识别定价偏差。

    Features:
        - 买卖权平价关系检测
        - 盒式价差套利分析
        - Conversion/Reversal检测
        - 蝶式套利检测

    Example:
        >>> calc = ArbitrageCalculator()
        >>> result = calc.calculate(
        ...     S=100, K_or_strikes=100, T=0.25, r=0.05,
        ...     call_price=5.0, put_price=3.76,
        ...     method='put_call_parity'
        ... )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        初始化期权套利检测计算器。

        Args:
            precision: 结果精度（默认: 6）
            risk_free_rate: 默认无风险利率（默认: 0.0）
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  S: float,
                  K_or_strikes: Any,
                  T: float,
                  r: float,
                  call_price: float = None,
                  put_price: float = None,
                  method: str = 'put_call_parity') -> Dict[str, Any]:
        """
        期权套利检测主入口。

        Args:
            S: 标的资产现货价格
            K_or_strikes:
                - put_call_parity/conversion_reversal: 行权价 (float)
                - box_spread: [K1, K2] 两个行权价
                - butterfly_arbitrage: [K1, K2, K3] 三个行权价
            T: 到期时间（年）
            r: 无风险利率
            call_price: 看涨期权价格
                - put_call_parity/conversion_reversal: float
                - box_spread: [C1, C2]
                - butterfly_arbitrage: [C1, C2, C3]
            put_price: 看跌期权价格
                - put_call_parity/conversion_reversal: float
                - box_spread: [P1, P2]
                - butterfly_arbitrage: 未使用
            method: 检测方法
                - 'put_call_parity'
                - 'box_spread'
                - 'conversion_reversal'
                - 'butterfly_arbitrage'

        Returns:
            Dictionary containing:
                - arbitrage_detected: 是否检测到套利
                - deviation: 偏离度
                - suggested_trade: 建议交易
                - expected_profit: 预期套利利润

        Raises:
            DataValidationError: 输入无效时
            CalculationError: 计算失败时
        """
        method = self.validate_method(method)

        S = self._validate_positive(S, 'spot_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')

        try:
            if method == 'put_call_parity' or method == 'conversion_reversal':
                K = self._validate_positive(K_or_strikes, 'strike')
                C = self._validate_positive(call_price, 'call_price')
                P = self._validate_positive(put_price, 'put_price')

                if method == 'put_call_parity':
                    result = self._check_put_call_parity(S, K, T, r, C, P)
                else:
                    result = self._check_conversion_reversal(S, K, T, r, C, P)

            elif method == 'box_spread':
                strikes = self._validate_numeric_input(K_or_strikes, 'strikes')
                if len(strikes) != 2:
                    raise DataValidationError(
                        "box_spread requires exactly 2 strikes",
                        field_name='K_or_strikes'
                    )
                call_prices = self._validate_numeric_input(call_price, 'call_prices')
                put_prices = self._validate_numeric_input(put_price, 'put_prices')
                if len(call_prices) != 2 or len(put_prices) != 2:
                    raise DataValidationError(
                        "box_spread requires exactly 2 call and 2 put prices",
                        field_name='prices'
                    )
                result = self._analyze_box_spread(
                    strikes, call_prices, put_prices, T, r
                )

            elif method == 'butterfly_arbitrage':
                strikes = self._validate_numeric_input(K_or_strikes, 'strikes')
                if len(strikes) != 3:
                    raise DataValidationError(
                        "butterfly_arbitrage requires exactly 3 strikes",
                        field_name='K_or_strikes'
                    )
                option_prices = self._validate_numeric_input(call_price, 'option_prices')
                if len(option_prices) != 3:
                    raise DataValidationError(
                        "butterfly_arbitrage requires exactly 3 option prices",
                        field_name='call_price_or_prices'
                    )
                result = self._check_butterfly_arbitrage(strikes, option_prices)

            else:
                raise DataValidationError(
                    f"Unknown method: {method}",
                    field_name='method'
                )

            return self._create_result_dict(
                value=result,
                method=method,
                parameters={
                    'S': S, 'T': T, 'r': r
                },
                metadata={
                    'arbitrage_detected': result.get('arbitrage_detected', False),
                    'deviation': result.get('deviation', 0.0)
                }
            )

        except Exception as e:
            raise CalculationError(
                f"Arbitrage detection failed: {str(e)}",
                calculation_type='arbitrage'
            )

    def _check_put_call_parity(self,
                                S: float,
                                K: float,
                                T: float,
                                r: float,
                                C: float,
                                P: float,
                                q: float = 0.0) -> Dict[str, Any]:
        """
        检测买卖权平价偏差。

        Put-Call Parity: C - P = S*e^(-qT) - K*e^(-rT)

        重构：
            C + K*e^(-rT) = P + S*e^(-qT)

        偏差 = (C + K*e^(-rT)) - (P + S)

        如果偏差 > 交易成本：做空合成标的 + 做多实际标的（Conversion）
        如果偏差 < -交易成本：做多合成标的 + 做空实际标的（Reversal）

        Args:
            S: 现货价格
            K: 行权价
            T: 到期时间
            r: 无风险利率
            C: 看涨期权价格
            P: 看跌期权价格
            q: 股息率

        Returns:
            Dictionary with arbitrage analysis
        """
        # 计算平价关系
        lhs = C - P  # 等式左边
        rhs = S * np.exp(-q * T) - K * np.exp(-r * T)  # 等式右边
        deviation = lhs - rhs

        # 隐含的远期价格
        implied_forward_from_options = K + (C - P) * np.exp(r * T)
        implied_forward_from_spot = S * np.exp((r - q) * T)

        # 交易成本估算（典型机构：~0.1-0.5%）
        estimated_cost = 0.002 * S  # 0.2% 估算交易成本

        arbitrage_detected = abs(deviation) > estimated_cost

        if arbitrage_detected:
            if deviation > 0:
                # C相对高估，做空合成标的（卖出C，买入P），做多现货
                suggested_trade = (
                    f"Sell Call @ {C}, Buy Put @ {P}, Buy Stock @ {S}. "
                    f"Expected profit: {deviation - estimated_cost:.4f}"
                )
            else:
                # P相对高估，做多合成标的（买入C，卖出P），做空现货
                suggested_trade = (
                    f"Buy Call @ {C}, Sell Put @ {P}, Sell Stock @ {S}. "
                    f"Expected profit: {-deviation - estimated_cost:.4f}"
                )
        else:
            suggested_trade = "No profitable arbitrage (deviation within transaction costs)"

        return {
            'arbitrage_detected': arbitrage_detected,
            'deviation': float(deviation),
            'deviation_percentage': float(deviation / S * 100.0),
            'lhs': float(lhs),  # C - P
            'rhs': float(rhs),  # S*e^(-qT) - K*e^(-rT)
            'implied_forward_from_options': float(implied_forward_from_options),
            'implied_forward_from_spot': float(implied_forward_from_spot),
            'estimated_transaction_cost': float(estimated_cost),
            'net_arbitrage_profit': float(abs(deviation) - estimated_cost) if arbitrage_detected else 0.0,
            'suggested_trade': suggested_trade,
            'parity_holds': not arbitrage_detected
        }

    def _analyze_box_spread(self,
                             strikes: np.ndarray,
                             call_prices: np.ndarray,
                             put_prices: np.ndarray,
                             T: float,
                             r: float) -> Dict[str, Any]:
        """
        分析盒式价差套利。

        Box Spread = 牛市看涨价差 + 熊市看跌价差

        使用 K1 < K2:
            Bull Call Spread = C(K1) - C(K2)  (做多低行权价C，做空高行权价C)
            Bear Put Spread = P(K2) - P(K1)   (做多高行权价P，做空低行权价P)

        Box Spread成本 = Bull Call Spread + Bear Put Spread
        Box Spread到期价值 = K2 - K1（无风险）

        如果Box成本 != (K2-K1)*e^(-rT)，存在套利。

        Args:
            strikes: [K1, K2]
            call_prices: [C(K1), C(K2)]
            put_prices: [P(K1), P(K2)]
            T: 到期时间
            r: 无风险利率

        Returns:
            Dictionary with box spread analysis
        """
        K1, K2 = strikes[0], strikes[1]
        C1, C2 = call_prices[0], call_prices[1]
        P1, P2 = put_prices[0], put_prices[1]

        # Box Spread成本（做多）
        bull_call = C1 - C2
        bear_put = P2 - P1
        box_cost = bull_call + bear_put  # 购买Box的成本

        # Box到期价值（现值）
        box_payoff = K2 - K1
        box_pv = box_payoff * np.exp(-r * T)

        # 隐含的无风险利率
        if box_cost > 0 and T > 0:
            implied_rate = np.log(box_payoff / box_cost) / T
        else:
            implied_rate = r

        # 偏差
        deviation = box_pv - box_cost

        # 估算标的资产价格（用put-call parity反推）
        S_est = None
        if K1 != K2:
            # 用ATM近似
            S_est = (K1 + K2) / 2 + (C1 - P1) - K1 * np.exp(-r * T)
            if S_est is None or np.isnan(S_est) or S_est <= 0:
                S_est = (K1 + K2) / 2

        # 检测套利
        if S_est is not None and S_est > 0:
            arbitrage_detected = abs(deviation) / S_est > 0.001
        else:
            arbitrage_detected = abs(deviation) > 0.01

        # 检测套利
        if deviation > 0.01:
            # Box被低估：买Box（做多）
            arbitrage_detected = True
            suggested_trade = (
                f"BUY Box Spread: Buy C({K1}) @ {C1}, Sell C({K2}) @ {C2}, "
                f"Buy P({K2}) @ {P2}, Sell P({K1}) @ {P1}. "
                f"Cost: {box_cost:.4f}, PV of Payoff: {box_pv:.4f}, "
                f"Arbitrage profit: {deviation:.4f}"
            )
        elif deviation < -0.01:
            # Box被高估：卖Box（做空）
            arbitrage_detected = True
            suggested_trade = (
                f"SELL Box Spread: Sell C({K1}) @ {C1}, Buy C({K2}) @ {C2}, "
                f"Sell P({K2}) @ {P2}, Buy P({K1}) @ {P1}. "
                f"Proceeds: {box_cost:.4f}, PV of Liability: {box_pv:.4f}, "
                f"Arbitrage profit: {-deviation:.4f}"
            )
        else:
            arbitrage_detected = False
            suggested_trade = "No profitable box spread arbitrage"

        return {
            'arbitrage_detected': arbitrage_detected,
            'K1': float(K1),
            'K2': float(K2),
            'box_cost': float(box_cost),
            'box_payoff': float(box_payoff),
            'box_pv': float(box_pv),
            'deviation': float(deviation),
            'implied_rate': float(implied_rate),
            'implied_rate_annualized': float(implied_rate / T if T > 0 else 0),
            'estimated_S': float(S_est) if S_est else None,
            'suggested_trade': suggested_trade,
            'components': {
                'bull_call_spread': float(bull_call),
                'bear_put_spread': float(bear_put),
                'C1': float(C1), 'C2': float(C2),
                'P1': float(P1), 'P2': float(P2)
            }
        }

    def _check_conversion_reversal(self,
                                     S: float,
                                     K: float,
                                     T: float,
                                     r: float,
                                     C: float,
                                     P: float,
                                     q: float = 0.0) -> Dict[str, Any]:
        """
        检测Conversion/Reversal套利。

        Conversion: 做空合成标的（卖出C，买入P）同时做多现货
            Profit = (C - P + K*e^(-rT) - S*e^(-qT))

        Reversal: 做多合成标的（买入C，卖出P）同时做空现货
            Profit = (S*e^(-qT) - C + P - K*e^(-rT))

        Args:
            S, K, T, r, C, P: 标准参数
            q: 股息率

        Returns:
            Dictionary with conversion/reversal analysis
        """
        # 合成多头成本 = C - P + K*e^(-rT)
        synthetic_long_cost = C - P + K * np.exp(-r * T)

        # 现货现值（调整股息）
        spot_pv = S * np.exp(-q * T)

        # Conversion: 做空合成标的 + 做多现货
        conversion_profit = spot_pv - synthetic_long_cost  # = rhs - lhs = -(lhs-rhs)

        # Reversal: 做多合成标的 + 做空现货
        reversal_profit = synthetic_long_cost - spot_pv

        # 交易成本估算
        est_cost = 0.002 * S

        if conversion_profit > est_cost:
            arbitrage_detected = True
            suggested_trade = (
                f"CONVERSION: Sell Call @ {C}, Buy Put @ {P}, Buy Stock @ {S}. "
                f"Expected profit: {conversion_profit - est_cost:.4f} per share"
            )
        elif reversal_profit > est_cost:
            arbitrage_detected = True
            suggested_trade = (
                f"REVERSAL: Buy Call @ {C}, Sell Put @ {P}, Sell Stock @ {S}. "
                f"Expected profit: {reversal_profit - est_cost:.4f} per share"
            )
        else:
            arbitrage_detected = False
            suggested_trade = "No profitable conversion/reversal opportunity"

        return {
            'arbitrage_detected': arbitrage_detected,
            'conversion_profit': float(conversion_profit),
            'reversal_profit': float(reversal_profit),
            'synthetic_long_cost': float(synthetic_long_cost),
            'spot_pv': float(spot_pv),
            'estimated_transaction_cost': float(est_cost),
            'net_arbitrage_profit': float(max(conversion_profit, reversal_profit) - est_cost) if arbitrage_detected else 0.0,
            'suggested_trade': suggested_trade
        }

    def _check_butterfly_arbitrage(self,
                                    strikes: np.ndarray,
                                    option_prices: np.ndarray,
                                    option_type: str = 'call') -> Dict[str, Any]:
        """
        检测蝶式套利机会。

        蝶式组合不应有负价格（无套利条件）：
            对于 K1 < K2 < K3:
            Butterfly价格 = C(K1) - 2*C(K2) + C(K3) >= 0

        如果蝶式价格为负，存在套利机会。

        Args:
            strikes: [K1, K2, K3]，等间距
            option_prices: [C(K1), C(K2), C(K3)] 或 [P(K1), P(K2), P(K3)]
            option_type: 'call' 或 'put'

        Returns:
            Dictionary with butterfly arbitrage analysis
        """
        K1, K2, K3 = strikes[0], strikes[1], strikes[2]
        C1, C2, C3 = option_prices[0], option_prices[1], option_prices[2]

        # 蝶式价格
        butterfly_price = C1 - 2.0 * C2 + C3

        # 理论最大收益发生在K2处
        max_payoff = (K2 - K1)  # 蝶式宽度

        # 套利检测
        arbitrage_detected = butterfly_price < -0.001  # 负蝶式价格

        if arbitrage_detected:
            if butterfly_price < 0:
                suggested_trade = (
                    f"BUTTERFLY ARBITRAGE: Sell butterfly (Sell {option_type} @ {K1} and {K3}, "
                    f"Buy 2x {option_type} @ {K2}). "
                    f"Premium received: {-butterfly_price:.4f}, Max payoff at {K2}: {max_payoff:.4f}"
                )
            else:
                suggested_trade = "No negative butterfly detected"
        else:
            # 检查凸性违规：外部加权平均 < 内部
            weight = (K3 - K2) / (K3 - K1) if K3 != K1 else 0.5
            convexity_check = C2 - (weight * C1 + (1 - weight) * C3)

            if convexity_check > 0.001:
                suggested_trade = (
                    f"CONVEXITY ARBITRAGE: Butterfly too cheap. "
                    f"Buy {option_type} @ {K1} and {K3}, Sell 2x {option_type} @ {K2}. "
                    f"Expected convexity value: {convexity_check:.4f}"
                )
            else:
                suggested_trade = "No butterfly arbitrage opportunity"

        return {
            'arbitrage_detected': arbitrage_detected or butterfly_price < 0,
            'butterfly_price': float(butterfly_price),
            'K1': float(K1), 'K2': float(K2), 'K3': float(K3),
            'spread_width': float(K2 - K1),
            'max_payoff_at_K2': float(max_payoff),
            'price_per_strike': {
                f'{option_type}({K1})': float(C1),
                f'{option_type}({K2})': float(C2),
                f'{option_type}({K3})': float(C3)
            },
            'suggested_trade': suggested_trade
        }

    def get_supported_methods(self) -> list:
        """获取支持的方法列表。"""
        return ['put_call_parity', 'box_spread', 'conversion_reversal', 'butterfly_arbitrage']
