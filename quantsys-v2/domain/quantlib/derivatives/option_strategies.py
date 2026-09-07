"""
期权策略分析模块
================

多腿期权策略的收益/风险分析，支持常见组合策略的盈亏分析。

支持的策略:
    - 跨式 (Straddle)
    - 宽跨式 (Strangle)
    - 蝶式 (Butterfly)
    - 秃鹰式 (Condor)
    - 价差 (Vertical/Bull/Bear Spread)
    - 日历价差 (Calendar Spread)

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
from scipy.stats import norm
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError


@dataclass
class OptionLeg:
    """
    期权腿数据结构。

    Attributes:
        option_type: 'call' 或 'put'
        strike: 行权价
        position: 持仓方向 (+1 多头, -1 空头)
        quantity: 合约数量
        premium: 期权费（每合约）
        expiry: 到期时间（年，可选）
    """
    option_type: str
    strike: float
    position: int  # +1 for long, -1 for short
    quantity: float = 1.0
    premium: float = 0.0
    expiry: Optional[float] = None

    def __post_init__(self):
        """验证期权腿参数。"""
        if self.option_type not in ('call', 'put'):
            raise ValueError(f"option_type must be 'call' or 'put', got '{self.option_type}'")
        if self.strike <= 0:
            raise ValueError(f"strike must be positive, got {self.strike}")
        if self.position not in (-1, 1):
            raise ValueError(f"position must be +1 or -1, got {self.position}")
        if self.quantity <= 0:
            raise ValueError(f"quantity must be positive, got {self.quantity}")


class OptionStrategiesCalculator(BaseCalculator):
    """
    期权策略分析计算器。

    分析多腿期权组合策略的盈亏特征，包括盈亏曲线、盈亏平衡点、
    最大盈亏和分析性Greeks。

    Features:
        - 自定义多腿策略盈亏分析
        - 标准策略快速分析（跨式、宽跨式、蝶式等）
        - 盈亏平衡点计算
        - 最大盈亏计算
        - 组合Greeks计算

    Example:
        >>> calc = OptionStrategiesCalculator()
        >>> legs = [
        ...     {'option_type': 'call', 'strike': 100, 'position': 1, 'premium': 5},
        ...     {'option_type': 'put', 'strike': 100, 'position': 1, 'premium': 5}
        ... ]
        >>> result = calc.calculate(legs=legs, S=100, method='breakeven')
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        初始化期权策略分析计算器。

        Args:
            precision: 结果精度（默认: 6）
            risk_free_rate: 默认无风险利率（默认: 0.0）
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def _parse_legs(self, legs: List[Dict]) -> List[OptionLeg]:
        """
        将字典列表解析为OptionLeg对象列表。

        Args:
            legs: 期权腿字典列表

        Returns:
            OptionLeg对象列表

        Raises:
            DataValidationError: 解析失败时
        """
        parsed = []
        for i, leg in enumerate(legs):
            try:
                parsed.append(OptionLeg(**leg))
            except (ValueError, TypeError) as e:
                raise DataValidationError(
                    f"Invalid leg at index {i}: {e}",
                    field_name=f'legs[{i}]'
                )
        if len(parsed) == 0:
            raise DataValidationError(
                "At least one option leg is required",
                field_name='legs'
            )
        return parsed

    def calculate(self,
                  legs: List[Dict],
                  S: float,
                  T: float = 0.04,
                  sigma: float = 0.2,
                  r: float = 0.05,
                  method: str = 'pnl_profile') -> Dict[str, Any]:
        """
        计算期权策略的盈亏分析。

        Args:
            legs: 期权腿列表 [{'option_type', 'strike', 'position', 'quantity', 'premium', 'expiry'}]
            S: 当前标的资产价格
            T: 到期时间（年，默认: 0.04 约为2周）
            sigma: 波动率（默认: 0.2）
            r: 无风险利率（默认: 0.05）
            method: 分析方法
                - 'pnl_profile': 盈亏曲线
                - 'breakeven': 盈亏平衡点
                - 'max_profit_loss': 最大盈亏
                - 'greeks': 组合Greeks

        Returns:
            Dictionary containing analysis results

        Raises:
            DataValidationError: 输入无效时
            CalculationError: 计算失败时
        """
        method = self.validate_method(method)

        S = self._validate_positive(S, 'spot_price')
        T = self._validate_positive(T, 'time_to_maturity')
        sigma = self._validate_positive(sigma, 'volatility')
        r = self._validate_numeric_input(r, 'risk_free_rate')

        option_legs = self._parse_legs(legs)

        try:
            if method == 'pnl_profile':
                result = self._calculate_pnl_profile(option_legs, S, T, sigma, r)
            elif method == 'breakeven':
                result = self._calculate_breakeven(option_legs, S)
            elif method == 'max_profit_loss':
                result = self._calculate_max_profit_loss(option_legs, S)
            elif method == 'greeks':
                result = self._calculate_portfolio_greeks(option_legs, S, T, sigma, r)
            else:
                raise CalculationError(
                    f"Unknown method: {method}",
                    calculation_type='option_strategies'
                )

            return self._create_result_dict(
                value=result,
                method=method,
                parameters={
                    'S': S, 'T': T, 'sigma': sigma, 'r': r,
                    'n_legs': len(option_legs)
                },
                metadata={
                    'legs': [asdict(leg) for leg in option_legs]
                }
            )

        except Exception as e:
            raise CalculationError(
                f"Option strategy analysis failed: {str(e)}",
                calculation_type='option_strategies'
            )

    def _calculate_pnl_profile(self,
                                legs: List[OptionLeg],
                                S: float,
                                T: float,
                                sigma: float,
                                r: float) -> Dict[str, Any]:
        """
        计算策略的盈亏曲线。

        Returns:
            Dictionary with spot_prices, pnl_values, current_pnl
        """
        # 生成标的资产价格范围（覆盖所有行权价的+/-50%）
        all_strikes = [leg.strike for leg in legs]
        min_S = min(all_strikes) * 0.5
        max_S = max(all_strikes) * 1.5
        spot_range = np.linspace(min_S, max_S, 200)

        def option_payoff(leg: OptionLeg, spot: float) -> float:
            """计算单腿期权到期收益。"""
            if leg.option_type == 'call':
                intrinsic = max(spot - leg.strike, 0)
            else:
                intrinsic = max(leg.strike - spot, 0)
            return leg.position * leg.quantity * (intrinsic - leg.premium)

        pnl_values = np.zeros_like(spot_range)
        for leg in legs:
            pnl_values += np.array([option_payoff(leg, s) for s in spot_range])

        # 当前理论P&L（使用BSM价格）
        current_pnl = self._calculate_current_pnl(legs, S, T, sigma, r)

        return {
            'spot_prices': spot_range.tolist(),
            'pnl_values': pnl_values.tolist(),
            'current_pnl': current_pnl,
            'S_current': S
        }

    def _calculate_breakeven(self,
                              legs: List[OptionLeg],
                              S: float) -> Dict[str, Any]:
        """
        计算策略的盈亏平衡点。

        Returns:
            Dictionary with breakeven_points, description
        """
        # 总净期权费收入（正=净收入，负=净支出）
        net_premium = sum(
            -leg.position * leg.quantity * leg.premium
            for leg in legs
        )

        # 在到期时，每个行权价处发生斜率变化
        # 盈亏平衡点是P&L=0的标的资产价格
        all_strikes = sorted(set(leg.strike for leg in legs))
        min_S = min(all_strikes) * 0.7
        max_S = max(all_strikes) * 1.3

        def payoff_at_expiry(spot: float) -> float:
            total = 0.0
            for leg in legs:
                if leg.option_type == 'call':
                    intrinsic = max(spot - leg.strike, 0)
                else:
                    intrinsic = max(leg.strike - spot, 0)
                total += leg.position * leg.quantity * (intrinsic - leg.premium)
            return total

        # 在边界和每个行权价之间搜索盈亏平衡点
        check_points = sorted(set([min_S] + all_strikes + [max_S]))
        breakevens = []

        for i in range(len(check_points) - 1):
            a = check_points[i]
            b = check_points[i + 1]
            fa = payoff_at_expiry(a)
            fb = payoff_at_expiry(b)

            if fa * fb <= 0:
                # 有零点，二分查找
                for _ in range(50):
                    mid = (a + b) / 2.0
                    fmid = payoff_at_expiry(mid)
                    if abs(fmid) < 1e-6:
                        breakevens.append(mid)
                        break
                    if fa * fmid <= 0:
                        b = mid
                        fb = fmid
                    else:
                        a = mid
                        fa = fmid

        breakevens = sorted(set(round(be, 4) for be in breakevens))

        return {
            'breakeven_points': breakevens,
            'net_premium': net_premium,
            'description': f"Breakeven(s) at: {breakevens}" if breakevens else "No breakeven points found"
        }

    def _calculate_max_profit_loss(self,
                                    legs: List[OptionLeg],
                                    S: float) -> Dict[str, Any]:
        """
        计算策略的最大盈亏。

        Returns:
            Dictionary with max_profit, max_loss, risk_reward_ratio
        """
        # 生成宽范围的标的资产价格
        all_strikes = [leg.strike for leg in legs]
        min_S = min(all_strikes) * 0.3
        max_S = max(all_strikes) * 1.7

        def payoff_at_expiry(spot: float) -> float:
            total = 0.0
            for leg in legs:
                if leg.option_type == 'call':
                    intrinsic = max(spot - leg.strike, 0)
                else:
                    intrinsic = max(leg.strike - spot, 0)
                total += leg.position * leg.quantity * (intrinsic - leg.premium)
            return total

        # 在所有行权价和端点搜索
        search_points = np.linspace(min_S, max_S, 1000)
        pnl_values = np.array([payoff_at_expiry(s) for s in search_points])

        max_profit = float(np.max(pnl_values)) if len(pnl_values) > 0 else 0.0
        max_loss = float(np.min(pnl_values)) if len(pnl_values) > 0 else 0.0

        risk_reward = abs(max_profit / max_loss) if max_loss != 0 and max_loss < 0 else float('inf')

        # 由于线性性，极值出现在行权价或边界处
        # 验证行权价处的极值
        for strike in all_strikes:
            pnl_at_strike = payoff_at_expiry(strike)
            max_profit = max(max_profit, pnl_at_strike)
            max_loss = min(max_loss, pnl_at_strike)

        return {
            'max_profit': max_profit,
            'max_loss': max_loss,
            'max_profit_unlimited': max_profit > 1e8,
            'max_loss_unlimited': max_loss < -1e8,
            'risk_reward_ratio': risk_reward if risk_reward != float('inf') else None,
            'net_premium_paid': sum(leg.position * leg.quantity * leg.premium for leg in legs)
        }

    def _calculate_portfolio_greeks(self,
                                     legs: List[OptionLeg],
                                     S: float,
                                     T: float,
                                     sigma: float,
                                     r: float) -> Dict[str, Any]:
        """
        计算期权组合的聚合Greeks。

        Returns:
            Dictionary with aggregated Greeks
        """
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        total_rho = 0.0
        total_value = 0.0

        for leg in legs:
            expiry = leg.expiry if leg.expiry is not None else T

            if expiry <= 0:
                continue

            # 使用BSM公式计算单腿Greeks
            d1 = (np.log(S / leg.strike) + (r + 0.5 * sigma ** 2) * expiry) / (sigma * np.sqrt(expiry))
            d2 = d1 - sigma * np.sqrt(expiry)
            n_d1 = norm.pdf(d1)

            # 单腿期权价格
            if leg.option_type == 'call':
                leg_price = S * norm.cdf(d1) - leg.strike * np.exp(-r * expiry) * norm.cdf(d2)
                leg_delta = norm.cdf(d1)
                leg_theta_term = -r * leg.strike * np.exp(-r * expiry) * norm.cdf(d2)
                leg_rho = leg.strike * expiry * np.exp(-r * expiry) * norm.cdf(d2) / 100.0
            else:
                leg_price = leg.strike * np.exp(-r * expiry) * norm.cdf(-d2) - S * norm.cdf(-d1)
                leg_delta = -norm.cdf(-d1)
                leg_theta_term = r * leg.strike * np.exp(-r * expiry) * norm.cdf(-d2)
                leg_rho = -leg.strike * expiry * np.exp(-r * expiry) * norm.cdf(-d2) / 100.0

            leg_gamma = n_d1 / (S * sigma * np.sqrt(expiry))
            leg_theta = (-(S * n_d1 * sigma) / (2 * np.sqrt(expiry)) + leg_theta_term) / 365.0
            leg_vega = S * n_d1 * np.sqrt(expiry) / 100.0

            # 聚合
            multiplier = leg.position * leg.quantity
            total_delta += leg_delta * multiplier
            total_gamma += leg_gamma * multiplier
            total_theta += leg_theta * multiplier
            total_vega += leg_vega * multiplier
            total_rho += leg_rho * multiplier
            total_value += leg_price * multiplier

        return {
            'delta': total_delta,
            'gamma': total_gamma,
            'theta': total_theta,
            'vega': total_vega,
            'rho': total_rho,
            'theoretical_value': total_value
        }

    def _calculate_current_pnl(self,
                                legs: List[OptionLeg],
                                S: float,
                                T: float,
                                sigma: float,
                                r: float) -> float:
        """计算当前理论P&L（基于BSM价格差异）。"""
        total_pnl = 0.0
        for leg in legs:
            expiry = leg.expiry if leg.expiry is not None else T
            if expiry <= 0:
                continue

            d1 = (np.log(S / leg.strike) + (r + 0.5 * sigma ** 2) * expiry) / (sigma * np.sqrt(expiry))
            d2 = d1 - sigma * np.sqrt(expiry)

            if leg.option_type == 'call':
                current_value = S * norm.cdf(d1) - leg.strike * np.exp(-r * expiry) * norm.cdf(d2)
            else:
                current_value = leg.strike * np.exp(-r * expiry) * norm.cdf(-d2) - S * norm.cdf(-d1)

            total_pnl += leg.position * leg.quantity * (current_value - leg.premium)

        return total_pnl

    # ===== 标准策略分析 =====

    def analyze_straddle(self,
                          S: float,
                          K: float,
                          premium_call: float,
                          premium_put: float,
                          qty: int = 1) -> Dict[str, Any]:
        """
        分析跨式策略（买入相同行权价的看涨和看跌期权）。

        Args:
            S: 标的资产当前价格
            K: 行权价
            premium_call: 看涨期权费
            premium_put: 看跌期权费
            qty: 数量

        Returns:
            Dictionary with strategy analysis
        """
        legs = [
            {'option_type': 'call', 'strike': K, 'position': 1,
             'quantity': float(qty), 'premium': premium_call},
            {'option_type': 'put', 'strike': K, 'position': 1,
             'quantity': float(qty), 'premium': premium_put}
        ]
        breakeven = self._calculate_breakeven(self._parse_legs(legs), S)
        max_pl = self._calculate_max_profit_loss(self._parse_legs(legs), S)

        total_cost = qty * (premium_call + premium_put)

        return {
            'strategy': 'long_straddle',
            'strike': K,
            'total_cost': total_cost,
            'breakeven_up': K + (premium_call + premium_put),
            'breakeven_down': K - (premium_call + premium_put),
            'max_profit': max_pl.get('max_profit'),
            'max_loss': -total_cost,
            'breakeven_points': breakeven.get('breakeven_points', []),
            'S_current': S
        }

    def analyze_strangle(self,
                          S: float,
                          K_call: float,
                          K_put: float,
                          premium_call: float,
                          premium_put: float,
                          qty: int = 1) -> Dict[str, Any]:
        """
        分析宽跨式策略（买入不同行权价的看涨和看跌期权）。

        Args:
            S: 标的资产当前价格
            K_call: 看涨行权价
            K_put: 看跌行权价
            premium_call: 看涨期权费
            premium_put: 看跌期权费
            qty: 数量

        Returns:
            Dictionary with strategy analysis
        """
        legs = [
            {'option_type': 'call', 'strike': K_call, 'position': 1,
             'quantity': float(qty), 'premium': premium_call},
            {'option_type': 'put', 'strike': K_put, 'position': 1,
             'quantity': float(qty), 'premium': premium_put}
        ]
        breakeven = self._calculate_breakeven(self._parse_legs(legs), S)

        total_cost = qty * (premium_call + premium_put)

        return {
            'strategy': 'long_strangle',
            'K_call': K_call,
            'K_put': K_put,
            'total_cost': total_cost,
            'breakeven_up': K_call + (premium_call + premium_put),
            'breakeven_down': K_put - (premium_call + premium_put),
            'max_loss': -total_cost,
            'breakeven_points': breakeven.get('breakeven_points', []),
            'S_current': S
        }

    def analyze_butterfly(self,
                           S: float,
                           K_low: float,
                           K_mid: float,
                           K_high: float,
                           premiums: List[float],
                           option_type: str = 'call',
                           qty: int = 1) -> Dict[str, Any]:
        """
        分析蝶式策略。

        买入一份低行权价期权 + 一份高行权价期权，卖出两份中间行权价期权。

        Args:
            S: 标的资产当前价格
            K_low: 低行权价
            K_mid: 中间行权价
            K_high: 高行权价
            premiums: [premium_low, premium_mid, premium_high]
            option_type: 'call' 或 'put'（默认: 'call'）
            qty: 数量

        Returns:
            Dictionary with strategy analysis
        """
        if len(premiums) != 3:
            raise DataValidationError(
                "premiums must have 3 values for butterfly",
                field_name='premiums'
            )

        legs = [
            {'option_type': option_type, 'strike': K_low, 'position': 1,
             'quantity': float(qty), 'premium': premiums[0]},
            {'option_type': option_type, 'strike': K_mid, 'position': -1,
             'quantity': float(qty * 2), 'premium': premiums[1]},
            {'option_type': option_type, 'strike': K_high, 'position': 1,
             'quantity': float(qty), 'premium': premiums[2]}
        ]

        parsed_legs = self._parse_legs(legs)
        breakeven = self._calculate_breakeven(parsed_legs, S)
        max_pl = self._calculate_max_profit_loss(parsed_legs, S)

        net_debit = qty * (premiums[0] - 2 * premiums[1] + premiums[2])

        return {
            'strategy': f'long_{option_type}_butterfly',
            'K_low': K_low,
            'K_mid': K_mid,
            'K_high': K_high,
            'net_debit': net_debit,
            'max_profit_at': K_mid,
            'max_profit': max_pl.get('max_profit'),
            'max_loss': max_pl.get('max_loss'),
            'breakeven_points': breakeven.get('breakeven_points', []),
            'S_current': S
        }

    def analyze_condor(self,
                        S: float,
                        K1: float,
                        K2: float,
                        K3: float,
                        K4: float,
                        premiums: List[float],
                        option_type: str = 'call',
                        qty: int = 1) -> Dict[str, Any]:
        """
        分析秃鹰式策略（比蝶式更宽的行权价间距）。

        买入K1和K4期权，卖出K2和K3期权。

        Args:
            S: 标的资产当前价格
            K1: 最低行权价
            K2: 次低行权价
            K3: 次高行权价
            K4: 最高行权价
            premiums: [premium_K1, premium_K2, premium_K3, premium_K4]
            option_type: 'call' 或 'put'（默认: 'call'）
            qty: 数量

        Returns:
            Dictionary with strategy analysis
        """
        if len(premiums) != 4:
            raise DataValidationError(
                "premiums must have 4 values for condor",
                field_name='premiums'
            )

        legs = [
            {'option_type': option_type, 'strike': K1, 'position': 1,
             'quantity': float(qty), 'premium': premiums[0]},
            {'option_type': option_type, 'strike': K2, 'position': -1,
             'quantity': float(qty), 'premium': premiums[1]},
            {'option_type': option_type, 'strike': K3, 'position': -1,
             'quantity': float(qty), 'premium': premiums[2]},
            {'option_type': option_type, 'strike': K4, 'position': 1,
             'quantity': float(qty), 'premium': premiums[3]}
        ]

        parsed_legs = self._parse_legs(legs)
        breakeven = self._calculate_breakeven(parsed_legs, S)
        max_pl = self._calculate_max_profit_loss(parsed_legs, S)

        net_debit = qty * (premiums[0] - premiums[1] - premiums[2] + premiums[3])

        return {
            'strategy': f'long_{option_type}_condor',
            'K1': K1, 'K2': K2, 'K3': K3, 'K4': K4,
            'net_debit': net_debit,
            'max_profit': max_pl.get('max_profit'),
            'max_loss': max_pl.get('max_loss'),
            'breakeven_points': breakeven.get('breakeven_points', []),
            'S_current': S
        }

    def analyze_spread(self,
                        S: float,
                        K_long: float,
                        K_short: float,
                        premium_long: float,
                        premium_short: float,
                        option_type: str = 'call',
                        qty: int = 1) -> Dict[str, Any]:
        """
        分析垂直价差策略（买入一份期权，卖出一份不同行权价的同类型期权）。

        Args:
            S: 标的资产当前价格
            K_long: 买入期权的行权价
            K_short: 卖出期权的行权价
            premium_long: 买入期权的期权费
            premium_short: 卖出期权的期权费
            option_type: 'call' 或 'put'（默认: 'call'）
            qty: 数量

        Returns:
            Dictionary with strategy analysis
        """
        legs = [
            {'option_type': option_type, 'strike': K_long, 'position': 1,
             'quantity': float(qty), 'premium': premium_long},
            {'option_type': option_type, 'strike': K_short, 'position': -1,
             'quantity': float(qty), 'premium': premium_short}
        ]

        parsed_legs = self._parse_legs(legs)
        breakeven = self._calculate_breakeven(parsed_legs, S)
        max_pl = self._calculate_max_profit_loss(parsed_legs, S)

        net_debit = qty * (premium_long - premium_short)
        spread_width = abs(K_long - K_short)

        # 判断是牛市还是熊市价差
        if option_type == 'call':
            direction = 'bull' if K_long < K_short else 'bear'
        else:
            direction = 'bull' if K_long > K_short else 'bear'

        return {
            'strategy': f'{direction}_{option_type}_spread',
            'K_long': K_long,
            'K_short': K_short,
            'spread_width': spread_width,
            'net_debit': net_debit,
            'max_profit': max_pl.get('max_profit'),
            'max_loss': max_pl.get('max_loss'),
            'breakeven_points': breakeven.get('breakeven_points', []),
            'S_current': S
        }

    def analyze_calendar(self,
                          S: float,
                          K: float,
                          T_long: float,
                          T_short: float,
                          premium_long: float,
                          premium_short: float,
                          sigma: float,
                          r: float,
                          qty: int = 1) -> Dict[str, Any]:
        """
        分析日历价差策略（买入远月期权，卖出近月相同行权价的期权）。

        Args:
            S: 标的资产当前价格
            K: 行权价
            T_long: 远月到期时间（年）
            T_short: 近月到期时间（年）
            premium_long: 远月期权费
            premium_short: 近月期权费
            sigma: 波动率
            r: 无风险利率
            qty: 数量

        Returns:
            Dictionary with strategy analysis
        """
        if T_long <= T_short:
            raise DataValidationError(
                "T_long must be greater than T_short for calendar spread",
                field_name='T_long'
            )

        # 近月到期时的远月期权理论价值
        remaining_T = T_long - T_short
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * remaining_T) / (sigma * np.sqrt(remaining_T))
        d2 = d1 - sigma * np.sqrt(remaining_T)

        long_forward_value = S * norm.cdf(d1) - K * np.exp(-r * remaining_T) * norm.cdf(d2)

        net_debit = qty * (premium_long - premium_short)
        max_profit_theoretical = long_forward_value - net_debit  # 近似

        legs = [
            {'option_type': 'call', 'strike': K, 'position': 1,
             'quantity': float(qty), 'premium': premium_long, 'expiry': T_long},
            {'option_type': 'call', 'strike': K, 'position': -1,
             'quantity': float(qty), 'premium': premium_short, 'expiry': T_short}
        ]

        return {
            'strategy': 'long_calendar_spread',
            'strike': K,
            'T_long': T_long,
            'T_short': T_short,
            'net_debit': net_debit,
            'max_profit_at_expiry_short': max_profit_theoretical,
            'max_loss': -net_debit,
            'near_expiry_theoretical_value': long_forward_value,
            'S_current': S
        }

    def get_supported_methods(self) -> list:
        """获取支持的方法列表。"""
        return ['pnl_profile', 'breakeven', 'max_profit_loss', 'greeks']
