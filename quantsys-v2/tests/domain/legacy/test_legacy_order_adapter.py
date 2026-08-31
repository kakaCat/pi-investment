# tests/domain/legacy/test_legacy_order_adapter.py
import pytest
from unittest.mock import Mock, MagicMock
from domain.trading.services.order_service import OrderService
from domain.trading.models.order import Order, OrderStatus
from domain.legacy.legacy_order_adapter import LegacyOrderAdapter

class TestLegacyOrderAdapter:
    """LegacyOrderAdapter 测试"""
    
    @pytest.fixture
    def mock_order_service(self):
        return Mock(spec=OrderService)
    
    @pytest.fixture
    def adapter(self, mock_order_service):
        return LegacyOrderAdapter(order_service=mock_order_service)
    
    def test_create_order(self, adapter, mock_order_service):
        """测试创建订单"""
        # Arrange
        mock_order = Mock()
        mock_order.id = 1
        mock_order_service.create_order.return_value = mock_order
        
        # Act
        order_id = adapter.create_order(
            symbol="600000",
            action="buy",
            order_type="limit",
            quantity=100,
            price=10.0,
            account_name="test_account",
        )
        
        # Assert
        assert order_id == 1
        mock_order_service.create_order.assert_called_once()
    
    def test_fill_order(self, adapter, mock_order_service):
        """测试成交订单"""
        # Arrange
        mock_trade = MagicMock()
        mock_trade.id = 1
        mock_trade.shares = 100
        mock_order_service.fill_order.return_value = mock_trade
        
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.status = OrderStatus.FILLED
        mock_order_service.get_order.return_value = mock_order
        
        # Act
        result = adapter.fill_order(
            order_id=1,
            fill_price=10.0,
        )
        
        # Assert
        assert result['trade_id'] == 1
        assert result['filled_quantity'] == 100
    
    def test_cancel_order(self, adapter, mock_order_service):
        """测试取消订单"""
        # Arrange
        mock_order_service.cancel_order.return_value = True
        
        # Act
        result = adapter.cancel_order(order_id=1)
        
        # Assert
        assert result is True
        mock_order_service.cancel_order.assert_called_once_with(1)
    
    def test_get_order(self, adapter, mock_order_service):
        """测试获取订单"""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.symbol = '600000'
        mock_order_service.get_order.return_value = mock_order
        
        # Act
        result = adapter.get_order(order_id=1)
        
        # Assert
        assert result is not None
        assert result['id'] == 1
    
    def test_list_orders(self, adapter, mock_order_service):
        """测试获取订单列表"""
        # Arrange
        mock_order1 = MagicMock()
        mock_order1.id = 1
        mock_order1.symbol = '600000'
        mock_order2 = MagicMock()
        mock_order2.id = 2
        mock_order2.symbol = '000001'
        mock_order_service.list_orders.return_value = [mock_order1, mock_order2]
        
        # Act
        result = adapter.list_orders(symbol="600000")
        
        # Assert
        assert len(result) == 2
        assert result[0]['id'] == 1
