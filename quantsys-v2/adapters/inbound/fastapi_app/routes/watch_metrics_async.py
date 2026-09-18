"""盯盘引擎最小观测面（REQ-c9f899 t10/t12）

用户裁定「不做控制台页面」，最小保留 = 引擎存活、影子模式与闭环规模可被外部看见：

  GET /api/watch/metrics → 心跳时间/年龄/引擎是否活着/影子模式状态/待办规模/抑噪规则数

接线说明（t12 §6-项7/项8）：
  · 路由注册进 main.py 由 t12 完成；
  · todo 规模字段此前显式 null（t10 时仓储未接线），t12 补齐为 **WatchTodoRepository.stats()**
    + WatchRuleNoiseRepository.count_suppressed()。取数失败写 degraded 并保持 null，
    **绝不拿 0 冒充事实**（R-013）；build_metrics 直调（未注入仓储）时同样返回 null，
    便于单测不碰 DB。
"""
import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter

from adapters.inbound.fastapi_app.watch_heartbeat_job import (
    DEFAULT_STALE_SEC,
    evaluate_heartbeat,
    evaluate_shadow_overdue,
)
from adapters.inbound.fastapi_app.watch_heartbeat_job import SHADOW_SINCE_ENV, SHADOW_DRY_RUN_ENV

router = APIRouter(tags=['watch'])


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _build_todo_fields(todo_repo, now: datetime, degraded: list) -> Dict[str, Any]:
    """待办规模（REQ-c9f899 t12 §6-项7）：未注入仓储 → 全 null（未知，不是 0）。"""
    empty = {'pending': None, 'by_level': None, 'by_flow_state': None,
             'created_today': None, 'closed_today': None, 'terminal_rate_today': None}
    if todo_repo is None:
        return empty
    try:
        stats = todo_repo.stats(now=now) or {}
    except Exception as e:  # noqa: BLE001 - 取数失败如实降级，不抛错
        degraded.append('todo_stats_failed: %s' % e)
        return empty
    return {
        'pending': stats.get('pending'),
        'by_level': stats.get('by_level'),
        'by_flow_state': stats.get('by_flow_state'),
        'created_today': stats.get('created_today'),
        'closed_today': stats.get('closed_today'),
        'terminal_rate_today': stats.get('terminal_rate_today'),
    }


def _build_suppressed(rule_noise_repo, now: datetime, degraded: list) -> Optional[int]:
    if rule_noise_repo is None:
        return None
    try:
        return int(rule_noise_repo.count_suppressed(now=now))
    except Exception as e:  # noqa: BLE001
        degraded.append('suppressed_rules_failed: %s' % e)
        return None


def build_metrics(now: Optional[datetime] = None, store=None, todo_repo=None,
                  rule_noise_repo=None) -> Dict[str, Any]:
    """组装指标（纯组装函数，便于单测；取数失败如实降级，不抛错）。

    store/todo_repo/rule_noise_repo 均可注入：**未注入即视为未知（null）**，绝不查库
    （单测与纯函数用法不依赖 DB）；生产路由会注入真实仓储。
    """
    now = now or datetime.now()
    degraded = []
    heartbeat_at = None
    if store is None:
        try:
            from adapters.outbound.repositories.watch_runtime_state_repository import (
                WatchRuntimeStateRepository,
            )
            store = WatchRuntimeStateRepository()
        except Exception as e:  # noqa: BLE001
            degraded.append('heartbeat_store_unavailable: %s' % e)
    if store is not None:
        try:
            meta = store.load_meta() or {}
            heartbeat_at = meta.get('heartbeat_at')
        except Exception as e:  # noqa: BLE001
            degraded.append('heartbeat_read_failed: %s' % e)

    hb = evaluate_heartbeat(heartbeat_at, now,
                            stale_sec=float(os.getenv('WATCH_HEARTBEAT_STALE_SEC', str(DEFAULT_STALE_SEC))),
                            enabled=_env_bool('WATCH_HEARTBEAT_ENABLED', True))

    dry_run = os.getenv(SHADOW_DRY_RUN_ENV, 'true').strip().lower() != 'false'
    since_raw = os.getenv(SHADOW_SINCE_ENV, '').strip()
    shadow_since = None
    if since_raw:
        try:
            shadow_since = datetime.fromisoformat(since_raw)
        except ValueError:
            degraded.append('shadow_since_unparsable: %s' % since_raw)
    shadow = evaluate_shadow_overdue(dry_run, shadow_since, now)

    todo_fields = _build_todo_fields(todo_repo, now, degraded)
    suppressed_rules = _build_suppressed(rule_noise_repo, now, degraded)

    notes = ['路由与定时巡检注册已由 t12 接线（main.py / daily_jobs_bootstrap）']
    if todo_repo is None:
        notes.append('todo 规模未注入仓储（build_metrics 直调）：null=未知，不是 0')
    if shadow['verdict'] == 'unknown':
        notes.append('影子起始时间未落地（WATCH_DIGEST_DRY_RUN_SINCE 空）——'
                     '由 shadow_mode_clock 落库（库优先、env 兜底），重启读回真值；仅库不可用时退化为 env')

    return {
        'heartbeat_at': heartbeat_at.isoformat() if heartbeat_at else None,
        'heartbeat_age_sec': hb['age_sec'],
        'heartbeat_verdict': hb['verdict'],
        'engine_alive': hb['verdict'] == 'ok',
        'heartbeat_reason': hb['reason'],
        'shadow_mode': shadow['verdict'],
        'shadow_since': shadow_since.isoformat() if shadow_since else None,
        'shadow_reason': shadow['reason'],
        'pending_todos': todo_fields['pending'],
        'by_level': todo_fields['by_level'],
        'by_flow_state': todo_fields['by_flow_state'],
        'todos_created_today': todo_fields['created_today'],
        'todos_closed_today': todo_fields['closed_today'],
        'terminal_rate_today': todo_fields['terminal_rate_today'],
        'suppressed_rules': suppressed_rules,
        'degraded': degraded,
        'notes': notes,
        'at': now.isoformat(),
    }


def _default_todo_repo():
    try:
        from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository
        return WatchTodoRepository()
    except Exception:  # noqa: BLE001 - 装配失败即未知（build_metrics 记 null）
        return None


def _default_noise_repo():
    try:
        from adapters.outbound.repositories.watch_rule_noise_repository import (
            WatchRuleNoiseRepository,
        )
        return WatchRuleNoiseRepository()
    except Exception:  # noqa: BLE001
        return None


@router.get('/api/watch/metrics')
def watch_metrics() -> Dict[str, Any]:
    return build_metrics(todo_repo=_default_todo_repo(),
                         rule_noise_repo=_default_noise_repo())
