"""
测试信号到订单的完整流程
"""
import pytest
from application.services.order_service import create_order_from_signal
from application.services.data_service import DataService


class TestSignalToOrderFlow:

    @pytest.fixture
    def ds(self):
        """创建 DataService 实例"""
        ds = DataService()

        # 确保测试股票存在
        test_stock = ds.stock.get_by_symbol('000001.SH')
        if not test_stock:
            ds.stock.save({
                'symbol': '000001.SH',
                'name': '浦发银行',
                'market': 'SH',
                'industry': '白酒',
                'list_date': '2001-08-27'
            })

        # 确保有K线数据
        latest_kline = ds.kline.get_latest_daily_kline('000001.SH')
        if not latest_kline:
            # 插入测试K线数据
            from datetime import datetime
            ds.kline.save_daily_kline({
                'symbol': '000001.SH',
                'trade_date': datetime.now().strftime('%Y-%m-%d'),
                'open': 100.0,
                'high': 105.0,
                'low': 98.0,
                'close': 102.0,
                'volume': 1000000,
                'amount': 102000000
            })

        return ds

    def test_create_order_from_legacy_signal(self, ds):
        """测试从旧格式信号创建订单"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'Test signal'
        }

        result = create_order_from_signal(ds, signal, '000001.SH')

        assert 'order_id' in result
        assert result['order_id'] > 0
        assert 'trade_params' in result

        # 验证订单创建
        order = ds.portfolio.get_order_by_id(result['order_id'])
        assert order is not None
        assert order['action'] == 'buy'
        assert order['quantity'] > 0
        assert order['stop_loss_price'] is not None  # 应该有默认止损

        # 清理测试数据
        ds.portfolio.cancel_order(result['order_id'])

    def test_create_order_with_risk_management(self, ds):
        """测试从新格式信号创建订单组"""
        signal = {
            'action': 'buy',
            'confidence': 0.85,
            'reason': 'ATR breakout',
            'risk_management': {
                'stop_loss': {
                    'type': 'atr',
                    'price': 48.50,
                    'params': {'atr_value': 2.35, 'atr_multiplier': 2.0}
                },
                'take_profit': {
                    'type': 'atr',
                    'price': 55.20,
                    'params': {'atr_multiplier': 3.0}
                },
                'position_sizing': {
                    'method': 'fixed_percent',
                    'value': 0.15,
                    'params': {}
                }
            }
        }

        result = create_order_from_signal(ds, signal, '000001.SH')

        # 验证主订单
        assert 'order_id' in result
        main_order = ds.portfolio.get_order_by_id(result['order_id'])
        assert main_order['action'] == 'buy'
        assert float(main_order['stop_loss_price']) == 48.50
        assert float(main_order['take_profit_price']) == 55.20

        # 验证止损单
        if 'stop_loss_order_id' in result:
            stop_order = ds.portfolio.get_order_by_id(result['stop_loss_order_id'])
            assert stop_order['action'] == 'sell'
            assert stop_order['order_type'] == 'stop'
            assert float(stop_order['price']) == 48.50
            assert stop_order['parent_order_id'] == result['order_id']

            # 清理止损单
            ds.portfolio.cancel_order(result['stop_loss_order_id'])

        # 验证止盈单
        if 'take_profit_order_id' in result:
            tp_order = ds.portfolio.get_order_by_id(result['take_profit_order_id'])
            assert tp_order['action'] == 'sell'
            assert float(tp_order['price']) == 55.20
            assert tp_order['parent_order_id'] == result['order_id']

            # 清理止盈单
            ds.portfolio.cancel_order(result['take_profit_order_id'])

        # 清理主订单
        ds.portfolio.cancel_order(result['order_id'])
