"""信号测试日志表（quant.signal_test_log）。

建立背景（2026-09-14，w-32314d00，REQ-24e15d B3-b）：
    该表此前**没有 ORM 模型**，9 处读写全部内联在
    `application/services/signal_test_log.py` 里（含运行时 CREATE TABLE IF NOT EXISTS
    与三处 f-string 拼 WHERE 子句的聚合查询）。本模型把表结构变成一等公民，
    SQL 收敛到仓储层。

命名说明：模型叫 **SignalTestRecord** 而不是 SignalTestLog —— 后者是服务类名
（application/services/signal_test_log.py::SignalTestLog），同名会造成"到底在说服务还是说表"的混乱。
"""
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..base import Base

__all__ = ['SignalTestRecord']


class SignalTestRecord(Base):
    """信号测试记录（一条买入/卖出信号及其事后验证结果）

    对应数据库表：quant.signal_test_log
    主键：id
    """
    __tablename__ = 'signal_test_log'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    name = Column(String(100))
    strategy_name = Column(String(100), nullable=False)
    signal_date = Column(Date, nullable=False)
    action = Column(String(10), nullable=False)
    confidence = Column(Float)
    signal_price = Column(Float)
    entry_price = Column(Float)
    stop_loss = Column(Float)
    reason = Column(Text)
    details = Column(JSONB)
    status = Column(String(20), server_default='pending')
    verify_date = Column(Date)
    current_price = Column(Float)
    pnl_pct = Column(Float)
    hit_stop_loss = Column(Boolean, server_default='false')
    hit_target_1 = Column(Boolean, server_default='false')
    hit_target_2 = Column(Boolean, server_default='false')
    hit_target_3 = Column(Boolean, server_default='false')
    max_pnl_pct = Column(Float)
    max_loss_pct = Column(Float)
    holding_days = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<SignalTestRecord(id={self.id}, symbol='{self.symbol}', action='{self.action}')>"
