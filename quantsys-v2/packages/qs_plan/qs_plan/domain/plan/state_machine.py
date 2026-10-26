"""计划生命周期状态机（纯逻辑，无 I/O）

状态：
  draft     草稿（可改 spec，未编译）
  active    运行中（已编译托管规则，无持仓）
  holding   持仓中（有成交）
  closing   退出中（退出指令已发，等待回执收敛）
  closed    已关闭（仓位清零或确认无仓）
  archived  已归档（closed 后收尾）
  paused    暂停（规则停用、保留状态）

三条纪律：
1. 非法迁移**拒绝并给可读原因**，绝不静默改写（调用方据此返回 422）；
2. 有持仓时关闭必须给 close_disposition（持仓处置方案）——否则计划会「关了但仓还在」；
3. closed → archived 仅允许在 closed 后（时间门槛由应用层判定，本函数只认状态）。
"""
from typing import Optional, Tuple

STATUS_DRAFT = 'draft'
STATUS_ACTIVE = 'active'
STATUS_HOLDING = 'holding'
STATUS_CLOSING = 'closing'
STATUS_CLOSED = 'closed'
STATUS_ARCHIVED = 'archived'
STATUS_PAUSED = 'paused'

STATUSES = (STATUS_DRAFT, STATUS_ACTIVE, STATUS_HOLDING, STATUS_CLOSING,
            STATUS_CLOSED, STATUS_ARCHIVED, STATUS_PAUSED)

#: 合法迁移表（from → 允许的 to 集合）
LEGAL_TRANSITIONS = {
    STATUS_DRAFT: {STATUS_ACTIVE},
    STATUS_ACTIVE: {STATUS_HOLDING, STATUS_PAUSED, STATUS_CLOSED},
    STATUS_HOLDING: {STATUS_CLOSING, STATUS_PAUSED},
    STATUS_CLOSING: {STATUS_CLOSED, STATUS_HOLDING},
    STATUS_CLOSED: {STATUS_ARCHIVED},
    STATUS_PAUSED: {STATUS_ACTIVE, STATUS_CLOSED},
    STATUS_ARCHIVED: set(),
}

#: 允许「有持仓时直接关闭」的目标状态（必须带处置方案）
_CLOSE_TARGETS = {STATUS_CLOSED, STATUS_CLOSING}


def is_legal_transition(from_status: str, to_status: str) -> bool:
    return to_status in LEGAL_TRANSITIONS.get(from_status, set())


def evaluate_plan_transition(from_status: str, to_status: str, *,
                             has_position: bool = False,
                             has_close_disposition: bool = False,
                             review_overdue: int = 0) -> Tuple[bool, Optional[str]]:
    """状态迁移守卫。返回 (ok, reason)；ok=False 时 reason 是可读拒绝原因。

    参数设计（而不是只传两个状态）是为了让「有持仓关闭」这类**条件边**在守卫里
    一次判完——调用方不需要在服务层再拼一遍条件。
    """
    if from_status not in LEGAL_TRANSITIONS:
        return False, '未知状态：%s' % from_status
    if to_status not in STATUSES:
        return False, '未知目标状态：%s' % to_status
    if from_status == to_status:
        return False, '状态未变化（%s）' % from_status
    if not is_legal_transition(from_status, to_status):
        if from_status == STATUS_ARCHIVED:
            return False, '已归档计划不可再做任何状态变更'
        if from_status == STATUS_CLOSED and to_status == STATUS_ACTIVE:
            return False, '已关闭计划不能重新激活，请新建计划'
        if from_status == STATUS_DRAFT and to_status == STATUS_CLOSED:
            return False, '草稿计划不能直接关闭；请先激活或删除草稿'
        return False, '不允许的状态迁移：%s → %s' % (from_status, to_status)
    if to_status in _CLOSE_TARGETS and has_position and not has_close_disposition:
        return False, '有持仓时必须给出持仓处置方案（close_disposition）才能关闭'
    if to_status == STATUS_ARCHIVED and review_overdue > 0:
        return False, '反思连续缺席 %d 次，先补齐反思再归档' % review_overdue
    return True, None


def next_close_status(has_position: bool) -> str:
    """关闭请求的目标状态：无仓直接 closed，有仓先进 closing。"""
    return STATUS_CLOSING if has_position else STATUS_CLOSED
