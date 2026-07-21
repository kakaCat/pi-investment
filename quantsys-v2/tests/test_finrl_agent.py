"""
Tests for FinRLAgent
====================

Tests the FinRLAgent class that wraps Stable-Baselines3 algorithms for financial trading.

Author: RL Migration Team
Date: 2026-05-25
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile
import shutil

# Import the modules we're testing
from domain.quantlib.finrl import FINRL_AVAILABLE
from domain.quantlib.finrl.config import get_default_config


# Mock environment for testing
class MockEnv:
    """Mock gym environment for testing."""

    def __init__(self, observation_space_shape=(10,), action_space_shape=(3,)):
        self.observation_space = Mock()
        self.observation_space.shape = observation_space_shape
        self.action_space = Mock()
        self.action_space.shape = action_space_shape
        self.action_space.n = action_space_shape[0] if len(action_space_shape) == 1 else None

    def reset(self):
        return np.random.randn(*self.observation_space.shape)

    def step(self, action):
        obs = np.random.randn(*self.observation_space.shape)
        reward = np.random.randn()
        done = False
        info = {}
        return obs, reward, done, info


@pytest.fixture
def mock_env():
    """Create a mock environment for testing."""
    return MockEnv()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
class TestFinRLAgentWithDependencies:
    """Tests that require FinRL dependencies."""

    def test_finrl_agent_instantiation_ppo(self, mock_env):
        """Test FinRLAgent instantiation with PPO algorithm."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        agent = FinRLAgent(algorithm='ppo', env=mock_env)

        assert agent.algorithm == 'ppo'
        assert agent.env == mock_env
        assert agent.model is None  # Model not created until train() is called

    def test_finrl_agent_instantiation_all_algorithms(self, mock_env):
        """Test FinRLAgent instantiation with all supported algorithms."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        algorithms = ['ppo', 'a2c', 'ddpg', 'sac', 'td3']

        for algo in algorithms:
            agent = FinRLAgent(algorithm=algo, env=mock_env)
            assert agent.algorithm == algo
            assert agent.env == mock_env

    def test_finrl_agent_invalid_algorithm(self, mock_env):
        """Test FinRLAgent with invalid algorithm raises ValueError."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        with pytest.raises(ValueError, match="Unsupported algorithm"):
            FinRLAgent(algorithm='invalid_algo', env=mock_env)

    def test_finrl_agent_inherits_from_base_rl_agent(self, mock_env):
        """Test that FinRLAgent inherits from BaseRLAgent."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent
        from domain.quantlib.finrl.base_rl_agent import BaseRLAgent

        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        assert isinstance(agent, BaseRLAgent)

    def test_finrl_agent_inherits_from_base_calculator(self, mock_env):
        """Test that FinRLAgent inherits from BaseCalculator."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent
        from domain.quantlib.core.base_calculator import BaseCalculator

        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        assert isinstance(agent, BaseCalculator)

    @patch('quantlib.finrl.finrl_agent.PPO')
    def test_train_method_ppo(self, mock_ppo_class, mock_env):
        """Test train() method with PPO algorithm."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        # Setup mock
        mock_model = MagicMock()
        mock_ppo_class.return_value = mock_model

        # Create agent and train
        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        config = get_default_config('ppo')

        result = agent.train(env=mock_env, config=config)

        # Verify model was created
        mock_ppo_class.assert_called_once()

        # Verify learn was called
        mock_model.learn.assert_called_once()

        # Verify result structure
        assert 'success' in result
        assert 'timesteps' in result
        assert 'algorithm' in result
        assert result['algorithm'] == 'ppo'

    @patch('quantlib.finrl.finrl_agent.A2C')
    def test_train_method_a2c(self, mock_a2c_class, mock_env):
        """Test train() method with A2C algorithm."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        # Setup mock
        mock_model = MagicMock()
        mock_a2c_class.return_value = mock_model

        # Create agent and train
        agent = FinRLAgent(algorithm='a2c', env=mock_env)
        config = get_default_config('a2c')

        result = agent.train(env=mock_env, config=config)

        # Verify model was created
        mock_a2c_class.assert_called_once()

        # Verify learn was called
        mock_model.learn.assert_called_once()

        # Verify result
        assert result['algorithm'] == 'a2c'

    @patch('quantlib.finrl.finrl_agent.PPO')
    def test_train_with_callbacks(self, mock_ppo_class, mock_env):
        """Test train() method with callbacks."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent
        from domain.quantlib.finrl.callbacks import CheckpointCallback

        # Setup mock
        mock_model = MagicMock()
        mock_ppo_class.return_value = mock_model

        # Create agent and callbacks
        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        config = get_default_config('ppo')
        callbacks = [CheckpointCallback(save_path='./test_models', save_freq=1000)]

        result = agent.train(env=mock_env, config=config, callbacks=callbacks)

        # Verify learn was called with callbacks
        call_kwargs = mock_model.learn.call_args[1]
        assert 'callback' in call_kwargs

    @patch('quantlib.finrl.finrl_agent.PPO')
    def test_predict_method(self, mock_ppo_class, mock_env):
        """Test predict() method."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        # Setup mock
        mock_model = MagicMock()
        mock_model.predict.return_value = (np.array([0.5, 0.3, 0.2]), None)
        mock_ppo_class.return_value = mock_model

        # Create agent and train
        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        config = get_default_config('ppo')
        agent.train(env=mock_env, config=config)

        # Test predict
        observation = np.random.randn(10)
        action = agent.predict(observation)

        # Verify predict was called
        mock_model.predict.assert_called_once()

        # Verify action is returned
        assert action is not None
        assert isinstance(action, np.ndarray)

    @patch('quantlib.finrl.finrl_agent.PPO')
    def test_predict_batch_observations(self, mock_ppo_class, mock_env):
        """Test predict() with batch observations."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        # Setup mock
        mock_model = MagicMock()
        mock_model.predict.return_value = (np.array([[0.5, 0.3, 0.2], [0.4, 0.4, 0.2]]), None)
        mock_ppo_class.return_value = mock_model

        # Create agent and train
        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        config = get_default_config('ppo')
        agent.train(env=mock_env, config=config)

        # Test predict with batch
        observations = np.random.randn(2, 10)
        actions = agent.predict(observations)

        # Verify actions shape
        assert actions.shape[0] == 2

    def test_predict_without_training_raises_error(self, mock_env):
        """Test predict() without training raises error."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        observation = np.random.randn(10)

        with pytest.raises(RuntimeError, match="Model not trained"):
            agent.predict(observation)

    @patch('quantlib.finrl.finrl_agent.PPO')
    def test_save_model(self, mock_ppo_class, mock_env, temp_dir):
        """Test save_model() method."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        # Setup mock
        mock_model = MagicMock()
        mock_ppo_class.return_value = mock_model

        # Create agent and train
        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        config = get_default_config('ppo')
        agent.train(env=mock_env, config=config)

        # Save model
        save_path = Path(temp_dir) / 'test_model'
        agent.save_model(str(save_path))

        # Verify save was called
        mock_model.save.assert_called_once()

    @patch('quantlib.finrl.finrl_agent.PPO')
    def test_load_model(self, mock_ppo_class, mock_env, temp_dir):
        """Test load_model() method."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        # Setup mock
        mock_model = MagicMock()
        mock_ppo_class.load.return_value = mock_model

        # Create agent and load
        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        load_path = Path(temp_dir) / 'test_model'

        agent.load_model(str(load_path))

        # Verify load was called
        mock_ppo_class.load.assert_called_once()

        # Verify model is set
        assert agent.model is not None

    @patch('quantlib.finrl.finrl_agent.PPO')
    def test_calculate_method(self, mock_ppo_class, mock_env):
        """Test calculate() method (inherited from BaseCalculator)."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        # Setup mock
        mock_model = MagicMock()
        mock_model.predict.return_value = (np.array([0.5, 0.3, 0.2]), None)
        mock_ppo_class.return_value = mock_model

        # Create agent and train
        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        config = get_default_config('ppo')
        agent.train(env=mock_env, config=config)

        # Test calculate (should call predict internally)
        observation = np.random.randn(10)
        result = agent.calculate(observation)

        # Verify result structure (from BaseCalculator)
        assert 'value' in result
        assert 'method' in result
        assert 'parameters' in result
        assert 'metadata' in result

    @patch('quantlib.finrl.finrl_agent.PPO')
    def test_get_supported_methods(self, mock_ppo_class, mock_env):
        """Test get_supported_methods() returns correct methods."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        methods = agent.get_supported_methods()

        assert isinstance(methods, list)
        assert 'train' in methods
        assert 'predict' in methods
        assert 'save_model' in methods
        assert 'load_model' in methods


class TestFinRLAgentWithoutDependencies:
    """Tests that work without FinRL dependencies."""

    def test_finrl_available_flag(self):
        """Test FINRL_AVAILABLE flag is set correctly."""
        # This test just verifies the flag exists
        assert isinstance(FINRL_AVAILABLE, bool)

    @pytest.mark.skipif(FINRL_AVAILABLE, reason="Test only when FinRL not available")
    def test_graceful_degradation_without_finrl(self):
        """Test graceful degradation when FinRL is not available."""
        # When FinRL is not available, import should still work but raise error on use
        try:
            from domain.quantlib.finrl.finrl_agent import FinRLAgent
            # If import succeeds, trying to use it should fail gracefully
            with pytest.raises((ImportError, RuntimeError)):
                agent = FinRLAgent(algorithm='ppo', env=None)
        except ImportError:
            # Expected when FinRL not available
            pass

    def test_config_module_always_available(self):
        """Test that config module is always available."""
        # Config module should work without FinRL dependencies
        config = get_default_config('ppo')

        assert config is not None
        assert 'algorithm' in config
        assert config['algorithm'] == 'ppo'


class TestBaseRLAgent:
    """Tests for BaseRLAgent base class."""

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_base_rl_agent_is_abstract(self):
        """Test that BaseRLAgent is abstract and cannot be instantiated directly."""
        from domain.quantlib.finrl.base_rl_agent import BaseRLAgent

        # BaseRLAgent should be abstract
        with pytest.raises(TypeError):
            BaseRLAgent()

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_base_rl_agent_defines_interface(self):
        """Test that BaseRLAgent defines the required interface."""
        from domain.quantlib.finrl.base_rl_agent import BaseRLAgent

        # Check that abstract methods are defined
        assert hasattr(BaseRLAgent, 'train')
        assert hasattr(BaseRLAgent, 'predict')
        assert hasattr(BaseRLAgent, 'save_model')
        assert hasattr(BaseRLAgent, 'load_model')


class TestFinRLAgentIntegration:
    """Integration tests for FinRLAgent."""

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    @patch('quantlib.finrl.finrl_agent.PPO')
    def test_full_training_pipeline(self, mock_ppo_class, mock_env, temp_dir):
        """Test full training pipeline: train -> predict -> save -> load."""
        from domain.quantlib.finrl.finrl_agent import FinRLAgent

        # Setup mock
        mock_model = MagicMock()
        mock_model.predict.return_value = (np.array([0.5, 0.3, 0.2]), None)
        mock_ppo_class.return_value = mock_model
        mock_ppo_class.load.return_value = mock_model

        # 1. Train
        agent = FinRLAgent(algorithm='ppo', env=mock_env)
        config = get_default_config('ppo', training={'total_timesteps': 1000})
        train_result = agent.train(env=mock_env, config=config)

        assert train_result['success']

        # 2. Predict
        observation = np.random.randn(10)
        action = agent.predict(observation)
        assert action is not None

        # 3. Save
        save_path = Path(temp_dir) / 'trained_model'
        agent.save_model(str(save_path))

        # 4. Load in new agent
        new_agent = FinRLAgent(algorithm='ppo', env=mock_env)
        new_agent.load_model(str(save_path))

        # 5. Predict with loaded model
        action2 = new_agent.predict(observation)
        assert action2 is not None

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_algorithm_mapping(self):
        """Test that all algorithms in ALGORITHM_MAP are supported."""
        from domain.quantlib.finrl.finrl_agent import ALGORITHM_MAP

        expected_algorithms = ['ppo', 'a2c', 'ddpg', 'sac', 'td3']

        for algo in expected_algorithms:
            assert algo in ALGORITHM_MAP
            assert ALGORITHM_MAP[algo] is not None
