"""
事件驱动策略

捕捉市场微观结构事件，快速响应
适用于高频交易

事件类型：
1. 大单冲击
2. 订单簿失衡
3. 价格跳跃
4. 成交量异常
"""
import structlog
logger = structlog.get_logger(__name__)

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import logging

logger = logging.getLogger(__name__)


class LargeOrderDetector:
    """
    大单检测器

    检测市场中的大额订单
    """

    def __init__(
        self,
        volume_threshold: float = 3.0,  # 成交量阈值（标准差倍数）
        lookback_period: int = 100
    ):
        """
        Args:
            volume_threshold: 成交量阈值
            lookback_period: 回溯期
        """
        self.volume_threshold = volume_threshold
        self.lookback_period = lookback_period
        self.volume_history = deque(maxlen=lookback_period)

    def update(self, volume: float):
        """
        更新成交量

        Args:
            volume: 成交量
        """
        self.volume_history.append(volume)

    def detect(self, current_volume: float) -> Optional[Dict]:
        """
        检测大单

        Args:
            current_volume: 当前成交量

        Returns:
            检测结果
        """
        if len(self.volume_history) < self.lookback_period:
            return None

        volumes = np.array(self.volume_history)
        mean_volume = np.mean(volumes)
        std_volume = np.std(volumes)

        if std_volume == 0:
            return None

        z_score = (current_volume - mean_volume) / std_volume

        if abs(z_score) > self.volume_threshold:
            return {
                'type': 'large_order',
                'volume': current_volume,
                'mean_volume': mean_volume,
                'z_score': z_score,
                'direction': 'buy' if z_score > 0 else 'sell',
                'timestamp': datetime.now()
            }

        return None


class OrderBookImbalanceDetector:
    """
    订单簿失衡检测器

    检测买卖盘力量失衡
    """

    def __init__(
        self,
        imbalance_threshold: float = 0.3,  # 失衡阈值
        depth: int = 5  # 盘口深度
    ):
        """
        Args:
            imbalance_threshold: 失衡阈值
            depth: 盘口深度
        """
        self.imbalance_threshold = imbalance_threshold
        self.depth = depth

    def calculate_imbalance(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]]
    ) -> float:
        """
        计算订单簿失衡度

        Args:
            bids: 买盘
            asks: 卖盘

        Returns:
            失衡度 [-1, 1]
        """
        bid_volume = sum(vol for _, vol in bids[:self.depth])
        ask_volume = sum(vol for _, vol in asks[:self.depth])

        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return 0.0

        return (bid_volume - ask_volume) / total_volume

    def detect(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]]
    ) -> Optional[Dict]:
        """
        检测失衡

        Args:
            bids: 买盘
            asks: 卖盘

        Returns:
            检测结果
        """
        imbalance = self.calculate_imbalance(bids, asks)

        if abs(imbalance) > self.imbalance_threshold:
            return {
                'type': 'order_book_imbalance',
                'imbalance': imbalance,
                'direction': 'bullish' if imbalance > 0 else 'bearish',
                'strength': abs(imbalance),
                'timestamp': datetime.now()
            }

        return None


class PriceJumpDetector:
    """
    价格跳跃检测器

    检测异常价格波动
    """

    def __init__(
        self,
        jump_threshold: float = 3.0,  # 跳跃阈值（标准差倍数）
        lookback_period: int = 100
    ):
        """
        Args:
            jump_threshold: 跳跃阈值
            lookback_period: 回溯期
        """
        self.jump_threshold = jump_threshold
        self.lookback_period = lookback_period
        self.price_history = deque(maxlen=lookback_period)
        self.return_history = deque(maxlen=lookback_period)

    def update(self, price: float):
        """
        更新价格

        Args:
            price: 价格
        """
        if self.price_history:
            ret = (price - self.price_history[-1]) / self.price_history[-1]
            self.return_history.append(ret)

        self.price_history.append(price)

    def detect(self, current_price: float) -> Optional[Dict]:
        """
        检测价格跳跃

        Args:
            current_price: 当前价格

        Returns:
            检测结果
        """
        if len(self.return_history) < self.lookback_period:
            return None

        if not self.price_history:
            return None

        # 计算当前收益率
        current_return = (current_price - self.price_history[-1]) / self.price_history[-1]

        # 计算历史收益率统计
        returns = np.array(self.return_history)
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return None

        z_score = (current_return - mean_return) / std_return

        if abs(z_score) > self.jump_threshold:
            return {
                'type': 'price_jump',
                'price': current_price,
                'return': current_return,
                'z_score': z_score,
                'direction': 'up' if z_score > 0 else 'down',
                'magnitude': abs(current_return),
                'timestamp': datetime.now()
            }

        return None


class EventDrivenStrategy:
    """
    事件驱动策略

    策略逻辑：
    1. 监控多种市场事件
    2. 事件触发时快速响应
    3. 短期持仓，快速止盈止损
    """

    def __init__(
        self,
        symbol: str,
        position_size: int = 100,
        hold_period: int = 10,  # 持仓周期（秒）
        profit_target: float = 0.001,  # 止盈目标（0.1%）
        stop_loss: float = 0.0005  # 止损（0.05%）
    ):
        """
        Args:
            symbol: 交易品种
            position_size: 持仓大小
            hold_period: 持仓周期
            profit_target: 止盈目标
            stop_loss: 止损
        """
        self.symbol = symbol
        self.position_size = position_size
        self.hold_period = hold_period
        self.profit_target = profit_target
        self.stop_loss = stop_loss

        # 事件检测器
        self.large_order_detector = LargeOrderDetector()
        self.imbalance_detector = OrderBookImbalanceDetector()
        self.jump_detector = PriceJumpDetector()

        # 持仓状态
        self.position = 0
        self.entry_price = 0.0
        self.entry_time = None
        self.pnl = 0.0

    def on_trade(self, price: float, volume: float):
        """
        交易事件回调

        Args:
            price: 成交价格
            volume: 成交量
        """
        # 更新检测器
        self.large_order_detector.update(volume)
        self.jump_detector.update(price)

        # 检测大单
        large_order = self.large_order_detector.detect(volume)
        if large_order:
            logger.info(f"Large order detected: {large_order}")
            return self._handle_large_order(large_order, price)

        # 检测价格跳跃
        price_jump = self.jump_detector.detect(price)
        if price_jump:
            logger.info(f"Price jump detected: {price_jump}")
            return self._handle_price_jump(price_jump, price)

        return None

    def on_order_book_update(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]]
    ):
        """
        订单簿更新回调

        Args:
            bids: 买盘
            asks: 卖盘
        """
        # 检测订单簿失衡
        imbalance = self.imbalance_detector.detect(bids, asks)
        if imbalance:
            logger.info(f"Order book imbalance detected: {imbalance}")
            return self._handle_imbalance(imbalance, bids, asks)

        return None

    def _handle_large_order(self, event: Dict, current_price: float) -> Optional[Dict]:
        """
        处理大单事件

        Args:
            event: 事件信息
            current_price: 当前价格

        Returns:
            交易信号
        """
        if self.position != 0:
            return None

        # 大单买入，跟随做多
        # 大单卖出，跟随做空
        direction = event['direction']

        signal = {
            'action': 'open',
            'symbol': self.symbol,
            'side': 'buy' if direction == 'buy' else 'sell',
            'quantity': self.position_size,
            'price': current_price,
            'reason': 'large_order',
            'event': event,
            'timestamp': datetime.now()
        }

        return signal

    def _handle_price_jump(self, event: Dict, current_price: float) -> Optional[Dict]:
        """
        处理价格跳跃事件

        Args:
            event: 事件信息
            current_price: 当前价格

        Returns:
            交易信号
        """
        if self.position != 0:
            return None

        # 价格向上跳跃，做多
        # 价格向下跳跃，做空
        direction = event['direction']

        signal = {
            'action': 'open',
            'symbol': self.symbol,
            'side': 'buy' if direction == 'up' else 'sell',
            'quantity': self.position_size,
            'price': current_price,
            'reason': 'price_jump',
            'event': event,
            'timestamp': datetime.now()
        }

        return signal

    def _handle_imbalance(
        self,
        event: Dict,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]]
    ) -> Optional[Dict]:
        """
        处理订单簿失衡事件

        Args:
            event: 事件信息
            bids: 买盘
            asks: 卖盘

        Returns:
            交易信号
        """
        if self.position != 0:
            return None

        # 买盘强，做多
        # 卖盘强，做空
        direction = event['direction']

        # 使用最优价格
        if direction == 'bullish':
            price = asks[0][0] if asks else None
            side = 'buy'
        else:
            price = bids[0][0] if bids else None
            side = 'sell'

        if price is None:
            return None

        signal = {
            'action': 'open',
            'symbol': self.symbol,
            'side': side,
            'quantity': self.position_size,
            'price': price,
            'reason': 'order_book_imbalance',
            'event': event,
            'timestamp': datetime.now()
        }

        return signal

    def check_exit(self, current_price: float) -> Optional[Dict]:
        """
        检查是否应该平仓

        Args:
            current_price: 当前价格

        Returns:
            平仓信号
        """
        if self.position == 0:
            return None

        # 计算持仓时间
        if self.entry_time:
            hold_time = (datetime.now() - self.entry_time).total_seconds()
            if hold_time > self.hold_period:
                return self._create_exit_signal(current_price, 'timeout')

        # 计算盈亏
        if self.position > 0:
            pnl_pct = (current_price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - current_price) / self.entry_price

        # 止盈
        if pnl_pct >= self.profit_target:
            return self._create_exit_signal(current_price, 'take_profit')

        # 止损
        if pnl_pct <= -self.stop_loss:
            return self._create_exit_signal(current_price, 'stop_loss')

        return None

    def _create_exit_signal(self, price: float, reason: str) -> Dict:
        """
        创建平仓信号

        Args:
            price: 价格
            reason: 原因

        Returns:
            平仓信号
        """
        return {
            'action': 'close',
            'symbol': self.symbol,
            'side': 'sell' if self.position > 0 else 'buy',
            'quantity': abs(self.position),
            'price': price,
            'reason': reason,
            'timestamp': datetime.now()
        }

    def on_fill(self, order: Dict):
        """
        订单成交回调

        Args:
            order: 订单信息
        """
        action = order['action']
        side = order['side']
        quantity = order['quantity']
        price = order['price']

        if action == 'open':
            # 开仓
            self.position = quantity if side == 'buy' else -quantity
            self.entry_price = price
            self.entry_time = datetime.now()

            logger.info(
                f"Position opened: {side} {quantity}@{price:.4f}"
            )
        else:
            # 平仓
            pnl = (price - self.entry_price) * self.position
            self.pnl += pnl

            logger.info(
                f"Position closed: {side} {quantity}@{price:.4f}, "
                f"pnl={pnl:.2f}, total_pnl={self.pnl:.2f}"
            )

            self.position = 0
            self.entry_price = 0.0
            self.entry_time = None


# 使用示例
def example_event_driven():
    """事件驱动策略示例"""
    logger.info('=== Event-Driven Strategy ===\n')

    strategy = EventDrivenStrategy(
        symbol='BTC/USDT',
        position_size=100,
        hold_period=10,
        profit_target=0.001,
        stop_loss=0.0005
    )

    # 模拟市场数据
    np.random.seed(42)
    base_price = 50000
    base_volume = 100

    for i in range(200):
        # 模拟价格和成交量
        price = base_price + np.random.randn() * 100
        volume = base_volume + np.random.randn() * 20

        # 偶尔出现大单
        if i % 50 == 0:
            volume *= 5

        # 偶尔出现价格跳跃
        if i % 75 == 0:
            price += np.random.choice([-1, 1]) * 500

        # 交易事件
        signal = strategy.on_trade(price, volume)
        if signal:
            logger.info(f"Step {i}: {signal['action'].upper()} signal")
            logger.info(f"  Reason: {signal['reason']}")
            logger.info(f"  Side: {signal['side']}")
            logger.info(f"  Price: {signal['price']:.2f}")
            strategy.on_fill(signal)
            logger.info("")

        # 检查平仓
        if strategy.position != 0:
            exit_signal = strategy.check_exit(price)
            if exit_signal:
                logger.info(f'Step {i}: EXIT signal')
                logger.info(f"  Reason: {exit_signal['reason']}")
                logger.info(f"  Price: {exit_signal['price']:.2f}")
                strategy.on_fill(exit_signal)
                logger.info("")

        # 模拟订单簿
        if i % 10 == 0:
            bids = [(price - j, 100 + np.random.randn() * 20) for j in range(1, 6)]
            asks = [(price + j, 100 + np.random.randn() * 20) for j in range(1, 6)]

            # 偶尔出现失衡
            if i % 30 == 0:
                bids = [(price - j, 200 + np.random.randn() * 50) for j in range(1, 6)]

            imbalance_signal = strategy.on_order_book_update(bids, asks)
            if imbalance_signal:
                logger.info(f'Step {i}: IMBALANCE signal')
                logger.info(f"  Reason: {imbalance_signal['reason']}")
                logger.info(f"  Side: {imbalance_signal['side']}")
                strategy.on_fill(imbalance_signal)
                logger.info("")

    logger.info(f'\nFinal PnL: {strategy.pnl:.2f}')


if __name__ == "__main__":
    example_event_driven()
