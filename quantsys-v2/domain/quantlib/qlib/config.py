"""
Qlib Configuration Module
==========================

Provides default settings and hyperparameters for Qlib RL agents.

This module defines configuration for:
- Algorithm-specific hyperparameters (PPO, DQN, A2C, SAC, TD3)
- Environment settings (initial capital, transaction costs, etc.)
- Training parameters (timesteps, evaluation frequency, etc.)

Usage:
    from domain.quantlib.qlib.config import get_default_config, validate_config

    # Get default config for PPO
    config = get_default_config('ppo')

    # Get config with custom parameters
    config = get_default_config('ppo', learning_rate=1e-3, batch_size=128)

    # Validate configuration
    is_valid, errors = validate_config(config)

Author: RL Migration Team
Date: 2026-05-25
"""

from typing import Any, Dict, List, Tuple
from copy import deepcopy


# Algorithm-specific hyperparameters for Qlib RL

# PPO (Proximal Policy Optimization)
PPO_PARAMS: Dict[str, Any] = {
    'learning_rate': 3e-4,
    'n_steps': 2048,
    'batch_size': 64,
    'n_epochs': 10,
    'gamma': 0.99,
    'gae_lambda': 0.95,
    'clip_range': 0.2,
    'ent_coef': 0.0,
    'vf_coef': 0.5,
}

# DQN (Deep Q-Network)
DQN_PARAMS: Dict[str, Any] = {
    'learning_rate': 1e-4,
    'buffer_size': 100000,
    'learning_starts': 1000,
    'batch_size': 32,
    'tau': 1.0,
    'gamma': 0.99,
    'train_freq': 4,
    'gradient_steps': 1,
    'target_update_interval': 1000,
    'exploration_fraction': 0.1,
    'exploration_initial_eps': 1.0,
    'exploration_final_eps': 0.05,
}

# A2C (Advantage Actor-Critic)
A2C_PARAMS: Dict[str, Any] = {
    'learning_rate': 7e-4,
    'n_steps': 5,
    'gamma': 0.99,
    'gae_lambda': 1.0,
    'ent_coef': 0.0,
    'vf_coef': 0.5,
}

# SAC (Soft Actor-Critic)
SAC_PARAMS: Dict[str, Any] = {
    'learning_rate': 3e-4,
    'buffer_size': 1000000,
    'learning_starts': 100,
    'batch_size': 256,
    'tau': 0.005,
    'gamma': 0.99,
    'train_freq': 1,
    'gradient_steps': 1,
    'ent_coef': 'auto',
}

# TD3 (Twin Delayed DDPG)
TD3_PARAMS: Dict[str, Any] = {
    'learning_rate': 1e-3,
    'buffer_size': 1000000,
    'learning_starts': 100,
    'batch_size': 100,
    'tau': 0.005,
    'gamma': 0.99,
    'train_freq': 1,
    'gradient_steps': 1,
    'policy_delay': 2,
    'target_policy_noise': 0.2,
    'target_noise_clip': 0.5,
}

# Environment configuration for Qlib trading
ENV_CONFIG: Dict[str, Any] = {
    'initial_capital': 100000,
    'transaction_cost': 0.001,
    'reward_scaling': 1.0,
    'state_space': 'default',
    'action_space': 'continuous',
    'max_steps': None,  # None means use all available data
}

# Training configuration
TRAINING_CONFIG: Dict[str, Any] = {
    'total_timesteps': 100000,
    'eval_freq': 1000,
    'save_freq': 5000,
    'log_interval': 10,
    'n_eval_episodes': 5,
    'eval_log_path': None,
}

# Algorithm parameter mapping
ALGORITHM_PARAMS: Dict[str, Dict[str, Any]] = {
    'ppo': PPO_PARAMS,
    'dqn': DQN_PARAMS,
    'a2c': A2C_PARAMS,
    'sac': SAC_PARAMS,
    'td3': TD3_PARAMS,
}


def get_default_config(
    algorithm: str,
    env: Dict[str, Any] | None = None,
    training: Dict[str, Any] | None = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Get default configuration for a specific RL algorithm.

    Args:
        algorithm: Algorithm name ('ppo', 'dqn', 'a2c', 'sac', 'td3')
        env: Optional environment config overrides
        training: Optional training config overrides
        **kwargs: Additional algorithm-specific parameter overrides

    Returns:
        Complete configuration dictionary with algorithm, env, and training settings

    Raises:
        ValueError: If algorithm is not supported

    Example:
        >>> config = get_default_config('ppo')
        >>> config = get_default_config('ppo', learning_rate=1e-3, batch_size=128)
        >>> config = get_default_config('ppo', env={'initial_capital': 50000})
    """
    # Normalize algorithm name to lowercase
    algo_lower = algorithm.lower()

    # Check if algorithm is supported
    if algo_lower not in ALGORITHM_PARAMS:
        supported = ', '.join(ALGORITHM_PARAMS.keys())
        raise ValueError(
            f"Unsupported algorithm: '{algorithm}'. "
            f"Supported algorithms: {supported}"
        )

    # Start with algorithm-specific parameters (deep copy to avoid mutation)
    config = deepcopy(ALGORITHM_PARAMS[algo_lower])

    # Add algorithm name
    config['algorithm'] = algo_lower

    # Merge environment config
    config['env'] = deepcopy(ENV_CONFIG)
    if env is not None:
        config['env'].update(env)

    # Merge training config
    config['training'] = deepcopy(TRAINING_CONFIG)
    if training is not None:
        config['training'].update(training)

    # Apply custom parameter overrides
    for key, value in kwargs.items():
        if key not in ['env', 'training', 'algorithm']:
            config[key] = value

    return config


def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate Qlib RL configuration.

    Checks for:
    - Required fields (algorithm, env, training)
    - Valid parameter ranges (learning_rate > 0, gamma in [0, 1], etc.)
    - Valid environment settings (initial_capital > 0, transaction_cost in [0, 1])
    - Valid training settings (positive timesteps, frequencies)

    Args:
        config: Configuration dictionary to validate

    Returns:
        Tuple of (is_valid, error_messages)
        - is_valid: True if config is valid, False otherwise
        - error_messages: List of validation error messages (empty if valid)

    Example:
        >>> config = get_default_config('ppo')
        >>> is_valid, errors = validate_config(config)
        >>> if not is_valid:
        ...     print("Validation errors:", errors)
    """
    errors: List[str] = []

    # Check required top-level fields
    if 'algorithm' not in config:
        errors.append("Missing required field: 'algorithm'")

    if 'env' not in config:
        errors.append("Missing required field: 'env'")
    elif not isinstance(config['env'], dict):
        errors.append("Field 'env' must be a dictionary")

    if 'training' not in config:
        errors.append("Missing required field: 'training'")
    elif not isinstance(config['training'], dict):
        errors.append("Field 'training' must be a dictionary")

    # Validate algorithm-specific parameters
    if 'learning_rate' in config:
        lr = config['learning_rate']
        if not isinstance(lr, (int, float)) or lr <= 0:
            errors.append(
                f"Invalid learning_rate: {lr}. Must be a positive number."
            )

    if 'gamma' in config:
        gamma = config['gamma']
        if not isinstance(gamma, (int, float)) or not (0 <= gamma <= 1):
            errors.append(
                f"Invalid gamma: {gamma}. Must be in range [0, 1]."
            )

    if 'n_steps' in config:
        n_steps = config['n_steps']
        if not isinstance(n_steps, int) or n_steps <= 0:
            errors.append(
                f"Invalid n_steps: {n_steps}. Must be a positive integer."
            )

    if 'batch_size' in config:
        batch_size = config['batch_size']
        if not isinstance(batch_size, int) or batch_size <= 0:
            errors.append(
                f"Invalid batch_size: {batch_size}. Must be a positive integer."
            )

    if 'buffer_size' in config:
        buffer_size = config['buffer_size']
        if not isinstance(buffer_size, int) or buffer_size <= 0:
            errors.append(
                f"Invalid buffer_size: {buffer_size}. Must be a positive integer."
            )

    if 'tau' in config:
        tau = config['tau']
        if not isinstance(tau, (int, float)) or tau <= 0:
            errors.append(
                f"Invalid tau: {tau}. Must be a positive number."
            )

    if 'n_epochs' in config:
        n_epochs = config['n_epochs']
        if not isinstance(n_epochs, int) or n_epochs <= 0:
            errors.append(
                f"Invalid n_epochs: {n_epochs}. Must be a positive integer."
            )

    # Validate environment config
    if 'env' in config and isinstance(config['env'], dict):
        env = config['env']

        if 'initial_capital' in env:
            capital = env['initial_capital']
            if not isinstance(capital, (int, float)) or capital <= 0:
                errors.append(
                    f"Invalid initial_capital: {capital}. Must be a positive number."
                )

        if 'transaction_cost' in env:
            cost = env['transaction_cost']
            if not isinstance(cost, (int, float)) or not (0 <= cost <= 1):
                errors.append(
                    f"Invalid transaction_cost: {cost}. Must be in range [0, 1]."
                )

        if 'reward_scaling' in env:
            scaling = env['reward_scaling']
            if not isinstance(scaling, (int, float)) or scaling <= 0:
                errors.append(
                    f"Invalid reward_scaling: {scaling}. Must be a positive number."
                )

    # Validate training config
    if 'training' in config and isinstance(config['training'], dict):
        training = config['training']

        if 'total_timesteps' in training:
            timesteps = training['total_timesteps']
            if not isinstance(timesteps, int) or timesteps <= 0:
                errors.append(
                    f"Invalid total_timesteps: {timesteps}. Must be a positive integer."
                )

        if 'eval_freq' in training:
            freq = training['eval_freq']
            if not isinstance(freq, int) or freq <= 0:
                errors.append(
                    f"Invalid eval_freq: {freq}. Must be a positive integer."
                )

        if 'save_freq' in training:
            freq = training['save_freq']
            if not isinstance(freq, int) or freq <= 0:
                errors.append(
                    f"Invalid save_freq: {freq}. Must be a positive integer."
                )

        if 'log_interval' in training:
            interval = training['log_interval']
            if not isinstance(interval, int) or interval <= 0:
                errors.append(
                    f"Invalid log_interval: {interval}. Must be a positive integer."
                )

        if 'n_eval_episodes' in training:
            n_eval = training['n_eval_episodes']
            if not isinstance(n_eval, int) or n_eval <= 0:
                errors.append(
                    f"Invalid n_eval_episodes: {n_eval}. Must be a positive integer."
                )

    # Return validation result
    is_valid = len(errors) == 0
    return is_valid, errors


__all__ = [
    'PPO_PARAMS',
    'DQN_PARAMS',
    'A2C_PARAMS',
    'SAC_PARAMS',
    'TD3_PARAMS',
    'ENV_CONFIG',
    'TRAINING_CONFIG',
    'ALGORITHM_PARAMS',
    'get_default_config',
    'validate_config',
]
