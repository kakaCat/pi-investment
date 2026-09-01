"""
测试向后兼容性

确保现有策略在添加风控管理功能后仍能正常工作。
"""
import pytest
from domain.quantlib.engine.strategy_runner import StrategyRunner
from adapters.outbound.repositories import StrategyORMRepository


class TestBackwardCompatibility:

    @pytest.fixture
    def klines(self):
        """生成测试 K 线数据"""
        return [
            {'trade_date': f'2024-01-{i:02d}', 'close': 50.0 + i * 0.5,
             'high': 51.0 + i * 0.5, 'low': 49.0 + i * 0.5, 'volume': 1000000}
            for i in range(1, 31)
        ]

    def test_all_legacy_strategies_still_work(self, klines):
        """确保所有旧策略仍然可以运行"""
        runner = StrategyRunner(strategy_repo=StrategyORMRepository())

        # 运行所有策略
        signals = runner.run(klines, symbol='000001.SH')

        # 所有信号都应该有基础字段
        for signal in signals:
            assert 'action' in signal
            assert 'confidence' in signal
            assert 'reason' in signal
            assert signal['action'] in ('buy', 'sell', 'hold')
            assert 0 <= signal['confidence'] <= 1

            # risk_management 是可选的
            if 'risk_management' in signal:
                self._validate_risk_management(signal['risk_management'])

    def _validate_risk_management(self, risk_mgmt):
        """验证风控信息格式"""
        if 'stop_loss' in risk_mgmt:
            assert 'type' in risk_mgmt['stop_loss']
            assert 'price' in risk_mgmt['stop_loss']
            assert 'params' in risk_mgmt['stop_loss']

        if 'take_profit' in risk_mgmt:
            assert 'type' in risk_mgmt['take_profit']
            assert 'price' in risk_mgmt['take_profit']

        if 'position_sizing' in risk_mgmt:
            assert 'method' in risk_mgmt['position_sizing']
            assert 'params' in risk_mgmt['position_sizing']

    def test_signal_processor_handles_legacy_signals(self, klines):
        """测试 SignalProcessor 处理旧格式信号"""
        from application.services.signal_processor import SignalProcessor
        from application.services.data_service import DataService

        # 模拟旧策略返回的信号
        legacy_signal = {
            'action': 'BUY',
            'confidence': 0.75,
            'reason': 'Legacy strategy signal'
        }

        processor = SignalProcessor(DataService())
        result = processor.process_signal(
            legacy_signal,
            '000001.SH',
            52.30,
            {'total_assets': 1000000, 'cash': 500000}
        )

        # 应该成功处理并添加默认风控参数
        assert result['action'] == 'BUY'
        assert result['quantity'] > 0
        assert result['stop_loss_price'] is not None
        assert len(result['warnings']) == 0  # 使用默认值不应该产生警告
