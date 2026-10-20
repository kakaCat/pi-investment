"""派单服务单测（2026-10-20）：信封、报告要求、派发结果。

纯离线：注入 fake facade，不触网、不连库。
"""
from qs_notification.application.agent_task_dispatch import (
    build_instruction,
    dispatch_agent_task,
)


class FakeFacade:
    def __init__(self, status='ok'):
        self.status = status
        self.calls = []

    def wake_agent(self, event, data, target_agent=None):
        self.calls.append({'event': event, 'data': data, 'target': target_agent})
        return self.status


def test_build_instruction_carries_task_and_report_demand():
    text = build_instruction('盯盘积压清理', '逐条看，别批量关。')
    assert '【任务】盯盘积压清理' in text
    assert '逐条看，别批量关。' in text
    assert '【交付要求·必须执行】' in text
    assert 'feishu_notify' in text
    for seg in ('范围与结果', '关键结论', '需人工拍板', '未完成/失败'):
        assert seg in text, seg
    assert '「盯盘积压清理｜完成」' in text


def test_build_instruction_silent_task_has_no_report_demand():
    text = build_instruction('夜间哨兵', '只读巡检。', requires_report=False)
    assert '【交付要求·必须执行】' not in text
    assert 'feishu_notify' not in text
    assert '静默任务' in text


def test_dispatch_sends_envelope_and_returns_status():
    facade = FakeFacade('ok')
    result = dispatch_agent_task(
        title='积压清理', instruction='逐条收敛', event='watch_backlog_sweep',
        target='agent-dh', facade=facade,
    )
    assert result['status'] == 'ok'
    assert result['requires_report'] is True
    assert len(result['prompt_sha256_16']) == 16
    assert len(facade.calls) == 1
    call = facade.calls[0]
    assert call['event'] == 'watch_backlog_sweep'
    assert call['target'] == 'agent-dh'
    # 收件人拿到的指令里必须有任务与报告要求
    instruction = call['data']['instruction']
    assert '【任务】积压清理' in instruction
    assert '【交付要求·必须执行】' in instruction
    assert call['data']['requires_report'] is True


def test_dispatch_silent_task_marks_requires_report_false():
    facade = FakeFacade('ok')
    dispatch_agent_task(title='哨兵', instruction='巡检', requires_report=False,
                        facade=facade)
    call = facade.calls[0]
    assert call['data']['requires_report'] is False
    assert '【交付要求·必须执行】' not in call['data']['instruction']


def test_dispatch_reports_channel_failure_verbatim():
    facade = FakeFacade('error')
    result = dispatch_agent_task(title='t', instruction='i', facade=facade)
    assert result['status'] == 'error'   # 不把失败改写成成功
