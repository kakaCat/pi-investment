"""cron 段数校验与触发器构造（2026-09-13 初始；2026-10-23 扩到 6 段秒级）。

背景（2026-09-13，w-32314d00）：任务行写成 6 段时曾直到 APScheduler 加载才抛
"Wrong number of fields"。当时用"拒绝 6 段"兜住。

2026-10-23（盯盘 V2 定时任务）：30 秒档需要秒级 cron，6 段表达式正式支持
（**秒 分 时 日 月 周**，首位是秒）；段数既非 5 也非 6 时才拒绝。
"""
import pytest

from qs_ops.infrastructure.scheduler.cron_compat import build_cron_trigger, validate_cron


def test_valid_5_field_cron_passes_and_builds():
    validate_cron('5 9 * * 1-5')
    trigger = build_cron_trigger('5 9 * * 1-5')
    # 5 段：秒位未指定（CronTrigger 视为 0）
    assert trigger is not None


def test_valid_6_field_cron_passes_and_carries_second():
    validate_cron('*/30 * 9-11,13-14 * * 1-5')
    trigger = build_cron_trigger('*/30 * 9-11,13-14 * * 1-5')
    assert str(trigger.fields[-1]) == '*/30', '6 段首位必须是秒'
    # 星期仍按标准 cron 翻译：1-5 = 周一..周五
    assert 'mon' in str(trigger.fields[4]) and 'fri' in str(trigger.fields[4])


def test_4_field_cron_rejected_with_actionable_message():
    with pytest.raises(ValueError) as ei:
        validate_cron('5 9 * *')
    msg = str(ei.value)
    assert '5 段' in msg and '6 段' in msg, '错误信息须点明合法段数'
    assert '4 段' in msg, '错误信息须点明实际段数'


def test_managed_by_agent_sentinel_is_allowed_by_validator():
    # 托管伪任务不是 cron，校验层放行（scheduler 加载阶段按 Agent OS 托管跳过）
    validate_cron('managed_by_agent_os')


def test_build_trigger_refuses_managed_sentinel():
    with pytest.raises(ValueError):
        build_cron_trigger('managed_by_agent_os')


def test_empty_cron_rejected():
    with pytest.raises(ValueError):
        validate_cron('')
