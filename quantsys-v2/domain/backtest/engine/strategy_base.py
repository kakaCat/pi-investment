"""
策略抽象基类

所有策略必须继承 StrategyBase 并实现 generate_signal 方法。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any


class StrategyBase(ABC):
    """
    策略抽象基类

    子类必须实现 generate_signal(klines, params) 方法，
    返回包含 action、confidence、reason 的字典。
    """

    def __init__(self, name: str = None):
        """
        初始化策略

        Args:
            name: 策略名称，未提供时使用类名
        """
        self.name = name or self.__class__.__name__

    @abstractmethod
    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据K线数据生成交易信号

        Args:
            klines: K线数据列表，每个元素包含 trade_date, open, high, low, close, volume
            params: 策略参数字典

        Returns:
            信号字典，格式:
            {
                'action': 'buy' | 'sell' | 'hold',
                'confidence': 0.0 ~ 1.0,
                'reason': str
            }
        """
        pass

    def _validate_klines(self, klines: List[Dict[str, Any]], min_length: int = 2) -> None:
        """
        验证K线数据有效性

        Args:
            klines: K线数据列表
            min_length: 最小长度要求

        Raises:
            ValueError: 数据不足时抛出
        """
        if not klines:
            raise ValueError("K线数据为空")
        if len(klines) < min_length:
            raise ValueError(
                f"K线数据不足: 需要至少 {min_length} 条，实际 {len(klines)} 条"
            )

        required_fields = ['close']
        for field in required_fields:
            if field not in klines[0]:
                raise ValueError(f"K线数据缺少必需字段: {field}")

    def _extract_closes(self, klines: List[Dict[str, Any]]) -> List[float]:
        """
        从K线数据中提取收盘价序列

        Args:
            klines: K线数据列表

        Returns:
            收盘价列表
        """
        return [float(k['close']) for k in klines]

    def _calculate_ma(self, prices: List[float], period: int) -> List[float]:
        """
        计算移动均线

        Args:
            prices: 价格序列
            period: 周期

        Returns:
            移动均线序列，前 period-1 个值为 None
        """
        if len(prices) < period:
            raise ValueError(
                f"价格数据不足: 需要至少 {period} 条，实际 {len(prices)} 条"
            )

        mas = [None] * (period - 1)
        window = sum(prices[:period])
        mas.append(window / period)

        for i in range(period, len(prices)):
            window = window - prices[i - period] + prices[i]
            mas.append(window / period)

        return mas

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """
        计算 RSI 指标值（Wilder's smoothing）

        Args:
            prices: 价格序列
            period: RSI 周期

        Returns:
            最新 RSI 值
        """
        if len(prices) < period + 1:
            raise ValueError(
                f"价格数据不足: 需要至少 {period + 1} 条，实际 {len(prices)} 条"
            )

        # 计算价格变化（deltas）
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # 初始平均: 简单平均前 period 个 delta
        init_gains = [d if d > 0 else 0 for d in deltas[:period]]
        init_losses = [abs(d) if d < 0 else 0 for d in deltas[:period]]
        avg_gain = sum(init_gains) / period
        avg_loss = sum(init_losses) / period

        # Wilder's 平滑处理后续 deltas
        for i in range(period, len(deltas)):
            delta = deltas[i]
            gain = delta if delta > 0 else 0
            loss = abs(delta) if delta < 0 else 0
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            if avg_gain == 0:
                return 50.0  # 无价格变动
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def _calculate_bollinger_bands(
        self,
        prices: List[float],
        period: int = 20,
        num_std: float = 2.0
    ) -> Dict[str, List[float]]:
        """
        计算布林带

        Args:
            prices: 价格序列
            period: 周期
            num_std: 标准差倍数

        Returns:
            包含 middle, upper, lower 的字典
        """
        if len(prices) < period:
            raise ValueError(
                f"价格数据不足: 需要至少 {period} 条，实际 {len(prices)} 条"
            )

        import math

        middle = self._calculate_ma(prices, period)
        upper = [None] * (period - 1)
        lower = [None] * (period - 1)

        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1:i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            std = math.sqrt(variance)

            upper.append(mean + num_std * std)
            lower.append(mean - num_std * std)

        return {
            'middle': middle,
            'upper': upper,
            'lower': lower,
        }

    # ==================== 风控辅助方法 ====================

    def _build_stop_loss_atr(
        self,
        entry_price: float,
        atr: float,
        multiplier: float = 2.0,
        direction: str = 'long'
    ) -> dict:
        """
        构建 ATR 止损

        Args:
            entry_price: 入场价格
            atr: ATR 值
            multiplier: ATR 倍数
            direction: 'long' 做多 | 'short' 做空

        Returns:
            止损配置字典
        """
        # Validate parameters
        if entry_price <= 0:
            raise ValueError("entry_price must be greater than 0")
        if atr <= 0:
            raise ValueError("atr must be greater than 0")
        if direction not in ['long', 'short']:
            raise ValueError("direction must be 'long' or 'short'")

        if direction == 'long':
            stop_price = entry_price - atr * multiplier
        else:
            stop_price = entry_price + atr * multiplier

        return {
            'type': 'atr',
            'price': round(stop_price, 2),
            'params': {
                'atr_value': atr,
                'atr_multiplier': multiplier,
                'entry_price': entry_price
            }
        }

    def _build_stop_loss_percent(
        self,
        entry_price: float,
        percent: float = 0.08,
        direction: str = 'long'
    ) -> dict:
        """
        构建固定百分比止损

        Args:
            entry_price: 入场价格
            percent: 止损百分比（如 0.08 表示 -8%）
            direction: 'long' 做多 | 'short' 做空

        Returns:
            止损配置字典
        """
        # Validate parameters
        if entry_price <= 0:
            raise ValueError("entry_price must be greater than 0")
        if not (0 <= percent <= 1):
            raise ValueError("percent must be between 0 and 1")
        if direction not in ['long', 'short']:
            raise ValueError("direction must be 'long' or 'short'")

        if direction == 'long':
            stop_price = entry_price * (1 - percent)
        else:
            stop_price = entry_price * (1 + percent)

        return {
            'type': 'fixed_percent',
            'price': round(stop_price, 2),
            'params': {
                'percent': percent,
                'entry_price': entry_price
            }
        }

    def _build_stop_loss_trailing(
        self,
        entry_price: float,
        trailing_percent: float = None,
        trailing_atr_multiplier: float = None,
        atr: float = None,
        direction: str = 'long'
    ) -> dict:
        """
        构建追踪止损

        Args:
            entry_price: 入场价格
            trailing_percent: 追踪百分比（如 0.05 表示追踪 5%）
            trailing_atr_multiplier: 追踪 ATR 倍数
            atr: ATR 值（使用 ATR 追踪时需要）
            direction: 'long' 做多 | 'short' 做空

        Returns:
            止损配置字典
        """
        # Validate parameters
        if entry_price <= 0:
            raise ValueError("entry_price must be greater than 0")
        if direction not in ['long', 'short']:
            raise ValueError("direction must be 'long' or 'short'")

        # Validate that exactly one trailing method is specified
        if trailing_percent is not None and trailing_atr_multiplier is not None:
            raise ValueError("Cannot provide both trailing_percent and trailing_atr_multiplier")
        if trailing_percent is None and trailing_atr_multiplier is None:
            raise ValueError("Must provide either trailing_percent or (trailing_atr_multiplier + atr)")

        params = {}

        if trailing_percent is not None:
            if not (0 <= trailing_percent <= 1):
                raise ValueError("trailing_percent must be between 0 and 1")
            params['trailing_percent'] = trailing_percent
            if direction == 'long':
                stop_price = entry_price * (1 - trailing_percent)
            else:
                stop_price = entry_price * (1 + trailing_percent)
        else:  # trailing_atr_multiplier is not None
            if atr is None:
                raise ValueError("atr must be provided when using trailing_atr_multiplier")
            if atr <= 0:
                raise ValueError("atr must be greater than 0")
            params['trailing_atr_multiplier'] = trailing_atr_multiplier
            if direction == 'long':
                stop_price = entry_price - atr * trailing_atr_multiplier
            else:
                stop_price = entry_price + atr * trailing_atr_multiplier

        return {
            'type': 'trailing',
            'price': round(stop_price, 2),
            'params': params
        }

    def _build_position_sizing_kelly(
        self,
        win_rate: float,
        profit_loss_ratio: float,
        kelly_fraction: float = 0.25
    ) -> dict:
        """
        构建 Kelly 仓位参数

        Args:
            win_rate: 胜率（0-1）
            profit_loss_ratio: 盈亏比（平均盈利/平均亏损）
            kelly_fraction: Kelly 分数（通常使用 1/4 Kelly）

        Returns:
            仓位配置字典
        """
        # Validate parameters
        if not (0 <= win_rate <= 1):
            raise ValueError("win_rate must be between 0 and 1")
        if profit_loss_ratio <= 0:
            raise ValueError("profit_loss_ratio must be greater than 0")
        if not (0 <= kelly_fraction <= 1):
            raise ValueError("kelly_fraction must be between 0 and 1")

        return {
            'method': 'kelly',
            'value': None,  # 由执行层计算
            'params': {
                'win_rate': win_rate,
                'profit_loss_ratio': profit_loss_ratio,
                'kelly_fraction': kelly_fraction
            }
        }

    def _build_position_sizing_percent(self, percent: float) -> dict:
        """
        构建固定比例仓位

        Args:
            percent: 仓位比例（如 0.15 表示 15%）

        Returns:
            仓位配置字典
        """
        # Validate parameters
        if not (0 <= percent <= 1):
            raise ValueError("percent must be between 0 and 1")

        return {
            'method': 'fixed_percent',
            'value': percent,
            'params': {}
        }

    def _build_position_sizing_shares(self, shares: int) -> dict:
        """
        构建固定股数仓位

        Args:
            shares: 股数

        Returns:
            仓位配置字典
        """
        # Validate parameters
        if shares <= 0:
            raise ValueError("shares must be greater than 0")

        return {
            'method': 'fixed_shares',
            'value': shares,
            'params': {}
        }
