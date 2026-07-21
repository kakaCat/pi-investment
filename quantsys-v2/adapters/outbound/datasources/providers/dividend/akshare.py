"""Akshare dividend data provider."""
import logging
from typing import Optional, List
from datetime import datetime
from adapters.outbound.datasources.base import DividendProvider
from adapters.outbound.datasources.models import DividendData

logger = logging.getLogger(__name__)


class AkshareDividendProvider(DividendProvider):
    """Akshare dividend data provider"""

    @property
    def name(self) -> str:
        return 'akshare'

    def get_dividends(self, symbol: str, years: int = 5) -> Optional[List[DividendData]]:
        """Get dividend history

        Args:
            symbol: Stock symbol
            years: Number of years to fetch

        Returns:
            List of DividendData or None if failed
        """
        try:
            import akshare as ak

            # Extract code without suffix (e.g., 600519.SH -> 600519)
            code = symbol.split('.')[0]
            df = ak.stock_dividend_cninfo(symbol=code)

            if df is None or df.empty:
                logger.warning(f"{self.name}: No dividend data for {symbol}")
                return None

            # Convert to DividendData list
            result = []
            for _, row in df.head(years * 2).iterrows():  # *2 to get more records
                result.append(DividendData(
                    symbol=symbol,
                    dividend_per_share=float(row.get('每股派息', 0)),
                    dividend_yield=float(row.get('股息率', 0)) if '股息率' in row else None,
                    ex_dividend_date=str(row.get('除权除息日', '')) if '除权除息日' in row else None,
                    source=self.name,
                    timestamp=datetime.now().isoformat()
                ))

            return result if result else None

        except Exception as e:
            logger.warning(f"{self.name} get_dividends failed: {e}")
            return None

    def get_dividend_calendar(self, start_date: str, end_date: str) -> Optional[List[DividendData]]:
        """Get dividend calendar within date range

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of DividendData or None if failed
        """
        # TODO: Extract logic from services/dividend_service.py when refactoring Phase 3
        logger.warning(f"{self.name} get_dividend_calendar not yet implemented")
        return None

    def screen_high_dividend(self, min_yield: float = 3.0, min_years: int = 5) -> Optional[List[DividendData]]:
        """Screen high dividend stocks

        Args:
            min_yield: Minimum dividend yield (%)
            min_years: Minimum consecutive dividend years

        Returns:
            List of DividendData or None if failed
        """
        # TODO: Extract logic from services/dividend_service.py when refactoring Phase 3
        logger.warning(f"{self.name} screen_high_dividend not yet implemented")
        return None
