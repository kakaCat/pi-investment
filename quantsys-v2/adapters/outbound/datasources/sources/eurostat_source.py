"""Eurostat EU statistical data source.
Provides EU-wide economic, social, and regional statistics. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class EurostatSource(EconomicDataSource):
    """Eurostat EU statistical data source.
    GDP, HICP inflation, unemployment, trade, government finance, industrial production."""

    BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"
    KEY_DATASETS = {"nama_10_gdp": "GDP components", "prc_hicp_manr": "HICP inflation",
        "une_rt_m": "Unemployment rate", "ext_st_eu27": "Extra-EU trade",
        "gov_10dd_edpt1": "Gov deficit/debt", "sts_inpr_m": "Industrial production"}

    def __init__(self):
        super().__init__(name="Eurostat", requires_api_key=False)
        self.session = SessionManager.get_session("eurostat")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/data/nama_10_gdp",
                params={"format": "JSON", "limit": 1}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "Eurostat"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_dataset(self, dataset_code: str, params: Optional[Dict[str, Any]] = None) -> DataSourceResponse:
        try:
            p: Dict[str, Any] = {"format": "JSON"}
            if params:
                p.update(params)
            r = self.session.get(f"{self.BASE_URL}/data/{dataset_code}", params=p, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "Eurostat", "dataset": dataset_code})
        except Exception as e:
            return handle_request_error(e, "Eurostat", "get_dataset")

    def get_gdp(self, country: str = "EU27_2020") -> DataSourceResponse:
        return self.get_dataset("nama_10_gdp", {"geo": country})

    def get_inflation(self, country: str = "EA20") -> DataSourceResponse:
        return self.get_dataset("prc_hicp_manr", {"geo": country})

    def get_key_datasets(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"code": c, "description": d} for c, d in self.KEY_DATASETS.items()],
            metadata={"source": "Eurostat", "count": len(self.KEY_DATASETS)})
