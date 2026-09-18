"""影子起始时间库持久化单测（REQ-c9f899 返工 B，2026-09-18）

问题回归：上一版只把影子起始时间写进进程 env，重启即丢——进程运行不满 48h 时会把
「影子已挂很久」读成「刚挂上」，超期告警被无限推迟（实测影子挂了 7 天无人知）。

本文件守住：
  1) 首次进入影子模式**写库**；
  2) 重启（env 清空 + now 前进）后**读回库里的真值**，起点不被刷新；
  3) env 现值（外部已设）首次落库；
  4) 非影子模式不写库不写 env；
  5) 读库/写库失败只降级为 env 口径，绝不抛错打断启动；
  6) store=None 时保持纯函数语义（不碰库）。

这些用例会红：把 ensure 里的写库/读库摘掉、或让非影子也写库时全部失败
（已做变异验证，见实现汇报）。
"""
from datetime import datetime

from application.services.watch_engine.shadow_mode_clock import (
    SHADOW_SINCE_ENV, ensure_shadow_since_env, resolve_shadow_since,
)

T1 = datetime(2026, 9, 1, 9, 0, 0)
T2 = datetime(2026, 9, 10, 9, 0, 0)          # 9 天后的「重启」时刻


class FakeShadowStore:
    """带专用影子读写方法的适配器桩；可注入读/写失败"""

    def __init__(self, value=None, fail_load=False, fail_save=False):
        self.value = value
        self.fail_load = fail_load
        self.fail_save = fail_save
        self.saves = []

    def load_shadow_since(self):
        if self.fail_load:
            raise RuntimeError('load boom')
        return self.value

    def save_shadow_since(self, dt):
        if self.fail_save:
            raise RuntimeError('save boom')
        self.value = dt
        self.saves.append(dt)


def test_watch_first_entry_persists_to_store():
    store = FakeShadowStore()
    env = {}
    value = ensure_shadow_since_env(now=T1, env=env, store=store)
    assert value == T1.isoformat()
    assert store.value == T1                                    # 首次进入影子模式写库
    assert store.saves == [T1]
    assert env[SHADOW_SINCE_ENV] == T1.isoformat()              # 同时镜像进 env


def test_watch_restart_reads_persisted_not_now():
    """核心用例：重启后起点是库里的真值，不再归零/不刷新。"""
    store = FakeShadowStore()
    ensure_shadow_since_env(now=T1, env={}, store=store)

    env_after_restart = {}
    value = ensure_shadow_since_env(now=T2, env=env_after_restart, store=store)
    assert value == T1.isoformat()                              # 不是 T2
    assert env_after_restart[SHADOW_SINCE_ENV] == T1.isoformat()  # 库 → env 镜像
    assert len(store.saves) == 1                                # 幂等：不重复写


def test_watch_env_only_value_is_persisted_on_first_run():
    store = FakeShadowStore()
    env = {SHADOW_SINCE_ENV: T1.isoformat()}
    value = ensure_shadow_since_env(now=T2, env=env, store=store)
    assert value == T1.isoformat()                              # env 现值优先于 now
    assert store.value == T1                                    # 首次落库


def test_watch_non_shadow_mode_returns_none_and_writes_nothing():
    store = FakeShadowStore()
    env = {'WATCH_DIGEST_DRY_RUN': 'false'}
    assert ensure_shadow_since_env(now=T1, env=env, store=store) is None
    assert store.saves == []
    assert SHADOW_SINCE_ENV not in env


def test_watch_db_read_failure_falls_back_to_env_without_raise():
    store = FakeShadowStore(value=T1, fail_load=True)
    env = {}
    value = ensure_shadow_since_env(now=T2, env=env, store=store)
    assert value == T2.isoformat()                              # 库不可读 → 退回 now
    assert env[SHADOW_SINCE_ENV] == T2.isoformat()


def test_watch_db_write_failure_degrades_to_env_without_raise():
    store = FakeShadowStore(fail_save=True)
    env = {}
    value = ensure_shadow_since_env(now=T1, env=env, store=store)
    assert value == T1.isoformat()
    assert store.saves == []                                    # 没写成就是没写成
    assert env[SHADOW_SINCE_ENV] == T1.isoformat()              # 仍写 env（不假装落库）


def test_watch_resolve_without_store_stays_pure():
    """store=None：不碰库，行为与上一版一致（env 现值优先，否则 now）。"""
    assert resolve_shadow_since(now=T1, env={}) == T1.isoformat()
    assert resolve_shadow_since(
        now=T1, env={SHADOW_SINCE_ENV: T2.isoformat()}) == T2.isoformat()
    assert resolve_shadow_since(now=T1, env={'WATCH_DIGEST_DRY_RUN': 'false'}) is None


def test_watch_resolve_prefers_store_over_env():
    store = FakeShadowStore(value=T1)
    value = resolve_shadow_since(now=T2, env={SHADOW_SINCE_ENV: T2.isoformat()}, store=store)
    assert value == T1.isoformat()                              # 库优先于 env


def test_watch_store_without_dedicated_methods_falls_back_to_meta_field():
    class OldStore:
        def __init__(self):
            self.meta = {}

        def load_meta(self):
            return dict(self.meta)

        def save_meta(self, **fields):
            self.meta.update(fields)

    store = OldStore()
    assert ensure_shadow_since_env(now=T1, env={}, store=store) == T1.isoformat()
    assert store.meta['digest_shadow_since'] == T1
    assert ensure_shadow_since_env(now=T2, env={}, store=store) == T1.isoformat()
