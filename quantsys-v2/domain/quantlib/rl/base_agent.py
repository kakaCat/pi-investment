"""
Base RL Agent Module
====================

Abstract base class for all reinforcement learning agents in QuantSys V2.
Inherits from BaseCalculator and provides RL-specific functionality.

Author: RL Migration Team
Date: 2026-05-25
"""

from __future__ import annotations

import numpy as np
from abc import abstractmethod
from typing import Any, Dict, Optional, Union

from domain.quantlib.base_calculator import BaseCalculator


class BaseRLAgent(BaseCalculator):
    """
    Abstract base class for reinforcement learning agents.

    Inherits from BaseCalculator and adds RL-specific functionality including
    training, prediction, model persistence, and environment interaction.

    This class serves as the foundation for all RL agents in QuantSys V2,
    providing a consistent interface for different RL algorithms (DQN, PPO,
    A2C, SAC, etc.) and frameworks (FinRL, Qlib, custom implementations).

    Attributes:
        action_space: Definition of the agent's action space (discrete/continuous)
        observation_space: Definition of the agent's observation space
        model: The underlying RL model (neural network, policy, etc.)
        precision: Number of decimal places for calculations (inherited)
        risk_free_rate: Default risk-free rate (inherited)
        logger: Logger instance (inherited)

    Example:
        class DQNAgent(BaseRLAgent):
            def train(self, env, episodes=1000, **kwargs):
                # Training logic
                return {"episodes": episodes, "reward": total_reward}

            def predict(self, observation, **kwargs):
                # Prediction logic
                return self.model.predict(observation)

            def save_model(self, filepath):
                self.model.save(filepath)
                return True

            def load_model(self, filepath):
                self.model.load(filepath)
                return True

        agent = DQNAgent(action_space={"type": "discrete", "n": 3})
        agent.train(env, episodes=5000)
        action = agent.predict(observation)
    """

    def __init__(
        self,
        precision: int = 6,
        risk_free_rate: float = 0.0,
        action_space: Optional[Dict[str, Any]] = None,
        observation_space: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize base RL agent with common parameters.

        Args:
            precision: Number of decimal places for calculations (default: 6)
            risk_free_rate: Default risk-free rate for calculations (default: 0.0)
            action_space: Definition of action space (e.g., {"type": "discrete", "n": 3})
            observation_space: Definition of observation space (e.g., {"type": "box", "shape": (10,)})
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

        self.action_space = action_space
        self.observation_space = observation_space
        self.model = None

    @abstractmethod
    def train(self, env, episodes: int = 1000, **kwargs) -> Dict[str, Any]:
        """
        Train the RL agent on the given environment.

        This method must be implemented by all subclasses to define the
        training procedure for the specific RL algorithm.

        Args:
            env: Training environment (should implement gym-like interface)
            episodes: Number of training episodes (default: 1000)
            **kwargs: Additional training parameters (learning_rate, gamma, etc.)

        Returns:
            Dictionary containing training results and metrics:
                - episodes: Number of episodes trained
                - total_reward: Cumulative reward
                - avg_reward: Average reward per episode
                - loss: Training loss (if applicable)
                - Additional algorithm-specific metrics

        Example:
            results = agent.train(env, episodes=5000, learning_rate=0.001)
            print(f"Average reward: {results['avg_reward']}")
        """
        pass

    @abstractmethod
    def predict(self, observation, **kwargs) -> Union[int, np.ndarray]:
        """
        Predict action given an observation.

        This method must be implemented by all subclasses to define how
        the agent selects actions based on observations.

        Args:
            observation: Current state observation from environment
            **kwargs: Additional prediction parameters (deterministic, temperature, etc.)

        Returns:
            Action to take (int for discrete, np.ndarray for continuous)

        Example:
            observation = env.reset()
            action = agent.predict(observation, deterministic=True)
            next_obs, reward, done, info = env.step(action)
        """
        pass

    @abstractmethod
    def save_model(self, filepath: str) -> bool:
        """
        Save the trained model to disk.

        This method must be implemented by all subclasses to define how
        the model is persisted.

        Args:
            filepath: Path where the model should be saved

        Returns:
            True if save was successful, False otherwise

        Example:
            agent.train(env, episodes=5000)
            agent.save_model('/models/dqn_agent.pkl')
        """
        pass

    @abstractmethod
    def load_model(self, filepath: str) -> bool:
        """
        Load a trained model from disk.

        This method must be implemented by all subclasses to define how
        the model is loaded.

        Args:
            filepath: Path to the saved model file

        Returns:
            True if load was successful, False otherwise

        Example:
            agent = DQNAgent()
            agent.load_model('/models/dqn_agent.pkl')
            action = agent.predict(observation)
        """
        pass

    def calculate(self, observation, **kwargs) -> Dict[str, Any]:
        """
        Calculate action for given observation (adapter for BaseCalculator interface).

        This method implements the abstract calculate() method from BaseCalculator
        by calling predict() internally. It provides a consistent interface for
        using RL agents as calculators in the QuantSys pipeline.

        Args:
            observation: Current state observation from environment
            **kwargs: Additional parameters passed to predict()

        Returns:
            Standardized result dictionary containing:
                - value: Predicted action
                - method: 'predict'
                - timestamp: Calculation timestamp
                - calculator: Agent class name
                - Additional metadata

        Example:
            result = agent.calculate(observation)
            action = result['value']
            print(f"Action: {action}, Method: {result['method']}")
        """
        # Call predict to get action
        action = self.predict(observation, **kwargs)

        # Create standardized result dictionary
        result = self._create_result_dict(
            value=action,
            method='predict',
            parameters={'observation_shape': np.array(observation).shape if hasattr(observation, '__len__') else None},
            metadata={
                'action_space': self.action_space,
                'observation_space': self.observation_space
            }
        )

        return result

    def get_supported_methods(self) -> 'list[str]':
        """
        Get list of supported calculation methods.

        Returns:
            List of supported method names

        Example:
            methods = agent.get_supported_methods()
            print(f"Supported methods: {methods}")
        """
        return ['predict', 'train']
