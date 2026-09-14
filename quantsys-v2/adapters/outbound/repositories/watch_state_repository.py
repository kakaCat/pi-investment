"""Watch 状态类适配器（REQ-f08def P4，2026-09-11，w-c8cae280）

实现 domain/watch/ports.py 的两个端口：
  · IWatchDigestStateRepository   摘要门状态（上次唤醒/当日次数）
  · IWatchInterventionRepository  介入记账（agent 被唤醒介入的留痕与统计）

按 ADR-001（六边形架构）：**裸 SQL/ORM 只允许出现在适配器层**——应用层此前直接
get_engine()/text() 写这两张表属违规，2026-09-11 重构上收于此。

2026-09-14（w-8b43d3b8，REQ-24e15d B4-c5）：本文件最后 6 处 text() 裸 SQL 收口到
ORM（模型见 infrastructure/persistence/orm/models/watch_state.py）：
  · 两条 SELECT 改成对模型的列投影查询（行/None 语义不变）；
  · upsert 改成 PostgreSQL insert(...).on_conflict_do_update(index_elements=[id])，
    跨日判断用 CASE 引用**冲突行自己的旧 wake_date**（与旧 SQL 的
    quant.watch_digest_state.wake_date 同义）；
  · 两条 INSERT 改成 ORM 对象落库，created_at 仍由数据库默认 now() 填充；
  · 对 quant.watch_rules 的账本自增**不是本表**的写，改走
    WatchRuleRepository.apply_intervention_ledger()，与介入行同事务提交
    （旧实现用同一个 begin() 块包住两条语句，原子性必须保持）。
异常行为照旧：读路径失败降级为"未唤醒/0/空"，写路径失败只记日志不外抛。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import case, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.persistence.orm import get_session
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

    def load_state(self) -> Dict[str, Any]:
        try:
            row = (
                get_session()
                .query(
                    WatchDigestState.last_wake_at,
                    WatchDigestState.wake_date,
                    WatchDigestState.wake_count,
                )
                .filter(WatchDigestState.id == 1)
                .first()
            )
            if row is None:
                return {"last_wake_at": None, "wake_date": None, "wake_count": 0}
            return {"last_wake_at": row[0], "wake_date": row[1], "wake_count": int(row[2] or 0)}
        except Exception as e:
            logger.warning("摘要状态读取失败（按未唤醒处理）", error=str(e))
            _safe_rollback()
            return {"last_wake_at": None, "wake_date": None, "wake_count": 0}

    def save_wake(self, now: datetime) -> None:
        try:
            tbl = WatchDigestState.__table__
            stmt = pg_insert(tbl).values(
                id=1,
                last_wake_at=now,
                wake_date=now.date(),
                wake_count=1,
                updated_at=func.now(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[tbl.c.id],
                set_={
                    'last_wake_at': now,
                    # 跨日判断：引用冲突行**旧**的 wake_date（PG 的 DO UPDATE 表达式
                    # 全部按旧行求值），与旧 SQL 的
                    # CASE WHEN quant.watch_digest_state.wake_date = :d THEN wake_count + 1 ELSE 1 END 同义。
                    'wake_count': case(
                        (tbl.c.wake_date == now.date(), tbl.c.wake_count + 1),
                        else_=1,
                    ),
                    'wake_date': now.date(),
                    'updated_at': func.now(),
                },
            )
            session = get_session()
            session.execute(stmt)
            session.commit()
        except Exception as e:
            logger.error("摘要状态写入失败", error=str(e))
            _safe_rollback()


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
