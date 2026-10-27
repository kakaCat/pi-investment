"""任务摘要端点契约锁（RFC 017 P1，2026-10-27，w-7e3880c6）

锁三件事：
  ① 状态归一化 _resolve_last_status 与 holdings 客户端 resolveLastRun() 等价
     （外层 success + 内层 failed 的假成功必须被纠正，来源可追踪）；
  ② 常量查询：无论页内多少任务，latest-run 与 today 聚合各只查一次（N+1 修复）；
  ③ 响应不带 lastRun.payload/result——大字段只留详情端点（13.68 MB 事故修复）。
"""
from typing import Any, Dict, List

import pytest

from adapters.inbound.fastapi_app.routes import scheduler_async


# --------------------------- ① 状态归一化 ---------------------------

class TestResolveLastStatus:
    def test_no_run(self):
        assert scheduler_async._resolve_last_status(None) == ('', 'none', '')

    def test_never_ran_empty_dict(self):
        assert scheduler_async._resolve_last_status({}) == ('', 'none', '')

    def test_outer_success(self):
        run = {'status': 'success', 'error': None, 'result': None}
        assert scheduler_async._resolve_last_status(run) == ('success', 'scheduler', '')

    def test_outer_completed_normalized_to_success(self):
        run = {'status': 'completed', 'error': None}
        assert scheduler_async._resolve_last_status(run) == ('success', 'scheduler', '')

    def test_outer_failed_with_error(self):
        run = {'status': 'failed', 'error': 'boom', 'result': None}
        assert scheduler_async._resolve_last_status(run) == ('failed', 'scheduler', 'boom')

    def test_inner_single_layer_wins_over_outer(self):
        """外层 success + 内层 details failed = 假成功，必须纠正为 failed（2026-09 实证陷阱）。"""
        run = {'status': 'success', 'error': None,
               'result': {'details': {'status': 'failed', 'error': 'engine down'}}}
        assert scheduler_async._resolve_last_status(run) == ('failed', 'inner_result', 'engine down')

    def test_inner_deep_layer_priority(self):
        """details.details（引擎双层）优先于 details（单层）。"""
        run = {'status': 'success', 'error': None,
               'result': {'details': {'status': 'failed', 'error': 'shallow',
                                      'details': {'status': 'skipped', 'error': 'deep'}}}}
        assert scheduler_async._resolve_last_status(run) == ('skipped', 'inner_result', 'deep')

    def test_inner_completed_normalized(self):
        run = {'status': 'success', 'error': None,
               'result': {'details': {'details': {'status': 'completed'}}}}
        assert scheduler_async._resolve_last_status(run) == ('success', 'inner_result', '')

    def test_inner_message_fallback_for_error(self):
        run = {'status': 'success', 'error': None,
               'result': {'details': {'status': 'failed', 'message': 'm-msg'}}}
        assert scheduler_async._resolve_last_status(run) == ('failed', 'inner_result', 'm-msg')

    def test_result_not_dict_treated_as_outer(self):
        """result 是字符串/None 等异常形状时不得炸——回退外层状态。"""
        run = {'status': 'success', 'error': None, 'result': 'plain-text-result'}
        assert scheduler_async._resolve_last_status(run) == ('success', 'scheduler', '')


# --------------------------- ②③ summary 端点 ---------------------------

def _fake_task(tid: int, name: str) -> Dict[str, Any]:
    return {'id': tid, 'name': name, 'is_enabled': True, 'cron_expression': '0 9 * * 1-5',
            'command': 'cmd_' + name, 'description': '', 'params': {},
            'next_run_at': '2026-10-28T09:00:00+08:00'}


class _RecordingRepo:
    """记录调用次数的桩 repository：锁「常量查询」（每方法恰一次，不随任务数增长）。"""

    def __init__(self, latest: Dict[int, dict], today: Dict[int, dict]):
        self._latest = latest
        self._today = today
        self.latest_calls = 0
        self.today_calls = 0

    def get_latest_runs_per_task(self, task_ids: List[int]) -> Dict[int, dict]:
        self.latest_calls += 1
        return self._latest

    def count_today_runs_per_task(self, task_ids: List[int], today: str) -> Dict[int, dict]:
        self.today_calls += 1
        return self._today


def _run(status: str, result=None, error=None, started: str = '2026-10-27T09:00:00+08:00') -> dict:
    return {'status': status, 'result': result, 'error': error, 'started_at': started}


def test_summary_contract(monkeypatch):
    tasks = [_fake_task(i, f'task_{i}') for i in range(1, 6)]  # 5 个任务
    monkeypatch.setattr(scheduler_async, '_list_visible_tasks', lambda limit, offset: (tasks, 5))

    latest = {
        1: _run('success', result={'details': {'details': {'status': 'failed', 'error': 'inner-boom'}}}),
        2: _run('failed', error='outer-boom'),
        3: _run('success'),
        # 4 无运行记录；5 外层 success 内层 skipped
        5: _run('success', result={'details': {'status': 'skipped'}}),
    }
    today = {1: {'triggered': 2, 'success': 1}, 3: {'triggered': 1, 'success': 1}}
    repo = _RecordingRepo(latest, today)
    monkeypatch.setattr(
        'adapters.outbound.repositories.scheduler_repository.SchedulerRepository',
        lambda: repo,
    )

    resp = scheduler_async.list_scheduler_tasks_summary(page=1, pageSize=100)
    body = dict(resp) if not hasattr(resp, 'body') else resp  # handle_api_error 原样返回 dict

    assert body['success'] is True
    assert body['contract_version'] == 2
    assert body['count'] == 5
    assert len(body['tasks']) == 5

    # 常量查询：5 个任务各方法仍只调一次（旧实现是 5 次 list_runs + 本地过滤）
    assert repo.latest_calls == 1, 'get_latest_runs_per_task 必须只查一次（N+1 修复）'
    assert repo.today_calls == 1, 'count_today_runs_per_task 必须只查一次（N+1 修复）'

    by_id = {t['id']: t for t in body['tasks']}
    # 假成功纠正：外层 success + 内层 failed → failed（服务端归一化，消费方不再解 payload）
    assert by_id['1']['lastStatus'] == 'failed'
    assert by_id['1']['lastStatusSource'] == 'inner_result'
    assert by_id['1']['lastError'] == 'inner-boom'
    # 外层失败直传
    assert by_id['2']['lastStatus'] == 'failed'
    assert by_id['2']['lastStatusSource'] == 'scheduler'
    assert by_id['2']['lastError'] == 'outer-boom'
    # 从未运行
    assert by_id['4']['lastStatus'] == ''
    assert by_id['4']['lastStatusSource'] == 'none'
    assert by_id['4']['lastAt'] is None
    # 当日统计
    assert by_id['1']['todayTriggered'] == 2
    assert by_id['1']['todaySuccess'] == 1
    assert by_id['3']['todaySuccess'] == 1

    # ③ 大字段剥离：响应中任何任务不得携带 payload/result/lastRun
    import json as _json
    serialized = _json.dumps(body, default=str)
    assert 'payload' not in serialized, 'summary 响应不得含 lastRun.payload（13.68MB 事故修复）'
    assert 'inner-boom' in serialized  # lastError 截断保留（2KB 上限内）


def test_summary_error_truncation(monkeypatch):
    tasks = [_fake_task(1, 'big_err')]
    monkeypatch.setattr(scheduler_async, '_list_visible_tasks', lambda limit, offset: (tasks, 1))
    huge = 'x' * 5000
    repo = _RecordingRepo({1: _run('failed', error=huge)}, {})
    monkeypatch.setattr(
        'adapters.outbound.repositories.scheduler_repository.SchedulerRepository',
        lambda: repo,
    )
    body = scheduler_async.list_scheduler_tasks_summary(page=1, pageSize=100)
    err = body['tasks'][0]['lastError']
    assert len(err) == 2048, f'lastError 必须截断到 2KB，实际 {len(err)}'
