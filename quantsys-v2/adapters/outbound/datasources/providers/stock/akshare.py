"""Akshare stock data provider."""
import logging
from typing import Optional
from datetime import datetime
from adapters.outbound.datasources.base import StockProvider
from adapters.outbound.datasources.models import StockData

logger = logging.getLogger(__name__)


class AkshareStockProvider(StockProvider):
    """Akshare stock data provider"""

    @property
    def name(self) -> str:
        return 'akshare'

    def get_announcements(self, symbol: str) -> Optional[StockData]:
        """Get stock announcements

        Args:
            symbol: Stock symbol

        Returns:
            StockData or None if failed
        """
        try:
            import akshare as ak

            # Get announcements
            df = ak.stock_notice_report(symbol=symbol)

            if df is None or df.empty:
                logger.warning(f"{self.name}: No announcements for {symbol}")
                return None

            # Convert to StockData
            announcements = df.to_dict('records')
            return StockData(
                symbol=symbol,
                data_type='announcement',
                data=announcements,
                total=len(announcements),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_announcements failed: {e}")
            return None

    def get_news(self, symbol: str, num: int = 10) -> Optional[StockData]:
        """Get stock news

        Args:
            symbol: Stock symbol
            num: Number of news items to fetch

        Returns:
            StockData or None if failed
        """
        try:
            import akshare as ak

            # Get news
            df = ak.stock_news_em(symbol=symbol)

            if df is None or df.empty:
                logger.warning(f"{self.name}: No news for {symbol}")
                return None

            # Convert to StockData
            news_list = df.head(num).to_dict('records')
            return StockData(
                symbol=symbol,
                data_type='news',
                data=news_list,
                total=len(news_list),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_news failed: {e}")
            return None

    def get_trading_calendar(self, start_date: str, end_date: str) -> Optional[StockData]:
        """Get trading calendar (trading days)

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            StockData or None if failed
        """
        try:
            import akshare as ak

            # Get trading calendar
            df = ak.tool_trade_date_hist_sina()

            if df is None or df.empty:
                logger.warning(f"{self.name}: No trading calendar data")
                return None

            # Filter by date range
            df['trade_date'] = df['trade_date'].astype(str)
            mask = (df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)
            filtered_df = df[mask]

            # Convert to StockData
            calendar = filtered_df.to_dict('records')
            return StockData(
                symbol='',  # No specific symbol for trading calendar
                data_type='trading_calendar',
                data=calendar,
                total=len(calendar),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_trading_calendar failed: {e}")
            return None
