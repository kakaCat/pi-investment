"""
条件规则ORM模型
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, TIMESTAMP, JSON, Float
from sqlalchemy.sql import func
from infrastructure.persistence.orm.base import Base


class ConditionRule(Base):
    """条件规则模型"""
    __tablename__ = 'condition_rules'
    __table_args__ = {'schema': 'quant'}

    rule_id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    condition_type = Column(String(50), nullable=False)  # price, volume, indicator, etc.
    symbol = Column(String(20))  # 可为空表示全市场
    condition_expr = Column(Text, nullable=False)  # 条件表达式
    threshold_value = Column(Float)
    comparison_op = Column(String(10))  # >, <, >=, <=, ==, !=
    action = Column(String(100))  # 触发后的动作
    action_params = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    cooldown_seconds = Column(Integer, default=300)  # 冷却时间
    last_triggered_at = Column(TIMESTAMP)
    trigger_count = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100))

    def to_dict(self):
        """转换为字典"""
        return {
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'description': self.description,
            'condition_type': self.condition_type,
            'symbol': self.symbol,
            'condition_expr': self.condition_expr,
            'threshold_value': self.threshold_value,
            'comparison_op': self.comparison_op,
            'action': self.action,
            'action_params': self.action_params,
            'is_active': self.is_active,
            'priority': self.priority,
            'cooldown_seconds': self.cooldown_seconds,
            'last_triggered_at': self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            'trigger_count': self.trigger_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
        }


class ConditionResult(Base):
    """条件监控结果模型"""
    __tablename__ = 'condition_results'
    __table_args__ = {'schema': 'quant'}

    result_id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, nullable=False)
    symbol = Column(String(20))
    check_time = Column(TIMESTAMP, server_default=func.now())
    condition_met = Column(Boolean, nullable=False)
    actual_value = Column(Float)
    threshold_value = Column(Float)
    trigger_action = Column(String(100))
    action_result = Column(JSON)
    message = Column(Text)

    def to_dict(self):
        """转换为字典"""
        return {
            'result_id': self.result_id,
            'rule_id': self.rule_id,
            'symbol': self.symbol,
            'check_time': self.check_time.isoformat() if self.check_time else None,
            'condition_met': self.condition_met,
            'actual_value': self.actual_value,
            'threshold_value': self.threshold_value,
            'trigger_action': self.trigger_action,
            'action_result': self.action_result,
            'message': self.message,
        }
