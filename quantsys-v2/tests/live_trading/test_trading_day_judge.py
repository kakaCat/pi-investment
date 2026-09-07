"""交易日判定与每日检查跳过可见性测试（2026-08-12）

回归背景：_is_trading_day 用"当天日K已落库"判定交易日，但日K 17:40 才更新，
盘中/早盘的调度检查（06:30/14:25/14:30/15:30）永远判定"今天不是交易日"，
v13/v14 调仓永远跳过，且跳过被记为 success——策略调度成为空转剧场。
"""
from datetime import date, datetime, timedelta

import pytest

from live_trading.simulation_trader import SimulationTrader, judge_trading_day


# ── judge_trading_day 纯函数 ─────────────────────────────

class TestJudgeTradingDay:
    def test_weekend_is_not_trading_day(self):
        # 2026-08-15 是周六，即使有K线（脏数据）也不算
        assert judge_trading_day(
            date(2026, 8, 15), kline_exists_on_date=True,
            latest_kline_date=date(2026, 8, 14), today=date(2026, 8, 15),
        ) is False

    def test_future_weekday_is_not_trading_day(self):
        assert judge_trading_day(
            date(2026, 8, 20), kline_exists_on_date=False,
            latest_kline_date=date(2026, 8, 14), today=date(2026, 8, 14),
        ) is False

    def test_past_weekday_with_kline(self):
        assert judge_trading_day(
            date(2026, 8, 11), kline_exists_on_date=True,
            latest_kline_date=date(2026, 8, 11), today=date(2026, 8, 12),
        ) is True

    def test_past_weekday_without_kline_is_holiday(self):
        # 过去的 weekday 没有K线 = 法定节假日
        assert judge_trading_day(
            date(2026, 5, 1), kline_exists_on_date=False,
            latest_kline_date=date(2026, 8, 11), today=date(2026, 8, 12),
        ) is False

    def test_today_intraday_without_kline_market_active(self):
        """核心回归：盘中当天日K未落库（17:40才更新），但只要市场近期活跃，
        今天就应判定为交易日——调度在 14:30 跑时正是这种状态"""
        assert judge_trading_day(
            date(2026, 8, 12), kline_exists_on_date=False,
            latest_kline_date=date(2026, 8, 11), today=date(2026, 8, 12),
        ) is True

    def test_today_after_long_suspension(self):
        """长期无K线（停市/数据断供超7天）→ 今天不算交易日，防长假后误判"""
        assert judge_trading_day(
            date(2026, 8, 12), kline_exists_on_date=False,
            latest_kline_date=date(2026, 8, 1), today=date(2026, 8, 12),
        ) is False

    def test_today_no_kline_data_at_all(self):
        assert judge_trading_day(
            date(2026, 8, 12), kline_exists_on_date=False,
            latest_kline_date=None, today=date(2026, 8, 12),
        ) is False


# ── run_daily_check 跳过可见性 ───────────────────────────

def _bare_trader(**attrs):
    """绕过 __init__ 重依赖（DB/broker），构造最小可用实例"""
    t = object.__new__(SimulationTrader)
    for k, v in attrs.items():
        setattr(t, k, v)
    return t


class TestRunDailyCheckSkipContract:
    def test_skip_when_not_trading_day(self):
        t = _bare_trader(
            model=object(), portfolio={},
            last_rebalance_date='2026-07-17',
            config={'strategy': {'rebalance_days': 7}},
        )
        t._is_rebalance_due = lambda d: False
        t._is_trading_day = lambda d: False

        result = t.run_daily_check()

        assert result['executed'] is False
        assert result['reason'] == 'not_trading_day'

    def test_skip_when_model_not_loaded(self):
        t = _bare_trader(model=None, portfolio={})
        result = t.run_daily_check()
        assert result['executed'] is False
        assert result['reason'] == 'model_not_loaded'

    def test_executed_when_rebalance_runs(self):
        calls = []
        t = _bare_trader(
            model=object(), portfolio={},
            last_rebalance_date='2026-07-17',
            config={'strategy': {'rebalance_days': 7}},
        )
        t._is_rebalance_due = lambda d: True
        t._is_trading_day = lambda d: True
        t.rebalance = lambda d: calls.append(d)

        result = t.run_daily_check()

        assert result['executed'] is True
        assert result['action'] == 'rebalance'
        assert len(calls) == 1


# ── 策略禁用守卫（v14 休眠开关）─────────────────────────

class TestDisabledStrategyGuard:
    def test_daily_check_refuses_disabled_strategy(self, monkeypatch):
        from application.services.strategy_service import StrategyService

        svc = object.__new__(StrategyService)
        monkeypatch.setattr(
            StrategyService, 'get_config',
            lambda self, name: {'strategy': {'name': 'v14', 'enabled': False},
                                'initial_capital': 100000},
        )
        created = []
        monkeypatch.setattr(
            StrategyService, '_create_trader',
            lambda self, config, **kw: created.append(1),
        )

        result = svc.daily_check('v14')

        assert result['status'] == 'disabled'
        assert not created, "禁用策略不应创建交易器/触碰账户"
