"""Database kline provider - primary source"""
import logging
from typing import List, Optional
from datetime import datetime

from adapters.outbound.datasources.providers.kline.base import KlineProvider, KlineData

logger = logging.getLogger(__name__)


class DatabaseKlineProvider(KlineProvider):
    """Kline provider using local database"""

    def __init__(self, kline_repo):
        """Initialize with kline repository

        Args:
            kline_repo: KlineRepository instance from ds.kline
        """
        self.kline_repo = kline_repo

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
        """Get kline data from database

        Args:
            symbol: Stock symbol
            period: Period (daily, weekly, monthly)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of KlineData if successful, None if failed
        """
        try:
            # Only support daily/weekly/monthly from database
            if period not in ['daily', 'weekly', 'monthly']:
                logger.warning(f"Database provider does not support period: {period}")
                return None

            # Query database
            klines_df = self.kline_repo.get_daily_klines(symbol, start_date, end_date)

            if klines_df.is_empty():
                logger.warning(f"No kline data in database for {symbol}")
                return None

            # Convert to KlineData list
            klines = klines_df.to_dicts()
            result = []

            for i, k in enumerate(klines):
                trade_date = str(k.get('trade_date', ''))[:10]
                close = float(k.get('close', 0))
                open_p = float(k.get('open', 0))
                high = float(k.get('high', 0))
                low = float(k.get('low', 0))
                volume = int(k.get('volume', 0))

                # Calculate change_pct
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
            logger.error(f"Database kline provider failed for {symbol}: {e}")
            return None
