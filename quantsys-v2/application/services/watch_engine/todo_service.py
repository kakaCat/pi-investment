"""盯盘待办应用服务（REQ-c9f899 t5，2026-09-18）

闭环状态机的唯一操作面（R2/I3/I4）：把 domain 的**纯判定**（route_owner 的归属 /
终态枚举）与**持久化**（IWatchTodoRepository）编排到一起，并做终态校验。

分层纪律（architecture.md §2）：级别判定 / 账户路由 / 终态校验规则本身都在 domain；
本服务只做编排 + 校验的**执行**（不新造第二份映射表）。

三条不可绕过的规则：

1) **策略账户不建待办**（R3/I5）：route_owner(account).out_of_scope 为真 → 拒绝。
   注意策略账户的 autonomy='not_applicable' **不符合** quant.watch_todos.autonomy 的
   DB CHECK；正确处置是**不建**，而不是把它改写成 remind_only 蒙混过关
   （那会让策略账户凭空产生盯盘待办）。防守型兜底：autonomy 不落在
   (autonomous, remind_only) 时抛 WatchTodoInvalidAutonomy 响亮失败。
   空账户（数据缺陷）**照常建**（is_data_defect=True，autonomy=remind_only）：数据缺陷
   不阻断闭环，否则"补归属前没人管"正是要修的滞留（I1）。

2) **close 四条校验**（违反即抛领域异常；路由层映射 400/409，见 interfaces §4）：
   a. terminal ∈ (handled, ignored, expired)                → WatchTodoInvalidTerminal（400）
   b. terminal=ignored 必须给 next_condition                → WatchTodoMissingNextCondition（400）
   c. 已终态再次关闭                                        → WatchTodoAlreadyClosed（409）
   d. flow_state=L3 且 action_kind ∈ (trade, rule_change)
      必须给 decision_audit_id                              → WatchTodoMissingAudit（400，I4）

3) **claim 只在未终态时生效**：与仓储的 WHERE terminal IS NULL 双保险；仓储返回 None
   （并发被抢先收敛）时抛 WatchTodoAlreadyClosed，绝不静默成功。
"""
from typing import Any, List, Optional

import structlog

from domain.watch.ports import (
    TODO_ALLOWED_AUTONOMY,
    TODO_AUDIT_ACTION_KINDS,
    TODO_FLOW_STATES,
    TODO_TERMINALS,
    IWatchTodoRepository,
    WatchTodoAlreadyClosed,
    WatchTodoInvalidAutonomy,
    WatchTodoInvalidTerminal,
    WatchTodoMissingAudit,
    WatchTodoMissingNextCondition,
    WatchTodoNotFound,
    WatchTodoOutOfScope,
)
from domain.watch.services.level_resolver import P0, P1
from domain.watch.services.owner_router import route_owner

logger = structlog.get_logger(__name__)

#: 直接进 L3 的级别（architecture.md §4：P0/P1 直达 agent；P2/P3 走 L1→L2→L3）
_L3_LEVELS = (P0, P1)


class TodoService:
    """待办落库 / 认领 / 关闭的编排服务（无状态，仓储由构造注入）"""

    def __init__(self, repo: IWatchTodoRepository, policy: Any = None, *,
                 receipt_service: Any = None, name_resolver: Any = None):
        self._repo = repo
        #: WatchDeliveryPolicy（可注入，缺省由 route_owner 用默认策略）——不缓存账户映射内容
        self._policy = policy
        # REQ-ad0a t5（FR-14）：处置结论回执（可选）。未注入 = 行为与改前一致
        # （close 只收敛不发回执）；注入后 close_and_receipt 在收敛成功时发三要素卡。
        self._receipt_service = receipt_service
        #: StockNameResolver（可选，FR-13）：close 单条解析标的名称，缺失 → 名称缺失标注
        self._name_resolver = name_resolver

    # ── 创建 ────────────────────────────────────────────────

    def create(self, symbol: str, *, level: str, sla_seconds: int, due_at: Any,
               account: Optional[str] = None, rule_id: Optional[int] = None,
               trigger_id: Optional[int] = None, flow_state: Optional[str] = None,
               action_kind: Optional[str] = None) -> Any:
        """落一条待办：账户 → 归属路由（out_of_scope 拒绝），并派生 flow_state

        flow_state 缺省按级别派生（architecture §4）：P0/P1 → L3（直达 agent），
        P2/P3 → L1（先通知，靠 SLA/认领推进）。显式传入则以其为准（过渡期兼容）。

        owner_kind/owner_ref/autonomy 一律取自 route_owner，**不接受调用方覆盖**——
        账户是责任归属的唯一事实源（R3/I5），调用方不该能"手动指定接收者"。
        """
        route = route_owner(account, self._policy)
        if route.out_of_scope:
            raise WatchTodoOutOfScope(
                f'账户 {account!r} 盯盘不介入（out_of_scope），不建待办：{route.reason}')

        autonomy = self._allowed_autonomy(route.autonomy)
        state = self._resolve_flow_state(flow_state, level)

        todo = self._repo.create(
            symbol=symbol, rule_id=rule_id, trigger_id=trigger_id, account=account,
            level=level, flow_state=state, owner_kind=route.owner_kind,
            owner_ref=route.owner_ref, autonomy=autonomy, sla_seconds=sla_seconds,
            due_at=due_at, action_kind=action_kind,
        )
        if todo is None:
            # 仓储契约是"失败抛错"；返回 None 说明实现坏了——不得当成创建成功
            raise RuntimeError('待办创建失败：仓储返回 None（契约要求失败抛错）')
        logger.info('盯盘待办已建', todo_id=todo.id, symbol=symbol, level=level,
                    flow_state=state, account=account, owner_kind=route.owner_kind,
                    owner_ref=route.owner_ref, autonomy=autonomy)
        return todo

    # ── 认领 ────────────────────────────────────────────────

    def claim(self, todo_id: int, owner_ref: str, *, now: Any = None) -> Any:
        """认领待办（L1→L2）。不存在→NotFound(404)；已终态→AlreadyClosed(409)。"""
        current = self._repo.get(todo_id)
        if current is None:
            raise WatchTodoNotFound(f'待办 {todo_id} 不存在')
        if getattr(current, 'terminal', None):
            raise WatchTodoAlreadyClosed(
                f'待办 {todo_id} 已收敛（terminal={current.terminal}），不可认领')

        claimed = self._repo.claim(todo_id, owner_ref, now=now)
        if claimed is None:
            # 与并发关闭竞争：仓储的 WHERE terminal IS NULL 未命中
            raise WatchTodoAlreadyClosed(f'待办 {todo_id} 已在认领前收敛，认领未生效')
        return claimed

    # ── 关闭 ────────────────────────────────────────────────

    def close(self, todo_id: int, terminal: str, *, close_reason: Optional[str] = None,
              next_condition: Optional[str] = None, action_kind: Optional[str] = None,
              decision_audit_id: Optional[str] = None, closed_by: Optional[str] = None,
              now: Any = None) -> Any:
        """收敛待办（终态校验见模块 docstring 的四条规则）。

        校验顺序：枚举 → ignored 的 NEXT → 存在性 → 已终态 → L3 动作审计。
        （先校输入再查库：请求解析错误是调用方问题，与库内状态无关。）
        """
        terminal_value = str(terminal or '').strip().lower()
        if terminal_value not in TODO_TERMINALS:
            raise WatchTodoInvalidTerminal(
                f'terminal={terminal!r} 不在 {list(TODO_TERMINALS)} 内')

        next_value = str(next_condition or '').strip() or None
        if terminal_value == 'ignored' and not next_value:
            raise WatchTodoMissingNextCondition(
                'terminal=ignored 必须给 next_condition（下次什么条件下才动，I4）')

        current = self._repo.get(todo_id)
        if current is None:
            raise WatchTodoNotFound(f'待办 {todo_id} 不存在')
        if getattr(current, 'terminal', None):
            raise WatchTodoAlreadyClosed(
                f'待办 {todo_id} 已是终态 {current.terminal}，不可重复关闭（I3）')

        action = str(action_kind or '').strip() or None
        flow_state = str(getattr(current, 'flow_state', '') or '').strip().upper()
        audit_id = str(decision_audit_id or '').strip() or None
        if flow_state == 'L3' and action in TODO_AUDIT_ACTION_KINDS and not audit_id:
            raise WatchTodoMissingAudit(
                f'L3 待办以 {action} 关闭必须带 decision_audit_id（I4：动作必须可核验）')

        closed = self._repo.close(
            todo_id, terminal_value, close_reason=close_reason, next_condition=next_value,
            action_kind=action, decision_audit_id=audit_id, closed_by=closed_by, now=now,
        )
        if closed is None:
            raise WatchTodoAlreadyClosed(f'待办 {todo_id} 已在关闭前收敛，关闭未生效')
        logger.info('盯盘待办已收敛', todo_id=todo_id, terminal=terminal_value,
                    action_kind=action, decision_audit_id=audit_id, closed_by=closed_by)
        return closed

    def close_and_receipt(self, todo_id: int, terminal: str, *,
                          close_reason: Optional[str] = None,
                          next_condition: Optional[str] = None,
                          action_kind: Optional[str] = None,
                          decision_audit_id: Optional[str] = None,
                          closed_by: Optional[str] = None,
                          now: Any = None) -> Any:
        """收敛 + 处置结论回执（REQ-260924104605-ad0a t5，FR-14）。

        返回 (todo, receipt_outcome|None)。receipt_service 未注入时等价 close()、
        outcome 为 None（**行为与改前完全一致**，验收锚点）。回执发送/落库异常
        不拖垮已成功的收敛：响亮记日志、outcome=None——收敛是闭环主线，回执是通知，
        通知失败绝不能让一次已经生效的处置看起来失败。
        重复 close 在 close() 的已终态校验处抛 WatchTodoAlreadyClosed（409），
        根本不会走到回执——重复处置不重复发送。
        """
        closed = self.close(todo_id, terminal, close_reason=close_reason,
                            next_condition=next_condition, action_kind=action_kind,
                            decision_audit_id=decision_audit_id, closed_by=closed_by,
                            now=now)
        if self._receipt_service is None:
            return closed, None
        try:
            outcome = self._receipt_service.result(
                closed, terminal=str(terminal or '').strip().lower() or None,
                name=self._resolve_name(closed),
                close_reason=close_reason, next_condition=next_condition,
                action_kind=action_kind)
        except Exception as e:  # noqa: BLE001 - 回执异常不拖垮已成功的收敛
            logger.error('处置结论回执失败（收敛已生效，回执丢失记日志）',
                         todo_id=todo_id, error=str(e))
            outcome = None
        return closed, outcome

    def _resolve_name(self, todo: Any) -> Optional[str]:
        """单条标的名称解析（FR-13）；未接线/异常 → None（渲染层如实标名称缺失）。"""
        if self._name_resolver is None:
            return None
        try:
            symbol = str(getattr(todo, 'symbol', '') or '')
            names = self._name_resolver.resolve_batch([symbol]) or {}
            return names.get(symbol.split('.')[0].strip())
        except Exception as e:  # noqa: BLE001 - 解析失败降级名称缺失，不打断收敛
            logger.error('close 回执名称解析异常（降级名称缺失）', error=str(e))
            return None

    # ── 读取（透传）────────────────────────────────────────

    def list(self, level: Optional[str] = None, account: Optional[str] = None,
             limit: int = 100, *, flow_state: Optional[str] = None,
             terminal: Optional[str] = None) -> List[Any]:
        """列出待办（GET /api/watch/todos 的读侧；过滤语义见仓储端口）"""
        return self._repo.list_pending(level=level, account=account, limit=limit,
                                       flow_state=flow_state, terminal=terminal)

    def overdue(self, now: Any = None, limit: int = 100) -> List[Any]:
        """到期未收敛待办（巡检读侧；I1 晋升依据）"""
        return self._repo.list_overdue(now=now, limit=limit)

    # ── 内部 ────────────────────────────────────────────────

    @staticmethod
    def _allowed_autonomy(autonomy: Any) -> str:
        """autonomy 只允许 autonomous/remind_only（DB CHECK 一致）

        失败是**响亮**的：把 not_applicable 悄悄改写成 remind_only 会让策略账户
        产生本不该存在的待办（见模块 docstring 第 1 条）。
        """
        value = str(autonomy or '').strip()
        if value not in TODO_ALLOWED_AUTONOMY:
            raise WatchTodoInvalidAutonomy(
                f'autonomy={value!r} 不符合 watch_todos CHECK（只允许 '
                f'{list(TODO_ALLOWED_AUTONOMY)}）；策略账户应由 out_of_scope 先行拒绝')
        return value

    @staticmethod
    def _resolve_flow_state(flow_state: Optional[str], level: Any) -> str:
        """flow_state：显式优先，否则按级别派生（P0/P1→L3，其余→L1）"""
        if flow_state is not None:
            state = str(flow_state).strip().upper()
            if state not in TODO_FLOW_STATES:
                raise ValueError(
                    f'flow_state={flow_state!r} 不在 {list(TODO_FLOW_STATES)} 内')
            return state
        lvl = str(level or '').strip().upper()
        return 'L3' if lvl in _L3_LEVELS else 'L1'
