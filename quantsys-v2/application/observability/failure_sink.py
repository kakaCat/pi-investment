"""失败可见性出口 —— 任何自动链路的失败都必须有一根通向人的线。

REQ-261004154902-a7cd · t1（FR-2 / FR-9）。

## 为什么需要它

2026-10-04 取证的三条事实：
1. 调度器内层失败只调 ``agent_os_reporter.report_event`` → 出口是**已下线的** Agent OS
   ``localhost:8080``（日志里 ``agent-os ingest POST failed (dropped)`` 出现 **1696 次**）；
2. 策略侧通知只在「确实有买卖单」时发，而调仓恰好崩在发通知前一步 → 调仓通知自 2026-09-11
   起**从未发出**；
3. 结果：失败与空转都只有日志，而日志没人盯。

本模块把「失败要外发」收成**一个函数**：先落结构化日志（含 source/reason，便于 grep 与归档），
再走既有的 ``NotificationFacade``（内置 agent → 飞书降级链）。**自身绝不抛异常**——
可见性出问题不许反过来打挂业务链路。

## 通道可注入

生产由 :func:`_default_sink` 走 NotificationFacade；测试与离线环境用
:func:`install_failure_alert_sink` 注入自己的 sink（传 None 恢复默认）。
这与 ``trading_day_guard.install_degraded_alert_notifier`` 是同一形态。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

__all__ = [
    "report_failure",
    "install_failure_alert_sink",
    "SEVERITY_NORMAL",
    "SEVERITY_HIGH",
]

logger = logging.getLogger(__name__)

SEVERITY_NORMAL = "normal"
SEVERITY_HIGH = "high"

#: 外发通道；None = 用默认（NotificationFacade）。签名：sink(title, content, urgency) -> bool
_alert_sink: Optional[Callable[[str, str, str], bool]] = None


def install_failure_alert_sink(
    sink: Optional[Callable[[str, str, str], bool]],
) -> None:
    """注入失败外发通道（传 None 恢复默认实现）。测试/离线环境用。"""
    global _alert_sink
    _alert_sink = sink


def _default_sink(title: str, content: str, urgency: str) -> bool:
    """生产通道：经 NotificationFacade 发卡片（agent 优先、飞书降级）。"""
    try:
        from application.notification import get_notification_facade

        return bool(
            get_notification_facade().send_card(
                title=title, content=content, urgency=urgency
            )
        )
    except Exception as exc:  # noqa: BLE001 - 通知失败不得影响判定与业务
        logger.error(
            "failure_sink: 默认通道不可用（source 见上一条日志）: %s", exc
        )
        return False


def _build_content(
    source: str,
    reason: str,
    error: Optional[str],
    severity: str,
    context: Optional[Dict[str, Any]],
) -> str:
    lines = [
        f"来源: {source}",
        f"原因: {reason}",
        f"严重度: {severity}",
    ]
    if error:
        lines.append(f"错误: {error}")
    if context:
        for key, value in context.items():
            lines.append(f"{key}: {value}")
    lines.append("")
    lines.append("处置建议: 先查该来源的日志与 scheduler_runs.result，再用「该跑没跑」盘点器确认影响面。")
    return "\n".join(lines)


def report_failure(
    source: str,
    reason: str,
    error: Optional[str] = None,
    severity: str = SEVERITY_NORMAL,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    """报告一次失败：结构化日志 + 主动外发。

    Args:
        source: 失败来源（如 ``strategy.rebalance`` / ``pending_orders.match``）。
        reason: 机器可读原因（建议用 :mod:`run_outcome` 的 ``REASON_*``）。
        error: 异常原文（可为 None，例如"该跑没跑"这类无异常来源）。
        severity: ``normal`` | ``high``。
        context: 附加键值（账户、任务名、date…）。

    Returns:
        bool: 外发是否送达；**任何情况下都不抛异常**。
    """
    ctx: Dict[str, Any] = dict(context or {})
    message = (
        "failure_sink: source=%s reason=%s severity=%s error=%s context=%s"
    )
    # 结构化日志（loud）：一条就够，source/reason 进正文，便于 grep 与归档
    logger.error(message, source, reason, severity, error, ctx)

    sink = _alert_sink or _default_sink
    delivered = False
    try:
        delivered = bool(
            sink(
                f"🚨 自动链路失败：{source}",
                _build_content(source, reason, error, severity, ctx),
                SEVERITY_HIGH if severity == SEVERITY_HIGH else SEVERITY_NORMAL,
            )
        )
    except Exception as exc:  # noqa: BLE001 - 通道自己抛也不许击穿调用方
        logger.error(
            "failure_sink: 外发通道抛异常（已吞）source=%s reason=%s error=%s",
            source,
            reason,
            exc,
        )
        delivered = False

    if not delivered:
        # 外发失败本身也必须可见（否则又回到"只有日志"的老路）
        logger.error(
            "failure_sink: 外发未送达 source=%s reason=%s（通道返回 False 或抛错）",
            source,
            reason,
        )
    return delivered
