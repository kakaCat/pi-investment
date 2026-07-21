"""
统一数据更新 API 测试
"""
import json
import pytest
from unittest.mock import patch
import pandas as pd

from adapters.inbound.api.server import app


@pytest.fixture
def client():
    """创建测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestDataUpdateValidation:
    """输入验证测试"""

    def test_invalid_source(self, client):
        """非法 source 返回 400"""
        rv = client.post('/api/data/update', json={'source': 'invalid'})
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert data['success'] is False
        assert 'error' in data
        assert 'invalid' in data['error'].lower()

    def test_missing_source(self, client):
        """缺少 source 返回 400"""
        rv = client.post('/api/data/update', json={})
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert data['success'] is False

    def test_invalid_days_zero(self, client):
        """days=0 返回 400"""
        rv = client.post('/api/data/update', json={'source': 'all', 'days': 0})
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert data['success'] is False
        assert 'days' in data['error'].lower()

    def test_invalid_days_negative(self, client):
        """days 为负数返回 400"""
        rv = client.post('/api/data/update', json={'source': 'all', 'days': -5})
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert data['success'] is False
        assert 'days' in data['error'].lower()

    def test_invalid_days_string(self, client):
        """days 为非数字字符串返回 400"""
        rv = client.post('/api/data/update', json={'source': 'all', 'days': 'abc'})
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert data['success'] is False
        assert 'days' in data['error'].lower()

    def test_valid_source_default_days(self, client):
        """有效的 source + 默认 days 不接受 400（验证不再触发参数校验）"""
        with patch('api.server._execute_data_update') as mock_exec:
            mock_exec.return_value = {
                'success': True, 'source': 'all',
                'total': 0, 'succeeded': 0, 'failed': 0, 'details': []
            }
            rv = client.post('/api/data/update', json={'source': 'all'})
            # 默认 days=730 有效，不应报 400
            assert rv.status_code == 200


class TestDataUpdateAsync:
    """异步模式测试"""

    @patch('api.server._resolve_source_symbols')
    def test_async_returns_job_id(self, mock_resolve, client):
        """异步模式返回 job_id"""
        mock_resolve.return_value = ['000001']
        rv = client.post('/api/data/update', json={
            'source': 'portfolio',
            'days': 30,
            'async': True
        })
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['success'] is True
        assert 'job_id' in data
        assert data['job_id'] != ''
        assert 'message' in data

    @patch('api.server._resolve_source_symbols')
    def test_async_multiple_sources(self, mock_resolve, client):
        """各 source 均支持异步"""
        mock_resolve.return_value = ['000001']
        for source in ('portfolio', 'watchlist', 'hs300', 'all'):
            rv = client.post('/api/data/update', json={
                'source': source,
                'async': True
            })
            assert rv.status_code == 200
            data = json.loads(rv.data)
            assert data['success'] is True
            assert 'job_id' in data

    @patch('api.server._execute_data_update')
    def test_async_job_status_endpoint_found(self, mock_exec, client):
        """异步创建的 job 可通过 job_id 查询状态"""
        mock_exec.return_value = {
            'success': True, 'source': 'all',
            'total': 0, 'succeeded': 0, 'failed': 0, 'details': []
        }
        rv = client.post('/api/data/update', json={
            'source': 'all',
            'async': True
        })
        assert rv.status_code == 200
        data = json.loads(rv.data)
        job_id = data['job_id']

        # 查询任务状态
        rv2 = client.get(f'/api/data/update/jobs/{job_id}')
        assert rv2.status_code == 200
        job_data = json.loads(rv2.data)
        assert 'status' in job_data
        assert 'source' in job_data
        assert job_data['source'] == 'all'

    def test_job_status_not_found(self, client):
        """查询不存在的 job_id 返回 404"""
        rv = client.get('/api/data/update/jobs/nonexistent-id')
        assert rv.status_code == 404
        data = json.loads(rv.data)
        assert data['success'] is False


class TestDataUpdateSources:
    """各数据源集成测试"""

    @patch('akshare.index_stock_cons_csindex')
    def test_hs300_resolves_component_code_column(self, mock_cons):
        """hs300 使用成分券代码列，不应把日期或指数代码当作股票代码"""
        from adapters.inbound.api.server import _resolve_source_symbols

        mock_cons.return_value = pd.DataFrame({
            '日期': ['2026-05-22', '2026-05-22'],
            '指数代码': ['000300', '000300'],
            '成分券代码': ['000001', '000001'],
            '成分券名称': ['平安银行', '浦发银行'],
        })

        assert _resolve_source_symbols('hs300') == ['000001', '000001']

    @patch('akshare.index_stock_cons_csindex')
    def test_hs300_rejects_unrecognized_code_columns(self, mock_cons):
        """无法识别股票代码列时直接报错，避免误用第一列"""
        from adapters.inbound.api.server import _resolve_source_symbols

        mock_cons.return_value = pd.DataFrame({
            '日期': ['2026-05-22'],
            '指数名称': ['沪深300'],
        })

        with pytest.raises(RuntimeError, match='Cannot identify stock code column'):
            _resolve_source_symbols('hs300')

    @patch('api.server._execute_data_update')
    def test_portfolio_source(self, mock_exec, client):
        """portfolio 源返回有效结构"""
        mock_exec.return_value = {
            'success': True, 'source': 'portfolio',
            'total': 2, 'succeeded': 2, 'failed': 0, 'details': []
        }
        rv = client.post('/api/data/update', json={'source': 'portfolio', 'days': 30})
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['success'] is True
        assert data['source'] == 'portfolio'
        assert 'total' in data
        assert 'succeeded' in data
        assert 'failed' in data
        assert 'details' in data

    @patch('api.server._execute_data_update')
    def test_watchlist_source(self, mock_exec, client):
        """watchlist 源返回有效结构"""
        mock_exec.return_value = {
            'success': True, 'source': 'watchlist',
            'total': 3, 'succeeded': 3, 'failed': 0, 'details': []
        }
        rv = client.post('/api/data/update', json={'source': 'watchlist', 'days': 30})
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['success'] is True
        assert data['source'] == 'watchlist'

    @patch('api.server._execute_data_update')
    def test_hs300_source(self, mock_exec, client):
        """hs300 源返回有效结构"""
        mock_exec.return_value = {
            'success': True, 'source': 'hs300',
            'total': 300, 'succeeded': 290, 'failed': 10,
            'details': [
                {'symbol': f'{i:06d}', 'error': 'timeout'}
                for i in range(1, 11)
            ]
        }
        rv = client.post('/api/data/update', json={'source': 'hs300', 'days': 30})
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['success'] is True
        assert data['source'] == 'hs300'
        assert data['total'] == 300
        assert len(data['details']) == 10

    @patch('api.server._execute_data_update')
    def test_all_source(self, mock_exec, client):
        """all 源返回有效结构"""
        mock_exec.return_value = {
            'success': True, 'source': 'all',
            'total': 500, 'succeeded': 498, 'failed': 2, 'details': []
        }
        rv = client.post('/api/data/update', json={'source': 'all', 'days': 730})
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['success'] is True
        assert data['source'] == 'all'
        assert 'total' in data

    @patch('api.server._execute_data_update')
    def test_empty_symbols(self, mock_exec, client):
        """源解析到的股票列表为空时仍返回成功"""
        mock_exec.return_value = {
            'success': True, 'source': 'portfolio',
            'total': 0, 'succeeded': 0, 'failed': 0, 'details': []
        }
        rv = client.post('/api/data/update', json={'source': 'portfolio', 'days': 30})
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['success'] is True
        assert data['total'] == 0

    @patch('api.server._execute_data_update')
    def test_force_flag_passed_through(self, mock_exec, client):
        """force 参数被传递到 _execute_data_update"""
        mock_exec.return_value = {
            'success': True, 'source': 'all',
            'total': 500, 'succeeded': 500, 'failed': 0, 'details': []
        }
        rv = client.post('/api/data/update', json={
            'source': 'all', 'days': 30, 'force': True
        })
        assert rv.status_code == 200
        mock_exec.assert_called_once_with('all', 30, True)

    @patch('api.server._execute_data_update')
    def test_force_defaults_to_false(self, mock_exec, client):
        """默认 force=False"""
        mock_exec.return_value = {
            'success': True, 'source': 'all',
            'total': 0, 'succeeded': 0, 'failed': 0, 'details': []
        }
        rv = client.post('/api/data/update', json={'source': 'all', 'days': 60})
        assert rv.status_code == 200
        mock_exec.assert_called_once_with('all', 60, False)

    @patch('api.server._execute_data_update')
    def test_execute_error_returns_500(self, mock_exec, client):
        """执行错误返回 500"""
        mock_exec.side_effect = RuntimeError('Database connection failed')
        rv = client.post('/api/data/update', json={'source': 'all', 'days': 30})
        assert rv.status_code == 500
        data = json.loads(rv.data)
        assert data['success'] is False
        assert 'error' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
