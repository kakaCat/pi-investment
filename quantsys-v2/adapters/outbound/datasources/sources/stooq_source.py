"""Stooq financial data source.

Provides access to historical stock, forex, commodity, and cryptocurrency data.

API Documentation: https://stooq.com/
No API key required for CSV downloads.
"""

from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
import pandas as pd
from io import StringIO

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class StooqSource(EconomicDataSource):
    """Stooq financial data source.

    Provides access to:
    - Stock prices (global markets)
    - Forex rates
    - Commodity prices
    - Cryptocurrency prices
    - Indices
    - Historical OHLCV data

    No API key required.
    """

    BASE_URL = "https://stooq.com/q/d/l/"

    # Supported intervals
    INTERVALS = {
        "daily": "d",
        "weekly": "w",
        "monthly": "m",
        "quarterly": "q",
        "yearly": "y"
    }

    def __init__(self):
        """Initialize Stooq data source."""
        super().__init__(name="Stooq", requires_api_key=False)
        self.session = SessionManager.get_session("stooq")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Stooq.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            # Test with SPY (S&P 500 ETF)
            response = self.session.get(
                f"{self.BASE_URL}",
                params={"s": "spy.us", "i": "d"},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Stooq"},
                metadata={"source": "Stooq", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Stooq connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(
        self,
        symbol: str,
        interval: str = "d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Make request to Stooq API.

        Args:
            symbol: Symbol (e.g., 'spy.us', 'eurusd', 'btcusd')
            interval: Data interval ('d', 'w', 'm', 'q', 'y')
            start_date: Start date (YYYYMMDD format)
            end_date: End date (YYYYMMDD format)

        Returns:
            DataFrame with OHLCV data

        Raises:
            Exception: If request fails
        """
        params = {
            "s": symbol.lower(),
            "i": interval
        }

        if start_date:
            params["d1"] = start_date
        if end_date:
            params["d2"] = end_date

        response = self.session.get(self.BASE_URL, params=params, timeout=30)
        response.raise_for_status()

        # Parse CSV response
        df = pd.read_csv(StringIO(response.text))
        return df

    def get_historical_data(
        self,
        symbol: str,
        interval: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_back: int = 365
    ) -> DataSourceResponse:
        """Get historical OHLCV data.

        Args:
            symbol: Symbol (e.g., 'SPY.US', 'EURUSD', 'BTCUSD')
            interval: Data interval ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            days_back: Days to look back if start_date not specified

        Returns:
            DataSourceResponse with historical data
        """
        try:
            # Convert interval
            interval_code = self.INTERVALS.get(interval, "d")

            # Convert dates to YYYYMMDD format
            if not start_date:
                start_dt = datetime.now() - timedelta(days=days_back)
                start_date = start_dt.strftime("%Y%m%d")
            else:
                start_date = start_date.replace("-", "")

            if end_date:
                end_date = end_date.replace("-", "")

            df = self._make_request(symbol, interval_code, start_date, end_date)

            # Convert DataFrame to dict
            data = df.to_dict(orient="records")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Stooq",
                    "symbol": symbol,
                    "interval": interval,
                    "count": len(data)
                }
            )
        except Exception as e:
            return handle_request_error(e, "Stooq", "get_historical_data")

    def get_stock_data(
        self,
        symbol: str,
        market: str = "US",
        days_back: int = 365
    ) -> DataSourceResponse:
        """Get stock historical data.

        Args:
            symbol: Stock symbol (e.g., 'SPY', 'AAPL')
            market: Market suffix ('US', 'UK', 'DE', 'JP', etc.)
            days_back: Days to look back

        Returns:
            DataSourceResponse with stock data
        """
        full_symbol = f"{symbol}.{market}"
        return self.get_historical_data(full_symbol, days_back=days_back)

    def get_forex_data(
        self,
        base: str,
        quote: str,
        days_back: int = 365
    ) -> DataSourceResponse:
        """Get forex historical data.

        Args:
            base: Base currency (e.g., 'EUR', 'GBP')
            quote: Quote currency (e.g., 'USD', 'JPY')
            days_back: Days to look back

        Returns:
            DataSourceResponse with forex data
        """
        symbol = f"{base}{quote}"
        return self.get_historical_data(symbol, days_back=days_back)

    def get_commodity_data(
        self,
        commodity: str,
        days_back: int = 365
    ) -> DataSourceResponse:
        """Get commodity historical data.

        Args:
            commodity: Commodity symbol (e.g., 'GC.F' for gold, 'CL.F' for crude oil)
            days_back: Days to look back

        Returns:
            DataSourceResponse with commodity data
        """
        return self.get_historical_data(commodity, days_back=days_back)

    def get_crypto_data(
        self,
        crypto: str,
        quote: str = "USD",
        days_back: int = 365
    ) -> DataSourceResponse:
        """Get cryptocurrency historical data.

        Args:
            crypto: Cryptocurrency symbol (e.g., 'BTC', 'ETH')
            quote: Quote currency (default: 'USD')
            days_back: Days to look back

        Returns:
            DataSourceResponse with crypto data
        """
        symbol = f"{crypto}{quote}"
        return self.get_historical_data(symbol, days_back=days_back)

    def get_index_data(
        self,
        index: str,
        days_back: int = 365
    ) -> DataSourceResponse:
        """Get index historical data.

        Args:
            index: Index symbol (e.g., '^SPX' for S&P 500, '^DJI' for Dow Jones)
            days_back: Days to look back

        Returns:
            DataSourceResponse with index data
        """
        return self.get_historical_data(index, days_back=days_back)
