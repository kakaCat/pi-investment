"""筹码分布 Repository — quant.chip_distribution_state / quant.chip_metrics

2026-09-14（w-32314d00，REQ-24e15d B4-c3-c）：本文件内 7 处 text() Core SQL
全部迁为 SQLAlchemy Core select()/insert()，指标口径不变（逐句对照旧 SQL 迁移，
并用真实库做新旧等价性比对）。
"""
from datetime import date
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import Column, Date, DateTime, Float, LargeBinary, Text, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base
from infrastructure.persistence.orm.models import DailyKline, Stock

logger = structlog.get_logger(__name__)


class ChipState(Base):
    __tablename__ = 'chip_distribution_state'
    __table_args__ = {'schema': 'quant'}

    symbol = Column(Text, primary_key=True)
    price_min = Column(Float, nullable=False)
    bin_width = Column(Float, nullable=False)
    counts = Column(LargeBinary, nullable=False)
    last_trade_date = Column(Date, nullable=False)
    updated_at = Column(DateTime)


class ChipMetrics(Base):
    __tablename__ = 'chip_metrics'
    __table_args__ = {'schema': 'quant'}

    symbol = Column(Text, primary_key=True)
    trade_date = Column(Date, primary_key=True)
    profit_ratio = Column(Float)
    avg_cost = Column(Float)
    cost_90_low = Column(Float)
    cost_90_high = Column(Float)
    cost_70_low = Column(Float)
    cost_70_high = Column(Float)
    peak_price = Column(Float)
    concentration = Column(Float)
    created_at = Column(DateTime)


class ChipRepository(BaseORMRepository[ChipState]):
    model = ChipState

    # ---------- K 线读取 ----------

    def get_klines(self, symbol: str, after_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """读日 K（时间升序）。after_date 为排他下界（增量更新用）。"""
        try:
            stmt = select(
                DailyKline.trade_date,
                DailyKline.low,
                DailyKline.high,
                DailyKline.close,
                DailyKline.volume,
                DailyKline.turnover_rate,
            ).where(DailyKline.symbol == symbol)
            if after_date:
                stmt = stmt.where(DailyKline.trade_date > after_date)
            stmt = stmt.order_by(DailyKline.trade_date)
            rows = self.session.execute(stmt).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_klines error: {e}")
            return []

    def get_latest_close(self, symbol: str) -> Optional[float]:
        try:
            row = self.session.execute(
                select(DailyKline.close)
                .where(DailyKline.symbol == symbol)
                .order_by(DailyKline.trade_date.desc())
                .limit(1)
            ).first()
            return float(row[0]) if row and row[0] else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_latest_close error: {e}")
            return None

    def get_circulating_mv(self, symbol: str) -> Optional[float]:
        try:
            row = self.session.execute(
                select(Stock.circulating_mv).where(Stock.symbol == symbol)
            ).first()
            return float(row[0]) if row and row[0] else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_circulating_mv error: {e}")
            return None

    def get_median_turnover(self, trade_date: date) -> Optional[float]:
        """当日全市场换手率中位数（最后一级回退用）"""
        try:
            row = self.session.execute(
                select(
                    func.percentile_cont(0.5).within_group(DailyKline.turnover_rate)
                ).where(
                    DailyKline.trade_date == trade_date,
                    DailyKline.turnover_rate.isnot(None),
                    DailyKline.turnover_rate > 0,
                )
            ).first()
            return float(row[0]) if row and row[0] else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_median_turnover error: {e}")
            return None

    # ---------- 状态读写 ----------

    def get_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            r = self.session.query(self.model).filter_by(symbol=symbol).first()
            if not r:
                return None
            return {
                "price_min": r.price_min,
                "bin_width": r.bin_width,
                "counts": bytes(r.counts),
                "last_trade_date": r.last_trade_date,
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_state error: {e}")
            return None

    def upsert_state(self, symbol: str, dist, last_trade_date) -> None:
        """dist 为 domain.chip_distribution.calculator.ChipDistribution"""
        try:
            stmt = pg_insert(ChipState).values(
                symbol=symbol,
                price_min=dist.price_min,
                bin_width=dist.bin_width,
                counts=dist.to_bytes(),
                last_trade_date=last_trade_date,
                updated_at=func.now(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['symbol'],
                set_={
                    'price_min': stmt.excluded.price_min,
                    'bin_width': stmt.excluded.bin_width,
                    'counts': stmt.excluded.counts,
                    'last_trade_date': stmt.excluded.last_trade_date,
                    'updated_at': func.now(),
                },
            )
            self.session.execute(stmt)
            self.session.commit()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip upsert_state error: {e}")
            raise

    # ---------- 指标读写 ----------

    def upsert_metrics(self, symbol: str, trade_date, metrics: Dict[str, Any]) -> None:
        try:
            stmt = pg_insert(ChipMetrics).values(
                symbol=symbol,
                trade_date=trade_date,
                profit_ratio=metrics["profit_ratio"],
                avg_cost=metrics["avg_cost"],
                cost_90_low=metrics["cost_90_low"],
                cost_90_high=metrics["cost_90_high"],
                cost_70_low=metrics["cost_70_low"],
                cost_70_high=metrics["cost_70_high"],
                peak_price=metrics["peak_price"],
                concentration=metrics["concentration"],
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['symbol', 'trade_date'],
                set_={
                    'profit_ratio': stmt.excluded.profit_ratio,
                    'avg_cost': stmt.excluded.avg_cost,
                    'cost_90_low': stmt.excluded.cost_90_low,
                    'cost_90_high': stmt.excluded.cost_90_high,
                    'cost_70_low': stmt.excluded.cost_70_low,
                    'cost_70_high': stmt.excluded.cost_70_high,
                    'peak_price': stmt.excluded.peak_price,
                    'concentration': stmt.excluded.concentration,
                },
            )
            self.session.execute(stmt)
            self.session.commit()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip upsert_metrics error: {e}")
            raise

    def get_metrics(self, symbol: str, trade_date: str) -> Optional[Dict[str, Any]]:
        try:
            r = self.session.query(ChipMetrics).filter_by(
                symbol=symbol, trade_date=trade_date).first()
            if not r:
                return None
            return {c.name: getattr(r, c.name) for c in ChipMetrics.__table__.columns}
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_metrics error: {e}")
            return None

    # ---------- 增量发现 ----------

    def get_symbols_with_pending_klines(self) -> List[Dict[str, Any]]:
        """有新 K 线未处理的股票：state 缺失或 last_trade_date 落后于最新 K 线。

        返回 [{symbol, from_date}]，from_date 为排他下界（None 表示全量）。
        """
        try:
            latest = (
                select(
                    DailyKline.symbol.label('symbol'),
                    func.max(DailyKline.trade_date).label('max_date'),
                )
                .group_by(DailyKline.symbol)
                .subquery('latest')
            )
            stmt = (
                select(latest.c.symbol, ChipState.last_trade_date.label('from_date'))
                .select_from(latest)
                .outerjoin(ChipState, ChipState.symbol == latest.c.symbol)
                .where(or_(
                    ChipState.symbol.is_(None),
                    ChipState.last_trade_date < latest.c.max_date,
                ))
            )
            rows = self.session.execute(stmt).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_symbols_with_pending error: {e}")
            return []
