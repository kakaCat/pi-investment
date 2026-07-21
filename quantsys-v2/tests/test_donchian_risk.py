"""
测试 DonchianChannelStrategy 风控功能
"""
import pytest
from domain.quantlib.engine.donchian_channel_strategy import DonchianChannelStrategy


class TestDonchianRisk:

    @pytest.fixture
    def strategy(self):
        """创建策略实例"""
        return DonchianChannelStrategy()

    @pytest.fixture
    def klines(self):
        """生成测试 K 线数据（25天）"""
        return [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': 50.0 + i * 0.4,
                'high': 51.0 + i * 0.4,
                'low': 49.0 + i * 0.4,
                'volume': 1000000
            }
            for i in range(1, 26)
        ]

    def test_buy_signal_includes_fixed_percent_stop_loss(self, strategy, klines):
        """测试买入信号包含固定百分比止损"""
        # 触发买入信号（突破上轨）
        prev_close = klines[-2]['close']
        klines[-1]['high'] = 75.0
        klines[-1]['close'] = 74.5

        signal = strategy.generate_signal(klines)

        assert signal['action'] == 'buy'
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']

        stop_loss = signal['risk_management']['stop_loss']
        assert stop_loss['type'] == 'fixed_percent'
        assert stop_loss['price'] < klines[-1]['close']
        assert 'percent' in stop_loss['params']
        assert stop_loss['params']['percent'] == 0.08
        # 验证止损价格计算正确（当前价 * 0.92）
        expected_stop = round(klines[-1]['close'] * 0.92, 2)
        assert stop_loss['price'] == expected_stop

    def test_buy_signal_includes_fixed_percent_sizing(self, strategy, klines):
        """测试买入信号包含固定比例仓位"""
        klines[-1]['high'] = 75.0
        klines[-1]['close'] = 74.5

        signal = strategy.generate_signal(klines)

        assert 'position_sizing' in signal['risk_management']

        sizing = signal['risk_management']['position_sizing']
        assert sizing['method'] == 'fixed_percent'
        assert sizing['value'] == 0.12  # 12%
        assert sizing['params'] == {}

    def test_sell_signal_includes_risk_management(self, strategy, klines):
        """测试卖出信号包含风控信息"""
        # 触发卖出信号（跌破下轨）
        klines[-1]['high'] = 46.0  # 确保不触发买入信号
        klines[-1]['low'] = 45.0
        klines[-1]['close'] = 45.5

        signal = strategy.generate_signal(klines)

        assert signal['action'] == 'sell'
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']
        # 做空止损价应该高于当前价
        assert signal['risk_management']['stop_loss']['price'] > klines[-1]['close']
        # 验证止损价格计算正确（当前价 * 1.08）
        expected_stop = round(klines[-1]['close'] * 1.08, 2)
        assert signal['risk_management']['stop_loss']['price'] == expected_stop

    def test_hold_signal_no_risk_management(self, strategy, klines):
        """测试持有信号不包含风控信息"""
        signal = strategy.generate_signal(klines)

        if signal['action'] == 'hold':
            assert 'risk_management' not in signal
