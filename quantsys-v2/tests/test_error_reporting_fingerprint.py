"""错误上报指纹与 Go 端跨语言一致性测试 — 2026-09-11 w-8f2c4cc5

背景：同一异常经两条通道落盘时曾生成两条看板事件——日志文件里的 structlog JSON 行（Go
worker 采集）指纹取「去易变键后的整段 JSON」，而 Python logging ERROR 经 agent_os_reporter
上报的事件指纹取「带 logger 前缀的文本行」，两者永不相等。实测 2026-09-11 00:52
SchedulerService.add_task TypeError 产生 f5341905(JSON) + 9e7070cc(文本上报) + 584abd31(5xx 访问日志)。

修复（双端同步）：JSON 通道指纹改取语义键文本（event/message/msg/error/exception/detail 顺序拼接）；
纯文本通道剥离 logger 模块前缀（adapters.x.y: msg 到 msg，不误伤 TypeError: 这类异常名开头）。

本用例与 Go 端 internal/repository/error_event_crosslang_test.go 使用同一组向量：任何一侧
改动归一化规则而另一侧未同步，都会在这里或那里失败。
"""
import json

import pytest

from infrastructure.error_reporting.agent_os_reporter import _fingerprint, normalize_msg

BARE_TEXT = "API错误: SchedulerService.add_task() got an unexpected keyword argument 'task_type'"


def _fp(msg: str, detail=None) -> str:
    return _fingerprint(msg, None, detail)


FRAGMENT_A_JSON = json.dumps({
    "event": BARE_TEXT,
    "trace_id": "95509f30",
    "logger": "adapters.inbound.fastapi_app.shared",
    "level": "error",
    "timestamp": "2026-09-10T16:52:06.189571Z",
})
FRAGMENT_B_TEXT = "adapters.inbound.fastapi_app.shared: " + BARE_TEXT
FRAGMENT_C_ACCESS500 = 'INFO:     127.0.0.1:65290 - "POST /api/scheduler/tasks HTTP/1.1" 500 Internal Server Error'

STACK_DETAIL = ("Traceback (most recent call last):\n"
                '  File "/app/services/pool.py", line 88, in shutdown\n'
                "    code()\n"
                "TypeError: x")

# 与 Go 端 error_event_crosslang_test.go 完全相同的向量表（双端同跑生成）
VECTORS = [
    ('json_event_with_emoji',
     '{"event":"❌ 所有数据源都无法获取 600737.SH 的实时行情","trace_id":"aaaa1111","logger":"lg","timestamp":"2026-09-10T05:43:16.574188Z"}',
     "", "e281d0995e9aa9325ae551401692b72b6d08a363"),
    ('json_event_timeout',
     '{"event":"计算散户资金流失败: timeout 30s","trace_id":"bb","logger":"lg","timestamp":"2026-09-10T06:00:00Z"}',
     "", "bed33d6f01d2ad4be8cc62d0b0d7df20b6347b68"),
    ('plain_text_volatile',
     'plain text error pool=default price=17.82 ts=2026-09-10T05:43:16Z id=550e8400-e29b-41d4-a716-446655440000',
     "", "68948263f623ba4506c592d1947985224c4cbe89"),
    ('json_event_html_escape',
     '{"event":"html <b> & > test","trace_id":"cc","logger":"lg"}',
     "", "56a5d0bd39327aa05b53a61b45c0f204406a0d8e"),
    ('stack_frames', "any msg here", STACK_DETAIL,
     "ce0711aeff698435f4df541136fa9f41956c4db6"),
    ('fragment_a_json_channel', FRAGMENT_A_JSON, "",
     "b48a75eeed631a95d4be041e530b088409644bac"),
    ('fragment_b_text_channel', FRAGMENT_B_TEXT, "",
     "b48a75eeed631a95d4be041e530b088409644bac"),
    ('fragment_c_access_500', FRAGMENT_C_ACCESS500, "",
     "a5c77b5739d19fe7edd61a29720585e8123fb3a2"),
    ('exception_name_not_stripped', "TypeError: boom at 2026-09-10T05:43:16Z", "",
     "8437b899337892657a3d61c33d1df4066b4ea901"),
]


@pytest.mark.parametrize("name,msg,detail,want", VECTORS, ids=[v[0] for v in VECTORS])
def test_fingerprint_cross_language_vectors(name, msg, detail, want):
    """逐位对齐 Go 端向量；不一致即双端归一化规则已漂移。"""
    assert _fp(msg, detail or None) == want, f"{name} 指纹与 Go 端向量不一致"


def test_same_incident_merges_across_channels():
    """一次异常的两个落盘通道必须同指纹（此前生成两条看板事件）。"""
    assert _fp(FRAGMENT_A_JSON) == _fp(FRAGMENT_B_TEXT) == _fp(BARE_TEXT)


def test_access_500_line_stays_distinct():
    """5xx 访问日志行携带 HTTP 路径与状态，口径不同，不得与异常行归并。"""
    assert _fp(FRAGMENT_C_ACCESS500) != _fp(FRAGMENT_A_JSON)


def test_normalize_strips_logger_module_prefix_only():
    assert normalize_msg(FRAGMENT_B_TEXT) == normalize_msg(BARE_TEXT)
    assert normalize_msg("TypeError: boom") == "TypeError: boom"
    assert normalize_msg("uvicorn.error: boom") == "boom"


def test_normalize_keeps_all_semantic_keys():
    """event 只是通用标签时 error 才是根因——语义键必须拼接保留，不能只取 event。"""
    normalized = normalize_msg(
        '{"error":"boom","event":"x_failed","trace_id":"abc12345","timestamp":"2026-09-09T00:00:00Z"}')
    assert "boom" in normalized and "x_failed" in normalized
    assert "abc12345" not in normalized
