"""CFTC Commitment of Traders (COT) data source.
Provides weekly futures and options positioning data by trader category. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class CFTCCommitmentOfTradersSource(EconomicDataSource):
    """CFTC Commitment of Traders report data source.
    Weekly breakdown of futures/options positions by trader type.
    Critical for: contrarian signals, trend exhaustion, crowding analysis."""

    BASE_URL = "https://www.cftc.gov/api"
    TRADER_CATEGORIES = ["commercial", "non_commercial", "non_reportable",
        "dealer_intermediary", "asset_manager", "leveraged_money", "other_reportable"]
    ASSET_CLASSES = {"currencies": "FX futures", "energies": "Crude oil, nat gas",
        "metals": "Gold, silver, copper", "agriculturals": "Corn, wheat, soybeans",
        "equities": "S&P 500, Nasdaq", "rates": "Treasury, Eurodollar"}

    def __init__(self):
        super().__init__(name="CFTC_CommitmentOfTraders", requires_api_key=False)
        self.session = SessionManager.get_session("cftc")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/v1/futures_markets", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected"}, metadata={"source": "CFTC"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_futures_markets(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/v1/futures_markets", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(), metadata={"source": "CFTC"})
        except Exception as e:
            return handle_request_error(e, "CFTC", "get_futures_markets")

    def get_cot_report(self, market_code: str, report_type: str = "legacy_futopt") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/v1/reports/{report_type}/market/{market_code}", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "CFTC_COT", "market_code": market_code})
        except Exception as e:
            return handle_request_error(e, "CFTC", "get_cot_report")

    def get_trader_categories(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.TRADER_CATEGORIES,
            metadata={"source": "CFTC", "count": len(self.TRADER_CATEGORIES)})

    def get_asset_classes(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"name": k, "description": v} for k, v in self.ASSET_CLASSES.items()],
            metadata={"source": "CFTC", "count": len(self.ASSET_CLASSES)})
