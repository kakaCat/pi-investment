"""规则变更审计仓储适配器（REQ-c9f899 R6 / t8，2026-09-18）

实现 domain/watch/ports.py 的 IWatchRuleChangeRepository（data-model.md §4 的
quant.watch_rule_changes）：

  · record        —— **追加写**一条规则变更（自愈抑噪 / agent 修复 / 用户确认后修复）；
  · exists_since  —— 自愈日幂等判据：该规则自 since 起是否已有某类变更；
  · list_by_rule  —— 按规则取变更历史（时间倒序），供复盘"这条规则被谁改过几次"。

按 ADR-001（六边形架构）：SQL/ORM 只允许出现在适配器层——应用层（NoiseSelfHealService）
只依赖端口。失败语义与 watch_receipt_repository 一致：**读写失败一律向上抛**
（回滚线程 scoped session 后 re-raise）。

契约硬化（写库前、触碰 session 之前）：
  · reason **必填非空**——规则变更的理由是复盘与反向应用的唯一凭据，空理由必须响亮拒绝，
    而不是让列 NOT NULL 在提交时才报错（那时异常语义与调用方错误已脱节）；
  · changed_by 必须是 agent/user/system（与迁移 20260918 的 CHECK 同集），大小写归一。
"""
from datetime import datetime
from typing import Any, List, Optional

import structlog

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models.watch_todo import WatchRuleChange

logger = structlog.get_logger(__name__)

#: 与迁移 20260918_watch_todo_loop.py 的 watch_rule_changes.changed_by CHECK 同集
CHANGED_BY_VALUES = ('agent', 'user', 'system')


def _iso(value):
    """datetime → ISO 字符串（None 透传）"""
    return value.isoformat() if value is not None else None


def change_to_dict(change: Any) -> dict:
    """规则变更记录 → API 响应 dict（snake_case，与 todo_to_dict 同风格）

    ⚠️ created_at 一律 ISO 字符串：JSONResponse 无法序列化 datetime（会 500）。
    """
    return {
        'id': change.id,
        'rule_id': change.rule_id,
        'changed_by': change.changed_by,
        'change_kind': change.change_kind,
        'before': change.before,
        'after': change.after,
        'reason': change.reason,
        'trigger_id': change.trigger_id,
        'todo_id': change.todo_id,
        'decision_audit_id': change.decision_audit_id,
        'created_at': _iso(change.created_at),
    }


class WatchRuleChangeRepository(BaseORMRepository[WatchRuleChange]):
    """IWatchRuleChangeRepository 的 PostgreSQL 实现（quant.watch_rule_changes）"""

    model = WatchRuleChange

    # ── 写入 ────────────────────────────────────────────────

    def record(self, rule_id: int, changed_by: str, change_kind: str, before: Any = None,
               after: Any = None, reason: str = '', trigger_id: Optional[int] = None,
               todo_id: Optional[int] = None,
               decision_audit_id: Optional[str] = None) -> WatchRuleChange:
        """追加写一条规则变更（审计只增不改）。

        change_kind 的**枚举校验在应用层**（noise_policy.CHANGE_KINDS / REPAIR_ACTIONS）——
        DB 的 change_kind 列没有 CHECK，这里只做"非空"兜底，避免适配器承担策略白名单
        （那是 domain 的职责，两处白名单 = 两份真相）。
        """
        reason_value = str(reason or '').strip()
        if not reason_value:
            raise ValueError('reason 必填：规则变更必须写明理由（R6/R-020，空理由无法复盘）')
        changed_by_value = str(changed_by or '').strip().lower()
        if changed_by_value not in CHANGED_BY_VALUES:
            raise ValueError(
                f'changed_by={changed_by!r} 不在 {list(CHANGED_BY_VALUES)} 内'
                '（与 watch_rule_changes.changed_by CHECK 同集）')
        kind_value = str(change_kind or '').strip().lower()
        if not kind_value:
            raise ValueError('change_kind 必填：规则变更必须说明改了什么')

        change = WatchRuleChange(
            rule_id=rule_id, changed_by=changed_by_value, change_kind=kind_value,
            before=before, after=after, reason=reason_value, trigger_id=trigger_id,
            todo_id=todo_id, decision_audit_id=decision_audit_id,
        )
        try:
            session = self.session
            session.add(change)
            session.commit()
            session.refresh(change)
        except Exception as e:  # noqa: BLE001 - 失败必须响亮
            logger.error('规则变更落库失败', rule_id=rule_id, change_kind=kind_value,
                         error=str(e))
            self._safe_rollback()
            raise
        return change

    # ── 读取 ────────────────────────────────────────────────

    def exists_since(self, rule_id: int, change_kind: str, since: datetime) -> bool:
        """该规则自 since 起是否已有某类变更（scan 的日幂等判据）。

        失败**向上抛**（绝不 catch 成 False）：静默 False 会让"审计库坏了"变成"今天还没
        记过"，同一天重复建「修规则」待办并重复写审计——噪声被放大而不是暴露。
        """
        kind_value = str(change_kind or '').strip().lower()
        if not kind_value:
            raise ValueError('change_kind 必填：空值无法判定幂等（exists_since 不做猜测）')
        try:
            row = (
                self.session.query(WatchRuleChange.id)
                .filter(WatchRuleChange.rule_id == rule_id,
                        WatchRuleChange.change_kind == kind_value,
                        WatchRuleChange.created_at >= since)
                .first()
            )
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise
        return row is not None

    def list_by_rule(self, rule_id: int, limit: int = 50) -> List[WatchRuleChange]:
        """按规则取变更历史（created_at 倒序、同刻按 id 倒序）"""
        try:
            return (
                self.session.query(WatchRuleChange)
                .filter(WatchRuleChange.rule_id == rule_id)
                .order_by(WatchRuleChange.created_at.desc(), WatchRuleChange.id.desc())
                .limit(max(1, int(limit)))
                .all()
            )
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise
