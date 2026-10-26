"""t9 验收用例：V2 宿主接入（FR-1/FR-11，backend.md IF-1）

覆盖：
- 开关默认关闭：WATCH_V2_ENABLED 未设 → 不启动（V1 行为不变）
- pytest skip=True → 返回 None（测试进程不拉起渲染循环）
- 开关解析：1/true/yes/on 均启用
- 每日任务已注册到 DailyJobs（v2_daily_cycle_reset）
- 每日重置**只重置活跃规则**（2026-10-23 用户裁定）
"""
import os

import pytest

from adapters.inbound.fastapi_app import watch_bootstrap_v2


class TestV2Switch:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv('WATCH_V2_ENABLED', raising=False)
        assert watch_bootstrap_v2.v2_enabled() is False

    @pytest.mark.parametrize('value', ['1', 'true', 'TRUE', 'yes', 'on'])
    def test_enabled_values(self, monkeypatch, value):
        monkeypatch.setenv('WATCH_V2_ENABLED', value)
        assert watch_bootstrap_v2.v2_enabled() is True

    @pytest.mark.parametrize('value', ['0', 'false', 'no', 'off', ''])
    def test_disabled_values(self, monkeypatch, value):
        monkeypatch.setenv('WATCH_V2_ENABLED', value)
        assert watch_bootstrap_v2.v2_enabled() is False


class TestStartStop:
    def test_skip_returns_none(self):
        assert watch_bootstrap_v2.start_watch_engine_v2(skip=True) is None

    def test_switch_off_returns_none(self, monkeypatch):
        monkeypatch.delenv('WATCH_V2_ENABLED', raising=False)
        assert watch_bootstrap_v2.start_watch_engine_v2(skip=False) is None

    def test_stop_none_safe(self):
        watch_bootstrap_v2.stop_watch_engine_v2(None)  # 不应抛异常


class TestDailyJobRegistered:
    def test_v2_daily_cycle_reset_registered(self):
        from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS
        ids = [j.job_id for j in JOBS]
        assert 'v2_daily_cycle_reset' in ids

    def test_job_has_weekday_schedule(self):
        from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS
        job = next(j for j in JOBS if j.job_id == 'v2_daily_cycle_reset')
        assert job.weekdays == (0, 1, 2, 3, 4)
        assert job.run_at.hour == 16 and job.run_at.minute == 35


class TestDailyCycleResetScope:
    """2026-10-23 用户裁定：活跃的才重置，非活跃的不需要重置。"""

    def test_job_resets_only_active_cycles(self, monkeypatch):
        import adapters.outbound.repositories.watch_rule_repository as wrr
        from adapters.inbound.fastapi_app.daily_jobs.v2_jobs import (
            _job_v2_daily_cycle_reset,
        )

        calls = []

        class FakeRepo:
            def reset_active_cycles(self):
                calls.append('reset_active_cycles')
                return 7

            def reset_all_cycles(self):  # 不应再被调用
                calls.append('reset_all_cycles')
                return 999

        monkeypatch.setattr(wrr, 'WatchRuleRepository', lambda: FakeRepo())
        result = _job_v2_daily_cycle_reset()

        assert result == {'reset_count': 7, 'scope': 'active', 'status': 'ok'}
        assert calls == ['reset_active_cycles'], '任务只走活跃规则重置（不是全量重置）'

    def test_job_degrades_without_raising(self, monkeypatch):
        import adapters.outbound.repositories.watch_rule_repository as wrr
        from adapters.inbound.fastapi_app.daily_jobs.v2_jobs import (
            _job_v2_daily_cycle_reset,
        )

        class BrokenRepo:
            def reset_active_cycles(self):
                raise RuntimeError('db down')

        monkeypatch.setattr(wrr, 'WatchRuleRepository', lambda: BrokenRepo())
        result = _job_v2_daily_cycle_reset()

        assert result['status'] == 'degraded'
        assert result['reset_count'] == 0
        assert result['scope'] == 'active'
        assert 'db down' in result['error']


class TestScheduledRegistration:
    """2026-10-23：V2 改为定时任务后，注册入口的开关语义。"""

    def test_switch_off_registers_nothing(self, monkeypatch):
        monkeypatch.delenv('WATCH_V2_ENABLED', raising=False)
        assert watch_bootstrap_v2.register_watch_v2_jobs() == 0

    def test_deprecated_start_keeps_none_contract(self):
        # 旧调用方仍可调，但不再起线程
        assert watch_bootstrap_v2.start_watch_engine_v2(skip=True) is None


class TestAccountAgentMap:
    def test_parse_json_map(self, monkeypatch):
        monkeypatch.setenv('WATCH_ACCOUNT_AGENT_MAP',
                           '{"agent_virtual": "agent-ts", "user_main": "agent-dh"}')
        assert watch_bootstrap_v2.account_agent_map_from_env() == {
            'agent_virtual': 'agent-ts', 'user_main': 'agent-dh'}

    def test_bad_json_falls_back_to_empty(self, monkeypatch):
        monkeypatch.setenv('WATCH_ACCOUNT_AGENT_MAP', '{bad json')
        assert watch_bootstrap_v2.account_agent_map_from_env() == {}

    def test_missing_env_is_empty(self, monkeypatch):
        monkeypatch.delenv('WATCH_ACCOUNT_AGENT_MAP', raising=False)
        assert watch_bootstrap_v2.account_agent_map_from_env() == {}


class TestFeishuSender:
    def test_missing_webhook_uses_existing_watch_channel(self, monkeypatch):
        from types import SimpleNamespace
        import qs_notification.application as notification_app

        class Facade:
            def __init__(self):
                self.calls = []

            def send_watch_triggered(self, **kwargs):
                self.calls.append(kwargs)
                return SimpleNamespace(success=True)

        facade = Facade()
        monkeypatch.setattr(notification_app, 'get_notification_facade', lambda: facade)
        sender = watch_bootstrap_v2.build_feishu_sender('')

        assert sender('止损盯盘 300750.SZ', '已到止损线') is True
        assert facade.calls[0]['symbol'] == '300750.SZ'
        assert facade.calls[0]['message'] == '已到止损线'
        assert facade.calls[0]['notify_mode'] == 'direct'


class TestTierPreflight:
    """切换安全网：watch_tier 列没落库就拒绝注册 V2 任务。"""

    def test_preflight_blocks_when_column_missing(self, monkeypatch):
        monkeypatch.setenv('WATCH_V2_ENABLED', 'true')
        rule = __import__('types').SimpleNamespace(id=1, watch_tier=None)

        class Repo:
            def list_by_state(self, state):
                return [rule]

        def _boom():
            raise AssertionError('预检未过时不该组装引擎')

        monkeypatch.setattr(watch_bootstrap_v2, 'build_engine_v2', _boom)
        assert watch_bootstrap_v2.register_watch_v2_jobs(rule_repo=Repo()) == 0

    def test_preflight_passes_when_column_present(self):
        rule = __import__('types').SimpleNamespace(id=1, watch_tier=30)

        class Repo:
            def list_by_state(self, state):
                return [rule]

        assert watch_bootstrap_v2.tier_column_ready(Repo()) is True
