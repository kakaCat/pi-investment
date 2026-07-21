"""
Qlib RL Integration Module
===========================

Integration with Qlib's reinforcement learning components.

Qlib provides RL-based portfolio management and trading strategies.
This module wraps Qlib RL components for use in QuantSys V2.

Modules:
    - config: Configuration and hyperparameters for Qlib RL algorithms
    - qlib_agent: Qlib RL agent wrapper
    - qlib_environment: Qlib RL environment adapter

Usage:
    from domain.quantlib.qlib import QlibRLAgent, QlibTradingEnv
    from domain.quantlib.qlib.config import get_default_config

    # Create environment
    env = QlibTradingEnv(df=data)

    # Create agent
    agent = QlibRLAgent(algorithm='ppo', env=env)

    # Train agent
    config = get_default_config('ppo')
    result = agent.train(env, config)

Requirements:
    - qlib>=0.9.0
    - torch>=2.0.0

Author: RL Migration Team
Date: 2026-05-25
"""

import warnings

# Graceful import handling for optional Qlib RL dependencies
QLIB_RL_AVAILABLE: bool = False
__all__ = ['QLIB_RL_AVAILABLE']

try:
    # Check for core dependencies (our implementation doesn't need official qlib package)
    import torch
    from stable_baselines3 import PPO, DQN, A2C, SAC, TD3

    QLIB_RL_AVAILABLE = True

    # Import our Qlib RL components
    try:
        from .qlib_agent import QlibRLAgent
        from .qlib_environment import QlibTradingEnv
        from .config import (
            get_default_config,
            validate_config,
            PPO_PARAMS,
            DQN_PARAMS,
            A2C_PARAMS,
            SAC_PARAMS,
            TD3_PARAMS,
            ENV_CONFIG,
            TRAINING_CONFIG,
            ALGORITHM_PARAMS,
        )

        __all__.extend([
            'QlibRLAgent',
            'QlibTradingEnv',
            'get_default_config',
            'validate_config',
            'PPO_PARAMS',
            'DQN_PARAMS',
            'A2C_PARAMS',
            'SAC_PARAMS',
            'TD3_PARAMS',
            'ENV_CONFIG',
            'TRAINING_CONFIG',
            'ALGORITHM_PARAMS',
        ])
    except ImportError as e:
        # Components not yet implemented or import error
        warnings.warn(
            f"Failed to import Qlib RL components: {e}",
            ImportWarning
        )
        QLIB_RL_AVAILABLE = False

except ImportError:
    warnings.warn(
        "Qlib RL dependencies not available. "
        "Install with: pip install torch stable-baselines3",
        ImportWarning
    )
