"""Agent Knowledge ORM Repository - agent_knowledge 表访问

表 DDL 见 infrastructure/persistence/migrations/recreate_agent_intelligence_tables.sql。
KnowledgeService 是 mock（返回空），真实读写走本 repository。
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from sqlalchemy import Column, Integer, String, Float, JSON, DateTime
from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


class AgentKnowledge(Base):
    __tablename__ = 'agent_knowledge'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    knowledge_id = Column(String(50), nullable=False, unique=True)
    domain = Column(String(100), nullable=False)
    knowledge_type = Column(String(50), nullable=False)
    content = Column(JSON, nullable=False)
    confidence = Column(Float, default=0.5)
    evidence = Column(JSON)
    learned_at = Column(DateTime, default=datetime.now)
    last_validated = Column(DateTime)
    validation_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    status = Column(String(20), default='active')
    created_by = Column(String(50), default='system')


class AgentKnowledgeORMRepository(BaseORMRepository[AgentKnowledge]):
    model = AgentKnowledge

    def upsert_knowledge(
        self,
        knowledge_id: str,
        domain: str,
        knowledge_type: str,
        content: Dict[str, Any],
        confidence: float,
        validation_count: int,
        success_count: int,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> None:
        """按 knowledge_id 幂等 upsert（存在则更新统计与内容）"""
        row = self.session.query(AgentKnowledge).filter_by(knowledge_id=knowledge_id).first()
        if row:
            row.content = content
            row.confidence = confidence
            row.validation_count = validation_count
            row.success_count = success_count
            row.evidence = evidence
            row.last_validated = datetime.now()
        else:
            row = AgentKnowledge(
                knowledge_id=knowledge_id,
                domain=domain,
                knowledge_type=knowledge_type,
                content=content,
                confidence=confidence,
                validation_count=validation_count,
                success_count=success_count,
                evidence=evidence,
                last_validated=datetime.now(),
            )
            self.session.add(row)
        self.session.commit()

    def get_by_knowledge_id(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        row = self.session.query(AgentKnowledge).filter_by(knowledge_id=knowledge_id).first()
        return self._to_dict(row) if row else None

    def get_by_domain(self, domain: str, knowledge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        query = self.session.query(AgentKnowledge).filter_by(domain=domain, status='active')
        if knowledge_type:
            query = query.filter_by(knowledge_type=knowledge_type)
        return [self._to_dict(r) for r in query.all()]

    def delete_by_knowledge_id(self, knowledge_id: str) -> None:
        self.session.query(AgentKnowledge).filter_by(knowledge_id=knowledge_id).delete()
        self.session.commit()

    @staticmethod
    def _to_dict(r: AgentKnowledge) -> Dict[str, Any]:
        return {
            'knowledge_id': r.knowledge_id,
            'domain': r.domain,
            'knowledge_type': r.knowledge_type,
            'content': r.content,
            'confidence': r.confidence,
            'validation_count': r.validation_count,
            'success_count': r.success_count,
            'status': r.status,
        }
