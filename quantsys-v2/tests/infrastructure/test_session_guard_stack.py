# -*- coding: utf-8 -*-
"""session_guard 可诊断性回归测试

2026-09-11（investor / w-8f2c4cc5）：
现场 session_leak_detected 累计 126 次却无法定位根因——detail 里的 traceback 被 500 字符
预算吃光，尾部停在 threading 引导帧 "self._targe"，真实调用方被截掉。
本测试锁定修复：创建点栈必须保留应用侧帧、剔除线程引导帧，并给出 origin（函数@文件:行号）。
"""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from infrastructure.persistence.orm import session_guard


class _FakeSession:
    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _enable_guard_registry():
    """只打开登记开关，不启动回收线程（避免测试期后台线程干扰）"""
    old = session_guard._guard_enabled
    session_guard._guard_enabled = True
    session_guard._session_registry.clear()
    yield
    session_guard._guard_enabled = old
    session_guard._session_registry.clear()


def create_session_in_worker():
    """模拟 ThreadPoolExecutor 工作线程里创建 Session（现场线程名 ThreadPoolExecutor-N_M）"""
    session = _FakeSession()
    session_guard.track_session_creation(session)
    return session


def test_stack_keeps_app_frames_and_drops_thread_bootstrap():
    with ThreadPoolExecutor(max_workers=1) as ex:
        session = ex.submit(create_session_in_worker).result()

    info = session_guard._session_registry[id(session)]
    tb = info['traceback']

    assert 'create_session_in_worker' in tb, f"应用侧帧缺失: {tb}"
    assert '_bootstrap_inner' not in tb, f"引导帧未被剔除: {tb}"
    assert 'concurrent/futures/thread.py' not in tb, f"线程池内部帧未被剔除: {tb}"
    # origin 必须直接指向创建点，便于从错误看板一眼定位
    assert info['origin'].startswith('create_session_in_worker@'), info['origin']
    assert 'test_session_guard_stack.py' in tb


def test_origin_points_to_main_thread_caller():
    session = _FakeSession()
    session_guard.track_session_creation(session)
    info = session_guard._session_registry[id(session)]
    assert 'test_session_guard_stack.py' in info['origin'], info['origin']


def test_close_unregisters_session():
    session = _FakeSession()
    session_guard.track_session_creation(session)
    assert id(session) in session_guard._session_registry
    session_guard.track_session_close(session)
    assert id(session) not in session_guard._session_registry


def test_guard_disabled_no_tracking():
    session_guard._guard_enabled = False
    session = _FakeSession()
    session_guard.track_session_creation(session)
    assert session_guard._session_registry == {}
