"""Australian Bureau of Statistics (ABS) data source.
Provides Australian economic, social, and demographic statistics. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class AustralianBureauStatisticsSource(EconomicDataSource):
    """Australian Bureau of Statistics data source.
    GDP, CPI, labour force, trade, retail, building approvals, wages, population."""

    BASE_URL = "https://api.data.abs.gov.au/data"
    KEY_DATASETS = {"CPI": "Consumer Price Index", "LF": "Labour Force",
        "GDP": "National Accounts", "ITG": "International Trade", "RT": "Retail Trade",
        "BA": "Building Approvals", "WPI": "Wage Price Index"}

    def __init__(self):
        super().__init__(name="AustralianBureauStatistics", requires_api_key=False)
        self.session = SessionManager.get_session("abs")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/CPI",
                params={"format": "jsondata", "limit": 1}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "ABS"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_dataset(self, dataset_id: str, params: Optional[Dict[str, Any]] = None) -> DataSourceResponse:
        try:
            p: Dict[str, Any] = {"format": "jsondata"}
            if params: p.update(params)
            r = self.session.get(f"{self.BASE_URL}/{dataset_id}", params=p, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "ABS", "dataset": dataset_id})
        except Exception as e:
            return handle_request_error(e, "ABS", "get_dataset")

    def get_cpi(self) -> DataSourceResponse:
        return self.get_dataset("CPI")

    def get_gdp(self) -> DataSourceResponse:
        return self.get_dataset("GDP")

    def get_datasets(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"code": c, "description": d} for c, d in self.KEY_DATASETS.items()],
            metadata={"source": "ABS", "count": len(self.KEY_DATASETS)})
