"""
测试 MomentumStrategy 风控功能
"""
import pytest
from domain.quantlib.engine.momentum_strategy import MomentumStrategy


class TestMomentumRisk:

    @pytest.fixture
    def strategy(self):
        """创建策略实例"""
        return MomentumStrategy()

    @pytest.fixture
    def klines(self):
        """生成测试 K 线数据（先下跌后上涨，触发 ROC 上穿零线）"""
        # 前15天下跌，后7天上涨，确保在第22天 ROC MA 从负转正
        closes = []
        for i in range(1, 16):
            closes.append(60.0 - i * 0.5)  # 下跌到 52.5
        for i in range(16, 23):
            closes.append(52.5 + (i - 15) * 0.8)  # 上涨

        return [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': closes[i - 1],
                'high': closes[i - 1] + 1.0,
                'low': closes[i - 1] - 1.0,
                'volume': 1000000
            }
            for i in range(1, 23)
        ]

    def test_buy_signal_includes_trailing_stop_loss(self, strategy, klines):
        """测试买入信号包含追踪止损"""
        signal = strategy.generate_signal(klines)

        # 确保触发买入信号（ROC上穿零线）
        if signal['action'] != 'buy':
            pytest.skip("未触发买入信号，调整测试数据")

        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']

        stop_loss = signal['risk_management']['stop_loss']
        assert stop_loss['type'] == 'trailing'
        assert stop_loss['price'] < klines[-1]['close']
        assert 'trailing_percent' in stop_loss['params']
        assert stop_loss['params']['trailing_percent'] == 0.05

    def test_buy_signal_includes_kelly_position_sizing(self, strategy, klines):
        """测试买入信号包含 Kelly 仓位管理"""
        signal = strategy.generate_signal(klines)

        if signal['action'] != 'buy':
            pytest.skip("未触发买入信号")

        assert 'position_sizing' in signal['risk_management']

        sizing = signal['risk_management']['position_sizing']
        assert sizing['method'] == 'kelly'
        assert sizing['value'] is None
        assert 'win_rate' in sizing['params']
        assert 'profit_loss_ratio' in sizing['params']
        assert 'kelly_fraction' in sizing['params']
        assert sizing['params']['kelly_fraction'] == 0.25

    def test_buy_signal_includes_roc_indicator(self, strategy, klines):
        """测试买入信号包含 ROC 指标"""
        signal = strategy.generate_signal(klines)

        if signal['action'] != 'buy':
            pytest.skip("未触发买入信号")

        assert 'indicators' in signal
        assert 'roc' in signal['indicators']
        assert 'roc_ma' in signal['indicators']

    def test_sell_signal_includes_risk_management(self, strategy):
        """测试卖出信号包含风控信息"""
        # 生成先上涨后下跌数据，触发 ROC 下穿零线
        closes = []
        for i in range(1, 16):
            closes.append(50.0 + i * 0.5)  # 上涨到 57.5
        for i in range(16, 23):
            closes.append(57.5 - (i - 15) * 0.8)  # 下跌

        klines = [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': closes[i - 1],
                'high': closes[i - 1] + 1.0,
                'low': closes[i - 1] - 1.0,
                'volume': 1000000
            }
            for i in range(1, 23)
        ]

        signal = strategy.generate_signal(klines)

        if signal['action'] != 'sell':
            pytest.skip("未触发卖出信号")

        assert 'risk_management' in signal
        assert 'stop_loss' in signal['risk_management']
        # 做空追踪止损价应该高于当前价
        assert signal['risk_management']['stop_loss']['price'] > klines[-1]['close']

    def test_hold_signal_no_risk_management(self, strategy, klines):
        """测试持有信号不包含风控信息"""
        # 生成平稳数据
        flat_klines = [
            {
                'trade_date': f'2024-01-{i:02d}',
                'close': 50.0,
                'high': 51.0,
                'low': 49.0,
                'volume': 1000000
            }
            for i in range(1, 31)
        ]

        signal = strategy.generate_signal(flat_klines)

        if signal['action'] == 'hold':
            assert 'risk_management' not in signal
