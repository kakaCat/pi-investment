# tests/application/services/test_new_order_service.py
"""
新订单服务测试 - 验证包装器正确委托给旧服务
"""
import pytest
from unittest.mock import patch, MagicMock
from application.services.new_order_service import (
    create_order, fill_order, cancel_order, get_order, list_orders,
    expire_orders, create_order_from_signal,
)


class TestNewOrderService:

    @patch('application.services.new_order_service._order_service')
    def test_create_order(self, mock_os):
        mock_os.create_order.return_value = 42

        order_id = create_order(
            "600000", "buy", "limit", 100, price=10.0, account_name="test_account",
        )

        assert order_id == 42
        mock_os.create_order.assert_called_once_with(
            symbol="600000", action="buy", order_type="limit",
            quantity=100, price=10.0, reason=None, signal_id=None,
            from_signal=False, account_name="test_account",
        )

    @patch('application.services.new_order_service._order_service')
    def test_fill_order(self, mock_os):
        mock_os.fill_order.return_value = {
            'order': {'id': 1, 'status': 'filled'},
            'trade_id': 7, 'filled_quantity': 100, 'is_full_fill': True,
        }

        result = fill_order(order_id=1, fill_price=10.5)

        assert result['trade_id'] == 7
        mock_os.fill_order.assert_called_once_with(order_id=1, fill_price=10.5, fill_quantity=None)

    @patch('application.services.new_order_service._order_service')
    def test_cancel_order(self, mock_os):
        mock_os.cancel_order.return_value = True

        result = cancel_order(order_id=5)

        assert result is True
        mock_os.cancel_order.assert_called_once_with(order_id=5)

    @patch('application.services.new_order_service._order_service')
    def test_get_order(self, mock_os):
        mock_os.get_order.return_value = {'id': 3, 'symbol': '000001'}

        result = get_order(order_id=3)

        assert result == {'id': 3, 'symbol': '000001'}
        mock_os.get_order.assert_called_once_with(order_id=3)

    @patch('application.services.new_order_service._order_service')
    def test_list_orders(self, mock_os):
        mock_os.list_orders.return_value = [{'id': 1}, {'id': 2}]

        result = list_orders(symbol="600000", status="pending", limit=10)

        assert len(result) == 2
        mock_os.list_orders.assert_called_once_with(symbol="600000", status="pending", limit=10)

    @patch('application.services.new_order_service._order_service')
    def test_expire_orders(self, mock_os):
        mock_os.expire_orders.return_value = 3

        result = expire_orders()

        assert result == 3
        mock_os.expire_orders.assert_called_once_with()

    @patch('application.services.new_order_service._order_service')
    def test_create_order_from_signal(self, mock_os):
        mock_os.create_order_from_signal.return_value = {'order_id': 1, 'stop_loss_order_id': 2}

        result = create_order_from_signal(signal={'id': 10}, symbol='600000')

        assert result == {'order_id': 1, 'stop_loss_order_id': 2}
        mock_os.create_order_from_signal.assert_called_once_with(
            signal={'id': 10}, symbol='600000', order_type='limit',
        )
