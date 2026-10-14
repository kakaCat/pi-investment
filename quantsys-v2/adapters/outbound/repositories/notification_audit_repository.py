"""外发审计仓储（REQ-261007101318-c392 FR-3）。

**回答的问题**：谁在几点、为哪条规则、发了什么标题、走哪个渠道、送达没有。

**为什么落在渠道服务层**（而不是引擎的 notifier 层）：用户 2026-10-07 收到的那张
688525 卡，在 `watch_rules` / `watch_triggers` / 日志里**全都查不到**——它根本不是引擎
那条路径发的。只审计引擎 = 恰好漏掉需要审计的那一类。挂在 `NotificationService`
（所有外发必经）才能覆盖：引擎、脚本、异地实例、手工调用。

**契约**：
  · `save(notification)` **永不抛错**——审计是增益，写失败只记 error 日志；
    绝不允许"发不出去"变成"没发出去还不知道"（更不允许审计把通知链路打挂）；
  · **一通知一行**：`NotificationService` 会在 mark_sending / mark_sent / mark_failed
    处多次 save，故按 `notification_id` upsert，末态即最终结果；
  · 正文只存 **sha1 摘要 + 前 500 字**：够核对"是不是这张卡"，又不让审计表膨胀。
"""
from __future__ import annotations

import hashlib
import json

import structlog
from sqlalchemy import text

from infrastructure.persistence.orm import get_session

logger = structlog.get_logger(__name__)

#: 正文摘录上限（字符）。够人眼核对面目，不整存长文。
EXCERPT_LIMIT = 500

_UPSERT = text("""
INSERT INTO quant.notification_audit (
    notification_id, notification_type, priority, title,
    content_digest, content_excerpt, status, error,
    delivery_channel, delivered, sender_id, payload_meta, updated_at
) VALUES (
    :notification_id, :notification_type, :priority, :title,
    :content_digest, :content_excerpt, :status, :error,
    :delivery_channel, :delivered, :sender_id, CAST(:payload_meta AS JSONB), now()
)
ON CONFLICT (notification_id) DO UPDATE SET
    status = EXCLUDED.status,
    error = EXCLUDED.error,
    delivery_channel = EXCLUDED.delivery_channel,
    delivered = EXCLUDED.delivered,
    sender_id = EXCLUDED.sender_id,
    payload_meta = EXCLUDED.payload_meta,
    updated_at = now()
""")

#: 进审计的 variables 白名单（避免把整份模板变量灌进审计表）
_VARIABLE_KEYS = ('symbol', 'name', 'rule_id', 'intent', 'trigger_level',
                  'watch_level', 'closed_loop', 'watch_channel')
#: 进审计的 metadata 白名单
_META_KEYS = ('sender_id', 'wake_target', 'delivery_channel', 'delivered')


class NotificationAuditRepository:
    """`NotificationRepository` 端口的外发审计实现（只写不读，读走 SQL/看板）。"""

    def save(self, notification) -> bool:
        """写一条外发审计（幂等 upsert）。**任何失败都自吞**，返回是否写入成功。"""
        session = None
        try:
            session = get_session()
            session.execute(_UPSERT, self._params(notification))
            session.commit()
            return True
        except Exception as e:  # noqa: BLE001 - 审计失败绝不许打挂通知
            logger.error('外发审计写入失败（通知不受影响）',
                         notification_id=getattr(notification, 'notification_id', None),
                         error=str(e))
            if session is not None:
                try:
                    session.rollback()
                except Exception:  # noqa: BLE001 - 回滚失败也不再上抛
                    pass
            return False

    # ── 内部 ────────────────────────────────────────────────

    @staticmethod
    def _digest(notification) -> str:
        raw = f'{getattr(notification, "title", "")}\n{getattr(notification, "content", "")}'
        return hashlib.sha1(raw.encode('utf-8')).hexdigest()

    def _payload_meta(self, notification) -> dict:
        """审计用的结构化上下文：variables + metadata 的**白名单**子集。"""
        variables = getattr(notification, 'variables', None) or {}
        meta = getattr(notification, 'metadata', None) or {}
        payload = {k: variables.get(k) for k in _VARIABLE_KEYS if k in variables}
        payload.update({k: meta.get(k) for k in _META_KEYS if k in meta})
        return payload

    def _params(self, notification) -> dict:
        ntype = getattr(notification, 'notification_type', None)
        status = getattr(notification, 'status', None)
        priority = getattr(notification, 'priority', None)
        meta = getattr(notification, 'metadata', None) or {}
        content = str(getattr(notification, 'content', '') or '')
        return {
            'notification_id': str(getattr(notification, 'notification_id', '') or ''),
            'notification_type': str(getattr(ntype, 'value', ntype) or '')[:32],
            'priority': str(getattr(priority, 'value', priority) or '')[:16],
            'title': str(getattr(notification, 'title', '') or '')[:255],
            'content_digest': self._digest(notification),
            'content_excerpt': content[:EXCERPT_LIMIT],
            'status': str(getattr(status, 'value', status) or '')[:20],
            'error': getattr(notification, 'error_message', None),
            'delivery_channel': meta.get('delivery_channel'),
            'delivered': meta.get('delivered'),
            'sender_id': meta.get('sender_id'),
            'payload_meta': json.dumps(self._payload_meta(notification),
                                       ensure_ascii=False, default=str),
        }
