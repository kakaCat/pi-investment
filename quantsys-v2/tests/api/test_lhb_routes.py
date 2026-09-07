"""
LHB API 路由集成测试
"""
import pytest
from unittest.mock import patch, Mock


def test_api_stock_lhb_success(client):
    """测试个股查询端点成功"""
    with patch('api.routes.sentiment.lhb_service') as mock_service:
        mock_service.get_stock_lhb.return_value = {
            'success': True,
            'symbol': '600737',
            'name': '中粮糖业',
            'total_records': 2,
            'records': [
                {
                    'date': '2026-05-31',
                    'reason': '日涨幅偏离值达7%',
                    'close_price': 10.50,
                    'change_pct': 8.5,
                    'net_buy': 5000.0
                }
            ]
        }

        response = client.get('/api/stock/600737/lhb?days=30')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['symbol'] == '600737'
        assert data['name'] == '中粮糖业'


def test_api_stock_lhb_no_data(client):
    """测试个股无数据"""
    with patch('api.routes.sentiment.lhb_service') as mock_service:
        mock_service.get_stock_lhb.return_value = {
            'success': False,
            'error': '该股票近期无龙虎榜记录'
        }

        response = client.get('/api/stock/999999/lhb?days=30')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert '无龙虎榜记录' in data['error']


def test_api_daily_lhb_success(client):
    """测试日期汇总端点成功"""
    with patch('api.routes.sentiment.lhb_service') as mock_service:
        mock_service.get_daily_lhb.return_value = {
            'success': True,
            'date': '2026-05-31',
            'total_stocks': 2,
            'stocks': [
                {
                    'symbol': '600737',
                    'name': '中粮糖业',
                    'reason': '日涨幅偏离值达7%',
                    'close_price': 10.50,
                    'change_pct': 8.5
                }
            ]
        }

        response = client.get('/api/lhb/daily?date=20260531')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['date'] == '2026-05-31'
        assert data['total_stocks'] == 2


def test_api_daily_lhb_missing_date(client):
    """测试缺少日期参数"""
    response = client.get('/api/lhb/daily')
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert '缺少必填参数' in data['error']
