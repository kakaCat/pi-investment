"""baostock 登录有限重试（2026-09-13，看板事件 79aaf17d）。

旧实现登录零重试：上游抖动（error_msg = 网络接收错误。）时直接 return None，
调用方随即把该标的判为失败 —— 09-10 22:02 ~ 09-12 01:21 累计 93 条日志、去重后 37 次事件。
本组测试锁住新契约：可重试错误退避重试、永久错误不重试、最终失败只打一次 ERROR。
"""
import logging
from types import SimpleNamespace

import pytest

pytest.importorskip("baostock", reason="baostock 未安装")

import baostock
from adapters.outbound.datasources.providers.kline import baostock as bsmod
from adapters.outbound.datasources.providers.kline.baostock import BaostockKlineProvider


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """退避用假的 sleep，测试不真等。"""
    monkeypatch.setattr(bsmod.time, 'sleep', lambda _s: None)


def _result(code, msg):
    return SimpleNamespace(error_code=code, error_msg=msg)


def test_transient_login_error_retries_then_succeeds(monkeypatch):
    calls = []

    def fake_login():
        calls.append(1)
        return _result('0', 'success') if len(calls) > 1 else _result('10001', '网络接收错误。')

    monkeypatch.setattr(baostock, 'login', fake_login, raising=False)
    provider = BaostockKlineProvider()
    assert provider._ensure_login() is baostock
    assert len(calls) == 2


def test_permanent_login_error_is_not_retried(monkeypatch):
    calls = []

    def fake_login():
        calls.append(1)
        return _result('10002', '账户不存在')

    monkeypatch.setattr(baostock, 'login', fake_login, raising=False)
    provider = BaostockKlineProvider()
    assert provider._ensure_login() is None
    assert len(calls) == 1, "永久错误不应重试"


def test_persistent_transient_error_exhausts_attempts_with_single_error_log(monkeypatch, caplog):
    calls = []

    def fake_login():
        calls.append(1)
        return _result('10001', '网络接收错误。')

    monkeypatch.setattr(baostock, 'login', fake_login, raising=False)
    provider = BaostockKlineProvider()
    with caplog.at_level(logging.ERROR):
        assert provider._ensure_login() is None
    assert len(calls) == BaostockKlineProvider._LOGIN_ATTEMPTS == 3
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1, "上游抖动不应刷多条 ERROR（旧实现 93 条同源日志）"
