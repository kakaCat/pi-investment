"""财报时效性告警日志契约回归（2026-09-13，w-32314d00，错误事件 8006b7ea）

事故：`infrastructure/jobs/financial_timeliness_check_job` 的 `_send_timeliness_alert` 用
**structlog 风格**调用了一个**标准库** logger：

    logger.warning("financial_timeliness_alert", symbol=..., expected_date=..., message=...)

标准库 `Logger._log()` 只接受 exc_info/stack_info/stacklevel/extra → 必然
`TypeError: Logger._log() got an unexpected keyword argument 'symbol'`；
异常又被同函数的 `except Exception` 吞掉，于是**告警正文从未落日志**，
只留下"发送时效性告警失败"这条症状级 error（09-12/09-13 两次 09:00 各报一次）。

本测试锁三件事：
  1. 告警函数不再抛（且不产生 ERROR 记录）；
  2. 告警正文（超期天数/建议行动）确实出现在 WARNING 日志里——修好 TypeError 但丢掉正文等于没修；
  3. 静态护栏：本模块内所有 stdlib logger 调用不得使用 structlog 风格的任意关键字参数。
"""
import ast
import logging
from pathlib import Path

import pytest

import application.notification as _notif_pkg
from infrastructure.jobs import financial_timeliness_check_job as mod
from infrastructure.jobs.financial_timeliness_check_job import _send_timeliness_alert

SAMPLE = {
    'check_date': '2026-09-13',
    'expected_report_date': '2026-06-30',
    'latest_report_date': '2026-03-31',
    'disclosure_deadline': '2026-08-31',
    'days_overdue': 6,
}

ALLOWED_LOGGER_KWARGS = {'exc_info', 'stack_info', 'stacklevel', 'extra'}
LEVELS = {'debug', 'info', 'warning', 'warn', 'error', 'exception', 'critical', 'fatal', 'log'}


class _FakeFacade:
    """假门面：记录调用、可控成功/失败/抛错。测试里**只能**用它，绝不碰真门面。"""

    def __init__(self, ok=True, raises=None):
        self.ok = ok
        self.raises = raises
        self.calls = []

    def send_card(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return self.ok


@pytest.fixture(autouse=True)
def _forbid_real_notifications(monkeypatch):
    """护栏：本文件任何用例都不得真的外发通知。

    2026-09-13（w-32314d00）血泪：接入 NotificationFacade 后，忘记注入 fake 的用例
    会**真的给用户发飞书消息**（实测发生）。默认把门面解析函数替换成"报错版"，
    忘注入 → 用例失败，而不是骚扰用户。
    """
    def _boom(*args, **kwargs):
        raise AssertionError('测试禁止使用真实 NotificationFacade —— 请注入 _FakeFacade')
    monkeypatch.setattr(_notif_pkg, 'get_notification_facade', _boom)


def _warnings(caplog):
    return [r for r in caplog.records if r.name == mod.__name__]


def test_alert_does_not_raise_and_emits_no_error(caplog):
    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        _send_timeliness_alert(SAMPLE, facade=_FakeFacade())   # 修复前：这里会走进 except 并打出 ERROR
    assert [r.levelno for r in _warnings(caplog) if r.levelno >= logging.ERROR] == []


def test_alert_body_reaches_the_log(caplog):
    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        _send_timeliness_alert(SAMPLE, facade=_FakeFacade())
    text = '\n'.join(r.getMessage() for r in _warnings(caplog))
    assert 'financial_timeliness_alert' in text
    assert '超期天数: 6 天' in text and '建议行动' in text
    assert 'symbol=全市场' in text


def test_alert_survives_missing_symbol_key(caplog):
    """本 job 是全市场检查，result_dict 不含 symbol（2026-09-11 事件 bd03ca47）——必须仍不抛。"""
    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        _send_timeliness_alert({k: v for k, v in SAMPLE.items() if k != 'symbol'},
                              facade=_FakeFacade())
    assert any('symbol=全市场' in r.getMessage() for r in _warnings(caplog))


def test_forgetting_to_inject_facade_fails_instead_of_sending(caplog):
    """护栏自检：不注入 facade 时门面解析被换成报错版 → 返回 False 并留 ERROR，
    **绝不会真的外发通知**（业务 except 会把 AssertionError 收敛成投递失败）。"""
    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        delivered = _send_timeliness_alert(SAMPLE)
    assert delivered is False
    assert any('禁止使用真实 NotificationFacade' in r.getMessage()
               for r in _warnings(caplog) if r.levelno >= logging.ERROR)


def test_no_structlog_style_kwargs_on_stdlib_logger():
    """静态护栏：stdlib logger 不吃任意 kwargs，写了就是运行期 TypeError。"""
    src = Path(mod.__file__).read_text(encoding='utf-8')
    tree = ast.parse(src)

    stdlib_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            f = node.value.func
            if isinstance(f, ast.Attribute) and f.attr == 'getLogger':
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        stdlib_names.add(tgt.id)
    assert stdlib_names, '未找到 logging.getLogger 绑定，护栏失效（请更新本测试）'

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in LEVELS:
            continue
        base = node.func.value
        if not isinstance(base, ast.Name) or base.id not in stdlib_names:
            continue
        bad = [k.arg for k in node.keywords if k.arg not in ALLOWED_LOGGER_KWARGS]
        if bad:
            offenders.append((node.lineno, bad))
    assert offenders == [], f'stdlib logger 收到非法 kwargs（运行期必抛 TypeError）: {offenders}'

# ---------------------------------------------------------------------------
# 外部投递（NotificationFacade）——2026-09-13 追加（用户要求：告警不能只写日志）
# 背景：该 job 的告警此前只写日志，财报超期 6 天无人知晓（日志没人主动看）。
# 现按架构铁律接 NotificationFacade；下面锁住：投递被调用、失败可观测、异常不外泄。
# ---------------------------------------------------------------------------


def test_alert_is_delivered_via_notification_facade(caplog):
    fake = _FakeFacade(ok=True)
    with caplog.at_level(logging.INFO, logger=mod.__name__):
        delivered = _send_timeliness_alert(SAMPLE, facade=fake)
    assert delivered is True
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call['urgency'] == 'high'
    assert '财报时效性' in call['title']
    assert '超期天数: 6 天' in call['content'] and '建议行动' in call['content']
    assert any('已投递' in r.getMessage() for r in _warnings(caplog))


def test_delivery_failure_is_observable(caplog):
    """门面返回 False = 未送达：必须返回 False 且打 ERROR（进 error_events 台账），
    否则"告警静默失败"又要靠人工翻日志才能发现。"""
    fake = _FakeFacade(ok=False)
    with caplog.at_level(logging.WARNING, logger=mod.__name__):   # WARNING 级可同时捕获 ERROR
        delivered = _send_timeliness_alert(SAMPLE, facade=fake)
    assert delivered is False
    errors = [r.getMessage() for r in _warnings(caplog) if r.levelno >= logging.ERROR]
    assert any('投递失败' in m for m in errors)
    # 日志留痕仍在（投递失败不等于本地无痕）
    assert any('financial_timeliness_alert' in r.getMessage() for r in _warnings(caplog))


def test_delivery_exception_does_not_escape(caplog):
    fake = _FakeFacade(raises=RuntimeError('feishu down'))
    with caplog.at_level(logging.ERROR, logger=mod.__name__):
        delivered = _send_timeliness_alert(SAMPLE, facade=fake)
    assert delivered is False
    recs = [r for r in _warnings(caplog) if r.levelno >= logging.ERROR]
    assert any('feishu down' in r.getMessage() for r in recs)
    assert any(r.exc_info for r in recs), '告警链路异常必须带栈（exc_info=True）'


def test_no_direct_feishu_channel_or_webhook_in_this_module():
    """架构铁律（CLAUDE.md）：出站通知只能经 NotificationFacade，
    禁止直接 import infrastructure.notification.channels.* 或裸 requests.post(webhook)。"""
    src = Path(mod.__file__).read_text(encoding='utf-8')
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod_names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ''])
            for name in mod_names:
                assert 'notification.channels' not in (name or ''), f'禁止直连渠道: {name}'
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = node.func.value
            if isinstance(base, ast.Name) and base.id == 'requests' and node.func.attr == 'post':
                raise AssertionError('禁止裸 requests.post（应经 NotificationFacade）')

