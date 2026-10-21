"""池级盯盘绑定 ORM（2026-10-20）：stock_pools ↔ watch_rules 接线配置"""
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, func

from ..base import Base


class WatchPoolBinding(Base):
    """盯盘池绑定：一个 stock_pools 池 → 一批盯盘规则（经 pool_watch_service reconcile）"""
    __tablename__ = 'watch_pool_bindings'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    pool_id = Column(Integer, nullable=False, comment='quant.stock_pools.id')
    pool_name = Column(String(128), nullable=False, server_default='', comment='绑定时的池名快照')
    conditions_template = Column(JSON, nullable=True, comment='池级统一条件模板（jsonb）')
    use_member_points = Column(Boolean, nullable=False, server_default='true',
                               comment='成员自带 buy_point/sell_point 是否生成 price_break 条件')
    member_points_mode = Column(String(16), nullable=False, server_default='breakout',
                                comment='买卖点语义：breakout=上破买/下破卖；pullback=下破买/上破卖')
    intent = Column(String(30), nullable=False, server_default='trend_observe', comment='生成规则的意图')
    account = Column(String(60), nullable=True, comment='归属账户（交易类意图必填，rule_guard 把关）')
    cooldown_sec = Column(Integer, nullable=True, comment='生成规则的默认冷却秒数')
    max_members = Column(Integer, nullable=False, server_default='100',
                         comment='单绑定最大成员数（防爆量，超出拒绝同步）')
    enabled = Column(Boolean, nullable=False, server_default='true')
    last_sync_summary = Column(JSON, nullable=True, comment='最近一次 reconcile 结果快照')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
