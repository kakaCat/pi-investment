"""筹码分布 Repository — quant.chip_distribution_state / quant.chip_metrics"""
from datetime import date
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import Column, Date, DateTime, Float, LargeBinary, Text, text

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

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
            sql = """
                SELECT trade_date, low, high, close, volume, turnover_rate
                FROM quant.daily_klines
                WHERE symbol = :symbol
            """
            params: Dict[str, Any] = {"symbol": symbol}
            if after_date:
                sql += " AND trade_date > :after_date"
                params["after_date"] = after_date
            sql += " ORDER BY trade_date"
            rows = self.session.execute(text(sql), params).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_klines error: {e}")
            return []

    def get_latest_close(self, symbol: str) -> Optional[float]:
        try:
            row = self.session.execute(
                text("""
                    SELECT close FROM quant.daily_klines
                    WHERE symbol = :s ORDER BY trade_date DESC LIMIT 1
                """),
                {"s": symbol},
            ).first()
            return float(row[0]) if row and row[0] else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_latest_close error: {e}")
            return None

    def get_circulating_mv(self, symbol: str) -> Optional[float]:
        try:
            row = self.session.execute(
                text("SELECT circulating_mv FROM quant.stocks WHERE symbol = :s"),
                {"s": symbol},
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
                text("""
                    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY turnover_rate)
                    FROM quant.daily_klines
                    WHERE trade_date = :d AND turnover_rate IS NOT NULL AND turnover_rate > 0
                """),
                {"d": trade_date},
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
            self.session.execute(
                text("""
                    INSERT INTO quant.chip_distribution_state
                        (symbol, price_min, bin_width, counts, last_trade_date, updated_at)
                    VALUES (:s, :pmin, :bw, :counts, :d, NOW())
                    ON CONFLICT (symbol) DO UPDATE SET
                        price_min = EXCLUDED.price_min,
                        bin_width = EXCLUDED.bin_width,
                        counts = EXCLUDED.counts,
                        last_trade_date = EXCLUDED.last_trade_date,
                        updated_at = NOW()
                """),
                {"s": symbol, "pmin": dist.price_min, "bw": dist.bin_width,
                 "counts": dist.to_bytes(), "d": last_trade_date},
            )
            self.session.commit()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip upsert_state error: {e}")
            raise

    # ---------- 指标读写 ----------

    def upsert_metrics(self, symbol: str, trade_date, metrics: Dict[str, Any]) -> None:
        try:
            self.session.execute(
                text("""
                    INSERT INTO quant.chip_metrics
                        (symbol, trade_date, profit_ratio, avg_cost,
                         cost_90_low, cost_90_high, cost_70_low, cost_70_high,
                         peak_price, concentration)
                    VALUES (:s, :d, :pr, :ac, :c90l, :c90h, :c70l, :c70h, :pp, :conc)
                    ON CONFLICT (symbol, trade_date) DO UPDATE SET
                        profit_ratio = EXCLUDED.profit_ratio,
                        avg_cost = EXCLUDED.avg_cost,
                        cost_90_low = EXCLUDED.cost_90_low,
                        cost_90_high = EXCLUDED.cost_90_high,
                        cost_70_low = EXCLUDED.cost_70_low,
                        cost_70_high = EXCLUDED.cost_70_high,
                        peak_price = EXCLUDED.peak_price,
                        concentration = EXCLUDED.concentration
                """),
                {"s": symbol, "d": trade_date, "pr": metrics["profit_ratio"],
                 "ac": metrics["avg_cost"], "c90l": metrics["cost_90_low"],
                 "c90h": metrics["cost_90_high"], "c70l": metrics["cost_70_low"],
                 "c70h": metrics["cost_70_high"], "pp": metrics["peak_price"],
                 "conc": metrics["concentration"]},
            )
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
            rows = self.session.execute(
                text("""
                    WITH latest AS (
                        SELECT symbol, MAX(trade_date) AS max_date
                        FROM quant.daily_klines GROUP BY symbol
                    )
                    SELECT l.symbol, s.last_trade_date AS from_date
                    FROM latest l
                    LEFT JOIN quant.chip_distribution_state s ON s.symbol = l.symbol
                    WHERE s.symbol IS NULL OR s.last_trade_date < l.max_date
                """),
            ).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"chip get_symbols_with_pending error: {e}")
            return []
