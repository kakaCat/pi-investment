"""
测试 StrategyBase 风控辅助方法
"""
import pytest
from domain.quantlib.engine.strategy_base import StrategyBase


class ConcreteStrategy(StrategyBase):
    """用于测试的具体策略类"""
    def generate_signal(self, klines, params=None):
        return {'action': 'hold', 'confidence': 0.5, 'reason': 'test'}


class TestStrategyBaseHelpers:

    def test_build_stop_loss_atr_long(self):
        """测试构建 ATR 止损（做多）"""
        strategy = ConcreteStrategy()

        result = strategy._build_stop_loss_atr(
            entry_price=100.0,
            atr=2.5,
            multiplier=2.0,
            direction='long'
        )

        assert result['type'] == 'atr'
        assert result['price'] == 95.0  # 100 - 2.5 * 2
        assert result['params']['atr_value'] == 2.5
        assert result['params']['atr_multiplier'] == 2.0
        assert result['params']['entry_price'] == 100.0

    def test_build_stop_loss_atr_short(self):
        """测试构建 ATR 止损（做空）"""
        strategy = ConcreteStrategy()

        result = strategy._build_stop_loss_atr(
            entry_price=100.0,
            atr=2.5,
            multiplier=2.0,
            direction='short'
        )

        assert result['type'] == 'atr'
        assert result['price'] == 105.0  # 100 + 2.5 * 2

    def test_build_stop_loss_percent_long(self):
        """测试构建固定百分比止损（做多）"""
        strategy = ConcreteStrategy()

        result = strategy._build_stop_loss_percent(
            entry_price=100.0,
            percent=0.08,
            direction='long'
        )

        assert result['type'] == 'fixed_percent'
        assert result['price'] == 92.0  # 100 * (1 - 0.08)
        assert result['params']['percent'] == 0.08
        assert result['params']['entry_price'] == 100.0

    def test_build_stop_loss_trailing(self):
        """测试构建追踪止损"""
        strategy = ConcreteStrategy()

        result = strategy._build_stop_loss_trailing(
            entry_price=100.0,
            trailing_percent=0.05,
            direction='long'
        )

        assert result['type'] == 'trailing'
        assert result['price'] == 95.0  # 100 * (1 - 0.05)
        assert result['params']['trailing_percent'] == 0.05

    def test_build_position_sizing_kelly(self):
        """测试构建 Kelly 仓位参数"""
        strategy = ConcreteStrategy()

        result = strategy._build_position_sizing_kelly(
            win_rate=0.60,
            profit_loss_ratio=2.5,
            kelly_fraction=0.25
        )

        assert result['method'] == 'kelly'
        assert result['value'] is None
        assert result['params']['win_rate'] == 0.60
        assert result['params']['profit_loss_ratio'] == 2.5
        assert result['params']['kelly_fraction'] == 0.25

    def test_build_position_sizing_percent(self):
        """测试构建固定比例仓位"""
        strategy = ConcreteStrategy()

        result = strategy._build_position_sizing_percent(0.15)

        assert result['method'] == 'fixed_percent'
        assert result['value'] == 0.15
        assert result['params'] == {}

    def test_build_position_sizing_shares(self):
        """测试构建固定股数仓位"""
        strategy = ConcreteStrategy()

        result = strategy._build_position_sizing_shares(2000)

        assert result['method'] == 'fixed_shares'
        assert result['value'] == 2000
        assert result['params'] == {}


class TestStrategyBaseHelpersValidation:
    """测试 StrategyBase 风控辅助方法的参数验证"""

    def test_build_stop_loss_atr_invalid_entry_price(self):
        """测试 ATR 止损：无效的入场价格"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="entry_price must be greater than 0"):
            strategy._build_stop_loss_atr(
                entry_price=0,
                atr=2.5,
                multiplier=2.0,
                direction='long'
            )

        with pytest.raises(ValueError, match="entry_price must be greater than 0"):
            strategy._build_stop_loss_atr(
                entry_price=-100.0,
                atr=2.5,
                multiplier=2.0,
                direction='long'
            )

    def test_build_stop_loss_atr_invalid_atr(self):
        """测试 ATR 止损：无效的 ATR 值"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="atr must be greater than 0"):
            strategy._build_stop_loss_atr(
                entry_price=100.0,
                atr=0,
                multiplier=2.0,
                direction='long'
            )

        with pytest.raises(ValueError, match="atr must be greater than 0"):
            strategy._build_stop_loss_atr(
                entry_price=100.0,
                atr=-2.5,
                multiplier=2.0,
                direction='long'
            )

    def test_build_stop_loss_atr_invalid_direction(self):
        """测试 ATR 止损：无效的方向"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="direction must be 'long' or 'short'"):
            strategy._build_stop_loss_atr(
                entry_price=100.0,
                atr=2.5,
                multiplier=2.0,
                direction='invalid'
            )

    def test_build_stop_loss_percent_invalid_percent(self):
        """测试固定百分比止损：无效的百分比"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="percent must be between 0 and 1"):
            strategy._build_stop_loss_percent(
                entry_price=100.0,
                percent=-0.08,
                direction='long'
            )

        with pytest.raises(ValueError, match="percent must be between 0 and 1"):
            strategy._build_stop_loss_percent(
                entry_price=100.0,
                percent=1.5,
                direction='long'
            )

    def test_build_stop_loss_percent_invalid_direction(self):
        """测试固定百分比止损：无效的方向"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="direction must be 'long' or 'short'"):
            strategy._build_stop_loss_percent(
                entry_price=100.0,
                percent=0.08,
                direction='up'
            )

    def test_build_stop_loss_trailing_no_params(self):
        """测试追踪止损：未提供任何追踪参数"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="Must provide either trailing_percent or \\(trailing_atr_multiplier \\+ atr\\)"):
            strategy._build_stop_loss_trailing(
                entry_price=100.0,
                direction='long'
            )

    def test_build_stop_loss_trailing_both_params(self):
        """测试追踪止损：同时提供两种追踪参数"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="Cannot provide both trailing_percent and trailing_atr_multiplier"):
            strategy._build_stop_loss_trailing(
                entry_price=100.0,
                trailing_percent=0.05,
                trailing_atr_multiplier=1.5,
                atr=3.0,
                direction='long'
            )

    def test_build_stop_loss_trailing_atr_without_atr_value(self):
        """测试追踪止损：提供 ATR 倍数但未提供 ATR 值"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="atr must be provided when using trailing_atr_multiplier"):
            strategy._build_stop_loss_trailing(
                entry_price=100.0,
                trailing_atr_multiplier=1.5,
                direction='long'
            )

    def test_build_stop_loss_trailing_invalid_percent(self):
        """测试追踪止损：无效的追踪百分比"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="trailing_percent must be between 0 and 1"):
            strategy._build_stop_loss_trailing(
                entry_price=100.0,
                trailing_percent=-0.05,
                direction='long'
            )

        with pytest.raises(ValueError, match="trailing_percent must be between 0 and 1"):
            strategy._build_stop_loss_trailing(
                entry_price=100.0,
                trailing_percent=1.2,
                direction='long'
            )

    def test_build_position_sizing_kelly_invalid_win_rate(self):
        """测试 Kelly 仓位：无效的胜率"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="win_rate must be between 0 and 1"):
            strategy._build_position_sizing_kelly(
                win_rate=-0.1,
                profit_loss_ratio=2.5,
                kelly_fraction=0.25
            )

        with pytest.raises(ValueError, match="win_rate must be between 0 and 1"):
            strategy._build_position_sizing_kelly(
                win_rate=1.5,
                profit_loss_ratio=2.5,
                kelly_fraction=0.25
            )

    def test_build_position_sizing_kelly_invalid_profit_loss_ratio(self):
        """测试 Kelly 仓位：无效的盈亏比"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="profit_loss_ratio must be greater than 0"):
            strategy._build_position_sizing_kelly(
                win_rate=0.60,
                profit_loss_ratio=0,
                kelly_fraction=0.25
            )

        with pytest.raises(ValueError, match="profit_loss_ratio must be greater than 0"):
            strategy._build_position_sizing_kelly(
                win_rate=0.60,
                profit_loss_ratio=-2.5,
                kelly_fraction=0.25
            )

    def test_build_position_sizing_kelly_invalid_kelly_fraction(self):
        """测试 Kelly 仓位：无效的 Kelly 分数"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="kelly_fraction must be between 0 and 1"):
            strategy._build_position_sizing_kelly(
                win_rate=0.60,
                profit_loss_ratio=2.5,
                kelly_fraction=-0.25
            )

        with pytest.raises(ValueError, match="kelly_fraction must be between 0 and 1"):
            strategy._build_position_sizing_kelly(
                win_rate=0.60,
                profit_loss_ratio=2.5,
                kelly_fraction=1.5
            )

    def test_build_position_sizing_percent_invalid_percent(self):
        """测试固定比例仓位：无效的比例"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="percent must be between 0 and 1"):
            strategy._build_position_sizing_percent(-0.15)

        with pytest.raises(ValueError, match="percent must be between 0 and 1"):
            strategy._build_position_sizing_percent(1.5)

    def test_build_position_sizing_shares_invalid_shares(self):
        """测试固定股数仓位：无效的股数"""
        strategy = ConcreteStrategy()

        with pytest.raises(ValueError, match="shares must be greater than 0"):
            strategy._build_position_sizing_shares(0)

        with pytest.raises(ValueError, match="shares must be greater than 0"):
            strategy._build_position_sizing_shares(-2000)
