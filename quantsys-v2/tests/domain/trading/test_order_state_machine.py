"""测试订单状态机校验"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from domain.trading.services.order_service import OrderService
from domain.trading.models.order import Order, OrderSide, OrderType, OrderStatus
from domain.accounts.services.account_service import AccountService
from domain.portfolio.services.position_service import PositionService


class TestOrderStateMachine:
    """订单状态机转换测试"""

    def setup_method(self):
        """每个测试前初始化"""
        self.account_service = Mock(spec=AccountService)
        self.position_service = Mock(spec=PositionService)
        self.order_repo = Mock()

        self.service = OrderService(
            account_service=self.account_service,
            position_service=self.position_service,
            order_repo=self.order_repo,
        )

    def test_valid_transition_pending_to_partial(self):
        """测试合法转换: PENDING -> PARTIAL"""
        # 准备订单
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000.SH",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=200,
            price=10.0,
            status=OrderStatus.PENDING,
            filled_quantity=0,
            avg_filled_price=0.0,
        )

        self.order_repo.get_order.return_value = order
        self.position_service.get_position.return_value = None

        # 部分成交 100 股
        trade = self.service.fill_order(order_id=1, fill_price=10.0, fill_quantity=100)

        # 验证状态转换成功
        assert self.order_repo.update_order_status.called
        call_args = self.order_repo.update_order_status.call_args
        assert call_args[1]['status'] == OrderStatus.PARTIAL
        assert call_args[1]['filled_quantity'] == 100

    def test_valid_transition_partial_to_filled(self):
        """测试合法转换: PARTIAL -> FILLED"""
        # 准备部分成交的订单
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000.SH",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=200,
            price=10.0,
            status=OrderStatus.PARTIAL,
            filled_quantity=100,
            avg_filled_price=10.0,
        )

        self.order_repo.get_order.return_value = order
        self.position_service.get_position.return_value = None

        # 剩余 100 股成交
        trade = self.service.fill_order(order_id=1, fill_price=10.0, fill_quantity=100)

        # 验证状态转换成功
        call_args = self.order_repo.update_order_status.call_args
        assert call_args[1]['status'] == OrderStatus.FILLED
        assert call_args[1]['filled_quantity'] == 200

    def test_valid_transition_pending_to_cancelled(self):
        """测试合法转换: PENDING -> CANCELLED"""
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000.SH",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=200,
            price=10.0,
            status=OrderStatus.PENDING,
            filled_quantity=0,
            avg_filled_price=0.0,
        )

        self.order_repo.get_order.return_value = order
        self.order_repo.cancel_order.return_value = True

        # 取消订单
        result = self.service.cancel_order(order_id=1)

        # 验证成功
        assert result is True
        assert self.order_repo.cancel_order.called

    def test_valid_transition_partial_to_cancelled(self):
        """测试合法转换: PARTIAL -> CANCELLED"""
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000.SH",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=200,
            price=10.0,
            status=OrderStatus.PARTIAL,
            filled_quantity=100,
            avg_filled_price=10.0,
        )

        self.order_repo.get_order.return_value = order
        self.order_repo.cancel_order.return_value = True

        # 取消部分成交的订单
        result = self.service.cancel_order(order_id=1)

        # 验证成功
        assert result is True

    def test_invalid_transition_filled_to_cancelled(self):
        """测试非法转换: FILLED -> CANCELLED (应拒绝)"""
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000.SH",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=200,
            price=10.0,
            status=OrderStatus.FILLED,
            filled_quantity=200,
            avg_filled_price=10.0,
        )

        self.order_repo.get_order.return_value = order

        # 尝试取消已完成的订单
        with pytest.raises(ValueError) as exc_info:
            self.service.cancel_order(order_id=1)

        # 验证错误消息
        assert "非法状态转换" in str(exc_info.value)
        assert "filled" in str(exc_info.value).lower()
        assert "cancelled" in str(exc_info.value).lower()

    def test_invalid_transition_cancelled_to_filled(self):
        """测试非法转换: CANCELLED -> FILLED (应拒绝)"""
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000.SH",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=200,
            price=10.0,
            status=OrderStatus.CANCELLED,
            filled_quantity=0,
            avg_filled_price=0.0,
        )

        self.order_repo.get_order.return_value = order

        # 尝试成交已取消的订单
        with pytest.raises(ValueError) as exc_info:
            self.service.fill_order(order_id=1, fill_price=10.0, fill_quantity=100)

        # 验证错误消息（已在 fill_order 前置校验中拒绝）
        assert "订单状态不允许成交" in str(exc_info.value)

    def test_invalid_transition_expired_to_partial(self):
        """测试非法转换: EXPIRED -> PARTIAL (应拒绝)"""
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000.SH",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=200,
            price=10.0,
            status=OrderStatus.EXPIRED,
            filled_quantity=0,
            avg_filled_price=0.0,
        )

        self.order_repo.get_order.return_value = order

        # 尝试成交过期订单
        with pytest.raises(ValueError) as exc_info:
            self.service.fill_order(order_id=1, fill_price=10.0, fill_quantity=100)

        # 验证错误消息
        assert "订单状态不允许成交" in str(exc_info.value)

    def test_valid_transition_pending_to_expired(self):
        """测试合法转换: PENDING -> EXPIRED"""
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000.SH",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=200,
            price=10.0,
            status=OrderStatus.PENDING,
            filled_quantity=0,
            avg_filled_price=0.0,
            expires_at=datetime(2020, 1, 1),  # 已过期
        )

        self.order_repo.get_pending_orders.return_value = [order]

        # 执行过期处理
        expired_count = self.service.expire_orders()

        # 验证状态转换成功
        assert expired_count == 1
        assert self.order_repo.update_order_status.called
        call_args = self.order_repo.update_order_status.call_args
        assert call_args[1]['status'] == OrderStatus.EXPIRED

    def test_idempotent_transition_same_status(self):
        """测试幂等操作: 相同状态转换（应允许）"""
        # 直接测试 _validate_status_transition
        # 相同状态转换应该不抛异常
        try:
            self.service._validate_status_transition(
                order_id=1,
                from_status=OrderStatus.PENDING,
                to_status=OrderStatus.PENDING,
            )
            # 没有异常表示成功
            success = True
        except ValueError:
            success = False

        assert success is True

    def test_all_valid_transitions_defined(self):
        """测试所有定义的合法转换"""
        from domain.trading.services.order_service import VALID_TRANSITIONS

        # 验证 VALID_TRANSITIONS 包含所有预期转换
        expected_transitions = [
            (OrderStatus.PENDING, OrderStatus.PARTIAL),
            (OrderStatus.PENDING, OrderStatus.CANCELLED),
            (OrderStatus.PENDING, OrderStatus.EXPIRED),
            (OrderStatus.PENDING, OrderStatus.REJECTED),
            (OrderStatus.PARTIAL, OrderStatus.FILLED),
            (OrderStatus.PARTIAL, OrderStatus.CANCELLED),
            (OrderStatus.PARTIAL, OrderStatus.EXPIRED),
            (OrderStatus.PARTIAL, OrderStatus.REJECTED),
        ]

        for transition in expected_transitions:
            assert transition in VALID_TRANSITIONS, f"缺少转换规则: {transition}"

    def test_multiple_partial_fills(self):
        """测试多次部分成交的状态转换"""
        # 第一次部分成交
        order = Order(
            id=1,
            account_name="test_account",
            symbol="600000.SH",
            name="浦发银行",
            action=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=300,
            price=10.0,
            status=OrderStatus.PENDING,
            filled_quantity=0,
            avg_filled_price=0.0,
        )

        self.order_repo.get_order.return_value = order
        self.position_service.get_position.return_value = None

        # 第一次成交 100 股
        self.service.fill_order(order_id=1, fill_price=10.0, fill_quantity=100)
        call_args = self.order_repo.update_order_status.call_args
        assert call_args[1]['status'] == OrderStatus.PARTIAL

        # 更新订单状态模拟数据库变化
        order.status = OrderStatus.PARTIAL
        order.filled_quantity = 100
        order.avg_filled_price = 10.0

        # 第二次成交 100 股
        self.service.fill_order(order_id=1, fill_price=10.0, fill_quantity=100)
        call_args = self.order_repo.update_order_status.call_args
        assert call_args[1]['status'] == OrderStatus.PARTIAL
        assert call_args[1]['filled_quantity'] == 200

        # 更新订单状态
        order.filled_quantity = 200

        # 第三次成交 100 股 (全部完成)
        self.service.fill_order(order_id=1, fill_price=10.0, fill_quantity=100)
        call_args = self.order_repo.update_order_status.call_args
        assert call_args[1]['status'] == OrderStatus.FILLED
        assert call_args[1]['filled_quantity'] == 300
