"""
LhbService 单元测试
"""
import pytest
from unittest.mock import Mock

from application.services.lhb_service import LhbService


class TestLhbService:

    def test_get_stock_lhb_success(self):
        mock_data_source = Mock()
        mock_data_source.get_stock_lhb.return_value = {
            'success': True,
            'symbol': '600737',
            'name': '中粮糖业',
            'total_records': 2,
            'records': [
                {'date': '2026-05-31', 'close_price': 10.50, 'reason': '日涨幅偏离值达7%'},
                {'date': '2026-05-30', 'close_price': 10.20, 'reason': '日振幅值达15%'},
            ],
            'source': 'mock',
        }

        service = LhbService(data_source=mock_data_source)
        result = service.get_stock_lhb('600737', days=30)

        assert result['success'] is True
        assert result['symbol'] == '600737'
        assert result['name'] == '中粮糖业'
        assert result['total_records'] == 2
        assert len(result['records']) == 2
        assert result['records'][0]['date'] == '2026-05-31'
        assert result['records'][0]['close_price'] == 10.50

    def test_get_stock_lhb_no_data(self):
        mock_data_source = Mock()
        mock_data_source.get_stock_lhb.return_value = {
            'success': False,
            'error': '无龙虎榜记录',
        }

        service = LhbService(data_source=mock_data_source)
        result = service.get_stock_lhb('600737', days=30)

        assert result['success'] is False
        assert '无龙虎榜记录' in result['error']

    def test_get_stock_lhb_exception(self):
        mock_data_source = Mock()
        mock_data_source.get_stock_lhb.side_effect = Exception('网络错误')

        service = LhbService(data_source=mock_data_source)
        with pytest.raises(Exception, match='网络错误'):
            service.get_stock_lhb('600737', days=30)

    def test_get_daily_lhb_success(self):
        mock_data_source = Mock()
        mock_data_source.get_daily_lhb.return_value = {
            'success': True,
            'date': '2026-05-31',
            'total_stocks': 2,
            'stocks': [
                {'symbol': '600737', 'name': '中粮糖业', 'close_price': 10.50, 'reason': '日涨幅偏离值达7%'},
                {'symbol': '600519', 'name': '贵州茅台', 'close_price': 1800.0, 'reason': '日振幅值达15%'},
            ],
            'source': 'mock',
        }

        service = LhbService(data_source=mock_data_source)
        result = service.get_daily_lhb('20260531')

        assert result['success'] is True
        assert result['date'] == '2026-05-31'
        assert result['total_stocks'] == 2
        assert len(result['stocks']) == 2
        assert result['stocks'][0]['symbol'] == '600737'

    def test_get_daily_lhb_no_data(self):
        mock_data_source = Mock()
        mock_data_source.get_daily_lhb.return_value = {
            'success': False,
            'error': '无龙虎榜数据',
        }

        service = LhbService(data_source=mock_data_source)
        result = service.get_daily_lhb('20260531')

        assert result['success'] is False
        assert '无龙虎榜数据' in result['error']

    def test_format_date(self):
        service = LhbService()
        assert service.data_source._format_date('20260531') == '2026-05-31'
        assert service.data_source._format_date('20261225') == '2026-12-25'
