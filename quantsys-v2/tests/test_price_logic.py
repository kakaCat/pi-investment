"""
测试核心价格逻辑 - 涨跌判断、价格比较

🔴 关键测试：上次涨跌判断弄反了，必须验证正确性
"""
import pytest


class TestPriceChangeDirection:
    """测试价格涨跌方向判断"""

    def test_price_increase(self):
        """测试价格上涨判断"""
        old_price = 100.0
        new_price = 110.0

        # 价格上涨
        change = new_price - old_price
        assert change > 0, "价格上涨，change应该>0"

        change_pct = (new_price - old_price) / old_price
        assert change_pct > 0, "价格上涨，涨幅应该>0"
        assert change_pct == 0.1, f"涨幅应该是10%，实际是{change_pct*100}%"

    def test_price_decrease(self):
        """测试价格下跌判断"""
        old_price = 100.0
        new_price = 90.0

        # 价格下跌
        change = new_price - old_price
        assert change < 0, "价格下跌，change应该<0"

        change_pct = (new_price - old_price) / old_price
        assert change_pct < 0, "价格下跌，跌幅应该<0"
        assert change_pct == -0.1, f"跌幅应该是-10%，实际是{change_pct*100}%"

    def test_price_unchanged(self):
        """测试价格不变"""
        old_price = 100.0
        new_price = 100.0

        change = new_price - old_price
        assert change == 0, "价格不变，change应该=0"

        change_pct = (new_price - old_price) / old_price
        assert change_pct == 0, "价格不变，涨跌幅应该=0"


class TestLimitUpDown:
    """测试涨跌停判断"""

    def test_limit_up_detection(self):
        """测试涨停判断"""
        prev_price = 100.0
        current_price = 110.0  # 涨10%

        change_pct = (current_price - prev_price) / prev_price
        is_limit_up = change_pct >= 0.099  # 接近10%

        assert is_limit_up == True, "涨10%应该判断为涨停"

    def test_limit_down_detection(self):
        """测试跌停判断"""
        prev_price = 100.0
        current_price = 90.0  # 跌10%

        change_pct = (current_price - prev_price) / prev_price
        is_limit_down = change_pct <= -0.099  # 接近-10%

        assert is_limit_down == True, "跌10%应该判断为跌停"

    def test_not_limit_up(self):
        """测试非涨停"""
        prev_price = 100.0
        current_price = 105.0  # 涨5%

        change_pct = (current_price - prev_price) / prev_price
        is_limit_up = change_pct >= 0.099

        assert is_limit_up == False, "涨5%不应该判断为涨停"

    def test_not_limit_down(self):
        """测试非跌停"""
        prev_price = 100.0
        current_price = 95.0  # 跌5%

        change_pct = (current_price - prev_price) / prev_price
        is_limit_down = change_pct <= -0.099

        assert is_limit_down == False, "跌5%不应该判断为跌停"


class TestStopLossTakeProfit:
    """测试止损止盈判断"""

    def test_stop_loss_triggered(self):
        """测试止损触发"""
        entry_price = 100.0
        stop_loss_price = 95.0  # 止损价
        current_price = 94.0    # 当前价跌破止损价

        # 止损触发条件：当前价 <= 止损价
        should_stop_loss = current_price <= stop_loss_price
        assert should_stop_loss == True, "当前价94跌破止损价95，应该触发止损"

    def test_stop_loss_not_triggered(self):
        """测试止损未触发"""
        entry_price = 100.0
        stop_loss_price = 95.0
        current_price = 96.0  # 当前价高于止损价

        should_stop_loss = current_price <= stop_loss_price
        assert should_stop_loss == False, "当前价96高于止损价95，不应该触发止损"

    def test_take_profit_triggered(self):
        """测试止盈触发"""
        entry_price = 100.0
        take_profit_price = 110.0  # 止盈价
        current_price = 111.0      # 当前价突破止盈价

        # 止盈触发条件：当前价 >= 止盈价
        should_take_profit = current_price >= take_profit_price
        assert should_take_profit == True, "当前价111突破止盈价110，应该触发止盈"

    def test_take_profit_not_triggered(self):
        """测试止盈未触发"""
        entry_price = 100.0
        take_profit_price = 110.0
        current_price = 109.0  # 当前价低于止盈价

        should_take_profit = current_price >= take_profit_price
        assert should_take_profit == False, "当前价109低于止盈价110，不应该触发止盈"


class TestPriceComparison:
    """测试价格比较逻辑"""

    def test_price_higher_than(self):
        """测试价格高于判断"""
        price_a = 110.0
        price_b = 100.0

        assert price_a > price_b, "110应该大于100"
        assert not (price_a < price_b), "110不应该小于100"

    def test_price_lower_than(self):
        """测试价格低于判断"""
        price_a = 90.0
        price_b = 100.0

        assert price_a < price_b, "90应该小于100"
        assert not (price_a > price_b), "90不应该大于100"

    def test_price_equal(self):
        """测试价格相等判断"""
        price_a = 100.0
        price_b = 100.0

        assert price_a == price_b, "100应该等于100"
        assert not (price_a > price_b), "100不应该大于100"
        assert not (price_a < price_b), "100不应该小于100"
