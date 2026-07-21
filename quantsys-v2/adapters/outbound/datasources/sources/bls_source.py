"""Bureau of Labor Statistics (BLS) US economic data source.

Provides access to US inflation, employment, and productivity data.
API key required (free registration at www.bls.gov).
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class BLSSource(EconomicDataSource):
    """Bureau of Labor Statistics (BLS) US economic data source.

    Provides Consumer Price Index (CPI, headline and core), Producer Price
    Index (PPI), Employment Situation (nonfarm payrolls, unemployment rate),
    JOLTS (job openings/labor turnover), Employment Cost Index (ECI), and
    productivity data. API key required (free from www.bls.gov).
    """

    BASE_URL = "https://api.bls.gov/publicAPI/v2"

    INDICATORS = {
        "cpi_u": "CPI-U All items (headline CPI)",
        "cpi_core": "CPI-U All items less food and energy (core CPI)",
        "ppi_final_demand": "PPI Final demand",
        "nonfarm_payrolls": "Nonfarm payroll employment",
        "unemployment_rate": "Civilian unemployment rate",
        "average_hourly_earnings": "Average hourly earnings",
        "labor_force_participation": "Labor force participation rate",
        "jolts_openings": "JOLTS Job openings",
        "eci_wages": "Employment Cost Index - wages and salaries",
        "productivity": "Nonfarm business labor productivity",
    }

    SERIES_IDS = {
        "cpi_u": "CUUR0000SA0",
        "cpi_core": "CUUR0000SA0L1E",
        "ppi_final_demand": "WPUFD49116",
        "nonfarm_payrolls": "CES0000000001",
        "unemployment_rate": "LNS14000000",
        "average_hourly_earnings": "CES0500000003",
        "jolts_openings": "JTS000000000000000JOL",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="BLS", requires_api_key=True)
        self.api_key = api_key or os.getenv("BLS_API_KEY", "")
        self.session = SessionManager.get_session("bls")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("BLS API key not configured. Register at https://www.bls.gov/developers/")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.post(
                f"{self.BASE_URL}/timeseries/data/",
                json={"seriesid": ["CUUR0000SA0"], "registrationkey": self.api_key, "startyear": "2023", "endyear": "2024"},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "BLS"},
                metadata={"source": "BLS", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"BLS connection test failed: {e}")
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
            series_id = self.SERIES_IDS.get(series_id, series_id)
            start_year = (start_date or "2015")[:4]
            end_year = (end_date or "2025")[:4]
            response = self.session.post(
                f"{self.BASE_URL}/timeseries/data/",
                json={
                    "seriesid": [series_id],
                    "registrationkey": self.api_key,
                    "startyear": start_year,
                    "endyear": end_year,
                },
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "BLS", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "BLS", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "BLS", "query": query},
        )

    def get_cpi(self) -> DataSourceResponse:
        """Get US Consumer Price Index (headline CPI)."""
        return self.get_series("cpi_u")

    def get_unemployment(self) -> DataSourceResponse:
        """Get US unemployment rate."""
        return self.get_series("unemployment_rate")

    def get_nonfarm_payrolls(self) -> DataSourceResponse:
        """Get US nonfarm payroll employment."""
        return self.get_series("nonfarm_payrolls")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "BLS", "count": len(items)},
        )
