"""
均线交叉策略 (MA Cross Strategy)

经典的双均线策略:
- 快线上穿慢线 → 金叉买入
- 快线下穿慢线 → 死叉卖出

参数:
- fast: 快线周期 (默认5)
- slow: 慢线周期 (默认20)
"""

from typing import List, Dict
import pandas as pd
import numpy as np
from ..base import BaseStrategy


class MACrossStrategy(BaseStrategy):
    """均线交叉策略"""

    def __init__(self, fast: int = 5, slow: int = 20):
        """
        初始化策略

        Args:
            fast: 快线周期
            slow: 慢线周期
        """
        super().__init__(
            name='MA交叉策略',
            params={'fast': fast, 'slow': slow}
        )
        self.fast = fast
        self.slow = slow

    def calculate_signals(self, date: str, data: pd.DataFrame) -> List[Dict]:
        """
        计算交易信号

        逻辑:
        1. 计算快慢均线
        2. 检测金叉/死叉
        3. 生成买入/卖出信号
        """
        signals = []

        # 获取所有股票列表
        symbols = data['symbol'].unique()

        for symbol in symbols:
            # 获取该股票的历史数据
            symbol_data = data[data['symbol'] == symbol].sort_values('date').reset_index(drop=True)

            # 需要足够的历史数据
            if len(symbol_data) < self.slow + 1:
                continue

            # 计算均线
            symbol_data['ma_fast'] = symbol_data['close'].rolling(window=self.fast).mean()
            symbol_data['ma_slow'] = symbol_data['close'].rolling(window=self.slow).mean()

            # 获取当前日期的位置
            current_mask = symbol_data['date'] == date
            if not current_mask.any():
                continue

            current_idx = symbol_data[current_mask].index[0]
            if current_idx == 0:
                continue

            prev_idx = current_idx - 1

            current = symbol_data.iloc[current_idx]
            prev = symbol_data.iloc[prev_idx]

            # 检查均线是否有效
            if pd.isna(current['ma_fast']) or pd.isna(current['ma_slow']):
                continue
            if pd.isna(prev['ma_fast']) or pd.isna(prev['ma_slow']):
                continue

            # 检测金叉 (买入信号)
            if (prev['ma_fast'] <= prev['ma_slow'] and
                current['ma_fast'] > current['ma_slow']):

                # 检查是否已持仓
                if symbol not in self.positions:
                    signals.append({
                        'symbol': symbol,
                        'action': 'buy',
                        'reason': f'金叉买入 (MA{self.fast}上穿MA{self.slow})'
                    })

            # 检测死叉 (卖出信号)
            elif (prev['ma_fast'] >= prev['ma_slow'] and
                  current['ma_fast'] < current['ma_slow']):

                # 检查是否持仓
                if symbol in self.positions:
                    signals.append({
                        'symbol': symbol,
                        'action': 'sell',
                        'reason': f'死叉卖出 (MA{self.fast}下穿MA{self.slow})'
                    })

        return signals

    def on_order_filled(self, order):
        """更新持仓状态"""
        if order.action == 'buy':
            self.positions[order.symbol] = {
                'entry_date': order.date,
                'entry_price': order.price,
                'shares': order.shares
            }
        elif order.action == 'sell':
            if order.symbol in self.positions:
                del self.positions[order.symbol]
