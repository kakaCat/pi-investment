"""cron 段数校验（2026-09-13，w-32314d00，看板事件 435f0c0a / 26737737 / c488fdad）。

背景：任务行写成 6 段（Agent OS / robfig-cron 风格，首位是秒）时，写入与任务注册都成功，
直到 APScheduler 加载才抛 ValueError: Wrong number of fields; got 6, expected 5 ——
表现是「任务根本没进调度器」：scheduler_runs 里查不到任何失败，只有一行加载日志。
本组用例锁定：校验拦在写入点与触发器构造点，且错误信息直指修法。
"""
import pytest

from infrastructure.scheduler.cron_compat import build_cron_trigger, validate_cron


def test_valid_5_field_cron_passes_and_builds():
    validate_cron('5 9 * * 1-5')
    assert build_cron_trigger('5 9 * * 1-5') is not None


def test_6_field_cron_rejected_with_actionable_message():
    with pytest.raises(ValueError) as ei:
        validate_cron('0 5 9 * * 1-5')
    msg = str(ei.value)
    assert '5 段' in msg
    assert '6 段' in msg, '错误信息须点明实际段数，否则看日志的人不知道差在哪'


def test_managed_by_agent_sentinel_is_allowed_by_validator():
    # 托管伪任务不是 cron，校验层放行（scheduler 加载阶段按 Agent OS 托管跳过）
    validate_cron('managed_by_agent_os')


def test_build_trigger_refuses_managed_sentinel():
    # 但真走到「构造触发器」这一步就是调用方漏了跳过逻辑 —— 必须显式报错而不是静默透传
    with pytest.raises(ValueError):
        build_cron_trigger('managed_by_agent_os')


def test_empty_cron_rejected():
    with pytest.raises(ValueError):
        validate_cron('')
