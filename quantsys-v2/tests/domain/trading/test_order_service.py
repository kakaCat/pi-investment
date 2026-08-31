# tests/domain/trading/test_order_service.py
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
from domain.accounts.services.account_service import AccountService
from domain.portfolio.services.position_service import PositionService
from domain.trading.models.order import Order, OrderSide, OrderType, OrderStatus
from domain.trading.ports.IOrderRepository import IOrderRepository
from domain.trading.services.order_service import OrderService

class TestOrderService:
    """OrderService 单元测试"""
    
    @pytest.fixture
    def mock_account_service(self):
        return Mock(spec=AccountService)
    
    @pytest.fixture
    def mock_position_service(self):
        return Mock(spec=PositionService)
    
    @pytest.fixture
    def mock_order_repo(self):
        return Mock(spec=IOrderRepository)
    
    @pytest.fixture
    def service(self, mock_account_service, mock_position_service, mock_order_repo):
        return OrderService(
            account_service=mock_account_service,
            position_service=mock_position_service,
            order_repo=mock_order_repo,
        )
    
    def test_create_order_buy_success(self, service, mock_account_service, mock_order_repo):
        """测试创建买入订单成功"""
        # Arrange
        mock_account_service.validate_buy_balance.return_value = True
        mock_order_repo.create_order.return_value = 1
        
        # Act
        order = service.create_order(
            account_name="test_account",
            symbol="600000",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=10.0,
        )
        
        # Assert
        assert order is not None
        assert order.id == 1
        assert order.status == OrderStatus.PENDING
        mock_order_repo.create_order.assert_called_once()
    
    def test_create_order_buy_insufficient_balance(
        self, service, mock_account_service
    ):
        """测试创建买入订单资金不足"""
        # Arrange
        mock_account_service.validate_buy_balance.return_value = False
        
        # Act & Assert
        with pytest.raises(ValueError, match="可用资金不足"):
            service.create_order(
                account_name="test_account",
                symbol="600000",
                name="浦发银行",
                action=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=10.0,
            )
    
    def test_create_order_sell_success(
        self, service, mock_position_service, mock_order_repo
    ):
        """测试创建卖出订单成功"""
        # Arrange
        mock_position_service.get_available_shares.return_value = 100
        mock_order_repo.create_order.return_value = 1
        
        # Act
        order = service.create_order(
            account_name="test_account",
            symbol="600000",
            name="浦发银行",
            action=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=12.0,
        )
        
        # Assert
        assert order is not None
        assert order.id == 1
    
    def test_create_order_sell_insufficient_shares(
        self, service, mock_position_service
    ):
        """测试创建卖出订单持仓不足"""
        # Arrange
        mock_position_service.get_available_shares.return_value = 50
        
        # Act & Assert
        with pytest.raises(ValueError, match="可卖数量不足"):
            service.create_order(
                account_name="test_account",
                symbol="600000",
                name="浦发银行",
                action=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=12.0,
            )
    
    def test_create_order_invalid_quantity(self, service):
        """测试创建订单数量无效"""
        # Act & Assert
        with pytest.raises(ValueError, match="必须是100股的整数倍"):
            service.create_order(
                account_name="test_account",
                symbol="600000",
                name="浦发银行",
                action=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=150,  # 不是100的整数倍
                price=10.0,
            )
    
    def test_create_order_invalid_price(self, service):
        """测试创建订单价格无效"""
        # Act & Assert
        with pytest.raises(ValueError, match="价格必须大于0"):
            service.create_order(
                account_name="test_account",
                symbol="600000",
                name="浦发银行",
                action=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=-5.0,
            )
    
    def test_cancel_order_success(self, service, mock_order_repo):
        """测试取消订单成功"""
        # Arrange
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000",
            action=OrderSide.BUY,
            status=OrderStatus.PENDING,
        )
        mock_order_repo.get_order.return_value = order
        mock_order_repo.cancel_order.return_value = True
        
        # Act
        result = service.cancel_order(1)
        
        # Assert
        assert result is True
        mock_order_repo.cancel_order.assert_called_once_with(1)
    
    def test_cancel_order_not_pending(self, service, mock_order_repo):
        """测试取消非pending订单"""
        # Arrange
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000",
            action=OrderSide.BUY,
            status=OrderStatus.FILLED,
        )
        mock_order_repo.get_order.return_value = order
        
        # Act & Assert
        with pytest.raises(ValueError, match="只能取消 pending 状态的订单"):
            service.cancel_order(1)
    
    def test_fill_order_success(self, service, mock_order_repo, mock_position_service):
        """测试成交订单成功"""
        # Arrange
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000",
            name="浦发银行",
            action=OrderSide.BUY,
            quantity=100,
            price=10.0,
            status=OrderStatus.PENDING,
            filled_quantity=0,
        )
        mock_order_repo.get_order.return_value = order
        mock_order_repo.update_order_status.return_value = True
        
        # Act
        trade = service.fill_order(order_id=1, fill_price=10.0)
        
        # Assert
        assert trade is not None
        assert trade.symbol == "600000"
        assert trade.shares == 100
        assert trade.filled_price == 10.0
    
    def test_fill_order_partial(self, service, mock_order_repo):
        """测试部分成交"""
        # Arrange
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000",
            name="浦发银行",
            action=OrderSide.BUY,
            quantity=200,
            price=10.0,
            status=OrderStatus.PENDING,
            filled_quantity=0,
        )
        mock_order_repo.get_order.return_value = order
        mock_order_repo.update_order_status.return_value = True
        
        # Act
        trade = service.fill_order(order_id=1, fill_price=10.0, fill_quantity=100)
        
        # Assert
        assert trade is not None
        assert trade.shares == 100
    
    def test_fill_order_not_found(self, service, mock_order_repo):
        """测试成交不存在的订单"""
        # Arrange
        mock_order_repo.get_order.return_value = None
        
        # Act & Assert
        with pytest.raises(ValueError, match="订单不存在"):
            service.fill_order(order_id=999, fill_price=10.0)
    
    def test_fill_order_invalid_status(self, service, mock_order_repo):
        """测试成交状态不允许的订单"""
        # Arrange
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000",
            action=OrderSide.BUY,
            status=OrderStatus.CANCELLED,
        )
        mock_order_repo.get_order.return_value = order
        
        # Act & Assert
        with pytest.raises(ValueError, match="订单状态不允许成交"):
            service.fill_order(order_id=1, fill_price=10.0)
