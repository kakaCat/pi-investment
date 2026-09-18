"""引擎心跳巡检（REQ-c9f899 t10）

解决的问题：引擎是后端进程内的一条 daemon 线程，摘要门/元触发/持仓联动全部内嵌在
run_forever 里——**线程一死，这些能力同时静默消失，而没有任何主动信号**（2026-08-05
同型事故：规则在、无人判定）。用户裁定「不做控制台」，最小保留就是本条：心跳缺失告警。

设计要点（都可被 tests/jobs/test_heartbeat.py 证伪）：
  · 判定是**纯函数**（evaluate_heartbeat / evaluate_shadow_overdue），时间由调用方注入；
  · **只在"曾有心跳但已过期"时告警**：心跳从未出现（还没启动/刚部署/未启用）不告警，
    只报 never——否则冷启动必然误报，告警一响就被无视；
  · 影子模式超期同样只报事实：dry_run 挂着超过 48h 必须提请裁决（影子模式没有到期自检，
    可以无限期挂着——实测已挂 7 天）。
  · 定时注册与真实通知通道接线归 t12（本模块不自建调度器、不直接发飞书）。

⚠️ 诚实边界：run_heartbeat_check 的 sender 默认只记日志（log-only）。真实飞书投递
需要通知通道装配（t12）。**不允许**在这里假装"已发飞书"。
"""
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

#: 心跳过期阈值（秒）：默认 180（= 3 个心跳周期，容忍两次抖动）
DEFAULT_STALE_SEC = 180.0

#: 影子模式最长挂载时长（小时）：超过即提请裁决（用户裁定：影子模式不许无限期挂着）
DEFAULT_SHADOW_MAX_HOURS = 48.0

SHADOW_SINCE_ENV = 'WATCH_DIGEST_DRY_RUN_SINCE'
SHADOW_DRY_RUN_ENV = 'WATCH_DIGEST_DRY_RUN'


def as_naive_datetime(value):
    """把可能带时区的 datetime 归一为 **naive 本地时间**；非 datetime 原样返回。

    为什么必须在消费侧兜一层：DB 的 TIMESTAMPTZ 读回来是 **aware**，而调用方普遍用
    naive 的 datetime.now()。直接相减会 TypeError——2026-09-18 线上实测
    /api/watch/metrics 因此 500（同一类错误当天在 shadow_mode_clock 出口也出现过一次）。
    单测用 naive 假数据，所以这条路只有真库才会暴露。
    """
    if not isinstance(value, datetime):
        return value
    return value.astimezone().replace(tzinfo=None) if value.tzinfo else value


def evaluate_heartbeat(heartbeat_at: Optional[datetime], now: datetime,
                       stale_sec: float = DEFAULT_STALE_SEC,
                       enabled: bool = True) -> Dict[str, Any]:
    """心跳判定（纯函数）。verdict ∈ ok / stale / never / disabled。"""
    if not enabled:
        return {'verdict': 'disabled', 'age_sec': None, 'should_alert': False,
                'reason': '心跳未启用（WATCH_HEARTBEAT_ENABLED=false）'}
    if heartbeat_at is None:
        return {'verdict': 'never', 'age_sec': None, 'should_alert': False,
                'reason': '从未收到心跳（尚未启动/未启用）——不告警，避免冷启动误报'}
    age = (as_naive_datetime(now) - as_naive_datetime(heartbeat_at)).total_seconds()
    if age > stale_sec:
        return {'verdict': 'stale', 'age_sec': age, 'should_alert': True,
                'reason': '心跳已过期 %.0fs > %.0fs：引擎线程可能已死（摘要门/元触发/持仓联动同时失效）'
                          % (age, stale_sec)}
    return {'verdict': 'ok', 'age_sec': age, 'should_alert': False,
            'reason': '心跳正常（%.0fs）' % age}


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


def run_heartbeat_check(now: Optional[datetime] = None,
                        store=None,
                        sender: Optional[Callable[[str], None]] = None,
                        stale_sec: float = DEFAULT_STALE_SEC,
                        shadow_max_hours: float = DEFAULT_SHADOW_MAX_HOURS) -> Dict[str, Any]:
    """巡检一次：读心跳/影子状态 → 判定 → 需要时调用 sender。

    返回结构含两个判定与 alerts 列表（供测试与调用方断言）。
    """
    now = now or datetime.now()
    enabled = os.getenv('WATCH_HEARTBEAT_ENABLED', 'true').strip().lower() in ('1', 'true', 'yes', 'on')
    heartbeat_at = None
    if store is not None:
        try:
            meta = store.load_meta() or {}
            heartbeat_at = meta.get('heartbeat_at')
        except Exception as e:  # noqa: BLE001
            logger.error('读取心跳失败（按 never 处理，不误报 stale）', error=str(e))

    hb = evaluate_heartbeat(heartbeat_at, now, stale_sec=stale_sec, enabled=enabled)

    dry_run = os.getenv(SHADOW_DRY_RUN_ENV, 'true').strip().lower() != 'false'
    since_raw = os.getenv(SHADOW_SINCE_ENV, '').strip()
    shadow_since = None
    if since_raw:
        try:
            shadow_since = datetime.fromisoformat(since_raw)
        except ValueError:
            logger.error('影子起始时间格式非法，按 unknown 处理', value=since_raw)
    shadow = evaluate_shadow_overdue(dry_run, shadow_since, now, max_hours=shadow_max_hours)

    alerts = []
    if hb['should_alert']:
        alerts.append(('engine_heartbeat', hb['reason']))
    if shadow['should_alert']:
        alerts.append(('shadow_mode_overdue', shadow['reason']))

    sent = 0
    for kind, reason in alerts:
        title = '【盯盘引擎】%s' % ('心跳丢失' if kind == 'engine_heartbeat' else '影子模式超期')
        if sender is not None:
            try:
                sender(title + ' | ' + reason)
                sent += 1
            except Exception as e:  # noqa: BLE001 - 告警通道失败不许打挂巡检
                logger.error('告警发送失败', kind=kind, error=str(e))
        else:
            logger.warning('告警(未接线，log-only)', kind=kind, reason=reason)

    logger.info('心跳巡检完成', heartbeat=hb['verdict'], shadow=shadow['verdict'],
                alerts=len(alerts), sent=sent)
    return {'heartbeat': hb, 'shadow': shadow, 'alerts': alerts, 'sent': sent, 'at': now}
