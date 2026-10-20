"""派单脚本单测（2026-10-20）。

只测纯逻辑与留痕：不触网、不连库、不真的唤醒 agent。
"""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / 'tools' / 'dispatch_agent_task.py'


def _load_module():
    spec = importlib.util.spec_from_file_location('dispatch_agent_task', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def test_build_instruction_requires_report_by_default():
    text = mod.build_instruction('盯盘积压清理', '逐条看，别批量关。')
    assert '【任务】盯盘积压清理' in text
    assert '逐条看，别批量关。' in text
    assert '【交付要求·必须执行】' in text
    assert 'feishu_notify' in text
    # 四段结构必须在（这是 10-20 晚补的教训：报告要可核对）
    for seg in ('范围与结果', '关键结论', '需人工拍板', '未完成/失败'):
        assert seg in text, seg
    assert '「盯盘积压清理｜完成」' in text


def test_build_instruction_silent_task_has_no_report_demand():
    text = mod.build_instruction('夜间哨兵', '只读巡检。', requires_report=False)
    assert '【交付要求·必须执行】' not in text
    assert 'feishu_notify' not in text
    assert '静默任务' in text


def test_dispatch_dry_run_does_not_send(capsys):
    rec = mod.dispatch(title='x', instruction='y', dry_run=True)
    assert rec['status'] == 'dry_run'
    assert rec['prompt_length'] > 0
    out = capsys.readouterr().out
    assert '[dry-run]' in out


def test_audit_log_appends_one_json_line(tmp_path):
    log = tmp_path / 'dispatch.jsonl'
    mod._append_audit(log, {'title': 'a', 'status': 'ok'})
    mod._append_audit(log, {'title': 'b', 'status': 'error'})
    rows = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
    assert [r['title'] for r in rows] == ['a', 'b']
