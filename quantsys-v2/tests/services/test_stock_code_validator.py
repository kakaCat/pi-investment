"""
Tests for StockCodeValidator optimization
"""
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from application.services.stock_code_validator import StockCodeValidator


class TestStockCodeValidatorOptimized:
    def test_validate_uses_lightweight_queries(self):
        validator = StockCodeValidator(kline_repo=Mock())
        validator.kline_repo.count_daily_klines = Mock(return_value=1200)

        last_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        validator.kline_repo.get_date_range = Mock(return_value=('2020-01-02', last_date))

        result = validator.validate('600519')

        validator.kline_repo.count_daily_klines.assert_called_once_with('600519')
        validator.kline_repo.get_date_range.assert_called_once_with('600519')

        assert result['valid'] is True
        assert result['exists'] is True
        assert result['has_recent_data'] is True
        assert result['data_summary']['total_records'] == 1200
        assert result['data_summary']['first_date'] == '2020-01-02'
        assert result['data_summary']['last_date'] == last_date
        assert isinstance(result['data_summary']['days_since_update'], int)
        assert result['data_summary']['days_since_update'] >= 2

    def test_validate_returns_invalid_when_no_records(self):
        validator = StockCodeValidator(kline_repo=Mock())
        validator.kline_repo.count_daily_klines = Mock(return_value=0)
        validator.kline_repo.get_date_range = Mock(return_value=None)

        result = validator.validate('999999')

        assert result['valid'] is False
        assert result['exists'] is False
        assert result['has_recent_data'] is False

    def test_validate_returns_invalid_when_date_range_missing(self):
        validator = StockCodeValidator(kline_repo=Mock())
        validator.kline_repo.count_daily_klines = Mock(return_value=5)
        validator.kline_repo.get_date_range = Mock(return_value=None)

        result = validator.validate('000001')

        assert result['valid'] is False
        assert result['exists'] is False
