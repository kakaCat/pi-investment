"""
知识管理服务 - KnowledgeService

管理Agent的知识积累、验证和应用
"""
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from domain.ports.repository_ports_extended import (
    IAgentKnowledgeRepository
)

logger = structlog.get_logger(__name__)


class KnowledgeService:
    """知识管理服务 - 完整版（接通repository）"""

    def __init__(self):
        """初始化服务"""
        self.repository = IAgentKnowledgeRepository()
        logger.info("✅ KnowledgeService initialized with repository")

    @property
    def session(self):
        """获取 session（通过 repository）"""
        return self.repository.session

    def get_active_knowledge(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取活跃的知识

        Args:
            domain: 知识领域过滤（可选）

        Returns:
            知识列表
        """
        logger.info(f"🔍 查询活跃知识: domain={domain}")

        if domain:
            return self.repository.get_by_domain(domain)
        else:
            # 获取所有活跃知识
            query = self.session.query(self.repository.model).filter_by(status='active')
            results = query.all()
            return [self.repository._to_dict(r) for r in results]

    def apply_knowledge(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        应用知识到当前决策

        Args:
            context: 决策上下文

        Returns:
            匹配的知识列表
        """
        logger.info(f"🔍 应用知识: context keys={list(context.keys())}")

        # 根据上下文匹配知识
        domain = context.get('domain')
        knowledge_type = context.get('knowledge_type')

        if domain:
            return self.repository.get_by_domain(domain, knowledge_type)
        else:
            # 返回所有活跃知识
            return self.get_active_knowledge()

    def get_knowledge_summary(self) -> Dict[str, Any]:
        """
        生成知识库摘要

        Returns:
            知识库统计
        """
        logger.info("📊 生成知识库摘要")

        # 统计所有知识
        all_knowledge = self.session.query(self.repository.model).all()
        total = len(all_knowledge)

        # 按置信度分类
        by_confidence = {'high': 0, 'medium': 0, 'low': 0}
        for k in all_knowledge:
            if k.confidence >= 0.7:
                by_confidence['high'] += 1
            elif k.confidence >= 0.4:
                by_confidence['medium'] += 1
            else:
                by_confidence['low'] += 1

        # 按领域分类
        by_domain = {}
        for k in all_knowledge:
            by_domain[k.domain] = by_domain.get(k.domain, 0) + 1

        # 按类型分类
        by_type = {}
        for k in all_knowledge:
            by_type[k.knowledge_type] = by_type.get(k.knowledge_type, 0) + 1

        # 统计最近一周新增
        from datetime import timedelta
        week_ago = datetime.now() - timedelta(days=7)
        weekly_new = sum(1 for k in all_knowledge if k.learned_at and k.learned_at >= week_ago)

        return {
            'total_knowledge': total,
            'weekly_new': weekly_new,
            'by_confidence': by_confidence,
            'by_domain': by_domain,
            'by_type': by_type
        }

    def validate_knowledge(self, knowledge_id: str, success: bool) -> Dict[str, Any]:
        """
        验证知识（应用后反馈结果）

        Args:
            knowledge_id: 知识ID
            success: 应用该知识后是否成功

        Returns:
            更新后的知识
        """
        logger.info(f"🔍 验证知识: {knowledge_id}, success={success}")

        # 获取现有知识
        knowledge = self.repository.get_by_knowledge_id(knowledge_id)
        if not knowledge:
            logger.warning(f"Knowledge not found: {knowledge_id}")
            return {
                'id': knowledge_id,
                'success': success,
                'validation_count': 0,
                'success_count': 0,
                'confidence': 0.0
            }

        # 更新统计
        validation_count = knowledge.get('validation_count', 0) + 1
        success_count = knowledge.get('success_count', 0) + (1 if success else 0)
        confidence = success_count / validation_count if validation_count > 0 else 0.0

        # 写回数据库
        self.repository.upsert_knowledge(
            knowledge_id=knowledge_id,
            domain=knowledge['domain'],
            knowledge_type=knowledge['knowledge_type'],
            content=knowledge['content'],
            confidence=confidence,
            validation_count=validation_count,
            success_count=success_count,
            evidence=knowledge.get('evidence')
        )

        return {
            'id': knowledge_id,
            'success': success,
            'validation_count': validation_count,
            'success_count': success_count,
            'confidence': confidence
        }
