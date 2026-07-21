"""
测试 SignalProcessor 服务
"""
import pytest
from application.services.signal_processor import SignalProcessor, SignalProcessingError
from application.services.data_service import DataService


class TestSignalProcessor:

    @pytest.fixture
    def processor(self):
        """创建 SignalProcessor 实例"""
        return SignalProcessor(DataService())

    @pytest.fixture
    def account_balance(self):
        """模拟账户余额"""
        return {
            'total_assets': 1000000,
            'cash': 500000
        }

    def test_process_legacy_signal(self, processor, account_balance):
        """测试处理旧格式信号（向后兼容）"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'MA cross'
        }

        result = processor.process_signal(
            signal,
            '000001.SH',
            52.30,
            account_balance
        )

        assert result['action'] == 'buy'
        assert result['price'] == 52.30
        assert result['quantity'] > 0
        assert result['quantity'] % 100 == 0  # 手数检查
        assert result['stop_loss_price'] == 48.12  # 默认 -8%, 四舍五入到2位小数
        assert result['take_profit_price'] is None
        assert 'warnings' in result

    def test_process_signal_with_atr_stop_loss(self, processor, account_balance):
        """测试 ATR 止损"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'Volatility breakout',
            'risk_management': {
                'stop_loss': {
                    'type': 'atr',
                    'price': 48.50,
                    'params': {'atr_value': 2.35, 'atr_multiplier': 2.0}
                }
            }
        }

        result = processor.process_signal(
            signal,
            '000001.SH',
            52.30,
            account_balance
        )

        assert result['stop_loss_price'] == 48.50
        assert result['risk_params']['stop_loss']['type'] == 'atr'

    def test_process_signal_with_fixed_percent_sizing(self, processor, account_balance):
        """测试固定比例仓位"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'Test',
            'risk_management': {
                'position_sizing': {
                    'method': 'fixed_percent',
                    'value': 0.15,  # 15%
                    'params': {}
                }
            }
        }

        result = processor.process_signal(
            signal,
            '000001.SH',
            52.30,
            account_balance
        )

        expected_qty = int((1000000 * 0.15) / 52.30 / 100) * 100
        assert result['quantity'] == expected_qty

    def test_invalid_signal_structure(self, processor, account_balance):
        """测试无效信号结构"""
        signal = {
            'action': 'buy'
            # 缺少 confidence 和 reason
        }

        with pytest.raises(ValueError, match="Missing required field"):
            processor.process_signal(signal, '000001.SH', 52.30, account_balance)

    def test_process_signal_with_kelly_sizing(self, processor, account_balance):
        """测试 Kelly 仓位计算"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'High probability setup',
            'risk_management': {
                'position_sizing': {
                    'method': 'kelly',
                    'params': {
                        'win_rate': 0.6,
                        'profit_loss_ratio': 2.0,
                        'kelly_fraction': 0.25
                    }
                }
            }
        }

        result = processor.process_signal(
            signal,
            '000001.SH',
            52.30,
            account_balance
        )

        assert result['quantity'] > 0
        assert result['quantity'] % 100 == 0  # 手数检查
        assert result['risk_params']['position_sizing']['method'] == 'kelly'
        # Kelly 仓位应该在合理范围内（1%-30%）
        position_value = result['quantity'] * 52.30
        position_percent = position_value / account_balance['total_assets']
        assert 0.01 <= position_percent <= 0.30
