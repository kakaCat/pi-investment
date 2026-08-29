"""
商品期货CTA策略

Commodity Trading Advisor (CTA) 策略
适用于商品期货、股指期货等衍生品

策略类型：
1. 趋势跟踪 - 捕捉中长期趋势
2. 均值回归 - 捕捉短期反转
3. 多品种组合 - 分散风险
"""
import structlog
logger = structlog.get_logger(__name__)

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import deque
import logging

logger = logging.getLogger(__name__)


class TrendFollowingCTA:
    """
    趋势跟踪CTA策略

    策略逻辑：
    1. 使用多重时间框架识别趋势
    2. 趋势确认后建仓
    3. 趋势反转时平仓
    4. 使用ATR动态止损
    """

    def __init__(
        self,
        symbol: str,
        fast_period: int = 20,
        slow_period: int = 60,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        position_size: int = 1,
        max_position: int = 3
    ):
        """
        Args:
            symbol: 品种代码
            fast_period: 快速均线周期
            slow_period: 慢速均线周期
            atr_period: ATR周期
            atr_multiplier: ATR止损倍数
            position_size: 单次开仓手数
            max_position: 最大持仓
        """
        self.symbol = symbol
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.position_size = position_size
        self.max_position = max_position

        self.price_history = deque(maxlen=slow_period)
        self.high_history = deque(maxlen=atr_period)
        self.low_history = deque(maxlen=atr_period)
        self.close_history = deque(maxlen=atr_period)

        self.position = 0
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.pnl = 0.0

    def update(self, high: float, low: float, close: float):
        """
        更新价格数据

        Args:
            high: 最高价
            low: 最低价
            close: 收盘价
        """
        self.price_history.append(close)
        self.high_history.append(high)
        self.low_history.append(low)
        self.close_history.append(close)

    def calculate_ma(self, period: int) -> Optional[float]:
        """
        计算移动平均

        Args:
            period: 周期

        Returns:
            移动平均值
        """
        if len(self.price_history) < period:
            return None

        prices = list(self.price_history)[-period:]
        return np.mean(prices)

    def calculate_atr(self) -> Optional[float]:
        """
        计算ATR

        Returns:
            ATR值
        """
        if len(self.high_history) < self.atr_period:
            return None

        highs = np.array(self.high_history)
        lows = np.array(self.low_history)
        closes = np.array(self.close_history)

        # True Range
        tr1 = highs - lows
        tr2 = np.abs(highs - np.roll(closes, 1))
        tr3 = np.abs(lows - np.roll(closes, 1))

        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        tr[0] = tr1[0]

        # ATR (简单移动平均)
        atr = np.mean(tr)

        return atr

    def identify_trend(self) -> Optional[str]:
        """
        识别趋势

        Returns:
            'uptrend', 'downtrend', 或 None
        """
        fast_ma = self.calculate_ma(self.fast_period)
        slow_ma = self.calculate_ma(self.slow_period)

        if fast_ma is None or slow_ma is None:
            return None

        if fast_ma > slow_ma:
            return 'uptrend'
        elif fast_ma < slow_ma:
            return 'downtrend'
        else:
            return None

    def generate_signal(self) -> Optional[Dict]:
        """
        生成交易信号

        Returns:
            交易信号
        """
        if len(self.price_history) < self.slow_period:
            return None

        trend = self.identify_trend()
        current_price = self.price_history[-1]
        atr = self.calculate_atr()

        if atr is None:
            return None

        signal = None

        if self.position == 0:
            # 无持仓，寻找入场机会
            if trend == 'uptrend':
                # 上升趋势，做多
                signal = {
                    'action': 'open',
                    'symbol': self.symbol,
                    'direction': 'long',
                    'quantity': self.position_size,
                    'price': current_price,
                    'stop_loss': current_price - atr * self.atr_multiplier,
                    'trend': trend,
                    'timestamp': datetime.now()
                }
            elif trend == 'downtrend':
                # 下降趋势，做空
                signal = {
                    'action': 'open',
                    'symbol': self.symbol,
                    'direction': 'short',
                    'quantity': self.position_size,
                    'price': current_price,
                    'stop_loss': current_price + atr * self.atr_multiplier,
                    'trend': trend,
                    'timestamp': datetime.now()
                }
        else:
            # 有持仓，检查止损和趋势反转
            if self.position > 0:
                # 多头持仓
                if current_price <= self.stop_loss:
                    # 触发止损
                    signal = {
                        'action': 'close',
                        'symbol': self.symbol,
                        'direction': 'long',
                        'quantity': abs(self.position),
                        'price': current_price,
                        'reason': 'stop_loss',
                        'timestamp': datetime.now()
                    }
                elif trend == 'downtrend':
                    # 趋势反转
                    signal = {
                        'action': 'close',
                        'symbol': self.symbol,
                        'direction': 'long',
                        'quantity': abs(self.position),
                        'price': current_price,
                        'reason': 'trend_reversal',
                        'timestamp': datetime.now()
                    }
                elif abs(self.position) < self.max_position and trend == 'uptrend':
                    # 加仓
                    signal = {
                        'action': 'add',
                        'symbol': self.symbol,
                        'direction': 'long',
                        'quantity': self.position_size,
                        'price': current_price,
                        'stop_loss': current_price - atr * self.atr_multiplier,
                        'timestamp': datetime.now()
                    }
            else:
                # 空头持仓
                if current_price >= self.stop_loss:
                    # 触发止损
                    signal = {
                        'action': 'close',
                        'symbol': self.symbol,
                        'direction': 'short',
                        'quantity': abs(self.position),
                        'price': current_price,
                        'reason': 'stop_loss',
                        'timestamp': datetime.now()
                    }
                elif trend == 'uptrend':
                    # 趋势反转
                    signal = {
                        'action': 'close',
                        'symbol': self.symbol,
                        'direction': 'short',
                        'quantity': abs(self.position),
                        'price': current_price,
                        'reason': 'trend_reversal',
                        'timestamp': datetime.now()
                    }
                elif abs(self.position) < self.max_position and trend == 'downtrend':
                    # 加仓
                    signal = {
                        'action': 'add',
                        'symbol': self.symbol,
                        'direction': 'short',
                        'quantity': self.position_size,
                        'price': current_price,
                        'stop_loss': current_price + atr * self.atr_multiplier,
                        'timestamp': datetime.now()
                    }

        return signal

    def on_fill(self, order: Dict):
        """
        订单成交回调

        Args:
            order: 订单信息
        """
        action = order['action']
        direction = order['direction']
        quantity = order['quantity']
        price = order['price']

        if action in ['open', 'add']:
            # 开仓或加仓
            if direction == 'long':
                self.position += quantity
            else:
                self.position -= quantity

            self.entry_price = price
            self.stop_loss = order.get('stop_loss', 0.0)

            logger.info(
                f"Position {action}: {direction} {quantity}@{price:.2f}, "
                f"total_position={self.position}, stop_loss={self.stop_loss:.2f}"
            )
        else:
            # 平仓
            if direction == 'long':
                pnl = (price - self.entry_price) * abs(self.position)
            else:
                pnl = (self.entry_price - price) * abs(self.position)

            self.pnl += pnl

            logger.info(
                f"Position closed: {direction} {quantity}@{price:.2f}, "
                f"pnl={pnl:.2f}, total_pnl={self.pnl:.2f}, "
                f"reason={order.get('reason', 'N/A')}"
            )

            self.position = 0
            self.entry_price = 0.0
            self.stop_loss = 0.0


class MeanReversionCTA:
    """
    均值回归CTA策略

    策略逻辑：
    1. 计算价格偏离均值的程度
    2. 偏离过大时建仓
    3. 回归均值时平仓
    """

    def __init__(
        self,
        symbol: str,
        lookback_period: int = 20,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        position_size: int = 1
    ):
        """
        Args:
            symbol: 品种代码
            lookback_period: 回溯期
            entry_threshold: 入场阈值（标准差倍数）
            exit_threshold: 出场阈值
            position_size: 持仓大小
        """
        self.symbol = symbol
        self.lookback_period = lookback_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.position_size = position_size

        self.price_history = deque(maxlen=lookback_period)
        self.position = 0
        self.entry_price = 0.0
        self.pnl = 0.0

    def update(self, price: float):
        """
        更新价格

        Args:
            price: 价格
        """
        self.price_history.append(price)

    def calculate_z_score(self) -> Optional[float]:
        """
        计算Z-score

        Returns:
            Z-score
        """
        if len(self.price_history) < self.lookback_period:
            return None

        prices = np.array(self.price_history)
        mean = np.mean(prices)
        std = np.std(prices)

        if std == 0:
            return None

        current_price = prices[-1]
        z_score = (current_price - mean) / std

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

        current_price = self.price_history[-1]
        signal = None

        if self.position == 0:
            # 无持仓
            if z_score > self.entry_threshold:
                # 价格过高，做空
                signal = {
                    'action': 'open',
                    'symbol': self.symbol,
                    'direction': 'short',
                    'quantity': self.position_size,
                    'price': current_price,
                    'z_score': z_score,
                    'timestamp': datetime.now()
                }
            elif z_score < -self.entry_threshold:
                # 价格过低，做多
                signal = {
                    'action': 'open',
                    'symbol': self.symbol,
                    'direction': 'long',
                    'quantity': self.position_size,
                    'price': current_price,
                    'z_score': z_score,
                    'timestamp': datetime.now()
                }
        else:
            # 有持仓
            if self.position > 0:
                # 多头，价格回归时平仓
                if z_score > -self.exit_threshold:
                    signal = {
                        'action': 'close',
                        'symbol': self.symbol,
                        'direction': 'long',
                        'quantity': abs(self.position),
                        'price': current_price,
                        'z_score': z_score,
                        'timestamp': datetime.now()
                    }
            else:
                # 空头，价格回归时平仓
                if z_score < self.exit_threshold:
                    signal = {
                        'action': 'close',
                        'symbol': self.symbol,
                        'direction': 'short',
                        'quantity': abs(self.position),
                        'price': current_price,
                        'z_score': z_score,
                        'timestamp': datetime.now()
                    }

        return signal

    def on_fill(self, order: Dict):
        """订单成交回调"""
        action = order['action']
        direction = order['direction']
        quantity = order['quantity']
        price = order['price']

        if action == 'open':
            self.position = quantity if direction == 'long' else -quantity
            self.entry_price = price
            logger.info(f"Position opened: {direction} {quantity}@{price:.2f}")
        else:
            pnl = (price - self.entry_price) * self.position
            self.pnl += pnl
            logger.info(f"Position closed: pnl={pnl:.2f}, total_pnl={self.pnl:.2f}")
            self.position = 0
            self.entry_price = 0.0


class MultiAssetCTA:
    """
    多品种CTA组合策略

    策略逻辑：
    1. 对多个品种分别运行CTA策略
    2. 根据相关性分配资金
    3. 动态调整品种权重
    """

    def __init__(
        self,
        symbols: List[str],
        total_capital: float,
        strategy_type: str = 'trend_following'
    ):
        """
        Args:
            symbols: 品种列表
            total_capital: 总资金
            strategy_type: 策略类型
        """
        self.symbols = symbols
        self.total_capital = total_capital
        self.strategy_type = strategy_type

        # 为每个品种创建策略实例
        self.strategies = {}
        for symbol in symbols:
            if strategy_type == 'trend_following':
                self.strategies[symbol] = TrendFollowingCTA(symbol)
            elif strategy_type == 'mean_reversion':
                self.strategies[symbol] = MeanReversionCTA(symbol)

        # 品种权重（均等权重）
        self.weights = {symbol: 1.0 / len(symbols) for symbol in symbols}

    def update_weights(self, correlation_matrix: pd.DataFrame):
        """
        根据相关性更新权重

        低相关性品种获得更高权重

        Args:
            correlation_matrix: 相关性矩阵
        """
        # 计算每个品种与其他品种的平均相关性
        avg_correlations = {}
        for symbol in self.symbols:
            if symbol in correlation_matrix.index:
                corr = correlation_matrix.loc[symbol].drop(symbol)
                avg_correlations[symbol] = abs(corr).mean()
            else:
                avg_correlations[symbol] = 0.5

        # 相关性越低，权重越高
        inverse_corr = {s: 1.0 / (c + 0.1) for s, c in avg_correlations.items()}
        total = sum(inverse_corr.values())

        self.weights = {s: v / total for s, v in inverse_corr.items()}

        logger.info(f"Updated weights: {self.weights}")

    def get_portfolio_statistics(self) -> Dict:
        """
        获取组合统计信息

        Returns:
            统计信息
        """
        total_pnl = sum(s.pnl for s in self.strategies.values())
        positions = {symbol: s.position for symbol, s in self.strategies.items()}

        return {
            'total_pnl': total_pnl,
            'positions': positions,
            'weights': self.weights,
            'num_strategies': len(self.strategies)
        }


# 使用示例
def example_trend_following():
    """趋势跟踪示例"""
    logger.info('=== Trend Following CTA ===\n')

    strategy = TrendFollowingCTA(
        symbol='CU2406',  # 铜期货
        fast_period=20,
        slow_period=60,
        atr_multiplier=2.0
    )

    # 模拟价格数据
    np.random.seed(42)
    base_price = 50000

    for i in range(100):
        # 模拟趋势
        trend = 100 if i < 50 else -100
        price = base_price + trend * i + np.random.randn() * 200

        high = price + np.random.rand() * 100
        low = price - np.random.rand() * 100

        strategy.update(high, low, price)

        if i >= 60:
            signal = strategy.generate_signal()
            if signal:
                logger.info(f"Step {i}: {signal['action'].upper()} signal")
                logger.info(f"  Direction: {signal['direction']}")
                logger.info(f"  Price: {signal['price']:.2f}")
                if 'trend' in signal:
                    logger.info(f"  Trend: {signal['trend']}")
                strategy.on_fill(signal)
                logger.info("")

    logger.info(f'Final PnL: {strategy.pnl:.2f}')


def example_mean_reversion():
    """均值回归示例"""
    logger.info('\n=== Mean Reversion CTA ===\n')

    strategy = MeanReversionCTA(
        symbol='RB2406',  # 螺纹钢期货
        lookback_period=20,
        entry_threshold=2.0
    )

    # 模拟均值回归价格
    np.random.seed(42)
    mean_price = 4000

    for i in range(100):
        # 价格围绕均值波动
        price = mean_price + np.sin(i / 10) * 200 + np.random.randn() * 50

        strategy.update(price)

        if i >= 20:
            signal = strategy.generate_signal()
            if signal:
                logger.info(f"Step {i}: {signal['action'].upper()} signal")
                logger.info(f"  Direction: {signal['direction']}")
                logger.info(f"  Price: {signal['price']:.2f}")
                logger.info(f"  Z-score: {signal['z_score']:.2f}")
                strategy.on_fill(signal)
                logger.info("")

    logger.info(f'Final PnL: {strategy.pnl:.2f}')


if __name__ == "__main__":
    example_trend_following()
    example_mean_reversion()
