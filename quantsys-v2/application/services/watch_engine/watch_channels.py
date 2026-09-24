"""盯盘闭环的真实通知通道（REQ-c9f899 t12，2026-09-18）

把心跳告警与三段回执接到 NotificationFacade（飞书）——此前 t10/t6 的 sender 默认
log-only，告警只在日志里、人看不到（§6 待接线项 6/10）。

纪律（对齐 pi-investment/CLAUDE.md 通知架构铁律）：
  · 只经 application.notification.get_notification_facade()；禁止直接 import
    infrastructure.notification.channels.*，禁止 requests.post(飞书 webhook)。
  · 发送失败必须抛错，不许静默返回 False：run_heartbeat_check 用 sender 是否抛错
    统计 sent；ReceiptService 用 sender 是否抛错 决定 delivery_status=sent/failed。
    若这里吞掉失败返回 False，回执会被记成 sent（假成功），心跳会把失败当成已送达。

路由（REQ-260924104605-ad0a t3，FR-3）：回执/告警经 facade.send_watch_receipt 携带
os_channel（逻辑频道码）——timeout/P0 → risk_stop，其余 → watch_symbol；AgentChannel
把它转发给 Agent OS 网关，按 notification_channels 表投递到盯盘群（FR-1 已配置
10 个盯盘频道指向专用 webhook）；Agent OS 不可达时降级直飞书兜底（不丢消息）。
卡片正文**不再外露频道码**（FR-12：「频道：」属内部字段）。
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
    ok = get_notification_facade().send_watch_receipt(
        title=title, content=content, os_channel='watch_symbol', urgency='high')
    if not ok:
        raise RuntimeError('盯盘告警未送达（agent→feishu 双路失败）')
    return True


def send_watch_receipt(payload: Dict[str, Any]) -> bool:
    """三段回执的真实投递（供 ReceiptService 的 sender 参数）。

    payload 由 ReceiptService._deliver 构造：todo_id/kind/channel/period/message/level。
    REQ-ad0a t3（FR-3）：os_channel 逻辑频道码直透 AgentChannel ——
    timeout/P0 → risk_stop（盯盘群内高优位），其余 → watch_symbol；
    失败抛错 → delivery_status=failed（如实）。
    """
    from application.notification import get_notification_facade

    data = payload or {}
    kind = str(data.get('kind') or '').strip().lower()
    level = str(data.get('level') or '').strip().upper()
    channel = str(data.get('channel') or '').strip()
    message = str(data.get('message') or '').strip()
    # 聚合卡（t4 flush_grouped）以 items 多条传入：os_channel 由调用方显式给出
    os_channel = str(data.get('os_channel') or '').strip()
    if not os_channel:
        os_channel = ('risk_stop' if (kind == 'timeout' or level == 'P0')
                      else 'watch_symbol')
    title = '📋 盯盘回执 · %s' % _KIND_LABELS.get(kind, kind or '-')
    # FR-12：频道码不外露（内部字段不进用户视野）
    content = message or "(无正文)"
    urgency = 'high' if (kind == 'timeout' or channel == 'alerts' or level == 'P0') else 'normal'
    ok = get_notification_facade().send_watch_receipt(
        title=title, content=content, os_channel=os_channel, urgency=urgency)
    if not ok:
        raise RuntimeError('盯盘回执未送达（agent→feishu 双路失败）')
    return True
