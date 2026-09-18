"""影子模式起始时间落地（REQ-c9f899 t12 §6-项9；返工 B 补完库持久化，2026-09-18）

问题：evaluate_shadow_overdue 依赖 WATCH_DIGEST_DRY_RUN_SINCE，而当前无人写入该 env
→ 恒 unknown 不告警 →「影子模式不许无限期挂着」的自动提醒失效（实测已挂 7 天无人知）。

本轮处置（返工 B+C 已授权加列迁移）：
  · **库优先、env 兜底**：quant.watch_runtime_meta.digest_shadow_since（本次迁移新增列）
    是跨重启的唯一事实源；进程启动时先读库，读到就把它镜像进 env（心跳巡检只读 env），
    读不到才用 env 现值，再读不到才用「现在」。
  · **首次进入影子模式写库**：库为空且处于影子模式时落库一次；此后幂等不覆盖
    （重启不刷新起点）——这正是上一版「env 独木难支、重启归零」要修的。
  · **失败只降级不致命**：读/写库失败都记日志并退回 env 口径，绝不阻断进程启动；
    降级时诚实承认「本进程仍用 env 兜底，跨重启会丢」，不假装已落库。

边界：非影子模式（WATCH_DIGEST_DRY_RUN=false）时函数返回 None，不写库、不写 env。

影子默认值不变：WATCH_DIGEST_DRY_RUN 缺省仍视为 true（影子，fail-safe）。
"""
import os
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

SHADOW_SINCE_ENV = 'WATCH_DIGEST_DRY_RUN_SINCE'
SHADOW_DRY_RUN_ENV = 'WATCH_DIGEST_DRY_RUN'
#: quant.watch_runtime_meta 的影子起始时间列名（迁移 20260918b 新增）
SHADOW_META_FIELD = 'digest_shadow_since'


def _shadow_dry_run(env: Dict[str, str]) -> bool:
    """是否处于影子模式（WATCH_DIGEST_DRY_RUN 默认 true = 影子，与 factory 同口径）"""
    return str(env.get(SHADOW_DRY_RUN_ENV, 'true') or 'true').strip().lower() != 'false'


def _default_store() -> Any:
    """懒构造运行态适配器；装配失败返回 None（退回 env 口径，不阻断启动）。

    延迟 import：本模块在 app 启动最早期被调用，此时 ORM/适配器链路未必已就绪；
    构造失败或后续查询失败都必须降级而不是抛错（进程启动不允许被它打断）。
    """
    try:
        from adapters.outbound.repositories.watch_runtime_state_repository import (
            WatchRuntimeStateRepository,
        )
        return WatchRuntimeStateRepository()
    except Exception as e:  # noqa: BLE001
        logger.warning('影子起始时间适配器装配失败，退回 env 口径', error=str(e))
        return None


def _parse_dt(value: Any) -> Optional[datetime]:
    """把库里的时间值（datetime 或 ISO 字符串）归一为 datetime；非法返回 None"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        logger.error('影子起始时间值非法，按 unknown 处理', value=repr(value)[:80])
        return None


def _load_persisted(store: Any) -> Optional[datetime]:
    """读库中的影子起始时间；store 为空或读失败返回 None（降级为 env 兜底）"""
    if store is None:
        return None
    loader = getattr(store, 'load_shadow_since', None)
    try:
        if callable(loader):
            return _parse_dt(loader())
        meta = store.load_meta() or {}          # 旧适配器/桩：退回 meta 字段
    except Exception as e:  # noqa: BLE001 —— 响亮但不致命
        logger.error('影子起始时间读库失败（降级为 env 兜底，跨重启可能丢）', error=str(e))
        return None
    return _parse_dt(meta.get(SHADOW_META_FIELD))


def _persist(store: Any, dt: datetime) -> bool:
    """写库（幂等由调用方保证：只在库为空时写）；失败只降级不抛错"""
    if store is None:
        return False
    saver = getattr(store, 'save_shadow_since', None)
    try:
        if callable(saver):
            saver(dt)
        else:
            store.save_meta(**{SHADOW_META_FIELD: dt})   # 旧适配器/桩：退回 meta 字段
        return True
    except Exception as e:  # noqa: BLE001
        logger.error('影子起始时间落库失败（本进程仍用 env 兜底，跨重启会丢）', error=str(e))
        return False


def _to_iso_naive(value: Any) -> Optional[str]:
    """归一为 **naive** ISO 串。

    为什么必须剥时区：下游 evaluate_shadow_overdue 用 naive 的 datetime.now() 做
    (now - shadow_since)；若这里放出 aware 串，相减直接 TypeError，会把「影子模式
    无限期挂着」的告警打死（比不告警更糟——故障以异常形式出现，看起来像代码错）。
    库列是 TIMESTAMPTZ，读回来天然带 tz，故必须在此出口归一。
    """
    dt = _parse_dt(value)
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.isoformat()


def resolve_shadow_since(now: Optional[datetime] = None,
                         env: Optional[Dict[str, str]] = None,
                         store: Any = None) -> Optional[str]:
    """影子起始时间：**库优先 → env 兜底 → now**；非影子返回 None。

    纯函数口径不变（now/env 可注入），新增可选 store：
      · store=None（缺省）→ 完全不碰库，行为与上一版一致（读 env，否者用 now）；
      · store 非空 → 先读库；库为空才看 env。
    这样既能被单测当纯函数用，也能在生产里承担「跨重启读回真值」。
    """
    store_env = os.environ if env is None else env
    # 非影子模式：不读库、不取 env、不返回——这是"影子关了就不该有影子起点"的不变式。
    # （返工 B 首版把 dry_run 判定放在 env 兜底之后，导致 dry_run=false 仍返回旧值。）
    if not _shadow_dry_run(store_env):
        return None
    persisted = _load_persisted(store)
    if persisted is not None:
        return _to_iso_naive(persisted)
    existing = str(store_env.get(SHADOW_SINCE_ENV) or '').strip()
    if existing:
        return _to_iso_naive(existing) or existing
    return _to_iso_naive(now or datetime.now())


def ensure_shadow_since_env(now: Optional[datetime] = None,
                            env: Optional[Dict[str, str]] = None,
                            store: Any = None,
                            persist: bool = True) -> Optional[str]:
    """进程启动时落地影子起始时间（库优先、env 兜底），返回最终值。

    流程：
      1) 读库 → 有值：镜像进 env（心跳巡检只读 env）并返回——**重启读回真值**；
      2) 库为空：取 env 现值，env 也空则用 now（仅影子模式）；然后把该值**首次写库**
         （persist=False 或库不可用时只写 env），并补 env。
    幂等：已有值不覆盖（重启不刷新起点）。返回 None = 非影子模式，不适用。
    """
    store_env = os.environ if env is None else env
    if not _shadow_dry_run(store_env):
        return None                                 # 非影子模式：不碰库、不碰 env
    if store is None and persist:
        store = _default_store()

    persisted = _load_persisted(store)
    if persisted is not None:
        iso = _to_iso_naive(persisted)
        if str(store_env.get(SHADOW_SINCE_ENV) or '').strip() != iso:
            store_env[SHADOW_SINCE_ENV] = iso      # 库 → env 镜像（心跳巡检通道）
        return iso

    value = resolve_shadow_since(now=now, env=store_env, store=None)
    if value is None:
        return None                                 # 非影子模式：不写库、不写 env
    dt = _parse_dt(value)
    if store is not None and dt is not None:
        _persist(store, dt)                         # 首次进入影子模式：落库（失败只降级）
    if not str(store_env.get(SHADOW_SINCE_ENV) or '').strip():
        store_env[SHADOW_SINCE_ENV] = value
    return value
