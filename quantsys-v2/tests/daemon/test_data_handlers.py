"""Tests for L1 data layer handlers."""
import pytest
import json
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_stock_info_success():
    """Test get_stock_info returns stock data."""
    from infrastructure.daemon.handlers.data_handlers import get_stock_info
    
    params = {"symbol": "AAPL"}
    
    # Mock API response
    mock_response = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "sector": "Technology"
    }
    
    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await get_stock_info(params)
        parsed = json.loads(result)
        
        assert parsed["symbol"] == "AAPL"
        assert parsed["name"] == "Apple Inc."
        mock_api.assert_called_once_with("GET", "/api/stocks/AAPL")


@pytest.mark.asyncio
async def test_get_stock_info_missing_symbol():
    """Test get_stock_info raises error for missing symbol."""
    from infrastructure.daemon.handlers.data_handlers import get_stock_info
    
    params = {}
    
    with pytest.raises(ValueError) as exc_info:
        await get_stock_info(params)
    
    assert "symbol" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_stock_info_api_error():
    """Test get_stock_info handles API errors."""
    from infrastructure.daemon.handlers.data_handlers import get_stock_info

    params = {"symbol": "INVALID"}

    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.side_effect = Exception("Stock not found")

        with pytest.raises(Exception) as exc_info:
            await get_stock_info(params)

        assert "Stock not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_stock_price_success():
    """Test get_stock_price returns price data."""
    from infrastructure.daemon.handlers.data_handlers import get_stock_price

    params = {
        "symbol": "AAPL",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }

    mock_response = {
        "symbol": "AAPL",
        "prices": [
            {"date": "2024-01-02", "close": 185.64},
            {"date": "2024-01-03", "close": 184.25}
        ]
    }

    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response

        result = await get_stock_price(params)
        parsed = json.loads(result)

        assert parsed["symbol"] == "AAPL"
        assert len(parsed["prices"]) == 2
        mock_api.assert_called_once_with("GET", "/api/stocks/AAPL/prices?start_date=2024-01-01&end_date=2024-01-31")


@pytest.mark.asyncio
async def test_get_stock_price_missing_symbol():
    """Test get_stock_price requires symbol."""
    from infrastructure.daemon.handlers.data_handlers import get_stock_price

    params = {"start_date": "2024-01-01"}

    with pytest.raises(ValueError) as exc_info:
        await get_stock_price(params)

    assert "symbol" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_stock_fundamentals_success():
    """Test get_stock_fundamentals returns fundamental data."""
    from infrastructure.daemon.handlers.data_handlers import get_stock_fundamentals

    params = {"symbol": "AAPL"}

    mock_response = {
        "symbol": "AAPL",
        "market_cap": 2800000000000,
        "pe_ratio": 28.5,
        "eps": 6.42
    }

    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response

        result = await get_stock_fundamentals(params)
        parsed = json.loads(result)

        assert parsed["symbol"] == "AAPL"
        assert parsed["pe_ratio"] == 28.5
        mock_api.assert_called_once_with("GET", "/api/stocks/AAPL/fundamentals")


@pytest.mark.asyncio
async def test_get_stock_fundamentals_missing_symbol():
    """Test get_stock_fundamentals requires symbol."""
    from infrastructure.daemon.handlers.data_handlers import get_stock_fundamentals

    params = {}

    with pytest.raises(ValueError) as exc_info:
        await get_stock_fundamentals(params)

    assert "symbol" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_search_stocks_success():
    """Test search_stocks returns search results."""
    from infrastructure.daemon.handlers.data_handlers import search_stocks

    params = {"query": "Apple", "limit": 10}

    mock_response = {
        "results": [
            {"symbol": "AAPL", "name": "Apple Inc."}
        ],
        "total": 1
    }

    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response

        result = await search_stocks(params)
        parsed = json.loads(result)

        assert parsed["total"] == 1
        assert parsed["results"][0]["symbol"] == "AAPL"
        mock_api.assert_called_once_with("GET", "/api/stocks/search?q=Apple&limit=10")


@pytest.mark.asyncio
async def test_search_stocks_missing_query():
    """Test search_stocks requires query."""
    from infrastructure.daemon.handlers.data_handlers import search_stocks

    params = {}

    with pytest.raises(ValueError) as exc_info:
        await search_stocks(params)

    assert "query" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_market_data_success():
    """Test get_market_data returns market overview."""
    from infrastructure.daemon.handlers.data_handlers import get_market_data

    params = {}

    mock_response = {
        "indices": {
            "SPX": {"value": 4783.45, "change": 0.5}
        },
        "timestamp": "2024-01-15T16:00:00Z"
    }

    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response

        result = await get_market_data(params)
        parsed = json.loads(result)

        assert "indices" in parsed
        assert parsed["indices"]["SPX"]["value"] == 4783.45
        mock_api.assert_called_once_with("GET", "/api/market/overview")


@pytest.mark.asyncio
async def test_update_stock_data_success():
    """Test update_stock_data triggers data update."""
    from infrastructure.daemon.handlers.data_handlers import update_stock_data

    params = {"symbol": "AAPL"}

    mock_response = {
        "status": "success",
        "message": "Data update triggered for AAPL"
    }

    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response

        result = await update_stock_data(params)
        parsed = json.loads(result)

        assert parsed["status"] == "success"
        mock_api.assert_called_once_with("POST", "/api/stocks/AAPL/update", data={})


@pytest.mark.asyncio
async def test_update_stock_data_missing_symbol():
    """Test update_stock_data requires symbol."""
    from infrastructure.daemon.handlers.data_handlers import update_stock_data

    params = {}

    with pytest.raises(ValueError) as exc_info:
        await update_stock_data(params)

    assert "symbol" in str(exc_info.value).lower()
