"""Unit tests for data sources.

Tests the new data source architecture with mocked responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from adapters.outbound.datasources.base import DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import (
    safe_call,
    handle_dataframe,
    normalize_date,
    normalize_date_display,
    safe_float,
    validate_symbol
)
from adapters.outbound.datasources.config import DataSourceConfig


class TestDataSourceResponse:
    """Test DataSourceResponse class."""

    def test_success_response(self):
        """Test creating a success response."""
        data = [{"date": "2024-01-01", "value": 100}]
        response = DataSourceResponse.success_response(data)

        assert response.success is True
        assert response.data == data
        assert response.count == 1
        assert response.error is None

    def test_error_response(self):
        """Test creating an error response."""
        error_msg = "API key not configured"
        response = DataSourceResponse.error_response(error_msg)

        assert response.success is False
        assert response.data == []
        assert response.error == error_msg
        assert response.count == 0

    def test_to_dict(self):
        """Test converting response to dict."""
        response = DataSourceResponse.success_response(
            {"test": "data"},
            metadata={"source": "test"}
        )
        result = response.to_dict()

        assert result["success"] is True
        assert result["data"] == {"test": "data"}
        assert result["count"] == 1
        assert result["metadata"]["source"] == "test"


class TestSessionManager:
    """Test SessionManager class."""

    def test_get_session(self):
        """Test getting a session."""
        session = SessionManager.get_session("test")
        assert session is not None
        assert isinstance(session.adapters, dict)

    def test_session_reuse(self):
        """Test that sessions are reused."""
        session1 = SessionManager.get_session("test")
        session2 = SessionManager.get_session("test")
        assert session1 is session2

    def test_close_session(self):
        """Test closing a session."""
        SessionManager.get_session("test_close")
        SessionManager.close_session("test_close")
        stats = SessionManager.get_session_stats()
        assert "test_close" not in stats["session_names"]

    def test_close_all_sessions(self):
        """Test closing all sessions."""
        SessionManager.get_session("test1")
        SessionManager.get_session("test2")
        SessionManager.close_all_sessions()
        stats = SessionManager.get_session_stats()
        assert stats["active_sessions"] == 0


class TestErrorHandler:
    """Test error handling utilities."""

    def test_handle_dataframe_empty(self):
        """Test handling empty DataFrame."""
        df = pd.DataFrame()
        response = handle_dataframe(df)

        assert response.success is True
        assert response.data == []
        assert response.count == 0

    def test_handle_dataframe_with_data(self):
        """Test handling DataFrame with data."""
        df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02"],
            "value": [100, 200]
        })
        response = handle_dataframe(df)

        assert response.success is True
        assert len(response.data) == 2
        assert response.data[0]["date"] == "2024-01-01"
        assert response.data[0]["value"] == 100

    def test_handle_dataframe_with_nan(self):
        """Test handling DataFrame with NaN values."""
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "value": [float("nan")]
        })
        response = handle_dataframe(df)

        assert response.success is True
        assert response.data[0]["value"] is None

    def test_safe_call_success(self):
        """Test safe_call with successful function."""
        def mock_func():
            return pd.DataFrame({"value": [1, 2, 3]})

        response = safe_call(mock_func, max_retries=1)

        assert response.success is True
        assert len(response.data) == 3

    def test_safe_call_with_retry(self):
        """Test safe_call with retry logic."""
        call_count = 0

        def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")
            return [{"value": 1}]

        response = safe_call(mock_func, max_retries=2, retry_delay=0.1)

        assert response.success is True
        assert call_count == 2

    def test_safe_call_failure(self):
        """Test safe_call with permanent failure."""
        def mock_func():
            raise Exception("Permanent error")

        response = safe_call(mock_func, max_retries=2, retry_delay=0.1)

        assert response.success is False
        assert "Permanent error" in response.error

    def test_normalize_date(self):
        """Test date normalization."""
        assert normalize_date("2024-01-01") == "20240101"
        assert normalize_date("2024/01/01") == "20240101"
        assert normalize_date("20240101") == "20240101"

    def test_normalize_date_display(self):
        """Test date display normalization."""
        assert normalize_date_display("20240101") == "2024-01-01"
        assert normalize_date_display("2024-01-01") == "2024-01-01"

    def test_safe_float(self):
        """Test safe float conversion."""
        assert safe_float(123) == 123.0
        assert safe_float("123.45") == 123.45
        assert safe_float(None) is None
        assert safe_float("invalid") is None

    def test_validate_symbol(self):
        """Test symbol validation."""
        assert validate_symbol("000001.SZ") is True
        assert validate_symbol("600000.SH") is True
        assert validate_symbol("") is False
        assert validate_symbol(None) is False
        assert validate_symbol("123") is False


class TestDataSourceConfig:
    """Test DataSourceConfig class."""

    def test_get_api_key_not_required(self):
        """Test getting API key for source that doesn't require one."""
        key = DataSourceConfig.get_api_key("akshare")
        assert key is None

    def test_is_configured_no_key_required(self):
        """Test configuration check for source without API key."""
        assert DataSourceConfig.is_configured("akshare") is True
        assert DataSourceConfig.is_configured("world_bank") is True

    @patch.dict("os.environ", {"FRED_API_KEY": "test_key"})
    def test_get_api_key_configured(self):
        """Test getting configured API key."""
        key = DataSourceConfig.get_api_key("fred")
        assert key == "test_key"

    @patch.dict("os.environ", {}, clear=True)
    def test_get_api_key_not_configured(self):
        """Test getting API key when not configured."""
        key = DataSourceConfig.get_api_key("fred")
        assert key is None

    def test_get_all_configured_sources(self):
        """Test getting all source configurations."""
        sources = DataSourceConfig.get_all_configured_sources()
        assert isinstance(sources, dict)
        assert "akshare" in sources
        assert "fred" in sources


class TestAkShareSource:
    """Test AkShareSource class."""

    @pytest.fixture
    def akshare_source(self):
        """Create AkShareSource instance."""
        from adapters.outbound.datasources.sources.akshare_source import AkShareSource
        return AkShareSource()

    def test_validate_config(self, akshare_source):
        """Test configuration validation."""
        # This will fail if akshare is not installed, which is expected
        result = akshare_source.validate_config()
        assert isinstance(result, bool)

    @patch("data_sources.sources.akshare_source.ak")
    def test_get_stock_info_success(self, mock_ak, akshare_source):
        """Test getting stock info successfully."""
        akshare_source.adapter.get_stock_info = Mock(return_value={
            "symbol": "000001.SZ",
            "name": "平安银行",
            "market": "A"
        })

        response = akshare_source.get_stock_info("000001.SZ")

        assert response.success is True
        assert response.data["symbol"] == "000001.SZ"

    def test_get_stock_info_invalid_symbol(self, akshare_source):
        """Test getting stock info with invalid symbol."""
        response = akshare_source.get_stock_info("")

        assert response.success is False
        assert "Invalid symbol" in response.error


class TestFREDSource:
    """Test FREDSource class."""

    @pytest.fixture
    def fred_source(self):
        """Create FREDSource instance."""
        from adapters.outbound.datasources.sources.fred_source import FREDSource
        return FREDSource()

    @patch.dict("os.environ", {}, clear=True)
    def test_validate_config_no_key(self, fred_source):
        """Test validation without API key."""
        result = fred_source.validate_config()
        assert result is False

    @patch.dict("os.environ", {"FRED_API_KEY": "test_key"})
    def test_validate_config_with_key(self, fred_source):
        """Test validation with API key."""
        fred_source.api_key = "test_key"
        result = fred_source.validate_config()
        assert result is True

    @patch.dict("os.environ", {"FRED_API_KEY": "test_key"})
    @patch("data_sources.sources.fred_source.SessionManager.get_session")
    def test_get_series_success(self, mock_session, fred_source):
        """Test getting FRED series successfully."""
        fred_source.api_key = "test_key"

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "observations": [
                {"date": "2024-01-01", "value": "100.5"}
            ],
            "seriess": [{
                "title": "GDP",
                "units": "Billions of Dollars"
            }]
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        mock_session.return_value.get.return_value = mock_response

        response = fred_source.get_series("GDP")

        assert response.success is True
        # Note: Actual implementation makes two requests, so this is simplified


class TestWorldBankSource:
    """Test WorldBankSource class."""

    @pytest.fixture
    def wb_source(self):
        """Create WorldBankSource instance."""
        from adapters.outbound.datasources.sources.world_bank_source import WorldBankSource
        return WorldBankSource()

    def test_validate_config(self, wb_source):
        """Test configuration validation."""
        result = wb_source.validate_config()
        assert result is True

    def test_list_commodities(self, wb_source):
        """Test listing commodities."""
        response = wb_source.list_commodities()

        assert response.success is True
        assert len(response.data) > 0
        assert any(c["name"] == "gold" for c in response.data)

    def test_search_series(self, wb_source):
        """Test searching for series."""
        response = wb_source.search_series("oil")

        assert response.success is True
        assert len(response.data) > 0
        assert any("oil" in c["name"] for c in response.data)

    @patch("data_sources.sources.world_bank_source.SessionManager.get_session")
    def test_get_commodity_price_success(self, mock_session, wb_source):
        """Test getting commodity price successfully."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = [
            {},
            [{"date": "2024", "value": 80.5}]
        ]
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        mock_session.return_value.get.return_value = mock_response

        response = wb_source.get_commodity_price("gold", 2024, 2024)

        assert response.success is True
        assert response.data["commodity"] == "gold"

    def test_get_commodity_price_invalid(self, wb_source):
        """Test getting price for invalid commodity."""
        response = wb_source.get_commodity_price("invalid_commodity")

        assert response.success is False
        assert "Unknown commodity" in response.error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
