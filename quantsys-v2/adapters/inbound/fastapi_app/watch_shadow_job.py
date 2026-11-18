"""影子模式超期巡检（REQ-c9f899 t10）

dry_run 挂载超过 48 小时必须提请裁决，避免影子模式无限期挂着。
判定是纯函数，时间由调用方注入；通知失败只记日志，不打挂巡检。
"""
import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_SHADOW_MAX_HOURS = 48.0
SHADOW_SINCE_ENV = 'WATCH_DIGEST_DRY_RUN_SINCE'
SHADOW_DRY_RUN_ENV = 'WATCH_DIGEST_DRY_RUN'


def as_naive_datetime(value):
    """把带时区的 datetime 归一为 naive 本地时间；非 datetime 原样返回。"""
    if not isinstance(value, datetime):
        return value
    return value.astimezone().replace(tzinfo=None) if value.tzinfo else value


def evaluate_shadow_overdue(dry_run: bool, shadow_since: Optional[datetime],
                            now: datetime, max_hours: float = DEFAULT_SHADOW_MAX_HOURS) -> Dict[str, Any]:
    """影子模式超期判定（纯函数）。verdict ∈ ok / overdue / unknown / off。"""
    if not dry_run:
        return {'verdict': 'off', 'hours': None, 'should_alert': False,
                'reason': '影子模式已关闭'}
    if shadow_since is None:
        return {'verdict': 'unknown', 'hours': None, 'should_alert': False,
                'reason': '不知道影子模式挂了多久（缺 %s）——无法判定超期，不告警'
                          % SHADOW_SINCE_ENV}
    hours = (as_naive_datetime(now) - as_naive_datetime(shadow_since)).total_seconds() / 3600.0
    if hours > max_hours:
        return {'verdict': 'overdue', 'hours': hours, 'should_alert': True,
                'reason': '影子模式已挂 %.1fh > %.0fh：请裁决——真开还是关掉（不许无限期挂着）'
                          % (hours, max_hours)}
    return {'verdict': 'ok', 'hours': hours, 'should_alert': False,
            'reason': '影子模式 %.1fh，未超期' % hours}


def run_shadow_check(now: Optional[datetime] = None,
                     sender: Optional[Callable[[str], None]] = None,
                     shadow_max_hours: float = DEFAULT_SHADOW_MAX_HOURS) -> Dict[str, Any]:
    """巡检一次影子状态，超期时通过 sender 告警。"""
    now = now or datetime.now()
    dry_run = os.getenv(SHADOW_DRY_RUN_ENV, 'true').strip().lower() != 'false'
    since_raw = os.getenv(SHADOW_SINCE_ENV, '').strip()
    shadow_since = None
    if since_raw:
        try:
            shadow_since = datetime.fromisoformat(since_raw)
        except ValueError:
            logger.error('影子起始时间格式非法，按 unknown 处理', value=since_raw)
    shadow = evaluate_shadow_overdue(dry_run, shadow_since, now, max_hours=shadow_max_hours)

    alerts = [('shadow_mode_overdue', shadow['reason'])] if shadow['should_alert'] else []
    sent = 0
    for kind, reason in alerts:
        if sender is not None:
            try:
                sender('【盯盘引擎】影子模式超期 | ' + reason)
                sent += 1
            except Exception as e:  # noqa: BLE001
                logger.error('告警发送失败', kind=kind, error=str(e))
        else:
            logger.warning('告警(未接线，log-only)', kind=kind, reason=reason)

    logger.info('影子模式巡检完成', shadow=shadow['verdict'],
                alerts=len(alerts), sent=sent)
    return {'shadow': shadow, 'alerts': alerts, 'sent': sent, 'at': now}
