"""
FinRL Integration Module
========================

Integration with FinRL (Financial Reinforcement Learning) framework.

FinRL provides pre-built environments, agents, and utilities for financial
reinforcement learning. This module wraps FinRL components for use in QuantSys V2.

Modules:
    - config: Configuration and hyperparameters for FinRL agents
    - finrl_agent: FinRL agent wrapper
    - finrl_environment: FinRL environment adapter

Usage:
    from domain.quantlib.finrl import FinRLAgent, FinRLEnvironment
    from domain.quantlib.finrl import get_default_config, validate_config

Requirements:
    - finrl>=0.3.6
    - stable-baselines3>=2.0.0
    - gym>=0.21.0

Author: RL Migration Team
Date: 2026-05-25
"""

import warnings

# Graceful import handling for optional FinRL dependencies
FINRL_AVAILABLE: bool = False
__all__ = ['FINRL_AVAILABLE']

# Always import config module (no external dependencies)
try:
    from .config import (
        get_default_config,
        validate_config,
        PPO_PARAMS,
        A2C_PARAMS,
        DDPG_PARAMS,
        SAC_PARAMS,
        TD3_PARAMS,
        ENV_CONFIG,
        TRAINING_CONFIG,
        ALGORITHM_PARAMS,
    )

    __all__.extend([
        'get_default_config',
        'validate_config',
        'PPO_PARAMS',
        'A2C_PARAMS',
        'DDPG_PARAMS',
        'SAC_PARAMS',
        'TD3_PARAMS',
        'ENV_CONFIG',
        'TRAINING_CONFIG',
        'ALGORITHM_PARAMS',
    ])
except ImportError as e:
    warnings.warn(
        f"Failed to import FinRL config module: {e}",
        ImportWarning
    )

# Always import callbacks module (handles missing dependencies gracefully)
try:
    from .callbacks import (
        TensorBoardCallback,
        CheckpointCallback,
        EvalCallback,
        create_callbacks,
    )

    __all__.extend([
        'TensorBoardCallback',
        'CheckpointCallback',
        'EvalCallback',
        'create_callbacks',
    ])
except ImportError as e:
    warnings.warn(
        f"Failed to import FinRL callbacks module: {e}",
        ImportWarning
    )

# Always import StockTradingEnv (only depends on BaseRLEnvironment, no external deps)
try:
    from .finrl_environment import StockTradingEnv

    __all__.extend(['StockTradingEnv'])
except ImportError as e:
    warnings.warn(
        f"Failed to import StockTradingEnv: {e}",
        ImportWarning
    )

try:
    # Check for core dependencies (our implementation doesn't need official finrl package)
    from stable_baselines3 import PPO, A2C, DDPG, SAC, TD3
    import gymnasium as gym

    FINRL_AVAILABLE = True

    # Import our FinRL components
    try:
        from .base_rl_agent import BaseRLAgent
        from .finrl_agent import FinRLAgent, ALGORITHM_MAP

        __all__.extend(['BaseRLAgent', 'FinRLAgent', 'ALGORITHM_MAP'])
    except ImportError as e:
        warnings.warn(
            f"Failed to import FinRL agent components: {e}",
            ImportWarning
        )
        FINRL_AVAILABLE = False

except ImportError:
    warnings.warn(
        "FinRL dependencies not available. "
        "Install with: pip install stable-baselines3 gymnasium torch",
        ImportWarning
    )
