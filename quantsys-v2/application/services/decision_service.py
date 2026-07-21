"""
决策管理服务 - DecisionService

管理Agent的所有决策记录、评估和查询
"""
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime
from adapters.outbound.repositories import (
    AgentIntelligenceORMRepository,
    PoolChangeLogRepository
)

logger = structlog.get_logger(__name__)


class DecisionService:
    """决策管理服务"""

    def __init__(self):
        """初始化服务"""
        self.decision_repo = AgentIntelligenceORMRepository()
        self.change_log_repo = PoolChangeLogRepository()

    def record_decision(self, decision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        记录一个决策

        Args:
            decision_data: {
                'decision_type': 'create_pool',  # 决策类型
                'context': {...},                 # 决策上下文
                'parameters': {...},              # 决策参数
                'reasoning': '...',               # 推理过程
                'related_entity_type': 'pool',    # 关联实体类型
                'related_entity_id': '5'          # 关联实体ID
            }

        Returns:
            创建的决策记录
        """
        logger.info(f"📝 记录决策: {decision_data.get('decision_type')}")

        try:
            # 验证必需字段
            self._validate_decision_data(decision_data)

            # 创建决策记录
            decision = self.decision_repo.create_decision(decision_data)

            logger.info(f"✅ 决策已记录: {decision['decision_id']}")
            return decision

        except Exception as e:
            logger.error(f"❌ 记录决策失败: {e}", exc_info=True)
            raise

    def record_pool_change(self, pool_change_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        记录池子变更

        Args:
            pool_change_data: {
                'pool_id': 5,
                'action': 'create',
                'symbol': '600519.SH',  # 可选，add/remove时需要
                'reason': '...',
                'agent_decision_id': 'dec_001',
                'before_state': {...},
                'after_state': {...}
            }

        Returns:
            变更记录
        """
        logger.info(f"📋 记录池子变更: pool_id={pool_change_data.get('pool_id')}")

        try:
            change_log = self.change_log_repo.log_change(pool_change_data)

            logger.info(f"✅ 变更已记录: log_id={change_log['id']}")
            return change_log

        except Exception as e:
            logger.error(f"❌ 记录变更失败: {e}", exc_info=True)
            raise

    def update_decision_result(self, decision_id: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新决策关联的实体

        Args:
            decision_id: 决策ID
            result_data: {
                'related_entity_type': 'pool',
                'related_entity_id': '5'
            }

        Returns:
            更新后的决策
        """
        logger.info(f"🔄 更新决策结果: {decision_id}")

        try:
            decision = self.decision_repo.get_decision(decision_id)
            if not decision:
                raise ValueError(f"决策不存在: {decision_id}")

            # 更新关联实体
            decision['related_entity_type'] = result_data.get('related_entity_type')
            decision['related_entity_id'] = result_data.get('related_entity_id')

            updated = self.decision_repo.update_decision(decision_id, decision)

            logger.info(f"✅ 决策结果已更新")
            return updated

        except Exception as e:
            logger.error(f"❌ 更新决策结果失败: {e}", exc_info=True)
            raise

    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个决策

        Args:
            decision_id: 决策ID

        Returns:
            决策记录
        """
        try:
            return self.decision_repo.get_decision(decision_id)
        except Exception as e:
            logger.error(f"❌ 获取决策失败: {e}")
            return None

    def get_decision_history(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        decision_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        查询决策历史

        Args:
            entity_type: 实体类型过滤（pool/stock等）
            entity_id: 实体ID过滤
            decision_type: 决策类型过滤
            limit: 返回数量限制

        Returns:
            决策列表
        """
        logger.info(f"🔍 查询决策历史: type={entity_type}, id={entity_id}")

        try:
            if entity_type and entity_id:
                decisions = self.decision_repo.get_decisions_by_entity(
                    entity_type,
                    entity_id
                )
            else:
                decisions = self.decision_repo.get_recent_decisions(limit)

            # 类型过滤
            if decision_type:
                decisions = [
                    d for d in decisions
                    if d.get('decision_type') == decision_type
                ]

            logger.info(f"✅ 找到{len(decisions)}条决策记录")
            return decisions[:limit]

        except Exception as e:
            logger.error(f"❌ 查询决策历史失败: {e}", exc_info=True)
            return []

    def get_pool_change_history(
        self,
        pool_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        查询池子变更历史

        Args:
            pool_id: 池子ID（可选）
            limit: 返回数量限制

        Returns:
            变更记录列表
        """
        logger.info(f"🔍 查询池子变更历史: pool_id={pool_id}")

        try:
            if pool_id:
                changes = self.change_log_repo.get_pool_history(pool_id)
            else:
                changes = self.change_log_repo.get_recent_changes(limit)

            logger.info(f"✅ 找到{len(changes)}条变更记录")
            return changes[:limit]

        except Exception as e:
            logger.error(f"❌ 查询变更历史失败: {e}", exc_info=True)
            return []

    def get_pending_evaluations(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        获取待评估的决策

        Args:
            days: 创建超过N天的决策

        Returns:
            待评估决策列表
        """
        logger.info(f"🔍 查询待评估决策（>{days}天）")

        try:
            decisions = self.decision_repo.list_pending_evaluations(days)

            logger.info(f"✅ 找到{len(decisions)}条待评估决策")
            return decisions

        except Exception as e:
            logger.error(f"❌ 查询待评估决策失败: {e}", exc_info=True)
            return []

    def _validate_decision_data(self, data: Dict[str, Any]):
        """
        验证决策数据

        Args:
            data: 决策数据

        Raises:
            ValueError: 数据不合法
        """
        required_fields = ['decision_type', 'context', 'parameters', 'reasoning']

        for field in required_fields:
            if field not in data:
                raise ValueError(f"缺少必需字段: {field}")

        # 验证决策类型
        valid_types = [
            'create_pool',
            'update_pool',
            'delete_pool',
            'refresh_pool',
            'add_stock',
            'remove_stock',
            'select_strategy',
            'screening',
            'auto_risk_control',
            'auto_capture_opportunity'
        ]

        if data['decision_type'] not in valid_types:
            logger.warning(f"未知的决策类型: {data['decision_type']}")

    def generate_decision_report(
        self,
        entity_type: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """
        生成决策报告

        Args:
            entity_type: 实体类型
            entity_id: 实体ID

        Returns:
            {
                'total_decisions': 10,
                'by_type': {...},
                'evaluation_status': {...},
                'success_rate': 0.75,
                'recent_decisions': [...]
            }
        """
        logger.info(f"📊 生成决策报告: {entity_type}/{entity_id}")

        try:
            decisions = self.get_decision_history(entity_type, entity_id, limit=100)

            # 统计
            total = len(decisions)
            by_type = {}
            evaluation_status = {
                'pending': 0,
                'evaluated': 0
            }
            success_count = 0

            for dec in decisions:
                # 按类型统计
                dec_type = dec.get('decision_type', 'unknown')
                by_type[dec_type] = by_type.get(dec_type, 0) + 1

                # 评估状态
                status = dec.get('evaluation_status', 'pending')
                evaluation_status[status] = evaluation_status.get(status, 0) + 1

                # 成功率
                if dec.get('success') is True:
                    success_count += 1

            # 成功率
            evaluated_count = evaluation_status.get('evaluated', 0)
            success_rate = success_count / evaluated_count if evaluated_count > 0 else 0

            report = {
                'total_decisions': total,
                'by_type': by_type,
                'evaluation_status': evaluation_status,
                'success_rate': success_rate,
                'recent_decisions': decisions[:10]
            }

            logger.info(f"✅ 决策报告生成完成")
            return report

        except Exception as e:
            logger.error(f"❌ 生成决策报告失败: {e}", exc_info=True)
            return {
                'total_decisions': 0,
                'by_type': {},
                'evaluation_status': {},
                'success_rate': 0,
                'recent_decisions': []
            }
