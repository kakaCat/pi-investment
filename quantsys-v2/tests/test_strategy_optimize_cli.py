"""
测试 strategy.optimize CLI 命令（v2 重写）

RED 阶段：编写失败的测试
"""
import pytest
from unittest.mock import patch, MagicMock
from adapters.inbound.cli.commands.strategy_commands import StrategyOptimizeCommand
from adapters.inbound.cli.command_base import CommandResult


class TestStrategyOptimizeCommandV2:
    """测试 strategy.optimize 命令（v2 API）"""

    def test_optimize_with_strategy_id_calls_v2_api(self):
        """测试使用 strategy_id 调用 v2 API"""
        # RED: 这个测试应该失败，因为当前实现调用的是 v1
        cmd = StrategyOptimizeCommand()

        with patch('cli.http_client.HTTPClient') as mock_client:
            mock_response = {
                'success': True,
                'data': {
                    'strategy_id': 1,
                    'symbol': '000001.SH',
                    'metric': 'sharpe',
                    'total_combinations': 4,
                    'successful': 4,
                    'best': {
                        'params': {'rsi_low': 30, 'rsi_high': 70},
                        'score': 2.15,
                        'sharpe_ratio': 2.15
                    }
                }
            }
            mock_client.return_value.post.return_value = mock_response

            result = cmd.execute(
                strategy_id=1,
                symbol='000001.SH',
                start_date='2025-01-01',
                end_date='2025-12-31',
                metric='sharpe',
                param_grid='{"rsi_low": [25, 30], "rsi_high": [70, 75]}'
            )

            assert result.success is True
            assert result.data['best']['score'] == 2.15
            # 验证调用了 v2 API
            mock_client.return_value.post.assert_called_once()
            call_args = mock_client.return_value.post.call_args
            assert '/api/portfolio/strategy-optimize' in call_args[0][0]

    def test_optimize_validates_required_params(self):
        """测试参数验证"""
        cmd = StrategyOptimizeCommand()

        # 缺少 strategy_id
        error = cmd.validate_params(
            symbol='000001.SH',
            param_grid='{"rsi_low": [30]}'
        )
        assert error is not None
        assert 'strategy_id' in error.lower()

        # 缺少 symbol
        error = cmd.validate_params(
            strategy_id=1,
            param_grid='{"rsi_low": [30]}'
        )
        assert error is not None
        assert 'symbol' in error.lower()

        # 缺少 param_grid
        error = cmd.validate_params(
            strategy_id=1,
            symbol='000001.SH'
        )
        assert error is not None
        assert 'param_grid' in error.lower()

    def test_optimize_parses_param_grid_json(self):
        """测试 param_grid JSON 解析"""
        cmd = StrategyOptimizeCommand()

        with patch('cli.http_client.HTTPClient') as mock_client:
            mock_client.return_value.post.return_value = {
                'success': True,
                'data': {'best': {'params': {}}}
            }

            result = cmd.execute(
                strategy_id=1,
                symbol='000001.SH',
                start_date='2025-01-01',
                end_date='2025-12-31',
                param_grid='{"rsi_low": [25, 30], "rsi_high": [70, 75]}'
            )

            # 验证 JSON 被正确解析并传递给 API
            call_args = mock_client.return_value.post.call_args
            payload = call_args[1]['json']
            assert 'param_grid' in payload
            assert payload['param_grid'] == {'rsi_low': [25, 30], 'rsi_high': [70, 75]}

    def test_optimize_handles_invalid_json(self):
        """测试处理无效的 JSON"""
        cmd = StrategyOptimizeCommand()

        result = cmd.execute(
            strategy_id=1,
            symbol='000001.SH',
            param_grid='invalid json'
        )

        assert result.success is False
        assert 'json' in result.error.lower()

    def test_optimize_supports_optional_params(self):
        """测试支持可选参数"""
        cmd = StrategyOptimizeCommand()

        with patch('cli.http_client.HTTPClient') as mock_client:
            mock_client.return_value.post.return_value = {
                'success': True,
                'data': {'best': {'params': {}}}
            }

            result = cmd.execute(
                strategy_id=1,
                symbol='000001.SH',
                start_date='2025-01-01',
                end_date='2025-12-31',
                metric='win_rate',
                initial_capital=2000000,
                max_combinations=100,
                param_grid='{"rsi_low": [30]}'
            )

            call_args = mock_client.return_value.post.call_args
            payload = call_args[1]['json']
            assert payload['metric'] == 'win_rate'
            assert payload['initial_capital'] == 2000000
            assert payload['max_combinations'] == 100

    def test_optimize_handles_api_error(self):
        """测试处理 API 错误"""
        cmd = StrategyOptimizeCommand()

        with patch('cli.http_client.HTTPClient') as mock_client:
            mock_client.return_value.post.return_value = {
                'success': False,
                'error': '参数组合过多'
            }

            result = cmd.execute(
                strategy_id=1,
                symbol='000001.SH',
                param_grid='{"p1": [1,2,3,4,5], "p2": [1,2,3,4,5]}'
            )

            assert result.success is False
            assert '参数组合过多' in result.error
