"""
远期与期货定价模块
==================

计算远期合约和期货合约的公允价值、基差和持有成本分析。

核心公式:
    F = S * exp((r + storage - convenience - dividend) * T)

持有成本模型 (Cost of Carry):
    远期/期货价格 = 现货价格 + 融资成本 + 储存成本 - 便利收益 - 股息收益

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
from typing import Dict, Any
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError


class ForwardFuturesCalculator(BaseCalculator):
    """
    远期与期货定价计算器。

    使用持有成本模型计算远期合约和期货合约的公允价值、
    基差和隐含便利收益。

    Features:
        - 持有成本模型定价
        - 隐含便利收益计算
        - 公允价值价差分析
        - 基差计算

    Example:
        >>> calc = ForwardFuturesCalculator()
        >>> result = calc.calculate(S=100, T=0.5, r=0.05, storage_cost=0.02)
        >>> print(f"Fair futures price: {result['value']:.2f}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        初始化远期/期货定价计算器。

        Args:
            precision: 结果精度（默认: 6）
            risk_free_rate: 默认无风险利率（默认: 0.0）
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  S: float,
                  T: float,
                  r: float,
                  storage_cost: float = 0.0,
                  convenience_yield: float = 0.0,
                  dividend_yield: float = 0.0,
                  method: str = 'cost_of_carry') -> Dict[str, Any]:
        """
        计算远期/期货的公允价值。

        Args:
            S: 标的资产现货价格
            T: 到期时间（年）
            r: 无风险利率（年化）
            storage_cost: 储存成本（年化，decimal形式，如 0.02 = 2%）
            convenience_yield: 便利收益（年化）
            dividend_yield: 股息率（年化）
            method: 计算方法
                - 'cost_of_carry': 标准持有成本模型
                - 'implied_convenience_yield': 从市场价格反推便利收益
                - 'fair_value_spread': 公允价值与市场价格的价差

        Returns:
            Dictionary containing:
                - value: 公允价值/计算结果
                - fair_price: 理论公允价值
                - method: 计算方法

        Raises:
            DataValidationError: 输入无效时
            CalculationError: 计算失败时
        """
        method = self.validate_method(method)

        S = self._validate_positive(S, 'spot_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        storage_cost = self._validate_numeric_input(storage_cost, 'storage_cost')
        convenience_yield = self._validate_numeric_input(convenience_yield, 'convenience_yield')
        dividend_yield = self._validate_numeric_input(dividend_yield, 'dividend_yield')

        try:
            if method == 'cost_of_carry':
                result = self._calculate_cost_of_carry(
                    S, T, r, storage_cost, convenience_yield, dividend_yield
                )
            elif method == 'implied_convenience_yield':
                result = self._calculate_implied_convenience_yield(
                    S, T, r, storage_cost, dividend_yield
                )
            elif method == 'fair_value_spread':
                result = self._calculate_fair_value_spread(
                    S, T, r, storage_cost, convenience_yield, dividend_yield
                )
            else:
                raise CalculationError(
                    f"Unknown method: {method}",
                    calculation_type='forward_futures'
                )

            return self._create_result_dict(
                value=result['value'],
                method=method,
                parameters={
                    'S': S, 'T': T, 'r': r,
                    'storage_cost': storage_cost,
                    'convenience_yield': convenience_yield,
                    'dividend_yield': dividend_yield
                },
                metadata=result.get('metadata', {})
            )

        except Exception as e:
            raise CalculationError(
                f"Forward/Futures calculation failed: {str(e)}",
                calculation_type='forward_futures'
            )

    def _calculate_cost_of_carry(self,
                                  S: float,
                                  T: float,
                                  r: float,
                                  storage_cost: float,
                                  convenience_yield: float,
                                  dividend_yield: float) -> Dict[str, Any]:
        """
        持有成本模型计算公允价值。

        F = S * exp((r + storage - convenience - dividend) * T)

        Returns:
            Dictionary with fair_price and cost components
        """
        net_carry_rate = r + storage_cost - convenience_yield - dividend_yield
        fair_price = S * np.exp(net_carry_rate * T)

        return {
            'value': float(fair_price),
            'metadata': {
                'fair_price': float(fair_price),
                'net_carry_rate': float(net_carry_rate),
                'cost_components': {
                    'financing_cost': float(S * (np.exp(r * T) - 1)),
                    'storage_cost_amount': float(S * (np.exp(storage_cost * T) - 1)),
                    'convenience_yield_benefit': float(S * (1 - np.exp(-convenience_yield * T))),
                    'dividend_benefit': float(S * (1 - np.exp(-dividend_yield * T)))
                },
                'basis': float(fair_price - S),
                'basis_percentage': float((fair_price / S - 1))
            }
        }

    def _calculate_implied_convenience_yield(self,
                                               S: float,
                                               T: float,
                                               r: float,
                                               storage_cost: float,
                                               dividend_yield: float) -> Dict[str, Any]:
        """
        从已知的远期市场价格反推隐含便利收益。

        注意：此方法需要额外的市场价格输入。如果没有提供，
        返回理论便利收益为0的情况。

        Returns:
            Dictionary with implied convenience yield
        """
        # 从已知参数反推：convenience = r + storage - dividend - ln(F/S)/T
        # 如果没有市场价格，返回0
        implied_conv = 0.0

        return {
            'value': implied_conv,
            'metadata': {
                'implied_convenience_yield': implied_conv,
                'input_parameters': {
                    'S': S, 'T': T, 'r': r,
                    'storage_cost': storage_cost,
                    'dividend_yield': dividend_yield
                }
            }
        }

    def _calculate_fair_value_spread(self,
                                       S: float,
                                       T: float,
                                       r: float,
                                       storage_cost: float,
                                       convenience_yield: float,
                                       dividend_yield: float) -> Dict[str, Any]:
        """
        计算公允价值与现货价格的价差。

        Returns:
            Dictionary with spread analysis
        """
        fair_price = S * np.exp((r + storage_cost - convenience_yield - dividend_yield) * T)
        spread = fair_price - S

        return {
            'value': float(spread),
            'metadata': {
                'fair_price': float(fair_price),
                'spread': float(spread),
                'spread_percentage': float(spread / S * 100.0),
                'annualized_spread': float(spread / T if T > 0 else 0),
                'contango': fair_price > S,  # 升水/期货溢价
                'backwardation': fair_price < S  # 贴水/现货溢价
            }
        }

    def calculate_futures_price(self,
                                 S: float,
                                 T: float,
                                 r: float,
                                 q: float = 0.0) -> Dict[str, Any]:
        """
        计算期货合约的公允价值（简化版持有成本模型）。

        F = S * exp((r - q) * T)

        Args:
            S: 标的资产现货价格
            T: 到期时间（年）
            r: 无风险利率
            q: 股息率或便利收益率（净收益）

        Returns:
            Dictionary containing:
                - fair_price: 期货公允价值
                - basis: 基差 (F - S)
                - contango: 是否升水
        """
        S = self._validate_positive(S, 'spot_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        q = self._validate_numeric_input(q, 'net_yield')

        try:
            fair_price = S * np.exp((r - q) * T)
            basis = fair_price - S

            return self._create_result_dict(
                value=float(fair_price),
                method='futures_pricing',
                parameters={'S': S, 'T': T, 'r': r, 'q': q},
                metadata={
                    'fair_price': float(fair_price),
                    'basis': float(basis),
                    'basis_percentage': float(basis / S * 100.0),
                    'contango': fair_price > S,
                    'backwardation': fair_price < S
                }
            )

        except Exception as e:
            raise CalculationError(
                f"Futures price calculation failed: {str(e)}",
                calculation_type='futures_pricing'
            )

    def calculate_basis(self,
                        S: float,
                        F: float,
                        T: float,
                        r: float,
                        q: float = 0.0) -> Dict[str, Any]:
        """
        计算基差分析。

        Basis = F - S

        Args:
            S: 现货价格
            F: 期货/远期价格
            T: 到期时间（年）
            r: 无风险利率
            q: 股息率/净收益

        Returns:
            Dictionary containing:
                - basis: 基差（绝对值）
                - basis_percentage: 基差百分比
                - annualized_basis: 年化基差
                - fair_price: 理论公允价值
                - basis_deviation: 基差偏离度
                - interpretation: 市场状态解读
        """
        S = self._validate_positive(S, 'spot_price')
        F = self._validate_positive(F, 'futures_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        q = self._validate_numeric_input(q, 'net_yield')

        try:
            basis = F - S
            basis_pct = basis / S * 100.0
            annualized_basis = basis / S / T if T > 0 else 0.0

            # 理论公允价值
            fair_price = S * np.exp((r - q) * T)
            basis_deviation = (F - fair_price) / fair_price if fair_price > 0 else 0.0

            # 市场状态解读
            if abs(basis_deviation) < 0.01:
                interpretation = "市场定价公允 (Fairly Priced)"
            elif basis_deviation > 0:
                interpretation = "期货相对高估 (Futures Overvalued) - 可考虑做空期货/做多现货"
            else:
                interpretation = "期货相对低估 (Futures Undervalued) - 可考虑做多期货/做空现货"

            return self._create_result_dict(
                value=float(basis),
                method='basis_analysis',
                parameters={'S': S, 'F': F, 'T': T, 'r': r, 'q': q},
                metadata={
                    'basis': float(basis),
                    'basis_percentage': float(basis_pct),
                    'annualized_basis': float(annualized_basis),
                    'fair_price': float(fair_price),
                    'basis_deviation': float(basis_deviation),
                    'contango': F > S,
                    'backwardation': F < S,
                    'interpretation': interpretation
                }
            )

        except Exception as e:
            raise CalculationError(
                f"Basis analysis failed: {str(e)}",
                calculation_type='basis_analysis'
            )

    def get_supported_methods(self) -> list:
        """获取支持的方法列表。"""
        return ['cost_of_carry', 'implied_convenience_yield', 'fair_value_spread']
