"""
StrategyRunner mock-based unit tests.

Tests StrategyRunner with mocked StrategyRepository and strategy classes
to achieve full coverage without a database connection.
"""
import pytest
import json
from unittest.mock import MagicMock, patch, PropertyMock

from domain.quantlib.engine.strategy_runner import StrategyRunner, STRATEGY_REGISTRY


# ==================== Helpers ====================

def _make_klines(closes):
    """Create synthetic kline dicts from a list of close prices."""
    klines = []
    for i, close in enumerate(closes):
        klines.append({
            'trade_date': f'2024-01-{i+1:02d}',
            'symbol': 'TEST01',
            'open': close,
            'high': close * 1.01,
            'low': close * 0.99,
            'close': close,
            'volume': 1000000.0,
        })
    return klines


def _make_config(**overrides):
    """Create a mock strategy config dict."""
    defaults = {
        'id': 1,
        'name': 'test_strategy',
        'strategy_type': 'ma_cross',
        'description': 'test',
        'parameters': {'ma_short': 5, 'ma_long': 20},
        'is_active': True,
    }
    defaults.update(overrides)
    return defaults


# ==================== _get_strategy_instance Tests ====================

class TestGetStrategyInstance:
    """Tests for StrategyRunner._get_strategy_instance."""

    def test_returns_instance_for_known_type(self):
        """已知类型返回策略实例"""
        mock_repo = MagicMock()
        runner = StrategyRunner(strategy_repo=mock_repo)

        config = _make_config(strategy_type='ma_cross')
        instance = runner._get_strategy_instance(config)

        assert instance is not None
        assert instance.name == 'test_strategy'

    def test_returns_none_for_unknown_type(self):
        """未知类型返回 None"""
        mock_repo = MagicMock()
        runner = StrategyRunner(strategy_repo=mock_repo)

        config = _make_config(strategy_type='unknown_type')
        instance = runner._get_strategy_instance(config)

        assert instance is None

    def test_returns_instance_for_rsi_reversal(self):
        """RSI反转类型返回策略实例"""
        mock_repo = MagicMock()
        runner = StrategyRunner(strategy_repo=mock_repo)

        config = _make_config(strategy_type='rsi_reversal', name=None)
        instance = runner._get_strategy_instance(config)

        assert instance is not None
        assert 'RSI' in instance.name

    def test_returns_instance_for_bollinger(self):
        """布林带类型返回策略实例"""
        mock_repo = MagicMock()
        runner = StrategyRunner(strategy_repo=mock_repo)

        config = _make_config(strategy_type='bollinger_breakout')
        instance = runner._get_strategy_instance(config)

        assert instance is not None


# ==================== Runner.run() Mock Tests ====================

class TestRunnerRun:
    """Tests for StrategyRunner.run() with mocked repo and strategies."""

    def test_run_returns_ordered_signals(self):
        """run 返回按置信度排序的信号列表"""
        mock_repo = MagicMock()
        # Two active configs
        mock_repo.get_all.return_value = [
            _make_config(id=1, name='ma_strat', strategy_type='ma_cross'),
            _make_config(id=2, name='rsi_strat', strategy_type='rsi_reversal'),
        ]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        signals = runner.run(klines, symbol='000001.SZ')

        assert len(signals) == 2
        assert signals[0]['strategy_name'] in ('ma_strat', 'rsi_strat')
        assert signals[1]['strategy_name'] in ('ma_strat', 'rsi_strat')
        # 验证信号格式
        for s in signals:
            assert 'action' in s
            assert s['action'] in ('buy', 'sell', 'hold')
            assert 'confidence' in s
            assert 0.0 <= s['confidence'] <= 1.0
            assert 'reason' in s
            assert 'parameters' in s

    def test_run_skips_unknown_strategy_type(self):
        """跳过未知类型的策略配置"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = [
            _make_config(id=1, name='unknown', strategy_type='nonexistent_type'),
            _make_config(id=2, name='ma_strat', strategy_type='ma_cross'),
        ]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        signals = runner.run(klines)

        # Only the known strategy produces a signal
        assert len(signals) == 1
        assert signals[0]['strategy_name'] == 'ma_strat'

    def test_run_handles_strategy_exception(self):
        """策略执行异常时返回 hold 信号"""
        mock_repo = MagicMock()

        # Create a mock strategy that raises on generate_signal
        mock_strategy = MagicMock()
        mock_strategy.generate_signal.side_effect = Exception("Boom")
        mock_strategy.name = 'failing_strat'

        config = _make_config(id=1, name='failing_strat', strategy_type='ma_cross')
        mock_repo.get_all.return_value = [config]

        runner = StrategyRunner(strategy_repo=mock_repo)

        # Patch _get_strategy_instance to return the failing mock
        with patch.object(runner, '_get_strategy_instance', return_value=mock_strategy):
            klines = _make_klines([10.0] * 30)
            signals = runner.run(klines)

        assert len(signals) == 1
        assert signals[0]['action'] == 'hold'
        assert signals[0]['confidence'] == 0.0
        assert '异常' in signals[0]['reason']

    def test_run_parses_json_string_params(self):
        """parameters 为 JSON 字符串时正确解析"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = [
            _make_config(id=1, name='ma_strat', strategy_type='ma_cross',
                         parameters=json.dumps({'ma_short': 10, 'ma_long': 30}))
        ]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 40)
        signals = runner.run(klines)

        assert len(signals) == 1
        # params should be parsed to dict
        assert isinstance(signals[0]['parameters'], dict)
        assert signals[0]['parameters']['ma_short'] == 10

    def test_run_handles_invalid_json_params(self):
        """parameters 为无效 JSON 时回退为空 dict"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = [
            _make_config(id=1, name='ma_strat', strategy_type='ma_cross',
                         parameters='not-valid-json{{{')
        ]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        signals = runner.run(klines)

        assert len(signals) == 1
        assert signals[0]['parameters'] == {}

    def test_run_active_only_false(self):
        """active_only=False 时获取所有策略（包括非活跃）"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = [
            _make_config(id=1, name='ma_strat', strategy_type='ma_cross'),
        ]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        runner.run(klines, active_only=False)

        mock_repo.get_all.assert_called_once_with(active_only=False)

    def test_run_no_active_strategies(self):
        """无活跃策略时返回空列表"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = []

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        signals = runner.run(klines)

        assert signals == []

    def test_run_sort_order_buy_before_sell(self):
        """按置信度和优先级排序：buy > sell > hold"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = [
            _make_config(id=1, name='s1', strategy_type='ma_cross'),
            _make_config(id=2, name='s2', strategy_type='rsi_reversal'),
        ]

        # Create a runner and patch _get_strategy_instance to return a mock
        runner = StrategyRunner(strategy_repo=mock_repo)
        mock_strategy = MagicMock()
        # Return buy and sell with same confidence so action priority dominates
        mock_strategy.generate_signal.side_effect = [
            {'action': 'sell', 'confidence': 0.8, 'reason': 'test sell'},
            {'action': 'buy', 'confidence': 0.8, 'reason': 'test buy'},
        ]
        mock_strategy.name = 'mock_strat'

        with patch.object(runner, '_get_strategy_instance', return_value=mock_strategy):
            klines = _make_klines([10.0] * 30)
            signals = runner.run(klines)

        # Both signals are generated
        assert len(signals) == 2
        # buy should come before sell when confidence is equal (action priority)
        assert signals[0]['action'] == 'buy'
        assert signals[1]['action'] == 'sell'


# ==================== Runner.get_top_signals() Tests ====================

class TestGetTopSignals:
    """Tests for StrategyRunner.get_top_signals()."""

    def test_get_top_signals_limits_results(self):
        """get_top_signals 限制返回数量"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = [
            _make_config(id=i, name=f'strat_{i}', strategy_type='ma_cross')
            for i in range(5)
        ]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        top = runner.get_top_signals(klines, top_n=3)

        assert len(top) == 3


# ==================== Runner.combine_signals() Tests ====================

class TestCombineSignals:
    """Tests for StrategyRunner.combine_signals()."""

    def test_combine_with_specific_config_ids(self):
        """指定 config_ids 进行组合"""
        mock_repo = MagicMock()
        config1 = _make_config(id=1, name='s1', strategy_type='ma_cross')
        config2 = _make_config(id=2, name='s2', strategy_type='rsi_reversal')
        mock_repo.get_by_id.side_effect = [config1, config2]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        result = runner.combine_signals(klines, config_ids=[1, 2], mode='majority')

        assert 'action' in result
        assert 'confidence' in result
        assert 'reason' in result

    def test_combine_skips_none_configs(self):
        """跳过不存在的 config_ids"""
        mock_repo = MagicMock()
        # First config None (not found), second exists
        mock_repo.get_by_id.side_effect = [None, _make_config(id=2, name='s2', strategy_type='bollinger_breakout')]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        result = runner.combine_signals(klines, config_ids=[999, 2], mode='or')

        assert 'action' in result

    def test_combine_all_active_when_no_ids(self):
        """未指定 config_ids 时使用所有活跃策略"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = [
            _make_config(id=1, name='s1', strategy_type='ma_cross'),
        ]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        result = runner.combine_signals(klines, mode='and')

        assert 'action' in result
        mock_repo.get_all.assert_called_once_with(active_only=True)
        mock_repo.get_by_id.assert_not_called()

    def test_combine_handles_strategy_exception(self):
        """组合时个别策略异常不影响整体"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = [
            _make_config(id=1, name='failing', strategy_type='ma_cross'),
            _make_config(id=2, name='working', strategy_type='rsi_reversal'),
        ]

        runner = StrategyRunner(strategy_repo=mock_repo)

        # Mock _get_strategy_instance to return failing then working
        mock_failing = MagicMock()
        mock_failing.generate_signal.side_effect = Exception("Boom in strategy")
        mock_failing.name = 'failing'

        mock_working = MagicMock()
        mock_working.generate_signal.return_value = {'action': 'buy', 'confidence': 0.7, 'reason': 'ok'}
        mock_working.name = 'working'

        with patch.object(runner, '_get_strategy_instance', side_effect=[mock_failing, mock_working]):
            klines = _make_klines([10.0] * 30)
            result = runner.combine_signals(klines, mode='or')

        # Should still produce a result from the working strategy
        assert result['action'] == 'buy'

    def test_combine_parses_json_params(self):
        """组合时正确解析 JSON 字符串参数"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = [
            _make_config(id=1, name='s1', strategy_type='rsi_reversal',
                         parameters=json.dumps({'period': 14}))
        ]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        result = runner.combine_signals(klines, mode='or')

        assert result['action'] in ('buy', 'sell', 'hold')

    def test_combine_weighted_mode(self):
        """加权模式组合"""
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = [
            _make_config(id=1, name='s1', strategy_type='ma_cross'),
            _make_config(id=2, name='s2', strategy_type='rsi_reversal'),
        ]

        runner = StrategyRunner(strategy_repo=mock_repo)
        klines = _make_klines([10.0] * 30)
        result = runner.combine_signals(klines, mode='weighted', weights=[0.6, 0.4])

        assert 'action' in result
        assert 'confidence' in result
        assert 'reason' in result


# ==================== Runner.close() Test ====================

class TestRunnerClose:
    """Tests for StrategyRunner.close()."""

    def test_close_calls_repo_close(self):
        """close 调用 repo 的 close 方法"""
        mock_repo = MagicMock()
        runner = StrategyRunner(strategy_repo=mock_repo)
        runner.close()

        mock_repo.close.assert_called_once()

    def test_close_with_no_repo(self):
        """没有 repo 时 close 不报错"""
        runner = StrategyRunner(strategy_repo=None)
        runner.close()  # should not raise
