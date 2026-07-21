"""Error handling utilities for data sources.

Provides unified error handling with retry logic and DataFrame conversion,
inspired by FinceptTerminal's safe_call pattern.
"""

import time
import pandas as pd
from typing import Any, Callable, Dict, Optional
import logging

from adapters.outbound.datasources.base import DataSourceResponse

logger = logging.getLogger(__name__)


def safe_call(
    func: Callable,
    *args,
    max_retries: int = 2,
    retry_delay: float = 1.0,
    **kwargs
) -> DataSourceResponse:
    """Safely call a function with error handling and retries.

    Inspired by FinceptTerminal's safe_call pattern. Automatically handles:
    - Retry logic with exponential backoff
    - DataFrame to dict conversion
    - NaN/Infinity handling
    - Standardized error responses

    Args:
        func: Function to call
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries (doubles each retry)
        **kwargs: Keyword arguments for func

    Returns:
        DataSourceResponse with success/error status and data

    Example:
        result = safe_call(ak.stock_zh_a_hist, symbol="000001", period="daily")
        if result.success:
            klines = result.data
    """
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)

            # Handle DataFrame results
            if isinstance(result, pd.DataFrame):
                return handle_dataframe(result)

            # Handle list/dict results
            elif isinstance(result, (list, dict)):
                count = len(result) if isinstance(result, list) else 1
                return DataSourceResponse.success_response(result)

            # Handle other types
            else:
                return DataSourceResponse.success_response(str(result))

        except Exception as e:
            if attempt < max_retries - 1:
                delay = retry_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
                continue

            # Final attempt failed
            error_msg = str(e)

            # Add context for common errors
            if "find_all" in error_msg or "NoneType" in error_msg:
                error_msg = f"Data source unavailable or temporarily down: {error_msg}"
            elif "timeout" in error_msg.lower():
                error_msg = f"Request timed out after {max_retries} attempts: {error_msg}"
            elif "connection" in error_msg.lower():
                error_msg = f"Connection failed after {max_retries} attempts: {error_msg}"

            return DataSourceResponse.error_response(error_msg)

    return DataSourceResponse.error_response("Data source unavailable after retries")


def handle_dataframe(df: pd.DataFrame) -> DataSourceResponse:
    """Convert a pandas DataFrame to a standardized response.

    Handles:
    - Empty DataFrames
    - Datetime column conversion
    - NaN/Infinity replacement
    - Dict conversion

    Args:
        df: pandas DataFrame to convert

    Returns:
        DataSourceResponse with converted data
    """
    if df is None or df.empty:
        return DataSourceResponse.success_response([])

    try:
        # Convert datetime columns to strings
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)

        # Replace NaN/Infinity with None for valid JSON
        df = df.replace([float("inf"), float("-inf")], None)
        df = df.where(pd.notna(df), None)

        # Convert to list of dicts
        data = df.to_dict(orient='records')

        return DataSourceResponse.success_response(data)

    except Exception as e:
        logger.error(f"Failed to convert DataFrame: {e}")
        return DataSourceResponse.error_response(f"DataFrame conversion failed: {e}")


def normalize_date(date_str: str) -> str:
    """Normalize date string to YYYYMMDD format.

    Args:
        date_str: Date string in various formats (YYYYMMDD, YYYY-MM-DD, etc.)

    Returns:
        Date string in YYYYMMDD format
    """
    # Remove common separators
    normalized = date_str.replace("-", "").replace("/", "").replace(".", "")
    # Take first 8 characters
    return normalized[:8]


def normalize_date_display(date_str: str) -> str:
    """Normalize date string to YYYY-MM-DD format for display.

    Args:
        date_str: Date string in various formats

    Returns:
        Date string in YYYY-MM-DD format
    """
    normalized = normalize_date(date_str)
    if len(normalized) == 8:
        return f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:8]}"
    return date_str


def safe_float(value: Any) -> Optional[float]:
    """Safely convert a value to float.

    Args:
        value: Value to convert

    Returns:
        Float value or None if conversion fails
    """
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value: Any) -> Optional[int]:
    """Safely convert a value to int.

    Args:
        value: Value to convert

    Returns:
        Int value or None if conversion fails
    """
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def validate_symbol(symbol: str) -> bool:
    """Validate a stock symbol format.

    Args:
        symbol: Stock symbol to validate

    Returns:
        True if valid, False otherwise
    """
    if not symbol or not isinstance(symbol, str):
        return False

    # Remove whitespace
    symbol = symbol.strip()

    # Check basic format (6 digits + optional .SZ/.SH/.HK suffix)
    if len(symbol) < 6:
        return False

    return True


def handle_request_error(error: Exception, source_name: str, method: str) -> DataSourceResponse:
    """Handle a request error and return a standardized error response.

    Args:
        error: The exception that was raised
        source_name: Name of the data source (e.g., "MarineTraffic")
        method: Name of the method that failed

    Returns:
        DataSourceResponse with error details
    """
    error_msg = str(error)

    if hasattr(error, 'response') and error.response is not None:
        status_code = error.response.status_code
        if status_code == 401:
            error_msg = f"Authentication failed - check API key"
        elif status_code == 403:
            error_msg = f"Access forbidden - insufficient permissions"
        elif status_code == 404:
            error_msg = f"Resource not found"
        elif status_code == 429:
            error_msg = f"Rate limit exceeded - try again later"
        elif status_code >= 500:
            error_msg = f"Server error ({status_code}) - try again later"
        else:
            error_msg = f"HTTP {status_code}: {str(error)}"

    logger.error(f"{source_name}.{method} failed: {error_msg}")
    return DataSourceResponse.error_response(error_msg)


def validate_date_range(start_date: str, end_date: str) -> bool:
    """Validate that start_date is before end_date.

    Args:
        start_date: Start date string (YYYYMMDD or YYYY-MM-DD)
        end_date: End date string (YYYYMMDD or YYYY-MM-DD)

    Returns:
        True if valid range, False otherwise
    """
    try:
        start = normalize_date(start_date)
        end = normalize_date(end_date)
        return start <= end
    except Exception:
        return False
