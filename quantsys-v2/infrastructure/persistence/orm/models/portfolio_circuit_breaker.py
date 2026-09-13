"""组合级回撤熔断状态表（quant.portfolio_circuit_breaker）。

建立背景（2026-09-14，w-32314d00，REQ-24e15d B4-b）：
    该表此前无 ORM 模型，读写内联在 application/services/portfolio_breaker_service.py
    （2 处 db_cursor + 一段带 CASE/COALESCE 的 UPSERT）。

这张表是**交易网关的硬拦截依据**（trade_guard 买入方向据此拒单），
故服务侧保留 fail-open 降级；模型/仓储只负责数据访问。
"""
from sqlalchemy import Boolean, Column, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..base import Base

__all__ = ['PortfolioCircuitBreaker']


class PortfolioCircuitBreaker(Base):
    """组合熔断状态（每账户一行）

    对应数据库表：quant.portfolio_circuit_breaker
    主键：account_name
    """
    __tablename__ = 'portfolio_circuit_breaker'
    __table_args__ = {'schema': 'quant'}

    account_name = Column(String, primary_key=True)
    active = Column(Boolean, nullable=False)
    triggered_at = Column(DateTime(timezone=True))
    # ⚠️ numeric（不是 float）—— 读取时需显式转 float，否则 JSON 序列化会炸
    triggered_drawdown = Column(Numeric)
    actions_taken = Column(JSONB)
    unblock_condition = Column(Text)
    note = Column(Text)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<PortfolioCircuitBreaker(account='{self.account_name}', active={self.active})>"
