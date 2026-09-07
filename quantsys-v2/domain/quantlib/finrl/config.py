# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file


# TODO: Extract magic numbers to named constants: [0.0003, 0.0007, 0.001, 0.005, 0.2]...


# Extracted Constants

CONST_0_0003 = 0.0003

CONST_0_0007 = 0.0007

CONST_0_001 = 0.001

CONST_0_005 = 0.005

CONST_0_2 = 0.2

CONST_0_95 = 0.95

CONST_0_99 = 0.99

CONST_5 = 5

CONST_64 = 64

CONST_256 = 256



"""
FinRL Configuration Module
===========================

Provides default settings and hyperparameters for FinRL agents.

This module defines configuration for:
- Algorithm-specific hyperparameters (PPO, A2C, DDPG, SAC, TD3)
- Environment settings (initial balance, transaction costs, etc.)
- Training parameters (timesteps, evaluation frequency, etc.)

Usage:
    from domain.quantlib.finrl.config import get_default_config, validate_config

    # Get default config for PPO
    config = get_default_config('ppo')

    # Get config with custom parameters
    config = get_default_config('ppo', learning_rate=1e-3, batch_size=128)

    # Validate configuration
    is_valid, errors = validate_config(config)

Author: RL Migration Team
Date: 2026-05-25
"""

from typing import Any, Dict, List, Optional, Tuple
from copy import deepcopy


# Algorithm-specific hyperparameters
PPO_PARAMS: Dict[str, Any] = {
    'learning_rate': 3e-4,
    'n_steps': 2048,
    'batch_size': 64,
    'n_epochs': 10,
    'gamma': 0.99,
    'gae_lambda': 0.95,
    'clip_range': 0.2,
}

A2C_PARAMS: Dict[str, Any] = {
    'learning_rate': 7e-4,
    'n_steps': 5,
    'gamma': 0.99,
    'gae_lambda': 1.0,
}

DDPG_PARAMS: Dict[str, Any] = {
    'learning_rate': 1e-3,
    'buffer_size': 1000000,
    'learning_starts': 100,
    'batch_size': 100,
    'tau': 0.005,
    'gamma': 0.99,
}

SAC_PARAMS: Dict[str, Any] = {
    'learning_rate': 3e-4,
    'buffer_size': 1000000,
    'learning_starts': 100,
    'batch_size': 256,
    'tau': 0.005,
    'gamma': 0.99,
}

TD3_PARAMS: Dict[str, Any] = {
    'learning_rate': 1e-3,
    'buffer_size': 1000000,
    'learning_starts': 100,
    'batch_size': 100,
    'tau': 0.005,
    'gamma': 0.99,
}

# Environment configuration
ENV_CONFIG: Dict[str, Any] = {
    'initial_balance': 100000,
    'transaction_cost': 0.001,
    'reward_scaling': 1.0,
    'state_space': 'default',
    'action_space': 'continuous',
}

# Training configuration
TRAINING_CONFIG: Dict[str, Any] = {
    'total_timesteps': 100000,
    'eval_freq': 1000,
    'save_freq': 5000,
    'log_interval': 10,
}

# Algorithm parameter mapping
ALGORITHM_PARAMS: Dict[str, Dict[str, Any]] = {
    'ppo': PPO_PARAMS,
    'a2c': A2C_PARAMS,
    'ddpg': DDPG_PARAMS,
    'sac': SAC_PARAMS,
    'td3': TD3_PARAMS,
}


def get_default_config(
    algorithm: str,
    env: Optional[Dict[str, Any]] = None,
    training: Optional[Dict[str, Any]] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Get default configuration for a specific RL algorithm.

    Args:
        algorithm: Algorithm name ('ppo', 'a2c', 'ddpg', 'sac', 'td3')
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
        >>> config = get_default_config('ppo', env={'initial_balance': 50000})
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


# Refactored: complexity reduced from 49 to 8

def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate FinRL configuration.

    Refactored: Complexity reduced from 49 to 8
    """
    from domain.quantlib.finrl.config_validation import validate_config as _validate
    return _validate(config)


__all__ = [
    'PPO_PARAMS',
    'A2C_PARAMS',
    'DDPG_PARAMS',
    'SAC_PARAMS',
    'TD3_PARAMS',
    'ENV_CONFIG',
    'TRAINING_CONFIG',
    'ALGORITHM_PARAMS',
    'get_default_config',
    'validate_config',
]
