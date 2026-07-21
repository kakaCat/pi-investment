"""US Fiscal Data (Treasury) data source.

Provides access to US government financial data from the Treasury Department.

API Documentation: https://fiscaldata.treasury.gov/api-documentation/
No API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class FiscalDataSource(EconomicDataSource):
    """US Treasury Fiscal Data source.

    Provides access to:
    - National debt
    - Federal spending
    - Revenue collections
    - Treasury securities
    - Interest rates
    - Exchange rates
    - Government account balances

    No API key required.
    """

    BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"

    # Popular datasets
    DATASETS = {
        "debt_to_penny": "v2/accounting/od/debt_to_penny",
        "mts": "v1/accounting/mts/mts_table_5",  # Monthly Treasury Statement
        "avg_interest_rates": "v2/accounting/od/avg_interest_rates",
        "treasury_securities": "v1/debt/tror/tror_securities",
        "exchange_rates": "v1/accounting/od/rates_of_exchange",
        "federal_revenue": "v1/accounting/mts/mts_table_4",
        "federal_spending": "v1/accounting/mts/mts_table_6",
        "operating_cash": "v1/accounting/dts/operating_cash_balance"
    }

    def __init__(self):
        """Initialize Fiscal Data source."""
        super().__init__(name="FiscalData", requires_api_key=False)
        self.session = SessionManager.get_session("fiscal_data")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Fiscal Data API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/v2/accounting/od/debt_to_penny",
                params={"page[size]": 1},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "FiscalData"},
                metadata={"source": "FiscalData", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Fiscal Data connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to Fiscal Data API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_datasets(self) -> DataSourceResponse:
        """Get list of available datasets.

        Returns:
            DataSourceResponse with dataset list
        """
        datasets = [
            {"key": key, "endpoint": endpoint}
            for key, endpoint in self.DATASETS.items()
        ]

        return DataSourceResponse.success_response(
            data=datasets,
            metadata={
                "source": "FiscalData",
                "count": len(datasets)
            }
        )

    def get_national_debt(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page_size: int = 100
    ) -> DataSourceResponse:
        """Get national debt data (debt to the penny).

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            page_size: Number of records per page

        Returns:
            DataSourceResponse with debt data
        """
        try:
            params = {"page[size]": page_size}

            filters = []
            if start_date:
                filters.append(f"record_date:gte:{start_date}")
            if end_date:
                filters.append(f"record_date:lte:{end_date}")

            if filters:
                params["filter"] = ",".join(filters)

            data = self._make_request(self.DATASETS["debt_to_penny"], params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FiscalData",
                    "dataset": "debt_to_penny",
                    "start_date": start_date,
                    "end_date": end_date,
                    "total_count": data.get("meta", {}).get("total-count", 0)
                }
            )
        except Exception as e:
            return handle_request_error(e, "FiscalData", "get_national_debt")

    def get_interest_rates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get average interest rates on US Treasury securities.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataSourceResponse with interest rate data
        """
        try:
            params = {"page[size]": 100}

            filters = []
            if start_date:
                filters.append(f"record_date:gte:{start_date}")
            if end_date:
                filters.append(f"record_date:lte:{end_date}")

            if filters:
                params["filter"] = ",".join(filters)

            data = self._make_request(self.DATASETS["avg_interest_rates"], params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FiscalData",
                    "dataset": "avg_interest_rates",
                    "start_date": start_date,
                    "end_date": end_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "FiscalData", "get_interest_rates")

    def get_exchange_rates(
        self,
        country: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get Treasury exchange rates.

        Args:
            country: Country name (optional)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataSourceResponse with exchange rate data
        """
        try:
            params = {"page[size]": 100}

            filters = []
            if country:
                filters.append(f"country:eq:{country}")
            if start_date:
                filters.append(f"record_date:gte:{start_date}")
            if end_date:
                filters.append(f"record_date:lte:{end_date}")

            if filters:
                params["filter"] = ",".join(filters)

            data = self._make_request(self.DATASETS["exchange_rates"], params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FiscalData",
                    "dataset": "exchange_rates",
                    "country": country,
                    "start_date": start_date,
                    "end_date": end_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "FiscalData", "get_exchange_rates")

    def get_federal_revenue(
        self,
        fiscal_year: Optional[int] = None
    ) -> DataSourceResponse:
        """Get federal revenue data.

        Args:
            fiscal_year: Fiscal year (optional)

        Returns:
            DataSourceResponse with revenue data
        """
        try:
            params = {"page[size]": 100}

            if fiscal_year:
                params["filter"] = f"record_fiscal_year:eq:{fiscal_year}"

            data = self._make_request(self.DATASETS["federal_revenue"], params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FiscalData",
                    "dataset": "federal_revenue",
                    "fiscal_year": fiscal_year
                }
            )
        except Exception as e:
            return handle_request_error(e, "FiscalData", "get_federal_revenue")

    def get_federal_spending(
        self,
        fiscal_year: Optional[int] = None
    ) -> DataSourceResponse:
        """Get federal spending data.

        Args:
            fiscal_year: Fiscal year (optional)

        Returns:
            DataSourceResponse with spending data
        """
        try:
            params = {"page[size]": 100}

            if fiscal_year:
                params["filter"] = f"record_fiscal_year:eq:{fiscal_year}"

            data = self._make_request(self.DATASETS["federal_spending"], params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FiscalData",
                    "dataset": "federal_spending",
                    "fiscal_year": fiscal_year
                }
            )
        except Exception as e:
            return handle_request_error(e, "FiscalData", "get_federal_spending")

    def get_operating_cash_balance(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get daily operating cash balance.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataSourceResponse with cash balance data
        """
        try:
            params = {"page[size]": 100}

            filters = []
            if start_date:
                filters.append(f"record_date:gte:{start_date}")
            if end_date:
                filters.append(f"record_date:lte:{end_date}")

            if filters:
                params["filter"] = ",".join(filters)

            data = self._make_request(self.DATASETS["operating_cash"], params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FiscalData",
                    "dataset": "operating_cash",
                    "start_date": start_date,
                    "end_date": end_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "FiscalData", "get_operating_cash_balance")

    def get_treasury_securities(
        self,
        security_type: Optional[str] = None
    ) -> DataSourceResponse:
        """Get Treasury securities data.

        Args:
            security_type: Security type (optional)

        Returns:
            DataSourceResponse with securities data
        """
        try:
            params = {"page[size]": 100}

            if security_type:
                params["filter"] = f"security_type_desc:eq:{security_type}"

            data = self._make_request(self.DATASETS["treasury_securities"], params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FiscalData",
                    "dataset": "treasury_securities",
                    "security_type": security_type
                }
            )
        except Exception as e:
            return handle_request_error(e, "FiscalData", "get_treasury_securities")
