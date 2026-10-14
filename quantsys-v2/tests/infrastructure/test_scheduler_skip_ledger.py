"""执行期交易日门集成测试（REQ-261006093620-a315 · t5 · FR-2/FR-3/FR-4/FR-6）

四条**负向断言**是本文件的存在理由——只验"休市日写了 skipped"是不够的：

- N1：休市日跳过时 `_execute_command` **零调用**（防"记了 skipped 但其实照跑了"）
- N2：休市日跳过时 `_report_failure_to_sink` 与 Agent OS 事件**零调用**（FR-3 的"不打扰"）
- N4：交易日路径 `complete_run_skipped` **零调用**（防门误伤交易日）
- FR-6：`manual=True` 时休市日**照跑**（人工触发不被门拦）

全部用假仓储 + 假门，零 DB 零网络。
"""
from __future__ import annotations

from datetime import datetime

import pytest

from infrastructure.scheduler import job_executor as je

_HOLIDAY_INFO = {
    'day': '2026-10-07',
    'is_trading_day': False,
    'source': 'trading-calendar-holiday',
    'degraded': False,
    'reason': '该日不在交易日历中',
}
_TRADING_INFO = {
    'day': '2026-09-30',
    'is_trading_day': True,
    'source': 'trading-calendar',
    'degraded': False,
    'reason': '日历答该日为交易日',
}


class _FakeSession:
    """执行体在照跑路径上会 `session.rollback()` 止血（防 aborted 事务），故必须支持。"""

    def rollback(self):
        pass

    def commit(self):
        pass

    def close(self):
        pass


class _FakeRepo:
    def __init__(self, task):
        self.task = task
        self.created: list = []
        self.skipped: list = []
        self.completed: list = []
        #: 照跑路径落账的 result（F5 修正的断言对象）
        self.completed_results: list = []
        #: 造「跳过记账失败」用（F6 修正）
        self.raise_on_create = False

    def get_task(self, task_id):
        return self.task

    def create_run(self, task_id):
        if self.raise_on_create:
            raise RuntimeError('create_run boom')
        self.created.append(task_id)
        return 9000 + len(self.created)

    def list_runs(self, **kwargs):
        return []

    def complete_run_skipped(self, run_id, result=None):
        self.skipped.append((run_id, result))
        return True

    def complete_run(self, run_id, success=True, result=None, error=None):
        self.completed.append((run_id, success))
        self.completed_results.append((run_id, success, result))
        return True


class _FakeReporter:
    def __init__(self):
        self.events: list = []

    def set_task_context(self, **kwargs):
        pass

    def clear_task_context(self):
        pass

    def report_event(self, *args, **kwargs):
        self.events.append((args, kwargs))


def _task(**over):
    task = {
        'id': 250,
        'name': 'pre-market-scan',
        'command': 'market_scan_preopen',
        'params': {},
        'is_enabled': True,
        'trading_day_policy': 'trading-days',
    }
    task.update(over)
    return task


@pytest.fixture
def env(monkeypatch):
    """装好假仓储 / 假门 / 假执行器 / 假失败上报，并回收调用记录。"""
    calls = {'executed': [], 'failure_sink': [], 'should_skip_policies': []}
    reporter = _FakeReporter()
    holder = {}

    def _install(task, skip, info):
        repo = _FakeRepo(task)
        holder['repo'] = repo
        monkeypatch.setattr(
            'adapters.outbound.repositories.scheduler_repository.SchedulerRepository',
            lambda session=None: repo,
        )
        monkeypatch.setattr('infrastructure.persistence.orm.get_session', lambda: _FakeSession())
        monkeypatch.setattr('infrastructure.error_reporting.agent_os_reporter', reporter)
        monkeypatch.setattr(je, '_execute_command',
                            lambda command, params: calls['executed'].append(command) or {'status': 'success'})
        monkeypatch.setattr(je, '_report_failure_to_sink',
                            lambda *a, **k: calls['failure_sink'].append(a))

        def _fake_should_skip(policy, now=None):
            calls['should_skip_policies'].append((policy, now))
            return skip, info

        monkeypatch.setattr('application.services.trading_day_gate.should_skip', _fake_should_skip)
        # 让 executor 内 `from ... import POLICY_ALWAYS, should_skip` 拿到假门
        import application.services.trading_day_gate as gate_mod
        monkeypatch.setattr(gate_mod, 'POLICY_ALWAYS', 'always')
        return repo

    env.install = _install
    env.calls = calls
    env.reporter = reporter
    env.holder = holder
    return env


# ---------------------------------------------------------------------------
# N1 / N2 / FR-3：休市日只留痕，不干活、不打扰
# ---------------------------------------------------------------------------


def test_holiday_skips_without_executing(env):
    """N1：跳过时 `_execute_command` 零调用，且留痕带五键。"""
    repo = env.install(_task(), skip=True, info=_HOLIDAY_INFO)

    je._execute_scheduled_job_impl(250)

    assert env.calls['executed'] == []          # 一行都没跑
    assert repo.completed == []                 # 也没记 success/failed
    assert len(repo.skipped) == 1
    _run_id, result = repo.skipped[0]
    assert result['skipped'] is True
    assert result['trading_day_source'] == 'trading-calendar-holiday'
    assert result['policy'] == 'trading-days'
    assert result['degraded'] is False
    assert 'last_error' not in result           # 跳过不是失败


def test_holiday_skip_does_not_notify(env):
    """N2：跳过时失败上报与 Agent OS 事件零调用（留痕 + 不打扰）。"""
    env.install(_task(), skip=True, info=_HOLIDAY_INFO)

    je._execute_scheduled_job_impl(250)

    assert env.calls['failure_sink'] == []
    assert env.reporter.events == []


def test_skip_uses_task_policy_and_defaults_to_always(env):
    """门按任务的 trading_day_policy 判定；缺字段时回落 always（行为与装门之前一致）。"""
    env.install(_task(trading_day_policy=None), skip=True, info=_HOLIDAY_INFO)

    je._execute_scheduled_job_impl(250)

    assert env.calls['should_skip_policies'][0][0] == 'always'


_DEGRADED_INFO = {
    'day': '2026-10-07',
    'is_trading_day': False,
    'source': 'unavailable',
    'degraded': True,
    'reason': '日历不可用 → 按降级照跑',
}


def test_degraded_run_annotates_result(env):
    """F5 修正（独立复核发现）：降级照跑时 result 必须留下降级痕迹——**不许静默**。

    FR-2 原文：「任何降级来源一律判该跑，并把 `source` / `degraded` 带进 result 与日志」。
    原先只有跳过分支带五键，降级照跑时 result 是命令自己的返回、零降级痕迹。
    """
    repo = env.install(_task(), skip=False, info=_DEGRADED_INFO)

    je._execute_scheduled_job_impl(250)

    assert env.calls['executed'] == ['market_scan_preopen']
    _rid, _ok, result = repo.completed_results[0]
    assert result['trading_day_gate'] == {
        'source': 'unavailable', 'degraded': True, 'policy': 'trading-days',
    }


def test_skip_ledger_failure_does_not_raise(env):
    """F6 修正（独立复核发现）：跳过记账失败**不得外抛到调度线程**，且仍不执行命令。

    外层 try 只有 finally、没有兜底 except —— `create_run` 一抛就会穿到 APScheduler 线程
    且不留任何 run 记录。FR-3 的「记账失败不许影响调度」必须覆盖到 `create_run`。
    """
    repo = env.install(_task(), skip=True, info=_HOLIDAY_INFO)
    repo.raise_on_create = True

    je._execute_scheduled_job_impl(250)          # 不得抛

    assert env.calls['executed'] == []           # 门已判定不该跑 → 仍不执行
    assert repo.skipped == []                    # 也没留下半条记账


# ---------------------------------------------------------------------------
# N4：交易日路径不得被门碰到
# ---------------------------------------------------------------------------


def test_trading_day_runs_and_never_calls_skip_ledger(env):
    """N4：交易日 → 照跑，且 `complete_run_skipped` 零调用。"""
    repo = env.install(_task(), skip=False, info=_TRADING_INFO)

    je._execute_scheduled_job_impl(250)

    assert env.calls['executed'] == ['market_scan_preopen']
    assert repo.skipped == []                   # 门没碰交易日
    assert repo.completed == [(9001, True)]     # 走的是既有 complete_run 路径


# ---------------------------------------------------------------------------
# FR-6：人工触发不被门拦
# ---------------------------------------------------------------------------


def test_manual_trigger_runs_on_holiday(env):
    """FR-6：`manual=True` 时休市日**照跑**，且不判门、不写 skipped。"""
    repo = env.install(_task(), skip=True, info=_HOLIDAY_INFO)

    je._execute_scheduled_job_impl(250, manual=True)

    assert env.calls['should_skip_policies'] == []   # 门根本没被问
    assert repo.skipped == []
    assert env.calls['executed'] == ['market_scan_preopen']
    assert repo.completed == [(9001, True)]


def test_execute_scheduled_job_passes_manual_through(env, monkeypatch):
    """入口透传：`execute_scheduled_job(..., manual=True)` 必须把 manual 传到执行体。"""
    seen = {}
    monkeypatch.setattr(je, '_execute_scheduled_job_impl',
                        lambda task_id, manual=False: seen.update(task_id=task_id, manual=manual))
    monkeypatch.setattr('infrastructure.error_reporting.agent_os_reporter', env.reporter)

    je.execute_scheduled_job(250, manual=True)
    assert seen == {'task_id': 250, 'manual': True}

    je.execute_scheduled_job(250)
    assert seen == {'task_id': 250, 'manual': False}
