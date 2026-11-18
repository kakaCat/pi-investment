"""盯盘最小观测面（REQ-c9f899 t10/t12）

  GET /api/watch/metrics → 影子模式状态/待办规模/抑噪规则数

取数失败写 degraded 并保持 null，绝不拿 0 冒充事实（R-013）。
"""
import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter

from adapters.inbound.fastapi_app.watch_shadow_job import (
    SHADOW_DRY_RUN_ENV,
    SHADOW_SINCE_ENV,
    evaluate_shadow_overdue,
)

router = APIRouter(tags=['watch'])


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


def _default_counters(now: datetime) -> Dict[str, Any]:
    """当日两条链路计数（FR-4）：news 待办数 / 反思唤醒数。取不到 → None。"""
    out: Dict[str, Any] = {'news_todos_today': None, 'reflection_woken_today': None}
    try:
        from sqlalchemy import text
        from qs_kernel.infrastructure.persistence.database.engine import get_engine
        day = now.date().isoformat()
        with get_engine().connect() as conn:
            out['news_todos_today'] = int(conn.execute(text(
                "SELECT count(*) FROM quant.watch_todos "
                "WHERE (evidence->>'source') = 'news' AND created_at::date = :d"),
                {'d': day}).scalar() or 0)
            out['reflection_woken_today'] = int(conn.execute(text(
                "SELECT coalesce(sum((result->>'woken')::int), 0) "
                "FROM quant.scheduler_runs WHERE started_at::date = :d "
                "AND task_id IN (SELECT id FROM quant.scheduler_tasks "
                "WHERE name LIKE 'plan_reflect%')"), {'d': day}).scalar() or 0)
    except Exception:  # noqa: BLE001 - 缺表/缺列一律按未知（null），不用 0 冒充
        return out
    return out


def build_metrics(now: Optional[datetime] = None, todo_repo=None,
                  rule_noise_repo=None, counts_provider=None) -> Dict[str, Any]:
    """组装指标；取数失败如实降级，不抛错。"""
    now = now or datetime.now()
    degraded = []
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
    try:
        counts = (counts_provider or _default_counters)(now) or {}
    except Exception as e:  # noqa: BLE001 - 计数是增益，失败降级为 null
        degraded.append('plan_closure_counters_failed: %s' % e)
        counts = {}

    notes = ['路由与定时巡检注册已由 t12 接线（main.py / daily_jobs_bootstrap）']
    if todo_repo is None:
        notes.append('todo 规模未注入仓储（build_metrics 直调）：null=未知，不是 0')
    if shadow['verdict'] == 'unknown':
        notes.append('影子起始时间未落地（WATCH_DIGEST_DRY_RUN_SINCE 空）——'
                     '由 shadow_mode_clock 落库（库优先、env 兜底），重启读回真值；仅库不可用时退化为 env')

    return {
        'shadow_mode': shadow['verdict'],
        'shadow_since': shadow_since.isoformat() if shadow_since else None,
        'shadow_reason': shadow['reason'],
        'pending_todos': todo_fields['pending'],
        'by_level': todo_fields['by_level'],
        'by_flow_state': todo_fields['by_flow_state'],
        'todos_created_today': todo_fields['created_today'],
        'todos_closed_today': todo_fields['closed_today'],
        'terminal_rate_today': todo_fields['terminal_rate_today'],
        'news_todos_today': counts.get('news_todos_today'),
        'reflection_woken_today': counts.get('reflection_woken_today'),
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
