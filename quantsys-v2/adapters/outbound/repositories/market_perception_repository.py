"""M1 市场感知 Repository（RFC 007）

三个表的 ORM Repository：
- MarketRegimeRepository: regime 落库与查询
- MarketSentimentDailyRepository: 情绪落库与查询
- MarketThemeRepository: 主线落库/查询/LLM回写

upsert 统一走 pg_insert().on_conflict_do_update()（项目惯用模式，
参照 fund_flow_repository.py / financial_repository.py）。
"""
from datetime import date
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.persistence.orm.base_repository import BaseORMRepository
from infrastructure.persistence.orm.models import (
    MarketRegime, MarketSentimentDaily, MarketTheme,
)

logger = structlog.get_logger(__name__)

__all__ = [
    'MarketRegimeRepository',
    'MarketSentimentDailyRepository',
    'MarketThemeRepository',
]


class MarketRegimeRepository(BaseORMRepository[MarketRegime]):
    """market_regime 表 Repository"""

    model = MarketRegime

    def upsert(self, trade_date: date, regime: str, reason: str,
               index_trend_score: Optional[float] = None,
               sentiment_score: Optional[float] = None,
               volume_ratio: Optional[float] = None,
               ad_ratio: Optional[float] = None,
               commit: bool = True) -> bool:
        """按交易日 upsert regime 记录。"""
        stmt = pg_insert(MarketRegime).values([{
            'trade_date': trade_date, 'regime': regime, 'reason': reason,
            'index_trend_score': index_trend_score,
            'sentiment_score': sentiment_score,
            'volume_ratio': volume_ratio, 'ad_ratio': ad_ratio,
        }])
        stmt = stmt.on_conflict_do_update(
            index_elements=['trade_date'],
            set_={
                'regime': stmt.excluded.regime,
                'reason': stmt.excluded.reason,
                'index_trend_score': stmt.excluded.index_trend_score,
                'sentiment_score': stmt.excluded.sentiment_score,
                'volume_ratio': stmt.excluded.volume_ratio,
                'ad_ratio': stmt.excluded.ad_ratio,
            },
        )
        try:
            self.session.execute(stmt)
            if commit:
                self.commit()
            return True
        except Exception as e:
            self._safe_rollback()
            logger.error(f"regime upsert 失败 {trade_date}: {e}", exc_info=True)
            return False

    def upsert_batch(self, rows: List[Dict[str, Any]], commit: bool = True) -> int:
        """批量 upsert（回填用，避免 N+1）。

        rows: [{trade_date, regime, reason, index_trend_score, ...}]
        返回成功条数。
        """
        if not rows:
            return 0
        stmt = pg_insert(MarketRegime).values(rows)
        # 回填只填空缺，不覆盖已有记录（无论真实快照还是旧回填值）
        stmt = stmt.on_conflict_do_nothing(index_elements=['trade_date'])
        try:
            self.session.execute(stmt)
            if commit:
                self.commit()
            return len(rows)
        except Exception as e:
            self._safe_rollback()
            logger.error(f"regime 批量 upsert 失败: {e}", exc_info=True)
            return 0

    def get_recent(self, days: int = 20) -> List[MarketRegime]:
        """最近 N 天 regime（按日期倒序）。"""
        return (self.session.query(MarketRegime)
                .order_by(MarketRegime.trade_date.desc())
                .limit(days).all())

    def get_by_date(self, trade_date: date) -> Optional[MarketRegime]:
        return (self.session.query(MarketRegime)
                .filter_by(trade_date=trade_date).first())


class MarketSentimentDailyRepository(BaseORMRepository[MarketSentimentDaily]):
    """market_sentiment_daily 表 Repository"""

    model = MarketSentimentDaily

    def upsert(self, trade_date: date, commit: bool = True, **fields) -> bool:
        """按交易日 upsert 情绪记录。

        fields: up_count/down_count/flat_count/ad_ratio/new_high_count/
                new_low_count/volume_ratio/total_turnover/volatility/
                fear_greed_index/coverage/partial
        """
        values = {'trade_date': trade_date, **fields}
        stmt = pg_insert(MarketSentimentDaily).values([values])
        stmt = stmt.on_conflict_do_update(
            index_elements=['trade_date'],
            set_={k: getattr(stmt.excluded, k) for k in fields},
        )
        try:
            self.session.execute(stmt)
            if commit:
                self.commit()
            return True
        except Exception as e:
            self._safe_rollback()
            logger.error(f"sentiment upsert 失败 {trade_date}: {e}", exc_info=True)
            return False

    def get_by_date(self, trade_date: date) -> Optional[MarketSentimentDaily]:
        return (self.session.query(MarketSentimentDaily)
                .filter_by(trade_date=trade_date).first())

    def get_recent(self, days: int = 20) -> List[MarketSentimentDaily]:
        """最近 N 天情绪（按日期倒序）。"""
        return (self.session.query(MarketSentimentDaily)
                .order_by(MarketSentimentDaily.trade_date.desc())
                .limit(days).all())


class MarketThemeRepository(BaseORMRepository[MarketTheme]):
    """market_theme 表 Repository"""

    model = MarketTheme

    def delete_without_catalyst(self, trade_date: date, commit: bool = False) -> int:
        """幂等重跑：删除当日无 catalyst 的记录（保留 LLM 已回写的）。"""
        try:
            result = self.session.execute(
                delete(MarketTheme).where(
                    MarketTheme.trade_date == trade_date,
                    MarketTheme.catalyst.is_(None),
                )
            )
            if commit:
                self.commit()
            return result.rowcount or 0
        except Exception as e:
            self._safe_rollback()
            logger.error(f"theme 清理失败 {trade_date}: {e}", exc_info=True)
            return 0

    def upsert(self, trade_date: date, rank: int, theme: str, sector: str,
               limit_up_count: int, stocks: list,
               fund_flow: Optional[float] = None,
               confidence: Optional[float] = None,
               commit: bool = True) -> Optional[int]:
        """按 (trade_date, rank) upsert 主线记录，返回记录 id。

        注意：catalyst 不在 upsert 字段中——已回写的 catalyst 不被覆盖。
        """
        stmt = pg_insert(MarketTheme).values([{
            'trade_date': trade_date, 'rank': rank, 'theme': theme,
            'sector': sector, 'limit_up_count': limit_up_count,
            'stocks': stocks, 'fund_flow': fund_flow, 'confidence': confidence,
        }])
        stmt = stmt.on_conflict_do_update(
            index_elements=['trade_date', 'rank'],
            set_={
                'theme': stmt.excluded.theme,
                'sector': stmt.excluded.sector,
                'limit_up_count': stmt.excluded.limit_up_count,
                'stocks': stmt.excluded.stocks,
                'fund_flow': stmt.excluded.fund_flow,
                'confidence': stmt.excluded.confidence,
            },
        ).returning(MarketTheme.id)
        try:
            row_id = self.session.execute(stmt).scalar()
            if commit:
                self.commit()
            return row_id
        except Exception as e:
            self._safe_rollback()
            logger.error(f"theme upsert 失败 {trade_date}#{rank}: {e}", exc_info=True)
            return None

    def get_by_date(self, trade_date: date) -> List[MarketTheme]:
        """指定日期的主线（按 rank 升序）。"""
        return (self.session.query(MarketTheme)
                .filter_by(trade_date=trade_date)
                .order_by(MarketTheme.rank).all())

    def get_latest(self) -> List[MarketTheme]:
        """最新交易日的主线（按 rank 升序）。"""
        latest = (self.session.query(MarketTheme.trade_date)
                  .order_by(MarketTheme.trade_date.desc()).first())
        if not latest:
            return []
        return self.get_by_date(latest[0])

    def update_catalyst(self, theme_id: int, commit: bool = True,
                        **fields) -> Optional[MarketTheme]:
        """LLM 回写：只允许 theme/catalyst/confidence 三字段。"""
        allowed = {k: v for k, v in fields.items()
                   if k in ('theme', 'catalyst', 'confidence') and v is not None}
        if not allowed:
            return None
        obj = self.get_by_id(theme_id)
        if not obj:
            return None
        try:
            for k, v in allowed.items():
                setattr(obj, k, v)
            if commit:
                self.commit()
            return obj
        except Exception as e:
            self._safe_rollback()
            logger.error(f"theme 回写失败 id={theme_id}: {e}", exc_info=True)
            return None
