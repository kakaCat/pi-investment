"""
Base RL Agent Module
====================

Abstract base class for reinforcement learning agents.

Provides a common interface for all RL agents in the QuantSys V2 system.
Inherits from BaseCalculator to integrate with the quantitative calculation framework.

Author: RL Migration Team
Date: 2026-05-25
"""

from abc import abstractmethod
from typing import Any, Dict, List, Optional
import numpy as np

from domain.quantlib.core.base_calculator import BaseCalculator


class BaseRLAgent(BaseCalculator):
    """
    Abstract base class for reinforcement learning agents.

    Provides a unified interface for training, prediction, and model management.
    All RL agents should inherit from this class and implement the abstract methods.

    Attributes:
        algorithm: Name of the RL algorithm (e.g., 'ppo', 'a2c', 'ddpg')
        env: Training environment
        model: Trained model instance (None until trained)

    Example:
        >>> class MyRLAgent(BaseRLAgent):
        ...     def train(self, env, config, callbacks=None):
        ...         # Implementation
        ...         pass
        ...
        ...     def predict(self, observation):
        ...         # Implementation
        ...         pass
        ...
        ...     def save_model(self, path):
        ...         # Implementation
        ...         pass
        ...
        ...     def load_model(self, path):
        ...         # Implementation
        ...         pass
    """

    def __init__(
        self,
        algorithm: str,
        env: Any,
        precision: int = 6,
        risk_free_rate: float = 0.0
    ):
        """
        Initialize BaseRLAgent.

        Args:
            algorithm: Name of the RL algorithm
            env: Training environment
            precision: Number of decimal places for calculations (inherited from BaseCalculator)
            risk_free_rate: Default risk-free rate (inherited from BaseCalculator)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)
        self.algorithm = algorithm
        self.env = env
        self.model: Optional[Any] = None

    @abstractmethod
    def train(
        self,
        env: Any,
        config: Dict[str, Any],
        callbacks: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Train the RL agent.

        Args:
            env: Training environment
            config: Configuration dictionary with hyperparameters
            callbacks: Optional list of training callbacks

        Returns:
            Dictionary with training results and metrics

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        pass

    @abstractmethod
    def predict(self, observation: np.ndarray) -> np.ndarray:
        """
        Predict action for given observation.

        Args:
            observation: Current state observation (single or batch)

        Returns:
            Predicted action(s)

        Raises:
            NotImplementedError: Must be implemented by subclass
            RuntimeError: If model is not trained
        """
        pass

    @abstractmethod
    def save_model(self, path: str) -> None:
        """
        Save trained model to disk.

        Args:
            path: Path to save the model

        Raises:
            NotImplementedError: Must be implemented by subclass
            RuntimeError: If model is not trained
        """
        pass

    @abstractmethod
    def load_model(self, path: str) -> None:
        """
        Load trained model from disk.

        Args:
            path: Path to load the model from

        Raises:
            NotImplementedError: Must be implemented by subclass
            FileNotFoundError: If model file does not exist
        """
        pass

    def calculate(self, observation: np.ndarray, **kwargs: Any) -> Dict[str, Any]:
        """
        Calculate action for given observation (BaseCalculator interface).

        This method provides the BaseCalculator interface for RL agents.
        It wraps the predict() method and returns a standardized result dictionary.

        Args:
            observation: Current state observation
            **kwargs: Additional parameters (unused)

        Returns:
            Standardized result dictionary with action and metadata

        Example:
            >>> agent = MyRLAgent(algorithm='ppo', env=env)
            >>> agent.train(env, config)
            >>> result = agent.calculate(observation)
            >>> action = result['value']
        """
        # Call predict to get action
        action = self.predict(observation)

        # Create standardized result using BaseCalculator method
        result = self._create_result_dict(
            value=action,
            method='predict',
            parameters={'observation_shape': observation.shape},
            metadata={
                'algorithm': self.algorithm,
                'model_trained': self.model is not None
            }
        )

        return result

    def get_supported_methods(self) -> List[str]:
        """
        Get list of supported methods.

        Returns:
            List of method names supported by this agent

        Example:
            >>> agent = MyRLAgent(algorithm='ppo', env=env)
            >>> methods = agent.get_supported_methods()
            >>> print(methods)
            ['train', 'predict', 'save_model', 'load_model', 'calculate']
        """
        return ['train', 'predict', 'save_model', 'load_model', 'calculate']


__all__ = ['BaseRLAgent']
