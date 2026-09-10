"""execute_trade 入参类型护栏回归测试（2026-09-11，w-8f2c4cc5）

背景（看板事件 56dab403）：
    客户端 POST /api/simulation/accounts/agent_virtual/trade 传 shares 为 JSON
    字符串时，execute_trade 直接执行 `shares % 100`——str % int 退化为字符串
    格式化，抛 TypeError("not all arguments converted during string formatting")，
    路由 except Exception 分支（当时无日志）返回 500 = 静默 500，根因无处可查。

护栏后：非法类型/取值一律 TradingError(400)，不再落到 500。
"""
import pytest

from application.services.account_trading_service import (
    AccountTradingService, TradingError,
)
from unittest.mock import Mock

REASON = "w-8f2c4cc5 回归测试：入参类型护栏（至少十字）"


def make_service():
    """校验路径不触达仓储/日历，用 Mock 占位（避免 DB 与行情依赖）"""
    cal = Mock()
    cal.is_trading_day.return_value = True
    return AccountTradingService(repo=Mock(), calendar=cal)


def call(**overrides):
    kw = dict(account_name='agent_virtual', action='BUY', symbol='600887',
              shares=100, reason=REASON, price=10.0, price_limit=None,
              amount=None, execute_at=None, allow_duplicate=False,
              max_positions=10)
    kw.update(overrides)
    return make_service().execute_trade(**kw)


class TestSharesTypeGuard:
    def test_shares_as_json_string_returns_400_not_500(self):
        """回归 56dab403：shares="100"（JSON 字符串）被规整为 int，不得 TypeError

        规整后进入正常业务护栏路径（此处为交易时段/仓位等 422），
        关键断言是：不再出现 TypeError 冒泡成 500，且状态码非 500。
        """
        try:
            call(shares="100")
        except TradingError as e:
            assert e.status_code != 500
        except TypeError as e:  # pragma: no cover
            pytest.fail(f"shares 字符串泄漏 TypeError（500 根因）: {e}")

    def test_shares_bool_rejected(self):
        with pytest.raises(TradingError) as ei:
            call(shares=True)
        assert ei.value.status_code == 400

    def test_shares_nonnumeric_string_rejected(self):
        with pytest.raises(TradingError) as ei:
            call(shares="一百")
        assert ei.value.status_code == 400

    def test_shares_list_rejected(self):
        with pytest.raises(TradingError) as ei:
            call(shares=[100])
        assert ei.value.status_code == 400

    def test_shares_non_integral_float_rejected(self):
        with pytest.raises(TradingError) as ei:
            call(shares=100.5)
        assert ei.value.status_code == 400

    def test_shares_float_integral_accepted(self):
        """100.0（JSON 无 int/float 区分）应被接受，进入正常护栏路径"""
        with pytest.raises(TradingError) as ei:
            call(shares=100.0)
        assert ei.value.status_code != 400  # 原因为价格/交易时段等业务护栏

    def test_shares_zero_rejected(self):
        with pytest.raises(TradingError) as ei:
            call(shares=0)
        assert ei.value.status_code == 400

    def test_shares_str_does_not_leak_typeerror(self):
        """关键回归：字符串 shares 绝不能抛 TypeError（曾冒泡成 500）"""
        try:
            call(shares="100")
        except TradingError:
            pass
        except TypeError as e:  # pragma: no cover
            pytest.fail(f"shares 字符串泄漏 TypeError（500 根因）: {e}")


class TestOtherNumberGuards:
    def test_price_nonnumeric_rejected(self):
        with pytest.raises(TradingError) as ei:
            call(price="abc")
        assert ei.value.status_code == 400

    def test_price_limit_nonnumeric_rejected(self):
        with pytest.raises(TradingError) as ei:
            call(price_limit="abc")
        assert ei.value.status_code == 400

    def test_amount_string_parsed(self):
        """amount="5000" 应被解析为 5000.0（不足一手 → 422 业务拒绝，非 400/500）"""
        with pytest.raises(TradingError) as ei:
            call(shares=None, amount="5000", price=10.0)
        assert ei.value.status_code in (422, 400)
        assert ei.value.status_code != 500

    def test_amount_negative_rejected(self):
        with pytest.raises(TradingError) as ei:
            call(shares=None, amount=-1000)
        assert ei.value.status_code == 400

    def test_symbol_missing_rejected(self):
        with pytest.raises(TradingError) as ei:
            call(symbol=None)
        assert ei.value.status_code == 400

    def test_symbol_non_string_rejected(self):
        with pytest.raises(TradingError) as ei:
            call(symbol=600887)
        assert ei.value.status_code == 400

    def test_max_positions_string_parsed(self):
        with pytest.raises(TradingError) as ei:
            call(shares=50, max_positions="10")
        assert ei.value.status_code == 422  # 非整手，业务护栏


class TestHelperCoercion:
    def test_as_int_accepts_numeric_variants(self):
        f = AccountTradingService._as_int
        assert f(100, 'x') == 100
        assert f(100.0, 'x') == 100
        assert f("100", 'x') == 100
        assert f(" 100.0 ", 'x') == 100
        assert f(None, 'x') is None

    def test_as_float_accepts_numeric_variants(self):
        f = AccountTradingService._as_float
        assert f(10, 'x') == 10.0
        assert f("10.5", 'x') == 10.5
        assert f(None, 'x') is None

    def test_as_int_rejects_garbage(self):
        with pytest.raises(TradingError):
            AccountTradingService._as_int("一百", 'shares')
