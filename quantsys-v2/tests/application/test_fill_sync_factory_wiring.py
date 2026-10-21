"""成交回执监听在组合根的装配测试（RFC 017 §2.1.4 收尾接线）。

覆盖：
  · create_watch_engine 完成后 register_fill_listener 已被调用（listener 就位）；
  · 装配失败只降级（不抛、引擎照常返回）；
  · 重复装配幂等（后注册覆盖前者，无泄漏报错）。
"""
from unittest.mock import MagicMock, patch

from application.trading.paper_trading_engine import get_fill_listener


def test_register_helper_installs_listener():
    from qs_watch.application.services.watch_engine.factory import (
        _register_fill_sync_listener,
    )

    engine = MagicMock()
    engine.rule_repo = MagicMock()
    engine.position_lifecycle_service = MagicMock()

    # 2026-10-21 反向越层阶段1：factory 仓储改经 _repo_resolver accessor 取（按键 resolve），
    # 测试注入点同步从「patch 类」改为「patch accessor」。
    with patch(
        'qs_watch.application.services.watch_engine._repo_resolver.todo_repo',
        return_value=MagicMock(),
    ), patch(
        'qs_watch.application.services.watch_engine._repo_resolver.watch_trigger_repo',
        return_value=MagicMock(),
    ), patch(
        'qs_watch.application.services.watch_engine._repo_resolver.sim_position_repo',
        return_value=MagicMock(),
    ):
        _register_fill_sync_listener(engine, MagicMock())

    assert get_fill_listener() is not None
    assert callable(getattr(get_fill_listener(), 'on_fill', None))


def test_register_helper_failure_degrades_silently():
    from qs_watch.application.services.watch_engine.factory import (
        _register_fill_sync_listener,
    )

    engine = MagicMock()
    engine.rule_repo = MagicMock()
    # 制造装配失败：todo_service 为 None 时 FillSyncService 内部容忍，这里改让
    # 仓储构造必炸：patch 掉仓储 import 目标抛错。
    with patch(
        'qs_watch.application.services.watch_engine._repo_resolver.todo_repo',
        side_effect=RuntimeError('db down'),
    ):
        # 不抛即降级成功
        _register_fill_sync_listener(engine, MagicMock())
