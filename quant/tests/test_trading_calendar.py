"""交易日历管理类测试"""
import pytest
from datetime import date, timedelta
from quantsys.data.trading_calendar import TradingCalendar


def test_load_trading_days():
    """测试加载交易日历"""
    calendar = TradingCalendar()
    start_date = date(2024, 1, 1)
    end_date = date(2024, 12, 31)

    trading_days = calendar.get_trading_days(start_date, end_date)

    assert len(trading_days) > 200  # 一年约240个交易日
    assert all(isinstance(d, date) for d in trading_days)
    assert trading_days == sorted(trading_days)  # 确保排序


def test_is_trading_day():
    """测试判断是否为交易日"""
    calendar = TradingCalendar()

    # 2024-01-02 是交易日（周二）
    assert calendar.is_trading_day(date(2024, 1, 2)) is True

    # 2024-01-01 是元旦假期
    assert calendar.is_trading_day(date(2024, 1, 1)) is False

    # 2024-01-06 是周六
    assert calendar.is_trading_day(date(2024, 1, 6)) is False


def test_get_trading_days_in_range():
    """测试获取日期范围内的交易日"""
    calendar = TradingCalendar()
    start_date = date(2024, 5, 20)
    end_date = date(2024, 5, 24)

    trading_days = calendar.get_trading_days(start_date, end_date)

    # 这周有5个交易日
    assert len(trading_days) == 5
    assert start_date in trading_days
    assert end_date in trading_days


def test_cache_mechanism():
    """测试缓存机制"""
    calendar = TradingCalendar()
    start_date = date(2024, 1, 1)
    end_date = date(2024, 12, 31)

    # 第一次调用，从API获取
    trading_days_1 = calendar.get_trading_days(start_date, end_date)

    # 第二次调用，从缓存获取
    trading_days_2 = calendar.get_trading_days(start_date, end_date)

    assert trading_days_1 == trading_days_2
