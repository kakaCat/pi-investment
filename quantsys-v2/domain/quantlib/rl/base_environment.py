"""
Base RL Environment - Abstract base class for trading environments

This module provides the base class for all reinforcement learning trading
environments. It follows the Gymnasium (OpenAI Gym) interface standard.

Author: RL Migration Team
Date: 2026-05-25
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
import numpy as np


class BaseRLEnvironment(ABC):
    """
    Abstract base class for reinforcement learning trading environments.

    This class follows the Gymnasium (OpenAI Gym) interface and provides the
    foundation for all trading environments. Subclasses must implement the
    abstract methods: reset(), step(), render(), and close().

    The environment follows the standard RL loop:
        1. Reset environment to initial state
        2. Agent observes state and selects action
        3. Environment executes action and returns (observation, reward, done, info)
        4. Repeat steps 2-3 until episode terminates
        5. Close environment to clean up resources

    Attributes:
        action_space: Definition of valid actions (e.g., {"type": "discrete", "n": 3})
        observation_space: Definition of observation structure
        state: Current environment state
        _np_random: NumPy random number generator for reproducibility

    Example:
        >>> class TradingEnv(BaseRLEnvironment):
        ...     def __init__(self):
        ...         super().__init__()
        ...         self.action_space = {"type": "discrete", "n": 3}
        ...         self.observation_space = {"type": "box", "shape": (10,)}
        ...
        ...     def reset(self, seed=None, options=None):
        ...         if seed is not None:
        ...             self.seed(seed)
        ...         self.state = np.zeros(10)
        ...         return self.state.copy(), {}
        ...
        ...     def step(self, action):
        ...         # Execute action logic
        ...         reward = 0.0
        ...         terminated = False
        ...         truncated = False
        ...         info = {}
        ...         return self.state.copy(), reward, terminated, truncated, info
        ...
        ...     def render(self):
        ...         return str(self.state)
        ...
        ...     def close(self):
        ...         self.state = None

    Notes:
        - Follows Gymnasium API (successor to OpenAI Gym)
        - step() returns 5-tuple: (observation, reward, terminated, truncated, info)
        - reset() returns 2-tuple: (observation, info)
        - terminated: episode ended naturally (goal reached, failure)
        - truncated: episode ended due to time limit or external constraint
    """

    def __init__(self):
        """
        Initialize base environment.

        Sets up core attributes that all environments need. Subclasses should
        call super().__init__() and then define their specific action_space
        and observation_space.
        """
        self.action_space: Optional[Dict[str, Any]] = None
        self.observation_space: Optional[Dict[str, Any]] = None
        self.state: Optional[np.ndarray] = None
        self._np_random: Optional[np.random.Generator] = None

    @abstractmethod
    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reset environment to initial state.

        This method must be called before the first step() call. It initializes
        the environment state and returns the initial observation.

        Args:
            seed: Random seed for reproducibility. If provided, should call
                  self.seed(seed) to set the random number generator.
            options: Optional configuration dict for reset behavior.

        Returns:
            observation: Initial observation of the environment (numpy array)
            info: Dictionary containing auxiliary information (e.g., metadata)

        Example:
            >>> obs, info = env.reset(seed=42)
            >>> print(obs.shape)
            (10,)
            >>> print(info)
            {'reset': True, 'step': 0}
        """
        pass

    @abstractmethod
    def step(
        self,
        action: Any
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Execute one step in the environment.

        Takes an action and returns the resulting observation, reward, and
        termination flags. This is the core method of the RL loop.

        Args:
            action: Action to execute. Type depends on action_space definition.
                   For discrete: int (0 to n-1)
                   For continuous: numpy array

        Returns:
            observation: New observation after executing action (numpy array)
            reward: Reward received for this step (float)
            terminated: Whether episode ended naturally (bool)
                       True if goal reached or failure occurred
            truncated: Whether episode ended due to time/resource limit (bool)
                      True if max steps reached or external constraint
            info: Dictionary with auxiliary information (e.g., metrics, debug info)

        Example:
            >>> obs, reward, terminated, truncated, info = env.step(action=1)
            >>> print(f"Reward: {reward}, Done: {terminated or truncated}")
            Reward: 0.5, Done: False

        Notes:
            - Must be called after reset()
            - terminated and truncated are separate flags (Gymnasium standard)
            - Episode ends when terminated OR truncated is True
        """
        pass

    @abstractmethod
    def render(self) -> Any:
        """
        Render the environment.

        Provides a visual or textual representation of the current environment
        state. Useful for debugging and visualization.

        Returns:
            Rendered output. Type depends on implementation:
                - str: Text description
                - np.ndarray: Image (RGB array)
                - None: Side-effect rendering (e.g., display window)

        Example:
            >>> output = env.render()
            >>> print(output)
            'Step: 10, Position: 100 shares, PnL: $1250.50'
        """
        pass

    @abstractmethod
    def close(self):
        """
        Clean up environment resources.

        Called when the environment is no longer needed. Should release any
        resources (files, connections, memory) held by the environment.

        Example:
            >>> env.close()
            >>> assert env.state is None
        """
        pass

    def seed(self, seed: int):
        """
        Set random seed for reproducibility.

        Creates a new NumPy random number generator with the given seed.
        This ensures reproducible behavior across episodes.

        Args:
            seed: Random seed (integer)

        Example:
            >>> env.seed(42)
            >>> obs1, _ = env.reset()
            >>> env.seed(42)
            >>> obs2, _ = env.reset()
            >>> assert np.array_equal(obs1, obs2)  # Reproducible
        """
        self._np_random = np.random.default_rng(seed)

    def _get_observation(self) -> np.ndarray:
        """
        Get current observation from environment state.

        Helper method to convert internal state to observation format.
        Returns a copy to prevent external modification of internal state.

        Returns:
            Current observation as numpy array (copy of state)

        Example:
            >>> obs = env._get_observation()
            >>> obs[0] = 999  # Modifying obs doesn't affect env.state
        """
        if self.state is None:
            raise RuntimeError("Environment state is None. Call reset() first.")
        return self.state.copy()
