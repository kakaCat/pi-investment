"""DataFetchStage - Multi-source data acquisition."""

import logging
from typing import List, Tuple, Optional, Protocol, Dict, Any
from datetime import datetime
import pandas as pd

from domain.backtest.stages.data_pipeline import PipelineContext, PipelineResult

logger = logging.getLogger(__name__)


class DataSource(Protocol):
    """Protocol for data source implementations."""

    def fetch_klines(self, symbols: List[str], date_range: Tuple[str, str]) -> pd.DataFrame:
        """Fetch K-line data for given symbols and date range."""
        ...


class DataSourceRegistry:
    """Simple registry for data sources.

    This is a placeholder implementation that can be replaced with
    a more sophisticated registry in the future.
    """

    def __init__(self):
        self._sources: Dict[str, DataSource] = {}

    def register(self, name: str, source: DataSource) -> None:
        """Register a data source."""
        self._sources[name] = source

    def get(self, name: str) -> DataSource:
        """Get a data source by name."""
        if name not in self._sources:
            raise ValueError(f"Data source '{name}' not found in registry")
        return self._sources[name]


class DataFetchStage:
    """Fetch data from multiple sources.

    This stage fetches K-line data from multiple data sources (akshare, tushare, etc.)
    and handles errors gracefully. If one source fails, it continues with others.

    Attributes:
        sources: List of data source names to fetch from
        symbols: List of stock symbols to fetch
        date_range: Tuple of (start_date, end_date) in 'YYYY-MM-DD' format
        data_source_registry: Registry for looking up data sources
    """

    def __init__(
        self,
        sources: List[str],
        symbols: List[str],
        date_range: Tuple[str, str]
    ):
        """Initialize DataFetchStage.

        Args:
            sources: List of data source names (e.g., ['akshare', 'tushare'])
            symbols: List of stock symbols (e.g., ['600000.SH', '000001.SZ'])
            date_range: Tuple of (start_date, end_date) strings

        Raises:
            ValueError: If sources, symbols, or date_range are invalid
        """
        if not sources:
            raise ValueError("sources list cannot be empty")
        if not symbols:
            raise ValueError("symbols list cannot be empty")
        if not date_range or len(date_range) != 2:
            raise ValueError("date_range must be a tuple of (start_date, end_date)")

        self.sources = sources
        self.symbols = symbols
        self.date_range = date_range
        self.data_source_registry = DataSourceRegistry()

    def execute(self, context: PipelineContext) -> PipelineResult:
        """Execute the data fetch stage.

        Fetches data from all configured sources. If a source fails, logs the error
        and continues with other sources. The stage succeeds if at least one source
        returns data.

        Args:
            context: Pipeline context with configuration and metadata

        Returns:
            PipelineResult with:
                - success: True if at least one source succeeded
                - data: Dict mapping source name to DataFrame
                - errors: List of error dicts for failed sources
                - metadata: Dict with sources_fetched and total_records counts
        """
        results = {}
        errors = []

        for source_name in self.sources:
            try:
                # Get data source from registry
                source = self.data_source_registry.get(source_name)

                # Fetch K-line data
                df = source.fetch_klines(self.symbols, self.date_range)

                # Copy DataFrame before mutation to prevent side effects
                df = df.copy()

                # Add metadata columns
                df['source'] = source_name
                df['fetch_time'] = datetime.now()

                # Store result
                results[source_name] = df

                logger.info(f"Fetched {len(df)} records from {source_name}")

            except Exception as e:
                # Log error and continue with other sources
                error_info = {
                    'source': source_name,
                    'error': str(e),
                    'timestamp': datetime.now()
                }
                errors.append(error_info)
                logger.warning(f"Failed to fetch from {source_name}: {e}")

        # Calculate metadata
        total_records = sum(len(df) for df in results.values())
        metadata = {
            'sources_fetched': len(results),
            'total_records': total_records
        }

        # Stage succeeds if at least one source returned data
        success = len(results) > 0

        return PipelineResult(
            success=success,
            data=results,
            errors=errors,
            metadata=metadata
        )
