"""
Tests for QlibRLAgent
=====================

Tests for Qlib RL agent wrapper, including training, prediction,
and model management.

Author: RL Migration Team
Date: 2026-05-25
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from domain.quantlib.qlib import QLIB_RL_AVAILABLE

# Skip all tests if Qlib is not available
pytestmark = pytest.mark.skipif(
    not QLIB_RL_AVAILABLE,
    reason="Qlib RL dependencies not available"
)


@pytest.fixture
def mock_env():
    """Create a mock Qlib trading environment."""
    env = Mock()
    env.observation_space = Mock()
    env.observation_space.shape = (10,)
    env.action_space = Mock()
    env.action_space.n = 3
    return env


@pytest.fixture
def mock_qlib_model():
    """Create a mock Qlib RL model."""
    model = Mock()
    model.predict = Mock(return_value=np.array([0.5, 0.3, 0.2]))
    model.learn = Mock(return_value={'total_timesteps': 1000})
    model.save = Mock()
    model.load = Mock()
    return model


class TestQlibRLAgent:
    """Test suite for QlibRLAgent."""

    def test_import_qlib_agent(self):
        """Test that QlibRLAgent can be imported."""
        from domain.quantlib.qlib import QlibRLAgent
        assert QlibRLAgent is not None

    def test_agent_initialization(self, mock_env):
        """Test agent initialization."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)

        assert agent.algorithm == 'ppo'
        assert agent.env == mock_env
        assert agent.model is None

    def test_agent_inherits_from_base(self, mock_env):
        """Test that QlibRLAgent inherits from BaseRLAgent."""
        from domain.quantlib.qlib import QlibRLAgent
        from domain.quantlib.finrl.base_rl_agent import BaseRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        assert isinstance(agent, BaseRLAgent)

    def test_supported_algorithms(self, mock_env):
        """Test that agent supports Qlib RL algorithms."""
        from domain.quantlib.qlib import QlibRLAgent

        algorithms = ['ppo', 'dqn', 'a2c', 'sac', 'td3']
        for algo in algorithms:
            agent = QlibRLAgent(algorithm=algo, env=mock_env)
            assert agent.algorithm == algo

    @patch('quantlib.qlib.qlib_agent.QLIB_RL_AVAILABLE', True)
    def test_train_method_exists(self, mock_env):
        """Test that train method exists."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        assert hasattr(agent, 'train')
        assert callable(agent.train)

    @patch('quantlib.qlib.qlib_agent.QLIB_RL_AVAILABLE', True)
    def test_train_with_config(self, mock_env, mock_qlib_model):
        """Test training with configuration."""
        from domain.quantlib.qlib import QlibRLAgent
        from domain.quantlib.qlib.config import get_default_config

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        config = get_default_config('ppo')

        # Mock the model creation
        with patch.object(agent, '_create_model', return_value=mock_qlib_model):
            result = agent.train(mock_env, config)

            assert isinstance(result, dict)
            assert agent.model is not None

    def test_predict_before_training_raises_error(self, mock_env):
        """Test that predict raises error before training."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        observation = np.random.randn(10)

        with pytest.raises(RuntimeError, match="not trained"):
            agent.predict(observation)

    @patch('quantlib.qlib.qlib_agent.QLIB_RL_AVAILABLE', True)
    def test_predict_after_training(self, mock_env, mock_qlib_model):
        """Test prediction after training."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        agent.model = mock_qlib_model

        observation = np.random.randn(10)
        action = agent.predict(observation)

        assert isinstance(action, np.ndarray)
        mock_qlib_model.predict.assert_called_once()

    def test_save_model_before_training_raises_error(self, mock_env, tmp_path):
        """Test that save_model raises error before training."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        model_path = str(tmp_path / "model.pkl")

        with pytest.raises(RuntimeError, match="not trained"):
            agent.save_model(model_path)

    @patch('quantlib.qlib.qlib_agent.QLIB_RL_AVAILABLE', True)
    def test_save_model_after_training(self, mock_env, mock_qlib_model, tmp_path):
        """Test saving model after training."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        agent.model = mock_qlib_model

        model_path = str(tmp_path / "model.pkl")
        agent.save_model(model_path)

        mock_qlib_model.save.assert_called_once()

    @patch('quantlib.qlib.qlib_agent.QLIB_RL_AVAILABLE', True)
    def test_load_model(self, mock_env, mock_qlib_model, tmp_path):
        """Test loading model from disk."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        model_path = str(tmp_path / "model.pkl")

        # Mock the model loading
        with patch.object(agent, '_load_model', return_value=mock_qlib_model):
            agent.load_model(model_path)

            assert agent.model is not None

    def test_load_model_nonexistent_file(self, mock_env, tmp_path):
        """Test that loading nonexistent model raises error."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        model_path = str(tmp_path / "nonexistent.pkl")

        with pytest.raises(FileNotFoundError):
            agent.load_model(model_path)

    def test_calculate_method(self, mock_env, mock_qlib_model):
        """Test calculate method (BaseCalculator interface)."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        agent.model = mock_qlib_model

        observation = np.random.randn(10)
        result = agent.calculate(observation)

        assert isinstance(result, dict)
        assert 'value' in result
        assert 'method' in result
        assert 'metadata' in result
        assert result['metadata']['algorithm'] == 'ppo'

    def test_get_supported_methods(self, mock_env):
        """Test get_supported_methods."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        methods = agent.get_supported_methods()

        assert isinstance(methods, list)
        assert 'train' in methods
        assert 'predict' in methods
        assert 'save_model' in methods
        assert 'load_model' in methods
        assert 'calculate' in methods

    @patch('quantlib.qlib.qlib_agent.QLIB_RL_AVAILABLE', False)
    def test_graceful_degradation_when_qlib_unavailable(self, mock_env):
        """Test that agent handles missing Qlib gracefully."""
        from domain.quantlib.qlib import QlibRLAgent
        from domain.quantlib.qlib.config import get_default_config

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        config = get_default_config('ppo')

        # Training should raise informative error
        with pytest.raises(ImportError, match="Qlib"):
            agent.train(mock_env, config)

    def test_agent_with_callbacks(self, mock_env, mock_qlib_model):
        """Test training with callbacks."""
        from domain.quantlib.qlib import QlibRLAgent
        from domain.quantlib.qlib.config import get_default_config

        agent = QlibRLAgent(algorithm='ppo', env=mock_env)
        config = get_default_config('ppo')
        callbacks = [Mock()]

        with patch.object(agent, '_create_model', return_value=mock_qlib_model):
            result = agent.train(mock_env, config, callbacks=callbacks)

            assert isinstance(result, dict)

    def test_agent_precision_parameter(self, mock_env):
        """Test that precision parameter is passed to BaseCalculator."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env, precision=4)
        assert agent.precision == 4

    def test_agent_risk_free_rate_parameter(self, mock_env):
        """Test that risk_free_rate parameter is passed to BaseCalculator."""
        from domain.quantlib.qlib import QlibRLAgent

        agent = QlibRLAgent(algorithm='ppo', env=mock_env, risk_free_rate=0.03)
        assert agent.risk_free_rate == 0.03
