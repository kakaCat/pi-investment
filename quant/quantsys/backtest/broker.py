"""
模拟券商 - 处理订单执行和交易成本

负责:
- 交易成本计算 (佣金+印花税)
- 订单验证
- 资金检查
"""

from typing import Optional


class SimulatedBroker:
    """模拟券商"""

    def __init__(
        self,
        commission_rate: float = 0.0003,  # 佣金 0.03%
        min_commission: float = 5.0,      # 最低佣金 5元
        stamp_tax_rate: float = 0.001,    # 印花税 0.1% (仅卖出)
    ):
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.stamp_tax_rate = stamp_tax_rate

    def calculate_buy_cost(self, price: float, shares: int) -> dict:
        """
        计算买入成本

        Returns:
            {
                'amount': 成交金额,
                'commission': 佣金,
                'total_cost': 总成本
            }
        """
        amount = price * shares
        commission = max(amount * self.commission_rate, self.min_commission)
        total_cost = amount + commission

        return {
            'amount': amount,
            'commission': commission,
            'stamp_tax': 0,
            'total_cost': total_cost
        }

    def calculate_sell_proceeds(self, price: float, shares: int) -> dict:
        """
        计算卖出收益

        Returns:
            {
                'amount': 成交金额,
                'commission': 佣金,
                'stamp_tax': 印花税,
                'total_proceeds': 实际到账
            }
        """
        amount = price * shares
        commission = max(amount * self.commission_rate, self.min_commission)
        stamp_tax = amount * self.stamp_tax_rate
        total_proceeds = amount - commission - stamp_tax

        return {
            'amount': amount,
            'commission': commission,
            'stamp_tax': stamp_tax,
            'total_proceeds': total_proceeds
        }

    def check_buying_power(self, cash: float, price: float, shares: int) -> bool:
        """检查购买力是否足够"""
        cost = self.calculate_buy_cost(price, shares)
        return cash >= cost['total_cost']

    def validate_order(self, order) -> tuple[bool, Optional[str]]:
        """
        验证订单

        Returns:
            (is_valid, error_message)
        """
        # 检查股数
        if order.shares < 100:
            return False, "股数必须 >= 100股"

        if order.shares % 100 != 0:
            return False, "股数必须是100的整数倍"

        # 检查价格
        if order.price <= 0:
            return False, "价格必须 > 0"

        return True, None
