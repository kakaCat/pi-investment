"""Database kline provider - primary source with gap detection"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date

from adapters.outbound.datasources.providers.kline.base import KlineProvider, KlineData

logger = logging.getLogger(__name__)


class DatabaseKlineProvider(KlineProvider):
    """Kline provider using local database

    When DB has data but gaps exist in the requested range, returns None
    to allow network providers to backfill the missing dates.
    """

    def __init__(self, kline_repo):
        """Initialize with kline repository

        Args:
            kline_repo: KlineRepository instance from ds.kline
        """
        self.kline_repo = kline_repo
        self.last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "database"

    def get_klines(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str
    ) -> Optional[List[KlineData]]:
        """Get kline data from database with gap detection

        Returns None if data is incomplete to allow network backfill.
        """
        self.last_error = None
        try:
            if period not in ['daily', 'weekly', 'monthly']:
                self.last_error = f"数据库不支持周期: {period}（分钟线仅走网络源）"
                logger.warning(f"Database provider does not support period: {period}")
                return None

            klines_df = self.kline_repo.get_daily_klines(symbol, start_date, end_date)

            if klines_df.is_empty():
                self.last_error = (
                    f"数据库无 {symbol} 的K线缓存"
                    "（本地仅缓存个股池标的，指数/冷门标的无数据）"
                )
                logger.warning(f"No kline data in database for {symbol}")
                return None

            klines = klines_df.to_dicts()

            if self._has_gaps(klines, start_date, end_date):
                self.last_error = f"数据库有 {symbol} 数据但存在缺口，触发网络回填"
                logger.info(f"DB has gaps for {symbol} in {start_date}~{end_date}, falling back to network")
                return None

            result = []
            for i, k in enumerate(klines):
                trade_date = str(k.get('trade_date', ''))[:10]
                close = float(k.get('close', 0))
                open_p = float(k.get('open', 0))
                high = float(k.get('high', 0))
                low = float(k.get('low', 0))
                volume = int(k.get('volume', 0))

                if i > 0:
                    prev_close = float(klines[i-1].get('close', 0))
                    change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0
                else:
                    change_pct = 0.0

                result.append(KlineData(
                    symbol=symbol,
                    date=trade_date,
                    open=open_p,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    change_pct=change_pct,
                    source=self.name,
                    timestamp=datetime.now().isoformat()
                ))

            logger.info(f"Database provider returned {len(result)} klines for {symbol}")
            return result

        except Exception as e:
            self.last_error = f"数据库查询异常: {type(e).__name__}: {e}"
            logger.error(f"Database kline provider failed for {symbol}: {e}")
            return None

    def _has_gaps(self, klines: list, start_date: str, end_date: str) -> bool:
        """Check if there are gaps in the kline data

        Compares actual trading days in DB against expected trading days.
        Allows up to 10% missing before triggering backfill.
        """
        if not klines:
            return True

        db_dates = set()
        for k in klines:
            trade_date = str(k.get('trade_date', ''))[:10]
            if trade_date:
                db_dates.add(trade_date)

        try:
            start = parse_date(start_date).date()
            end = parse_date(end_date).date()
            total_days = (end - start).days + 1
            if total_days <= 0:
                return False
        except Exception:
            return False

        coverage = len(db_dates) / max(total_days, 1)
        return coverage < 0.9
