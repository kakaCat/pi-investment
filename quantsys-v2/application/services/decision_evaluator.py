"""
决策评估引擎 - DecisionEvaluator

自动评估历史决策的结果，提取经验教训
"""
from domain.ports import IAgentDecisionRepository, IStockPoolRepository
import structlog
from typing import Dict, Any, List
from datetime import datetime, timedelta
from application.services.knowledge_service import KnowledgeService

logger = structlog.get_logger(__name__)


class DecisionEvaluator:
    """决策评估器 - 评估决策结果并提取知识"""

    def __init__(self):
        """初始化服务"""
        self.decision_repo = IAgentIntelligenceRepository()
        self.pool_repo = IStockPoolRepository()
        self.knowledge_service = KnowledgeService()

    def batch_evaluate_pending(self, days: int = 7) -> Dict[str, Any]:
        """
        批量评估待评估的决策

        Args:
            days: 创建超过N天的决策才评估

        Returns:
            {
                'evaluated_count': 10,
                'success_count': 7,
                'failed_count': 3,
                'knowledge_extracted': 5
            }
        """
        logger.info(f"📊 开始批量评估决策（>{days}天）")

        try:
            # 获取待评估决策
            pending_decisions = self.decision_repo.list_pending_evaluations(days)

            if not pending_decisions:
                logger.info("没有待评估的决策")
                return {
                    'evaluated_count': 0,
                    'success_count': 0,
                    'failed_count': 0,
                    'knowledge_extracted': 0
                }

            evaluated_count = 0
            success_count = 0
            failed_count = 0
            knowledge_extracted = 0

            for decision in pending_decisions:
                try:
                    # 评估单个决策
                    result = self.evaluate_decision(decision['decision_id'])

                    evaluated_count += 1

                    if result['success']:
                        success_count += 1

                        # 从成功决策中提取知识
                        knowledge = self.knowledge_service.extract_knowledge_from_decision(result)
                        if knowledge:
                            knowledge_extracted += 1
                    else:
                        failed_count += 1

                except Exception as e:
                    logger.warning(f"评估决策失败: {decision['decision_id']} - {e}")
                    continue

            summary = {
                'evaluated_count': evaluated_count,
                'success_count': success_count,
                'failed_count': failed_count,
                'knowledge_extracted': knowledge_extracted
            }

            logger.info(
                f"✅ 批量评估完成: "
                f"{evaluated_count}条评估，"
                f"{success_count}条成功，"
                f"{failed_count}条失败，"
                f"提取{knowledge_extracted}条知识"
            )

            return summary

        except Exception as e:
            logger.error(f"❌ 批量评估失败: {e}", exc_info=True)
            raise

    def evaluate_decision(self, decision_id: str) -> Dict[str, Any]:
        """
        评估单个决策

        Args:
            decision_id: 决策ID

        Returns:
            评估结果 {
                'decision_id': 'dec_001',
                'success': True,
                'profit': 8.5,  # %
                'days_held': 7,
                'sharpe_ratio': 1.8,
                'max_drawdown': -3.2,
                'learned_lesson': '...',
                'confidence_score': 0.85
            }
        """
        logger.info(f"📊 评估决策: {decision_id}")

        try:
            # 获取决策
            decision = self.decision_repo.get_decision(decision_id)
            if not decision:
                raise ValueError(f"决策不存在: {decision_id}")

            # 根据决策类型评估
            decision_type = decision.get('decision_type')

            if decision_type in ['create_pool', 'update_pool']:
                evaluation = self._evaluate_pool_decision(decision)
            elif decision_type in ['add_stock', 'remove_stock']:
                evaluation = self._evaluate_stock_decision(decision)
            else:
                # 其他类型暂时标记为成功
                evaluation = {
                    'success': True,
                    'learned_lesson': f'{decision_type}决策已执行'
                }

            # 更新决策记录
            self.decision_repo.update_evaluation(decision_id, evaluation)

            logger.info(f"✅ 决策评估完成: success={evaluation.get('success')}")

            return {
                'decision_id': decision_id,
                **decision,
                **evaluation
            }

        except Exception as e:
            logger.error(f"❌ 评估决策失败: {e}", exc_info=True)
            raise

    def _evaluate_pool_decision(self, decision: Dict) -> Dict[str, Any]:
        """
        评估池子相关决策

        Args:
            decision: 决策记录

        Returns:
            评估结果
        """
        try:
            # 获取关联的池子
            pool_id = decision.get('related_entity_id')
            if not pool_id:
                return {
                    'success': False,
                    'learned_lesson': '无法找到关联的池子'
                }

            pool = self.pool_repo.get_pool(int(pool_id))
            if not pool:
                return {
                    'success': False,
                    'learned_lesson': '池子已被删除'
                }

            # 计算收益指标
            created_at = decision.get('created_at')
            days_held = (datetime.now() - created_at).days if created_at else 0

            # 简化评估：基于池子状态
            # TODO: 实际应该计算收益率、夏普比率等
            profit = 0.0  # 占位符，实际需要计算

            # 判断成功/失败
            # 简化判断：持有7天以上且未删除 = 成功
            success = days_held >= 7 and pool.get('status') != 'deleted'

            evaluation = {
                'success': success,
                'profit': profit,
                'days_held': days_held,
                'learned_lesson': self._generate_lesson(decision, success, profit)
            }

            return evaluation

        except Exception as e:
            logger.warning(f"评估池子决策失败: {e}")
            return {
                'success': False,
                'learned_lesson': f'评估失败: {str(e)}'
            }

    def _evaluate_stock_decision(self, decision: Dict) -> Dict[str, Any]:
        """
        评估股票相关决策

        Args:
            decision: 决策记录

        Returns:
            评估结果
        """
        # 简化实现
        return {
            'success': True,
            'learned_lesson': '股票操作已执行'
        }

    def _generate_lesson(self, decision: Dict, success: bool, profit: float) -> str:
        """
        生成经验教训

        Args:
            decision: 决策记录
            success: 是否成功
            profit: 收益率

        Returns:
            经验教训描述
        """
        context = decision.get('context', {})
        decision_type = decision.get('decision_type', '')

        parts = []

        # 上下文
        if 'market_phase' in context:
            parts.append(f"在{context['market_phase']}阶段")

        if 'sector' in context:
            parts.append(f"{context['sector']}板块")

        # 操作
        if decision_type == 'create_pool':
            parts.append("创建池子")

        # 结果
        if success:
            if profit > 0:
                parts.append(f"收益{profit:.1f}%")
            else:
                parts.append("策略有效")
        else:
            parts.append("策略失效")

        return '，'.join(parts) if parts else '决策已执行'
