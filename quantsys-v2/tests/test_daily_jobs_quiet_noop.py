"""每日任务空结果不发飞书 · 回归锁（REQ-261006165125-23a9，FR-1~FR-8）

对应用例编号见 docs/requirements/REQ-261006165125-23a9/design/test-cases.md §2（T-1 ~ T-16）。

⚠️ **打桩点铁律**（`CLAUDE.md` 通知守卫一节 / REQ-261003150739-b98d 的教训）：
`_run_job` 读的是 **runtime 模块自己的全局名**（runtime.py 用
`from ...alerting import _send_feishu` 取值导入），所以桩**必须**打在
`daily_jobs.runtime._send_feishu` / `_mark_running` / `_mark_done` 上——
打在 `alerting._send_feishu` 或 `daily_jobs_bootstrap._send_feishu` 上会**名字在、不生效**，
测试会绿着把真消息发出去（历史上正是这样发出过假卡片）。

本文件不碰库、不碰网络：台账写入全部换成桩，通知通道全部换成捕获列表。
"""
import threading
import time
from datetime import time as dtime

import pytest

from adapters.inbound.fastapi_app.daily_jobs import notify_policy as np
from adapters.inbound.fastapi_app.daily_jobs import runtime
from adapters.inbound.fastapi_app.daily_jobs.defs import JobDef

JOB_ID = 'event_calendar_check'
JOB_DESC = '事件日历检查：未来2日 pending 高优事件（imp>=2）飞书提醒→标记notified'


class _Capture:
    def __init__(self):
        self.texts = []
        self.marks = []


@pytest.fixture
def sent(monkeypatch):
    """捕获宿主发出的通知文本与台账写入（桩打在 runtime 模块）。"""
    cap = _Capture()
    monkeypatch.setattr(runtime, '_send_feishu',
                        lambda text: (cap.texts.append(text), True)[1])
    monkeypatch.setattr(runtime, '_mark_running', lambda *a, **k: None)
    monkeypatch.setattr(runtime, '_mark_done', lambda *a, **k: cap.marks.append((a, k)))
    # 默认态：两个开关都未设（= 新行为），避免宿主环境变量泄漏进用例
    monkeypatch.delenv(np.ENV_NOTIFY_NOOP, raising=False)
    monkeypatch.delenv(np.ENV_RUNNING_NOTICE_SECONDS, raising=False)
    return cap


def _job(handler, job_id: str = JOB_ID) -> JobDef:
    return JobDef(job_id, dtime(16, 45), (0, 1, 2, 3, 4, 5, 6), handler, JOB_DESC)


def _boom():
    raise RuntimeError('boom')


# ── T-1 / T-2：无事判据（FR-1）───────────────────────────────────────────────

@pytest.mark.parametrize('result, expected', [
    ({'status': 'no_event'}, True),
    ({'status': 'no_op'}, True),
    ({'no_output': True}, True),
    # 反向锁：真值但非 True / 未知取值 / 非 dict 一律**不外发**
    ({'no_output': 1}, False),
    ({'no_output': 'true'}, False),
    ({'status': 'success'}, False),
    ({'status': 'no_event', 'no_output': False}, True),   # status 命中即成立
    ({}, False),
    (None, False),
    ('x', False),
    ([], False),
])
def test_t1_is_no_op_whitelist(result, expected):
    assert np.is_no_op(result) is expected


def test_t2_is_no_op_normalizes_case_and_space():
    assert np.is_no_op({'status': ' NO_EVENT '}) is True
    assert np.is_no_op({'status': 'No_Op'}) is True
    assert np.is_no_op({'status': 'no event'}) is False


# ── T-3 ~ T-5：判据与开关（FR-1 / FR-7）─────────────────────────────────────

def test_t3_should_send_completion_four_branches(monkeypatch):
    monkeypatch.delenv(np.ENV_NOTIFY_NOOP, raising=False)
    assert np.should_send_completion(result={'status': 'no_event'}) is False
    assert np.should_send_completion(result={'updated': 12}) is True
    assert np.should_send_completion(result={'status': 'no_event'}, manual=True) is True
    assert np.should_send_completion(result={'updated': 12}, manual=True) is True
    # 回滚态：无事也发
    monkeypatch.setenv(np.ENV_NOTIFY_NOOP, 'true')
    assert np.should_send_completion(result={'status': 'no_event'}) is True


@pytest.mark.parametrize('raw, expected', [
    (None, False), ('', False), ('0', False), ('false', False), ('nope', False),
    ('1', True), ('true', True), ('TRUE', True), ('yes', True), ('on', True),
])
def test_t4_notify_noop_flag_parsing(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv(np.ENV_NOTIFY_NOOP, raising=False)
    else:
        monkeypatch.setenv(np.ENV_NOTIFY_NOOP, raw)
    assert np.notify_noop_enabled() is expected
    assert np.should_send_start() is expected


@pytest.mark.parametrize('raw, expected', [
    (None, 60.0), ('', 60.0), ('abc', 60.0), ('0', 0.0), ('-1', 0.0), ('30', 30.0),
])
def test_t5_running_notice_seconds_parsing(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv(np.ENV_RUNNING_NOTICE_SECONDS, raising=False)
    else:
        monkeypatch.setenv(np.ENV_RUNNING_NOTICE_SECONDS, raw)
    assert np.running_notice_seconds() == expected


# ── T-6 ~ T-10：宿主行为（FR-2 / FR-3 / FR-4 / FR-6）────────────────────────

def test_t6_no_event_sends_nothing_but_keeps_ledger(sent):
    """无事 = 零消息；台账仍是 success 且 result 原样（FR-2/FR-5）。"""
    payload = {'status': 'no_event', 'pending_in_window': 0, 'notified': 0}
    runtime._run_job(_job(lambda: payload), '2026-10-07')

    assert sent.texts == [], sent.texts
    assert sent.marks and sent.marks[-1][0][2] == 'success'
    assert sent.marks[-1][1].get('result') == payload


def test_t7_output_sends_exactly_one_completion(sent):
    """有产出 → 只发一条完成消息（开始消息已被本需求取消），耗时按秒渲染。"""
    runtime._run_job(_job(lambda: {'updated': 12}), '2026-10-07')

    assert len(sent.texts) == 1, sent.texts
    text = sent.texts[0]
    assert text.startswith(f'✅ 每日任务完成：{JOB_ID}')
    line = [ln for ln in text.split('\n') if ln.startswith('耗时: ')][0]
    assert line.endswith('秒'), line


def test_t8_exception_still_alerts(sent):
    """异常不受静默规则影响（FR-4）。"""
    runtime._run_job(_job(_boom), '2026-10-07')

    assert len(sent.texts) == 1, sent.texts
    assert sent.texts[0].startswith(f'🚨 每日任务失败：{JOB_ID}')
    assert sent.marks[-1][0][2] == 'failed'


def test_t9_inner_failure_wins_over_no_op(sent):
    """无事 + 内层失败 → 以失败为准（FR-4）。"""
    runtime._run_job(_job(lambda: {'status': 'no_event', 'success': False}), '2026-10-07')

    assert len(sent.texts) == 1, sent.texts
    assert sent.texts[0].startswith(f'🚨 每日任务失败：{JOB_ID}')
    assert sent.marks[-1][0][2] == 'failed'


def test_t10_manual_trigger_always_gets_receipt(sent):
    """人工触发必有回执，即使本次无事（FR-6）。"""
    runtime._run_job(_job(lambda: {'status': 'no_event'}), '2026-10-07', manual=True)

    assert len(sent.texts) == 1, sent.texts
    assert sent.texts[0].startswith(f'✅ 每日任务完成（人工触发）：{JOB_ID}')
    assert not any(t.startswith('▶️') for t in sent.texts)


# ── T-11：回滚态（FR-7）─────────────────────────────────────────────────────

def test_t11_legacy_switch_restores_old_behavior(sent, monkeypatch):
    """开关打开 = 旧行为：立即开始 + 完成必发（零产出用 ⚠️ 语气）。"""
    monkeypatch.setenv(np.ENV_NOTIFY_NOOP, 'true')

    runtime._run_job(_job(lambda: {'updated': 1}), '2026-10-07')
    assert len(sent.texts) == 2, sent.texts
    assert sent.texts[0].startswith(f'▶️ 每日任务开始：{JOB_ID}')
    assert sent.texts[1].startswith(f'✅ 每日任务完成：{JOB_ID}')

    sent.texts.clear()
    runtime._run_job(_job(lambda: {'no_output': True, 'computed_ok': 0}), '2026-10-07')
    assert len(sent.texts) == 2, sent.texts
    assert sent.texts[1].startswith(f'⚠️ 每日任务完成（无有效产出）：{JOB_ID}')


# ── T-12 ~ T-15：超阈值提示（FR-3）──────────────────────────────────────────

def test_t12_no_running_notice_within_threshold(sent, monkeypatch):
    monkeypatch.setenv(np.ENV_RUNNING_NOTICE_SECONDS, '5')
    runtime._run_job(_job(lambda: {'updated': 1}), '2026-10-07')

    assert [t for t in sent.texts if t.startswith('⏳')] == [], sent.texts
    assert len(sent.texts) == 1


def test_t13_running_notice_after_threshold(sent, monkeypatch):
    monkeypatch.setenv(np.ENV_RUNNING_NOTICE_SECONDS, '0.05')

    def slow():
        time.sleep(0.3)
        return {'updated': 1}

    runtime._run_job(_job(slow), '2026-10-07')

    notices = [t for t in sent.texts if t.startswith('⏳')]
    assert len(notices) == 1, sent.texts
    assert notices[0].startswith(f'⏳ 每日任务仍在运行：{JOB_ID}')
    assert '已跑 ' in notices[0]
    assert len(sent.texts) == 2, sent.texts          # 提示 + 完成（有产出）


def test_t14_zero_threshold_disables_notice(sent, monkeypatch):
    monkeypatch.setenv(np.ENV_RUNNING_NOTICE_SECONDS, '0')

    def slow():
        time.sleep(0.15)
        return {'updated': 1}

    runtime._run_job(_job(slow), '2026-10-07')

    assert [t for t in sent.texts if t.startswith('⏳')] == [], sent.texts
    assert len(sent.texts) == 1


def test_t15_notice_failure_does_not_affect_job(sent, monkeypatch):
    """提示回调自己炸了不许影响任务终态（回调在 timer 线程里，异常会静默丢失）。"""
    monkeypatch.setenv(np.ENV_RUNNING_NOTICE_SECONDS, '0.05')

    def flaky(text):
        if text.startswith('⏳'):
            raise RuntimeError('notice channel down')
        sent.texts.append(text)
        return True

    monkeypatch.setattr(runtime, '_send_feishu', flaky)

    def slow():
        time.sleep(0.2)
        return {'updated': 1}

    runtime._run_job(_job(slow), '2026-10-07')

    assert sent.marks[-1][0][2] == 'success'
    assert any(t.startswith('✅') for t in sent.texts), sent.texts


# ── T-16：人工触发的接线（FR-6）─────────────────────────────────────────────

def test_t16_trigger_job_passes_manual_true(monkeypatch):
    from adapters.inbound.fastapi_app.daily_jobs import registry

    job = _job(lambda: {'status': 'no_event'})
    monkeypatch.setattr(registry, 'JOBS', [job])
    monkeypatch.setattr(runtime, '_get_run', lambda *a, **k: None)

    got = {}
    called = threading.Event()

    def fake_run(j, run_date, **kw):
        got['job_id'] = j.job_id
        got['manual'] = kw.get('manual')
        called.set()

    monkeypatch.setattr(runtime, '_run_job', fake_run)

    result = runtime.trigger_job(JOB_ID, force=True)

    assert result['success'] is True, result
    assert called.wait(3), 'trigger_job 没有把任务交给线程执行'
    assert got['job_id'] == JOB_ID
    assert got['manual'] is True, got
