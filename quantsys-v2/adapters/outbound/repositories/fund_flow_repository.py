"""
Fund Flow ORM Repository - 完全迁移版本

迁移状态：✅ 已完成ORM迁移

数据表：quant.stock_fund_flow（007_add_stock_fund_flow_table.sql）
单位约定：所有 *_net_inflow 金额字段均为【万元】（东财原始数据为元，采集时 /10000）
"""
from datetime import datetime
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, func
from infrastructure.persistence.orm.base import Base
from domain.ports import IFundFlowRepository
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class FundFlow(Base):
    __tablename__ = 'stock_fund_flow'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    trade_date = Column(Date, nullable=False)
    close_price = Column(Numeric(10, 2))
    change_pct = Column(Numeric(8, 4))

    main_net_inflow = Column(Numeric(18, 2))
    main_net_inflow_rate = Column(Numeric(8, 4))
    large_net_inflow = Column(Numeric(18, 2))   # 超大单
    large_net_inflow_rate = Column(Numeric(8, 4))
    big_net_inflow = Column(Numeric(18, 2))     # 大单
    big_net_inflow_rate = Column(Numeric(8, 4))
    medium_net_inflow = Column(Numeric(18, 2))
    medium_net_inflow_rate = Column(Numeric(8, 4))
    small_net_inflow = Column(Numeric(18, 2))
    small_net_inflow_rate = Column(Numeric(8, 4))

    source = Column(String(50))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class FundFlowORMRepository(BaseORMRepository[FundFlow], IFundFlowRepository):
    """ORM Repository for stock_fund_flow"""
    model = FundFlow

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            logger.error(f"Error listing: {e}")
            return []

    def get_fund_flow(self, symbol: str, start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            q = self.session.query(self.model)
            if symbol:
                q = q.filter(self.model.symbol == symbol)
            if start_date:
                q = q.filter(self.model.trade_date >= start_date)
            if end_date:
                q = q.filter(self.model.trade_date <= end_date)
            rows = q.order_by(self.model.trade_date.desc()).all()
            return [{c.name: getattr(r, c.name) for c in self.model.__table__.columns} for r in rows]
        except Exception as e:
            logger.error(f"Error in get_fund_flow: {e}")
            return []

    def get_latest_fund_flow(self, symbol: str, days: int = 5) -> List[Dict[str, Any]]:
        """获取个股最近 N 条资金流（按交易日倒序），供 FundFlowDataSource 缓存层使用"""
        try:
            rows = (self.session.query(self.model)
                    .filter(self.model.symbol == symbol)
                    .order_by(self.model.trade_date.desc())
                    .limit(days)
                    .all())
            return [{c.name: getattr(r, c.name) for c in self.model.__table__.columns} for r in rows]
        except Exception as e:
            logger.error(f"Error in get_latest_fund_flow: {e}")
            return []

    def batch_upsert(self, records: List[Dict[str, Any]]) -> int:
        """批量 upsert 资金流记录（按 symbol+trade_date 去重），返回写入条数"""
        if not records:
            return 0
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            now = datetime.now()
            rows = []
            for r in records:
                row = {k: r.get(k) for k in (
                    'symbol', 'trade_date', 'close_price', 'change_pct',
                    'main_net_inflow', 'main_net_inflow_rate',
                    'large_net_inflow', 'large_net_inflow_rate',
                    'big_net_inflow', 'big_net_inflow_rate',
                    'medium_net_inflow', 'medium_net_inflow_rate',
                    'small_net_inflow', 'small_net_inflow_rate',
                    'source',
                )}
                row['updated_at'] = now
                rows.append(row)

            stmt = pg_insert(self.model).values(rows)
            update_cols = {c.name: getattr(stmt.excluded, c.name)
                           for c in self.model.__table__.columns
                           if c.name not in ('id', 'symbol', 'trade_date', 'created_at')}
            stmt = stmt.on_conflict_do_update(
                index_elements=['symbol', 'trade_date'],
                set_=update_cols,
            )
            self.session.execute(stmt)
            self.session.commit()
            return len(rows)
        except Exception as e:
            logger.error(f"Error in batch_upsert: {e}")
            self.session.rollback()
            return 0

    def get_market_aggregate_flow(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """市场聚合资金流向（按交易日分组，全市场求和）

        Returns:
            [{trade_date, total_small_flow, total_medium_flow,
              total_large_flow, total_big_flow}]
            金额单位：万元
        """
        try:
            m = self.model
            rows = (self.session.query(
                        m.trade_date,
                        func.sum(m.main_net_inflow).label('total_main_flow'),
                        func.sum(m.small_net_inflow).label('total_small_flow'),
                        func.sum(m.medium_net_inflow).label('total_medium_flow'),
                        func.sum(m.large_net_inflow).label('total_large_flow'),
                        func.sum(m.big_net_inflow).label('total_big_flow'),
                    )
                    .filter(m.trade_date >= start_date, m.trade_date <= end_date)
                    .group_by(m.trade_date)
                    .order_by(m.trade_date)
                    .all())
            return [{
                'trade_date': r.trade_date,
                'total_main_flow': float(r.total_main_flow or 0),
                'total_small_flow': float(r.total_small_flow or 0),
                'total_medium_flow': float(r.total_medium_flow or 0),
                'total_large_flow': float(r.total_large_flow or 0),
                'total_big_flow': float(r.total_big_flow or 0),
            } for r in rows]
        except Exception as e:
            logger.error(f"Error in get_market_aggregate_flow: {e}")
            return []

    def get_industry_aggregate_flow(self, trade_date: str) -> List[Dict[str, Any]]:
        """按行业聚合主力净流入（join stocks 表取行业分类）

        Returns:
            [{industry, main_net_inflow}] 按净流入降序，单位：万元
        """
        try:
            from infrastructure.persistence.orm.models import Stock

            m = self.model
            rows = (self.session.query(
                        Stock.industry.label('industry'),
                        func.sum(m.main_net_inflow).label('main_net_inflow'),
                    )
                    .join(Stock, Stock.symbol == m.symbol)
                    .filter(m.trade_date == trade_date)
                    .filter(Stock.industry.isnot(None), Stock.industry != '')
                    .group_by(Stock.industry)
                    .order_by(func.sum(m.main_net_inflow).desc())
                    .all())
            return [{
                'industry': r.industry,
                'main_net_inflow': float(r.main_net_inflow or 0),
            } for r in rows]
        except Exception as e:
            logger.error(f"Error in get_industry_aggregate_flow: {e}")
            return []

    def get_latest_trade_date(self) -> Optional[str]:
        """表中最新交易日（无数据返回 None）"""
        try:
            latest = self.session.query(func.max(self.model.trade_date)).scalar()
            return latest.strftime('%Y-%m-%d') if latest else None
        except Exception as e:
            logger.error(f"Error in get_latest_trade_date: {e}")
            return None


__all__ = ['FundFlowORMRepository']
