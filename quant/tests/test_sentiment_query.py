"""Tests for sentiment_query module."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock
from quantsys.cli.sentiment_query import (
    get_stock_fund_flow,
    get_fund_flow_stats,
    _fetch_from_sina,
    _fetch_from_akshare,
    _update_stats,
    _source_stats,
)


@pytest.fixture(autouse=True)
def reset_stats():
    """Reset stats before each test."""
    _source_stats['sina']['success'] = 0
    _source_stats['sina']['failure'] = 0
    _source_stats['sina']['last_success_time'] = None
    _source_stats['akshare']['success'] = 0
    _source_stats['akshare']['failure'] = 0
    _source_stats['akshare']['last_success_time'] = None
    yield


def test_get_fund_flow_stats_initial():
    """Test stats with no requests."""
    stats = get_fund_flow_stats()
    assert stats['sina']['success'] == 0
    assert stats['sina']['failure'] == 0
    assert stats['sina']['total_requests'] == 0
    assert stats['sina']['success_rate'] == 0.0


def test_get_fund_flow_stats_with_data():
    """Test stats after some requests."""
    _update_stats('sina', success=True)
    _update_stats('sina', success=True)
    _update_stats('sina', success=False)

    stats = get_fund_flow_stats()
    assert stats['sina']['success'] == 2
    assert stats['sina']['failure'] == 1
    assert stats['sina']['total_requests'] == 3
    assert abs(stats['sina']['success_rate'] - 0.6667) < 0.01


def test_update_stats_success():
    """Test updating stats on success."""
    _update_stats('sina', success=True)
    assert _source_stats['sina']['success'] == 1
    assert _source_stats['sina']['failure'] == 0
    assert _source_stats['sina']['last_success_time'] is not None


def test_update_stats_failure():
    """Test updating stats on failure."""
    _update_stats('sina', success=False)
    assert _source_stats['sina']['success'] == 0
    assert _source_stats['sina']['failure'] == 1
    assert _source_stats['sina']['last_success_time'] is None


def test_update_stats_multiple():
    """Test multiple stat updates."""
    _update_stats('sina', success=True)
    _update_stats('sina', success=True)
    _update_stats('sina', success=False)
    assert _source_stats['sina']['success'] == 2
    assert _source_stats['sina']['failure'] == 1


@patch('requests.get')
def test_fetch_from_sina_success(mock_get):
    """Test successful Sina API call."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = [
        {
            "opendate": "2024-01-15",
            "trade": "10.50",
            "changeratio": "0.02",
            "netamount": "1000000",
            "ratioamount": "0.05",
        },
        {
            "opendate": "2024-01-16",
            "trade": "10.70",
            "changeratio": "0.019",
            "netamount": "1200000",
            "ratioamount": "0.06",
        },
    ]
    mock_get.return_value = mock_response

    result = _fetch_from_sina("600094", days=2)

    assert 'error' not in result
    assert result['symbol'] == "600094"
    assert result['source'] == "sina"
    assert len(result['data']) == 2
    assert len(result['estimated_fields']) == 8

    # Check field mapping
    record = result['data'][0]
    assert record['日期'] == "2024-01-15"
    assert record['收盘价'] == 10.50
    assert record['涨跌幅'] == 2.0
    assert record['主力净流入-净额'] == 1000000.0
    assert record['主力净流入-净占比'] == 5.0

    # Check estimation ratios
    assert record['超大单净流入-净额'] == 600000.0  # 60%
    assert record['大单净流入-净额'] == 400000.0  # 40%
    assert record['中单净流入-净额'] == -500000.0  # -50%
    assert record['小单净流入-净额'] == -500000.0  # -50%


@patch('requests.get')
def test_fetch_from_sina_empty_data(mock_get):
    """Test Sina API returning empty data."""
    mock_response = Mock()
    mock_response.json.return_value = []
    mock_get.return_value = mock_response

    result = _fetch_from_sina("600094", days=10)

    assert 'error' in result
    assert result['symbol'] == "600094"
    assert "新浪返回空数据" in result['error']


@patch('requests.get')
def test_fetch_from_sina_network_error(mock_get):
    """Test Sina API network failure."""
    mock_get.side_effect = Exception("Connection timeout")

    result = _fetch_from_sina("600094", days=10)

    assert 'error' in result
    assert result['symbol'] == "600094"
    assert "新浪数据源失败" in result['error']
    assert "Connection timeout" in result['error']


@patch('requests.get')
def test_fetch_from_sina_http_error(mock_get):
    """Test Sina API HTTP error."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("404 Not Found")
    mock_get.return_value = mock_response

    result = _fetch_from_sina("600094", days=10)

    assert 'error' in result
    assert result['symbol'] == "600094"


@patch('akshare.stock_individual_fund_flow')
@patch('quantsys.cli.sentiment_query._disable_proxy_env')
def test_fetch_from_akshare_success(mock_disable, mock_ak):
    """Test successful akshare API call."""
    import pandas as pd

    # Mock DataFrame response
    mock_df = pd.DataFrame([
        {"日期": "2024-01-15", "收盘价": 10.50, "主力净流入-净额": 1000000},
        {"日期": "2024-01-16", "收盘价": 10.70, "主力净流入-净额": 1200000},
    ])
    mock_ak.return_value = mock_df

    result = _fetch_from_akshare("600094", days=2)

    assert 'error' not in result
    assert result['symbol'] == "600094"
    assert result['source'] == "akshare"
    assert len(result['data']) == 2
    assert result['estimated_fields'] == []  # akshare has no estimated fields


@patch('akshare.stock_individual_fund_flow')
@patch('quantsys.cli.sentiment_query._disable_proxy_env')
def test_fetch_from_akshare_empty(mock_disable, mock_ak):
    """Test akshare returning empty DataFrame."""
    import pandas as pd

    mock_ak.return_value = pd.DataFrame()

    result = _fetch_from_akshare("600094", days=10)

    assert 'error' in result
    assert result['symbol'] == "600094"
    assert "无资金流向数据" in result['error']


@patch('akshare.stock_individual_fund_flow')
@patch('quantsys.cli.sentiment_query._disable_proxy_env')
def test_fetch_from_akshare_exception(mock_disable, mock_ak):
    """Test akshare API exception."""
    mock_ak.side_effect = Exception("API error")

    result = _fetch_from_akshare("600094", days=10)

    assert 'error' in result
    assert result['symbol'] == "600094"
    assert "akshare 数据源失败" in result['error']


@patch('quantsys.cli.sentiment_query._fetch_from_akshare')
@patch('quantsys.cli.sentiment_query._fetch_from_sina')
def test_get_stock_fund_flow_sina_success(mock_sina, mock_akshare):
    """Test successful Sina call (no fallback)."""
    mock_sina.return_value = {
        "symbol": "600094",
        "data": [{"日期": "2024-01-15"}],
        "source": "sina",
        "estimated_fields": []
    }

    result = get_stock_fund_flow("600094", days=5)

    assert result['source'] == "sina"
    assert mock_sina.called
    assert not mock_akshare.called  # Should not fallback


@patch('quantsys.cli.sentiment_query._fetch_from_akshare')
@patch('quantsys.cli.sentiment_query._fetch_from_sina')
def test_get_stock_fund_flow_fallback_to_akshare(mock_sina, mock_akshare):
    """Test fallback to akshare when Sina fails."""
    mock_sina.return_value = {"error": "Sina failed", "symbol": "600094"}
    mock_akshare.return_value = {
        "symbol": "600094",
        "data": [{"日期": "2024-01-15"}],
        "source": "akshare",
        "estimated_fields": []
    }

    result = get_stock_fund_flow("600094", days=5)

    assert result['source'] == "akshare"
    assert mock_sina.called
    assert mock_akshare.called  # Should fallback


@patch('quantsys.cli.sentiment_query._fetch_from_akshare')
@patch('quantsys.cli.sentiment_query._fetch_from_sina')
def test_get_stock_fund_flow_both_fail(mock_sina, mock_akshare):
    """Test when both sources fail."""
    mock_sina.return_value = {"error": "Sina failed", "symbol": "600094"}
    mock_akshare.return_value = {"error": "akshare failed", "symbol": "600094"}

    result = get_stock_fund_flow("600094", days=5)

    assert 'error' in result
    assert mock_sina.called
    assert mock_akshare.called


@patch('quantsys.cli.sentiment_query._fetch_from_sina')
def test_get_stock_fund_flow_with_zero_days(mock_sina):
    """Test with days=0 (boundary case)."""
    mock_sina.return_value = {"symbol": "600094", "data": [], "source": "sina", "estimated_fields": []}

    result = get_stock_fund_flow("600094", days=0)

    # This test will reveal if validation is needed
    assert mock_sina.called


@patch('quantsys.cli.sentiment_query._fetch_from_sina')
def test_get_stock_fund_flow_with_negative_days(mock_sina):
    """Test with negative days (invalid input)."""
    mock_sina.return_value = {"symbol": "600094", "data": [], "source": "sina", "estimated_fields": []}

    result = get_stock_fund_flow("600094", days=-5)

    # This test will reveal if validation is needed
    assert mock_sina.called


@patch('quantsys.cli.sentiment_query._fetch_from_sina')
def test_get_stock_fund_flow_with_large_days(mock_sina):
    """Test with very large days value."""
    mock_sina.return_value = {"symbol": "600094", "data": [], "source": "sina", "estimated_fields": []}

    result = get_stock_fund_flow("600094", days=10000)

    assert mock_sina.called


@patch('requests.get')
def test_fetch_from_sina_with_malformed_data(mock_get):
    """Test Sina API with missing fields."""
    mock_response = Mock()
    mock_response.json.return_value = [
        {"opendate": "2024-01-15"}  # Missing required fields
    ]
    mock_get.return_value = mock_response

    result = _fetch_from_sina("600094", days=1)

    # Should handle missing fields gracefully (defaults to 0)
    assert 'error' not in result
    assert 'data' in result
    assert len(result['data']) == 1
    # Check that missing fields default to 0
    record = result['data'][0]
    assert record['日期'] == "2024-01-15"
    assert record['收盘价'] == 0.0
    assert record['涨跌幅'] == 0.0
    assert record['主力净流入-净额'] == 0.0


@patch('requests.get')
def test_fetch_from_sina_market_sh(mock_get):
    """Test Shanghai market prefix (6xxxxx)."""
    mock_response = Mock()
    mock_response.json.return_value = [{"opendate": "2024-01-15", "trade": "10", "changeratio": "0", "netamount": "0", "ratioamount": "0"}]
    mock_get.return_value = mock_response

    _fetch_from_sina("600094", days=1)

    # Verify API called with sh prefix
    call_args = mock_get.call_args
    assert call_args[1]['params']['daima'] == "sh600094"


@patch('requests.get')
def test_fetch_from_sina_market_sz(mock_get):
    """Test Shenzhen market prefix (0xxxxx, 3xxxxx)."""
    mock_response = Mock()
    mock_response.json.return_value = [{"opendate": "2024-01-15", "trade": "10", "changeratio": "0", "netamount": "0", "ratioamount": "0"}]
    mock_get.return_value = mock_response

    _fetch_from_sina("000001", days=1)

    call_args = mock_get.call_args
    assert call_args[1]['params']['daima'] == "sz000001"


@patch('requests.get')
def test_fetch_from_sina_market_bj(mock_get):
    """Test Beijing market prefix (8xxxxx, 4xxxxx)."""
    mock_response = Mock()
    mock_response.json.return_value = [{"opendate": "2024-01-15", "trade": "10", "changeratio": "0", "netamount": "0", "ratioamount": "0"}]
    mock_get.return_value = mock_response

    _fetch_from_sina("830001", days=1)

    call_args = mock_get.call_args
    assert call_args[1]['params']['daima'] == "bj830001"


@patch('akshare.stock_individual_fund_flow')
@patch('quantsys.cli.sentiment_query._disable_proxy_env')
def test_fetch_from_akshare_market_detection(mock_disable, mock_ak):
    """Test akshare market parameter."""
    import pandas as pd
    mock_ak.return_value = pd.DataFrame([{"日期": "2024-01-15"}])

    # Test sh
    _fetch_from_akshare("600094", days=1)
    assert mock_ak.call_args[1]['market'] == "sh"

    # Test sz
    _fetch_from_akshare("000001", days=1)
    assert mock_ak.call_args[1]['market'] == "sz"

    # Test bj
    _fetch_from_akshare("830001", days=1)
    assert mock_ak.call_args[1]['market'] == "bj"
