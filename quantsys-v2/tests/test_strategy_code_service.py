"""
Tests for StrategyCodeService
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from application.services.strategy_code_service import StrategyCodeService


class TestBacktestStrategyWithParamsOverride:
    """Test backtest_strategy with params_override"""

    @pytest.fixture
    def service(self):
        """Create StrategyCodeService instance"""
        from unittest.mock import Mock
        mock_strategy_repo = Mock()
        mock_kline_repo = Mock()
        return StrategyCodeService(
            strategy_repo=mock_strategy_repo,
            kline_repo=mock_kline_repo
        )

    @pytest.fixture
    def sample_strategy(self):
        """Sample strategy for testing"""
        return {
            'id': 1,
            'strategy_name': 'Test Strategy',
            'code_type': 'indicator',
            'code_content': '''
# Simple RSI strategy
df['rsi'] = ta.rsi(df['close'], length=14)
df['buy'] = df['rsi'] < 30
df['sell'] = df['rsi'] > 70
''',
            'parsed_params': [
                {'name': 'rsi_low', 'value': 30, 'type': 'int'},
                {'name': 'rsi_high', 'value': 70, 'type': 'int'}
            ],
            'validation_status': 'valid',
            'is_active': True
        }

    @pytest.fixture
    def sample_klines(self):
        """样本 K 线（**程序化生成 30 条**）。

        2026-10-02（REQ-261001145152-3982 审查）：原为硬编码的 15 条，而服务侧要求
        ≥20 条（实测报 `K线数据不足，至少需要20条，实际15条`）→ 3 条用例失败。
        生成 30 条既满足下限，也不再因"写死几条"而随实现门槛变化而碎。
        """
        return [
            {
                'trade_date': f'2025-01-{i + 1:02d}',
                'open': 100.0 + i,
                'high': 105.0 + i,
                'low': 95.0 + i,
                'close': 102.0 + i,
                'volume': 1_000_000 + i * 10_000,
            }
            for i in range(30)
        ]
    def test_backtest_strategy_with_params_override(self, service, sample_strategy, sample_klines):
        """Test backtest_strategy with params_override parameter"""
        # Mock the repository and executor
        with patch.object(service.strategy_repo, 'get_by_id') as mock_get_strategy, \
             patch.object(service, 'validate_code') as mock_validate, \
             patch.object(service, '_get_klines') as mock_get_klines, \
             patch.object(service, '_inject_fund_flow') as mock_inject_fund, \
             patch.object(service, '_inject_financial') as mock_inject_financial, \
             patch.object(service, '_inject_technical_indicators') as mock_inject_tech, \
             patch.object(service, '_backtest_indicator_strategy') as mock_backtest_indicator, \
             patch.object(service.strategy_repo, 'update_last_executed'):

            # Setup mocks
            mock_get_strategy.return_value = sample_strategy
            mock_validate.return_value = {'valid': True}
            mock_get_klines.return_value = sample_klines
            mock_inject_fund.return_value = sample_klines
            mock_inject_financial.return_value = sample_klines
            mock_inject_tech.return_value = sample_klines

            # Mock backtest result
            mock_backtest_result = {
                'total_return': 0.15,
                'sharpe_ratio': 1.8,
                'max_drawdown': -0.12,
                'win_rate': 0.65,
                'total_trades': 45,
                'trades': [],
                'equity_curve': []
            }
            mock_backtest_indicator.return_value = mock_backtest_result

            # Call backtest_strategy with params_override
            params_override = {'rsi_low': 25, 'rsi_high': 75}
            result = service.backtest_strategy(
                strategy_id=1,
                symbol='000001',
                start_date='2025-01-01',
                end_date='2025-01-15',
                initial_cash=1000000,
                params_override=params_override
            )

            # Verify the result
            assert result is not None
            assert 'total_return' in result
            assert 'sharpe_ratio' in result
            assert result['total_return'] == 0.15
            assert result['sharpe_ratio'] == 1.8

            # Verify that _backtest_indicator_strategy was called with params_override
            mock_backtest_indicator.assert_called_once()
            call_args = mock_backtest_indicator.call_args
            assert call_args[1]['params_override'] == params_override

    def test_run_strategy_passes_selected_period_to_kline_fetch(self, service, sample_strategy, sample_klines):
        """Realtime indicator preview should use the selected kline period."""
        with patch.object(service.strategy_repo, 'get_by_id') as mock_get_strategy, \
             patch.object(service, 'validate_code') as mock_validate, \
             patch.object(service, '_get_klines') as mock_get_klines, \
             patch.object(service, '_inject_fund_flow') as mock_inject_fund, \
             patch.object(service, '_inject_financial') as mock_inject_financial, \
             patch.object(service, '_inject_technical_indicators') as mock_inject_tech, \
             patch.object(service.indicator_executor, 'execute') as mock_execute, \
             patch.object(service.strategy_repo, 'update_last_executed'):

            mock_get_strategy.return_value = sample_strategy
            mock_validate.return_value = {'valid': True}
            mock_get_klines.return_value = sample_klines
            mock_inject_fund.return_value = sample_klines
            mock_inject_financial.return_value = sample_klines
            mock_inject_tech.return_value = sample_klines

            signals = pd.DataFrame(sample_klines)
            signals['buy'] = False
            signals['sell'] = False
            mock_execute.return_value = MagicMock(signals=signals)

            service.run_strategy(
                strategy_id=1,
                symbol='000001',
                limit=260,
                chart_limit=260,
                period='30min'
            )

            mock_get_klines.assert_called_once_with(
                symbol='000001',
                limit=260,
                period='30min'
            )

    def test_backtest_strategy_without_params_override(self, service, sample_strategy, sample_klines):
        """Test backtest_strategy without params_override (uses default params)"""
        with patch.object(service.strategy_repo, 'get_by_id') as mock_get_strategy, \
             patch.object(service, 'validate_code') as mock_validate, \
             patch.object(service, '_get_klines') as mock_get_klines, \
             patch.object(service, '_inject_fund_flow') as mock_inject_fund, \
             patch.object(service, '_inject_financial') as mock_inject_financial, \
             patch.object(service, '_inject_technical_indicators') as mock_inject_tech, \
             patch.object(service, '_backtest_indicator_strategy') as mock_backtest_indicator, \
             patch.object(service.strategy_repo, 'update_last_executed'):

            # Setup mocks
            mock_get_strategy.return_value = sample_strategy
            mock_validate.return_value = {'valid': True}
            mock_get_klines.return_value = sample_klines
            mock_inject_fund.return_value = sample_klines
            mock_inject_financial.return_value = sample_klines
            mock_inject_tech.return_value = sample_klines

            # Mock backtest result
            mock_backtest_result = {
                'total_return': 0.10,
                'sharpe_ratio': 1.5,
                'max_drawdown': -0.15,
                'win_rate': 0.60,
                'total_trades': 40,
                'trades': [],
                'equity_curve': []
            }
            mock_backtest_indicator.return_value = mock_backtest_result

            # Call backtest_strategy without params_override
            result = service.backtest_strategy(
                strategy_id=1,
                symbol='000001',
                start_date='2025-01-01',
                end_date='2025-01-15',
                initial_cash=1000000
            )

            # Verify the result
            assert result is not None
            assert result['total_return'] == 0.10

            # Verify that _backtest_indicator_strategy was called with None params_override
            mock_backtest_indicator.assert_called_once()
            call_args = mock_backtest_indicator.call_args
            assert call_args[1]['params_override'] is None

    def test_backtest_script_strategy_with_params_override(self, service, sample_klines):
        """Test backtest_strategy with script strategy type and params_override"""
        script_strategy = {
            'id': 2,
            'strategy_name': 'Script Strategy',
            'code_type': 'script',
            'code_content': '''
def on_init(ctx):
    ctx.params = {'stop_loss': 0.02, 'take_profit': 0.05}

def on_bar(ctx, bar):
    pass
''',
            'parsed_params': [
                {'name': 'stop_loss', 'value': 0.02, 'type': 'float'},
                {'name': 'take_profit', 'value': 0.05, 'type': 'float'}
            ],
            'validation_status': 'valid',
            'is_active': True
        }

        with patch.object(service.strategy_repo, 'get_by_id') as mock_get_strategy, \
             patch.object(service, 'validate_code') as mock_validate, \
             patch.object(service, '_get_klines') as mock_get_klines, \
             patch.object(service, '_inject_fund_flow') as mock_inject_fund, \
             patch.object(service, '_inject_financial') as mock_inject_financial, \
             patch.object(service, '_inject_technical_indicators') as mock_inject_tech, \
             patch.object(service, '_backtest_script_strategy') as mock_backtest_script, \
             patch.object(service.strategy_repo, 'update_last_executed'):

            # Setup mocks
            mock_get_strategy.return_value = script_strategy
            mock_validate.return_value = {'valid': True}
            mock_get_klines.return_value = sample_klines
            mock_inject_fund.return_value = sample_klines
            mock_inject_financial.return_value = sample_klines
            mock_inject_tech.return_value = sample_klines

            # Mock backtest result
            mock_backtest_result = {
                'total_return': 0.20,
                'sharpe_ratio': 2.0,
                'max_drawdown': -0.10,
                'win_rate': 0.70,
                'total_trades': 50,
                'trades': [],
                'equity_curve': []
            }
            mock_backtest_script.return_value = mock_backtest_result

            # Call backtest_strategy with params_override
            params_override = {'stop_loss': 0.03, 'take_profit': 0.08}
            result = service.backtest_strategy(
                strategy_id=2,
                symbol='000001',
                start_date='2025-01-01',
                end_date='2025-01-15',
                initial_cash=1000000,
                params_override=params_override
            )

            # Verify the result
            assert result is not None
            assert result['total_return'] == 0.20

            # Verify that _backtest_script_strategy was called with params_override
            mock_backtest_script.assert_called_once()
            call_args = mock_backtest_script.call_args
            assert call_args[1]['params_override'] == params_override

    def test_generate_signal(self, service, sample_strategy):
        """测试信号生成"""
        # Create extended klines with at least 20 records
        extended_klines = []
        for i in range(25):
            extended_klines.append({
                'trade_date': f'2025-01-{i+1:02d}' if i < 31 else f'2025-02-{i-30:02d}',
                'open': 100.0 + i,
                'high': 105.0 + i,
                'low': 95.0 + i,
                'close': 102.0 + i,
                'volume': 1000000 + i * 100000
            })

        with patch.object(service.strategy_repo, 'get_by_id') as mock_get_strategy, \
             patch.object(service, '_get_klines') as mock_get_klines, \
             patch.object(service, '_inject_fund_flow') as mock_inject_fund, \
             patch.object(service, '_inject_financial') as mock_inject_financial, \
             patch.object(service, '_inject_technical_indicators') as mock_inject_tech, \
             patch.object(service.indicator_executor, 'execute') as mock_execute:

            # Setup mocks
            mock_get_strategy.return_value = sample_strategy
            mock_get_klines.return_value = extended_klines
            mock_inject_fund.return_value = extended_klines
            mock_inject_financial.return_value = extended_klines
            mock_inject_tech.return_value = extended_klines

            # Mock executor result with signals
            df = pd.DataFrame(extended_klines)
            df['buy'] = [False] * (len(df) - 1) + [True]
            df['sell'] = [False] * len(df)
            df['confidence'] = [0.0] * (len(df) - 1) + [0.85]

            mock_result = MagicMock()
            mock_result.signals = df
            mock_execute.return_value = mock_result

            # Call generate_signal
            signal = service.generate_signal(
                strategy_id=sample_strategy['id'],
                symbol='000001',
                date='2025-01-15'
            )

            # Verify the signal
            assert signal is not None
            assert signal['symbol'] == '000001'
            assert signal['strategy_id'] == sample_strategy['id']
            assert signal['signal_type'] == 'buy'
            assert signal['confidence'] == 0.85
            assert 'signal_date' in signal
            assert 'price' in signal
            assert 'created_at' in signal
