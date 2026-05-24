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


class _MyStocksCursor:
    """Mock cursor for my-stocks endpoint tests"""
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _MyStocksConnection:
    """Mock connection for my-stocks endpoint tests"""
    def __init__(self, positions_data, watchlist_data):
        self.positions_data = positions_data
        self.watchlist_data = watchlist_data
        self.query_count = 0

    def execute(self, query, params=()):
        self.query_count += 1
        # First query is positions, second is watchlist
        if self.query_count == 1:
            return _MyStocksCursor(self.positions_data)
        else:
            return _MyStocksCursor(self.watchlist_data)

    def close(self):
        pass


def test_my_stocks_with_positions_and_watchlist(monkeypatch):
    """测试返回持仓和自选股"""
    positions_data = [
        ('600000.SH', '浦发银行'),
        ('000001.SZ', '平安银行'),
    ]
    watchlist_data = [
        ('600519.SH', '贵州茅台'),
        ('000858.SZ', '五粮液'),
    ]

    def mock_get_db():
        return _MyStocksConnection(positions_data, watchlist_data)

    monkeypatch.setattr(server, 'get_db', mock_get_db)

    with server.app.test_client() as client:
        response = client.get('/api/stocks/my-stocks')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'positions' in data
        assert 'watchlist' in data

        assert len(data['positions']) == 2
        assert data['positions'][0] == {'symbol': '600000.SH', 'name': '浦发银行'}
        assert data['positions'][1] == {'symbol': '000001.SZ', 'name': '平安银行'}

        assert len(data['watchlist']) == 2
        assert data['watchlist'][0] == {'symbol': '600519.SH', 'name': '贵州茅台'}
        assert data['watchlist'][1] == {'symbol': '000858.SZ', 'name': '五粮液'}


def test_my_stocks_empty():
    """测试空持仓和自选股"""
    def mock_get_db():
        return _MyStocksConnection([], [])

    import api.server as server_module
    original_get_db = server_module.get_db
    server_module.get_db = mock_get_db

    try:
        with server.app.test_client() as client:
            response = client.get('/api/stocks/my-stocks')
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data['positions'] == []
            assert data['watchlist'] == []
    finally:
        server_module.get_db = original_get_db


def test_my_stocks_error_handling(monkeypatch):
    """测试错误处理"""
    def mock_get_db():
        raise Exception("Database connection failed")

    monkeypatch.setattr(server, 'get_db', mock_get_db)

    with server.app.test_client() as client:
        response = client.get('/api/stocks/my-stocks')
        assert response.status_code == 500

        data = json.loads(response.data)
        assert data['positions'] == []
        assert data['watchlist'] == []
