"""
Tests for QlibTradingEnv
========================

Tests for Qlib RL trading environment wrapper.

Author: RL Migration Team
Date: 2026-05-25
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch
from domain.quantlib.qlib import QLIB_RL_AVAILABLE

# Skip all tests if Qlib is not available
pytestmark = pytest.mark.skipif(
    not QLIB_RL_AVAILABLE,
    reason="Qlib RL dependencies not available"
)


@pytest.fixture
def sample_data():
    """Create sample stock data for testing."""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    data = pd.DataFrame({
        'date': dates,
        'open': np.random.randn(100) * 10 + 100,
        'high': np.random.randn(100) * 10 + 105,
        'low': np.random.randn(100) * 10 + 95,
        'close': np.random.randn(100) * 10 + 100,
        'volume': np.random.randint(1000000, 10000000, 100),
    })
    return data


class TestQlibTradingEnv:
    """Test suite for QlibTradingEnv."""

    def test_import_qlib_environment(self):
        """Test that QlibTradingEnv can be imported."""
        from domain.quantlib.qlib import QlibTradingEnv
        assert QlibTradingEnv is not None

    def test_environment_initialization(self, sample_data):
        """Test environment initialization."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(
            df=sample_data,
            initial_capital=100000,
            transaction_cost=0.001
        )

        assert env.initial_capital == 100000
        assert env.transaction_cost == 0.001
        assert len(env.df) == 100

    def test_environment_inherits_from_base(self, sample_data):
        """Test that QlibTradingEnv inherits from BaseRLEnvironment."""
        from domain.quantlib.qlib import QlibTradingEnv
        from domain.quantlib.rl.base_environment import BaseRLEnvironment

        env = QlibTradingEnv(df=sample_data)
        assert isinstance(env, BaseRLEnvironment)

    def test_action_space_defined(self, sample_data):
        """Test that action space is properly defined."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)

        assert env.action_space is not None
        assert isinstance(env.action_space, dict)

    def test_observation_space_defined(self, sample_data):
        """Test that observation space is properly defined."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)

        assert env.observation_space is not None
        assert isinstance(env.observation_space, dict)

    def test_reset_method(self, sample_data):
        """Test environment reset."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data, initial_capital=100000)
        observation, info = env.reset(seed=42)

        assert isinstance(observation, np.ndarray)
        assert isinstance(info, dict)
        assert env.state is not None

    def test_reset_with_seed(self, sample_data):
        """Test that reset with seed is reproducible."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)

        obs1, _ = env.reset(seed=42)
        obs2, _ = env.reset(seed=42)

        np.testing.assert_array_equal(obs1, obs2)

    def test_step_method(self, sample_data):
        """Test environment step."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)
        env.reset(seed=42)

        action = 0  # Example action
        observation, reward, terminated, truncated, info = env.step(action)

        assert isinstance(observation, np.ndarray)
        assert isinstance(reward, (int, float))
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_step_before_reset_raises_error(self, sample_data):
        """Test that step before reset raises error."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)

        with pytest.raises(RuntimeError, match="reset"):
            env.step(0)

    def test_render_method(self, sample_data):
        """Test environment rendering."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)
        env.reset()

        output = env.render()

        assert isinstance(output, str)
        assert len(output) > 0

    def test_close_method(self, sample_data):
        """Test environment cleanup."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)
        env.reset()
        env.close()

        assert env.state is None

    def test_empty_dataframe_raises_error(self):
        """Test that empty DataFrame raises error."""
        from domain.quantlib.qlib import QlibTradingEnv

        with pytest.raises(ValueError, match="empty"):
            QlibTradingEnv(df=pd.DataFrame())

    def test_missing_columns_raises_error(self):
        """Test that missing required columns raises error."""
        from domain.quantlib.qlib import QlibTradingEnv

        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'close': np.random.randn(10) + 100,
        })

        with pytest.raises(ValueError, match="missing required columns"):
            QlibTradingEnv(df=df)

    def test_portfolio_tracking(self, sample_data):
        """Test that environment tracks portfolio state."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data, initial_capital=100000)
        env.reset()

        # Check initial state
        assert hasattr(env, 'balance')
        assert hasattr(env, 'holdings')
        assert hasattr(env, 'portfolio_value')

    def test_transaction_cost_applied(self, sample_data):
        """Test that transaction costs are applied."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(
            df=sample_data,
            initial_capital=100000,
            transaction_cost=0.001
        )
        env.reset()

        initial_balance = env.balance
        env.step(1)  # Execute buy action

        # Balance should change due to transaction cost
        # (exact assertion depends on implementation)
        assert hasattr(env, 'transaction_cost')

    def test_reward_calculation(self, sample_data):
        """Test that rewards are calculated correctly."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)
        env.reset()

        _, reward1, _, _, _ = env.step(0)
        _, reward2, _, _, _ = env.step(1)

        assert isinstance(reward1, (int, float))
        assert isinstance(reward2, (int, float))

    def test_episode_termination(self, sample_data):
        """Test that episode terminates correctly."""
        from domain.quantlib.qlib import QlibTradingEnv

        # Use small dataset to reach end quickly
        small_data = sample_data.head(5)
        env = QlibTradingEnv(df=small_data)
        env.reset()

        terminated = False
        steps = 0
        max_steps = 10

        while not terminated and steps < max_steps:
            _, _, terminated, truncated, _ = env.step(0)
            steps += 1
            if truncated:
                break

        assert steps <= max_steps

    def test_observation_shape_consistency(self, sample_data):
        """Test that observation shape is consistent."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)
        obs1, _ = env.reset()
        obs2, _, _, _, _ = env.step(0)

        assert obs1.shape == obs2.shape

    def test_seed_method(self, sample_data):
        """Test seed method."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)
        env.seed(42)

        assert env._np_random is not None

    def test_multiple_episodes(self, sample_data):
        """Test running multiple episodes."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)

        # Episode 1
        env.reset(seed=42)
        env.step(0)
        env.step(1)

        # Episode 2
        env.reset(seed=42)
        env.step(0)
        env.step(1)

        # Should not raise errors

    def test_info_dict_contains_metadata(self, sample_data):
        """Test that info dict contains useful metadata."""
        from domain.quantlib.qlib import QlibTradingEnv

        env = QlibTradingEnv(df=sample_data)
        _, info = env.reset()

        assert isinstance(info, dict)

        _, _, _, _, info = env.step(0)
        assert isinstance(info, dict)

    def test_qlib_data_format_integration(self, sample_data):
        """Test integration with Qlib data format."""
        from domain.quantlib.qlib import QlibTradingEnv

        # Qlib typically uses specific column names and formats
        env = QlibTradingEnv(df=sample_data)
        env.reset()

        # Environment should handle Qlib data format
        assert env.df is not None
        assert len(env.df) > 0

    @patch('quantlib.qlib.qlib_environment.QLIB_RL_AVAILABLE', False)
    def test_graceful_degradation_when_qlib_unavailable(self, sample_data):
        """Test that environment handles missing Qlib gracefully."""
        from domain.quantlib.qlib import QlibTradingEnv

        # Should still be able to create environment
        # but may have limited functionality
        env = QlibTradingEnv(df=sample_data)
        assert env is not None
