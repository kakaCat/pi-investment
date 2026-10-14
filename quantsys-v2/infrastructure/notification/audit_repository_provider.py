"""通知外发审计仓储的装配出口（组合根，infrastructure 侧）。

**为什么在这里装配**（REQ-261007101318-c392 外发审计）：
`application/notification/notification_factory.py` 需要 `NotificationAuditRepository`，
但 application 层不得直连 adapters（分层门禁 `application → adapters`，见
`tools/analyze_layer_violations.py` 与 `.git-hooks/pre-commit` 的 ratchet）。
把"端口 → 具体实现"的绑定收在 infrastructure（本仓既有的组合点：22 个 infra 文件
就是这样引用 adapters 的），application 只调用本函数。

**契约**：延迟导入具体 adapter——保持本模块 import 期零 adapters 依赖；
装配失败由调用方（factory）降级为 `repository=None`，不得打断通知栈。
"""
from __future__ import annotations

from typing import Any


def create_notification_audit_repository() -> Any:
    """创建外发审计仓储实例（`NotificationRepository` 端口的外发审计实现）。

    延迟导入：具体 adapter 只在本函数被调用时才加载，application 侧因此
    看不到 adapters 依赖，也不增加 import 期负担。

    Returns:
        装配好的审计仓储实例；导入/构造异常由调用方捕获并降级。
    """
    from adapters.outbound.repositories.notification_audit_repository import (
        NotificationAuditRepository,
    )

    return NotificationAuditRepository()


__all__ = ['create_notification_audit_repository']
