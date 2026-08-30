"""
高频交易策略 - 做市策略

做市策略通过在买卖两侧同时挂单，赚取买卖价差
适用于流动性好的品种

核心要素：
1. 订单簿分析
2. 价差管理
3. 库存控制
4. 风险管理
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import deque
import logging

logger = logging.getLogger(__name__)


class OrderBook:
    """
    订单簿模拟器

    维护买卖盘口数据
    """

    def __init__(self, depth: int = 10):
        """
        Args:
            depth: 盘口深度
        """
        self.depth = depth
        self.bids = []  # [(price, volume), ...]
        self.asks = []  # [(price, volume), ...]
        self.last_update = None

    def update(self, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]):
        """
        更新订单簿

        Args:
            bids: 买盘 [(价格, 数量), ...]，按价格降序
            asks: 卖盘 [(价格, 数量), ...]，按价格升序
        """
        self.bids = sorted(bids, key=lambda x: x[0], reverse=True)[:self.depth]
        self.asks = sorted(asks, key=lambda x: x[0])[:self.depth]
        self.last_update = datetime.now()

    def get_best_bid(self) -> Optional[Tuple[float, float]]:
        """获取最优买价"""
        return self.bids[0] if self.bids else None

    def get_best_ask(self) -> Optional[Tuple[float, float]]:
        """获取最优卖价"""
        return self.asks[0] if self.asks else None

    def get_mid_price(self) -> Optional[float]:
        """获取中间价"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()

        if best_bid and best_ask:
            return (best_bid[0] + best_ask[0]) / 2
        return None

    def get_spread(self) -> Optional[float]:
        """获取买卖价差"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()

        if best_bid and best_ask:
            return best_ask[0] - best_bid[0]
        return None

    def get_imbalance(self) -> float:
        """
        计算订单簿不平衡度

        Returns:
            不平衡度 [-1, 1]，正值表示买盘强，负值表示卖盘强
        """
        if not self.bids or not self.asks:
            return 0.0

        bid_volume = sum(vol for _, vol in self.bids)
        ask_volume = sum(vol for _, vol in self.asks)

        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return 0.0

        return (bid_volume - ask_volume) / total_volume


class MarketMakingStrategy:
    """
    做市策略

    策略逻辑：
    1. 在买卖两侧同时挂单
    2. 根据市场状况动态调整报价
    3. 控制库存风险
    4. 赚取买卖价差
    """

    def __init__(
        self,
        symbol: str,
        min_spread: float = 0.0002,  # 最小价差（0.02%）
        target_spread: float = 0.0005,  # 目标价差（0.05%）
        max_inventory: int = 1000,  # 最大库存
        order_size: int = 100,  # 单次下单量
        inventory_penalty: float = 0.0001  # 库存惩罚系数
    ):
        """
        Args:
            symbol: 交易品种
            min_spread: 最小价差
            target_spread: 目标价差
            max_inventory: 最大库存
            order_size: 单次下单量
            inventory_penalty: 库存惩罚系数
        """
        self.symbol = symbol
        self.min_spread = min_spread
        self.target_spread = target_spread
        self.max_inventory = max_inventory
        self.order_size = order_size
        self.inventory_penalty = inventory_penalty

        self.inventory = 0  # 当前库存
        self.order_book = OrderBook()
        self.pnl = 0.0
        self.trades = []

    def calculate_quote_prices(
        self,
        mid_price: float,
        spread: float,
        imbalance: float
    ) -> Tuple[float, float]:
        """
        计算报价

        Args:
            mid_price: 中间价
            spread: 当前价差
            imbalance: 订单簿不平衡度

        Returns:
            (买价, 卖价)
        """
        # 基础价差
        half_spread = max(self.target_spread, spread) / 2

        # 库存调整
        # 库存过多时，降低买价、提高卖价，促进卖出
        # 库存过少时，提高买价、降低卖价，促进买入
        inventory_adjustment = self.inventory / self.max_inventory * self.inventory_penalty

        # 订单簿不平衡调整
        # 买盘强时，提高报价
        # 卖盘强时，降低报价
        imbalance_adjustment = imbalance * 0.0001

        # 计算最终报价
        bid_price = mid_price - half_spread - inventory_adjustment + imbalance_adjustment
        ask_price = mid_price + half_spread - inventory_adjustment + imbalance_adjustment

        # 确保最小价差
        if ask_price - bid_price < self.min_spread:
            half_min_spread = self.min_spread / 2
            bid_price = mid_price - half_min_spread
            ask_price = mid_price + half_min_spread

        return bid_price, ask_price

    def should_quote(self) -> bool:
        """
        判断是否应该报价

        Returns:
            是否报价
        """
        # 检查库存限制
        if abs(self.inventory) >= self.max_inventory:
            logger.warning(f"Inventory limit reached: {self.inventory}")
            return False

        # 检查价差
        spread = self.order_book.get_spread()
        if spread and spread < self.min_spread:
            logger.debug(f"Spread too small: {spread}")
            return False

        return True

    def generate_orders(self) -> List[Dict]:
        """
        生成做市订单

        Returns:
            订单列表
        """
        if not self.should_quote():
            return []

        mid_price = self.order_book.get_mid_price()
        spread = self.order_book.get_spread()
        imbalance = self.order_book.get_imbalance()

        if not mid_price or not spread:
            return []

        # 计算报价
        bid_price, ask_price = self.calculate_quote_prices(
            mid_price, spread, imbalance
        )

        orders = []

        # 买单（库存未满时）
        if self.inventory < self.max_inventory:
            orders.append({
                'symbol': self.symbol,
                'side': 'buy',
                'price': bid_price,
                'quantity': self.order_size,
                'type': 'limit',
                'timestamp': datetime.now()
            })

        # 卖单（库存未空时）
        if self.inventory > -self.max_inventory:
            orders.append({
                'symbol': self.symbol,
                'side': 'sell',
                'price': ask_price,
                'quantity': self.order_size,
                'type': 'limit',
                'timestamp': datetime.now()
            })

        return orders

    def on_fill(self, order: Dict, fill_price: float, fill_quantity: int):
        """
        订单成交回调

        Args:
            order: 订单信息
            fill_price: 成交价格
            fill_quantity: 成交数量
        """
        side = order['side']

        # 更新库存
        if side == 'buy':
            self.inventory += fill_quantity
            pnl_change = -fill_price * fill_quantity
        else:
            self.inventory -= fill_quantity
            pnl_change = fill_price * fill_quantity

        self.pnl += pnl_change

        # 记录交易
        self.trades.append({
            'timestamp': datetime.now(),
            'side': side,
            'price': fill_price,
            'quantity': fill_quantity,
            'inventory': self.inventory,
            'pnl': self.pnl
        })

        logger.info(
            f"Fill: {side} {fill_quantity}@{fill_price:.4f}, "
            f"inventory={self.inventory}, pnl={self.pnl:.2f}"
        )

    def get_statistics(self) -> Dict:
        """
        获取策略统计信息

        Returns:
            统计信息
        """
        if not self.trades:
            return {}

        df = pd.DataFrame(self.trades)

        return {
            'total_trades': len(self.trades),
            'total_pnl': self.pnl,
            'avg_pnl_per_trade': self.pnl / len(self.trades),
            'current_inventory': self.inventory,
            'max_inventory': df['inventory'].abs().max(),
            'buy_trades': len(df[df['side'] == 'buy']),
            'sell_trades': len(df[df['side'] == 'sell']),
            'avg_buy_price': df[df['side'] == 'buy']['price'].mean(),
            'avg_sell_price': df[df['side'] == 'sell']['price'].mean()
        }


class StatisticalArbitrageStrategy:
    """
    统计套利策略

    策略逻辑：
    1. 寻找相关性强的品种对
    2. 计算价差序列
    3. 价差偏离均值时建仓
    4. 价差回归时平仓
    """

    def __init__(
        self,
        symbol_a: str,
        symbol_b: str,
        lookback_period: int = 60,
        entry_threshold: float = 2.0,  # 入场阈值（标准差倍数）
        exit_threshold: float = 0.5,  # 出场阈值
        max_position: int = 1000
    ):
        """
        Args:
            symbol_a: 品种A
            symbol_b: 品种B
            lookback_period: 回溯期
            entry_threshold: 入场阈值
            exit_threshold: 出场阈值
            max_position: 最大持仓
        """
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self.lookback_period = lookback_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.max_position = max_position

        self.price_a_history = deque(maxlen=lookback_period)
        self.price_b_history = deque(maxlen=lookback_period)
        self.spread_history = deque(maxlen=lookback_period)

        self.position_a = 0
        self.position_b = 0
        self.pnl = 0.0

    def update_prices(self, price_a: float, price_b: float):
        """
        更新价格

        Args:
            price_a: 品种A价格
            price_b: 品种B价格
        """
        self.price_a_history.append(price_a)
        self.price_b_history.append(price_b)

        # 计算价差（对数价差）
        spread = np.log(price_a) - np.log(price_b)
        self.spread_history.append(spread)

    def calculate_hedge_ratio(self) -> float:
        """
        计算对冲比率

        使用OLS回归计算

        Returns:
            对冲比率
        """
        if len(self.price_a_history) < 2:
            return 1.0

        prices_a = np.array(self.price_a_history)
        prices_b = np.array(self.price_b_history)

        # 简单线性回归
        # price_a = beta * price_b + alpha
        beta = np.cov(prices_a, prices_b)[0, 1] / np.var(prices_b)

        return beta

    def calculate_z_score(self) -> Optional[float]:
        """
        计算价差的Z-score

        Returns:
            Z-score
        """
        if len(self.spread_history) < self.lookback_period:
            return None

        spreads = np.array(self.spread_history)
        mean = np.mean(spreads)
        std = np.std(spreads)

        if std == 0:
            return None

        current_spread = spreads[-1]
        z_score = (current_spread - mean) / std

        return z_score

    def generate_signal(self) -> Optional[Dict]:
        """
        生成交易信号

        Returns:
            交易信号
        """
        z_score = self.calculate_z_score()

        if z_score is None:
            return None

        hedge_ratio = self.calculate_hedge_ratio()

        # 当前持仓状态
        has_position = self.position_a != 0

        signal = None

        if not has_position:
            # 无持仓，寻找入场机会
            if z_score > self.entry_threshold:
                # 价差过高，做空价差
                # 卖出A，买入B
                signal = {
                    'action': 'open',
                    'direction': 'short_spread',
                    'symbol_a': self.symbol_a,
                    'symbol_b': self.symbol_b,
                    'quantity_a': -self.max_position,
                    'quantity_b': int(self.max_position * hedge_ratio),
                    'z_score': z_score,
                    'hedge_ratio': hedge_ratio,
                    'timestamp': datetime.now()
                }
            elif z_score < -self.entry_threshold:
                # 价差过低，做多价差
                # 买入A，卖出B
                signal = {
                    'action': 'open',
                    'direction': 'long_spread',
                    'symbol_a': self.symbol_a,
                    'symbol_b': self.symbol_b,
                    'quantity_a': self.max_position,
                    'quantity_b': -int(self.max_position * hedge_ratio),
                    'z_score': z_score,
                    'hedge_ratio': hedge_ratio,
                    'timestamp': datetime.now()
                }
        else:
            # 有持仓，判断是否平仓
            if self.position_a > 0:
                # 做多价差，价差回归时平仓
                if z_score > -self.exit_threshold:
                    signal = {
                        'action': 'close',
                        'direction': 'long_spread',
                        'symbol_a': self.symbol_a,
                        'symbol_b': self.symbol_b,
                        'quantity_a': -self.position_a,
                        'quantity_b': -self.position_b,
                        'z_score': z_score,
                        'timestamp': datetime.now()
                    }
            else:
                # 做空价差，价差回归时平仓
                if z_score < self.exit_threshold:
                    signal = {
                        'action': 'close',
                        'direction': 'short_spread',
                        'symbol_a': self.symbol_a,
                        'symbol_b': self.symbol_b,
                        'quantity_a': -self.position_a,
                        'quantity_b': -self.position_b,
                        'z_score': z_score,
                        'timestamp': datetime.now()
                    }

        return signal

    def on_fill(self, symbol: str, quantity: int, price: float):
        """
        订单成交回调

        Args:
            symbol: 品种
            quantity: 数量
            price: 价格
        """
        if symbol == self.symbol_a:
            self.position_a += quantity
            self.pnl -= quantity * price
        elif symbol == self.symbol_b:
            self.position_b += quantity
            self.pnl -= quantity * price

        logger.info(
            f"Fill: {symbol} {quantity}@{price:.4f}, "
            f"positions=({self.position_a}, {self.position_b}), pnl={self.pnl:.2f}"
        )


# 使用示例
def example_market_making():
    """做市策略示例"""
    print("=== Market Making Strategy ===\n")

    strategy = MarketMakingStrategy(
        symbol='BTC/USDT',
        min_spread=0.0002,
        target_spread=0.0005,
        max_inventory=1000,
        order_size=100
    )

    # 模拟订单簿更新
    bids = [(50000, 10), (49999, 20), (49998, 15)]
    asks = [(50001, 12), (50002, 18), (50003, 25)]

    strategy.order_book.update(bids, asks)

    # 生成订单
    orders = strategy.generate_orders()

    print("Generated Orders:")
    for order in orders:
        print(f"  {order['side'].upper()} {order['quantity']}@{order['price']:.2f}")

    # 模拟成交
    if orders:
        strategy.on_fill(orders[0], orders[0]['price'], orders[0]['quantity'])

    # 统计信息
    stats = strategy.get_statistics()
    if stats:
        print("\nStatistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")


def example_statistical_arbitrage():
    """统计套利示例"""
    print("\n=== Statistical Arbitrage Strategy ===\n")

    strategy = StatisticalArbitrageStrategy(
        symbol_a='ETH/USDT',
        symbol_b='BTC/USDT',
        lookback_period=60,
        entry_threshold=2.0,
        exit_threshold=0.5
    )

    # 模拟价格序列
    np.random.seed(42)
    for i in range(100):
        price_a = 3000 + np.random.randn() * 50
        price_b = 50000 + np.random.randn() * 500

        strategy.update_prices(price_a, price_b)

        if i >= 60:  # 等待足够的历史数据
            signal = strategy.generate_signal()

            if signal:
                print(f"Signal at step {i}:")
                print(f"  Action: {signal['action']}")
                print(f"  Direction: {signal['direction']}")
                print(f"  Z-score: {signal['z_score']:.2f}")
                print(f"  Hedge ratio: {signal.get('hedge_ratio', 0):.4f}")
                print()


if __name__ == "__main__":
    example_market_making()
    example_statistical_arbitrage()
