"""
Tests for FinRL Configuration Module
=====================================

Tests configuration loading, validation, and algorithm-specific settings.

Author: RL Migration Team
Date: 2026-05-25
"""

import pytest
from typing import Any, Dict


def test_import_config_module():
    """Test that config module can be imported."""
    from domain.quantlib.finrl.config import (
        get_default_config,
        validate_config,
        PPO_PARAMS,
        A2C_PARAMS,
        DDPG_PARAMS,
        SAC_PARAMS,
        TD3_PARAMS,
        ENV_CONFIG,
        TRAINING_CONFIG,
    )

    assert PPO_PARAMS is not None
    assert A2C_PARAMS is not None
    assert DDPG_PARAMS is not None
    assert SAC_PARAMS is not None
    assert TD3_PARAMS is not None
    assert ENV_CONFIG is not None
    assert TRAINING_CONFIG is not None
    assert callable(get_default_config)
    assert callable(validate_config)


def test_ppo_default_config():
    """Test PPO algorithm default configuration."""
    from domain.quantlib.finrl.config import get_default_config

    config = get_default_config('ppo')

    assert config['algorithm'] == 'ppo'
    assert 'learning_rate' in config
    assert 'n_steps' in config
    assert 'batch_size' in config
    assert 'n_epochs' in config
    assert 'gamma' in config
    assert 'gae_lambda' in config
    assert 'clip_range' in config

    # Check specific values
    assert config['learning_rate'] == 3e-4
    assert config['n_steps'] == 2048
    assert config['batch_size'] == 64
    assert config['n_epochs'] == 10
    assert config['gamma'] == 0.99
    assert config['gae_lambda'] == 0.95
    assert config['clip_range'] == 0.2


def test_a2c_default_config():
    """Test A2C algorithm default configuration."""
    from domain.quantlib.finrl.config import get_default_config

    config = get_default_config('a2c')

    assert config['algorithm'] == 'a2c'
    assert 'learning_rate' in config
    assert 'n_steps' in config
    assert 'gamma' in config
    assert 'gae_lambda' in config

    # Check specific values
    assert config['learning_rate'] == 7e-4
    assert config['n_steps'] == 5
    assert config['gamma'] == 0.99
    assert config['gae_lambda'] == 1.0


def test_ddpg_default_config():
    """Test DDPG algorithm default configuration."""
    from domain.quantlib.finrl.config import get_default_config

    config = get_default_config('ddpg')

    assert config['algorithm'] == 'ddpg'
    assert 'learning_rate' in config
    assert 'buffer_size' in config
    assert 'learning_starts' in config
    assert 'batch_size' in config
    assert 'tau' in config
    assert 'gamma' in config

    # Check specific values
    assert config['learning_rate'] == 1e-3
    assert config['buffer_size'] == 1000000
    assert config['learning_starts'] == 100
    assert config['batch_size'] == 100
    assert config['tau'] == 0.005
    assert config['gamma'] == 0.99


def test_sac_default_config():
    """Test SAC algorithm default configuration."""
    from domain.quantlib.finrl.config import get_default_config

    config = get_default_config('sac')

    assert config['algorithm'] == 'sac'
    assert 'learning_rate' in config
    assert 'buffer_size' in config
    assert 'learning_starts' in config
    assert 'batch_size' in config
    assert 'tau' in config
    assert 'gamma' in config

    # Check specific values
    assert config['learning_rate'] == 3e-4
    assert config['buffer_size'] == 1000000
    assert config['learning_starts'] == 100
    assert config['batch_size'] == 256
    assert config['tau'] == 0.005
    assert config['gamma'] == 0.99


def test_td3_default_config():
    """Test TD3 algorithm default configuration."""
    from domain.quantlib.finrl.config import get_default_config

    config = get_default_config('td3')

    assert config['algorithm'] == 'td3'
    assert 'learning_rate' in config
    assert 'buffer_size' in config
    assert 'learning_starts' in config
    assert 'batch_size' in config
    assert 'tau' in config
    assert 'gamma' in config

    # Check specific values
    assert config['learning_rate'] == 1e-3
    assert config['buffer_size'] == 1000000
    assert config['learning_starts'] == 100
    assert config['batch_size'] == 100
    assert config['tau'] == 0.005
    assert config['gamma'] == 0.99


def test_environment_config():
    """Test environment configuration."""
    from domain.quantlib.finrl.config import get_default_config

    config = get_default_config('ppo')

    assert 'env' in config
    env_config = config['env']

    assert 'initial_balance' in env_config
    assert 'transaction_cost' in env_config
    assert 'reward_scaling' in env_config
    assert 'state_space' in env_config
    assert 'action_space' in env_config

    # Check types
    assert isinstance(env_config['initial_balance'], (int, float))
    assert isinstance(env_config['transaction_cost'], float)
    assert isinstance(env_config['reward_scaling'], (int, float))


def test_training_config():
    """Test training configuration."""
    from domain.quantlib.finrl.config import get_default_config

    config = get_default_config('ppo')

    assert 'training' in config
    training_config = config['training']

    assert 'total_timesteps' in training_config
    assert 'eval_freq' in training_config
    assert 'save_freq' in training_config
    assert 'log_interval' in training_config

    # Check types
    assert isinstance(training_config['total_timesteps'], int)
    assert isinstance(training_config['eval_freq'], int)
    assert isinstance(training_config['save_freq'], int)
    assert isinstance(training_config['log_interval'], int)


def test_invalid_algorithm():
    """Test that invalid algorithm raises error."""
    from domain.quantlib.finrl.config import get_default_config

    with pytest.raises(ValueError, match="Unsupported algorithm"):
        get_default_config('invalid_algo')


def test_case_insensitive_algorithm():
    """Test that algorithm names are case-insensitive."""
    from domain.quantlib.finrl.config import get_default_config

    config_lower = get_default_config('ppo')
    config_upper = get_default_config('PPO')
    config_mixed = get_default_config('Ppo')

    assert config_lower['algorithm'] == 'ppo'
    assert config_upper['algorithm'] == 'ppo'
    assert config_mixed['algorithm'] == 'ppo'


def test_validate_config_valid():
    """Test validation of valid configuration."""
    from domain.quantlib.finrl.config import get_default_config, validate_config

    config = get_default_config('ppo')

    # Should not raise any exception
    is_valid, errors = validate_config(config)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_config_missing_algorithm():
    """Test validation fails when algorithm is missing."""
    from domain.quantlib.finrl.config import validate_config

    config = {
        'learning_rate': 3e-4,
        'env': {'initial_balance': 100000},
        'training': {'total_timesteps': 100000}
    }

    is_valid, errors = validate_config(config)
    assert is_valid is False
    assert any('algorithm' in error.lower() for error in errors)


def test_validate_config_missing_env():
    """Test validation fails when env config is missing."""
    from domain.quantlib.finrl.config import validate_config

    config = {
        'algorithm': 'ppo',
        'learning_rate': 3e-4,
        'training': {'total_timesteps': 100000}
    }

    is_valid, errors = validate_config(config)
    assert is_valid is False
    assert any('env' in error.lower() for error in errors)


def test_validate_config_missing_training():
    """Test validation fails when training config is missing."""
    from domain.quantlib.finrl.config import validate_config

    config = {
        'algorithm': 'ppo',
        'learning_rate': 3e-4,
        'env': {'initial_balance': 100000}
    }

    is_valid, errors = validate_config(config)
    assert is_valid is False
    assert any('training' in error.lower() for error in errors)


def test_validate_config_invalid_learning_rate():
    """Test validation fails for invalid learning rate."""
    from domain.quantlib.finrl.config import get_default_config, validate_config

    config = get_default_config('ppo')
    config['learning_rate'] = -0.001  # Negative learning rate

    is_valid, errors = validate_config(config)
    assert is_valid is False
    assert any('learning_rate' in error.lower() for error in errors)


def test_validate_config_invalid_gamma():
    """Test validation fails for invalid gamma."""
    from domain.quantlib.finrl.config import get_default_config, validate_config

    config = get_default_config('ppo')
    config['gamma'] = 1.5  # Gamma should be in [0, 1]

    is_valid, errors = validate_config(config)
    assert is_valid is False
    assert any('gamma' in error.lower() for error in errors)


def test_validate_config_invalid_initial_balance():
    """Test validation fails for invalid initial balance."""
    from domain.quantlib.finrl.config import get_default_config, validate_config

    config = get_default_config('ppo')
    config['env']['initial_balance'] = -10000  # Negative balance

    is_valid, errors = validate_config(config)
    assert is_valid is False
    assert any('initial_balance' in error.lower() for error in errors)


def test_validate_config_invalid_transaction_cost():
    """Test validation fails for invalid transaction cost."""
    from domain.quantlib.finrl.config import get_default_config, validate_config

    config = get_default_config('ppo')
    config['env']['transaction_cost'] = 1.5  # Transaction cost > 1

    is_valid, errors = validate_config(config)
    assert is_valid is False
    assert any('transaction_cost' in error.lower() for error in errors)


def test_config_immutability():
    """Test that getting config returns a copy, not reference."""
    from domain.quantlib.finrl.config import get_default_config

    config1 = get_default_config('ppo')
    config2 = get_default_config('ppo')

    # Modify config1
    config1['learning_rate'] = 0.999

    # config2 should not be affected
    assert config2['learning_rate'] == 3e-4


def test_all_algorithms_have_required_fields():
    """Test that all algorithms have required configuration fields."""
    from domain.quantlib.finrl.config import get_default_config

    algorithms = ['ppo', 'a2c', 'ddpg', 'sac', 'td3']
    required_fields = ['algorithm', 'learning_rate', 'gamma', 'env', 'training']

    for algo in algorithms:
        config = get_default_config(algo)
        for field in required_fields:
            assert field in config, f"{algo} missing required field: {field}"


def test_config_types():
    """Test that configuration values have correct types."""
    from domain.quantlib.finrl.config import get_default_config

    config = get_default_config('ppo')

    # Algorithm params
    assert isinstance(config['learning_rate'], float)
    assert isinstance(config['gamma'], float)
    assert isinstance(config['n_steps'], int)
    assert isinstance(config['batch_size'], int)

    # Environment config
    assert isinstance(config['env']['initial_balance'], (int, float))
    assert isinstance(config['env']['transaction_cost'], float)

    # Training config
    assert isinstance(config['training']['total_timesteps'], int)
    assert isinstance(config['training']['eval_freq'], int)


def test_custom_config_override():
    """Test that custom parameters can override defaults."""
    from domain.quantlib.finrl.config import get_default_config

    custom_params = {
        'learning_rate': 1e-3,
        'batch_size': 128,
    }

    config = get_default_config('ppo', **custom_params)

    assert config['learning_rate'] == 1e-3
    assert config['batch_size'] == 128
    # Other params should remain default
    assert config['gamma'] == 0.99


def test_env_config_override():
    """Test that environment config can be overridden."""
    from domain.quantlib.finrl.config import get_default_config

    custom_env = {
        'initial_balance': 50000,
        'transaction_cost': 0.002,
    }

    config = get_default_config('ppo', env=custom_env)

    assert config['env']['initial_balance'] == 50000
    assert config['env']['transaction_cost'] == 0.002


def test_training_config_override():
    """Test that training config can be overridden."""
    from domain.quantlib.finrl.config import get_default_config

    custom_training = {
        'total_timesteps': 500000,
        'eval_freq': 5000,
    }

    config = get_default_config('ppo', training=custom_training)

    assert config['training']['total_timesteps'] == 500000
    assert config['training']['eval_freq'] == 5000
