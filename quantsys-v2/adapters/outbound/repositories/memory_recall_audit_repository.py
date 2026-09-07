"""Memory Recall Audit Repository - quant.memory_recall_audit 数据访问层（P1-T4）"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import Column, BigInteger, Text, Boolean, DateTime, and_
from sqlalchemy.dialects.postgresql import JSONB

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


class MemoryRecallAuditModel(Base):
    __tablename__ = "memory_recall_audit"
    __table_args__ = {"schema": "quant"}

    id = Column(BigInteger, primary_key=True)
    ts = Column(DateTime(timezone=True), nullable=False)
    session_id = Column(Text)
    flow = Column(Text, nullable=False)
    query_text = Column(Text)
    strategy = Column(Text)
    degraded = Column(Boolean, default=False)
    gate_result = Column(Text, nullable=False)
    suppress_reason = Column(Text)
    hits = Column(JSONB, nullable=False, default=[])
    created_at = Column(DateTime(timezone=True), default=datetime.now)


class MemoryRecallAuditRepository(BaseORMRepository[MemoryRecallAuditModel]):
    model = MemoryRecallAuditModel

    # gate_result 规范值：'passed'（注入放行）/ 'suppressed'（抑制），
    # 由 agent-ts P1-T2 quality-gate 域写入。'injected' 为历史/外部兼容值，统计时等价 passed。
    _INJECTED_VALUES = ("passed", "injected")

    @staticmethod
    def _date_to_exclusive(date_to: str) -> datetime:
        """date_to 上界（不含）。date-only（YYYY-MM-DD）按当日整天处理 → 次日 0 点；
        完整时间戳原样使用。修复：date-only 曾被解析为当日 0 点导致同日查询全零。"""
        dt = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        if len(date_to.strip()) == 10:
            return dt + timedelta(days=1)
        return dt

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建审计记录"""
        try:
            # 转换 ts 字符串为 datetime
            if isinstance(data.get("ts"), str):
                data["ts"] = datetime.fromisoformat(data["ts"].replace("Z", "+00:00"))

            row = self.model(**data)
            self.session.add(row)
            self.session.commit()
            return self._to_dict(row)
        except Exception as e:
            self._safe_rollback()
            logger.error(f"recall_audit create failed: {e}")
            raise

    def get_by_id(self, audit_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取审计记录"""
        try:
            row = self.session.query(self.model).filter_by(id=audit_id).first()
            return self._to_dict(row) if row else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"recall_audit get_by_id failed: {e}")
            return None

    def list_filtered(
        self,
        flow: Optional[str] = None,
        gate_result: Optional[str] = None,
        suppressed_only: bool = False,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[Dict[str, Any]], int]:
        """分页列举审计记录，返回 (items, total)"""
        try:
            query = self.session.query(self.model)

            # 筛选
            if flow:
                query = query.filter(self.model.flow == flow)
            if gate_result:
                query = query.filter(self.model.gate_result == gate_result)
            if suppressed_only:
                query = query.filter(self.model.gate_result == "suppressed")
            if date_from:
                dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
                query = query.filter(self.model.ts >= dt_from)
            if date_to:
                query = query.filter(self.model.ts < self._date_to_exclusive(date_to))

            # 总数
            total = query.count()

            # 分页
            query = query.order_by(self.model.ts.desc())
            offset = (page - 1) * page_size
            rows = query.offset(offset).limit(page_size).all()

            return [self._to_dict(r) for r in rows], total
        except Exception as e:
            self._safe_rollback()
            logger.error(f"recall_audit list_filtered failed: {e}")
            return [], 0

    def get_stats(
        self, date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """统计注入率、分流、抑制原因、分数直方图"""
        try:
            from sqlalchemy import func, case

            query = self.session.query(self.model)

            # 日期范围
            if date_from:
                dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
                query = query.filter(self.model.ts >= dt_from)
            if date_to:
                query = query.filter(self.model.ts < self._date_to_exclusive(date_to))

            rows = query.all()
            total = len(rows)
            injected = sum(1 for r in rows if r.gate_result in self._INJECTED_VALUES)
            suppressed = sum(1 for r in rows if r.gate_result == "suppressed")

            # 分流统计
            by_flow = {}
            for r in rows:
                if r.flow not in by_flow:
                    by_flow[r.flow] = {"total": 0, "injected": 0, "suppressed": 0}
                by_flow[r.flow]["total"] += 1
                if r.gate_result in self._INJECTED_VALUES:
                    by_flow[r.flow]["injected"] += 1
                elif r.gate_result == "suppressed":
                    by_flow[r.flow]["suppressed"] += 1

            # 抑制原因
            suppress_reasons = {}
            for r in rows:
                if r.gate_result == "suppressed" and r.suppress_reason:
                    suppress_reasons[r.suppress_reason] = suppress_reasons.get(r.suppress_reason, 0) + 1

            # 分数直方图
            buckets = [(i / 10, (i + 1) / 10) for i in range(10)]
            histogram = [{"bucket": f"{low:.1f}-{high:.1f}", "count": 0} for low, high in buckets]
            for r in rows:
                if not r.hits:
                    continue
                for hit in r.hits:
                    score = hit.get("score", 0)
                    idx = min(int(score * 10), 9)
                    histogram[idx]["count"] += 1

            return {
                "total": total,
                "injected": injected,
                "suppressed": suppressed,
                "injection_rate": round(injected / total, 2) if total > 0 else 0,
                "by_flow": by_flow,
                "suppress_reasons": suppress_reasons,
                "score_histogram": histogram,
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"recall_audit get_stats failed: {e}")
            return {
                "total": 0,
                "injected": 0,
                "suppressed": 0,
                "injection_rate": 0,
                "by_flow": {},
                "suppress_reasons": {},
                "score_histogram": [],
            }

    def update_feedback(
        self,
        audit_id: int,
        memory_id: int,
        feedback: str,
        feedback_by: str,
    ) -> Dict[str, Any]:
        """更新 hits 数组中指定 memory_id 的 feedback（409 = agent 覆盖 human）"""
        try:
            from sqlalchemy.orm.attributes import flag_modified

            row = self.session.query(self.model).filter_by(id=audit_id).with_for_update().first()
            if not row:
                raise ValueError(f"Audit not found: id={audit_id}")

            hits = row.hits or []
            target_idx = None
            for i, hit in enumerate(hits):
                if hit.get("memory_id") == memory_id:
                    target_idx = i
                    break

            if target_idx is None:
                raise ValueError(f"memory_id {memory_id} not found in hits")

            target = hits[target_idx]
            existing_by = target.get("feedback_by")

            # agent 覆盖 human → 409
            if existing_by == "human" and feedback_by == "agent":
                raise PermissionError("Agent cannot override human feedback")

            # 更新
            target["feedback"] = feedback
            target["feedback_by"] = feedback_by
            target["feedback_at"] = datetime.now().isoformat()
            hits[target_idx] = target

            # 回写（触发 JSONB 更新需要 flag_modified）
            row.hits = hits
            flag_modified(row, "hits")
            self.session.commit()
            return self._to_dict(row)
        except (ValueError, PermissionError):
            self._safe_rollback()
            raise
        except Exception as e:
            self._safe_rollback()
            logger.error(f"recall_audit update_feedback failed: {e}")
            raise

    def _to_dict(self, row) -> Dict[str, Any]:
        """ORM 模型转字典"""
        if not row:
            return {}
        return {
            "id": row.id,
            "ts": row.ts.isoformat() if row.ts else None,
            "session_id": row.session_id,
            "flow": row.flow,
            "query_text": row.query_text,
            "strategy": row.strategy,
            "degraded": row.degraded,
            "gate_result": row.gate_result,
            "suppress_reason": row.suppress_reason,
            "hits": row.hits,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
