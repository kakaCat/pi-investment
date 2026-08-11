"""
Agent Intelligence ORM Repository - 智能体决策仓储

修复记录：2026-07-19 重建决策部分
  - 原模型表名错误（agent_intelligences），实际表 quant.agent_decisions
  - 补齐 DecisionService/DecisionEvaluator 需要的全部方法
  - save_snapshot/save_metrics/create_event 等博弈模块方法保持原有日志 stub 行为
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Text, JSON, Boolean, DateTime
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from domain.ports import IAgentIntelligenceRepository
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import structlog

logger = structlog.get_logger(__name__)


class AgentDecision(Base):
    __tablename__ = 'agent_decisions'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    decision_id = Column(String(50), nullable=False, unique=True)
    decision_type = Column(String(50), nullable=False)
    context = Column(JSON, nullable=False)
    parameters = Column(JSON, nullable=False)
    reasoning = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(String(50), default='agent')
    evaluation_status = Column(String(20), default='pending')
    evaluation_result = Column(JSON)
    evaluation_date = Column(DateTime)
    learned_lesson = Column(Text)
    confidence_score = Column(Float)
    success = Column(Boolean)
    related_entity_type = Column(String(50))
    related_entity_id = Column(String(50))
    session_key = Column(String(200))  # 关联的 agent 会话（gateway 审计联动）
    score = Column(Float)               # 决策打分 [-1,1]（P0a，2026-08-07）
    score_band = Column(String(20))     # big_win/small_win/neutral/small_loss/big_loss


# 兼容旧代码中对模型名的引用
AgentIntelligence = AgentDecision


class AgentIntelligenceORMRepository(BaseORMRepository[AgentDecision], IAgentIntelligenceRepository):
    """ORM Repository for agent_decisions"""
    model = AgentDecision

    # ---------- 决策方法（DecisionService / DecisionEvaluator 依赖） ----------

    def create_decision(self, decision_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建决策记录，返回完整决策字典"""
        try:
            decision_id = decision_data.get('decision_id') or (
                f"DEC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
            )
            row = self.model(
                decision_id=decision_id,
                decision_type=decision_data.get('decision_type', 'unknown'),
                context=decision_data.get('context') or {},
                parameters=decision_data.get('parameters') or {},
                reasoning=decision_data.get('reasoning'),
                created_by=decision_data.get('created_by', 'agent'),
                confidence_score=decision_data.get('confidence_score'),
                related_entity_type=decision_data.get('related_entity_type'),
                related_entity_id=(str(decision_data['related_entity_id'])
                                   if decision_data.get('related_entity_id') is not None else None),
                session_key=decision_data.get('session_key'),
                evaluation_status='pending',
            )
            created = self.create(row)
            if created is None:
                raise RuntimeError("创建决策记录失败")
            return self._to_dict(created)
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error creating decision: {e}")
            raise

    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """按 decision_id 查询决策"""
        try:
            row = (self.session.query(self.model)
                   .filter_by(decision_id=decision_id).first())
            return self._to_dict(row) if row else None
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error getting decision {decision_id}: {e}")
            return None

    def update_decision(self, decision_id: str, decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新决策可变字段，返回更新后的决策"""
        try:
            row = (self.session.query(self.model)
                   .filter_by(decision_id=decision_id).first())
            if row is None:
                return None

            for field in ('decision_type', 'context', 'parameters', 'reasoning',
                          'confidence_score', 'related_entity_type', 'related_entity_id',
                          'evaluation_status', 'evaluation_result', 'learned_lesson', 'success'):
                if field in decision and decision[field] is not None:
                    value = decision[field]
                    if field == 'related_entity_id':
                        value = str(value)
                    setattr(row, field, value)

            self.session.commit()
            return self._to_dict(row)
        except SQLAlchemyError as e:
            logger.error(f"Error updating decision {decision_id}: {e}")
            self.session.rollback()
            return None

    def update_evaluation(self, decision_id: str, evaluation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """写入评估结果，返回更新后的决策 dict（不存在返回 None）。

        evaluation_status 写 'evaluated'：decision_service 统计报表按
        'evaluated' 计数算 success_rate，之前写 'completed' 导致报表恒 0。
        生产调用方（decision_evaluator/strategy_rotation_engine）忽略返回值，
        bool→dict 无影响。
        """
        try:
            row = (self.session.query(self.model)
                   .filter_by(decision_id=decision_id).first())
            if row is None:
                logger.warning(f"Decision not found for evaluation: {decision_id}")
                return None

            row.evaluation_status = 'evaluated'
            row.evaluation_result = evaluation
            row.evaluation_date = datetime.now()
            if 'success' in evaluation:
                row.success = evaluation['success']
            if 'learned_lesson' in evaluation:
                row.learned_lesson = evaluation['learned_lesson']
            if 'confidence_score' in evaluation:
                row.confidence_score = evaluation['confidence_score']

            self.session.commit()
            return self._to_dict(row)
        except SQLAlchemyError as e:
            logger.error(f"Error updating evaluation for {decision_id}: {e}")
            self.session.rollback()
            return None

    def get_decisions_by_entity(self, entity_type: str, entity_id: str,
                                limit: int = 50) -> List[Dict[str, Any]]:
        """查询指定实体的决策历史（按时间倒序）"""
        try:
            rows = (self.session.query(self.model)
                    .filter_by(related_entity_type=entity_type,
                               related_entity_id=str(entity_id))
                    .order_by(self.model.created_at.desc())
                    .limit(limit).all())
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error getting decisions for {entity_type}/{entity_id}: {e}")
            return []

    def get_recent_decisions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """查询最近的决策（按时间倒序）"""
        try:
            rows = (self.session.query(self.model)
                    .order_by(self.model.created_at.desc())
                    .limit(limit).all())
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error getting recent decisions: {e}")
            return []

    def list_pending_evaluations(self, days: int = 7) -> List[Dict[str, Any]]:
        """查询创建超过 days 天仍待评估的决策"""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            rows = (self.session.query(self.model)
                    .filter(self.model.evaluation_status == 'pending',
                            self.model.created_at <= cutoff)
                    .order_by(self.model.created_at.asc())
                    .all())
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error listing pending evaluations: {e}")
            return []

    # ---------- 接口方法 ----------

    def save_decision(self, decision: dict) -> int:
        """接口方法：保存决策记录，返回记录ID"""
        try:
            created = self.create_decision(decision)
            return int(created['id']) if created.get('id') else 0
        except Exception as e:
            self._safe_rollback()
            logger.error(f"保存决策失败: {e}")
            return 0

    # ---------- 博弈模块 stub（保持原行为：记录日志） ----------

    def save_snapshot(self, snapshot: dict) -> int:
        """保存对手行为快照"""
        try:
            logger.info("保存对手行为快照", snapshot_keys=list(snapshot.keys()))
            return 1
        except Exception as e:
            self._safe_rollback()
            logger.error(f"保存快照失败: {e}")
            return 0

    def save_metrics(self, metrics: dict) -> int:
        """保存博弈指标"""
        try:
            logger.info("保存博弈指标", metrics_keys=list(metrics.keys()))
            return 1
        except Exception as e:
            self._safe_rollback()
            logger.error(f"保存指标失败: {e}")
            return 0

    def create_event(self, event: dict) -> int:
        """创建操纵事件"""
        try:
            logger.info("创建操纵事件", event_keys=list(event.keys()))
            return 1
        except Exception as e:
            self._safe_rollback()
            logger.error(f"创建事件失败: {e}")
            return 0

    def get_active_events(self) -> List[dict]:
        """获取活跃事件"""
        try:
            return []
        except Exception as e:
            self._safe_rollback()
            logger.error(f"获取活跃事件失败: {e}")
            return []

    def resolve_event(self, event_id: int) -> bool:
        """解决事件"""
        try:
            logger.info("解决事件", event_id=event_id)
            return True
        except Exception as e:
            self._safe_rollback()
            logger.error(f"解决事件失败: {e}")
            return False

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing: {e}")
            return []

    # ---------- 工具方法 ----------

    @staticmethod
    def _to_dict(r: AgentDecision) -> Dict[str, Any]:
        return {
            'id': r.id,
            'decision_id': r.decision_id,
            'decision_type': r.decision_type,
            'context': r.context,
            'parameters': r.parameters,
            'reasoning': r.reasoning,
            'created_at': r.created_at.isoformat(sep=' ') if r.created_at else None,
            'created_by': r.created_by,
            'evaluation_status': r.evaluation_status,
            'evaluation_result': r.evaluation_result,
            'evaluation_date': r.evaluation_date.isoformat(sep=' ') if r.evaluation_date else None,
            'learned_lesson': r.learned_lesson,
            'confidence_score': r.confidence_score,
            'success': r.success,
            'related_entity_type': r.related_entity_type,
            'related_entity_id': r.related_entity_id,
            'session_key': r.session_key,
        }


# 兼容旧命名（DecisionService 等引用 AgentDecisionRepository）
AgentDecisionRepository = AgentIntelligenceORMRepository

__all__ = ['AgentIntelligenceORMRepository', 'AgentDecisionRepository', 'AgentDecision']
