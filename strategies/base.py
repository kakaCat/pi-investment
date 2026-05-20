"""
策略基类

所有策略必须继承此基类并实现calculate_signals方法
"""

from typing import List, Dict, Optional
import pandas as pd


class BaseStrategy:
    """策略基类"""

    def __init__(self, name: str, params: Optional[Dict] = None):
        """
        初始化策略

        Args:
            name: 策略名称
            params: 策略参数
        """
        self.name = name
        self.params = params or {}
        self.positions = {}

    def calculate_signals(self, date: str, data: pd.DataFrame) -> List[Dict]:
        """
        计算交易信号

        Args:
            date: 当前日期
            data: 历史数据 (包含所有股票的OHLCV数据)

        Returns:
            信号列表:
            [
                {
                    'symbol': '000001',
                    'action': 'buy',  # or 'sell'
                    'reason': '金叉买入'
                },
                ...
            ]
        """
        raise NotImplementedError("子类必须实现calculate_signals方法")

    def on_order_filled(self, order):
        """
        订单成交回调

        Args:
            order: 成交订单
        """
        pass

    def on_bar(self, bar):
        """
        每根K线触发

        Args:
            bar: K线数据
        """
        pass

    def __str__(self):
        return f"{self.name}({self.params})"
