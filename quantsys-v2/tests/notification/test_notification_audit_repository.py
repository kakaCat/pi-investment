"""外发审计回归锁（REQ-261007101318-c392 FR-3）。

**它回答的问题**（用户 2026-10-07 用一张卡把这个问题问了出来）：
这张「盯盘触发 - 688525」是谁、在哪台机器、哪个进程、几点、为哪条规则发的？
——在本次修复前，答案是"查不到"：`watch_rules` / `watch_triggers` / 日志全无，
因为 `NotificationService(repository=None)` **外发零持久化**。

本文件锁定三条：
  1. 写进去：一次外发落一行，字段齐（标题 / 摘要 / 状态 / 渠道 / 送达 / 发送方）；
  2. 幂等：同一 notification_id 在生命周期里 save 多次 → **仍只有一行**（末态覆盖）；
  3. 写失败不打挂通知：仓储抛错时 `save` 返回 False 而不上抛（审计是增益不是前提）。
"""
from domain.notification.models.notification import (
    Notification, NotificationPriority, NotificationStatus, NotificationType,
)
from adapters.outbound.repositories.notification_audit_repository import (
    NotificationAuditRepository,
)


def _notification(**overrides):
    base = dict(
        notification_type=NotificationType.WATCH_TRIGGERED,
        title='盯盘触发 - 688525',
        content='现价 192.35 ≤ 阈值 218.24（下破）',
        priority=NotificationPriority.HIGH,
        variables={'symbol': '688525.SH', 'name': '佰维存储', 'rule_id': 501,
                   'intent': 'exit_stop', 'trigger_level': 'L1',
                   'watch_level': 'P1', 'closed_loop': False},
        metadata={'sender_id': 'v2-watch@test-host#4321',
                  'delivery_channel': 'feishu', 'delivered': True},
    )
    base.update(overrides)
    return Notification(**base)


def _row(notification_id):
    from infrastructure.persistence.orm import get_session
    from sqlalchemy import text
    session = get_session()
    return session.execute(text(
        "select notification_id, notification_type, title, content_digest, "
        "       content_excerpt, status, delivery_channel, delivered, sender_id "
        "from quant.notification_audit where notification_id = :n"),
        {'n': notification_id}).first()


def test_audit_row_records_who_sent_what(db_session_cleanup=None):
    """一次外发 → 一行审计，且字段足以回答"谁在几点发了什么"。"""
    repo = NotificationAuditRepository()
    notif = _notification()
    assert repo.save(notif) is True

    row = _row(notif.notification_id)
    assert row is not None, '外发必须落一行审计（FR-3 的核心判据）'
    assert row[1] == 'watch_triggered'
    assert row[2] == '盯盘触发 - 688525'
    assert row[3], '必须有正文摘要（sha1）供核对发的是不是这张卡'
    assert row[4] == '现价 192.35 ≤ 阈值 218.24（下破）'
    assert row[6] == 'feishu' and row[7] is True
    assert row[8] == 'v2-watch@test-host#4321', '必须有发送方标识（跨机/跨进程可分辨）'


def test_audit_is_upsert_not_append():
    """生命周期多次 save → 只有一行，末态覆盖（否则每次通知写 2~3 行噪声）。"""
    repo = NotificationAuditRepository()
    notif = _notification()
    assert repo.save(notif) is True                      # mark_sending 时
    notif.status = NotificationStatus.SENT
    notif.metadata = {**notif.metadata, 'delivered': True}
    assert repo.save(notif) is True                      # mark_sent 时

    from infrastructure.persistence.orm import get_session
    from sqlalchemy import text
    count = get_session().execute(text(
        "select count(*) from quant.notification_audit where notification_id = :n"),
        {'n': notif.notification_id}).scalar()
    assert count == 1, f'同一通知只能有一行审计，实测 {count} 行'
    assert _row(notif.notification_id)[5] == 'sent'


def test_audit_failure_never_breaks_notification(monkeypatch):
    """审计写失败 → `save` 返回 False 且**不上抛**（不许把通知链路打挂）。"""
    repo = NotificationAuditRepository()

    def boom(*args, **kwargs):
        raise RuntimeError('模拟审计库不可用')

    monkeypatch.setattr(repo, '_params', boom)
    assert repo.save(_notification()) is False           # 自吞 + 如实回报


def test_service_path_stamps_channel_and_delivered_into_audit():
    """贯穿 `NotificationService` 全链：渠道与送达结果确实进了审计行。

    盯盘卡实际走的是**降级路径**（agent 失败 → 飞书），所以这里用
    `send_with_fallback` 复现该形态，断言审计里记的是"最后从哪个渠道出去"。
    """
    from unittest.mock import Mock
    from domain.notification.models.channel import NotificationChannel, ChannelResult
    from domain.notification.policies.notification_policy import NotificationPolicy
    from domain.notification.services.notification_service import NotificationService

    primary = Mock(spec=NotificationChannel)
    primary.get_name.return_value = 'agent'
    primary.send.return_value = ChannelResult.error('Agent OS 不可达')

    fallback = Mock(spec=NotificationChannel)
    fallback.get_name.return_value = 'feishu'
    fallback.send.return_value = ChannelResult.ok('飞书发送成功')

    service = NotificationService(channels=[primary, fallback],
                                  policy=NotificationPolicy(),
                                  repository=NotificationAuditRepository())
    notif = _notification(metadata={'sender_id': 'v2-watch@test-host#4321'})
    service.send_with_fallback(notif, 'agent', 'feishu')

    row = _row(notif.notification_id)
    assert row is not None, '走服务层也必须落审计'
    assert row[6] == 'feishu', f'审计必须记"最后从哪个渠道出去"（实测 {row[6]}）'
    assert row[7] is True, '送达结果必须进审计'
    assert row[8] == 'v2-watch@test-host#4321', '发送方标识必须进审计（FR-3 核心）'


def test_factory_degrades_to_none_when_audit_repo_unavailable(monkeypatch):
    """装配失败必须降级为 repository=None（通知照发），不得把异常抛进通知栈。

    设计 §6 登记的未覆盖项：审计仓储装配失败的降级路径此前只有代码、没有用例。
    """
    import adapters.outbound.repositories.notification_audit_repository as audit_mod
    from application.notification.notification_factory import NotificationFactory

    class _Boom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('模拟审计仓储装配失败（表缺失 / DB 不可用）')

    monkeypatch.setattr(audit_mod, 'NotificationAuditRepository', _Boom)
    # 不建渠道：避免健康检查走网络（本用例只验装配降级）
    monkeypatch.setattr(NotificationFactory, '_create_channels',
                        staticmethod(lambda settings, formatters: []))

    facade = NotificationFactory.create_from_settings()
    assert facade.service.repository is None, '装配失败必须降级为 None，而不是抛错'

    # 无渠道时发送应"失败但不抛"——证明降级没有把通知栈变成异常源
    from domain.notification.models.notification import Notification, NotificationType
    result = facade.service.send(Notification(notification_type=NotificationType.SYSTEM_ALERT,
                                              title='降级自检', content='不应上抛'))
    assert result.success is False
