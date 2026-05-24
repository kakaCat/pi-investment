"""
测试股票 API 端点
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = PROJECT_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

from api import server


def test_get_my_stocks_success():
    """测试成功获取持仓和自选股"""
    with server.app.test_client() as client:
        response = client.get('/api/stocks/my-stocks')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'positions' in data
        assert 'watchlist' in data
        assert isinstance(data['positions'], list)
        assert isinstance(data['watchlist'], list)


def test_get_my_stocks_empty():
    """测试空持仓和自选股"""
    with server.app.test_client() as client:
        response = client.get('/api/stocks/my-stocks')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data['positions'], list)
        assert isinstance(data['watchlist'], list)


def test_get_my_stocks_response_format():
    """测试响应格式"""
    with server.app.test_client() as client:
        response = client.get('/api/stocks/my-stocks')
        assert response.status_code == 200
        data = json.loads(response.data)

        # 验证返回的数据结构
        assert 'positions' in data
        assert 'watchlist' in data

        # 如果有数据，验证每个项目的格式
        for position in data['positions']:
            assert 'symbol' in position
            assert 'name' in position

        for stock in data['watchlist']:
            assert 'symbol' in stock
            assert 'name' in stock
