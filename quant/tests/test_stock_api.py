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


def test_get_stock_list_reads_from_postgres_compat(monkeypatch):
    """股票列表接口应通过 PG compat 查询，不访问 SQLite 文件。"""
    executed = []

    class FakeCursor:
        def __init__(self, rows):
            self.rows = rows

        def fetchone(self):
            return self.rows[0]

        def fetchall(self):
            return self.rows

    class FakeConnection:
        def execute(self, sql, params=None):
            executed.append((sql, params))
            if sql.strip().startswith("SELECT COUNT"):
                return FakeCursor([(1,)])
            return FakeCursor([("600519", "贵州茅台", "A", "酿酒行业")])

        def close(self):
            pass

    monkeypatch.setattr(server, "get_db", lambda: FakeConnection())

    with server.app.test_client() as client:
        response = client.get("/api/stocks/list?market=A&page=1&pageSize=10")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["stocks"] == [
        {"symbol": "600519", "name": "贵州茅台", "market": "A", "industry": "酿酒行业"}
    ]
    assert "FROM stocks" in executed[0][0]
    assert executed[0][1] == ["A"]


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
