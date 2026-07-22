"""WatchEngine 盯盘规则/触发记录 ORM Repository"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base


class WatchRule(Base):
    __tablename__ = 'watch_rules'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    enabled = Column(Boolean, default=True)
    conditions = Column(JSONB, nullable=False)
    context = Column(Text)
    cost_price = Column(Numeric(12, 4))
    active_window = Column(JSONB)
    expires_at = Column(DateTime)
    created_by = Column(String(50), default='agent')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class WatchTrigger(Base):
    __tablename__ = 'watch_triggers'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('quant.watch_rules.id', ondelete='SET NULL'))
    symbol = Column(String(20), nullable=False)
    condition = Column(JSONB, nullable=False)
    trigger_price = Column(Numeric(12, 4))
    detail = Column(JSONB)
    agent_response = Column(JSONB)
    notified = Column(Boolean, default=False)
    triggered_at = Column(DateTime, default=datetime.now)


def rule_to_dict(rule: WatchRule) -> dict:
    """序列化为 API 响应 dict（snake_case，与现有契约风格一致）"""
    return {
        'id': rule.id,
        'symbol': rule.symbol,
        'enabled': rule.enabled,
        'conditions': rule.conditions,
        'context': rule.context,
        'cost_price': float(rule.cost_price) if rule.cost_price is not None else None,
        'active_window': rule.active_window,
        'expires_at': rule.expires_at.isoformat() if rule.expires_at else None,
        'created_by': rule.created_by,
        'created_at': rule.created_at.isoformat() if rule.created_at else None,
        'updated_at': rule.updated_at.isoformat() if rule.updated_at else None,
    }


def trigger_to_dict(t: WatchTrigger) -> dict:
    return {
        'id': t.id,
        'rule_id': t.rule_id,
        'symbol': t.symbol,
        'condition': t.condition,
        'trigger_price': float(t.trigger_price) if t.trigger_price is not None else None,
        'detail': t.detail,
        'agent_response': t.agent_response,
        'notified': t.notified,
        'triggered_at': t.triggered_at.isoformat() if t.triggered_at else None,
    }


class WatchRuleRepository(BaseORMRepository[WatchRule]):
    model = WatchRule

    def create_rule(self, symbol, conditions, context=None, cost_price=None,
                    active_window=None, expires_at=None, created_by='agent') -> WatchRule:
        rule = WatchRule(
            symbol=symbol, conditions=conditions, context=context,
            cost_price=cost_price, active_window=active_window,
            expires_at=expires_at, created_by=created_by, enabled=True,
        )
        return self.create(rule)

    def list_enabled(self) -> List[WatchRule]:
        """启用的规则（排除已过期）"""
        return (
            self.session.query(WatchRule)
            .filter(WatchRule.enabled.is_(True))
            .filter((WatchRule.expires_at.is_(None)) | (WatchRule.expires_at > datetime.now()))
            .all()
        )

    def list_rules(self, symbol: Optional[str] = None,
                   enabled: Optional[bool] = None) -> List[WatchRule]:
        q = self.session.query(WatchRule)
        if symbol:
            q = q.filter(WatchRule.symbol == symbol)
        if enabled is not None:
            q = q.filter(WatchRule.enabled.is_(enabled))
        return q.order_by(WatchRule.id.desc()).all()

    def update_fields(self, rule_id: int, **fields) -> Optional[WatchRule]:
        rule = self.get_by_id(rule_id)
        if rule is None:
            return None
        allowed = {'symbol', 'enabled', 'conditions', 'context',
                   'cost_price', 'active_window', 'expires_at'}
        for key, value in fields.items():
            if key in allowed:
                setattr(rule, key, value)
        rule.updated_at = datetime.now()
        return self.update(rule)


class WatchTriggerRepository(BaseORMRepository[WatchTrigger]):
    model = WatchTrigger

    def record(self, rule_id, symbol, condition, trigger_price,
               detail=None, notified=False) -> WatchTrigger:
        trigger = WatchTrigger(
            rule_id=rule_id, symbol=symbol, condition=condition,
            trigger_price=trigger_price, detail=detail, notified=notified,
        )
        return self.create(trigger)

    def list_by_symbol(self, symbol: Optional[str] = None, limit: int = 50) -> List[WatchTrigger]:
        q = self.session.query(WatchTrigger)
        if symbol:
            q = q.filter(WatchTrigger.symbol == symbol)
        return q.order_by(WatchTrigger.triggered_at.desc()).limit(limit).all()
