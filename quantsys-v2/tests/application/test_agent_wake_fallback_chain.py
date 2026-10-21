"""wake 候选链互备投递测试（2026-10-16）

可失败性（对应一次真实事故）：
  · agent-dh（默认目标）不可达时**必须**继续尝试 agent-ts——旧实现只在
    `key != DEFAULT_TARGET` 时回退，目标就是默认 agent 时没有任何回退，
    2026-10-16 21:36 因此 13 条待办全部 `wake_status=error`；
  · 回退成功必须标注真实落点（delivery_target / delivery_fallback_from）——换人不得静默；
  · 首个候选 **超时** 不得换人（"大概率已送达"，换人 = 重复处置风险）；
  · 全链失败如实返回 error（不假装已送达）。

为什么 mock requests.post：本文件测的是**候选链编排与载荷标注**（谁先谁后、标注什么），
真实 HTTP 由 agent 侧的 /wake 契约覆盖；`AGENT_NOTIFY_ALLOW_TEST` 只开非生产闸门。
"""
from unittest.mock import MagicMock, patch

import pytest
import requests


@pytest.fixture(autouse=True)
def _allow_non_prod_notify(monkeypatch):
    monkeypatch.setenv("AGENT_NOTIFY_ALLOW_TEST", "true")
    monkeypatch.delenv("WATCH_AGENT_FALLBACKS", raising=False)


def _ok_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {'success': True}
    return resp


def _service(**kwargs):
    from qs_agenthub.application.services.agent_notification_service import AgentNotificationService
    return AgentNotificationService(allow_non_prod=True, **kwargs)


# ── 候选链构造（纯函数）─────────────────────────────────────────────────────

def test_default_chain_is_mutual_backup():
    from qs_agenthub.application.services.agent_notification_service import AgentNotificationService as S
    assert S.candidate_chain('agent-dh') == ['agent-dh', 'agent-ts']
    assert S.candidate_chain('agent-ts') == ['agent-ts', 'agent-dh']
    assert S.candidate_chain(None) == ['agent-dh', 'agent-ts']      # None = 默认 agent


def test_chain_honours_env_override(monkeypatch):
    from qs_agenthub.application.services.agent_notification_service import AgentNotificationService as S
    monkeypatch.setenv('WATCH_AGENT_FALLBACKS', 'agent-ts')
    # 显式配置即"按配置的顺序兜底"，但目标仍优先且去重
    assert S.candidate_chain('agent-dh') == ['agent-dh', 'agent-ts']
    assert S.candidate_chain('agent-ts') == ['agent-ts']


# ── 投递编排 ────────────────────────────────────────────────────────────────

def test_default_agent_down_falls_back_to_other_agent():
    """事故回归：目标=agent-dh 挂掉 → 仍要送到 agent-ts（旧实现直接放弃）"""
    calls = []

    def _post(url, json=None, timeout=None, headers=None):
        calls.append((url, json))
        if '13080' in url:
            raise requests.exceptions.ConnectionError('refused')
        return _ok_response()

    with patch('qs_agenthub.application.services.agent_notification_service.requests.post',
               side_effect=_post):
        status = _service().notify_agent_detailed('watch_todo_timeout', {'todo_id': 91},
                                                  target='agent-dh')

    assert status == 'ok'
    assert [c[0] for c in calls] == ['http://127.0.0.1:13080/wake',
                                     'http://127.0.0.1:3002/wake']
    fb = calls[-1][1]['data']
    assert fb['delivery_target'] == 'agent-ts'          # 真实落点
    assert fb['delivery_fallback_from'] == 'agent-dh'   # 原目标
    assert fb['delivery_fallback_hops'] == 1
    assert 'cannot connect' in fb['delivery_fallback_reason']   # 如实带原因（含原 URL）
    assert fb['todo_id'] == 91                          # 业务载荷不被破坏


def test_primary_ok_stops_chain():
    calls = []

    def _post(url, json=None, timeout=None, headers=None):
        calls.append(url)
        return _ok_response()

    with patch('qs_agenthub.application.services.agent_notification_service.requests.post',
               side_effect=_post):
        assert _service().notify_agent_detailed('e', {}, target='agent-ts') == 'ok'

    assert calls == ['http://127.0.0.1:3002/wake']       # 命中即止，不多投


def test_timeout_does_not_switch_agent():
    """首个候选超时 = 大概率已送达：不换人（避免重复处置）"""
    calls = []

    def _post(url, json=None, timeout=None, headers=None):
        calls.append(url)
        raise requests.exceptions.Timeout('slow')

    with patch('qs_agenthub.application.services.agent_notification_service.requests.post',
               side_effect=_post):
        status = _service().notify_agent_detailed('e', {}, target='agent-dh')

    assert status == 'timeout'
    assert calls == ['http://127.0.0.1:13080/wake']


def test_all_candidates_failed_reports_error():
    calls = []

    def _post(url, json=None, timeout=None, headers=None):
        calls.append(url)
        raise requests.exceptions.ConnectionError('refused')

    with patch('qs_agenthub.application.services.agent_notification_service.requests.post',
               side_effect=_post):
        status = _service().notify_agent_detailed('e', {}, target='agent-dh')

    assert status == 'error'                             # 如实报未送达
    assert len(calls) == 2                               # 两个候选都试过


def test_chain_uses_injected_target_urls():
    """显式注入的 targets 地址参与候选链（联调/单测可用假端口）"""
    calls = []
    svc = _service(targets={'agent-dh': 'http://dh.test', 'agent-ts': 'http://ts.test'})

    def _post(url, json=None, timeout=None, headers=None):
        calls.append(url)
        raise requests.exceptions.ConnectionError('refused')

    with patch('qs_agenthub.application.services.agent_notification_service.requests.post',
               side_effect=_post):
        assert svc.notify_agent_detailed('e', {}) == 'error'

    assert calls == ['http://dh.test/wake', 'http://ts.test/wake']
