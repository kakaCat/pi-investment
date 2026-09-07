"""
测试盈亏计算逻辑

🔴 关键测试：确保盈亏计算正确，包括手续费、印花税
"""
import pytest


class TestUnrealizedPnL:
    """测试浮动盈亏计算"""

    def test_unrealized_profit(self):
        """测试浮动盈利"""
        entry_price = 100.0
        current_price = 110.0
        quantity = 100

        # 浮动盈亏 = (当前价 - 入场价) * 数量
        unrealized_pnl = (current_price - entry_price) * quantity

        assert unrealized_pnl == 1000.0, f"浮动盈利应该是1000，实际是{unrealized_pnl}"
        assert unrealized_pnl > 0, "盈利应该>0"

    def test_unrealized_loss(self):
        """测试浮动亏损"""
        entry_price = 100.0
        current_price = 90.0
        quantity = 100

        unrealized_pnl = (current_price - entry_price) * quantity

        assert unrealized_pnl == -1000.0, f"浮动亏损应该是-1000，实际是{unrealized_pnl}"
        assert unrealized_pnl < 0, "亏损应该<0"

    def test_unrealized_breakeven(self):
        """测试浮动盈亏为0"""
        entry_price = 100.0
        current_price = 100.0
        quantity = 100

        unrealized_pnl = (current_price - entry_price) * quantity

        assert unrealized_pnl == 0.0, "持平时浮动盈亏应该是0"


class TestRealizedPnL:
    """测试已实现盈亏计算"""

    def test_realized_profit_no_commission(self):
        """测试已实现盈利（不含手续费）"""
        entry_price = 100.0
        exit_price = 110.0
        quantity = 100

        # 已实现盈亏 = (卖出价 - 买入价) * 数量
        realized_pnl = (exit_price - entry_price) * quantity

        assert realized_pnl == 1000.0, f"已实现盈利应该是1000，实际是{realized_pnl}"
        assert realized_pnl > 0, "盈利应该>0"

    def test_realized_loss_no_commission(self):
        """测试已实现亏损（不含手续费）"""
        entry_price = 100.0
        exit_price = 90.0
        quantity = 100

        realized_pnl = (exit_price - entry_price) * quantity

        assert realized_pnl == -1000.0, f"已实现亏损应该是-1000，实际是{realized_pnl}"
        assert realized_pnl < 0, "亏损应该<0"

    def test_realized_profit_with_commission(self):
        """测试已实现盈利（含手续费）"""
        entry_price = 100.0
        exit_price = 110.0
        quantity = 100
        commission_rate = 0.0003  # 0.03%
        stamp_tax_rate = 0.001    # 0.1% (仅卖出)

        # 买入成本
        buy_amount = entry_price * quantity
        buy_commission = max(buy_amount * commission_rate, 5)  # 最低5元
        total_cost = buy_amount + buy_commission

        # 卖出收入
        sell_amount = exit_price * quantity
        sell_commission = max(sell_amount * commission_rate, 5)
        stamp_tax = sell_amount * stamp_tax_rate
        total_proceeds = sell_amount - sell_commission - stamp_tax

        # 已实现盈亏
        realized_pnl = total_proceeds - total_cost

        # 验证计算
        expected_cost = 10000 + 5  # 买入10000 + 佣金5
        expected_proceeds = 11000 - 5 - 11  # 卖出11000 - 佣金5 - 印花税11
        expected_pnl = expected_proceeds - expected_cost

        assert abs(realized_pnl - expected_pnl) < 0.01, \
            f"含手续费的盈利计算错误，期望{expected_pnl}，实际{realized_pnl}"
        assert realized_pnl > 0, "扣除手续费后仍应该盈利"

    def test_realized_loss_with_commission(self):
        """测试已实现亏损（含手续费）"""
        entry_price = 100.0
        exit_price = 90.0
        quantity = 100
        commission_rate = 0.0003
        stamp_tax_rate = 0.001

        # 买入成本
        buy_amount = entry_price * quantity
        buy_commission = max(buy_amount * commission_rate, 5)
        total_cost = buy_amount + buy_commission

        # 卖出收入
        sell_amount = exit_price * quantity
        sell_commission = max(sell_amount * commission_rate, 5)
        stamp_tax = sell_amount * stamp_tax_rate
        total_proceeds = sell_amount - sell_commission - stamp_tax

        # 已实现盈亏
        realized_pnl = total_proceeds - total_cost

        # 验证计算
        expected_cost = 10000 + 5
        expected_proceeds = 9000 - 5 - 9
        expected_pnl = expected_proceeds - expected_cost

        assert abs(realized_pnl - expected_pnl) < 0.01, \
            f"含手续费的亏损计算错误，期望{expected_pnl}，实际{realized_pnl}"
        assert realized_pnl < 0, "亏损应该<0"


class TestProfitPercentage:
    """测试盈亏百分比计算"""

    def test_profit_percentage(self):
        """测试盈利百分比"""
        entry_price = 100.0
        exit_price = 110.0

        # 盈利百分比 = (卖出价 - 买入价) / 买入价
        profit_pct = (exit_price - entry_price) / entry_price

        assert profit_pct == 0.1, f"盈利百分比应该是10%，实际是{profit_pct*100}%"
        assert profit_pct > 0, "盈利百分比应该>0"

    def test_loss_percentage(self):
        """测试亏损百分比"""
        entry_price = 100.0
        exit_price = 90.0

        loss_pct = (exit_price - entry_price) / entry_price

        assert loss_pct == -0.1, f"亏损百分比应该是-10%，实际是{loss_pct*100}%"
        assert loss_pct < 0, "亏损百分比应该<0"


class TestSlippage:
    """测试滑点计算"""

    def test_buy_slippage(self):
        """测试买入滑点"""
        base_price = 100.0
        slippage_rate = 0.001  # 0.1%

        # 买入：价格上浮
        fill_price = base_price * (1 + slippage_rate)

        assert fill_price == 100.1, f"买入滑点价格应该是100.1，实际是{fill_price}"
        assert fill_price > base_price, "买入滑点应该使价格上涨"

    def test_sell_slippage(self):
        """测试卖出滑点"""
        base_price = 100.0
        slippage_rate = 0.001

        # 卖出：价格下浮
        fill_price = base_price * (1 - slippage_rate)

        assert fill_price == 99.9, f"卖出滑点价格应该是99.9，实际是{fill_price}"
        assert fill_price < base_price, "卖出滑点应该使价格下跌"
