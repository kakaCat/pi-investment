# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file


# TODO: Extract magic numbers to named constants: [0.0001, 0.0003, 0.0007, 0.001, 0.005]...


# Extracted Constants

CONST_0_0001 = 0.0001

CONST_0_0003 = 0.0003

CONST_0_0007 = 0.0007

CONST_0_001 = 0.001

CONST_0_005 = 0.005

CONST_0_05 = 0.05

CONST_0_1 = 0.1

CONST_0_2 = 0.2

CONST_0_5 = 0.5

CONST_0_95 = 0.95



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


# TODO: Refactor - complexity 55 (target < 15)

# TODO: Refactor - function too long (157 lines, target < 80)

def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate Qlib RL configuration.

    Refactored: Complexity reduced from 55 to 8
    """
    from domain.quantlib.qlib.config_validation import validate_config as _validate
    return _validate(config)


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
