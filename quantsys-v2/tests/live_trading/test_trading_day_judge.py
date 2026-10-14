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
    """run_daily_check 的结果契约。

    2026-10-04（REQ-261004154902-a7cd t2）契约升级：新增 ok / status，
    且**失败一律 executed=False**（需求判定标准禁止再出现
    「executed=True + action='rebalance'」这一旧形状）。

    本组用例必须打桩失败出口：新契约会在失败时主动外发，
    而测试期真实外发会被 tests/notify_guard.py 判失败（这是有意设计）。
    """

    @pytest.fixture(autouse=True)
    def _stub_failure_sink(self, monkeypatch):
        import live_trading.simulation_trader as st

        monkeypatch.setattr(
            st, "report_failure", lambda *a, **k: True
        )

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
        # 跳过不是成功（旧实现会把它记成 success，导致空转数周无人察觉）
        assert result['status'] == 'skipped'
        assert result['ok'] is False

    def test_skip_when_model_not_loaded(self):
        t = _bare_trader(model=None, portfolio={})
        result = t.run_daily_check()
        assert result['executed'] is False
        assert result['reason'] == 'model_not_loaded'
        # 模型没加载是**环境坏**，不是"合理跳过"
        assert result['status'] == 'failed'
        assert result['ok'] is False

    def test_executed_when_rebalance_runs(self):
        calls = []
        t = _bare_trader(
            model=object(), portfolio={},
            last_rebalance_date='2026-07-17',
            config={'strategy': {'rebalance_days': 7}},
        )
        t._is_rebalance_due = lambda d: True
        t._is_trading_day = lambda d: True

        def _fake_rebalance(date):
            calls.append(date)
            return {'success': True, 'position_count': 0, 'total_value': 0.0}

        t.rebalance = _fake_rebalance

        result = t.run_daily_check()

        assert result['executed'] is True
        assert result['action'] == 'rebalance'
        assert result['status'] == 'success'
        assert result['ok'] is True
        assert len(calls) == 1

    def test_rebalance_failure_is_not_reported_as_success(self):
        """回归锁：调仓失败必须失败，且不得是 executed=True + action='rebalance'。"""
        t = _bare_trader(
            model=object(), portfolio={},
            last_rebalance_date='2026-07-17',
            config={'strategy': {'rebalance_days': 7}},
        )
        t._is_rebalance_due = lambda d: True
        t._is_trading_day = lambda d: True
        t.rebalance = lambda d: {'success': False, 'error': 'boom'}

        result = t.run_daily_check()

        assert result['status'] == 'failed'
        assert result['ok'] is False
        assert result['reason'] == 'rebalance_failed'
        assert not (result['executed'] is True and result['action'] == 'rebalance')


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
