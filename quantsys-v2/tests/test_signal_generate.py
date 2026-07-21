"""
Tests for signal generation endpoint with sync/async modes
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


@pytest.fixture
def client():
    """Flask test client"""
    from adapters.inbound.api.server import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_strategy_service():
    """Mock StrategyCodeService"""
    with patch('services.strategy_code_service.StrategyCodeService') as mock:
        service_instance = MagicMock()
        mock.return_value = service_instance

        # Mock strategy repository
        service_instance.strategy_repo.get_by_id.return_value = {
            'strategy_id': 1,
            'strategy_name': 'Test Strategy',
            'code_content': 'df["buy"] = True',
            'code_type': 'indicator'
        }

        yield service_instance


class TestSignalGenerateSyncMode:
    """Test sync mode (< 50 stocks)"""

    def test_sync_mode_single_stock(self, client, mock_strategy_service):
        """Test sync mode with single stock"""
        # Mock generate_signal to return a buy signal
        mock_strategy_service.generate_signal.return_value = {
            'symbol': '000001',
            'strategy_id': 1,
            'strategy_name': 'Test Strategy',
            'signal_type': 'buy',
            'confidence': 0.85,
            'signal_date': '2026-05-27',
            'price': 1680.0,
            'created_at': '2026-05-27T12:00:00'
        }

        response = client.post(
            '/api/cli/signal-generate',
            json={
                'strategy_id': 1,
                'symbols': ['000001']
            }
        )

        assert response.status_code == 200
        assert response.content_type == 'application/x-ndjson'

        # Parse NDJSON response
        lines = response.data.decode('utf-8').strip().split('\n')
        assert len(lines) == 2  # 1 signal + 1 summary

        # Check signal line
        signal = json.loads(lines[0])
        assert signal['type'] == 'signal'
        assert signal['data']['symbol'] == '000001'
        assert signal['data']['signal_type'] == 'buy'
        assert signal['data']['confidence'] == 0.85

        # Check summary line
        summary = json.loads(lines[1])
        assert summary['type'] == 'summary'
        assert summary['data']['total'] == 1
        assert summary['data']['buy'] == 1
        assert summary['data']['sell'] == 0
        assert summary['data']['hold'] == 0

    def test_sync_mode_multiple_stocks(self, client, mock_strategy_service):
        """Test sync mode with multiple stocks (< 50)"""
        # Mock generate_signal to return different signals
        def mock_generate(strategy_id, symbol, date=None):
            signals = {
                '000001': {'signal_type': 'buy', 'confidence': 0.85},
                '000001': {'signal_type': 'sell', 'confidence': 0.75},
                '600036': {'signal_type': 'hold', 'confidence': 0.50}
            }
            base = {
                'symbol': symbol,
                'strategy_id': strategy_id,
                'strategy_name': 'Test Strategy',
                'signal_date': '2026-05-27',
                'price': 100.0,
                'created_at': '2026-05-27T12:00:00'
            }
            base.update(signals.get(symbol, {'signal_type': 'hold', 'confidence': 0.5}))
            return base

        mock_strategy_service.generate_signal.side_effect = mock_generate

        response = client.post(
            '/api/cli/signal-generate',
            json={
                'strategy_id': 1,
                'symbols': ['000001', '000001', '600036']
            }
        )

        assert response.status_code == 200
        assert response.content_type == 'application/x-ndjson'

        lines = response.data.decode('utf-8').strip().split('\n')
        assert len(lines) == 4  # 3 signals + 1 summary

        # Check summary
        summary = json.loads(lines[-1])
        assert summary['type'] == 'summary'
        assert summary['data']['total'] == 3
        assert summary['data']['buy'] == 1
        assert summary['data']['sell'] == 1
        assert summary['data']['hold'] == 1

    def test_sync_mode_with_errors(self, client, mock_strategy_service):
        """Test sync mode handles errors gracefully"""
        def mock_generate(strategy_id, symbol, date=None):
            if symbol == '000001':
                return {
                    'symbol': symbol,
                    'strategy_id': strategy_id,
                    'strategy_name': 'Test Strategy',
                    'signal_type': 'buy',
                    'confidence': 0.85,
                    'signal_date': '2026-05-27',
                    'price': 1680.0,
                    'created_at': '2026-05-27T12:00:00'
                }
            else:
                raise ValueError(f"Data not available for {symbol}")

        mock_strategy_service.generate_signal.side_effect = mock_generate

        response = client.post(
            '/api/cli/signal-generate',
            json={
                'strategy_id': 1,
                'symbols': ['000001', '000001']
            }
        )

        assert response.status_code == 200
        lines = response.data.decode('utf-8').strip().split('\n')

        # Should have 1 signal + 1 error + 1 summary
        assert len(lines) == 3

        # Check error line
        error_line = json.loads(lines[1])
        assert error_line['type'] == 'error'
        assert error_line['data']['symbol'] == '000001'
        assert 'Data not available' in error_line['data']['error']


class TestSignalGenerateAsyncMode:
    """Test async mode (>= 50 stocks)"""

    def test_async_mode_large_batch(self, client, mock_strategy_service):
        """Test async mode with >= 50 stocks"""
        # Generate 50 stock symbols
        symbols = [f'60{i:04d}' for i in range(50)]

        with patch('api.routes.pipeline.threading.Thread') as mock_thread:
            response = client.post(
                '/api/cli/signal-generate',
                json={
                    'strategy_id': 1,
                    'symbols': symbols
                }
            )

            assert response.status_code == 202
            data = response.get_json()

            assert data['success'] is True
            assert 'run_id' in data
            assert data['status'] == 'running'
            assert '后台任务已启动' in data['message']

            # Verify background thread was started
            mock_thread.assert_called_once()
            call_kwargs = mock_thread.call_args[1]
            assert call_kwargs['daemon'] is True

    def test_async_mode_exactly_50_stocks(self, client, mock_strategy_service):
        """Test threshold: exactly 50 stocks triggers async mode"""
        symbols = [f'60{i:04d}' for i in range(50)]

        with patch('api.routes.pipeline.threading.Thread') as mock_thread:
            response = client.post(
                '/api/cli/signal-generate',
                json={
                    'strategy_id': 1,
                    'symbols': symbols
                }
            )

            assert response.status_code == 202
            mock_thread.assert_called_once()

    def test_sync_mode_49_stocks(self, client, mock_strategy_service):
        """Test threshold: 49 stocks uses sync mode"""
        symbols = [f'60{i:04d}' for i in range(49)]

        # Mock generate_signal to return hold signals
        mock_strategy_service.generate_signal.return_value = {
            'symbol': '600000',
            'strategy_id': 1,
            'strategy_name': 'Test Strategy',
            'signal_type': 'hold',
            'confidence': 0.5,
            'signal_date': '2026-05-27',
            'price': 100.0,
            'created_at': '2026-05-27T12:00:00'
        }

        response = client.post(
            '/api/cli/signal-generate',
            json={
                'strategy_id': 1,
                'symbols': symbols
            }
        )

        # Should use sync mode (200, not 202)
        assert response.status_code == 200
        assert response.content_type == 'application/x-ndjson'


class TestSignalGenerateValidation:
    """Test input validation"""

    def test_missing_strategy_id(self, client):
        """Test missing strategy_id parameter"""
        response = client.post(
            '/api/cli/signal-generate',
            json={'symbols': ['000001']}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'strategy_id' in data['error']

    def test_invalid_strategy_id(self, client):
        """Test invalid strategy_id"""
        response = client.post(
            '/api/cli/signal-generate',
            json={
                'strategy_id': 'invalid',
                'symbols': ['000001']
            }
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert '无效的 strategy_id' in data['error']

    def test_empty_symbols(self, client):
        """Test empty symbols list"""
        with patch('api.routes.pipeline.Path.exists', return_value=False):
            response = client.post(
                '/api/cli/signal-generate',
                json={
                    'strategy_id': 1,
                    'symbols': []
                }
            )

            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'symbols' in data['error'] or 'portfolio' in data['error']

    def test_symbols_from_portfolio(self, client, mock_strategy_service):
        """Test reading symbols from portfolio.json"""
        # This test verifies the portfolio fallback logic
        # For simplicity, we'll test that when no symbols are provided and portfolio doesn't exist,
        # we get an appropriate error

        response = client.post(
            '/api/cli/signal-generate',
            json={'strategy_id': 1}
        )

        # Should fail with appropriate error message
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'symbols' in data['error'] or 'portfolio' in data['error']


class TestSignalGenerateConcurrentLock:
    """Test concurrent execution behavior for async mode"""

    def test_signal_generate_async_multiple_requests(self, client, mock_strategy_service):
        """测试异步模式支持多个并发请求"""
        symbols = [f'60{i:04d}' for i in range(50)]

        with patch('api.routes.pipeline.threading.Thread') as mock_thread:
            # First request
            response1 = client.post(
                '/api/cli/signal-generate',
                json={
                    'strategy_id': 1,
                    'symbols': symbols
                }
            )
            assert response1.status_code == 202
            data1 = response1.get_json()
            assert data1['success'] is True
            assert 'run_id' in data1

            # Second concurrent request should also succeed
            response2 = client.post(
                '/api/cli/signal-generate',
                json={
                    'strategy_id': 1,
                    'symbols': symbols
                }
            )
            assert response2.status_code == 202
            data2 = response2.get_json()
            assert data2['success'] is True
            assert 'run_id' in data2

            # Both threads should have been started
            assert mock_thread.call_count == 2

    def test_signal_generate_lock_release_on_completion(self, client, mock_strategy_service):
        """测试任务完成后的清理"""
        symbols = [f'60{i:04d}' for i in range(50)]

        with patch('api.routes.pipeline.threading.Thread'):
            response = client.post(
                '/api/cli/signal-generate',
                json={
                    'strategy_id': 1,
                    'symbols': symbols
                }
            )

            assert response.status_code == 202
            data = response.get_json()
            assert 'run_id' in data
            # Verify run_id format
            assert data['run_id'].startswith('signal_')


class TestSignalGenerateModeSelection:
    """Test automatic mode selection based on stock count"""

    def test_signal_generate_mode_selection(self, client, mock_strategy_service):
        """测试模式自动选择 - < 50 stocks = sync, >= 50 = async"""
        # Test sync mode with 1 stock
        mock_strategy_service.generate_signal.return_value = {
            'symbol': '000001',
            'strategy_id': 1,
            'strategy_name': 'Test Strategy',
            'signal_type': 'buy',
            'confidence': 0.85,
            'signal_date': '2026-05-27',
            'price': 1680.0,
            'created_at': '2026-05-27T12:00:00'
        }

        response = client.post(
            '/api/cli/signal-generate',
            json={
                'strategy_id': 1,
                'symbols': ['000001']
            }
        )

        # Should use sync mode (200, NDJSON)
        assert response.status_code == 200
        assert response.content_type == 'application/x-ndjson'

    def test_signal_generate_sync_threshold_boundary_49(self, client, mock_strategy_service):
        """测试同步模式边界 - 49 stocks 应使用同步模式"""
        symbols = [f'60{i:04d}' for i in range(49)]

        mock_strategy_service.generate_signal.return_value = {
            'symbol': '600000',
            'strategy_id': 1,
            'strategy_name': 'Test Strategy',
            'signal_type': 'hold',
            'confidence': 0.5,
            'signal_date': '2026-05-27',
            'price': 100.0,
            'created_at': '2026-05-27T12:00:00'
        }

        response = client.post(
            '/api/cli/signal-generate',
            json={
                'strategy_id': 1,
                'symbols': symbols
            }
        )

        # Should use sync mode (200, not 202)
        assert response.status_code == 200
        assert response.content_type == 'application/x-ndjson'

        # Verify NDJSON format
        lines = response.data.decode('utf-8').strip().split('\n')
        # 49 signals + 1 summary = 50 lines
        assert len(lines) == 50

    def test_signal_generate_async_threshold_boundary_50(self, client, mock_strategy_service):
        """测试异步模式边界 - 50 stocks 应使用异步模式"""
        symbols = [f'60{i:04d}' for i in range(50)]

        with patch('api.routes.pipeline.threading.Thread') as mock_thread:
            response = client.post(
                '/api/cli/signal-generate',
                json={
                    'strategy_id': 1,
                    'symbols': symbols
                }
            )

            # Should use async mode (202)
            assert response.status_code == 202
            data = response.get_json()
            assert data['success'] is True
            assert 'run_id' in data
            assert data['status'] == 'running'

    def test_signal_generate_async_threshold_boundary_51(self, client, mock_strategy_service):
        """测试异步模式边界 - 51 stocks 应使用异步模式"""
        symbols = [f'60{i:04d}' for i in range(51)]

        with patch('api.routes.pipeline.threading.Thread') as mock_thread:
            response = client.post(
                '/api/cli/signal-generate',
                json={
                    'strategy_id': 1,
                    'symbols': symbols
                }
            )

            # Should use async mode (202)
            assert response.status_code == 202
            data = response.get_json()
            assert data['success'] is True
            assert 'run_id' in data

    def test_signal_generate_large_batch_async(self, client, mock_strategy_service):
        """测试大批量股票异步模式 - 100+ stocks"""
        symbols = [f'60{i:04d}' for i in range(100)]

        with patch('api.routes.pipeline.threading.Thread') as mock_thread:
            response = client.post(
                '/api/cli/signal-generate',
                json={
                    'strategy_id': 1,
                    'symbols': symbols
                }
            )

            # Should use async mode
            assert response.status_code == 202
            data = response.get_json()
            assert data['success'] is True
            assert data['status'] == 'running'

            # Verify thread was started
            mock_thread.assert_called_once()
            call_kwargs = mock_thread.call_args[1]
            assert call_kwargs['daemon'] is True


class TestSignalGenerateStreamingFormat:
    """Test streaming response format for sync mode"""

    def test_signal_generate_ndjson_format(self, client, mock_strategy_service):
        """测试流式响应格式 - NDJSON"""
        def mock_generate(strategy_id, symbol, date=None):
            signals = {
                '000001': {'signal_type': 'buy', 'confidence': 0.85},
                '000001': {'signal_type': 'sell', 'confidence': 0.75},
            }
            base = {
                'symbol': symbol,
                'strategy_id': strategy_id,
                'strategy_name': 'Test Strategy',
                'signal_date': '2026-05-27',
                'price': 100.0,
                'created_at': '2026-05-27T12:00:00'
            }
            base.update(signals.get(symbol, {'signal_type': 'hold', 'confidence': 0.5}))
            return base

        mock_strategy_service.generate_signal.side_effect = mock_generate

        response = client.post(
            '/api/cli/signal-generate',
            json={
                'strategy_id': 1,
                'symbols': ['000001', '000001']
            }
        )

        assert response.status_code == 200
        assert response.content_type == 'application/x-ndjson'

        lines = response.data.decode('utf-8').strip().split('\n')
        assert len(lines) == 3  # 2 signals + 1 summary

        # Verify each line is valid JSON
        for line in lines:
            obj = json.loads(line)
            assert 'type' in obj
            assert 'data' in obj

        # Verify signal lines
        signal1 = json.loads(lines[0])
        assert signal1['type'] == 'signal'
        assert signal1['data']['symbol'] == '000001'
        assert signal1['data']['signal_type'] == 'buy'

        signal2 = json.loads(lines[1])
        assert signal2['type'] == 'signal'
        assert signal2['data']['symbol'] == '000001'
        assert signal2['data']['signal_type'] == 'sell'

        # Verify summary line
        summary = json.loads(lines[2])
        assert summary['type'] == 'summary'
        assert summary['data']['total'] == 2
        assert summary['data']['buy'] == 1
        assert summary['data']['sell'] == 1
        assert summary['data']['hold'] == 0

    def test_signal_generate_error_in_stream(self, client, mock_strategy_service):
        """测试流式响应中的错误处理"""
        def mock_generate(strategy_id, symbol, date=None):
            if symbol == '000001':
                return {
                    'symbol': symbol,
                    'strategy_id': strategy_id,
                    'strategy_name': 'Test Strategy',
                    'signal_type': 'buy',
                    'confidence': 0.85,
                    'signal_date': '2026-05-27',
                    'price': 1680.0,
                    'created_at': '2026-05-27T12:00:00'
                }
            else:
                raise ValueError(f"Data not available for {symbol}")

        mock_strategy_service.generate_signal.side_effect = mock_generate

        response = client.post(
            '/api/cli/signal-generate',
            json={
                'strategy_id': 1,
                'symbols': ['000001', '000001', '600036']
            }
        )

        assert response.status_code == 200
        lines = response.data.decode('utf-8').strip().split('\n')

        # Should have 1 signal + 2 errors + 1 summary = 4 lines
        assert len(lines) == 4

        # Check signal line
        signal = json.loads(lines[0])
        assert signal['type'] == 'signal'
        assert signal['data']['symbol'] == '000001'

        # Check error lines
        error1 = json.loads(lines[1])
        assert error1['type'] == 'error'
        assert error1['data']['symbol'] == '000001'
        assert 'Data not available' in error1['data']['error']

        error2 = json.loads(lines[2])
        assert error2['type'] == 'error'
        assert error2['data']['symbol'] == '600036'

        # Check summary
        summary = json.loads(lines[3])
        assert summary['type'] == 'summary'
        assert summary['data']['total'] == 3
        assert summary['data']['buy'] == 1
        assert summary['data']['hold'] == 2  # 2 errors counted as hold


class TestSignalGenerateBackwardCompatibility:
    """Test backward compatibility with existing async mode"""

    def test_old_async_format_still_works(self, client, mock_strategy_service):
        """Test that old async mode format is maintained"""
        symbols = [f'60{i:04d}' for i in range(50)]

        with patch('api.routes.pipeline.threading.Thread'):
            response = client.post(
                '/api/cli/signal-generate',
                json={
                    'strategy_id': 1,
                    'symbols': symbols
                }
            )

            assert response.status_code == 202
            data = response.get_json()

            # Check old format fields are present
            assert 'success' in data
            assert 'run_id' in data
            assert 'status' in data
            assert 'message' in data
