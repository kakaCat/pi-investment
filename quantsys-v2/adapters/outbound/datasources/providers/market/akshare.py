"""Akshare market data provider."""
import logging
from typing import Optional
from datetime import datetime
from adapters.outbound.datasources.base import MarketProvider
from adapters.outbound.datasources.models import MarketData

logger = logging.getLogger(__name__)


class AkshareMarketProvider(MarketProvider):
    """Akshare market data provider"""

    @property
    def name(self) -> str:
        return 'akshare'

    def get_market_overview(self) -> Optional[MarketData]:
        """Get market overview (rise/fall counts, indices)

        Returns:
            MarketData or None if failed
        """
        try:
            import akshare as ak

            # Get market overview data
            df = ak.stock_zh_a_spot_em()

            if df is None or df.empty:
                logger.warning(f"{self.name}: No market overview data")
                return None

            # Calculate rise/fall counts
            rise_count = len(df[df['涨跌幅'] > 0])
            fall_count = len(df[df['涨跌幅'] < 0])
            unchanged_count = len(df[df['涨跌幅'] == 0])

            overview_data = {
                'rise': rise_count,
                'fall': fall_count,
                'unchanged': unchanged_count,
                'total': len(df)
            }

            return MarketData(
                data_type='overview',
                data=overview_data,
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_market_overview failed: {e}")
            return None

    def get_lhb_stock(self, symbol: str, date: str) -> Optional[MarketData]:
        """Get dragon-tiger list (龙虎榜) for a stock

        Args:
            symbol: Stock symbol
            date: Date (YYYY-MM-DD)

        Returns:
            MarketData or None if failed
        """
        try:
            import akshare as ak

            # Get LHB data for specific stock
            # Note: akshare API may vary, this is a placeholder implementation
            df = ak.stock_lhb_detail_em(symbol=symbol, start_date=date, end_date=date)

            if df is None or df.empty:
                logger.warning(f"{self.name}: No LHB data for {symbol} on {date}")
                return None

            lhb_data = df.to_dict('records')

            return MarketData(
                data_type='lhb',
                data={'symbol': symbol, 'date': date, 'records': lhb_data},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_lhb_stock failed: {e}")
            return None

    def get_lhb_daily(self, date: str) -> Optional[MarketData]:
        """Get daily dragon-tiger list

        Args:
            date: Date (YYYY-MM-DD)

        Returns:
            MarketData or None if failed
        """
        try:
            import akshare as ak

            # Get daily LHB data
            df = ak.stock_lhb_stock_statistic_em(start_date=date, end_date=date)

            if df is None or df.empty:
                logger.warning(f"{self.name}: No daily LHB data for {date}")
                return None

            lhb_data = df.to_dict('records')

            return MarketData(
                data_type='lhb_daily',
                data={'date': date, 'records': lhb_data, 'total': len(lhb_data)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_lhb_daily failed: {e}")
            return None
