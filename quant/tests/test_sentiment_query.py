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
