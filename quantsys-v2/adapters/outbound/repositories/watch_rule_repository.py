"""WatchEngine 盯盘规则/触发记录 ORM Repository"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Text, ForeignKey, or_
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
    # account：规则归属账户（account_name 全名）。None=通用观察（无主/跨账户候选，
    # 2026-09-04 看板按账户分组展示用）。历史规则由迁移脚本按 context/持仓回填。
    account = Column(String(50))
    # notify_mode：direct=v2 直发飞书（纯提醒）；agent=唤醒 LLM 分析后再发
    # （2026-09-02 修复：模型此前漏此列，致 getattr 拿不到、agent 模式静默降级为 direct）
    notify_mode = Column(String(20), default='direct')
    # RFC 011：分层提醒与自动升级
    action_hint = Column(JSONB, default={})
    escalation_policy = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    # ── 价值生命周期（REQ-f08def P1/P4/P7，RFC 014 v3 §7.1）──────────────
    # 2026-09-11 实测教训（两次踩）：①migration 加了 DB 列但 ORM 未声明 →
    # intent/lifecycle_stage/scope/价值账本对 ORM 完全不可见，update_fields 的改动
    # 也不落库（#120 改成 entry 看似成功、库里仍是旧值）；②锚点 agent_response 在
    # WatchTrigger 里也有，第一次补列插错了类。补 ORM 列时必须做唯一性断言。
    intent = Column(String(30))
    lifecycle_stage = Column(String(30), default='tracking')
    scope = Column(String(20), default='symbol')
    target = Column(String(60))
    linked_account = Column(String(60))
    created_from = Column(String(80))
    next_action_hint = Column(String(160))
    last_reviewed_at = Column(DateTime)
    review_interval_days = Column(Integer)
    review_due_at = Column(DateTime)
    burst_count_window = Column(Integer, default=0)
    last_burst_alert_at = Column(DateTime)
    valuable_actions = Column(Integer, default=0)
    valuable_reviews = Column(Integer, default=0)
    interventions = Column(Integer, default=0)
    noise_triggers = Column(Integer, default=0)
    tokens_cost = Column(Numeric(12, 4), default=0)
    last_value_at = Column(DateTime)


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
    # ── 处置状态机（REQ-f08def，2026-09-11）─────────────────────────────
    # 为什么要落库：实测近 200 条触发 agent_response 全为 null，触发无终态 = 无闭环。
    # disposition 让每条触发有明确归属：机械归档 / 去重合并 / 升级给 agent / 待处置 / 已处置。
    disposition = Column(String(20), default='pending')
    disposition_reason = Column(Text)
    disposition_by = Column(String(50))
    disposition_at = Column(DateTime)
    dup_of = Column(Integer)


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
        'account': rule.account,
        'notify_mode': rule.notify_mode,
        'action_hint': rule.action_hint,
        'escalation_policy': rule.escalation_policy,
        'created_at': rule.created_at.isoformat() if rule.created_at else None,
        'updated_at': rule.updated_at.isoformat() if rule.updated_at else None,
        # ── 价值生命周期字段（REQ-f08def P1，RFC 014 v3 §7.1）──
        # 没有 intent/lifecycle_stage，agent 拿到触发不知道该回答什么问题。
        'intent': getattr(rule, 'intent', None),
        'lifecycle_stage': getattr(rule, 'lifecycle_stage', None),
        'scope': getattr(rule, 'scope', None),
        'target': getattr(rule, 'target', None),
        'linked_account': getattr(rule, 'linked_account', None),
        'created_from': getattr(rule, 'created_from', None),
        'next_action_hint': getattr(rule, 'next_action_hint', None),
        'last_reviewed_at': rule.last_reviewed_at.isoformat() if getattr(rule, 'last_reviewed_at', None) else None,
        'review_interval_days': getattr(rule, 'review_interval_days', None),
        'review_due_at': rule.review_due_at.isoformat() if getattr(rule, 'review_due_at', None) else None,
        'value_ledger': {
            'valuable_actions': getattr(rule, 'valuable_actions', 0) or 0,
            'valuable_reviews': getattr(rule, 'valuable_reviews', 0) or 0,
            'interventions': getattr(rule, 'interventions', 0) or 0,
            'noise_triggers': getattr(rule, 'noise_triggers', 0) or 0,
            'tokens_cost': getattr(rule, 'tokens_cost', 0.0) or 0.0,
            'last_value_at': rule.last_value_at.isoformat() if getattr(rule, 'last_value_at', None) else None,
        },
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
        # 处置状态机字段（REQ-f08def）
        'disposition': getattr(t, 'disposition', None),
        'disposition_reason': getattr(t, 'disposition_reason', None),
        'disposition_by': getattr(t, 'disposition_by', None),
        'disposition_at': t.disposition_at.isoformat() if getattr(t, 'disposition_at', None) else None,
        'dup_of': getattr(t, 'dup_of', None),
    }


class WatchRuleRepository(BaseORMRepository[WatchRule]):
    model = WatchRule

    def create_rule(self, symbol, conditions, context=None, cost_price=None,
                    active_window=None, expires_at=None, created_by='agent',
                    account=None) -> WatchRule:
        rule = WatchRule(
            symbol=symbol, conditions=conditions, context=context,
            cost_price=cost_price, active_window=active_window,
            expires_at=expires_at, created_by=created_by, enabled=True,
            account=account,
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
                   enabled: Optional[bool] = None,
                   account: Optional[str] = None) -> List[WatchRule]:
        """account=某账户时返回「该账户归属 + 通用观察(account IS NULL)」——
        看板按账户展示盯盘需要两组都可见；不传则返回全部。"""
        q = self.session.query(WatchRule)
        if symbol:
            q = q.filter(WatchRule.symbol == symbol)
        if enabled is not None:
            q = q.filter(WatchRule.enabled.is_(enabled))
        if account:
            q = q.filter(or_(WatchRule.account == account, WatchRule.account.is_(None)))
        return q.order_by(WatchRule.id.desc()).all()

    def update_fields(self, rule_id: int, **fields) -> Optional[WatchRule]:
        rule = self.get_by_id(rule_id)
        if rule is None:
            return None
        allowed = {'symbol', 'enabled', 'conditions', 'context',
                   'cost_price', 'active_window', 'expires_at', 'account',
                   'notify_mode',  # 2026-09-05 补：notify_mode 曾被白名单静默丢弃
                   # 2026-09-11（w-c8cae280 / REQ-f08def Phase 3）：规则演化（改分级/改动作/改升级策略）
                   # 需要这两个字段可写，否则 agent 无法按 RFC 014 §4 的反馈边调整规则。
                   'action_hint', 'escalation_policy',
                   # REQ-f08def P2：规则重配置所需字段（价值账本计数由系统维护，不在此列）
                   'intent', 'lifecycle_stage', 'scope', 'target',
                   'linked_account', 'created_from', 'next_action_hint',
                   'review_interval_days', 'review_due_at'}
        for key, value in fields.items():
            if key in allowed:
                setattr(rule, key, value)
        rule.updated_at = datetime.now()
        return self.update(rule)


class WatchTriggerRepository(BaseORMRepository[WatchTrigger]):
    model = WatchTrigger

    def record(self, rule_id, symbol, condition, trigger_price,
               detail=None, notified=False, disposition='pending',
               disposition_reason=None, disposition_by='system',
               dup_of=None) -> WatchTrigger:
        """落一条触发 + 其处置初态（REQ-f08def）。

        disposition 由 application/services/watch_engine/disposition.decide() 决定：
        机械可判的（observe/message 类、去重合并）当场收敛，不唤醒 agent。
        """
        trigger = WatchTrigger(
            rule_id=rule_id, symbol=symbol, condition=condition,
            trigger_price=trigger_price, detail=detail, notified=notified,
            disposition=disposition,
            disposition_reason=disposition_reason,
            disposition_by=disposition_by,
            disposition_at=datetime.now() if disposition not in ('pending', 'escalated') else None,
            dup_of=dup_of,
        )
        return self.create(trigger)

    def update_disposition(self, trigger_id: int, disposition: str,
                           reason: str = None, by: str = 'agent') -> Optional[WatchTrigger]:
        """处置一条触发（handled / ignored / expired）。ignored 必须带 reason。"""
        from domain.watch.services.disposition import DISPOSITION_IGNORED
        if disposition == DISPOSITION_IGNORED and not (reason or '').strip():
            raise ValueError('ignored 状态必须填写 reason（为什么知悉但不动作）')
        trigger = self.get_by_id(trigger_id)
        if trigger is None:
            return None
        trigger.disposition = disposition
        trigger.disposition_reason = reason
        trigger.disposition_by = by
        trigger.disposition_at = datetime.now()
        self.session.commit()
        return trigger


    def get_rule_trigger_stats(self) -> dict:
        """批量触发统计（元触发复核用，避免 N+1）：{rule_id: {today, last_at}}

        对应 domain/watch/ports.ITriggerHistoryRepository 的批量口径扩展。
        """
        from sqlalchemy import text
        from infrastructure.persistence.database.engine import get_engine
        out = {}
        try:
            with get_engine().connect() as conn:
                rows = conn.execute(text(
                    "SELECT rule_id, count(*) FILTER (WHERE triggered_at >= CURRENT_DATE) AS today_cnt,"
                    "       max(triggered_at) AS last_at"
                    "  FROM quant.watch_triggers GROUP BY rule_id"
                )).fetchall()
            for r in rows:
                out[int(r[0])] = {"today": int(r[1] or 0), "last_at": r[2]}
        except Exception as e:
            import structlog
            structlog.get_logger(__name__).warning("批量触发统计读取失败", error=str(e))
        return out

    def list_triggers(self, symbol: Optional[str] = None,
                      disposition: Optional[str] = None,
                      dispositions: Optional[tuple] = None,
                      limit: int = 200) -> List[WatchTrigger]:
        """按状态查触发（盘后未处置清单的数据源）"""
        q = self.session.query(WatchTrigger)
        if symbol:
            q = q.filter(WatchTrigger.symbol == symbol)
        if disposition:
            q = q.filter(WatchTrigger.disposition == disposition)
        if dispositions:
            q = q.filter(WatchTrigger.disposition.in_(list(dispositions)))
        return q.order_by(WatchTrigger.triggered_at.desc()).limit(limit).all()

    def list_by_symbol(self, symbol: Optional[str] = None, limit: int = 50) -> List[WatchTrigger]:
        q = self.session.query(WatchTrigger)
        if symbol:
            q = q.filter(WatchTrigger.symbol == symbol)
        return q.order_by(WatchTrigger.triggered_at.desc()).limit(limit).all()
