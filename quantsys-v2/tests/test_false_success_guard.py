"""假成功防护回归（2026-09-13，w-32314d00）

背景：`scheduler_tasks.last_status` / `quant.inprocess_job_runs` 连续多日记 success，
但真实失败藏在返回值里没人看。审计实证（2026-09-13）：

- `quant.inprocess_job_runs` 近 30 天 6 条 success 的结果含失败标记：
  evening_pipeline 2026-09-03/04/07/08/09 五天（`kline_sync: column "updated_at" does not exist`）
  + financial_statements 2026-09-05（handler reported success=false）；另有 1 条 running 卡 12h+；
- `quant.scheduler_runs` 近 14 天 7 条 success 的结果含失败标记
  （task 323/301 'regime_daily' 属性错、task 258 'list_pools' 属性错、task 232 "name 'datetime' is not defined"）。

本测试锁住三处执行路径的判定：①公共判定函数 find_result_failure（含嵌套、含 skipped 语义）；
②SchedulerService.run_task（APScheduler/手动触发路径）；③daily_jobs_bootstrap._run_job（进程内宿主）
与孤儿 running 行的判死。
"""
import logging
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

import pytest

from infrastructure.scheduler.job_executor import (
    classify_job_result,
    find_result_failure,
)


# ---------------------------------------------------------------------------
# ① 公共判定函数
# ---------------------------------------------------------------------------

def test_top_level_failures_are_detected():
    assert find_result_failure({'success': False, 'error': 'boom'}) == 'boom'
    assert find_result_failure({'status': 'error', 'error': 'db down'}) == 'db down'
    assert find_result_failure({'status': 'failed'}) is not None
    assert find_result_failure({'error': 'bare error'}) == 'bare error'


def test_success_shapes_are_not_flagged():
    assert find_result_failure({'success': True, 'symbols': 10}) is None
    assert find_result_failure({'status': 'success', 'computed': 5}) is None
    assert find_result_failure({'action': 'x', 'errors': 0}) is None
    assert find_result_failure(None) is None
    assert find_result_failure({'detail': 'no markers'}) is None


def test_nested_failure_is_detected():
    """实证形态：外层正常，失败藏在 kline_sync 里。"""
    result = {
        'kline_sync': {'status': 'error', 'error': 'column "updated_at" does not exist'},
        'factor_compute': {'status': 'success', 'symbols_computed': 5000},
    }
    err = find_result_failure(result)
    assert err is not None and err.startswith('kline_sync: ') and 'updated_at' in err


def test_nested_skip_is_not_a_failure():
    result = {'kline_sync': {'status': 'skipped', 'reason': 'K线已新鲜'}}
    assert find_result_failure(result) is None


def test_explicit_skip_wins_over_success_false():
    """非交易日/幂等跳过用 {'skipped': True, 'success': False} 表达，不算失败。"""
    result = {'success': False, 'skipped': True, 'reason': 'non_trading_day'}
    assert find_result_failure(result) is None


def test_diagnostic_error_lists_do_not_cause_false_positives():
    """failed_jobs 这类诊断字段（列表里的 job_id/error）不能判失败——误报会让巡检噪声化。"""
    result = {'status': 'fresh', 'failed_jobs': [{'job_id': 'chip_distribution', 'error': 'x'}]}
    assert find_result_failure(result) is None


def test_classify_still_used_for_single_level():
    assert classify_job_result({'success': False}) is not None
    assert classify_job_result({'status': 'error'}) is not None


# ---------------------------------------------------------------------------
# ② SchedulerService.run_task（手动触发 / 调度循环路径）
# ---------------------------------------------------------------------------

class _FakeRepo:
    def __init__(self, task):
        self._task = task
        self.completed = []

    def get_task(self, task_id):
        return self._task

    def list_runs(self, task_id=None, limit=50, offset=0, statuses=None, date_filter=None):
        return []

    def create_run(self, task_id):
        return 4242

    def complete_run(self, run_id, success=True, result=None, error=None):
        self.completed.append({'run_id': run_id, 'success': success, 'error': error})
        return True


def _service_with(repo):
    from infrastructure.scheduler.scheduler import SchedulerService
    return SchedulerService(repo=repo)


def test_run_task_marks_failed_on_inner_failure():
    repo = _FakeRepo({'id': 999, 'name': 't', 'command': 'fake_cmd', 'params': {}, 'is_enabled': True})
    svc = _service_with(repo)
    svc._execute_command = lambda command, params: {'success': False, 'error': 'inner boom'}

    out = svc.run_task(999)

    assert out['status'] == 'failed'
    assert repo.completed[-1]['success'] is False
    assert 'inner boom' in (repo.completed[-1]['error'] or '')


def test_run_task_marks_success_for_clean_result():
    repo = _FakeRepo({'id': 999, 'name': 't', 'command': 'fake_cmd', 'params': {}, 'is_enabled': True})
    svc = _service_with(repo)
    svc._execute_command = lambda command, params: {'status': 'success', 'computed': 3}

    out = svc.run_task(999)

    assert out['status'] == 'success'
    assert repo.completed[-1]['success'] is True


def test_run_task_marks_failed_on_nested_failure():
    repo = _FakeRepo({'id': 999, 'name': 't', 'command': 'fake_cmd', 'params': {}, 'is_enabled': True})
    svc = _service_with(repo)
    svc._execute_command = lambda command, params: {'kline_sync': {'status': 'error', 'error': 'nested boom'}}

    out = svc.run_task(999)

    assert out['status'] == 'failed' and 'nested boom' in out['error']


# ---------------------------------------------------------------------------
# ③ 进程内宿主（daily_jobs_bootstrap）
# ---------------------------------------------------------------------------

def test_inprocess_host_marks_failed_on_inner_failure(monkeypatch):
    from adapters.inbound.fastapi_app import daily_jobs_bootstrap as host

    marks = []
    monkeypatch.setattr(host, '_mark_running', lambda *a, **k: None)
    monkeypatch.setattr(host, '_mark_done',
                        lambda job_id, run_date, status, **kw: marks.append((status, kw)))
    monkeypatch.setattr(host, '_send_feishu', lambda *a, **k: True)

    job = host.JobDef('fake_job', dtime(0, 0), (0, 1, 2, 3, 4, 5, 6),
                      lambda: {'kline_sync': {'status': 'error', 'error': 'nested boom'}},
                      '测试任务')
    host._run_job(job, '2026-09-13')

    assert marks and marks[0][0] == 'failed', marks
    assert 'nested boom' in str(marks[0][1].get('error'))


def test_inprocess_host_marks_success_for_clean_result(monkeypatch):
    from adapters.inbound.fastapi_app import daily_jobs_bootstrap as host

    marks = []
    monkeypatch.setattr(host, '_mark_running', lambda *a, **k: None)
    monkeypatch.setattr(host, '_mark_done',
                        lambda job_id, run_date, status, **kw: marks.append((status, kw)))
    monkeypatch.setattr(host, '_send_feishu', lambda *a, **k: True)

    job = host.JobDef('fake_job', dtime(0, 0), (0, 1, 2, 3, 4, 5, 6),
                      lambda: {'symbols_updated': 10}, '测试任务')
    host._run_job(job, '2026-09-13')

    assert marks and marks[0][0] == 'success', marks


class _RecordingRepo:
    """记录调用的假仓储（_reap_orphan_runs 用）。

    2026-09-14（w-32314d00，REQ-24e15d B4-c4）：原实现打桩的是
    infrastructure...engine.get_engine（假引擎记 SQL 文本）。孤儿判死已收口到
    JobRunRepository（list_orphan_runs / mark_orphans_failed），不再有 SQL 经过 engine，
    打桩点随之失效。接缝变了，打桩层跟着换 —— **测试要保护的行为一条没变**：
      ① 有孤儿 running 行时返回条数、并把它们判死；② 无孤儿时不发 UPDATE（no-op）。
    """

    def __init__(self, rows):
        self.rows = rows
        self.calls = []          # [(方法名, 参数), ...]

    def list_orphan_runs(self, cutoff):
        self.calls.append(('list_orphan_runs', cutoff))
        return list(self.rows)

    def mark_orphans_failed(self, cutoff):
        self.calls.append(('mark_orphans_failed', cutoff))
        return len(self.rows)


def test_orphan_running_rows_are_reaped(monkeypatch):
    """进程重启后遗留的 running 行必须判死，否则永久隐形（既不被重跑也不被告警）。"""
    from adapters.inbound.fastapi_app import daily_jobs_bootstrap as host
    from adapters.outbound.repositories.job_run_repository import JobRunRepository

    repo = _RecordingRepo(rows=[('financial_statements', '2026-09-12')])
    monkeypatch.setattr(JobRunRepository, '__new__', lambda cls, *a, **k: repo, raising=True)

    n = host._reap_orphan_runs(now=datetime(2026, 9, 13, 11, 40))

    assert n == 1
    assert [c[0] for c in repo.calls] == ['list_orphan_runs', 'mark_orphans_failed'], repo.calls
    assert repo.calls[0][1] == datetime(2026, 9, 13, 11, 35)
    assert repo.calls[1][1] == datetime(2026, 9, 13, 11, 35)


def test_orphan_mark_failed_sets_status_failed_and_keeps_error():
    """判死的 SQL 语义（已收口到仓储）：status 置 failed、finished_at 落库、
    error 用 COALESCE 保留原有原因，不覆盖已有错误。断言的是**编译后的 SQL**。

    这是从旧 test_orphan_running_rows_are_reaped 里拆出来的一条：原用例断言假引擎收到的
    SQL 文本，接缝搬到仓储后，等价且更精确的断言是在仓储层编译语句看它到底写了什么。
    """
    from datetime import datetime as _dt

    from sqlalchemy import update, func
    from sqlalchemy.dialects import postgresql

    from infrastructure.persistence.orm.models import InProcessJobRun

    cutoff = _dt(2026, 9, 13, 11, 35)
    stmt = (
        update(InProcessJobRun)
        .where(InProcessJobRun.status == 'running')
        .where(InProcessJobRun.started_at < cutoff)
        .values(
            status='failed',
            finished_at=func.now(),
            error=func.coalesce(
                InProcessJobRun.error,
                '宿主重启导致中断（孤儿 running 行，进程已不在）',
            ),
        )
    )
    compiled = stmt.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    # status 是绑定参数，断言要落在参数值上（不是拼进 SQL 的字面量）
    assert compiled.params.get('status') == 'failed', compiled.params
    assert 'finished_at=now()' in sql.replace('finished_at = ', 'finished_at='), sql
    assert 'coalesce(quant.inprocess_job_runs.error' in sql.lower(), sql


def test_orphan_reap_logs_single_warning_not_error():
    """孤儿判死是「已被发现并收尾」的既成事实，用一条聚合 warning 输出。

    2026-09-13（事件 c0e69791）：原来按行打 error → 每次实例重启都在 error_events 里生成
    一张需要人工闭环的卡片，把「已经处理好的事」变成待办噪声。事故记录本身落在
    quant.inprocess_job_runs（status=failed）+ _job_failure_watch 巡检，足够可追溯。
    """
    from adapters.inbound.fastapi_app import daily_jobs_bootstrap as host

    src = Path(host.__file__).read_text(encoding='utf-8')
    body = src[src.index('def _reap_orphan_runs'):src.index('def _jobs_loop')]
    assert 'logger.warning(' in body, '孤儿判死必须用 warning'
    assert 'logger.error("inprocess_job_orphan_reaped"' not in body, '不得再按行打 error'
    assert 'jobs=' in body, '聚合警告需带 job@date 明细'


def test_orphan_reap_is_noop_when_nothing_running(monkeypatch):
    from adapters.inbound.fastapi_app import daily_jobs_bootstrap as host
    from adapters.outbound.repositories.job_run_repository import JobRunRepository

    repo = _RecordingRepo(rows=[])
    monkeypatch.setattr(JobRunRepository, '__new__', lambda cls, *a, **k: repo, raising=True)

    assert host._reap_orphan_runs(now=datetime(2026, 9, 13, 11, 40)) == 0
    assert [c[0] for c in repo.calls] == ['list_orphan_runs'], repo.calls  # 只查，不更新


# ---------------------------------------------------------------------------
# ④ 财报时效性：告警未送达 → 抛异常（不再"success 但功能失败"）
# ---------------------------------------------------------------------------

def test_timeliness_job_raises_when_alert_not_delivered():
    from infrastructure.jobs import financial_timeliness_check_job as tj

    assert hasattr(tj, 'AlertDeliveryError')
    assert issubclass(tj.AlertDeliveryError, RuntimeError)
