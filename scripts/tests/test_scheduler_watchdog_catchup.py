"""补跑业务规则单测（2026-09-13，w-c8cae280）。

被测对象：scripts/scheduler_watchdog.py 的纯函数 catchup_decision / is_trading_now。
规则顺序：一次性任务 → 授权位 → 已被后续成功运行覆盖 → 次数上限 → 补跑窗口
        → 最早补跑时刻 → 交易时段。
"""
import importlib.util
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

CST = timezone(timedelta(hours=8))
WATCHDOG = pathlib.Path(__file__).resolve().parents[1] / 'scheduler_watchdog.py'


@pytest.fixture(scope='module')
def wd():
    spec = importlib.util.spec_from_file_location('scheduler_watchdog', WATCHDOG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rule(**kw):
    base = {
        'enabled': True, 'max_attempts': 1, 'check_after': None,
        'window_hours': 12, 'market_hours_only': False, 'task_type': 'cron',
        'superseded': False, 'slot_age_hours': 1.0, 'attempts_used': 0,
    }
    base.update(kw)
    return base


# 用周三 14:00（交易时段内）与周三 22:00 两个基准时刻
TUE_TRADING = datetime(2026, 9, 16, 14, 0, tzinfo=CST)
TUE_NIGHT = datetime(2026, 9, 16, 22, 0, tzinfo=CST)
SAT = datetime(2026, 9, 19, 14, 0, tzinfo=CST)


def test_eligible_when_all_rules_pass(wd):
    ok, reason = wd.catchup_decision(_rule(), TUE_NIGHT)
    assert (ok, reason) == (True, 'eligible')


def test_one_off_never_caught_up(wd):
    ok, reason = wd.catchup_decision(_rule(task_type='once'), TUE_NIGHT)
    assert ok is False and reason == 'one_off'


def test_unauthorized_task_skipped(wd):
    ok, reason = wd.catchup_decision(_rule(enabled=False), TUE_NIGHT)
    assert ok is False and reason == 'policy_alert_only'


def test_superseded_slot_skipped(wd):
    """槽位之后已有成功运行 → 补跑只会重复（真实场景：238/253 次日已手工补跑成功）。"""
    ok, reason = wd.catchup_decision(_rule(superseded=True), TUE_NIGHT)
    assert ok is False and reason == 'superseded'


def test_max_attempts_enforced(wd):
    ok, reason = wd.catchup_decision(_rule(max_attempts=2, attempts_used=2), TUE_NIGHT)
    assert ok is False and reason == 'max_attempts'
    ok2, _ = wd.catchup_decision(_rule(max_attempts=2, attempts_used=1), TUE_NIGHT)
    assert ok2 is True


def test_window_exceeded_skipped(wd):
    ok, reason = wd.catchup_decision(_rule(window_hours=6, slot_age_hours=6.1), TUE_NIGHT)
    assert ok is False and reason == 'window_exceeded'


def test_before_check_after_deferred(wd):
    """未到最早补跑时刻：不补但不作废（下一轮会重判）。"""
    ok, reason = wd.catchup_decision(_rule(check_after='08:00'), datetime(2026, 9, 16, 3, 0, tzinfo=CST))
    assert ok is False and reason == 'before_check_after'
    ok2, _ = wd.catchup_decision(_rule(check_after='08:00'), datetime(2026, 9, 16, 9, 0, tzinfo=CST))
    assert ok2 is True


def test_market_hours_only_blocks_off_hours_and_weekend(wd):
    r = _rule(market_hours_only=True)
    assert wd.catchup_decision(r, TUE_NIGHT)[1] == 'outside_market_hours'
    assert wd.catchup_decision(r, SAT)[1] == 'outside_market_hours'
    # 午间休市（11:45）不算交易时段
    assert wd.catchup_decision(r, datetime(2026, 9, 16, 11, 45, tzinfo=CST))[1] == 'outside_market_hours'
    assert wd.catchup_decision(r, TUE_TRADING) == (True, 'eligible')


def test_is_trading_now_boundaries(wd):
    assert wd.is_trading_now(datetime(2026, 9, 16, 9, 30, tzinfo=CST)) is True
    assert wd.is_trading_now(datetime(2026, 9, 16, 9, 29, tzinfo=CST)) is False
    assert wd.is_trading_now(datetime(2026, 9, 16, 15, 0, tzinfo=CST)) is True
    assert wd.is_trading_now(datetime(2026, 9, 16, 15, 1, tzinfo=CST)) is False
    assert wd.is_trading_now(SAT) is False


def test_reason_codes_have_chinese_text(wd):
    for code in ('one_off', 'policy_alert_only', 'superseded', 'max_attempts',
                 'window_exceeded', 'before_check_after', 'outside_market_hours', 'eligible'):
        assert code in wd.CATCHUP_REASON_ZH
