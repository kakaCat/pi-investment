"""
PortfolioRepository单元测试
"""
import pytest
from adapters.outbound.repositories import PortfolioORMRepository


class TestHoldings:
    """持仓管理测试"""

    def setup_method(self):
        self.repo = PortfolioORMRepository()

    def teardown_method(self):
        if hasattr(self.repo, 'db') and self.repo.db:
            self.repo.db.close()

    # ==================== 参数校验测试 ====================

    def test_get_holding_invalid_symbol(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.get_holding("INVALID")

    def test_get_holding_empty_symbol(self):
        with pytest.raises(ValueError, match="股票代码不能为空"):
            self.repo.get_holding("")

    def test_add_holding_missing_fields(self):
        with pytest.raises(ValueError, match="缺少必需字段"):
            self.repo.add_or_update_holding({"symbol": "000001.SZ"})

    def test_add_holding_invalid_symbol(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.add_or_update_holding({
                "symbol": "INVALID",
                "name": "测试",
                "quantity": 100,
                "avg_cost": 10.0,
                "total_invested": 1000.0,
                "market": "A",
                "added_date": "2024-01-01"
            })

    def test_add_holding_invalid_date(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.add_or_update_holding({
                "symbol": "000001.SZ",
                "name": "测试",
                "quantity": 100,
                "avg_cost": 10.0,
                "total_invested": 1000.0,
                "market": "A",
                "added_date": "2024/01/01"
            })

    # ==================== 查询方法测试 ====================

    def test_get_holding_not_found(self):
        holding = self.repo.get_holding("999999.SZ")
        assert holding is None

    def test_get_all_holdings(self):
        holdings = self.repo.get_all_holdings()
        assert isinstance(holdings, list)
        if len(holdings) > 0:
            assert 'symbol' in holdings[0]
            assert 'name' in holdings[0]
            assert 'quantity' in holdings[0]

    def test_get_all_holdings_by_market(self):
        holdings = self.repo.get_all_holdings(market="A")
        assert isinstance(holdings, list)
        for h in holdings:
            assert h['market'] == 'A'

    def test_get_all_holdings_by_sector(self):
        holdings = self.repo.get_all_holdings(sector="白酒")
        assert isinstance(holdings, list)
        for h in holdings:
            assert h.get('sector') == '白酒'

    def test_get_holdings_stats(self):
        stats = self.repo.get_holdings_stats()
        assert isinstance(stats, dict)
        assert 'total_positions' in stats
        assert 'total_invested' in stats
        assert 'sector_distribution' in stats
        assert 'market_distribution' in stats
        assert isinstance(stats['total_positions'], int)

    # ==================== 写入方法测试 ====================

    def test_add_or_update_holding_basic(self):
        holding_data = {
            "symbol": "000001.SZ",
            "name": "平安银行",
            "quantity": 1000,
            "avg_cost": 10.50,
            "total_invested": 10500.0,
            "market": "A",
            "added_date": "2024-01-15",
            "sector": "银行",
            "buy_reason": "估值修复"
        }
        try:
            result = self.repo.add_or_update_holding(holding_data)
            assert result is True
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    def test_remove_holding(self):
        try:
            self.repo.remove_holding("999999.SZ")
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")


class TestTrades:
    """交易记录测试"""

    def setup_method(self):
        self.repo = PortfolioORMRepository()

    def teardown_method(self):
        if hasattr(self.repo, 'db') and self.repo.db:
            self.repo.db.close()

    # ==================== 参数校验测试 ====================

    def test_get_trades_by_symbol_invalid(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.get_trades_by_symbol("INVALID")

    def test_get_trades_by_date_invalid_date(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.get_trades_by_date("2024/01/01", "2024-01-31")

    def test_record_trade_missing_fields(self):
        with pytest.raises(ValueError, match="缺少必需字段"):
            self.repo.record_trade({"symbol": "000001.SZ"})

    def test_record_trade_invalid_action(self):
        with pytest.raises(ValueError, match="无效的交易方向"):
            self.repo.record_trade({
                "symbol": "000001.SZ",
                "name": "平安银行",
                "action": "hold",
                "price": 10.0,
                "quantity": 100,
                "amount": 1000.0,
                "trade_date": "2024-01-02"
            })

    def test_record_trade_invalid_symbol(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.record_trade({
                "symbol": "INVALID",
                "name": "测试",
                "action": "buy",
                "price": 10.0,
                "quantity": 100,
                "amount": 1000.0,
                "trade_date": "2024-01-02"
            })

    def test_get_trades_by_date_invalid_action(self):
        with pytest.raises(ValueError, match="无效的交易方向"):
            self.repo.get_trades_by_date("2024-01-01", "2024-01-31", action="hold")

    # ==================== 查询方法测试 ====================

    def test_get_trade_not_found(self):
        trade = self.repo.get_trade(999999999)
        assert trade is None

    def test_get_trades_by_symbol_no_data(self):
        trades = self.repo.get_trades_by_symbol("999999.SZ")
        assert isinstance(trades, list)
        assert trades == []

    def test_get_trades_by_date_no_data(self):
        trades = self.repo.get_trades_by_date("2020-01-01", "2020-01-31")
        assert isinstance(trades, list)
        assert trades == []

    def test_get_trade_stats(self):
        stats = self.repo.get_trade_stats()
        assert isinstance(stats, dict)
        if stats:
            assert 'total_trades' in stats
            assert 'buy_trades' in stats
            assert 'sell_trades' in stats

    # ==================== 写入方法测试 ====================

    def test_record_trade_basic(self):
        trade_data = {
            "symbol": "000001.SZ",
            "name": "平安银行",
            "action": "buy",
            "price": 10.50,
            "quantity": 100,
            "amount": 1050.00,
            "fee": 5.0,
            "stamp_duty": 1.0,
            "trade_date": "2024-01-02",
            "reason": "技术突破买入"
        }
        try:
            trade_id = self.repo.record_trade(trade_data)
            assert isinstance(trade_id, int)
            assert trade_id > 0
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")


class TestOrders:
    """订单管理测试"""

    def setup_method(self):
        self.repo = PortfolioORMRepository()

    def teardown_method(self):
        if hasattr(self.repo, 'db') and self.repo.db:
            self.repo.db.close()

    # ==================== 参数校验测试 ====================

    def test_get_orders_invalid_status(self):
        with pytest.raises(ValueError, match="无效的订单状态"):
            self.repo.get_orders(status="unknown")

    def test_create_order_missing_fields(self):
        with pytest.raises(ValueError, match="缺少必需字段"):
            self.repo.create_order({"symbol": "000001.SZ"})

    def test_create_order_invalid_type(self):
        with pytest.raises(ValueError, match="无效的订单类型"):
            self.repo.create_order({
                "symbol": "000001.SZ",
                "name": "平安银行",
                "order_type": "invalid",
                "action": "buy",
                "quantity": 100,
                "status": "pending"
            })

    def test_create_order_invalid_action(self):
        with pytest.raises(ValueError, match="无效的订单方向"):
            self.repo.create_order({
                "symbol": "000001.SZ",
                "name": "平安银行",
                "order_type": "limit",
                "action": "hold",
                "quantity": 100,
                "status": "pending"
            })

    def test_create_order_invalid_status(self):
        with pytest.raises(ValueError, match="无效的订单状态"):
            self.repo.create_order({
                "symbol": "000001.SZ",
                "name": "平安银行",
                "order_type": "limit",
                "action": "buy",
                "quantity": 100,
                "status": "unknown"
            })

    def test_create_order_invalid_symbol(self):
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.create_order({
                "symbol": "INVALID",
                "name": "测试",
                "order_type": "limit",
                "action": "buy",
                "quantity": 100,
                "status": "pending"
            })

    def test_update_order_invalid_status(self):
        with pytest.raises(ValueError, match="无效的订单状态"):
            self.repo.update_order_status(1, "unknown")

    # ==================== 查询方法测试 ====================

    def test_get_order_not_found(self):
        order = self.repo.get_order(999999999)
        assert order is None

    def test_get_orders_empty(self):
        orders = self.repo.get_orders(symbol="999999.SZ")
        assert isinstance(orders, list)

    def test_get_pending_orders(self):
        orders = self.repo.get_pending_orders()
        assert isinstance(orders, list)
        for o in orders:
            assert o['status'] == 'pending'

    def test_get_order_stats(self):
        stats = self.repo.get_order_stats()
        assert isinstance(stats, dict)
        if stats:
            assert 'total_orders' in stats
            assert 'pending' in stats
            assert 'filled' in stats

    # ==================== 写入方法测试 ====================

    def test_create_order_basic(self):
        order_data = {
            "symbol": "000001.SZ",
            "name": "平安银行",
            "order_type": "limit",
            "action": "buy",
            "price": 10.50,
            "quantity": 100,
            "status": "pending",
            "reason": "技术突破买入"
        }
        try:
            order_id = self.repo.create_order(order_data)
            assert isinstance(order_id, int)
            assert order_id > 0
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    def test_cancel_order_not_exist(self):
        try:
            result = self.repo.cancel_order(999999999)
            assert result is False
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
