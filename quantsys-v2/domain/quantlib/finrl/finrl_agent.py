"""
FinRL Agent Module
==================

Wrapper for Stable-Baselines3 algorithms for financial reinforcement learning.

This module provides a unified interface for training and using RL agents
with financial trading environments. Supports PPO, A2C, DDPG, SAC, and TD3 algorithms.

Usage:
    from domain.quantlib.finrl import FinRLAgent, get_default_config

    # Create agent
    agent = FinRLAgent(algorithm='ppo', env=trading_env)

    # Train agent
    config = get_default_config('ppo', training={'total_timesteps': 100000})
    result = agent.train(env=trading_env, config=config)

    # Predict action
    observation = env.reset()
    action = agent.predict(observation)

    # Save model
    agent.save_model('./models/ppo_trading_agent')

    # Load model
    agent.load_model('./models/ppo_trading_agent')

Requirements:
    - stable-baselines3>=2.0.0
    - gym>=0.21.0 or gymnasium>=0.29.0

Author: RL Migration Team
Date: 2026-05-25
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import numpy as np

from .base_rl_agent import BaseRLAgent
from .config import get_default_config, validate_config

# Import stable-baselines3 algorithms
try:
    from stable_baselines3 import PPO, A2C, DDPG, SAC, TD3
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    # Define dummy classes for type hints
    PPO = A2C = DDPG = SAC = TD3 = None


# Algorithm mapping
ALGORITHM_MAP: Dict[str, Any] = {
    'ppo': PPO,
    'a2c': A2C,
    'ddpg': DDPG,
    'sac': SAC,
    'td3': TD3,
}


class FinRLAgent(BaseRLAgent):
    """
    FinRL agent wrapper for Stable-Baselines3 algorithms.

    Provides a unified interface for training and using RL agents with financial
    trading environments. Supports multiple algorithms (PPO, A2C, DDPG, SAC, TD3)
    with configurable hyperparameters.

    Attributes:
        algorithm: Name of the RL algorithm ('ppo', 'a2c', 'ddpg', 'sac', 'td3')
        env: Trading environment
        model: Trained SB3 model instance (None until trained)
        config: Configuration dictionary used for training

    Example:
        >>> from domain.quantlib.finrl import FinRLAgent, get_default_config
        >>> agent = FinRLAgent(algorithm='ppo', env=trading_env)
        >>> config = get_default_config('ppo')
        >>> result = agent.train(env=trading_env, config=config)
        >>> action = agent.predict(observation)
    """

    def __init__(
        self,
        algorithm: str,
        env: Any,
        precision: int = 6,
        risk_free_rate: float = 0.0
    ):
        """
        Initialize FinRLAgent.

        Args:
            algorithm: Name of the RL algorithm ('ppo', 'a2c', 'ddpg', 'sac', 'td3')
            env: Trading environment (gym or gymnasium)
            precision: Number of decimal places for calculations
            risk_free_rate: Default risk-free rate for calculations

        Raises:
            ValueError: If algorithm is not supported
            ImportError: If stable-baselines3 is not available
        """
        # Check if SB3 is available
        if not SB3_AVAILABLE:
            raise ImportError(
                "stable-baselines3 is required for FinRLAgent. "
                "Install with: pip install stable-baselines3"
            )

        # Normalize algorithm name
        algo_lower = algorithm.lower()

        # Validate algorithm
        if algo_lower not in ALGORITHM_MAP:
            supported = ', '.join(ALGORITHM_MAP.keys())
            raise ValueError(
                f"Unsupported algorithm: '{algorithm}'. "
                f"Supported algorithms: {supported}"
            )

        # Initialize base class
        super().__init__(
            algorithm=algo_lower,
            env=env,
            precision=precision,
            risk_free_rate=risk_free_rate
        )

        # Store configuration
        self.config: Optional[Dict[str, Any]] = None

    def train(
        self,
        env: Any,
        config: Dict[str, Any],
        callbacks: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Train the RL agent.

        Creates a new SB3 model with the specified configuration and trains it
        on the provided environment. Training progress can be monitored using callbacks.

        Args:
            env: Trading environment for training
            config: Configuration dictionary with hyperparameters.
                   Use get_default_config() to get default settings.
                   Required keys: 'algorithm', 'training' (with 'total_timesteps')
            callbacks: Optional list of training callbacks (e.g., CheckpointCallback)

        Returns:
            Dictionary with training results:
                - success: True if training completed successfully
                - timesteps: Total timesteps trained
                - algorithm: Algorithm name
                - config: Configuration used

        Raises:
            ValueError: If config is invalid
            RuntimeError: If training fails

        Example:
            >>> config = get_default_config('ppo', training={'total_timesteps': 50000})
            >>> callbacks = create_callbacks(log_dir='./logs', save_path='./models')
            >>> result = agent.train(env=env, config=config, callbacks=callbacks)
            >>> print(f"Trained for {result['timesteps']} timesteps")
        """
        # Validate configuration
        is_valid, errors = validate_config(config)
        if not is_valid:
            error_msg = "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

        # Store configuration
        self.config = config

        # Get algorithm class
        algo_class = ALGORITHM_MAP[self.algorithm]

        # Extract hyperparameters (exclude special keys)
        hyperparams = {
            k: v for k, v in config.items()
            if k not in ['algorithm', 'env', 'training']
        }

        # Create model
        self.logger.info(f"Creating {self.algorithm.upper()} model with hyperparameters: {hyperparams}")
        try:
            self.model = algo_class(
                policy='MlpPolicy',
                env=env,
                verbose=1,
                **hyperparams
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create {self.algorithm.upper()} model: {e}") from e

        # Get training parameters
        total_timesteps = config['training']['total_timesteps']
        log_interval = config['training'].get('log_interval', 10)

        # Train model
        self.logger.info(f"Training {self.algorithm.upper()} for {total_timesteps} timesteps")
        try:
            self.model.learn(
                total_timesteps=total_timesteps,
                callback=callbacks,
                log_interval=log_interval
            )
        except Exception as e:
            raise RuntimeError(f"Training failed: {e}") from e

        self.logger.info("Training completed successfully")

        # Return training results
        return {
            'success': True,
            'timesteps': total_timesteps,
            'algorithm': self.algorithm,
            'config': config
        }

    def predict(self, observation: np.ndarray) -> np.ndarray:
        """
        Predict action for given observation.

        Uses the trained model to predict the best action for the current state.
        Supports both single observations and batches.

        Args:
            observation: Current state observation
                        - Single: shape (obs_dim,)
                        - Batch: shape (batch_size, obs_dim)

        Returns:
            Predicted action(s):
                - Single: shape (action_dim,)
                - Batch: shape (batch_size, action_dim)

        Raises:
            RuntimeError: If model is not trained
            ValueError: If observation has invalid shape

        Example:
            >>> observation = env.reset()
            >>> action = agent.predict(observation)
            >>> next_obs, reward, done, info = env.step(action)
        """
        # Check if model is trained
        if self.model is None:
            raise RuntimeError(
                "Model not trained. Call train() before predict()."
            )

        # Validate observation
        try:
            observation = self._validate_numeric_input(observation, 'observation')
        except ValueError as e:
            raise ValueError(f"Invalid observation: {e}") from e

        # Predict action
        try:
            action, _ = self.model.predict(observation, deterministic=True)
            return action
        except Exception as e:
            raise RuntimeError(f"Prediction failed: {e}") from e

    def save_model(self, path: str) -> None:
        """
        Save trained model to disk.

        Saves the SB3 model and metadata (algorithm, config) to the specified path.
        Creates parent directories if they don't exist.

        Args:
            path: Path to save the model (without extension)
                 Model will be saved as: {path}.zip
                 Metadata will be saved as: {path}_metadata.json

        Raises:
            RuntimeError: If model is not trained
            IOError: If save fails

        Example:
            >>> agent.save_model('./models/ppo_trading_agent')
            # Creates:
            #   ./models/ppo_trading_agent.zip
            #   ./models/ppo_trading_agent_metadata.json
        """
        # Check if model is trained
        if self.model is None:
            raise RuntimeError(
                "Model not trained. Call train() before save_model()."
            )

        # Create parent directory
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # Save model
        try:
            self.model.save(str(save_path))
            self.logger.info(f"Model saved to: {save_path}.zip")
        except Exception as e:
            raise IOError(f"Failed to save model: {e}") from e

        # Save metadata
        metadata = {
            'algorithm': self.algorithm,
            'config': self.config,
            'precision': self.precision,
            'risk_free_rate': self.risk_free_rate
        }

        metadata_path = save_path.parent / f"{save_path.name}_metadata.json"
        try:
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            self.logger.info(f"Metadata saved to: {metadata_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save metadata: {e}")

    def load_model(self, path: str) -> None:
        """
        Load trained model from disk.

        Loads a previously saved SB3 model and its metadata.

        Args:
            path: Path to load the model from (without extension)
                 Expects: {path}.zip and optionally {path}_metadata.json

        Raises:
            FileNotFoundError: If model file does not exist
            IOError: If load fails

        Example:
            >>> agent = FinRLAgent(algorithm='ppo', env=env)
            >>> agent.load_model('./models/ppo_trading_agent')
            >>> action = agent.predict(observation)
        """
        # Check if model file exists
        model_path = Path(path)
        if not model_path.with_suffix('.zip').exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}.zip"
            )

        # Get algorithm class
        algo_class = ALGORITHM_MAP[self.algorithm]

        # Load model
        try:
            self.model = algo_class.load(str(model_path))
            self.logger.info(f"Model loaded from: {model_path}.zip")
        except Exception as e:
            raise IOError(f"Failed to load model: {e}") from e

        # Load metadata if available
        metadata_path = model_path.parent / f"{model_path.name}_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)

                self.config = metadata.get('config')
                self.precision = metadata.get('precision', self.precision)
                self.risk_free_rate = metadata.get('risk_free_rate', self.risk_free_rate)

                self.logger.info(f"Metadata loaded from: {metadata_path}")
            except Exception as e:
                self.logger.warning(f"Failed to load metadata: {e}")


__all__ = ['FinRLAgent', 'ALGORITHM_MAP']
