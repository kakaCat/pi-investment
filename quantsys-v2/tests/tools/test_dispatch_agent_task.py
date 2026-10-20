"""派单 CLI 单测（2026-10-20）：只测薄壳——参数拼装与 dry-run，不触网。"""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / 'tools' / 'dispatch_agent_task.py'


def _load_module():
    spec = importlib.util.spec_from_file_location('dispatch_agent_task_cli', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def test_dry_run_prints_envelope_without_sending(capsys):
    rc = mod.main(['--title', '示例任务', '--instruction', '逐条看。', '--dry-run'])
    out = capsys.readouterr().out
    assert rc == 0
    assert '【任务】示例任务' in out
    assert '【交付要求·必须执行】' in out
    assert '[dry-run]' in out


def test_dry_run_no_report(capsys):
    mod.main(['--title', '哨兵', '--instruction', '巡检', '--dry-run', '--no-report'])
    out = capsys.readouterr().out
    assert '【交付要求·必须执行】' not in out
    assert '静默任务' in out


def test_audit_appends_json_lines(tmp_path):
    log = tmp_path / 'dispatch.jsonl'
    mod.append_audit(log, {'title': 'a', 'status': 'ok'})
    mod.append_audit(log, {'title': 'b', 'status': 'error'})
    rows = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
    assert [r['title'] for r in rows] == ['a', 'b']
