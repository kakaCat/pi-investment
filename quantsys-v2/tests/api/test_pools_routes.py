"""Tests for /api/pools/* routes."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    """Create a test Flask client with pools blueprint."""
    from flask import Flask
    from adapters.inbound.api.routes.pools import pools_bp

    app = Flask(__name__)
    app.register_blueprint(pools_bp)

    with app.test_client() as c:
        yield c


class TestPoolsRoutes:
    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_create_pool(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.create_pool.return_value = {
            'id': 1, 'name': '测试池', 'pool_type': 'static',
            'symbols': ['600519.SH'],
        }
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.post('/api/pools', json={
            'name': '测试池',
            'poolType': 'static',
            'symbols': ['600519.SH'],
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['id'] == 1

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_create_pool_missing_name(self, mock_get, client):
        mock_get.return_value = (MagicMock(), MagicMock())
        resp = client.post('/api/pools', json={
            'poolType': 'static',
            'symbols': ['600519.SH'],
        })
        assert resp.status_code == 400

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_list_pools(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.list_pools.return_value = [
            {'id': 1, 'name': '测试池', 'pool_type': 'static', 'symbol_count': 1},
        ]
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.get('/api/pools')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['data']) == 1

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_get_pool(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.get_pool.return_value = {
            'id': 1, 'name': '测试池', 'pool_type': 'static',
            'symbols': ['600519.SH'],
        }
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.get('/api/pools/1')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['id'] == 1

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_update_pool(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.update_pool.return_value = {
            'id': 1, 'name': '更新后', 'pool_type': 'static',
        }
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.put('/api/pools/1', json={'name': '更新后'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_delete_pool(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.delete_pool.return_value = True
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.delete('/api/pools/1')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_refresh_pool(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.refresh_pool.return_value = {
            'id': 1, 'name': '动态池', 'symbols': ['600519.SH', '000858.SZ'],
        }
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.post('/api/pools/1/refresh')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_sync_stock_names(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.sync_stock_names.return_value = {
            'id': 1,
            'name': '测试池',
            'members': [
                {'symbol': '600519.SH', 'name': '贵州茅台'},
            ],
        }
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.post('/api/pools/1/sync-stock-names')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['members'][0]['name'] == '贵州茅台'
        mock_svc.sync_stock_names.assert_called_once_with(1)

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_validate_pool(self, mock_get, client):
        mock_val = MagicMock()
        mock_val.validate_pool.return_value = {
            'pool_id': 1, 'pool_name': '测试池',
            'best_strategy': {'id': 53, 'score': 82.5},
            'rankings': [], 'recommended_pairs': [],
        }
        mock_get.return_value = (MagicMock(), mock_val)

        resp = client.post('/api/pools/1/validate', json={
            'strategyIds': [53, 54],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['best_strategy']['id'] == 53

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_scan_and_create(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.create_from_scan.return_value = {
            'id': 2, 'name': '扫描池', 'pool_type': 'dynamic',
            'symbols': ['600519.SH', '000858.SZ'],
            'filter_template': {'min_score': 60},
        }
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.post('/api/pools/scan-and-create', json={
            'name': '扫描池',
            'poolType': 'dynamic',
            'filter': {'minScore': 60, 'fundamental': ['pe_low']},
            'refreshInterval': 'weekly',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['id'] == 2


class TestPoolMemberRoutes:
    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_add_members(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.add_members.return_value = {
            'pool': {'id': 1, 'name': '测试池'},
            'added': ['000858.SZ'], 'skipped': [],
        }
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.post('/api/pools/1/members', json={
            'symbols': ['000858.SZ'], 'description': '关注', 'buyPoint': '120以下',
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['data']['added'] == ['000858.SZ']
        mock_svc.add_members.assert_called_once_with(
            pool_id=1, symbols=['000858.SZ'],
            member_data={'description': '关注', 'buy_point': '120以下',
                         'sell_point': None, 'tags': []},
        )

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_add_members_missing_symbols(self, mock_get, client):
        mock_get.return_value = (MagicMock(), MagicMock())
        resp = client.post('/api/pools/1/members', json={})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_add_members_pool_not_found(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.add_members.side_effect = ValueError('Pool 999 not found')
        mock_get.return_value = (mock_svc, MagicMock())
        resp = client.post('/api/pools/999/members', json={'symbols': ['600519.SH']})
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_remove_members(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.remove_members.return_value = {
            'pool': {'id': 1, 'name': '测试池'},
            'removed': ['000858.SZ'], 'skipped': [],
        }
        mock_get.return_value = (mock_svc, MagicMock())

        resp = client.delete('/api/pools/1/members', json={'symbols': ['000858.SZ']})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['data']['removed'] == ['000858.SZ']
        mock_svc.remove_members.assert_called_once_with(
            pool_id=1, symbols=['000858.SZ'])

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_remove_members_missing_symbols(self, mock_get, client):
        mock_get.return_value = (MagicMock(), MagicMock())
        resp = client.delete('/api/pools/1/members', json={})
        assert resp.status_code == 400

    @patch('adapters.inbound.api.routes.pools._get_services')
    def test_remove_members_pool_not_found(self, mock_get, client):
        mock_svc = MagicMock()
        mock_svc.remove_members.side_effect = ValueError('Pool 999 not found')
        mock_get.return_value = (mock_svc, MagicMock())
        resp = client.delete('/api/pools/999/members', json={'symbols': ['600519.SH']})
        assert resp.status_code == 404
