"""Watch 状态类适配器（REQ-f08def P4，2026-09-11，w-c8cae280）

实现 domain/watch/ports.py 的两个端口：
  · IWatchDigestStateRepository   摘要门状态（上次唤醒/当日次数）
  · IWatchInterventionRepository  介入记账（agent 被唤醒介入的留痕与统计）

按 ADR-001（六边形架构）：**裸 SQL/ORM 只允许出现在适配器层**——应用层此前直接
get_engine()/text() 写这两张表属违规，2026-09-11 重构上收于此。

2026-09-14（w-8b43d3b8，REQ-24e15d B4-c5）：本文件最后 6 处 text() 裸 SQL 收口到
ORM（模型见 infrastructure/persistence/orm/models/watch_state.py）：
  · 两条 SELECT 改成对模型的列投影查询（行/None 语义不变）；
  · 单行 upsert 采用 insert(...).on_conflict_do_nothing 确保存在，随后 SELECT FOR UPDATE
    读取旧日期并串行更新计数/wake_marks；固定 pending 跨日保留；
  · 两条 INSERT 改成 ORM 对象落库，created_at 仍由数据库默认 now() 填充；
  · 对 quant.watch_rules 的账本自增**不是本表**的写，改走
    WatchRuleRepository.apply_intervention_ledger()，与介入行同事务提交
    （旧实现用同一个 begin() 块包住两条语句，原子性必须保持）。
异常行为：读路径失败返回 load_error（摘要门 fail-closed，不生成新事件），写路径返回 False。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from qs_kernel.infrastructure.persistence.orm import get_session
from infrastructure.persistence.orm.models import WatchDigestState, WatchIntervention
from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository

logger = structlog.get_logger(__name__)


def _safe_rollback() -> None:
    """回滚当前线程的 ORM session。

    与旧实现的关键差异：旧代码各自 get_engine().connect() 开独立连接，出错只影响
    自己；现在共用线程级 scoped_session，一次 PG 报错会让事务进入 aborted 状态，
    不回滚则同线程后续所有查询撞 "current transaction is aborted"（线程毒化）。
    """
    try:
        get_session().rollback()
    except Exception as rb_err:  # noqa: BLE001
        logger.warning("介入/摘要状态回滚失败", error=str(rb_err))


class WatchDigestStateRepository:
    """摘要门状态（quant.watch_digest_state，单行 id=1）"""

    _PENDING_KEY = '__pending_batches__'

    def load_state(self) -> Dict[str, Any]:
        try:
            row = (
                get_session()
                .query(
                    WatchDigestState.last_wake_at,
                    WatchDigestState.wake_date,
                    WatchDigestState.wake_count,
                    WatchDigestState.wake_marks,
                )
                .filter(WatchDigestState.id == 1)
                .first()
            )
            if row is None:
                return {"last_wake_at": None, "wake_date": None, "wake_count": 0,
                        "wake_marks": {}}
            marks = dict(row[3] or {})
            pending = marks.pop(self._PENDING_KEY, {})
            return {"last_wake_at": row[0], "wake_date": row[1], "wake_count": int(row[2] or 0),
                    "wake_marks": marks, "pending_batches": pending}
        except Exception as e:
            logger.warning("摘要状态读取失败（本轮禁止唤醒）", error=str(e))
            _safe_rollback()
            return {"last_wake_at": None, "wake_date": None, "wake_count": 0,
                    "wake_marks": {}, "load_error": str(e)}

    def save_wake(self, now: datetime, account: Optional[str] = None) -> bool:
        """行锁内记唤醒并合并账户水位；跨日只清普通水位，绝不清固定 pending。"""
        try:
            session = get_session()
            tbl = WatchDigestState.__table__
            # 先确保单行存在，再锁行读取旧日期。不能在 upsert 改日期后才判断跨日。
            session.execute(pg_insert(tbl).values(id=1).on_conflict_do_nothing(
                index_elements=[tbl.c.id]))
            row = (session.query(WatchDigestState)
                   .filter(WatchDigestState.id == 1).with_for_update().one())
            previous_date = row.wake_date
            row.last_wake_at = now
            row.wake_count = (int(row.wake_count or 0) + 1
                              if previous_date == now.date() else 1)
            row.wake_date = now.date()
            row.updated_at = func.now()
            if account is not None:
                marks = dict(row.wake_marks or {})
                if previous_date != now.date():
                    pending = marks.get(self._PENDING_KEY)
                    marks = {self._PENDING_KEY: pending} if pending else {}
                marks[str(account)] = now.isoformat()
                row.wake_marks = marks
            session.commit()
            return True
        except Exception as e:
            logger.error("摘要状态写入失败", error=str(e))
            _safe_rollback()
            return False

    def save_wake_mark(self, account: str, at: datetime) -> None:
        """只钉某账户的水位（不动 last_wake_at/wake_count）。

        用途（2026-10-19 P1-5）：账户唤醒**失败**时把水位钉在本轮窗口起点——
        下轮 effective_since 取全部水位的最小值，失败账户的触发由此留在增量段。
        单行表读-改-写统一使用 SELECT FOR UPDATE，序列化多 worker 对 wake_marks 的合并。
        """
        try:
            session = get_session()
            row = (session.query(WatchDigestState)
                   .filter(WatchDigestState.id == 1).with_for_update().first())
            if row is None:
                # 单行尚未建立（从未唤醒过）：建行同时落水位
                session.add(WatchDigestState(id=1,
                                             wake_marks={str(account): at.isoformat()}))
            else:
                marks = dict(row.wake_marks or {})
                marks[str(account)] = at.isoformat()
                row.wake_marks = marks
            session.commit()
        except Exception as e:
            logger.error("逐账户水位写入失败", error=str(e))
            _safe_rollback()
    def save_pending_batch(self, account: str, batch: Dict[str, Any]) -> bool:
        """在网络前持久化固定重试批次，复用 wake_marks JSONB 的保留区域。"""
        try:
            session = get_session()
            row = (session.query(WatchDigestState)
                   .filter(WatchDigestState.id == 1).with_for_update().first())
            if row is None:
                row = WatchDigestState(id=1, wake_marks={})
                session.add(row)
            marks = dict(row.wake_marks or {})
            pending = dict(marks.get(self._PENDING_KEY) or {})
            existing = pending.get(str(account))
            incoming_id = str((batch.get('payload') or {}).get('event_id') or '')
            existing_id = str(((existing or {}).get('payload') or {}).get('event_id') or '')
            if existing is not None and existing_id != incoming_id:
                logger.warning('拒绝覆盖另一 worker 的固定摘要批次',
                               account=account, existing=existing_id, incoming=incoming_id)
                _safe_rollback()
                return False
            pending[str(account)] = batch
            marks[self._PENDING_KEY] = pending
            row.wake_marks = marks
            session.commit()
            return True
        except Exception as e:
            logger.error("摘要固定重试批次写入失败", account=account, error=str(e))
            _safe_rollback()
            return False

    def clear_pending_batch(self, account: str, expected_event_id: str) -> bool:
        """仅清理完成者自己的 pending；旧 event 不得删除另一 worker 的新批次。"""
        if not str(expected_event_id or '').strip():
            return False
        try:
            session = get_session()
            row = (session.query(WatchDigestState)
                   .filter(WatchDigestState.id == 1).with_for_update().first())
            if row is None:
                _safe_rollback()
                return True
            marks = dict(row.wake_marks or {})
            pending = dict(marks.get(self._PENDING_KEY) or {})
            current = pending.get(str(account))
            current_id = str(((current or {}).get('payload') or {}).get('event_id') or '')
            if current is None:
                _safe_rollback()
                return True
            if current_id != expected_event_id:
                logger.info('旧摘要完成者保留另一 worker 的新 pending',
                            account=account, expected=expected_event_id, current=current_id)
                _safe_rollback()
                return True
            pending.pop(str(account), None)
            if pending:
                marks[self._PENDING_KEY] = pending
            else:
                marks.pop(self._PENDING_KEY, None)
            row.wake_marks = marks
            session.commit()
            return True
        except Exception as e:
            logger.error("摘要固定重试批次清理失败", account=account, error=str(e))
            _safe_rollback()
            return False


class WatchInterventionRepository:
    """介入记账（quant.watch_interventions + 规则价值账本计数）"""

    def count_today(self) -> int:
        try:
            count = (
                get_session()
                .query(func.count())
                .select_from(WatchIntervention)
                .filter(WatchIntervention.created_at >= func.current_date())
                .scalar()
            )
            return int(count or 0)
        except Exception as e:
            logger.warning("介入计数读取失败（按 0 处理）", error=str(e))
            _safe_rollback()
            return 0

    def record(self, symbol: str, intent: Optional[str] = None, rule_id: Optional[int] = None,
               trigger_kind: str = "price", outcome: str = "escalated",
               trigger_ids: Optional[List[int]] = None, tokens: Optional[int] = None,
               cost_yuan: float = 0.0, decision_audit_id: Optional[str] = None) -> None:
        try:
            session = get_session()
            session.add(WatchIntervention(
                rule_id=rule_id,
                symbol=symbol,
                intent=intent,
                trigger_kind=trigger_kind,
                outcome=outcome,
                # 文本列（不是数组）：空列表落成空串，与旧实现 ",".join([]) 一致
                trigger_ids=",".join(str(i) for i in (trigger_ids or [])),
                tokens=tokens,
                cost_yuan=cost_yuan,
                decision_audit_id=decision_audit_id,
            ))
            if rule_id is not None:
                # 与介入行**同一事务**（旧实现两条语句包在同一个 begin() 块里）；
                # 该方法内部不 commit，由这里统一提交/回滚。
                WatchRuleRepository().apply_intervention_ledger(
                    rule_id=rule_id,
                    cost_delta=cost_yuan,
                    valuable=outcome in ("handled", "reviewed"),
                )
            session.commit()
        except Exception as e:
            logger.error("介入记账失败", error=str(e), symbol=symbol)
            _safe_rollback()

    def summary_today(self) -> Dict[str, Any]:
        try:
            rows = (
                get_session()
                .query(WatchIntervention.outcome, func.count())
                .filter(WatchIntervention.created_at >= func.current_date())
                .group_by(WatchIntervention.outcome)
                .all()
            )
            by_outcome = {r[0]: int(r[1]) for r in rows}
            total = sum(by_outcome.values())
            valuable = by_outcome.get("handled", 0) + by_outcome.get("reviewed", 0)
            return {"interventions_today": total, "by_outcome": by_outcome,
                    "valuable_actions": valuable,
                    "yield_per_wake": round(valuable / total, 3) if total else None}
        except Exception as e:
            logger.warning("介入概览读取失败", error=str(e))
            _safe_rollback()
            return {"interventions_today": 0, "by_outcome": {}, "valuable_actions": 0, "yield_per_wake": None}
