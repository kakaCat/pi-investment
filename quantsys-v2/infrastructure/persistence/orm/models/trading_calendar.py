"""交易日历表（quant.trading_calendar）。

建立背景（2026-09-14，w-32314d00，REQ-24e15d）：
    该表此前**没有 ORM 模型**，全仓唯一读入口是
    `application/services/data_pipeline_service.py` 的模块级函数
    `load_trading_calendar_from_db`（db_cursor + 裸 SQL），它是 8 段数据管道的
    TimeAlignmentStage 的 calendar_loader。收口后：表名/列名由模型唯一确定，
    （写错列名在导入期即 UndefinedColumn，而不是运行时静默抛错），
    服务层只剩"取日历 → 空则回退 K 线 → 打日志"的编排。

语义要点：
    · 主键是 **(trade_date, exchange) 复合主键**（见 pg_constraint：
      trading_calendar_pkey PRIMARY KEY (trade_date, exchange)）——
      同一交易日在 SSE / SZSE / ALL 三个 exchange 下各有一行，
      所以按 exchange 过滤是必须的，否则日历会三倍重复；
    · is_trading_day 可为 NULL，且查询口径是 `is_trading_day = TRUE`
      （NULL 不入选）；`.is_(True)` 与 `= TRUE` 在此完全等价（两者都排除 NULL）；
    · trade_date 是 date（无时区），回传给 TimeAlignmentStage 的集合元素类型
      与旧实现（psycopg2 → datetime.date）一致。
"""
from sqlalchemy import Boolean, Column, Date, String

from ..base import Base

__all__ = ['TradingCalendar']


class TradingCalendar(Base):
    """交易所交易日历

    对应数据库表：quant.trading_calendar
    主键：(trade_date, exchange)
    """
    __tablename__ = 'trading_calendar'
    __table_args__ = {'schema': 'quant'}

    trade_date = Column(Date, primary_key=True, nullable=False, comment='交易日')
    exchange = Column(String(10), primary_key=True, nullable=False, comment='交易所代码（SSE/SZSE/ALL）')
    is_trading_day = Column(Boolean, nullable=True, comment='是否交易日（NULL 表示未知）')

    def __repr__(self):
        return f"<TradingCalendar(date='{self.trade_date}', exchange='{self.exchange}', trading={self.is_trading_day})>"
