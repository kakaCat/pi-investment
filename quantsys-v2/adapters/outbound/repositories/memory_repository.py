"""Memory Repository - quant.memory_entries 数据访问层"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import Column, BigInteger, Text, Float, Integer, DateTime, CheckConstraint, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


class MemoryEntryModel(Base):
    __tablename__ = "memory_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('rule', 'episode', 'experience', 'stock_note')", name="check_kind"),
        CheckConstraint(
            "status IN ('testing', 'active', 'deprecated', 'archived')", name="check_status"
        ),
        {"schema": "quant"},
    )

    id = Column(BigInteger, primary_key=True)
    kind = Column(Text, nullable=False)
    scope = Column(Text, nullable=False, default="global")
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    payload = Column(JSONB)
    evidence = Column(JSONB)
    status = Column(Text, nullable=False, default="testing")
    confidence = Column(Float, default=0.3)
    validation_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    provenance = Column(JSONB, nullable=False)
    last_recalled_at = Column(DateTime(timezone=True))
    source = Column(Text)
    supersedes = Column(BigInteger, ForeignKey("quant.memory_entries.id"))
    embedding = Column(Text)  # W1.2: 临时用 TEXT，W1.3 升级为 vector(1024)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)


class MemoryRepository(BaseORMRepository[MemoryEntryModel]):
    model = MemoryEntryModel

    # ---------- 写入 ----------

    def create(self, entry) -> Dict[str, Any]:
        """创建新记忆条目（接收 domain.memory.models.MemoryEntry）"""
        try:
            data = {
                "kind": entry.kind,
                "scope": entry.scope,
                "title": entry.title,
                "content": entry.content,
                "payload": entry.payload,
                "evidence": entry.evidence,
                "status": entry.status,
                "confidence": entry.confidence,
                "validation_count": entry.validation_count,
                "success_count": entry.success_count,
                "provenance": entry.provenance,
                "last_recalled_at": entry.last_recalled_at,
                "source": entry.source,
                "supersedes": entry.supersedes,
                "embedding": entry.embedding,
            }
            row = self.model(**data)
            self.session.add(row)
            self.session.commit()
            return self._to_dict(row)
        except Exception as e:
            self._safe_rollback()
            logger.error(f"memory create failed: {e}")
            raise

    def update(self, entry_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新记忆条目"""
        try:
            row = self.session.query(self.model).filter_by(id=entry_id).first()
            if not row:
                raise ValueError(f"Memory entry not found: id={entry_id}")

            for key, value in updates.items():
                if hasattr(row, key):
                    setattr(row, key, value)

            self.session.commit()
            return self._to_dict(row)
        except Exception as e:
            self._safe_rollback()
            logger.error(f"memory update failed: {e}")
            raise

    # ---------- 查询 ----------

    def get_by_id(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取记忆"""
        try:
            row = self.session.query(self.model).filter_by(id=entry_id).first()
            return self._to_dict(row) if row else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"memory get_by_id failed: {e}")
            return None

    def search(
        self,
        q: Optional[str] = None,
        scope: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """检索记忆（本期关键词 ILIKE，W1.3 升级向量检索）"""
        try:
            query = self.session.query(self.model)

            # 过滤条件
            if scope:
                query = query.filter(self.model.scope == scope)
            if kind:
                query = query.filter(self.model.kind == kind)
            if status:
                query = query.filter(self.model.status == status)

            # 关键词搜索（title + content）
            if q:
                search_pattern = f"%{q}%"
                query = query.filter(
                    (self.model.title.ilike(search_pattern))
                    | (self.model.content.ilike(search_pattern))
                )

            # 排序：最新优先
            query = query.order_by(self.model.created_at.desc())
            query = query.limit(limit)

            rows = query.all()
            return [self._to_dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"memory search failed: {e}")
            return []

    def get_all(self) -> List[Dict[str, Any]]:
        """全量导出（无分页）"""
        try:
            rows = self.session.query(self.model).order_by(self.model.id).all()
            return [self._to_dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"memory get_all failed: {e}")
            return []

    def find_duplicate(
        self, title: str, source: Optional[str], provenance: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """查找重复记忆（导入时去重用）"""
        try:
            query = self.session.query(self.model).filter(self.model.title == title)

            if source:
                query = query.filter(self.model.source == source)

            # provenance 精确匹配（JSONB 比较）
            if provenance:
                query = query.filter(self.model.provenance == provenance)

            row = query.first()
            return self._to_dict(row) if row else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"memory find_duplicate failed: {e}")
            return None

    # ---------- 辅助方法 ----------

    def _to_dict(self, row) -> Dict[str, Any]:
        """ORM 模型转字典"""
        if not row:
            return {}
        return {
            "id": row.id,
            "kind": row.kind,
            "scope": row.scope,
            "title": row.title,
            "content": row.content,
            "payload": row.payload,
            "evidence": row.evidence,
            "status": row.status,
            "confidence": row.confidence,
            "validation_count": row.validation_count,
            "success_count": row.success_count,
            "provenance": row.provenance,
            "last_recalled_at": row.last_recalled_at.isoformat() if row.last_recalled_at else None,
            "source": row.source,
            "supersedes": row.supersedes,
            "embedding": row.embedding,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
