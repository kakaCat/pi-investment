"""交易计划仓储（REQ-261021222905-6dff t2，2026-10-22）

口径（与设计文档一致）：
- 五表读写全部走 ORM（trading_plan 模型），事务边界在仓储内：
  create_plan / apply_version / transition_status 均为单事务（行 + 版本 + 事件同生共死），
  失败整体回滚，不留半成品。
- 缺表降级：迁移未落库时**读**返回空（列表 [] / None），**写**抛
  TradingPlanSchemaMissing 并提示先跑迁移——宁可响亮失败，也不静默写丢。
- 版本 CAS：apply_version / transition_status 均接 expected_version；
  行数 0 = 冲突（返回 None），由服务层转 409。
- 编译映射幂等：(plan_id, role, symbol) 主键，重复写入 ON CONFLICT DO NOTHING。
- 反思同周期重写：version = max(已存版本)+1（旧行保留可查）。
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from infrastructure.persistence.orm import close_session
from qs_kernel.infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models.trading_plan import (
    PlanReflection,
    TradingPlan,
    TradingPlanEvent,
    TradingPlanRule,
    TradingPlanVersion,
)

logger = structlog.get_logger(__name__)

#: 新表不存在时的降级口径（读空 / 写拒）
_TABLES_PRESENT_CACHE: Dict[str, bool] = {}


class TradingPlanSchemaMissing(RuntimeError):
    """迁移未落库：写路径拒绝执行（读路径已降级为空）。"""


class TradingPlanRepository(BaseORMRepository[TradingPlan]):
    model = TradingPlan

    # ── 缺表预检 ──────────────────────────────────────────────
    def _tables_ready(self) -> bool:
        """五表是否就位（缓存；探活失败按在位处理——走正常路径报真错）。"""
        try:
            bind = self.session.get_bind()
        except Exception:  # noqa: BLE001
            return True
        key = str(getattr(bind, "url", bind))
        cached = _TABLES_PRESENT_CACHE.get(key)
        if cached is not None:
            return cached
        try:
            rows = self.session.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema='quant' AND table_name IN "
                    "('trading_plans','trading_plan_versions','trading_plan_rules',"
                    "'trading_plan_events','plan_reflections')"
                )
            ).scalar()
            _TABLES_PRESENT_CACHE[key] = int(rows or 0) == 5
        except Exception:  # noqa: BLE001
            return True
        return _TABLES_PRESENT_CACHE[key]

    def _require_schema(self) -> None:
        if not self._tables_ready():
            raise TradingPlanSchemaMissing(
                "trading_plan 五表不存在：先运行 "
                "infrastructure/persistence/migrations/20261105_trading_plan.py --apply"
            )

    # ── 计划本体 ──────────────────────────────────────────────
    def create_plan(
        self,
        account: str,
        name: str,
        horizon: str,
        spec: Dict[str, Any],
        created_by: str,
        review_interval_days: int = 1,
        status: str = "draft",
        actor: Optional[str] = None,
    ) -> TradingPlan:
        """建计划 + 首个版本行 + 创建事件（单事务）。"""
        self._require_schema()
        try:
            plan = TradingPlan(
                account=account,
                name=name,
                horizon=horizon,
                status=status,
                spec=spec,
                version=1,
                review_interval_days=review_interval_days,
                created_by=created_by,
            )
            self.session.add(plan)
            self.session.flush()
            self.session.add(
                TradingPlanVersion(
                    plan_id=plan.id,
                    version=1,
                    spec=spec,
                    window_days=10,
                    created_by=created_by,
                )
            )
            self.session.add(
                TradingPlanEvent(
                    plan_id=plan.id,
                    kind="status_change",
                    from_status=None,
                    to_status=status,
                    reason="创建计划",
                    actor=actor or created_by,
                )
            )
            self.session.commit()
            self.session.refresh(plan)
            return plan
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()

    def get_plan(self, plan_id: int) -> Optional[TradingPlan]:
        if not self._tables_ready():
            return None
        try:
            return self.session.query(TradingPlan).filter(TradingPlan.id == plan_id).first()
        finally:
            close_session()

    def list_plans(
        self, account: str, statuses: Optional[List[str]] = None, include_archived: bool = False
    ) -> List[TradingPlan]:
        if not self._tables_ready():
            return []
        try:
            q = self.session.query(TradingPlan).filter(TradingPlan.account == account)
            if statuses:
                q = q.filter(TradingPlan.status.in_(statuses))
            elif not include_archived:
                q = q.filter(TradingPlan.status != "archived")
            return q.order_by(TradingPlan.id.desc()).all()
        finally:
            close_session()

    def list_due_plans(self, now, statuses=None) -> List[TradingPlan]:
        """反思到期扫描：活跃计划里 review_due_at 为空或已到期的。"""
        if not self._tables_ready():
            return []
        from qs_plan.domain.plan import STATUS_ACTIVE, STATUS_CLOSING, STATUS_HOLDING

        statuses = statuses or [STATUS_ACTIVE, STATUS_HOLDING, STATUS_CLOSING]
        try:
            return (
                self.session.query(TradingPlan)
                .filter(TradingPlan.status.in_(statuses))
                .filter((TradingPlan.review_due_at.is_(None)) | (TradingPlan.review_due_at <= now))
                .all()
            )
        finally:
            close_session()

    def set_review_due(self, plan_id: int, due_at) -> None:
        self._require_schema()
        try:
            self.session.execute(
                text("UPDATE quant.trading_plans SET review_due_at = :d WHERE id = :id"),
                {"d": due_at, "id": plan_id},
            )
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()

    def update_draft_spec(
        self, plan_id: int, draft_spec: Optional[Dict[str, Any]], expected_version: int
    ) -> bool:
        """暂存修改（CAS）。行数 0 = 版本冲突。"""
        self._require_schema()
        try:
            # psycopg2 不认 dict → 显式序列化 + ::jsonb 转换；None 走裸 NULL
            payload = json.dumps(draft_spec, ensure_ascii=False) if draft_spec is not None else None
            rows = self.session.execute(
                text(
                    "UPDATE quant.trading_plans SET draft_spec = "
                    "CAST(:draft AS jsonb) WHERE id = :id AND version = :v"
                ),
                {"draft": payload, "id": plan_id, "v": expected_version},
            ).rowcount
            self.session.commit()
            return rows == 1
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()

    def apply_version(
        self,
        plan_id: int,
        expected_version: int,
        spec: Dict[str, Any],
        baseline: Optional[Dict[str, Any]] = None,
        window_days: int = 10,
        change_reason: Optional[str] = None,
        hypothesis: Optional[Dict[str, Any]] = None,
        created_by: str = "agent",
        decision_audit_id: Optional[str] = None,
        to_status: Optional[str] = None,
    ) -> Optional[int]:
        """生效新版本：版本行 + 计划更新（version+1、清 draft、可选状态）+ 事件（单事务）。

        返回新版本号；版本冲突返回 None（不改任何行）。
        """
        self._require_schema()
        try:
            plan = (
                self.session.query(TradingPlan)
                .filter(TradingPlan.id == plan_id)
                .with_for_update()
                .first()
            )
            if plan is None or plan.version != expected_version:
                self.session.rollback()
                return None
            new_version = expected_version + 1
            plan.spec = spec
            plan.draft_spec = None
            plan.version = new_version
            if to_status:
                plan.status = to_status
            self.session.add(
                TradingPlanVersion(
                    plan_id=plan_id,
                    version=new_version,
                    spec=spec,
                    baseline=baseline,
                    window_days=window_days,
                    change_reason=change_reason,
                    hypothesis=hypothesis,
                    created_by=created_by,
                    decision_audit_id=decision_audit_id,
                )
            )
            self.session.add(
                TradingPlanEvent(
                    plan_id=plan_id,
                    kind="spec_change",
                    from_status=plan.status if to_status is None else to_status,
                    to_status=to_status,
                    detail={"version": new_version, "reason": change_reason},
                    reason=change_reason,
                    actor=created_by,
                    decision_audit_id=decision_audit_id,
                )
            )
            self.session.commit()
            return new_version
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()

    def transition_status(
        self,
        plan_id: int,
        to_status: str,
        actor: str,
        reason: Optional[str] = None,
        decision_audit_id: Optional[str] = None,
        expected_version: Optional[int] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """状态迁移（可选 CAS）：更新状态 + 事件留痕（单事务）。"""
        self._require_schema()
        try:
            q = self.session.query(TradingPlan).filter(TradingPlan.id == plan_id)
            q = q.with_for_update()
            plan = q.first()
            if plan is None:
                self.session.rollback()
                return False
            if expected_version is not None and plan.version != expected_version:
                self.session.rollback()
                return False
            from_status = plan.status
            plan.status = to_status
            if extra_fields:
                for k, v in extra_fields.items():
                    if hasattr(plan, k):
                        setattr(plan, k, v)
            self.session.add(
                TradingPlanEvent(
                    plan_id=plan_id,
                    kind="status_change",
                    from_status=from_status,
                    to_status=to_status,
                    reason=reason,
                    actor=actor,
                    decision_audit_id=decision_audit_id,
                )
            )
            self.session.commit()
            return True
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()

    # ── 版本 ──────────────────────────────────────────────────
    def list_versions(self, plan_id: int, limit: int = 50) -> List[TradingPlanVersion]:
        if not self._tables_ready():
            return []
        try:
            return (
                self.session.query(TradingPlanVersion)
                .filter(TradingPlanVersion.plan_id == plan_id)
                .order_by(TradingPlanVersion.version.desc())
                .limit(limit)
                .all()
            )
        finally:
            close_session()

    # ── 编译映射（幂等） ──────────────────────────────────────
    def record_rule_mapping(
        self, plan_id: int, rule_id: int, role: str, symbol: str, batch: int = 0
    ) -> None:
        self._require_schema()
        try:
            self.session.execute(
                text(
                    "INSERT INTO quant.trading_plan_rules "
                    "(plan_id, rule_id, role, symbol, batch) "
                    "VALUES (:p, :r, :role, :s, :b) "
                    "ON CONFLICT (plan_id, role, symbol, batch) DO NOTHING"
                ),
                {"p": plan_id, "r": rule_id, "role": role, "s": symbol, "b": batch},
            )
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()

    def list_rule_mappings(self, plan_id: int) -> List[TradingPlanRule]:
        if not self._tables_ready():
            return []
        try:
            return (
                self.session.query(TradingPlanRule).filter(TradingPlanRule.plan_id == plan_id).all()
            )
        finally:
            close_session()

    def delete_rule_mapping(self, plan_id: int, role: str, symbol: str, batch: int = 0) -> int:
        self._require_schema()
        try:
            rows = (
                self.session.query(TradingPlanRule)
                .filter(
                    TradingPlanRule.plan_id == plan_id,
                    TradingPlanRule.role == role,
                    TradingPlanRule.symbol == symbol,
                    TradingPlanRule.batch == batch,
                )
                .delete()
            )
            self.session.commit()
            return rows
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()

    # ── 事件 ──────────────────────────────────────────────────
    def record_event(
        self,
        plan_id: int,
        kind: str,
        actor: str,
        reason: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        decision_audit_id: Optional[str] = None,
    ) -> None:
        self._require_schema()
        try:
            self.session.add(
                TradingPlanEvent(
                    plan_id=plan_id,
                    kind=kind,
                    actor=actor,
                    reason=reason,
                    detail=detail,
                    from_status=from_status,
                    to_status=to_status,
                    decision_audit_id=decision_audit_id,
                )
            )
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()

    def list_events(self, plan_id: int, limit: int = 50) -> List[TradingPlanEvent]:
        if not self._tables_ready():
            return []
        try:
            return (
                self.session.query(TradingPlanEvent)
                .filter(TradingPlanEvent.plan_id == plan_id)
                .order_by(TradingPlanEvent.id.desc())
                .limit(limit)
                .all()
            )
        finally:
            close_session()

    # ── 反思 ──────────────────────────────────────────────────
    def record_reflection(
        self,
        plan_id: int,
        kind: str,
        period: str,
        evidence_pack: Dict[str, Any],
        answers: Dict[str, Any],
        verdict: str,
        reasoning: Optional[str] = None,
        actions: Optional[List[Any]] = None,
        knowledge_updates: Optional[List[Any]] = None,
        agent_session_id: Optional[str] = None,
    ) -> int:
        """反思落库；同 (plan_id, kind, period) 再写则 version+1 新行。返回行 id。"""
        self._require_schema()
        try:
            latest = (
                self.session.query(PlanReflection.version)
                .filter(
                    PlanReflection.plan_id == plan_id,
                    PlanReflection.kind == kind,
                    PlanReflection.period == period,
                )
                .order_by(PlanReflection.version.desc())
                .first()
            )
            version = (latest[0] + 1) if latest else 1
            row = PlanReflection(
                plan_id=plan_id,
                kind=kind,
                period=period,
                version=version,
                evidence_pack=evidence_pack,
                answers=answers,
                verdict=verdict,
                reasoning=reasoning,
                actions=actions,
                knowledge_updates=knowledge_updates,
                agent_session_id=agent_session_id,
            )
            self.session.add(row)
            self.session.flush()
            rid = row.id
            self.session.commit()
            return rid
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()

    def get_reflection(self, reflection_id: int) -> Optional[PlanReflection]:
        if not self._tables_ready():
            return None
        try:
            return (
                self.session.query(PlanReflection)
                .filter(PlanReflection.id == reflection_id)
                .first()
            )
        finally:
            close_session()

    def list_reflections(self, plan_id: int, limit: int = 20) -> List[PlanReflection]:
        if not self._tables_ready():
            return []
        try:
            return (
                self.session.query(PlanReflection)
                .filter(PlanReflection.plan_id == plan_id)
                .order_by(PlanReflection.created_at.desc())
                .limit(limit)
                .all()
            )
        finally:
            close_session()

    # ── 反思周期字段 ──────────────────────────────────────────
    def mark_reflected(self, plan_id: int, at: datetime) -> None:
        self._require_schema()
        try:
            self.session.execute(
                text(
                    "UPDATE quant.trading_plans SET last_reflected_at = :at, "
                    "reflection_overdue_count = 0 WHERE id = :id"
                ),
                {"at": at, "id": plan_id},
            )
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()

    def bump_overdue(self, plan_id: int) -> int:
        self._require_schema()
        try:
            self.session.execute(
                text(
                    "UPDATE quant.trading_plans SET reflection_overdue_count = "
                    "reflection_overdue_count + 1 WHERE id = :id"
                ),
                {"id": plan_id},
            )
            self.session.commit()
            row = self.session.execute(
                text("SELECT reflection_overdue_count FROM quant.trading_plans WHERE id = :id"),
                {"id": plan_id},
            ).scalar()
            return int(row or 0)
        except SQLAlchemyError:
            self.session.rollback()
            raise
        finally:
            close_session()
