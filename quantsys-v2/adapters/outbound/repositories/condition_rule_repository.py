"""
条件监控ORM Repository
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import structlog

from sqlalchemy import and_, or_
from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import ConditionRule, ConditionResult

logger = structlog.get_logger(__name__)

__all__ = ['ConditionRuleORMRepository', 'ConditionResultORMRepository']


class ConditionRuleORMRepository(BaseORMRepository[ConditionRule]):
    """条件规则ORM Repository

    示例用法：
        repo = ConditionRuleORMRepository()

        # 获取所有活跃规则
        active_rules = repo.get_active_rules()

        # 创建新规则
        rule = repo.create_rule({
            'rule_name': 'price_alert',
            'condition_type': 'price',
            'symbol': '000001',
            'condition_expr': 'close > threshold',
            'threshold_value': 10.0,
            'comparison_op': '>',
            'action': 'send_notification'
        })
    """

    model = ConditionRule

    def get_active_rules(
        self,
        condition_type: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> List[ConditionRule]:
        """获取所有活跃的规则

        Args:
            condition_type: 条件类型过滤（可选）
            symbol: 股票代码过滤（可选）

        Returns:
            活跃规则列表
        """
        try:
            query = self.session.query(ConditionRule).filter(
                ConditionRule.is_active == True
            )

            if condition_type:
                query = query.filter(ConditionRule.condition_type == condition_type)

            if symbol:
                query = query.filter(
                    or_(
                        ConditionRule.symbol == symbol,
                        ConditionRule.symbol.is_(None)  # 全市场规则
                    )
                )

            return query.order_by(ConditionRule.priority.desc()).all()
        except Exception as e:
            logger.error(f"Error getting active rules: {e}")
            return []

    def get_rule_by_name(self, rule_name: str) -> Optional[ConditionRule]:
        """根据规则名称获取规则

        Args:
            rule_name: 规则名称

        Returns:
            规则对象，不存在返回None
        """
        try:
            return self.session.query(ConditionRule).filter(
                ConditionRule.rule_name == rule_name
            ).first()
        except Exception as e:
            logger.error(f"Error getting rule by name {rule_name}: {e}")
            return None

    def create_rule(self, rule_data: Dict[str, Any]) -> Optional[ConditionRule]:
        """创建条件规则

        Args:
            rule_data: 规则数据字典

        Returns:
            创建的规则对象
        """
        try:
            rule = ConditionRule(
                rule_name=rule_data['rule_name'],
                description=rule_data.get('description'),
                condition_type=rule_data['condition_type'],
                symbol=rule_data.get('symbol'),
                condition_expr=rule_data['condition_expr'],
                threshold_value=rule_data.get('threshold_value'),
                comparison_op=rule_data.get('comparison_op'),
                action=rule_data.get('action'),
                action_params=rule_data.get('action_params', {}),
                is_active=rule_data.get('is_active', True),
                priority=rule_data.get('priority', 0),
                cooldown_seconds=rule_data.get('cooldown_seconds', 300),
                created_by=rule_data.get('created_by'),
            )
            return self.create(rule)
        except Exception as e:
            logger.error(f"Error creating rule: {e}")
            return None

    def update_rule(
        self,
        rule_name: str,
        updates: Dict[str, Any]
    ) -> bool:
        """更新规则

        Args:
            rule_name: 规则名称
            updates: 要更新的字段字典

        Returns:
            成功返回True
        """
        try:
            rule = self.get_rule_by_name(rule_name)
            if not rule:
                return False

            for key, value in updates.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)

            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating rule {rule_name}: {e}")
            self.session.rollback()
            return False

    def record_trigger(self, rule_id: int) -> bool:
        """记录规则触发

        Args:
            rule_id: 规则ID

        Returns:
            成功返回True
        """
        try:
            rule = self.get_by_id(rule_id)
            if not rule:
                return False

            rule.last_triggered_at = datetime.now()
            rule.trigger_count = (rule.trigger_count or 0) + 1
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error recording trigger for rule {rule_id}: {e}")
            self.session.rollback()
            return False

    def can_trigger(self, rule: ConditionRule) -> bool:
        """检查规则是否可以触发（考虑冷却时间）

        Args:
            rule: 规则对象

        Returns:
            可以触发返回True
        """
        if not rule.is_active:
            return False

        if not rule.last_triggered_at:
            return True

        cooldown_delta = timedelta(seconds=rule.cooldown_seconds)
        return datetime.now() - rule.last_triggered_at > cooldown_delta


class ConditionResultORMRepository(BaseORMRepository[ConditionResult]):
    """条件监控结果ORM Repository"""

    model = ConditionResult

    def record_result(self, result_data: Dict[str, Any]) -> Optional[ConditionResult]:
        """记录监控结果

        Args:
            result_data: 结果数据字典

        Returns:
            创建的结果对象
        """
        try:
            result = ConditionResult(
                rule_id=result_data['rule_id'],
                symbol=result_data.get('symbol'),
                condition_met=result_data['condition_met'],
                actual_value=result_data.get('actual_value'),
                threshold_value=result_data.get('threshold_value'),
                trigger_action=result_data.get('trigger_action'),
                action_result=result_data.get('action_result'),
                message=result_data.get('message'),
            )
            return self.create(result)
        except Exception as e:
            logger.error(f"Error recording result: {e}")
            return None

    def get_results_by_rule(
        self,
        rule_id: int,
        limit: int = 100
    ) -> List[ConditionResult]:
        """获取规则的历史结果

        Args:
            rule_id: 规则ID
            limit: 返回数量限制

        Returns:
            结果列表
        """
        try:
            return self.session.query(ConditionResult).filter(
                ConditionResult.rule_id == rule_id
            ).order_by(ConditionResult.check_time.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting results for rule {rule_id}: {e}")
            return []

    def get_triggered_results(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ConditionResult]:
        """获取触发的结果

        Args:
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            limit: 返回数量限制

        Returns:
            触发的结果列表
        """
        try:
            query = self.session.query(ConditionResult).filter(
                ConditionResult.condition_met == True
            )

            if start_time:
                query = query.filter(ConditionResult.check_time >= start_time)

            if end_time:
                query = query.filter(ConditionResult.check_time <= end_time)

            return query.order_by(ConditionResult.check_time.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting triggered results: {e}")
            return []
