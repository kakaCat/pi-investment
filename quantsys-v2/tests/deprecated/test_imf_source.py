"""Tests for IMF data source."""

import pytest
from adapters.outbound.datasources.sources.imf_source import IMFSource


class TestIMFSource:
    """Test suite for IMF data source."""

    @pytest.fixture
    def imf_source(self):
        """Create IMF source instance."""
        return IMFSource()

    def test_initialization(self, imf_source):
        """Test IMF source initialization."""
        assert imf_source.name == "IMF"
        assert imf_source.requires_api_key is False
        assert imf_source.BASE_URL == "http://dataservices.imf.org/REST/SDMX_JSON.svc/"

    def test_validate_config(self, imf_source):
        """Test configuration validation (no API key needed)."""
        assert imf_source.validate_config() is True

    def test_connection(self, imf_source):
        """Test IMF API connection."""
        result = imf_source.test_connection()
        assert result.success is True
        assert result.metadata["source"] == "imf"

    def test_normalize_country(self, imf_source):
        """Test country name normalization."""
        assert imf_source._normalize_country("United States") == "US"
        assert imf_source._normalize_country("usa") == "US"
        assert imf_source._normalize_country("US") == "US"
        assert imf_source._normalize_country("China") == "CN"
        assert imf_source._normalize_country("Japan") == "JP"

    def test_normalize_country_list(self, imf_source):
        """Test country list normalization."""
        result = imf_source._normalize_country_list("US,CN,JP")
        assert result == "US+CN+JP"

        result = imf_source._normalize_country_list("United States, China")
        assert result == "US+CN"

    def test_get_economic_indicators_default(self, imf_source):
        """Test getting economic indicators with default parameters."""
        result = imf_source.get_economic_indicators(
            countries="US",
            symbols="top_lines",
            frequency="quarter"
        )

        assert result.success is True
        assert result.count > 0
        assert result.metadata["countries"] == "US"
        assert result.metadata["frequency"] == "quarter"

    def test_get_economic_indicators_multiple_countries(self, imf_source):
        """Test getting economic indicators for multiple countries."""
        result = imf_source.get_economic_indicators(
            countries="US,CN,JP",
            symbols="reserve_assets",
            frequency="annual"
        )

        assert result.success is True
        assert result.metadata["countries"] == "US,CN,JP"

    def test_get_economic_indicators_with_dates(self, imf_source):
        """Test getting economic indicators with date range."""
        result = imf_source.get_economic_indicators(
            countries="US",
            symbols="gold_reserves",
            frequency="quarter",
            start_date="2020-01-01",
            end_date="2023-12-31"
        )

        assert result.success is True
        assert result.count > 0

    def test_get_direction_of_trade(self, imf_source):
        """Test getting direction of trade statistics."""
        result = imf_source.get_direction_of_trade(
            countries="US",
            counterparts="CN",
            direction="exports",
            frequency="quarter"
        )

        assert result.success is True
        assert result.metadata["direction"] == "exports"

    def test_get_direction_of_trade_all(self, imf_source):
        """Test getting all trade directions."""
        result = imf_source.get_direction_of_trade(
            countries="US",
            direction="all",
            frequency="annual"
        )

        assert result.success is True

    def test_search_indicators(self, imf_source):
        """Test searching available indicators."""
        result = imf_source.search_indicators()

        assert result.success is True
        assert result.count > 0
        assert isinstance(result.data, list)

    def test_search_indicators_with_query(self, imf_source):
        """Test searching indicators with query."""
        result = imf_source.search_indicators(query="GDP")

        assert result.success is True
        # Should have fewer results than no query
        assert result.count > 0

    def test_adjust_date_by_frequency_quarterly(self, imf_source):
        """Test date adjustment for quarterly frequency."""
        # Start of quarter
        result = imf_source._adjust_date_by_frequency("2023-02-15", "quarter", is_start=True)
        assert result == "2023-01-01"

        # End of quarter
        result = imf_source._adjust_date_by_frequency("2023-02-15", "quarter", is_start=False)
        assert result == "2023-03-31"

    def test_adjust_date_by_frequency_annual(self, imf_source):
        """Test date adjustment for annual frequency."""
        # Start of year
        result = imf_source._adjust_date_by_frequency("2023-06-15", "annual", is_start=True)
        assert result == "2023-01-01"

        # End of year
        result = imf_source._adjust_date_by_frequency("2023-06-15", "annual", is_start=False)
        assert result == "2023-12-31"

    def test_frequency_mapping(self, imf_source):
        """Test frequency code mapping."""
        assert imf_source.frequency_map["annual"] == "A"
        assert imf_source.frequency_map["quarter"] == "Q"
        assert imf_source.frequency_map["month"] == "M"

    def test_sector_mapping(self, imf_source):
        """Test sector code mapping."""
        assert imf_source.sector_map["government"] == "S1311"
        assert imf_source.sector_map["central_bank"] == "S121"
        assert imf_source.sector_map["monetary_authorities"] == "S1X"

    def test_trade_indicators(self, imf_source):
        """Test trade indicator mapping."""
        assert "exports" in imf_source.trade_indicators
        assert "imports" in imf_source.trade_indicators
        assert "balance" in imf_source.trade_indicators
        assert "all" in imf_source.trade_indicators

    def test_irfcl_presets(self, imf_source):
        """Test IRFCL preset configurations."""
        assert "top_lines" in imf_source.irfcl_presets
        assert "reserve_assets" in imf_source.irfcl_presets
        assert "gold_reserves" in imf_source.irfcl_presets
        assert "derivative_assets" in imf_source.irfcl_presets


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
