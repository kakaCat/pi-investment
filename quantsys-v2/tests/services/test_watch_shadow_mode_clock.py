"""影子起始时间落地（REQ-c9f899 t12 §6-项9）。

可失败性：已有值优先；非影子不写；默认影子写 now；ensure 幂等不刷新起点。
"""
from datetime import datetime

from application.services.watch_engine.shadow_mode_clock import (
    SHADOW_DRY_RUN_ENV,
    SHADOW_SINCE_ENV,
    ensure_shadow_since_env,
    resolve_shadow_since,
)

NOW = datetime(2026, 9, 18, 10, 0, 0)


def test_existing_value_wins():
    env = {SHADOW_SINCE_ENV: "2026-01-01T00:00:00"}
    assert resolve_shadow_since(NOW, env) == "2026-01-01T00:00:00"


def test_none_when_not_dry_run():
    assert resolve_shadow_since(NOW, {SHADOW_DRY_RUN_ENV: "false"}) is None


def test_default_is_shadow_and_returns_now():
    assert resolve_shadow_since(NOW, {}) == NOW.isoformat()


def test_ensure_writes_once_and_is_idempotent():
    env = {}
    assert ensure_shadow_since_env(NOW, env) == NOW.isoformat()
    assert env[SHADOW_SINCE_ENV] == NOW.isoformat()
    later = datetime(2026, 9, 19, 0, 0, 0)
    assert ensure_shadow_since_env(later, env) == NOW.isoformat()   # 不覆盖起点
    assert env[SHADOW_SINCE_ENV] == NOW.isoformat()


def test_ensure_noop_when_dry_run_off():
    env = {SHADOW_DRY_RUN_ENV: "false"}
    assert ensure_shadow_since_env(NOW, env) is None
    assert SHADOW_SINCE_ENV not in env