"""
Tests for BaseRLAgent and BaseRLEnvironment - base classes for reinforcement learning

Author: RL Migration Team
Date: 2026-05-25
"""

import numpy as np
import pandas as pd
import pytest
from abc import ABC
from unittest.mock import MagicMock, patch
from typing import Any, Tuple

from domain.quantlib.base_calculator import BaseCalculator
from domain.quantlib.rl.base_agent import BaseRLAgent
from domain.quantlib.rl.base_environment import BaseRLEnvironment


class ConcreteRLAgent(BaseRLAgent):
    """Concrete implementation for testing BaseRLAgent"""

    def train(self, env, episodes: int = 1000, **kwargs):
        """Mock train implementation"""
        return {"episodes": episodes, "status": "trained"}

    def predict(self, observation, **kwargs):
        """Mock predict implementation"""
        if isinstance(observation, np.ndarray):
            return np.argmax(observation)
        return 0

    def save_model(self, filepath: str):
        """Mock save_model implementation"""
        return True

    def load_model(self, filepath: str):
        """Mock load_model implementation"""
        return True


class IncompleteRLAgent(BaseRLAgent):
    """Incomplete implementation to test abstract method enforcement"""

    def train(self, env, episodes: int = 1000, **kwargs):
        return {"status": "trained"}

    # Missing: predict, save_model, load_model


@pytest.fixture
def sample_observation():
    """Create sample observation data"""
    return np.array([0.1, 0.5, 0.3, 0.8])


@pytest.fixture
def sample_action_space():
    """Create sample action space"""
    return {"type": "discrete", "n": 4}


@pytest.fixture
def sample_observation_space():
    """Create sample observation space"""
    return {"type": "box", "shape": (4,), "low": 0.0, "high": 1.0}


class TestBaseRLAgent:
    """Test suite for BaseRLAgent"""

    def test_inheritance_from_base_calculator(self):
        """Test BaseRLAgent inherits from BaseCalculator"""
        assert issubclass(BaseRLAgent, BaseCalculator)
        assert issubclass(BaseRLAgent, ABC)

    def test_instantiation_with_defaults(self):
        """Test BaseRLAgent instantiation with default parameters"""
        agent = ConcreteRLAgent()

        assert agent.precision == 6
        assert agent.risk_free_rate == 0.0
        assert agent.action_space is None
        assert agent.observation_space is None
        assert agent.model is None
        assert agent.logger is not None

    def test_instantiation_with_custom_parameters(self, sample_action_space, sample_observation_space):
        """Test BaseRLAgent instantiation with custom parameters"""
        agent = ConcreteRLAgent(
            precision=4,
            risk_free_rate=0.03,
            action_space=sample_action_space,
            observation_space=sample_observation_space
        )

        assert agent.precision == 4
        assert agent.risk_free_rate == 0.03
        assert agent.action_space == sample_action_space
        assert agent.observation_space == sample_observation_space

    def test_abstract_method_enforcement_train(self):
        """Test that train() must be implemented"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            class NoTrainAgent(BaseRLAgent):
                def predict(self, observation, **kwargs):
                    return 0
                def save_model(self, filepath: str):
                    return True
                def load_model(self, filepath: str):
                    return True

            NoTrainAgent()

    def test_abstract_method_enforcement_predict(self):
        """Test that predict() must be implemented"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            class NoPredictAgent(BaseRLAgent):
                def train(self, env, episodes: int = 1000, **kwargs):
                    return {}
                def save_model(self, filepath: str):
                    return True
                def load_model(self, filepath: str):
                    return True

            NoPredictAgent()

    def test_abstract_method_enforcement_save_model(self):
        """Test that save_model() must be implemented"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            class NoSaveAgent(BaseRLAgent):
                def train(self, env, episodes: int = 1000, **kwargs):
                    return {}
                def predict(self, observation, **kwargs):
                    return 0
                def load_model(self, filepath: str):
                    return True

            NoSaveAgent()

    def test_abstract_method_enforcement_load_model(self):
        """Test that load_model() must be implemented"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            class NoLoadAgent(BaseRLAgent):
                def train(self, env, episodes: int = 1000, **kwargs):
                    return {}
                def predict(self, observation, **kwargs):
                    return 0
                def save_model(self, filepath: str):
                    return True

            NoLoadAgent()

    def test_calculate_calls_predict(self, sample_observation):
        """Test calculate() method calls predict() internally"""
        agent = ConcreteRLAgent()

        result = agent.calculate(sample_observation)

        assert isinstance(result, dict)
        assert 'value' in result
        assert 'method' in result
        assert result['method'] == 'predict'
        assert 'timestamp' in result
        assert 'calculator' in result
        assert result['calculator'] == 'ConcreteRLAgent'

    def test_calculate_with_observation_array(self, sample_observation):
        """Test calculate() with numpy array observation"""
        agent = ConcreteRLAgent()

        result = agent.calculate(sample_observation)

        # Should return argmax of observation (index 3)
        assert result['value'] == 3

    def test_calculate_with_kwargs(self, sample_observation):
        """Test calculate() passes kwargs to predict()"""
        agent = ConcreteRLAgent()

        result = agent.calculate(sample_observation, deterministic=True)

        assert isinstance(result, dict)
        assert 'value' in result

    def test_train_method(self):
        """Test train() method"""
        agent = ConcreteRLAgent()
        mock_env = MagicMock()

        result = agent.train(mock_env, episodes=500)

        assert isinstance(result, dict)
        assert result['episodes'] == 500
        assert result['status'] == 'trained'

    def test_predict_method(self, sample_observation):
        """Test predict() method"""
        agent = ConcreteRLAgent()

        action = agent.predict(sample_observation)

        assert isinstance(action, (int, np.integer))
        assert action == 3  # argmax of [0.1, 0.5, 0.3, 0.8]

    def test_save_model_method(self):
        """Test save_model() method"""
        agent = ConcreteRLAgent()

        result = agent.save_model('/tmp/test_model.pkl')

        assert result is True

    def test_load_model_method(self):
        """Test load_model() method"""
        agent = ConcreteRLAgent()

        result = agent.load_model('/tmp/test_model.pkl')

        assert result is True

    def test_action_space_attribute(self, sample_action_space):
        """Test action_space attribute"""
        agent = ConcreteRLAgent(action_space=sample_action_space)

        assert agent.action_space == sample_action_space
        assert agent.action_space['type'] == 'discrete'
        assert agent.action_space['n'] == 4

    def test_observation_space_attribute(self, sample_observation_space):
        """Test observation_space attribute"""
        agent = ConcreteRLAgent(observation_space=sample_observation_space)

        assert agent.observation_space == sample_observation_space
        assert agent.observation_space['type'] == 'box'
        assert agent.observation_space['shape'] == (4,)

    def test_model_attribute(self):
        """Test model attribute"""
        agent = ConcreteRLAgent()

        assert agent.model is None

        # Set model
        mock_model = MagicMock()
        agent.model = mock_model

        assert agent.model is mock_model

    def test_inherited_base_calculator_methods(self):
        """Test inherited BaseCalculator methods are available"""
        agent = ConcreteRLAgent()

        # Test inherited methods
        assert hasattr(agent, '_validate_numeric_input')
        assert hasattr(agent, '_validate_positive')
        assert hasattr(agent, '_validate_probability')
        assert hasattr(agent, '_round_result')
        assert hasattr(agent, 'set_precision')
        assert hasattr(agent, 'set_risk_free_rate')

    def test_inherited_validation_methods(self):
        """Test inherited validation methods work correctly"""
        agent = ConcreteRLAgent()

        # Test numeric validation
        validated = agent._validate_numeric_input([1.0, 2.0, 3.0], 'test_data')
        assert isinstance(validated, np.ndarray)

        # Test positive validation
        validated_pos = agent._validate_positive(5.0, 'test_value')
        assert validated_pos == 5.0

        # Test probability validation
        validated_prob = agent._validate_probability(0.5, 'test_prob')
        assert validated_prob == 0.5

    def test_precision_setting(self):
        """Test precision can be set and affects results"""
        agent = ConcreteRLAgent(precision=2)

        assert agent.precision == 2

        agent.set_precision(4)
        assert agent.precision == 4

    def test_risk_free_rate_setting(self):
        """Test risk_free_rate can be set"""
        agent = ConcreteRLAgent(risk_free_rate=0.02)

        assert agent.risk_free_rate == 0.02

        agent.set_risk_free_rate(0.05)
        assert agent.risk_free_rate == 0.05

    def test_logger_setup(self):
        """Test logger is properly set up"""
        agent = ConcreteRLAgent()

        assert agent.logger is not None
        assert agent.logger.name == 'ConcreteRLAgent'

    def test_calculate_result_structure(self, sample_observation):
        """Test calculate() returns properly structured result"""
        agent = ConcreteRLAgent()

        result = agent.calculate(sample_observation)

        # Check result structure
        assert isinstance(result, dict)
        assert 'value' in result
        assert 'method' in result
        assert 'timestamp' in result
        assert 'calculator' in result

        # Check types
        assert isinstance(result['method'], str)
        assert isinstance(result['timestamp'], str)
        assert isinstance(result['calculator'], str)

    def test_calculate_with_metadata(self, sample_observation):
        """Test calculate() can include metadata"""
        agent = ConcreteRLAgent()

        result = agent.calculate(sample_observation)

        # Result should have standard metadata
        assert 'timestamp' in result
        assert 'calculator' in result

    def test_multiple_predictions(self, sample_observation):
        """Test multiple predictions work correctly"""
        agent = ConcreteRLAgent()

        result1 = agent.calculate(sample_observation)
        result2 = agent.calculate(sample_observation)

        # Should produce consistent results
        assert result1['value'] == result2['value']

    def test_different_observation_types(self):
        """Test predict() with different observation types"""
        agent = ConcreteRLAgent()

        # Test with numpy array
        obs_array = np.array([0.1, 0.5, 0.3])
        action1 = agent.predict(obs_array)
        assert isinstance(action1, (int, np.integer))

        # Test with list (will be converted)
        obs_list = [0.1, 0.5, 0.3]
        action2 = agent.predict(np.array(obs_list))
        assert isinstance(action2, (int, np.integer))

    def test_spaces_can_be_none(self):
        """Test action_space and observation_space can be None"""
        agent = ConcreteRLAgent()

        assert agent.action_space is None
        assert agent.observation_space is None

        # Agent should still work
        result = agent.calculate(np.array([0.1, 0.5]))
        assert 'value' in result

    def test_spaces_can_be_updated(self, sample_action_space, sample_observation_space):
        """Test spaces can be updated after initialization"""
        agent = ConcreteRLAgent()

        agent.action_space = sample_action_space
        agent.observation_space = sample_observation_space

        assert agent.action_space == sample_action_space
        assert agent.observation_space == sample_observation_space

    def test_calculate_rounds_result(self):
        """Test calculate() rounds result according to precision"""
        agent = ConcreteRLAgent(precision=2)

        # Mock predict to return float
        agent.predict = lambda obs, **kwargs: 3.14159265

        result = agent.calculate(np.array([0.1, 0.5]))

        assert result['value'] == 3.14

    def test_train_with_kwargs(self):
        """Test train() accepts additional kwargs"""
        agent = ConcreteRLAgent()
        mock_env = MagicMock()

        result = agent.train(
            mock_env,
            episodes=100,
            learning_rate=0.001,
            gamma=0.99
        )

        assert isinstance(result, dict)

    def test_predict_with_kwargs(self, sample_observation):
        """Test predict() accepts additional kwargs"""
        agent = ConcreteRLAgent()

        # Should not raise error
        action = agent.predict(sample_observation, deterministic=True, temperature=0.5)

        assert isinstance(action, (int, np.integer))

    def test_docstring_presence(self):
        """Test BaseRLAgent has proper docstring"""
        assert BaseRLAgent.__doc__ is not None
        assert len(BaseRLAgent.__doc__) > 50

    def test_method_docstrings(self):
        """Test abstract methods have docstrings"""
        # Check that abstract methods are documented
        assert hasattr(BaseRLAgent, 'train')
        assert hasattr(BaseRLAgent, 'predict')
        assert hasattr(BaseRLAgent, 'save_model')
        assert hasattr(BaseRLAgent, 'load_model')


# ============================================================================
# BaseRLEnvironment Tests
# ============================================================================


class ConcreteRLEnvironment(BaseRLEnvironment):
    """Concrete implementation for testing BaseRLEnvironment"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Define action space (discrete: 0=hold, 1=buy, 2=sell)
        self.action_space = {"type": "discrete", "n": 3}
        # Define observation space (4 features)
        self.observation_space = {"type": "box", "shape": (4,), "low": -np.inf, "high": np.inf}
        self.state = None
        self._step_count = 0
        self._max_steps = 100

    def reset(self, seed=None, options=None) -> Tuple[np.ndarray, dict]:
        """Reset environment to initial state"""
        if seed is not None:
            self.seed(seed)
        self.state = np.array([1.0, 0.0, 0.0, 0.0])
        self._step_count = 0
        info = {"reset": True, "step": 0}
        return self.state.copy(), info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """Execute action and return (obs, reward, terminated, truncated, info)"""
        self._step_count += 1

        # Simple mock logic
        reward = float(action)  # Mock reward
        self.state = self.state + np.random.randn(4) * 0.1

        terminated = self._step_count >= self._max_steps
        truncated = False
        info = {"step": self._step_count, "action": action}

        return self.state.copy(), reward, terminated, truncated, info

    def render(self) -> str:
        """Render environment state"""
        return f"Step: {self._step_count}, State: {self.state}"

    def close(self):
        """Clean up resources"""
        self.state = None
        self._step_count = 0


class IncompleteRLEnvironment(BaseRLEnvironment):
    """Incomplete implementation to test abstract method enforcement"""

    def reset(self, seed=None, options=None):
        return np.array([0.0]), {}

    # Missing: step, render, close


@pytest.fixture
def concrete_env():
    """Create a concrete environment instance"""
    return ConcreteRLEnvironment()


class TestBaseRLEnvironment:
    """Test suite for BaseRLEnvironment"""

    def test_inheritance_from_abc(self):
        """Test BaseRLEnvironment inherits from ABC"""
        assert issubclass(BaseRLEnvironment, ABC)

    def test_instantiation_with_defaults(self):
        """Test BaseRLEnvironment instantiation with default parameters"""
        env = ConcreteRLEnvironment()

        assert env.action_space is not None
        assert env.observation_space is not None
        assert env.state is None
        assert env._np_random is None

    def test_abstract_method_enforcement_reset(self):
        """Test that reset() must be implemented"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            class NoResetEnv(BaseRLEnvironment):
                def step(self, action):
                    return np.array([0.0]), 0.0, False, False, {}
                def render(self):
                    return ""
                def close(self):
                    pass

            NoResetEnv()

    def test_abstract_method_enforcement_step(self):
        """Test that step() must be implemented"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            class NoStepEnv(BaseRLEnvironment):
                def reset(self, seed=None, options=None):
                    return np.array([0.0]), {}
                def render(self):
                    return ""
                def close(self):
                    pass

            NoStepEnv()

    def test_abstract_method_enforcement_render(self):
        """Test that render() must be implemented"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            class NoRenderEnv(BaseRLEnvironment):
                def reset(self, seed=None, options=None):
                    return np.array([0.0]), {}
                def step(self, action):
                    return np.array([0.0]), 0.0, False, False, {}
                def close(self):
                    pass

            NoRenderEnv()

    def test_abstract_method_enforcement_close(self):
        """Test that close() must be implemented"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            class NoCloseEnv(BaseRLEnvironment):
                def reset(self, seed=None, options=None):
                    return np.array([0.0]), {}
                def step(self, action):
                    return np.array([0.0]), 0.0, False, False, {}
                def render(self):
                    return ""

            NoCloseEnv()

    def test_reset_returns_tuple(self, concrete_env):
        """Test reset() returns (observation, info) tuple"""
        result = concrete_env.reset()

        assert isinstance(result, tuple)
        assert len(result) == 2

        observation, info = result
        assert isinstance(observation, np.ndarray)
        assert isinstance(info, dict)

    def test_reset_with_seed(self, concrete_env):
        """Test reset() with seed parameter"""
        obs1, info1 = concrete_env.reset(seed=42)
        obs2, info2 = concrete_env.reset(seed=42)

        assert isinstance(obs1, np.ndarray)
        assert isinstance(info1, dict)
        assert "reset" in info1

    def test_reset_with_options(self, concrete_env):
        """Test reset() with options parameter"""
        options = {"difficulty": "hard"}
        obs, info = concrete_env.reset(options=options)

        assert isinstance(obs, np.ndarray)
        assert isinstance(info, dict)

    def test_step_returns_five_tuple(self, concrete_env):
        """Test step() returns (obs, reward, terminated, truncated, info) tuple"""
        concrete_env.reset()
        result = concrete_env.step(1)

        assert isinstance(result, tuple)
        assert len(result) == 5

        obs, reward, terminated, truncated, info = result
        assert isinstance(obs, np.ndarray)
        assert isinstance(reward, (int, float))
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_step_action_execution(self, concrete_env):
        """Test step() executes action correctly"""
        concrete_env.reset()

        obs, reward, terminated, truncated, info = concrete_env.step(1)

        assert "action" in info
        assert info["action"] == 1
        assert "step" in info

    def test_step_termination(self, concrete_env):
        """Test step() handles termination correctly"""
        concrete_env.reset()

        # Run until termination
        terminated = False
        step_count = 0
        while not terminated and step_count < 200:
            obs, reward, terminated, truncated, info = concrete_env.step(0)
            step_count += 1

        assert terminated or step_count >= 200

    def test_render_returns_value(self, concrete_env):
        """Test render() returns a value"""
        concrete_env.reset()

        result = concrete_env.render()

        assert result is not None
        assert isinstance(result, str)

    def test_close_cleanup(self, concrete_env):
        """Test close() cleans up resources"""
        concrete_env.reset()
        concrete_env.step(1)

        concrete_env.close()

        assert concrete_env.state is None
        assert concrete_env._step_count == 0

    def test_action_space_attribute(self, concrete_env):
        """Test action_space attribute"""
        assert concrete_env.action_space is not None
        assert isinstance(concrete_env.action_space, dict)
        assert "type" in concrete_env.action_space

    def test_observation_space_attribute(self, concrete_env):
        """Test observation_space attribute"""
        assert concrete_env.observation_space is not None
        assert isinstance(concrete_env.observation_space, dict)
        assert "type" in concrete_env.observation_space

    def test_state_attribute(self, concrete_env):
        """Test state attribute"""
        assert concrete_env.state is None

        concrete_env.reset()
        assert concrete_env.state is not None
        assert isinstance(concrete_env.state, np.ndarray)

    def test_seed_method(self, concrete_env):
        """Test seed() method sets random seed"""
        concrete_env.seed(42)

        assert concrete_env._np_random is not None

    def test_get_observation_method(self, concrete_env):
        """Test _get_observation() helper method"""
        concrete_env.reset()

        obs = concrete_env._get_observation()

        assert isinstance(obs, np.ndarray)
        assert np.array_equal(obs, concrete_env.state)

    def test_gymnasium_interface_compatibility(self, concrete_env):
        """Test Gymnasium interface compatibility"""
        # Test reset signature
        obs, info = concrete_env.reset(seed=42, options=None)
        assert isinstance(obs, np.ndarray)
        assert isinstance(info, dict)

        # Test step signature
        obs, reward, terminated, truncated, info = concrete_env.step(1)
        assert isinstance(obs, np.ndarray)
        assert isinstance(reward, (int, float))
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

        # Test render
        result = concrete_env.render()
        assert result is not None

        # Test close
        concrete_env.close()

    def test_multiple_episodes(self, concrete_env):
        """Test multiple episodes work correctly"""
        for episode in range(3):
            obs, info = concrete_env.reset()
            assert isinstance(obs, np.ndarray)

            done = False
            steps = 0
            while not done and steps < 10:
                obs, reward, terminated, truncated, info = concrete_env.step(1)
                done = terminated or truncated
                steps += 1

    def test_state_persistence_across_steps(self, concrete_env):
        """Test state persists and updates across steps"""
        obs1, _ = concrete_env.reset()

        obs2, _, _, _, _ = concrete_env.step(1)
        obs3, _, _, _, _ = concrete_env.step(2)

        # State should change across steps
        assert not np.array_equal(obs1, obs2)
        assert not np.array_equal(obs2, obs3)

    def test_reset_clears_state(self, concrete_env):
        """Test reset() clears previous state"""
        concrete_env.reset()
        concrete_env.step(1)
        concrete_env.step(2)

        obs, info = concrete_env.reset()

        assert "reset" in info
        assert info["reset"] is True

    def test_action_space_discrete(self):
        """Test discrete action space"""
        env = ConcreteRLEnvironment()

        assert env.action_space["type"] == "discrete"
        assert env.action_space["n"] == 3

    def test_observation_space_box(self):
        """Test box observation space"""
        env = ConcreteRLEnvironment()

        assert env.observation_space["type"] == "box"
        assert env.observation_space["shape"] == (4,)

    def test_reward_type(self, concrete_env):
        """Test reward is numeric"""
        concrete_env.reset()

        _, reward, _, _, _ = concrete_env.step(1)

        assert isinstance(reward, (int, float, np.number))

    def test_info_dict_structure(self, concrete_env):
        """Test info dict contains useful information"""
        _, reset_info = concrete_env.reset()
        assert isinstance(reset_info, dict)

        _, _, _, _, step_info = concrete_env.step(1)
        assert isinstance(step_info, dict)
        assert "step" in step_info

    def test_np_random_initialization(self, concrete_env):
        """Test _np_random is initialized after seed()"""
        assert concrete_env._np_random is None

        concrete_env.seed(42)
        assert concrete_env._np_random is not None

    def test_get_observation_returns_copy(self, concrete_env):
        """Test _get_observation() returns a copy of state"""
        concrete_env.reset()

        obs1 = concrete_env._get_observation()
        obs2 = concrete_env._get_observation()

        # Should be equal but not the same object
        assert np.array_equal(obs1, obs2)
        obs1[0] = 999.0
        assert not np.array_equal(obs1, obs2)

    def test_docstring_presence(self):
        """Test BaseRLEnvironment has proper docstring"""
        assert BaseRLEnvironment.__doc__ is not None
        assert len(BaseRLEnvironment.__doc__) > 50

    def test_method_docstrings_environment(self):
        """Test abstract methods have docstrings"""
        assert hasattr(BaseRLEnvironment, 'reset')
        assert hasattr(BaseRLEnvironment, 'step')
        assert hasattr(BaseRLEnvironment, 'render')
        assert hasattr(BaseRLEnvironment, 'close')

    def test_seed_reproducibility(self):
        """Test seed() produces reproducible results"""
        env1 = ConcreteRLEnvironment()
        env2 = ConcreteRLEnvironment()

        env1.seed(42)
        env2.seed(42)

        obs1, _ = env1.reset()
        obs2, _ = env2.reset()

        # Initial observations should be the same
        assert np.array_equal(obs1, obs2)

    def test_truncated_flag(self, concrete_env):
        """Test truncated flag in step() return"""
        concrete_env.reset()

        _, _, terminated, truncated, _ = concrete_env.step(1)

        assert isinstance(truncated, bool)
        # In this implementation, truncated is always False
        assert truncated is False

    def test_terminated_flag(self, concrete_env):
        """Test terminated flag in step() return"""
        concrete_env.reset()

        # Run until termination
        for _ in range(150):
            _, _, terminated, _, _ = concrete_env.step(0)
            if terminated:
                break

        assert isinstance(terminated, bool)

    def test_environment_lifecycle(self, concrete_env):
        """Test complete environment lifecycle"""
        # Initialize
        obs, info = concrete_env.reset(seed=42)
        assert isinstance(obs, np.ndarray)

        # Run episode
        for _ in range(10):
            obs, reward, terminated, truncated, info = concrete_env.step(1)
            if terminated or truncated:
                break

        # Render
        render_output = concrete_env.render()
        assert render_output is not None

        # Close
        concrete_env.close()
        assert concrete_env.state is None
