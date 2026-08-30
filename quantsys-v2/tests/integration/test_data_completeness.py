"""Integration tests for data completeness checking"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import pandas as pd

from adapters.outbound.datasources.manager import DataProviderManager
from domain.models.market_data import KlineData


class TestDataCompleteness:
    """Test data completeness checking against trading calendar"""

    @pytest.fixture
    def manager(self):
        """Create DataProviderManager instance"""
        return DataProviderManager()

    @pytest.fixture
    def mock_trading_days(self):
        """Mock trading calendar - 5 consecutive trading days"""
        return [
            '2024-01-02',  # Tuesday
            '2024-01-03',  # Wednesday
            '2024-01-04',  # Thursday
            '2024-01-05',  # Friday
            '2024-01-08',  # Monday (next week)
        ]

    def test_completeness_100_percent(self, manager, mock_trading_days):
        """Complete data (5/5) should return 100% completeness"""
        kline_data = [
            KlineData(symbol='000001', date='2024-01-02', open=10.0, high=11.0,
                     low=9.5, close=10.5, volume=1000000, source='test'),
            KlineData(symbol='000001', date='2024-01-03', open=10.5, high=11.5,
                     low=10.0, close=11.0, volume=1100000, source='test'),
            KlineData(symbol='000001', date='2024-01-04', open=11.0, high=12.0,
                     low=10.5, close=11.5, volume=1200000, source='test'),
            KlineData(symbol='000001', date='2024-01-05', open=11.5, high=12.5,
                     low=11.0, close=12.0, volume=1300000, source='test'),
            KlineData(symbol='000001', date='2024-01-08', open=12.0, high=13.0,
                     low=11.5, close=12.5, volume=1400000, source='test'),
        ]

        with patch('application.services.trading_calendar_service.TradingCalendarService') as mock_cal:
            mock_cal.return_value.get_trading_days.return_value = mock_trading_days

            result = manager.get_data_completeness(
                symbol='000001',
                start_date='2024-01-02',
                end_date='2024-01-08',
                data=kline_data
            )

        assert result['completeness'] == 1.0
        assert result['expected_days'] == 5
        assert result['actual_days'] == 5
        assert result['missing_dates'] == []
        assert result['has_data'] is True

    def test_completeness_80_percent(self, manager, mock_trading_days):
        """Missing 1 day (4/5) should return 80% completeness"""
        # Missing 2024-01-04
        kline_data = [
            KlineData(symbol='000001', date='2024-01-02', open=10.0, high=11.0,
                     low=9.5, close=10.5, volume=1000000, source='test'),
            KlineData(symbol='000001', date='2024-01-03', open=10.5, high=11.5,
                     low=10.0, close=11.0, volume=1100000, source='test'),
            # 2024-01-04 missing
            KlineData(symbol='000001', date='2024-01-05', open=11.5, high=12.5,
                     low=11.0, close=12.0, volume=1300000, source='test'),
            KlineData(symbol='000001', date='2024-01-08', open=12.0, high=13.0,
                     low=11.5, close=12.5, volume=1400000, source='test'),
        ]

        with patch('application.services.trading_calendar_service.TradingCalendarService') as mock_cal:
            mock_cal.return_value.get_trading_days.return_value = mock_trading_days

            result = manager.get_data_completeness(
                symbol='000001',
                start_date='2024-01-02',
                end_date='2024-01-08',
                data=kline_data
            )

        assert result['completeness'] == 0.8
        assert result['expected_days'] == 5
        assert result['actual_days'] == 4
        assert result['missing_dates'] == ['2024-01-04']
        assert result['has_data'] is True

    def test_completeness_no_data(self, manager, mock_trading_days):
        """No data (0/5) should return 0% completeness"""
        kline_data = []

        with patch('application.services.trading_calendar_service.TradingCalendarService') as mock_cal:
            mock_cal.return_value.get_trading_days.return_value = mock_trading_days

            result = manager.get_data_completeness(
                symbol='000001',
                start_date='2024-01-02',
                end_date='2024-01-08',
                data=kline_data
            )

        assert result['completeness'] == 0.0
        assert result['expected_days'] == 5
        assert result['actual_days'] == 0
        assert result['missing_dates'] == mock_trading_days
        assert result['has_data'] is False

    def test_completeness_with_dataframe(self, manager, mock_trading_days):
        """Should handle pandas DataFrame input"""
        df = pd.DataFrame([
            {'date': '2024-01-02', 'open': 10.0, 'close': 10.5},
            {'date': '2024-01-03', 'open': 10.5, 'close': 11.0},
            {'date': '2024-01-05', 'open': 11.5, 'close': 12.0},
            {'date': '2024-01-08', 'open': 12.0, 'close': 12.5},
        ])

        with patch('application.services.trading_calendar_service.TradingCalendarService') as mock_cal:
            mock_cal.return_value.get_trading_days.return_value = mock_trading_days

            result = manager.get_data_completeness(
                symbol='000001',
                start_date='2024-01-02',
                end_date='2024-01-08',
                data=df
            )

        assert result['completeness'] == 0.8
        assert result['expected_days'] == 5
        assert result['actual_days'] == 4
        assert result['missing_dates'] == ['2024-01-04']

    def test_completeness_with_trade_date_column(self, manager, mock_trading_days):
        """Should handle DataFrame with 'trade_date' column"""
        df = pd.DataFrame([
            {'trade_date': '2024-01-02', 'open': 10.0, 'close': 10.5},
            {'trade_date': '2024-01-03', 'open': 10.5, 'close': 11.0},
            {'trade_date': '2024-01-04', 'open': 11.0, 'close': 11.5},
        ])

        with patch('application.services.trading_calendar_service.TradingCalendarService') as mock_cal:
            mock_cal.return_value.get_trading_days.return_value = mock_trading_days

            result = manager.get_data_completeness(
                symbol='000001',
                start_date='2024-01-02',
                end_date='2024-01-08',
                data=df
            )

        assert result['completeness'] == 0.6
        assert result['expected_days'] == 5
        assert result['actual_days'] == 3
        assert set(result['missing_dates']) == {'2024-01-05', '2024-01-08'}

    def test_completeness_auto_fetch(self, manager, mock_trading_days):
        """Should auto-fetch data when data=None"""
        mock_klines = [
            KlineData(symbol='000001', date='2024-01-02', open=10.0, high=11.0,
                     low=9.5, close=10.5, volume=1000000, source='database'),
            KlineData(symbol='000001', date='2024-01-03', open=10.5, high=11.5,
                     low=10.0, close=11.0, volume=1100000, source='database'),
        ]

        with patch('application.services.trading_calendar_service.TradingCalendarService') as mock_cal, \
             patch.object(manager, 'get_klines') as mock_get:

            mock_cal.return_value.get_trading_days.return_value = mock_trading_days
            mock_get.return_value = {
                'success': True,
                'data': mock_klines,
                'source': 'database'
            }

            result = manager.get_data_completeness(
                symbol='000001',
                start_date='2024-01-02',
                end_date='2024-01-08',
                data=None  # Auto-fetch
            )

        assert result['completeness'] == 0.4
        assert result['expected_days'] == 5
        assert result['actual_days'] == 2
        assert result['source'] == 'database'
        assert result['has_data'] is True
        mock_get.assert_called_once_with('000001', 'daily', '2024-01-02', '2024-01-08')

    def test_completeness_fetch_failed(self, manager, mock_trading_days):
        """Should return error when auto-fetch fails"""
        with patch('application.services.trading_calendar_service.TradingCalendarService') as mock_cal, \
             patch.object(manager, 'get_klines') as mock_get:

            mock_cal.return_value.get_trading_days.return_value = mock_trading_days
            mock_get.return_value = {
                'success': False,
                'error': 'All providers failed'
            }

            result = manager.get_data_completeness(
                symbol='000001',
                start_date='2024-01-02',
                end_date='2024-01-08',
                data=None
            )

        assert result['completeness'] == 0.0
        assert result['expected_days'] == 5
        assert result['actual_days'] == 0
        assert result['has_data'] is False
        assert 'error' in result
        assert result['missing_dates'] == mock_trading_days

    def test_completeness_no_trading_days(self, manager):
        """Should handle date range with no trading days"""
        with patch('application.services.trading_calendar_service.TradingCalendarService') as mock_cal:
            mock_cal.return_value.get_trading_days.return_value = []

            result = manager.get_data_completeness(
                symbol='000001',
                start_date='2024-01-06',  # Weekend
                end_date='2024-01-07',
                data=[]
            )

        assert result['completeness'] == 0.0
        assert result['expected_days'] == 0
        assert result['actual_days'] == 0
        assert result['missing_dates'] == []
        assert result['has_data'] is False
        assert 'error' in result

    def test_completeness_with_dict_list(self, manager, mock_trading_days):
        """Should handle list of dict input"""
        dict_data = [
            {'date': '2024-01-02', 'open': 10.0, 'close': 10.5},
            {'date': '2024-01-03', 'open': 10.5, 'close': 11.0},
            {'date': '2024-01-04', 'open': 11.0, 'close': 11.5},
            {'date': '2024-01-05', 'open': 11.5, 'close': 12.0},
            {'date': '2024-01-08', 'open': 12.0, 'close': 12.5},
        ]

        with patch('application.services.trading_calendar_service.TradingCalendarService') as mock_cal:
            mock_cal.return_value.get_trading_days.return_value = mock_trading_days

            result = manager.get_data_completeness(
                symbol='000001',
                start_date='2024-01-02',
                end_date='2024-01-08',
                data=dict_data
            )

        assert result['completeness'] == 1.0
        assert result['expected_days'] == 5
        assert result['actual_days'] == 5
        assert result['missing_dates'] == []

    def test_completeness_exception_handling(self, manager):
        """Should handle exceptions gracefully"""
        with patch('application.services.trading_calendar_service.TradingCalendarService') as mock_cal:
            mock_cal.return_value.get_trading_days.side_effect = Exception("Calendar service down")

            result = manager.get_data_completeness(
                symbol='000001',
                start_date='2024-01-02',
                end_date='2024-01-08',
                data=[]
            )

        assert result['completeness'] == 0.0
        assert result['expected_days'] == 0
        assert result['actual_days'] == 0
        assert result['has_data'] is False
        assert 'error' in result
        assert 'Calendar service down' in result['error']
