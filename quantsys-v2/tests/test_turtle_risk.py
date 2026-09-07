"""
测试 TurtleStrategy 风控功能
"""
import pytest
from domain.quantlib.engine.turtle_strategy import TurtleStrategy


class TestTurtleRisk:

    @pytest.fixture
    def strategy(self):
        """创建策略实例"""
        return TurtleStrategy()

    @pytest.fixture
    def klines(self):
        """生成测试 K 线数据（25天）"""
        return [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': 50.0 + i * 0.3,
                'high': 51.0 + i * 0.3,
                'low': 49.0 + i * 0.3,
                'volume': 1000000
            }
            for i in range(1, 26)
        ]

    def test_buy_signal_includes_atr_stop_loss(self, strategy, klines):
        """测试买入信号包含 ATR 止损"""
        # 触发买入信号（突破20日高点）
        klines[-1]['high'] = 70.0
        klines[-1]['close'] = 69.5

        signal = strategy.generate_signal(klines)

        assert signal['action'] == 'BUY'
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']

        stop_loss = signal['risk_management']['stop_loss']
        assert stop_loss['type'] == 'atr'
        assert stop_loss['price'] < klines[-1]['close']
        assert 'atr_value' in stop_loss['params']
        assert stop_loss['params']['atr_multiplier'] == 2.0

    def test_buy_signal_includes_fixed_percent_sizing(self, strategy, klines):
        """测试买入信号包含固定比例仓位"""
        klines[-1]['high'] = 70.0
        klines[-1]['close'] = 69.5

        signal = strategy.generate_signal(klines)

        assert 'position_sizing' in signal['risk_management']

        sizing = signal['risk_management']['position_sizing']
        assert sizing['method'] == 'fixed_percent'
        assert sizing['value'] == 0.15  # 15%
        assert sizing['params'] == {}

    def test_sell_signal_includes_risk_management(self, strategy, klines):
        """测试卖出信号包含风控信息"""
        # 触发卖出信号（跌破10日低点）
        klines[-1]['high'] = 46.0  # 不触发买入信号
        klines[-1]['low'] = 45.0
        klines[-1]['close'] = 45.5

        signal = strategy.generate_signal(klines)

        assert signal['action'] == 'SELL'
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']
        assert signal['risk_management']['stop_loss']['price'] > klines[-1]['close']

    def test_hold_signal_no_risk_management(self, strategy, klines):
        """测试持有信号不包含风控信息"""
        signal = strategy.generate_signal(klines)

        if signal['action'] == 'hold':
            assert 'risk_management' not in signal
