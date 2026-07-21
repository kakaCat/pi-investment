"""
测试 VolatilityBreakoutStrategy 风控功能
"""
import pytest
from domain.quantlib.engine.volatility_breakout_strategy import VolatilityBreakoutStrategy


class TestVolatilityBreakoutRisk:

    @pytest.fixture
    def strategy(self):
        """创建策略实例"""
        return VolatilityBreakoutStrategy()

    @pytest.fixture
    def klines(self):
        """生成测试 K 线数据（30天，价格上涨趋势）"""
        return [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': 50.0 + i * 0.5,
                'high': 51.0 + i * 0.5,
                'low': 49.0 + i * 0.5,
                'volume': 1000000
            }
            for i in range(1, 31)
        ]

    def test_buy_signal_includes_atr_stop_loss(self, strategy, klines):
        """测试买入信号包含 ATR 止损"""
        # 修改最后一天数据，触发买入信号（突破上阈值）
        klines[-1]['high'] = 70.0
        klines[-1]['close'] = 69.5

        signal = strategy.generate_signal(klines)

        assert signal['action'] == 'buy'
        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']

        stop_loss = signal['risk_management']['stop_loss']
        assert stop_loss['type'] == 'atr'
        assert stop_loss['price'] > 0
        assert stop_loss['price'] < klines[-1]['close']  # 止损价低于当前价
        assert 'atr_value' in stop_loss['params']
        assert 'atr_multiplier' in stop_loss['params']
        assert stop_loss['params']['atr_multiplier'] == 2.0

    def test_buy_signal_includes_kelly_position_sizing(self, strategy, klines):
        """测试买入信号包含 Kelly 仓位管理"""
        klines[-1]['high'] = 70.0
        klines[-1]['close'] = 69.5

        signal = strategy.generate_signal(klines)

        assert 'position_sizing' in signal['risk_management']

        sizing = signal['risk_management']['position_sizing']
        assert sizing['method'] == 'kelly'
        assert sizing['value'] is None  # Kelly 由执行层计算
        assert 'win_rate' in sizing['params']
        assert 'profit_loss_ratio' in sizing['params']
        assert 'kelly_fraction' in sizing['params']
        assert 0 <= sizing['params']['win_rate'] <= 1
        assert sizing['params']['profit_loss_ratio'] > 0
        assert sizing['params']['kelly_fraction'] == 0.25

    def test_buy_signal_includes_indicators(self, strategy, klines):
        """测试买入信号包含指标数据"""
        klines[-1]['high'] = 70.0
        klines[-1]['close'] = 69.5

        signal = strategy.generate_signal(klines)

        assert 'indicators' in signal
        assert 'atr' in signal['indicators']
        assert signal['indicators']['atr'] > 0

    def test_sell_signal_includes_risk_management(self, strategy, klines):
        """测试卖出信号包含风控信息"""
        # 修改最后一天数据，触发卖出信号（跌破下阈值）
        klines[-1]['low'] = 40.0
        klines[-1]['close'] = 40.5

        signal = strategy.generate_signal(klines)

        assert signal['action'] == 'sell'
        assert 'risk_management' in signal
        # 卖出信号也应该有止损（做空止损）
        assert 'stop_loss' in signal['risk_management']
        assert signal['risk_management']['stop_loss']['price'] > klines[-1]['close']

    def test_hold_signal_no_risk_management(self, strategy, klines):
        """测试持有信号不包含风控信息"""
        # 默认 klines 应该触发 hold 信号
        signal = strategy.generate_signal(klines)

        assert signal['action'] == 'hold'
        # hold 信号不需要风控信息
        assert 'risk_management' not in signal
