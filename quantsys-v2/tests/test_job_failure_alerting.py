"""调度失败的飞书兜底与告警覆盖面（REQ-261004154902-a7cd · t-322d78 · FR-2/FR-8/FR-9）。

三条被取证的丢消息路径：
1. APScheduler 路径的任务失败只调 `agent_os_reporter.report_event` → 出口是**已下线的**
   Agent OS `localhost:8080`（日志里 `agent-os ingest POST failed (dropped)` 1696 次）；
2. `_job_failure_watch` 只扫 JOBS（9 个 DailyJobs），**不含** `quant.scheduler_tasks`
   里那 11 张卡 → task 251 连续 21 次失败没有任何人被告知；
3. `_summarize_result` 的键列表里没有 stale/未覆盖 之类 → 「一只都没更新」不进消息正文，
   `evening_pipeline` 的 K 线同步「成功 0 只 / 未覆盖 5271 只」却记 success。

本文件是故障注入测试：**不写库、不发通知**（全部打桩）。打桩点一律取
「被调函数所在模块」（CLAUDE.md 通知测试铁律），不取转发壳。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from urllib.error import URLError

import pytest

import adapters.inbound.fastapi_app.daily_jobs.alerting as alerting
from application.observability import failure_sink
from infrastructure.error_reporting import agent_os_reporter as rep
from infrastructure.scheduler.job_executor import find_result_failure


# ---------------------------------------------------------------------------
# 公共夹具
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_send_failure_state():
    """清空进程内留痕（降级节流表 / drop 限频表 / 告警投递失败清单），避免用例间串扰。"""
    with rep._fallback_lock:
        rep._fallback_recent.clear()
    with rep._drop_log_lock:
        rep._drop_log_recent.clear()
    alerting.drain_alert_send_failures()
    yield
    with rep._fallback_lock:
        rep._fallback_recent.clear()
    with rep._drop_log_lock:
        rep._drop_log_recent.clear()
    alerting.drain_alert_send_failures()


def _payload(**overrides) -> dict:
    """一条结构化上报 payload（形如 job_executor 的 report_event 入队体）。"""
    payload = {
        "source": "v2",
        "msg": "[scheduler_task] signal_monitor_realtime inner failed: boom",
        "task_id": "251",
        "task_name": "signal_monitor_realtime",
        "metadata": {"channel": "structured_reporter",
                     "logger": "infrastructure.scheduler.job_executor"},
        "fingerprint": "fp-t322d78",
    }
    payload.update(overrides)
    return payload


def _post_unreachable(_payload: dict):
    """模拟 8080 不可达（urllib 抛 URLError，与真实 dropped 路径一致）。"""
    raise URLError("connection refused")


# ---------------------------------------------------------------------------
# ① 8080 不可达 → 降级到 NotificationFacade（经 failure_sink.report_failure）
#
# 分流口径（父 agent 裁决 2026-10-05）：AGENT_OS_ENABLED=false 是**既定架构**
# （ADR-004 业务调度归 v2）→ 只 warning + 计数，不外发；=true 却连不上（真故障）
# → error + 保留一次降级外发。故下列用例显式把开关置 true。
# ---------------------------------------------------------------------------

def test_ingest_unreachable_degrades_to_notification(monkeypatch):
    """断言被打桩的 report_failure 被调用，且参数里带 task 名（开关为 true=真故障）。"""
    calls = []

    def fake_report_failure(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setenv("AGENT_OS_ENABLED", "true")
    monkeypatch.setattr(failure_sink, "report_failure", fake_report_failure)
    monkeypatch.setattr(rep, "_post", _post_unreachable)

    assert rep._handle_item(_payload()) is False, "8080 不可达时上报不可能送达"

    assert calls, "8080 不可达必须降级到 NotificationFacade（此前只在日志里 dropped）"
    kw = calls[0]
    assert kw["source"] == rep._FALLBACK_SOURCE
    assert kw["reason"] == rep._FALLBACK_REASON
    assert kw["severity"] == "high", "失败类上报按 high（防刷屏靠节流，不靠降级）"
    assert kw["context"]["task_name"] == "signal_monitor_realtime"
    assert kw["context"]["task_id"] == "251"
    assert rep.fallback_stats()["degraded_total"] >= 1, "降级必须留痕"


def test_agent_os_expected_off_does_not_alert(monkeypatch):
    """开关 false（既定架构）时**不外发**：否则同一次失败两张卡片（假警报）。"""
    calls = []
    degraded_before = rep.fallback_stats()["degraded_total"]
    monkeypatch.setenv("AGENT_OS_ENABLED", "false")
    monkeypatch.setattr(failure_sink, "report_failure",
                        lambda **kw: (calls.append(kw), True)[1])
    monkeypatch.setattr(rep, "_post", _post_unreachable)

    assert rep._handle_item(_payload()) is False

    assert calls == [], "Agent OS 按架构关闭时不得外发（可见性由 failure_sink 直接外发承担）"
    assert rep.fallback_stats()["degraded_total"] == degraded_before, "开关 false 时零降级"
    assert rep.drop_stats()["dropped_total"] >= 1, "丢弃必须计数留痕（便于排查'上报全丢'）"


def test_drop_log_is_rate_limited_per_event_and_task(monkeypatch):
    """drop 日志限频：同一 (event, task) 键 5 分钟内只记一条，计数照加。"""
    class _FakeLog:
        def __init__(self):
            self.warnings = []
            self.errors = []

        def warning(self, msg, *args):
            self.warnings.append((msg, args))

        def error(self, msg, *args):
            self.errors.append((msg, args))

    fake_log = _FakeLog()
    monkeypatch.setenv("AGENT_OS_ENABLED", "false")
    monkeypatch.setattr(rep, "log", fake_log)
    monkeypatch.setattr(rep, "_post", _post_unreachable)

    rep._handle_item(_payload())
    rep._handle_item(_payload())          # 同键 → 不再记
    rep._handle_item(_payload(fingerprint="fp-other", task_name="chan_scan_daily"))

    assert len(fake_log.warnings) == 2, f"同键只记一条，实测 {fake_log.warnings}"
    assert not fake_log.errors, "开关 false 是既定状态 → warning 而非 error"
    assert rep.drop_stats()["dropped_total"] >= 3, "限频只影响日志，计数必须照加"


def test_drop_log_level_follows_switch(monkeypatch):
    """开关 true 连不上（真故障）→ error；false（既定关闭）→ warning。"""
    class _FakeLog:
        def __init__(self):
            self.warnings = []
            self.errors = []

        def warning(self, msg, *args):
            self.warnings.append((msg, args))

        def error(self, msg, *args):
            self.errors.append((msg, args))

    fake_log = _FakeLog()
    monkeypatch.setattr(rep, "log", fake_log)
    monkeypatch.setattr(rep, "_post", _post_unreachable)
    # 开关 true 会真的降级外发 → 必须桩掉通道（notify-guard 会判"未声明外发"）
    monkeypatch.setattr(failure_sink, "report_failure", lambda **kw: False)

    monkeypatch.setenv("AGENT_OS_ENABLED", "true")
    rep._handle_item(_payload())
    with rep._drop_log_lock:
        rep._drop_log_recent.clear()

    monkeypatch.setenv("AGENT_OS_ENABLED", "false")
    rep._handle_item(_payload())

    assert len(fake_log.errors) == 1 and "dropped" in fake_log.errors[0][0]
    assert len(fake_log.warnings) >= 1


def test_degradation_is_throttled_per_fingerprint(monkeypatch):
    """1696 次 dropped 不许变成 1696 条飞书：同指纹 10 分钟只降级一次。"""
    calls = []
    monkeypatch.setenv("AGENT_OS_ENABLED", "true")
    monkeypatch.setattr(failure_sink, "report_failure",
                        lambda **kw: (calls.append(kw), True)[1])
    monkeypatch.setattr(rep, "_post", _post_unreachable)

    rep._handle_item(_payload())
    rep._handle_item(_payload())

    assert len(calls) == 1, f"同指纹只应降级一次，实测 {len(calls)} 次"


def test_failure_sink_logs_are_not_re_degraded(monkeypatch):
    """递归护栏：降级动作自身（failure_sink 的 ERROR 日志）不得再触发降级。"""
    calls = []
    monkeypatch.setenv("AGENT_OS_ENABLED", "true")
    monkeypatch.setattr(failure_sink, "report_failure",
                        lambda **kw: (calls.append(kw), True)[1])
    monkeypatch.setattr(rep, "_post", _post_unreachable)

    rep._handle_item(_payload())
    assert len(calls) == 1

    sink_log = _payload(
        msg="failure_sink: source=agent_os_reporter.ingest reason=agent_os_unreachable",
        metadata={"logger": "application.observability.failure_sink", "channel": "log_handler"},
        fingerprint="fp-sink-log", task_id=None, task_name=None,
    )
    rep._handle_item(sink_log)

    assert len(calls) == 1, "降级产生的日志不得再次降级（否则 8080 长期不可达会自我放大）"


def test_degradation_reaches_injected_channel(monkeypatch):
    """端到端：真 report_failure → 注入通道（等价 NotificationFacade）收到卡片。"""
    sent = []
    monkeypatch.setenv("AGENT_OS_ENABLED", "true")
    monkeypatch.setattr(rep, "_post", _post_unreachable)
    failure_sink.install_failure_alert_sink(
        lambda title, content, urgency: (sent.append((title, content, urgency)), True)[1])
    try:
        rep._handle_item(_payload())
    finally:
        failure_sink.install_failure_alert_sink(None)   # 恢复默认，不留全局状态

    assert sent, "降级必须真的到通道（不是只写日志）"
    assert "agent_os_reporter" in sent[0][0]
    assert sent[0][2] == "high"
    assert "signal_monitor_realtime" in sent[0][1]


# ---------------------------------------------------------------------------
# ② job_executor 两条失败分支都补第二条线（source=scheduler.job_executor）
# ---------------------------------------------------------------------------

class _FakeSession:
    def rollback(self):
        pass

    def close(self):
        pass


class _FakeSchedulerRepo:
    def __init__(self, session=None):
        self.completed = []

    def get_task(self, task_id):
        return {'id': task_id, 'name': 'signal_scan_daily', 'command': 'signal_generate',
                'params': {}, 'is_enabled': True}

    def list_runs(self, **kwargs):
        return []

    def create_run(self, task_id):
        return 4242

    def complete_run(self, **kwargs):
        self.completed.append(kwargs)


def _patch_executor(monkeypatch, repo, *, result=None, raises=None):
    """把 `_execute_scheduled_job_impl` 的取库/执行替换成替身（不碰 DB、不跑真 job）。"""
    import adapters.outbound.repositories.scheduler_repository as sr
    import infrastructure.persistence.orm as orm
    from infrastructure.scheduler import job_executor as je

    monkeypatch.setattr(sr, 'SchedulerRepository', lambda session=None: repo)
    monkeypatch.setattr(orm, 'get_session', lambda: _FakeSession())
    monkeypatch.setattr(orm, 'close_session', lambda: None)

    def fake_execute(command, params):
        if raises is not None:
            raise raises
        return result

    monkeypatch.setattr(je, '_execute_command', fake_execute)
    return je


def test_job_executor_inner_failure_reports_via_sink(monkeypatch):
    """内层失败（handler 返回失败态、不抛异常）：除 agent_os_reporter 外必须也走 FailureSink。"""
    calls = []
    monkeypatch.setattr(failure_sink, "report_failure",
                        lambda **kw: (calls.append(kw), True)[1])
    repo = _FakeSchedulerRepo()
    je = _patch_executor(monkeypatch, repo, result={'success': False, 'error': 'inner boom'})

    je._execute_scheduled_job_impl(251)

    assert repo.completed and repo.completed[0]['success'] is False
    assert calls, "内层失败必须补第二条线（8080 死时 report_event 只留一行 dropped）"
    assert calls[0]['source'] == je.FAILURE_SOURCE == 'scheduler.job_executor'
    assert calls[0]['reason'] == je.FAILURE_REASON_INNER
    assert calls[0]['severity'] == 'high'
    assert calls[0]['context']['task_name'] == 'signal_scan_daily'
    assert calls[0]['context']['task_id'] == 251
    assert calls[0]['context']['run_id'] == '4242'


def test_job_executor_exception_reports_via_sink(monkeypatch):
    """异常分支（job 抛异常）同样必须走 FailureSink。"""
    calls = []
    monkeypatch.setattr(failure_sink, "report_failure",
                        lambda **kw: (calls.append(kw), True)[1])
    repo = _FakeSchedulerRepo()
    je = _patch_executor(monkeypatch, repo, raises=RuntimeError('boom at import'))

    je._execute_scheduled_job_impl(251)

    assert repo.completed and repo.completed[0]['success'] is False
    assert calls and calls[0]['reason'] == je.FAILURE_REASON_EXCEPTION
    assert 'boom at import' in calls[0]['error']
    assert calls[0]['severity'] == 'high'


# ---------------------------------------------------------------------------
# ③ 失败巡检覆盖面：JOBS + quant.scheduler_tasks 启用任务 + 告警投递失败
# ---------------------------------------------------------------------------

class _FakeSchedulerTasksRepo:
    """`quant.scheduler_tasks` / `quant.scheduler_runs` 只读替身。"""

    def __init__(self, session=None):
        pass

    def list_tasks(self, enabled_only=False):
        return [
            {'id': 251, 'name': 'signal_monitor_realtime', 'is_enabled': True},
            {'id': 260, 'name': 'chan_scan_daily', 'is_enabled': True},
        ]

    def list_runs(self, **kwargs):
        fresh = datetime.now() - timedelta(days=1)
        stale = datetime.now() - timedelta(days=30)
        return [
            {'task_id': 251, 'status': 'failed', 'started_at': fresh,
             'error': 'AttributeError: boom（连续 21 次失败无人知）'},
            {'task_id': 999, 'status': 'failed', 'started_at': fresh,
             'error': '已退役任务的历史残留，不该告警'},
            {'task_id': 260, 'status': 'failed', 'started_at': stale,
             'error': '超出 3 天窗口，不该告警'},
        ]


def _patch_watch_repos(monkeypatch, seen):
    import adapters.outbound.repositories.job_run_repository as jrr
    import adapters.outbound.repositories.scheduler_repository as sr

    class _FakeRunRepo:
        def list_recent_failures(self, job_ids, days=3):
            seen['ids'] = list(job_ids)
            return [{'job_id': 'chip_distribution', 'run_date': '2026-10-04', 'error': 'x'}]

    monkeypatch.setattr(sr, 'SchedulerRepository', _FakeSchedulerTasksRepo)
    monkeypatch.setattr(jrr, 'JobRunRepository', lambda: _FakeRunRepo())


def test_job_failure_watch_covers_scheduler_tasks(monkeypatch):
    """候选集合必须含 scheduler_tasks 的启用任务名，且其 failed run 要进告警清单。"""
    seen = {}
    _patch_watch_repos(monkeypatch, seen)

    out = alerting._job_failure_watch(engine=None)

    assert 'signal_monitor_realtime' in seen['ids'], \
        f"候选集合必须扩到 scheduler_tasks 启用任务，实测={seen['ids']}"
    assert 'chan_scan_daily' in seen['ids']
    assert 'chip_distribution' in seen['ids'], 'JOBS 原有覆盖不得丢'

    names = [f['job_id'] for f in out]
    assert 'signal_monitor_realtime' in names, '库表任务的 failed run 必须能被巡到'
    assert 'chip_distribution' in names
    hit = [f for f in out if f['job_id'] == 'signal_monitor_realtime'][0]
    assert hit['source'] == 'scheduler_runs'
    assert '连续 21 次失败' in hit['error']
    assert not any('退役任务' in str(f.get('error')) for f in out), '未启用任务的历史残留不告警'
    assert 'chan_scan_daily' not in names, '超出 3 天窗口的失败不告警'


def test_alert_delivery_failure_surfaces_in_watch_once(monkeypatch):
    """「告警自己没发出去」必须交回调用方，且同一条只报一次（消费式）。"""
    seen = {}
    _patch_watch_repos(monkeypatch, seen)

    alerting._record_alert_send_failure('🚨 数据新鲜度告警', '通道返回 False（未送达）')
    first = [f for f in alerting._job_failure_watch(engine=None)
             if f['job_id'] == alerting.ALERT_DELIVERY_JOB_ID]
    assert first, '告警投递失败必须进巡检清单（否则"发不出告警"永远没人知道）'
    assert '未送达' in first[0]['error']

    second = [f for f in alerting._job_failure_watch(engine=None)
              if f['job_id'] == alerting.ALERT_DELIVERY_JOB_ID]
    assert second == [], '消费式：同一条投递失败只报一次，避免自我放大'


def test_send_feishu_false_return_is_consumed(monkeypatch):
    """`_send_feishu` 返回 False 必须被消费（此前 6 处调用方全不看返回值）。"""
    import application.notification as notif

    class _FakeFacade:
        def send_card(self, **kwargs):
            return False

    monkeypatch.setattr(notif, 'get_notification_facade', lambda: _FakeFacade())

    assert alerting._send_feishu('🚨 数据新鲜度告警\n缺 5271 只') is False
    failures = alerting.drain_alert_send_failures()
    assert failures and failures[0]['job_id'] == alerting.ALERT_DELIVERY_JOB_ID
    assert '未送达' in failures[0]['error']


def test_send_feishu_exception_is_consumed(monkeypatch):
    """通道抛异常同样留痕（且不得把异常抛回任务流）。"""
    import application.notification as notif

    def _boom():
        raise RuntimeError('webhook 连接被拒')

    monkeypatch.setattr(notif, 'get_notification_facade', _boom)

    assert alerting._send_feishu('🚨 数据新鲜度告警\n正文') is False
    failures = alerting.drain_alert_send_failures()
    assert failures and 'webhook 连接被拒' in failures[0]['error']


# ---------------------------------------------------------------------------
# ④ 「没做成的动作」判定与进正文
# ---------------------------------------------------------------------------

#: evening_pipeline K 线同步的真实返回形态（infrastructure/jobs/kline_update_job.py:236-249）
EVE_KLINE = {
    'action': 'kline_update', 'status': 'success', 'total': 5281, 'success': 0,
    'failed': 0, 'skipped': 0, 'stale': 5271,
    'message': 'K线更新完成: 成功0只, 失败0只, 跳过0只, 未覆盖基准日5271只',
}


def test_evening_pipeline_noop_gap_is_failure():
    """success=0 + 未覆盖 5271 → 失败（此前 status='success' 直接短路成成功）。"""
    err = find_result_failure(EVE_KLINE)
    assert err is not None, '「成功 0 只 / 未覆盖 5271 只」不得再记 success'
    assert 'stale=5271' in err

    nested = find_result_failure({'kline_sync': EVE_KLINE})
    assert nested is not None and nested.startswith('kline_sync: ')


def test_noop_without_gap_is_not_a_failure():
    """宁少报不误报：没有缺口（本来就没活干）或已做成了事，都不判失败。"""
    assert find_result_failure({'status': 'success', 'updated': 0}) is None
    assert find_result_failure({'updated': 0, 'skipped': True}) is None
    assert find_result_failure({'symbols_updated': 10, 'stale': 5}) is None
    assert find_result_failure({'status': 'stale', 'stale': ['chip']}) is None, \
        '诊断字段（列表）不是缺口计数，不得误判'
    # 既有口径锁：显式成功态不得被新规则带偏
    assert find_result_failure({'success': True, 'symbols': 10}) is None
    assert find_result_failure({'status': 'success', 'computed': 5}) is None


def test_chinese_uncovered_key_is_a_gap():
    assert find_result_failure({'status': 'success', 'success': 0, '未覆盖': 5271}) is not None


def test_summarize_result_surfaces_unfinished_actions():
    """没做成的动作（停用/跳过/未覆盖）必须进消息正文。"""
    text = alerting._summarize_result(
        {'status': 'success', 'success': 0, 'stale': 5271,
         'auto_disabled': 3, 'missed': 2})

    assert 'stale=5271' in text
    assert 'auto_disabled=3' in text
    assert 'missed=2' in text


def test_summarize_result_surfaces_nested_unfinished_actions():
    text = alerting._summarize_result({'kline_sync': {'status': 'success', 'updated': 0,
                                                      'stale': 5271}})
    assert 'kline_sync[' in text and 'stale=5271' in text
