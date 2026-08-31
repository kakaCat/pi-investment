# tests/application/services/test_new_order_service.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from application.services.new_order_service import create_order, fill_order, cancel_order, get_order, list_orders

class TestNewOrderService:
    """新订单服务测试"""
    
    @patch('application.services.new_order_service.domain_service_factory')
    def test_create_order(self, mock_factory):
        """测试创建订单"""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = 1
        mock_factory.order_service.create_order.return_value = mock_order
        
        # Act
        order_id = create_order(
            symbol="600000",
            action="buy",
            order_type="limit",
            quantity=100,
            price=10.0,
            account_name="test_account",
        )
        
        # Assert
        assert order_id == 1
    
    @patch('application.services.new_order_service.domain_service_factory')
    def test_fill_order(self, mock_factory):
        """测试成交订单"""
        # Arrange
        from domain.trading.models.order import OrderStatus
        
        mock_trade = MagicMock()
        mock_trade.id = 1
        mock_trade.shares = 100
        mock_factory.order_service.fill_order.return_value = mock_trade
        
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.status = OrderStatus.FILLED
        mock_factory.order_service.get_order.return_value = mock_order
        
        # Act
        result = fill_order(
            order_id=1,
            fill_price=10.0,
        )
        
        # Assert
        assert result['trade_id'] == 1
        assert result['filled_quantity'] == 100
    
    @patch('application.services.new_order_service.domain_service_factory')
    def test_cancel_order(self, mock_factory):
        """测试取消订单"""
        # Arrange
        mock_factory.order_service.cancel_order.return_value = True
        
        # Act
        result = cancel_order(order_id=1)
        
        # Assert
        assert result is True
    
    @patch('application.services.new_order_service.domain_service_factory')
    def test_get_order(self, mock_factory):
        """测试获取订单"""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.symbol = '600000'
        mock_factory.order_service.get_order.return_value = mock_order
        
        # Act
        result = get_order(order_id=1)
        
        # Assert
        assert result is not None
        assert result['id'] == 1
    
    @patch('application.services.new_order_service.domain_service_factory')
    def test_list_orders(self, mock_factory):
        """测试获取订单列表"""
        # Arrange
        mock_order1 = MagicMock()
        mock_order1.id = 1
        mock_order1.symbol = '600000'
        mock_order2 = MagicMock()
        mock_order2.id = 2
        mock_order2.symbol = '000001'
        mock_factory.order_service.list_orders.return_value = [mock_order1, mock_order2]
        
        # Act
        result = list_orders(symbol="600000")
        
        # Assert
        assert len(result) == 2
        assert result[0]['id'] == 1
