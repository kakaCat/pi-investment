import pytest
from datetime import datetime
from application.services.combo_strategy_backtest_service import ComboStrategyBacktestService


class TestComboStrategyBacktestService:

    @pytest.fixture
    def mock_strategy_repo(self):
        class MockStrategyRepo:
            def get_by_id(self, strategy_id):
                return {'id': strategy_id, 'name': f'Strategy {strategy_id}'}

            def get_all(self, active_only=False):
                return [
                    {'id': 53, 'name': 'Strategy 53'},
                    {'id': 54, 'name': 'Strategy 54'}
                ]
        return MockStrategyRepo()

    @pytest.fixture
    def mock_backtest_engine(self):
        class MockBacktestEngine:
            def backtest(self, strategy, symbols, **kwargs):
                # Return mock result
                initial = kwargs.get('initial_capital', 100000)
                return {
                    'strategy_id': strategy.get('id'),
                    'equity_curve': [
                        {'date': '2025-01-01', 'value': initial},
                        {'date': '2025-12-31', 'value': initial * 1.1}
                    ],
                    'metrics': {
                        'total_return': 0.1,
                        'sharpe_ratio': 1.5,
                        'max_drawdown': -0.05
                    }
                }
        return MockBacktestEngine()

    @pytest.fixture
    def service(self, mock_strategy_repo, mock_backtest_engine):
        return ComboStrategyBacktestService(
            strategy_repo=mock_strategy_repo,
            backtest_engine=mock_backtest_engine,
            strategy_combiner=None
        )

    def test_portfolio_mode_basic(self, service):
        """Test portfolio mode with 2 strategies"""
        result = service.backtest_combo(
            mode='portfolio',
            strategies=[
                {'strategy_id': 53, 'weight': 0.3},
                {'strategy_id': 54, 'weight': 0.7}
            ],
            symbols=['600519.SH'],
            start_date='2025-01-01',
            end_date='2025-12-31',
            initial_capital=1000000.0
        )

        assert result['mode'] == 'portfolio'
        assert 'overall_metrics' in result
        assert len(result['strategy_breakdown']) == 2
        assert result['strategy_breakdown'][0]['weight'] == 0.3
        assert result['strategy_breakdown'][1]['weight'] == 0.7

    def test_portfolio_weight_validation_fails(self, service):
        """Test that weight sum != 1.0 raises error"""
        with pytest.raises(ValueError, match="权重和必须为1"):
            service.backtest_combo(
                mode='portfolio',
                strategies=[
                    {'strategy_id': 53, 'weight': 0.4},
                    {'strategy_id': 54, 'weight': 0.5}  # Sum = 0.9
                ],
                symbols=['600519.SH'],
                start_date='2025-01-01',
                end_date='2025-12-31',
                initial_capital=1000000.0
            )

    def test_portfolio_minimum_strategies(self, service):
        """Test that < 2 strategies raises error"""
        with pytest.raises(ValueError, match="至少需要2个策略"):
            service.backtest_combo(
                mode='portfolio',
                strategies=[{'strategy_id': 53, 'weight': 1.0}],
                symbols=['600519.SH'],
                start_date='2025-01-01',
                end_date='2025-12-31',
                initial_capital=1000000.0
            )

    @pytest.fixture
    def mock_strategy_combiner(self):
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        return StrategyCombiner(mode='weighted')

    @pytest.fixture
    def service_with_combiner(self, mock_strategy_repo, mock_backtest_engine, mock_strategy_combiner):
        return ComboStrategyBacktestService(
            strategy_repo=mock_strategy_repo,
            backtest_engine=mock_backtest_engine,
            strategy_combiner=mock_strategy_combiner
        )

    def test_ensemble_mode_weighted(self, service_with_combiner):
        """Test ensemble mode with weighted signal fusion"""
        result = service_with_combiner.backtest_combo(
            mode='ensemble',
            strategies=[
                {'strategy_id': 53, 'signal_weight': 0.6},
                {'strategy_id': 54, 'signal_weight': 0.4}
            ],
            symbols=['600519.SH'],
            start_date='2025-01-01',
            end_date='2025-12-31',
            initial_capital=1000000.0,
            ensemble_method='weighted'
        )

        assert result['mode'] == 'ensemble'
        assert 'overall_metrics' in result
        assert result['overall_metrics']['total_return'] >= 0

    def test_ensemble_invalid_method(self, service_with_combiner):
        """Test that invalid ensemble_method raises error"""
        with pytest.raises(ValueError, match="无效的 ensemble_method"):
            service_with_combiner.backtest_combo(
                mode='ensemble',
                strategies=[
                    {'strategy_id': 53, 'signal_weight': 0.6},
                    {'strategy_id': 54, 'signal_weight': 0.4}
                ],
                symbols=['600519.SH'],
                start_date='2025-01-01',
                end_date='2025-12-31',
                initial_capital=1000000.0,
                ensemble_method='invalid_method'
            )
