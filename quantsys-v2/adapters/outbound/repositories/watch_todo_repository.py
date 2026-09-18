"""盯盘待办仓储适配器（REQ-c9f899 t5，2026-09-18）

实现 domain/watch/ports.py 的 IWatchTodoRepository（interfaces.md §2）：

  · create / get   —— 落待办、按 id 取；
  · claim          —— **只在未终态时生效**（WHERE terminal IS NULL），并把 L1 通知推进到
                      L2 待办（R2：L1 的退出条件 = 有人认领）；已终态返回 None；
  · close          —— **只写终态字段**（terminal/closed_at/close_reason/next_condition/
                      action_kind/decision_audit_id + updated_at），不改身份列；
                      已终态（或并发抢先）返回 None，绝不二次改写（I3）；
  · list_overdue   —— (terminal IS NULL AND due_at < now)，命中
                      idx_watch_todos_overdue(terminal, due_at)，按 due_at 升序（I1 巡检口径）；
  · promote        —— 仅对未终态行生效，置 flow_state 并累加 escalate_count；
  · list_pending   —— 缺省未收敛；支持 level/account/flow_state/terminal 过滤。

按 ADR-001（六边形架构）：**SQL/ORM 只允许出现在适配器层**——应用层（TodoService）
只依赖端口。失败语义与 watch_runtime_state_repository 一致：**读写失败一律向上抛**
（回滚线程 scoped session 后 re-raise），绝不静默返回空值把"查询坏了"伪装成"没有待办"。

关于 closed_by：interfaces.md §2 的 close() 带 closed_by，但 data-model.md §2 的
quant.watch_todos **没有该列**。为避免"参数收下不生效"，此处显式说明：closed_by 只用于
审计日志（structlog），**不落 watch_todos**；关闭者身份的可核验留痕由
close_reason / decision_audit_id 与（t6 的回执表）承担。若后续要给该列落库，必须走迁移
（本任务不改表结构）。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import case, func, update as sa_update

from infrastructure.persistence.orm.base_repository import BaseORMRepository
from infrastructure.persistence.orm.models.watch_todo import WatchTodo

logger = structlog.get_logger(__name__)

#: 待办列表默认/上限（对齐 GET /api/watch/todos 的 limit 语义）
DEFAULT_LIMIT = 100
MAX_LIMIT = 500

def _iso(value):
    """datetime → ISO 字符串（None 透传）"""
    return value.isoformat() if value is not None else None


def todo_to_dict(todo: Any) -> dict:
    """待办记录 → API 响应 dict（snake_case，与 watch_async 的 rule_to_dict 同风格）

    ⚠️ 时间字段一律 ISO 字符串：JSONResponse 无法序列化 datetime（会 500），
    而 watch_async 既有的 *_to_dict 也是这个口径。
    """
    return {
        'id': todo.id,
        'trigger_id': todo.trigger_id,
        'rule_id': todo.rule_id,
        'symbol': todo.symbol,
        'account': todo.account,
        'level': todo.level,
        'flow_state': todo.flow_state,
        'owner_kind': todo.owner_kind,
        'owner_ref': todo.owner_ref,
        'autonomy': todo.autonomy,
        'sla_seconds': todo.sla_seconds,
        'due_at': _iso(todo.due_at),
        'terminal': todo.terminal,
        'close_reason': todo.close_reason,
        'next_condition': todo.next_condition,
        'action_kind': todo.action_kind,
        'decision_audit_id': todo.decision_audit_id,
        'escalate_count': todo.escalate_count,
        'claimed_at': _iso(todo.claimed_at),
        'closed_at': _iso(todo.closed_at),
        'created_at': _iso(todo.created_at),
    }


class WatchTodoRepository(BaseORMRepository[WatchTodo]):
    """IWatchTodoRepository 的 PostgreSQL 实现（quant.watch_todos）"""

    model = WatchTodo

    # ── 写入 ────────────────────────────────────────────────

    def create(self, symbol: str, *, rule_id: Optional[int] = None,
               trigger_id: Optional[int] = None, account: Optional[str] = None,
               level: str, flow_state: str = 'L1', owner_kind: Optional[str] = None,
               owner_ref: Optional[str] = None, autonomy: Optional[str] = None,
               sla_seconds: int, due_at: datetime,
               action_kind: Optional[str] = None) -> WatchTodo:
        todo = WatchTodo(
            symbol=symbol, rule_id=rule_id, trigger_id=trigger_id, account=account,
            level=level, flow_state=flow_state, owner_kind=owner_kind, owner_ref=owner_ref,
            autonomy=autonomy, sla_seconds=sla_seconds, due_at=due_at,
            action_kind=action_kind,
        )
        try:
            session = self.session
            session.add(todo)
            session.commit()
            session.refresh(todo)
        except Exception as e:  # noqa: BLE001 - 失败必须响亮
            logger.error('待办创建失败', symbol=symbol, level=level, error=str(e))
            self._safe_rollback()
            raise
        return todo

    def claim(self, todo_id: int, owner_ref: str, *,
              now: Optional[datetime] = None) -> Optional[WatchTodo]:
        """认领：仅未终态行生效；L1→L2（有人认领 = L1 的退出条件，R2）"""
        stamp = now if now is not None else func.now()
        stmt = (
            sa_update(WatchTodo)
            .where(WatchTodo.id == todo_id, WatchTodo.terminal.is_(None))
            .values(
                owner_ref=owner_ref,
                claimed_at=stamp,
                flow_state=case((WatchTodo.flow_state == 'L1', 'L2'),
                                else_=WatchTodo.flow_state),
                updated_at=func.now(),
            )
            .execution_options(synchronize_session=False)
        )
        try:
            session = self.session
            result = session.execute(stmt)
            session.commit()
        except Exception as e:  # noqa: BLE001
            logger.error('待办认领失败', todo_id=todo_id, error=str(e))
            self._safe_rollback()
            raise
        if not result.rowcount:
            # 不存在或已终态：调用方（TodoService/路由）据 None 区分 404 / 409
            return None
        return self.get(todo_id)

    def close(self, todo_id: int, terminal: str, *, close_reason: Optional[str] = None,
              next_condition: Optional[str] = None, action_kind: Optional[str] = None,
              decision_audit_id: Optional[str] = None, closed_by: Optional[str] = None,
              now: Optional[datetime] = None) -> Optional[WatchTodo]:
        """收敛：只写终态字段；已终态/并发抢先返回 None（绝不二次改写，I3）"""
        stamp = now if now is not None else func.now()
        stmt = (
            sa_update(WatchTodo)
            .where(WatchTodo.id == todo_id, WatchTodo.terminal.is_(None))
            .values(
                terminal=terminal,
                closed_at=stamp,
                close_reason=close_reason,
                next_condition=next_condition,
                action_kind=action_kind,
                decision_audit_id=decision_audit_id,
                updated_at=func.now(),
            )
            .execution_options(synchronize_session=False)
        )
        try:
            session = self.session
            result = session.execute(stmt)
            session.commit()
        except Exception as e:  # noqa: BLE001
            logger.error('待办关闭失败', todo_id=todo_id, terminal=terminal, error=str(e))
            self._safe_rollback()
            raise
        if not result.rowcount:
            return None
        if closed_by:
            # watch_todos 无 closed_by 列（见模块 docstring）：身份只进日志，不落该表
            logger.info('待办已关闭', todo_id=todo_id, terminal=terminal, closed_by=closed_by)
        return self.get(todo_id)

    def promote(self, todo_id: int, to_state: str, *,
                escalate_count: Optional[int] = None,
                now: Optional[datetime] = None) -> Optional[WatchTodo]:
        """晋升：仅未终态行生效；escalate_count 缺省自增 1"""
        values: dict = {
            'flow_state': to_state,
            'updated_at': func.now(),
        }
        values['escalate_count'] = (WatchTodo.escalate_count + 1
                                    if escalate_count is None else escalate_count)
        stmt = (
            sa_update(WatchTodo)
            .where(WatchTodo.id == todo_id, WatchTodo.terminal.is_(None))
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        try:
            session = self.session
            result = session.execute(stmt)
            session.commit()
        except Exception as e:  # noqa: BLE001
            logger.error('待办晋升失败', todo_id=todo_id, to_state=to_state, error=str(e))
            self._safe_rollback()
            raise
        if not result.rowcount:
            return None
        return self.get(todo_id)

    # ── 读取 ────────────────────────────────────────────────

    def get(self, todo_id: int) -> Optional[WatchTodo]:
        try:
            return self.session.query(WatchTodo).filter(WatchTodo.id == todo_id).first()
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise

    def list_overdue(self, now: Optional[datetime] = None, limit: int = DEFAULT_LIMIT) -> List[WatchTodo]:
        """巡检扫描：terminal IS NULL AND due_at < now（now 缺省用数据库 NOW()）

        WHERE 顺序即索引口径：idx_watch_todos_overdue(terminal, due_at)。
        """
        try:
            query = (
                self.session.query(WatchTodo)
                .filter(WatchTodo.terminal.is_(None))
                .filter(WatchTodo.due_at < (now if now is not None else func.now()))
                .order_by(WatchTodo.due_at.asc())
                .limit(_bounded_limit(limit))
            )
            return query.all()
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise

    def stats(self, *, now: Optional[datetime] = None) -> Dict[str, Any]:
        """闭环规模统计（GET /api/watch/metrics 的 todo 字段，REQ-c9f899 t12 §6-项7）。

        返回：pending（未收敛总数）/ by_level / by_flow_state（均只统计未收敛）/
        created_today / closed_today / terminal_rate_today（= closed/created；
        当日无创建 → None，**不拿 0 冒充事实**，R-013）。失败向上抛，由调用方记 degraded。
        """
        at = now or datetime.now()
        day_start = datetime.combine(at.date(), datetime.min.time())
        try:
            session = self.session
            pending = int(
                session.query(func.count()).select_from(WatchTodo)
                .filter(WatchTodo.terminal.is_(None)).scalar() or 0)
            by_level = {
                str(row[0]): int(row[1]) for row in
                session.query(WatchTodo.level, func.count())
                .filter(WatchTodo.terminal.is_(None))
                .group_by(WatchTodo.level).all()
            }
            by_flow = {
                str(row[0]): int(row[1]) for row in
                session.query(WatchTodo.flow_state, func.count())
                .filter(WatchTodo.terminal.is_(None))
                .group_by(WatchTodo.flow_state).all()
            }
            created_today = int(
                session.query(func.count()).select_from(WatchTodo)
                .filter(WatchTodo.created_at >= day_start).scalar() or 0)
            closed_today = int(
                session.query(func.count()).select_from(WatchTodo)
                .filter(WatchTodo.closed_at.isnot(None), WatchTodo.closed_at >= day_start)
                .scalar() or 0)
        except Exception:  # noqa: BLE001 - 失败必须响亮
            self._safe_rollback()
            raise
        return {
            'pending': pending,
            'by_level': by_level,
            'by_flow_state': by_flow,
            'created_today': created_today,
            'closed_today': closed_today,
            'terminal_rate_today': (closed_today / created_today) if created_today else None,
        }

    def list_pending(self, level: Optional[str] = None, account: Optional[str] = None,
                     limit: int = DEFAULT_LIMIT, *, flow_state: Optional[str] = None,
                     terminal: Optional[str] = None) -> List[WatchTodo]:
        """列出待办：缺省只含未收敛（§2 list_pending 语义）

        terminal：None=未收敛；'*'=不过滤终态；其他=精确匹配该终态。
        level/account/flow_state 为精确过滤。按 due_at 升序（最紧急在前）。
        """
        try:
            query = self.session.query(WatchTodo)
            if terminal is None:
                query = query.filter(WatchTodo.terminal.is_(None))
            elif str(terminal).strip() != '*':
                query = query.filter(WatchTodo.terminal == terminal)
            if level:
                query = query.filter(WatchTodo.level == level)
            if account:
                query = query.filter(WatchTodo.account == account)
            if flow_state:
                query = query.filter(WatchTodo.flow_state == flow_state)
            return (
                query.order_by(WatchTodo.due_at.asc())
                .limit(_bounded_limit(limit))
                .all()
            )
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise


def _bounded_limit(limit: Any) -> int:
    """limit 归一：1..MAX_LIMIT（非法值回落默认，与 watch_async._limit_of 同口径）"""
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))
