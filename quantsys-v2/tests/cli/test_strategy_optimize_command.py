"""
测试 strategy.optimize CLI 命令
"""
import pytest
import json
from unittest.mock import Mock, patch
from adapters.inbound.cli.commands.strategy_commands import StrategyOptimizeCommand


class TestStrategyOptimizeCommand:
    """测试策略优化 CLI 命令"""

    def test_validate_params_requires_strategy_id(self):
        """测试验证需要策略ID"""
        cmd = StrategyOptimizeCommand()
        error = cmd.validate_params(symbol='000001.SH', param_ranges='{}')
        assert error is not None
        assert 'strategy_id' in error.lower() or '策略' in error

    def test_validate_params_requires_symbol(self):
        """测试验证需要股票代码"""
        cmd = StrategyOptimizeCommand()
        error = cmd.validate_params(strategy_id=1, param_ranges='{}')
        assert error is not None
        assert 'symbol' in error.lower() or '股票' in error

    def test_validate_params_requires_param_ranges(self):
        """测试验证需要参数范围"""
        cmd = StrategyOptimizeCommand()
        error = cmd.validate_params(strategy_id=1, symbol='000001.SH')
        assert error is not None
        assert 'param' in error.lower() or '参数' in error

    def test_validate_params_success(self):
        """测试验证成功"""
        cmd = StrategyOptimizeCommand()
        error = cmd.validate_params(
            strategy_id=1,
            symbol='000001.SH',
            param_ranges='{"fast": [5, 10]}'
        )
        assert error is None

    @patch('cli.http_client.HTTPClient')
    def test_execute_calls_correct_api_endpoint(self, mock_client_class):
        """测试执行调用正确的 API 端点"""
        mock_client = Mock()
        mock_client.post.return_value = {
            'success': True,
            'results': [
                {'params': {'fast': 10}, 'sharpeRatio': 2.0}
            ]
        }
        mock_client_class.return_value = mock_client

        cmd = StrategyOptimizeCommand()
        result = cmd.execute(
            strategy_id=1,
            symbol='000001.SH',
            start_date='2024-01-01',
            end_date='2024-12-31',
            param_ranges='{"fast": [5, 10, 20]}'
        )

        assert result.success is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == '/api/strategies/optimize'

    @patch('cli.http_client.HTTPClient')
    def test_execute_sends_correct_payload(self, mock_client_class):
        """测试执行发送正确的请求体"""
        mock_client = Mock()
        mock_client.post.return_value = {'success': True, 'results': []}
        mock_client_class.return_value = mock_client

        cmd = StrategyOptimizeCommand()
        cmd.execute(
            strategy_id=1,
            symbol='000001.SH',
            start_date='2024-01-01',
            end_date='2024-12-31',
            param_ranges='{"fast": [5, 10], "slow": [20, 30]}'
        )

        call_args = mock_client.post.call_args
        payload = call_args[1]['json']

        assert payload['strategyId'] == 1
        assert payload['symbol'] == '000001.SH'
        assert payload['startDate'] == '2024-01-01'
        assert payload['endDate'] == '2024-12-31'
        assert payload['paramRanges'] == {'fast': [5, 10], 'slow': [20, 30]}

    @patch('cli.http_client.HTTPClient')
    def test_execute_handles_invalid_json(self, mock_client_class):
        """测试执行处理无效 JSON"""
        cmd = StrategyOptimizeCommand()
        result = cmd.execute(
            strategy_id=1,
            symbol='000001.SH',
            param_ranges='invalid json'
        )

        assert result.success is False
        assert 'json' in result.error.lower() or '格式' in result.error

    @patch('cli.http_client.HTTPClient')
    def test_execute_handles_api_error(self, mock_client_class):
        """测试执行处理 API 错误"""
        mock_client = Mock()
        mock_client.post.return_value = {
            'success': False,
            'error': '策略不存在'
        }
        mock_client_class.return_value = mock_client

        cmd = StrategyOptimizeCommand()
        result = cmd.execute(
            strategy_id=999,
            symbol='000001.SH',
            param_ranges='{"fast": [5, 10]}'
        )

        assert result.success is False
        assert '策略不存在' in result.error
