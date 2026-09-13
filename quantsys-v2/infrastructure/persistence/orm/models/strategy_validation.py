"""策略验证报告表（quant.strategy_validation_reports）。

建立背景（2026-09-14，REQ-24e15d）：这张表此前**没有 ORM 模型** —— 写入在
adapters/outbound/repositories/strategy_repository.py 的 save_validation_report()
（裸 INSERT ... RETURNING id），读取在
application/services/strategy_validation_service.py 的「当日幂等存在性 COUNT」
（session.execute(text(...))）。本轮把这条读路径收口到 ORM，模型即表结构的唯一事实源。

语义要点：
    · 一行 = 一次"某策略在某日"的批量验证结果快照（**追加写**，不更新旧行）；
    · validation_date 是 **timestamp without time zone**，语义是"报告所属的那一天"
      （服务层写入的是当天 00:00:00），因此"当日幂等"判定是
      validation_date >= 当天零点，而不是 = 某个精确时刻；
    · score/status 为 NOT NULL（写报告前必须先算出分数）；其余指标列可空；
    · strategy_id 对 quant.strategy_configs(id) 有外键，且 **ON DELETE CASCADE** ——
      策略被物理删除时其验证报告一并被删（与 pool_change_log 那种 ON DELETE SET NULL 的
      审计台账不同：本表是"策略的派生数据"，不追求活得比主表久）。
      2026-09-14 实测：写探针行时必须用 strategy_configs 里真实存在的 id，否则直接撞 FK。
"""
from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String

from ..base import Base

__all__ = ['StrategyValidationReport']


class StrategyValidationReport(Base):
    """策略验证报告（一次验证一行，追加写）

    对应数据库表：quant.strategy_validation_reports
    主键：id
    """
    __tablename__ = 'strategy_validation_reports'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, nullable=False, comment='策略 ID（quant.strategy_configs.id，无外键）')
    validation_date = Column(DateTime(timezone=False), nullable=False, comment='报告所属日（写入时为当天 00:00:00）')
    score = Column(Numeric, nullable=False, comment='综合评分')
    status = Column(String, nullable=False, comment='验证状态 valid/invalid')
    annual_return = Column(Numeric, nullable=True)
    sharpe_ratio = Column(Numeric, nullable=True)
    max_drawdown = Column(Numeric, nullable=True)
    win_rate = Column(Numeric, nullable=True)
    profit_factor = Column(Numeric, nullable=True)
    backtest_count = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)
    start_date = Column(Date, nullable=True, comment='回测窗口开始')
    end_date = Column(Date, nullable=True, comment='回测窗口结束')
    created_at = Column(DateTime(timezone=False), nullable=True)

    def __repr__(self):
        return (f"<StrategyValidationReport(strategy_id={self.strategy_id}, "
                f"validation_date='{self.validation_date}', status='{self.status}')>")
