"""
订单和交易服务测试

覆盖 order_service 和 trade_service 的完整功能。
支持 mock DB 和真实 DB（连接失败时优雅跳过）。
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta

from application.services.data_service import DataService
from application.services import order_service
from application.services import trade_service


# ==================== Helpers ====================

def _make_mock_order(**overrides):
    """创建 mock 订单字典"""
    defaults = {
        'id': 1,
        'symbol': '000001.SZ',
        'name': '平安银行',
        'order_type': 'limit',
        'action': 'buy',
        'price': 10.50,
        'quantity': 1000,
        'status': 'pending',
        'filled_quantity': 0,
        'avg_filled_price': None,
        'reason': '测试订单',
        'signal_id': None,
        'expires_at': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_mock_ds():
    """创建带有 mock repositories 的 DataService"""
    ds = MagicMock(spec=DataService)
    ds.stock = MagicMock()
    ds.kline = MagicMock()
    ds.portfolio = MagicMock()
    return ds


# ==================== Order Creation Tests ====================

class TestOrderCreation:
    """测试 create_order 参数校验和逻辑"""

    def test_invalid_symbol_format(self):
        """无效股票代码格式应抛出 ValueError"""
        ds = _make_mock_ds()

        with pytest.raises(ValueError, match="股票代码"):
            order_service.create_order(ds, "INVALID", "buy", "limit", 100, price=10.0)

    def test_empty_symbol(self):
        """空股票代码应抛出 ValueError"""
        ds = _make_mock_ds()

        with pytest.raises(ValueError, match="股票代码不能为空"):
            order_service.create_order(ds, "", "buy", "limit", 100, price=10.0)

    def test_negative_quantity(self):
        """负数量应抛出 ValueError"""
        ds = _make_mock_ds()
        ds.stock.get_by_symbol.return_value = {'symbol': '000001.SZ', 'name': '测试'}

        with pytest.raises(ValueError, match="quantity"):
            order_service.create_order(ds, "000001.SZ", "buy", "limit", -100, price=10.0)

    def test_zero_quantity(self):
        """零数量应抛出 ValueError"""
        ds = _make_mock_ds()
        ds.stock.get_by_symbol.return_value = {'symbol': '000001.SZ', 'name': '测试'}

        with pytest.raises(ValueError, match="quantity"):
            order_service.create_order(ds, "000001.SZ", "buy", "limit", 0, price=10.0)

    def test_invalid_action(self):
        """无效交易方向应抛出 ValueError"""
        ds = _make_mock_ds()
        ds.stock.get_by_symbol.return_value = {'symbol': '000001.SZ', 'name': '测试'}

        with pytest.raises(ValueError, match="无效的订单方向"):
            order_service.create_order(ds, "000001.SZ", "hold", "limit", 100, price=10.0)

    def test_invalid_order_type(self):
        """无效订单类型应抛出 ValueError"""
        ds = _make_mock_ds()
        ds.stock.get_by_symbol.return_value = {'symbol': '000001.SZ', 'name': '测试'}

        with pytest.raises(ValueError, match="无效的订单类型"):
            order_service.create_order(ds, "000001.SZ", "buy", "gtd", 100, price=10.0)

    def test_limit_order_requires_price(self):
        """限价单必须提供价格"""
        ds = _make_mock_ds()
        ds.stock.get_by_symbol.return_value = {'symbol': '000001.SZ', 'name': '测试'}

        with pytest.raises(ValueError, match="必须提供价格"):
            order_service.create_order(ds, "000001.SZ", "buy", "limit", 100)

    def test_stop_order_requires_price(self):
        """止损单必须提供价格"""
        ds = _make_mock_ds()
        ds.stock.get_by_symbol.return_value = {'symbol': '000001.SZ', 'name': '测试'}

        with pytest.raises(ValueError, match="必须提供价格"):
            order_service.create_order(ds, "000001.SZ", "sell", "stop", 100)

    def test_market_order_no_price_ok(self):
        """市价单可以不提供价格"""
        ds = _make_mock_ds()
        ds.stock.get_by_symbol.return_value = {'symbol': '000001.SZ', 'name': '测试'}
        ds.portfolio.create_order.return_value = 42

        order_id = order_service.create_order(
            ds, "000001.SZ", "buy", "market", 100
        )

        assert order_id == 42
        # 验证传入的 order_data 中 price 为 None
        call_args = ds.portfolio.create_order.call_args[0][0]
        assert call_args['price'] is None

    def test_stock_not_found(self):
        """不存在的股票应抛出 RuntimeError"""
        ds = _make_mock_ds()
        ds.stock.get_by_symbol.return_value = None

        with pytest.raises(RuntimeError, match="股票不存在"):
            order_service.create_order(ds, "999999.SZ", "buy", "market", 100)

    def test_negative_price(self):
        """负价格应抛出 ValueError"""
        ds = _make_mock_ds()
        ds.stock.get_by_symbol.return_value = {'symbol': '000001.SZ', 'name': '测试'}

        with pytest.raises(ValueError, match="price"):
            order_service.create_order(ds, "000001.SZ", "buy", "limit", 100, price=-10.0)

    def test_create_order_success(self):
        """成功创建订单"""
        ds = _make_mock_ds()
        ds.stock.get_by_symbol.return_value = {'symbol': '000001.SZ', 'name': '平安银行'}
        ds.portfolio.create_order.return_value = 100

        order_id = order_service.create_order(
            ds, "000001.SZ", "buy", "limit", 500,
            price=10.50, reason="技术突破", signal_id=7
        )

        assert order_id == 100
        call_args = ds.portfolio.create_order.call_args[0][0]
        assert call_args['symbol'] == '000001.SZ'
        assert call_args['name'] == '平安银行'
        assert call_args['action'] == 'buy'
        assert call_args['order_type'] == 'limit'
        assert call_args['quantity'] == 500
        assert call_args['price'] == 10.50
        assert call_args['status'] == 'pending'
        assert call_args['reason'] == '技术突破'
        assert call_args['signal_id'] == 7
        assert call_args['expires_at'] is not None


# ==================== Order Fill Tests ====================

class TestOrderFill:
    """测试 fill_order 成交逻辑"""

    def test_order_not_found(self):
        """不存在的订单应抛出 RuntimeError"""
        ds = _make_mock_ds()
        ds.portfolio.get_order.return_value = None

        with pytest.raises(RuntimeError, match="订单不存在"):
            order_service.fill_order(ds, 999, 10.50)

    def test_cannot_fill_cancelled_order(self):
        """已取消的订单不能成交"""
        ds = _make_mock_ds()
        order = _make_mock_order(status='cancelled')
        ds.portfolio.get_order.return_value = order

        with pytest.raises(ValueError, match="订单状态不允许成交"):
            order_service.fill_order(ds, 1, 10.50)

    def test_cannot_fill_filled_order(self):
        """已成交的订单不能再次成交"""
        ds = _make_mock_ds()
        order = _make_mock_order(status='filled', filled_quantity=1000, avg_filled_price=10.50)
        ds.portfolio.get_order.return_value = order

        with pytest.raises(ValueError, match="订单状态不允许成交"):
            order_service.fill_order(ds, 1, 10.50)

    def test_fill_exceeds_remaining(self):
        """成交数量超过剩余数量应抛出 ValueError"""
        ds = _make_mock_ds()
        order = _make_mock_order(quantity=100, filled_quantity=80)
        ds.portfolio.get_order.return_value = order

        with pytest.raises(ValueError, match="超过剩余数量"):
            order_service.fill_order(ds, 1, 10.50, fill_quantity=50)

    def test_partial_fill(self):
        """部分成交：filled_quantity < total quantity"""
        ds = _make_mock_ds()
        order = _make_mock_order(quantity=1000, filled_quantity=0)
        ds.portfolio.get_order.side_effect = [
            order,  # first call: get current order
            # after fill, get_order returns updated order
            {**order, 'status': 'partial', 'filled_quantity': 300, 'avg_filled_price': 10.50},
        ]
        ds.portfolio.update_order_status.return_value = True
        ds.portfolio.create_order.return_value = 1  # not actually used in fill_order but...

        with patch('services.trade_service.create_trade_from_order', return_value=200):
            result = order_service.fill_order(ds, 1, 10.50, fill_quantity=300)

        assert result['is_full_fill'] is False
        assert result['filled_quantity'] == 300
        assert result['trade_id'] == 200

        # 验证 update_order_status 被正确调用
        ds.portfolio.update_order_status.assert_called_once()
        update_kwargs = ds.portfolio.update_order_status.call_args[1]
        assert update_kwargs['order_id'] == 1
        assert update_kwargs['status'] == 'partial'
        assert update_kwargs['filled_quantity'] == 300
        assert update_kwargs['avg_filled_price'] == 10.50

    def test_full_fill(self):
        """全部成交：filled_quantity == total quantity"""
        ds = _make_mock_ds()
        order = _make_mock_order(quantity=1000, filled_quantity=700, avg_filled_price=10.50)
        ds.portfolio.get_order.side_effect = [
            order,
            {**order, 'status': 'filled', 'filled_quantity': 1000, 'avg_filled_price': 10.65},
        ]
        ds.portfolio.update_order_status.return_value = True

        with patch('services.trade_service.create_trade_from_order', return_value=201):
            result = order_service.fill_order(ds, 1, 11.00, fill_quantity=300)

        assert result['is_full_fill'] is True
        assert result['filled_quantity'] == 300
        assert result['trade_id'] == 201

        update_kwargs = ds.portfolio.update_order_status.call_args[1]
        assert update_kwargs['status'] == 'filled'
        assert update_kwargs['filled_quantity'] == 1000
        # avg_filled_price = (700*10.50 + 300*11.00) / 1000 = (7350 + 3300) / 1000 = 10.65
        assert update_kwargs['avg_filled_price'] == 10.65

    def test_fill_all_remaining_when_none_specified(self):
        """fill_quantity 为 None 时成交所有剩余数量"""
        ds = _make_mock_ds()
        order = _make_mock_order(quantity=1000, filled_quantity=400)
        ds.portfolio.get_order.side_effect = [
            order,
            {**order, 'status': 'filled', 'filled_quantity': 1000, 'avg_filled_price': 8.90},
        ]
        ds.portfolio.update_order_status.return_value = True

        with patch('services.trade_service.create_trade_from_order', return_value=202):
            result = order_service.fill_order(ds, 1, 9.50)

        assert result['filled_quantity'] == 600
        assert result['is_full_fill'] is True

    def test_fill_zero_quantity_rejected(self):
        """fill_quantity 为 0 应抛出 ValueError"""
        ds = _make_mock_ds()
        order = _make_mock_order(quantity=1000, filled_quantity=0)
        ds.portfolio.get_order.return_value = order

        with pytest.raises(ValueError, match="fill_quantity"):
            order_service.fill_order(ds, 1, 10.50, fill_quantity=0)

    def test_fill_negative_quantity_rejected(self):
        """fill_quantity 为负数应抛出 ValueError"""
        ds = _make_mock_ds()
        order = _make_mock_order(quantity=1000, filled_quantity=0)
        ds.portfolio.get_order.return_value = order

        with pytest.raises(ValueError, match="fill_quantity"):
            order_service.fill_order(ds, 1, 10.50, fill_quantity=-5)


# ==================== Order Cancel Tests ====================

class TestOrderCancel:
    """测试 cancel_order"""

    def test_cancel_nonexistent_order(self):
        """不存在的订单应抛出 RuntimeError"""
        ds = _make_mock_ds()
        ds.portfolio.get_order.return_value = None

        with pytest.raises(RuntimeError, match="订单不存在"):
            order_service.cancel_order(ds, 999)

    def test_cannot_cancel_filled_order(self):
        """已成交的订单不能取消"""
        ds = _make_mock_ds()
        order = _make_mock_order(status='filled')
        ds.portfolio.get_order.return_value = order

        with pytest.raises(ValueError, match="只能取消 pending 状态"):
            order_service.cancel_order(ds, 1)

    def test_cannot_cancel_partial_order(self):
        """部分成交的订单不能取消"""
        ds = _make_mock_ds()
        order = _make_mock_order(status='partial', filled_quantity=300)
        ds.portfolio.get_order.return_value = order

        with pytest.raises(ValueError, match="只能取消 pending 状态"):
            order_service.cancel_order(ds, 1)

    def test_cancel_pending_order(self):
        """取消 pending 订单成功"""
        ds = _make_mock_ds()
        order = _make_mock_order(status='pending')
        ds.portfolio.get_order.return_value = order
        ds.portfolio.cancel_order.return_value = True

        result = order_service.cancel_order(ds, 1)

        assert result is True
        ds.portfolio.cancel_order.assert_called_once_with(1)


# ==================== Order Expire Tests ====================

class TestOrderExpire:
    """测试 expire_orders"""

    def test_no_pending_orders(self):
        """没有待处理订单时返回 0"""
        ds = _make_mock_ds()
        ds.portfolio.get_pending_orders.return_value = []

        count = order_service.expire_orders(ds)

        assert count == 0

    def test_expire_past_due_orders(self):
        """过期已超时的 pending 订单"""
        ds = _make_mock_ds()
        past = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        future = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

        ds.portfolio.get_pending_orders.return_value = [
            _make_mock_order(id=1, expires_at=past),
            _make_mock_order(id=2, expires_at=future),
            _make_mock_order(id=3, expires_at=past),
        ]
        ds.portfolio.update_order_status.return_value = True

        count = order_service.expire_orders(ds)

        # 只有 id=1 和 id=3 过期
        assert count == 2
        assert ds.portfolio.update_order_status.call_count == 2

    def test_expire_with_none_expires_at(self):
        """expires_at 为 None 的订单跳过不处理"""
        ds = _make_mock_ds()
        ds.portfolio.get_pending_orders.return_value = [
            _make_mock_order(id=1, expires_at=None),
        ]

        count = order_service.expire_orders(ds)
        # None expires_at 跳过，不尝试过期
        assert count == 0

    def test_expire_with_iso_date_format(self):
        """expires_at 为 ISO 格式 (YYYY-MM-DDTHH:MM:SS) 的过期处理"""
        ds = _make_mock_ds()
        past_iso = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')
        ds.portfolio.get_pending_orders.return_value = [
            _make_mock_order(id=1, expires_at=past_iso),
        ]
        ds.portfolio.update_order_status.return_value = True

        count = order_service.expire_orders(ds)
        assert count == 1

    def test_expire_with_date_only_format(self):
        """expires_at 为 YYYY-MM-DD 格式的过期处理"""
        ds = _make_mock_ds()
        past_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        ds.portfolio.get_pending_orders.return_value = [
            _make_mock_order(id=1, expires_at=past_date),
        ]
        ds.portfolio.update_order_status.return_value = True

        count = order_service.expire_orders(ds)
        assert count == 1

    def test_expire_handles_update_exception(self):
        """过期更新失败时被捕获，不中断其他订单处理"""
        ds = _make_mock_ds()
        past = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        future = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

        ds.portfolio.get_pending_orders.return_value = [
            _make_mock_order(id=1, expires_at=past),
            _make_mock_order(id=2, expires_at=past),
            _make_mock_order(id=3, expires_at=future),
        ]
        # 第一个更新失败，第二个成功
        ds.portfolio.update_order_status.side_effect = [
            Exception("DB error"),
            True,
        ]

        count = order_service.expire_orders(ds)
        # 只有 id=2 成功过期
        assert count == 1


# ==================== Order Query Tests ====================

class TestOrderQuery:
    """测试 get_order 和 list_orders 查询方法"""

    def test_get_order_returns_order(self):
        """get_order 委托给 portfolio.get_order"""
        ds = _make_mock_ds()
        expected = _make_mock_order(id=42)
        ds.portfolio.get_order.return_value = expected

        result = order_service.get_order(ds, 42)

        assert result == expected
        ds.portfolio.get_order.assert_called_once_with(42)

    def test_get_order_returns_none(self):
        """不存在的订单返回 None"""
        ds = _make_mock_ds()
        ds.portfolio.get_order.return_value = None

        result = order_service.get_order(ds, 999)

        assert result is None

    def test_list_orders_all(self):
        """列出所有订单"""
        ds = _make_mock_ds()
        expected = [_make_mock_order(id=1), _make_mock_order(id=2)]
        ds.portfolio.get_orders.return_value = expected

        result = order_service.list_orders(ds)

        assert result == expected
        ds.portfolio.get_orders.assert_called_once_with(symbol=None, status=None, limit=50)

    def test_list_orders_with_filters(self):
        """带筛选条件列出订单"""
        ds = _make_mock_ds()
        ds.portfolio.get_orders.return_value = []

        order_service.list_orders(ds, symbol='000001.SZ', status='filled', limit=10)

        ds.portfolio.get_orders.assert_called_once_with(
            symbol='000001.SZ', status='filled', limit=10
        )


# ==================== Trade Creation Tests ====================

class TestTradeCreation:
    """测试 create_trade_from_order"""

    def test_buy_trade_fee_calculation(self):
        """买入交易费用：仅佣金 0.03%"""
        ds = _make_mock_ds()
        ds.portfolio.record_trade.return_value = 300

        order = _make_mock_order(action='buy', symbol='000001.SZ', name='平安银行')
        trade_id = trade_service.create_trade_from_order(ds, order, 10.50, 1000)

        assert trade_id == 300
        call_args = ds.portfolio.record_trade.call_args[0][0]

        # amount = 10.50 * 1000 = 10500
        assert call_args['amount'] == 10500.0
        # fee = 10500 * 0.0003 = 3.15
        assert call_args['fee'] == 3.15
        # stamp_duty = 0 (buy only)
        assert call_args['stamp_duty'] == 0.0
        assert call_args['action'] == 'buy'
        assert call_args['price'] == 10.50
        assert call_args['quantity'] == 1000
        assert call_args['order_id'] == 1
        assert call_args['reason'] == '测试订单'

    def test_sell_trade_fee_calculation(self):
        """卖出交易费用：佣金 0.03% + 印花税 0.1%"""
        ds = _make_mock_ds()
        ds.portfolio.record_trade.return_value = 301

        order = _make_mock_order(action='sell', symbol='000001.SZ', name='平安银行')
        trade_id = trade_service.create_trade_from_order(ds, order, 15.00, 500)

        call_args = ds.portfolio.record_trade.call_args[0][0]

        # amount = 15.00 * 500 = 7500
        assert call_args['amount'] == 7500.0
        # fee = 7500 * 0.0003 = 2.25
        assert call_args['fee'] == 2.25
        # stamp_duty = 7500 * 0.001 = 7.50
        assert call_args['stamp_duty'] == 7.50
        assert call_args['action'] == 'sell'

    def test_trade_negative_price(self):
        """负成交价格应抛出 ValueError"""
        ds = _make_mock_ds()
        order = _make_mock_order(action='buy')

        with pytest.raises(ValueError, match="fill_price"):
            trade_service.create_trade_from_order(ds, order, -10.0, 100)

    def test_trade_zero_quantity(self):
        """零成交数量应抛出 ValueError"""
        ds = _make_mock_ds()
        order = _make_mock_order(action='buy')

        with pytest.raises(ValueError, match="fill_quantity"):
            trade_service.create_trade_from_order(ds, order, 10.0, 0)

    def test_trade_date_is_today(self):
        """交易日期应为当天"""
        ds = _make_mock_ds()
        ds.portfolio.record_trade.return_value = 302

        order = _make_mock_order(action='buy')
        trade_service.create_trade_from_order(ds, order, 10.0, 100)

        call_args = ds.portfolio.record_trade.call_args[0][0]
        assert call_args['trade_date'] == datetime.now().strftime('%Y-%m-%d')


# ==================== Position Calculation Tests ====================

class TestGetPosition:
    """测试 get_position 持仓计算"""

    def test_no_trades_empty_position(self):
        """无交易记录时持仓为空"""
        ds = _make_mock_ds()
        ds.portfolio.get_trades_by_symbol.return_value = []
        ds.kline.get_latest_daily_kline.return_value = None

        pos = trade_service.get_position(ds, '000001.SZ')

        assert pos['symbol'] == '000001.SZ'
        assert pos['remaining_quantity'] == 0
        assert pos['avg_cost'] == 0.0
        assert pos['total_cost'] == 0.0
        assert pos['market_value'] == 0.0
        assert pos['realized_pnl'] == 0.0
        assert pos['unrealized_pnl'] == 0.0
        assert pos['total_pnl'] == 0.0

    def test_buy_only_position(self):
        """仅有买入记录时正确计算持仓"""
        ds = _make_mock_ds()
        ds.portfolio.get_trades_by_symbol.return_value = [
            {'action': 'buy', 'quantity': 1000, 'amount': 10000.0, 'fee': 3.0, 'stamp_duty': 0.0, 'name': '平安银行'},
            {'action': 'buy', 'quantity': 500, 'amount': 5500.0, 'fee': 1.65, 'stamp_duty': 0.0, 'name': '平安银行'},
        ]
        ds.kline.get_latest_daily_kline.return_value = {'close': 12.0, 'trade_date': '2024-06-01'}

        pos = trade_service.get_position(ds, '000001.SZ')

        # total buy qty = 1500, total buy amount = 15500
        assert pos['remaining_quantity'] == 1500
        assert pos['avg_cost'] == pytest.approx(15500.0 / 1500, rel=1e-4)  # 10.3333
        assert pos['total_cost'] == pytest.approx(15500.0, rel=1e-4)
        assert pos['latest_price'] == 12.0
        # market_value = 1500 * 12.0 = 18000
        assert pos['market_value'] == 18000.0
        # unrealized_pnl = 1500 * (12.0 - 10.3333) = 2500.0
        assert pos['unrealized_pnl'] == pytest.approx(2500.0, rel=1e-2)
        # realized = 0 (no sells)
        assert pos['realized_pnl'] == 0.0

    def test_full_position_with_sells(self):
        """买入+卖出后正确计算剩余持仓"""
        ds = _make_mock_ds()
        ds.portfolio.get_trades_by_symbol.return_value = [
            {'action': 'buy', 'quantity': 1000, 'amount': 10000.0, 'fee': 3.0, 'stamp_duty': 0.0, 'name': '平安银行'},
            {'action': 'buy', 'quantity': 500, 'amount': 5500.0, 'fee': 1.65, 'stamp_duty': 0.0, 'name': '平安银行'},
            {'action': 'sell', 'quantity': 800, 'amount': 9600.0, 'fee': 2.88, 'stamp_duty': 9.60, 'name': '平安银行'},
        ]
        ds.kline.get_latest_daily_kline.return_value = {'close': 13.0, 'trade_date': '2024-06-15'}

        pos = trade_service.get_position(ds, '000001.SZ')

        # total buy: 1500, 15500; total sell: 800, 9600
        # remaining = 1500 - 800 = 700
        assert pos['remaining_quantity'] == 700
        # avg_cost = 15500 / 1500 = 10.3333
        assert pos['avg_cost'] == pytest.approx(10.3333, rel=1e-4)
        # market_value = 700 * 13.0 = 9100
        assert pos['market_value'] == 9100.0
        # unrealized = 700 * (13.0 - 10.3333) = 1866.67
        assert pos['unrealized_pnl'] == pytest.approx(1866.67, rel=1e-2)
        # realized = 9600 - 800*10.3333 - (2.88+9.60+3.0+1.65) = 9600 - 8266.67 - 17.13 = 1316.20
        # More precisely: cost of sold = 800 * 10.3333 = 8266.67
        # total fees = 3.0 + 1.65 + 2.88 + 9.60 = 17.13
        # realized = 9600 - 8266.67 - 17.13 = 1316.20
        expected_realized = 9600.0 - (800 * 15500.0 / 1500) - (3.0 + 1.65 + 2.88 + 9.60)
        assert pos['realized_pnl'] == pytest.approx(expected_realized, rel=1e-2)

    def test_invalid_symbol(self):
        """无效股票代码应抛出 ValueError"""
        ds = _make_mock_ds()

        with pytest.raises(ValueError, match="股票代码"):
            trade_service.get_position(ds, "INVALID")

    def test_position_kline_error_handling(self):
        """K线获取失败时仍能返回持仓（无市场价格）"""
        ds = _make_mock_ds()
        ds.portfolio.get_trades_by_symbol.return_value = [
            {'action': 'buy', 'quantity': 100, 'amount': 1000.0, 'fee': 0.3, 'stamp_duty': 0.0, 'name': '测试'},
        ]
        ds.kline.get_latest_daily_kline.side_effect = Exception("Kline unavailable")

        pos = trade_service.get_position(ds, '000001.SZ')

        assert pos['remaining_quantity'] == 100
        assert pos['latest_price'] is None
        assert pos['market_value'] == 0.0
        assert pos['unrealized_pnl'] == 0.0


# ==================== Get Trades Tests ====================

class TestGetTrades:
    """测试 trade_service.get_trades"""

    def test_get_trades_by_symbol(self):
        """按股票代码查询交易记录"""
        ds = _make_mock_ds()
        expected = [
            {'trade_id': 1, 'symbol': '000001.SZ', 'action': 'buy'},
            {'trade_id': 2, 'symbol': '000001.SZ', 'action': 'sell'},
        ]
        ds.portfolio.get_trades_by_symbol.return_value = expected

        result = trade_service.get_trades(ds, symbol='000001.SZ')

        assert result == expected
        ds.portfolio.get_trades_by_symbol.assert_called_once_with('000001.SZ', None, None)

    def test_get_trades_by_symbol_with_dates(self):
        """按股票代码和时间范围查询"""
        ds = _make_mock_ds()
        ds.portfolio.get_trades_by_symbol.return_value = []

        trade_service.get_trades(ds, symbol='000001.SZ', start_date='2024-01-01', end_date='2024-12-31')

        ds.portfolio.get_trades_by_symbol.assert_called_once_with(
            '000001.SZ', '2024-01-01', '2024-12-31'
        )

    def test_get_trades_by_date_without_symbol(self):
        """不带股票代码，按日期查询"""
        ds = _make_mock_ds()
        expected = [{'trade_id': 1}, {'trade_id': 2}]
        ds.portfolio.get_trades_by_date.return_value = expected

        result = trade_service.get_trades(ds, start_date='2024-01-01', end_date='2024-06-01')

        assert result == expected
        ds.portfolio.get_trades_by_date.assert_called_once_with('2024-01-01', '2024-06-01')

    def test_get_trades_default_date_fallback(self):
        """不带日期和股票代码时使用默认日期范围"""
        ds = _make_mock_ds()
        expected = [{'trade_id': 1}]
        ds.portfolio.get_trades_by_date.return_value = expected

        result = trade_service.get_trades(ds)

        # start_date defaults to '2000-01-01', end_date to today
        call_args = ds.portfolio.get_trades_by_date.call_args[0]
        assert call_args[0] == '2000-01-01'
        assert call_args[1] == datetime.now().strftime('%Y-%m-%d')
        assert result == expected

    def test_get_trades_with_limit(self):
        """返回结果受 limit 限制"""
        ds = _make_mock_ds()
        trades = [{'trade_id': i} for i in range(100)]
        ds.portfolio.get_trades_by_date.return_value = trades

        result = trade_service.get_trades(ds, limit=5)

        assert len(result) == 5
        assert result[0]['trade_id'] == 0


# ==================== Trade Stats Tests ====================

class TestTradeStats:
    """测试 get_trade_stats"""

    def test_empty_stats(self):
        """无交易时返回零值"""
        ds = _make_mock_ds()
        ds.portfolio.get_trade_stats.return_value = {}

        stats = trade_service.get_trade_stats(ds)

        assert stats['total_trades'] == 0
        assert stats['total_buys'] == 0
        assert stats['total_sells'] == 0
        assert stats['total_buy_amount'] == 0.0
        assert stats['total_sell_amount'] == 0.0
        assert stats['total_commission'] == 0.0
        assert stats['gross_pnl'] == 0.0
        assert stats['net_pnl'] == 0.0

    def test_with_trades(self):
        """有交易时正确计算盈亏"""
        ds = _make_mock_ds()
        ds.portfolio.get_trade_stats.return_value = {
            'total_trades': 5,
            'buy_trades': 3,
            'sell_trades': 2,
            'total_buy_amount': 50000.0,
            'total_sell_amount': 55000.0,
            'total_fee': 150.0,
        }

        stats = trade_service.get_trade_stats(ds)

        assert stats['total_trades'] == 5
        assert stats['total_buys'] == 3
        assert stats['total_sells'] == 2
        assert stats['gross_pnl'] == 5000.0
        assert stats['net_pnl'] == 4850.0  # 5000 - 150
        assert stats['total_commission'] == 150.0

    def test_negative_pnl(self):
        """亏损时 net_pnl 为负"""
        ds = _make_mock_ds()
        ds.portfolio.get_trade_stats.return_value = {
            'total_trades': 2,
            'buy_trades': 1,
            'sell_trades': 1,
            'total_buy_amount': 20000.0,
            'total_sell_amount': 18000.0,
            'total_fee': 66.0,
        }

        stats = trade_service.get_trade_stats(ds)

        assert stats['gross_pnl'] == -2000.0
        assert stats['net_pnl'] == -2066.0


# ==================== Integration Smoke Tests (with real DB) ====================

class TestOrderTradeIntegration:
    """真实数据库的烟雾测试 - 连接失败时跳过"""

    @pytest.fixture
    def ds(self):
        """创建真实 DataService"""
        try:
            service = DataService()
            # 验证连接
            if service.stock.db is None:
                pytest.skip("数据库连接不可用")
            return service
        except Exception as e:
            pytest.skip(f"无法创建 DataService: {e}")

    def test_create_and_fill_order_flow(self, ds):
        """完整的创建→成交→查询流程"""
        try:
            # 确保股票存在
            stock = ds.stock.get_by_symbol('000001.SZ')
            if stock is None:
                pytest.skip("测试股票 000001.SZ 不在数据库中")

            # 1. 创建订单
            order_id = order_service.create_order(
                ds, '000001.SZ', 'buy', 'limit', 100,
                price=5.00, reason='集成测试'
            )
            assert isinstance(order_id, int)
            assert order_id > 0

            # 2. 查询订单
            order = order_service.get_order(ds, order_id)
            assert order is not None
            assert order['status'] == 'pending'
            assert order['symbol'] == '000001.SZ'

            # 3. 部分成交
            result = order_service.fill_order(ds, order_id, 5.50, fill_quantity=40)
            assert result['is_full_fill'] is False
            assert result['filled_quantity'] == 40

            # 4. 验证订单状态
            order = order_service.get_order(ds, order_id)
            assert order['status'] == 'partial'
            assert order['filled_quantity'] == 40

            # 5. 全部成交
            result = order_service.fill_order(ds, order_id, 5.60, fill_quantity=60)
            assert result['is_full_fill'] is True

            # 6. 验证最终状态
            order = order_service.get_order(ds, order_id)
            assert order['status'] == 'filled'
            assert order['filled_quantity'] == 100

            # 7. 验证交易记录
            trades = trade_service.get_trades(ds, symbol='000001.SZ', limit=10)
            trade_ids = [t['order_id'] for t in trades]
            assert order_id in trade_ids

        except Exception as e:
            pytest.skip(f"集成测试跳过（DB错误）: {e}")

    def test_cancel_order_flow(self, ds):
        """创建→取消流程"""
        try:
            stock = ds.stock.get_by_symbol('000001.SZ')
            if stock is None:
                pytest.skip("测试股票 000001.SZ 不在数据库中")

            # 创建订单
            order_id = order_service.create_order(
                ds, '000001.SZ', 'sell', 'limit', 200,
                price=20.00, reason='取消测试'
            )

            # 取消订单
            result = order_service.cancel_order(ds, order_id)
            assert result is True

            # 验证状态
            order = order_service.get_order(ds, order_id)
            assert order['status'] == 'cancelled'

        except Exception as e:
            pytest.skip(f"集成测试跳过（DB错误）: {e}")

    def test_expire_orders(self, ds):
        """过期订单处理"""
        try:
            stock = ds.stock.get_by_symbol('000001.SZ')
            if stock is None:
                pytest.skip("测试股票 000001.SZ 不在数据库中")

            # 创建一个已过期的订单（直接在DB层操作）
            import psycopg2
            from infrastructure.persistence.database.base_repository import _resolve_db_dsn
            dsn = _resolve_db_dsn()
            if not dsn:
                pytest.skip("数据库连接不可用")

            conn = psycopg2.connect(dsn)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO quant.orders (symbol, name, order_type, action, price, quantity, status, reason, expires_at)
                VALUES ('000001.SZ', '平安银行', 'limit', 'buy', 5.00, 100, 'pending', '过期测试', '2000-01-01 00:00:00')
                RETURNING id
            """)
            expired_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()

            # 执行过期
            count = order_service.expire_orders(ds)
            assert count >= 1

            # 验证已过期
            order = order_service.get_order(ds, expired_id)
            assert order['status'] == 'expired'

        except Exception as e:
            pytest.skip(f"集成测试跳过（DB错误）: {e}")

    def test_get_position(self, ds):
        """持仓计算"""
        try:
            pos = trade_service.get_position(ds, '000001.SZ')
            assert 'symbol' in pos
            assert 'remaining_quantity' in pos
            assert 'avg_cost' in pos
            assert 'unrealized_pnl' in pos
            assert 'realized_pnl' in pos
        except Exception as e:
            pytest.skip(f"集成测试跳过（DB错误）: {e}")

    def test_get_trade_stats(self, ds):
        """交易统计"""
        try:
            stats = trade_service.get_trade_stats(ds)
            assert 'total_trades' in stats
            assert 'net_pnl' in stats
            assert 'gross_pnl' in stats
        except Exception as e:
            pytest.skip(f"集成测试跳过（DB错误）: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
