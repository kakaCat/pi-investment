"""Nasdaq Data Link (formerly Quandl) data source.

Provides financial, economic, and alternative datasets including Fed data, commodities, and futures.
Free tier available with limited requests.
"""

import os
from typing import List, Optional, Dict
import requests

from ..base import MarketDataSource, DataSourceResponse


class NasdaqDataLinkSource(MarketDataSource):
    """Nasdaq Data Link (formerly Quandl) data source.

    Features:
    - Financial time series data
    - Economic indicators (FRED, World Bank, etc.)
    - Commodities and futures
    - Alternative datasets
    - Database and dataset search
    - Bulk downloads

    API Key: Required (free tier available)
    Rate Limits: Varies by plan
    """

    BASE_URL = "https://data.nasdaq.com/api/v3"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="Nasdaq Data Link", requires_api_key=True)
        self.api_key = api_key or os.environ.get('NASDAQ_DATA_LINK_API_KEY', '')
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=3
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def validate_config(self) -> bool:
        """Validate API key is configured."""
        return bool(self.api_key)

    def test_connection(self) -> DataSourceResponse:
        """Test connection by fetching a sample dataset."""
        try:
            if not self.validate_config():
                return DataSourceResponse.error_response(
                    "Nasdaq Data Link API key not configured. Set NASDAQ_DATA_LINK_API_KEY environment variable."
                )

            # Test with a simple dataset request (FRED GDP)
            result = self.get_dataset("FRED", "GDP")
            if result.success:
                return DataSourceResponse.success_response(
                    {"status": "connected"},
                    metadata={"message": "Nasdaq Data Link API connection successful"}
                )
            return result

        except Exception as e:
            return self._handle_error("test_connection", e)

    def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make API request with error handling."""
        if params is None:
            params = {}

        params['api_key'] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}" if not endpoint.startswith('http') else endpoint

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response.json()

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Get stock information (limited support - use dataset metadata instead).

        Args:
            symbol: Stock ticker symbol

        Returns:
            DataSourceResponse with dataset metadata
        """
        try:
            # Nasdaq Data Link doesn't have a direct stock info endpoint
            # Try to get metadata for common stock databases
            databases = ["WIKI", "EOD", "FSE"]

            for db in databases:
                try:
                    result = self.get_dataset_metadata(db, symbol.upper())
                    if result.success:
                        return result
                except:
                    continue

            return DataSourceResponse.error_response(
                f"No stock data found for {symbol}. Try using get_dataset() with specific database/dataset codes."
            )

        except Exception as e:
            return self._handle_error("get_stock_info", e)

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get OHLCV kline data (requires database code).

        Args:
            symbol: Stock ticker symbol
            period: Time period (not used - Nasdaq Data Link uses database-specific formats)
            start_date: Start date (YYYYMMDD format)
            end_date: End date (YYYYMMDD format)

        Returns:
            DataSourceResponse with OHLCV data
        """
        try:
            # Convert date format from YYYYMMDD to YYYY-MM-DD
            from datetime import datetime
            start = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")

            # Try common stock databases
            databases = ["WIKI", "EOD"]

            for db in databases:
                try:
                    result = self.get_dataset(db, symbol.upper(), start, end)
                    if result.success:
                        return result
                except:
                    continue

            return DataSourceResponse.error_response(
                f"No price data found for {symbol}. Specify database code using get_dataset()."
            )

        except Exception as e:
            return self._handle_error("get_klines", e)

    def get_realtime_quote(self, symbols: List[str]) -> DataSourceResponse:
        """Get real-time quotes (not supported - Nasdaq Data Link provides historical data).

        Args:
            symbols: List of stock ticker symbols

        Returns:
            DataSourceResponse indicating feature not available
        """
        return DataSourceResponse.error_response(
            "Real-time quotes are not supported by Nasdaq Data Link. Use get_dataset() for historical data."
        )

    def get_dataset(
        self,
        database_code: str,
        dataset_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get dataset time series data.

        Args:
            database_code: Database code (e.g., "FRED", "WIKI", "EOD")
            dataset_code: Dataset code (e.g., "GDP", "AAPL")
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)

        Returns:
            DataSourceResponse with time series data
        """
        try:
            params = {}
            if start_date:
                params['start_date'] = start_date
            if end_date:
                params['end_date'] = end_date

            data = self._make_request(
                f"datasets/{database_code}/{dataset_code}/data.json",
                params
            )

            if 'dataset_data' not in data:
                return DataSourceResponse.error_response(
                    f"No data found for {database_code}/{dataset_code}"
                )

            dataset_data = data['dataset_data']

            # Parse time series
            column_names = dataset_data.get('column_names', [])
            data_points = dataset_data.get('data', [])

            # Convert to list of dicts
            series = []
            for point in data_points:
                item = {}
                for i, col_name in enumerate(column_names):
                    item[col_name.lower().replace(' ', '_')] = point[i] if i < len(point) else None
                series.append(item)

            return DataSourceResponse.success_response(
                series,
                metadata={
                    'database': database_code,
                    'dataset': dataset_code,
                    'columns': column_names,
                    'count': len(series)
                }
            )

        except Exception as e:
            return self._handle_error("get_dataset", e)

    def get_dataset_metadata(
        self,
        database_code: str,
        dataset_code: str
    ) -> DataSourceResponse:
        """Get dataset metadata.

        Args:
            database_code: Database code
            dataset_code: Dataset code

        Returns:
            DataSourceResponse with metadata
        """
        try:
            data = self._make_request(
                f"datasets/{database_code}/{dataset_code}/metadata.json"
            )

            if 'dataset' not in data:
                return DataSourceResponse.error_response(
                    f"No metadata found for {database_code}/{dataset_code}"
                )

            dataset = data['dataset']

            metadata = {
                'id': dataset.get('id'),
                'dataset_code': dataset.get('dataset_code'),
                'database_code': dataset.get('database_code'),
                'name': dataset.get('name'),
                'description': dataset.get('description'),
                'refreshed_at': dataset.get('refreshed_at'),
                'newest_available_date': dataset.get('newest_available_date'),
                'oldest_available_date': dataset.get('oldest_available_date'),
                'column_names': dataset.get('column_names'),
                'frequency': dataset.get('frequency'),
                'type': dataset.get('type'),
                'premium': dataset.get('premium')
            }

            return DataSourceResponse.success_response(
                metadata,
                metadata={'database': database_code, 'dataset': dataset_code}
            )

        except Exception as e:
            return self._handle_error("get_dataset_metadata", e)

    def get_database_metadata(self, database_code: str) -> DataSourceResponse:
        """Get database metadata.

        Args:
            database_code: Database code (e.g., "FRED", "WIKI")

        Returns:
            DataSourceResponse with database metadata
        """
        try:
            data = self._make_request(f"databases/{database_code}.json")

            if 'database' not in data:
                return DataSourceResponse.error_response(
                    f"No metadata found for database: {database_code}"
                )

            database = data['database']

            metadata = {
                'id': database.get('id'),
                'name': database.get('name'),
                'database_code': database.get('database_code'),
                'description': database.get('description'),
                'datasets_count': database.get('datasets_count'),
                'downloads': database.get('downloads'),
                'premium': database.get('premium'),
                'image': database.get('image')
            }

            return DataSourceResponse.success_response(
                metadata,
                metadata={'database': database_code}
            )

        except Exception as e:
            return self._handle_error("get_database_metadata", e)

    def search_datasets(
        self,
        query: str,
        database_code: Optional[str] = None,
        per_page: int = 20,
        page: int = 1
    ) -> DataSourceResponse:
        """Search for datasets.

        Args:
            query: Search query
            database_code: Optional database code to filter by
            per_page: Results per page
            page: Page number

        Returns:
            DataSourceResponse with search results
        """
        try:
            params = {
                'query': query,
                'per_page': per_page,
                'page': page
            }

            if database_code:
                params['database_code'] = database_code

            data = self._make_request("datasets.json", params)

            if 'datasets' not in data:
                return DataSourceResponse.error_response(
                    f"No datasets found for query: {query}"
                )

            datasets = []
            for ds in data['datasets']:
                datasets.append({
                    'id': ds.get('id'),
                    'dataset_code': ds.get('dataset_code'),
                    'database_code': ds.get('database_code'),
                    'name': ds.get('name'),
                    'description': ds.get('description'),
                    'refreshed_at': ds.get('refreshed_at'),
                    'newest_available_date': ds.get('newest_available_date'),
                    'oldest_available_date': ds.get('oldest_available_date'),
                    'premium': ds.get('premium')
                })

            return DataSourceResponse.success_response(
                datasets,
                metadata={
                    'query': query,
                    'count': len(datasets),
                    'page': page,
                    'per_page': per_page
                }
            )

        except Exception as e:
            return self._handle_error("search_datasets", e)

    def get_datatable(
        self,
        datatable_code: str,
        filters: Optional[Dict] = None
    ) -> DataSourceResponse:
        """Get datatable data.

        Args:
            datatable_code: Datatable code (e.g., "WIKI/PRICES")
            filters: Optional filters as key-value pairs

        Returns:
            DataSourceResponse with datatable data
        """
        try:
            params = {}
            if filters:
                params.update(filters)

            data = self._make_request(f"datatables/{datatable_code}.json", params)

            if 'datatable' not in data:
                return DataSourceResponse.error_response(
                    f"No datatable found: {datatable_code}"
                )

            datatable = data['datatable']

            return DataSourceResponse.success_response(
                datatable.get('data', []),
                metadata={
                    'datatable': datatable_code,
                    'columns': datatable.get('columns', []),
                    'count': len(datatable.get('data', []))
                }
            )

        except Exception as e:
            return self._handle_error("get_datatable", e)

    def search_symbols(self, query: str) -> DataSourceResponse:
        """Search for symbols/datasets.

        Args:
            query: Search query

        Returns:
            DataSourceResponse with search results
        """
        return self.search_datasets(query)
