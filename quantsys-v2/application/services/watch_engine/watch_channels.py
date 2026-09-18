"""盯盘闭环的真实通知通道（REQ-c9f899 t12，2026-09-18）

把心跳告警与三段回执接到 NotificationFacade（飞书）——此前 t10/t6 的 sender 默认
log-only，告警只在日志里、人看不到（§6 待接线项 6/10）。

纪律（对齐 pi-investment/CLAUDE.md 通知架构铁律）：
  · 只经 application.notification.get_notification_facade()；禁止直接 import
    infrastructure.notification.channels.*，禁止 requests.post(飞书 webhook)。
  · 发送失败必须抛错，不许静默返回 False：run_heartbeat_check 用 sender 是否抛错
    统计 sent；ReceiptService 用 sender 是否抛错 决定 delivery_status=sent/failed。
    若这里吞掉失败返回 False，回执会被记成 sent（假成功），心跳会把失败当成已送达。

诚实边界（channel 路由）：facade.send_card 走 NotificationService → 渠道（feishu），
而 FeishuChannel 忽略 os_channel / 逻辑频道码（只有 AgentChannel 把 os_channel
转发给 Agent OS 网关）。因此 alerts/reports 的物理群区分在本路径上不被支持：
本模块把频道码写进卡片正文与优先级（timeout/P0 → urgency=high），但不假装已按群路由。
需要真按群路由时走 AgentChannel（agent_os_enabled）或给 FeishuChannel 加频道 webhook——
属后续接线，见 t12 汇报的偏差项。
"""
from typing import Any, Dict

import structlog

logger = structlog.get_logger(__name__)

#: 回执类型 → 卡片标题（三种回执 + 抑噪，R5）
_KIND_LABELS = {
    'escalate': '升级即回执',
    'result': '处置后回执',
    'timeout': '超时回执',
    'suppressed': '抑噪回执',
}


def send_watch_alert(text: str) -> bool:
    """心跳/影子超期告警的真实投递（供 run_heartbeat_check 的 sender 参数）。

    run_heartbeat_check 传入的是「标题 | 原因」；按首个竖线拆标题与正文。
    失败抛错（run_heartbeat_check 会如实记 sent=0），绝不假装已发。
    """
    from application.notification import get_notification_facade

    raw = str(text or "").strip()
    title, _, body = raw.partition("|")
    title = (title.strip() or "【盯盘引擎】告警")
    content = (body.strip() or title)
    ok = get_notification_facade().send_card(title=title, content=content, urgency='high')
    if not ok:
        raise RuntimeError('飞书 send_card 返回 False（盯盘告警未送达）')
    return True


def send_watch_receipt(payload: Dict[str, Any]) -> bool:
    """三段回执的真实投递（供 ReceiptService 的 sender 参数）。

    payload 由 ReceiptService._deliver 构造：todo_id/kind/channel/period/message。
    频道（alerts/reports）决定强提醒程度；失败抛错 → delivery_status=failed（如实）。
    """
    from application.notification import get_notification_facade

    data = payload or {}
    kind = str(data.get('kind') or '').strip().lower()
    channel = str(data.get('channel') or '').strip()
    message = str(data.get('message') or '').strip()
    title = '📋 盯盘回执 · %s' % _KIND_LABELS.get(kind, kind or '-')
    content = "**频道**：%s\n%s" % (channel or "-", message or "(无正文)")
    urgency = 'high' if channel == 'alerts' else 'normal'
    ok = get_notification_facade().send_card(title=title, content=content, urgency=urgency)
    if not ok:
        raise RuntimeError('飞书 send_card 返回 False（盯盘回执未送达）')
    return True
