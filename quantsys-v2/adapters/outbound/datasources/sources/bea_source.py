"""Bureau of Economic Analysis (BEA) US economic data source.

Provides access to US national accounts, GDP by industry, personal income,
and international trade data. API key required (free registration).
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class BEASource(EconomicDataSource):
    """Bureau of Economic Analysis (BEA) US economic data source.

    Provides GDP (current/chained dollars), personal income and outlays,
    international transactions (trade balance, current account), fixed assets,
    and GDP by industry. API key required (free from www.bea.gov).
    """

    BASE_URL = "https://apps.bea.gov/api/data"

    DATASETS = {
        "NIPA": "National Income and Product Accounts (GDP, personal income)",
        "NIUnderlyingDetail": "NIPA underlying detail tables",
        "FixedAssets": "Fixed assets and consumer durable goods",
        "ITA": "International transactions accounts",
        "IIP": "International investment position",
        "InputOutput": "Input-output accounts",
        "GDPbyIndustry": "GDP by industry",
        "Regional": "Regional economic accounts (GDP by state/county)",
    }

    INDICATORS = {
        "gdp": "Gross Domestic Product (GDP)",
        "real_gdp": "Real GDP (chained 2017 dollars)",
        "personal_income": "Personal income",
        "disposable_income": "Disposable personal income",
        "personal_consumption": "Personal consumption expenditures (PCE)",
        "corporate_profits": "Corporate profits",
        "trade_balance": "International trade balance",
        "current_account": "Current account balance",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="BEA", requires_api_key=True)
        self.api_key = api_key or os.getenv("BEA_API_KEY", "")
        self.session = SessionManager.get_session("bea")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("BEA API key not configured. Register at https://apps.bea.gov")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/GDP",
                params={"UserID": self.api_key, "Method": "GETPARAMETERLIST"},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "BEA"},
                metadata={"source": "BEA", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"BEA connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DataSourceResponse:
        try:
            params: Dict[str, Any] = {
                "UserID": self.api_key,
                "Method": "GetData",
                "datasetname": "NIPA",
                "TableName": series_id,
                "Frequency": "Q",
                "Year": "ALL",
                "ResultFormat": "JSON",
            }
            response = self.session.get(
                self.BASE_URL, params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "BEA", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "BEA", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "BEA", "query": query},
        )

    def get_gdp(self) -> DataSourceResponse:
        """Get US GDP data from BEA."""
        return self.get_series("T10101")

    def get_personal_income(self) -> DataSourceResponse:
        """Get US personal income and outlays."""
        return self.get_series("T20600")

    def get_datasets(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.DATASETS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "BEA", "count": len(items)},
        )

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "BEA", "count": len(items)},
        )
