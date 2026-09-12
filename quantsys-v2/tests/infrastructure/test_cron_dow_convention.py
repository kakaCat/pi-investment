"""DOW 约定回归测（2026-09-12，w-c8cae280）。

此前 APScheduler 的 from_crontab 用 0=周一，而库里元数据/看门狗/检查点/人工书写
都用标准 cron（0=周日），导致 23 个带 DOW 的 enabled 任务整体错位一天：
Mon-Fri 实跑 Tue-Sat（周一整日缺失），周日任务实跑周一。本测把"标准 cron 的
星期六就是星期六"钉死，防止再次踩回。
"""
from datetime import datetime, timedelta, timezone

from infrastructure.scheduler.cron_compat import build_cron_trigger, convert_standard_dow

CST = timezone(timedelta(hours=8))
SAT = datetime(2026, 9, 12, 12, 0, tzinfo=CST)  # 2026-09-12 是星期六


def _next(expr: str, base: datetime = SAT) -> datetime:
    return build_cron_trigger(expr).get_next_fire_time(None, base).astimezone(CST)


def _week(expr: str, base: datetime = SAT) -> set:
    """围绕 base 取 7 次连续触发，返回星期缩写集合。

    迭代必须把上一次触发时刻作为 get_next_fire_time 的第一参数，
    否则 APScheduler 会一直返回同一时刻（本测初版就踩了这个坑）。
    """
    trg = build_cron_trigger(expr)
    prev, seen = None, set()
    for _ in range(7):
        nxt = trg.get_next_fire_time(prev, base if prev is None else prev)
        seen.add(nxt.astimezone(CST).strftime('%a'))
        prev = nxt
    return seen


def test_dow_6_is_saturday():
    t = _next('30 18 * * 6')
    assert t.strftime('%a') == 'Sat', t
    assert (t.hour, t.minute) == (18, 30)


def test_dow_0_is_sunday():
    assert _next('0 1 * * 0').strftime('%a') == 'Sun'


def test_dow_7_also_sunday():
    assert _next('0 1 * * 7').strftime('%a') == 'Sun'


def test_weekday_range_covers_monday_and_excludes_saturday():
    seen = _week('30 22 * * 1-5')
    assert seen == {'Mon', 'Tue', 'Wed', 'Thu', 'Fri'}, seen


def test_range_0_4_covers_sunday_through_thursday():
    seen = _week('0 23 * * 0-4')
    assert seen == {'Sun', 'Mon', 'Tue', 'Wed', 'Thu'}, seen


def test_other_fields_passed_through():
    t = _next('*/5 9-11,13-15 * * 1-5', datetime(2026, 9, 14, 0, 0, tzinfo=CST))
    assert (t.hour, t.minute) == (9, 0), t
    assert t.strftime('%a') == 'Mon', t


def test_all_days_star_unchanged():
    t = _next('0 8 * * *')
    assert t.strftime('%a') == 'Sun' and t.hour == 8


def test_convert_outputs_apscheduler_names():
    assert convert_standard_dow('6') == 'sat'
    assert convert_standard_dow('0') == 'sun'
    assert convert_standard_dow('*') == '*'
    assert convert_standard_dow('1-5') == 'mon,tue,wed,thu,fri'
    assert convert_standard_dow('0-4') == 'mon,tue,wed,thu,sun'
    assert convert_standard_dow('mon-fri') == 'mon,tue,wed,thu,fri'
