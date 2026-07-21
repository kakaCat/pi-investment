"""
API 服务单元测试
"""
import pytest
import json
from adapters.inbound.api.server import app


@pytest.fixture
def client():
    """创建测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealth:
    """健康检查测试"""

    def test_health_check(self, client):
        rv = client.get('/api/health')
        assert rv.status_code in (200, 500)  # 200 if DB connected, 500 if not
        data = json.loads(rv.data)
        assert 'status' in data


class TestStocks:
    """股票接口测试"""

    def test_search_stocks_empty(self, client):
        rv = client.get('/api/stocks/search')
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert 'error' in data

    def test_search_stocks(self, client):
        rv = client.get('/api/stocks/search?q=平安')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'stocks' in data
        assert 'total' in data

    def test_stock_list(self, client):
        rv = client.get('/api/stocks/list')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'stocks' in data
        assert 'count' in data

    def test_stock_list_with_market(self, client):
        rv = client.get('/api/stocks/list?market=A')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        for s in data['stocks']:
            assert s['market'] == 'A'

    def test_resolve_stock_empty(self, client):
        rv = client.post('/api/stocks/resolve', json={})
        assert rv.status_code == 400

    def test_resolve_stock(self, client):
        rv = client.post('/api/stocks/resolve', json={'code': '999999.SZ'})
        assert rv.status_code == 404

    def test_data_status(self, client):
        rv = client.get('/api/stocks/data-status?symbol=000001.SZ')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'checks' in data


class TestKlines:
    """K线接口测试"""

    def test_get_klines_nonexistent(self, client):
        rv = client.get('/api/stock/999999.SZ/klines')
        assert rv.status_code == 404


class TestFactors:
    """因子接口测试"""

    def test_get_factors(self, client):
        rv = client.get('/api/stock/000001.SZ/factors')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'symbol' in data

    def test_compare_stocks_empty(self, client):
        rv = client.post('/api/stocks/compare', json={})
        assert rv.status_code == 400

    def test_compare_stocks_too_many(self, client):
        rv = client.post('/api/stocks/compare', json={'symbols': ['a', 'b', 'c', 'd', 'e', 'f']})
        assert rv.status_code == 400


class TestSignals:
    """信号接口测试"""

    def test_get_signals(self, client):
        rv = client.get('/api/signals')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'signals' in data
        assert 'count' in data

    def test_get_signals_with_date(self, client):
        rv = client.get('/api/signals?date=2024-01-02')
        assert rv.status_code == 200

    def test_signals_history(self, client):
        rv = client.get('/api/signals/history')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'success' in data

    def test_scan_signals_empty(self, client):
        rv = client.post('/api/signals/scan', json={})
        assert rv.status_code == 400


class TestBacktest:
    """回测接口测试"""

    def test_get_backtest_results(self, client):
        rv = client.get('/api/backtest/results')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'count' in data

    def test_run_backtest_missing_params(self, client):
        rv = client.post('/api/backtest', json={})
        assert rv.status_code == 400

    def test_run_backtest_no_data(self, client):
        rv = client.post('/api/backtest', json={
            'strategy_name': 'test',
            'symbol': '999999.SZ',
            'start_date': '2020-01-01',
            'end_date': '2020-01-31',
            'initial_capital': 100000
        })
        assert rv.status_code == 400

    def test_run_backtest_accepts_rsi_period_from_params_alias(self, client):
        rv = client.post('/api/backtest', json={
            'strategy': 'rsi_reversal',
            'symbol': '999999.SZ',
            'startDate': '2020-01-01',
            'endDate': '2020-01-31',
            'initialCapital': 100000,
            'params': {
                'rsiPeriod': 14
            }
        })
        data = json.loads(rv.data)
        assert rv.status_code == 400
        assert data['error'] != 'RSI策略缺少参数: rsi_period (或 rsiPeriod)'

    def test_run_backtest_passes_selected_period_to_workflow_data(self, client, mocker):
        mock_get_workflow_data = mocker.patch('api.routes.backtest.ds.get_backtest_workflow_data')
        mock_get_workflow_data.return_value = {
            'klines': [
                {'trade_date': f'2024-01-{day:02d} 09:30:00', 'open': 10 + day, 'high': 11 + day, 'low': 9 + day, 'close': 10 + day, 'volume': 1000}
                for day in range(1, 25)
            ]
        }

        rv = client.post('/api/backtest', json={
            'strategy': 'ma_cross',
            'symbol': '000001.SZ',
            'startDate': '2024-01-01',
            'endDate': '2024-01-31',
            'initialCapital': 100000,
            'period': '15min',
            'parameters': {
                'fastPeriod': 5,
                'slowPeriod': 20
            }
        })

        assert rv.status_code == 200
        mock_get_workflow_data.assert_called_once_with(
            '000001.SZ',
            '2024-01-01',
            '2024-01-31',
            period='15min'
        )


class TestRisk:
    """风险接口测试"""

    def test_risk_check_empty(self, client):
        rv = client.post('/api/risk/check', json={})
        assert rv.status_code == 200

    def test_risk_check_with_symbols(self, client):
        rv = client.post('/api/risk/check', json={'symbols': ['999999.SZ']})
        assert rv.status_code == 200


class TestReport:
    """报告接口测试"""

    def test_daily_report(self, client):
        rv = client.get('/api/report/daily')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'risk_summary' in data


class TestExecutions:
    """信号执行接口测试"""

    def test_list_executions(self, client):
        rv = client.get('/api/executions')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'executions' in data
        assert 'count' in data

    def test_list_executions_with_status(self, client):
        rv = client.get('/api/executions?status=pending')
        assert rv.status_code == 200

    def test_execution_stats(self, client):
        rv = client.get('/api/executions/stats')
        assert rv.status_code == 200

    def test_execution_stats_with_dates(self, client):
        rv = client.get('/api/executions/stats?start_date=2024-01-01&end_date=2024-12-31')
        assert rv.status_code == 200

    def test_daily_execution_stats_missing_params(self, client):
        rv = client.get('/api/executions/daily')
        assert rv.status_code == 400

    def test_daily_execution_stats(self, client):
        rv = client.get('/api/executions/daily?start_date=2024-01-01&end_date=2024-01-31')
        assert rv.status_code == 200

    def test_get_execution_not_found(self, client):
        rv = client.get('/api/executions/999999')
        assert rv.status_code == 404

    def test_get_executions_by_signal(self, client):
        rv = client.get('/api/executions/signal/1')
        assert rv.status_code == 200

    def test_pending_executions(self, client):
        rv = client.get('/api/executions/pending')
        assert rv.status_code == 200

    def test_create_execution_empty(self, client):
        rv = client.post('/api/executions', json={})
        assert rv.status_code == 400

    def test_create_execution_invalid(self, client):
        rv = client.post('/api/executions', json={
            'signal_id': 999999,
            'execution_date': '2024-01-15',
            'execution_price': 10.5,
            'quantity': 100,
        })
        assert rv.status_code in (201, 500)

    def test_close_execution_missing_params(self, client):
        rv = client.put('/api/executions/1/close', json={})
        assert rv.status_code == 400

    def test_close_execution_not_found(self, client):
        rv = client.put('/api/executions/999999/close', json={
            'close_date': '2024-06-15',
            'close_price': 35.0,
        })
        assert rv.status_code == 404

    def test_cancel_execution_not_found(self, client):
        rv = client.put('/api/executions/999999/cancel')
        assert rv.status_code == 404

    def test_update_status_missing(self, client):
        rv = client.put('/api/executions/1/status', json={})
        assert rv.status_code == 400

    def test_update_status_invalid(self, client):
        rv = client.put('/api/executions/1/status', json={'status': 'invalid'})
        assert rv.status_code in (400, 404, 500)

    def test_execution_summary(self, client):
        rv = client.get('/api/executions/summary')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'stats' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
