"""
Tests for Qlib Configuration Module
====================================

Tests for Qlib RL configuration, including default configs,
validation, and algorithm-specific parameters.

Author: RL Migration Team
Date: 2026-05-25
"""

import pytest
from domain.quantlib.qlib.config import (
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


class TestQlibConfig:
    """Test suite for Qlib configuration module."""

    def test_algorithm_params_exist(self):
        """Test that all algorithm parameter dictionaries exist."""
        assert isinstance(PPO_PARAMS, dict)
        assert isinstance(DQN_PARAMS, dict)
        assert isinstance(A2C_PARAMS, dict)
        assert isinstance(SAC_PARAMS, dict)
        assert isinstance(TD3_PARAMS, dict)
        assert isinstance(ALGORITHM_PARAMS, dict)

    def test_env_config_exists(self):
        """Test that environment config exists."""
        assert isinstance(ENV_CONFIG, dict)
        assert 'initial_capital' in ENV_CONFIG
        assert 'transaction_cost' in ENV_CONFIG

    def test_training_config_exists(self):
        """Test that training config exists."""
        assert isinstance(TRAINING_CONFIG, dict)
        assert 'total_timesteps' in TRAINING_CONFIG
        assert 'eval_freq' in TRAINING_CONFIG
        assert 'save_freq' in TRAINING_CONFIG

    def test_get_default_config_ppo(self):
        """Test getting default config for PPO."""
        config = get_default_config('ppo')

        assert config['algorithm'] == 'ppo'
        assert 'env' in config
        assert 'training' in config
        assert 'learning_rate' in config
        assert config['learning_rate'] == PPO_PARAMS['learning_rate']

    def test_get_default_config_dqn(self):
        """Test getting default config for DQN."""
        config = get_default_config('dqn')

        assert config['algorithm'] == 'dqn'
        assert 'env' in config
        assert 'training' in config
        assert 'learning_rate' in config

    def test_get_default_config_a2c(self):
        """Test getting default config for A2C."""
        config = get_default_config('a2c')

        assert config['algorithm'] == 'a2c'
        assert 'env' in config
        assert 'training' in config

    def test_get_default_config_sac(self):
        """Test getting default config for SAC."""
        config = get_default_config('sac')

        assert config['algorithm'] == 'sac'
        assert 'env' in config
        assert 'training' in config

    def test_get_default_config_td3(self):
        """Test getting default config for TD3."""
        config = get_default_config('td3')

        assert config['algorithm'] == 'td3'
        assert 'env' in config
        assert 'training' in config

    def test_get_default_config_case_insensitive(self):
        """Test that algorithm names are case-insensitive."""
        config_lower = get_default_config('ppo')
        config_upper = get_default_config('PPO')
        config_mixed = get_default_config('Ppo')

        assert config_lower['algorithm'] == 'ppo'
        assert config_upper['algorithm'] == 'ppo'
        assert config_mixed['algorithm'] == 'ppo'

    def test_get_default_config_with_overrides(self):
        """Test getting config with parameter overrides."""
        config = get_default_config('ppo', learning_rate=1e-3, batch_size=128)

        assert config['learning_rate'] == 1e-3
        assert config['batch_size'] == 128

    def test_get_default_config_with_env_overrides(self):
        """Test getting config with environment overrides."""
        config = get_default_config('ppo', env={'initial_capital': 50000})

        assert config['env']['initial_capital'] == 50000
        assert 'transaction_cost' in config['env']  # Other defaults preserved

    def test_get_default_config_with_training_overrides(self):
        """Test getting config with training overrides."""
        config = get_default_config('ppo', training={'total_timesteps': 50000})

        assert config['training']['total_timesteps'] == 50000
        assert 'eval_freq' in config['training']  # Other defaults preserved

    def test_get_default_config_unsupported_algorithm(self):
        """Test that unsupported algorithm raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            get_default_config('invalid_algo')

    def test_validate_config_valid(self):
        """Test validation of valid config."""
        config = get_default_config('ppo')
        is_valid, errors = validate_config(config)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_config_missing_algorithm(self):
        """Test validation fails when algorithm is missing."""
        config = {'env': {}, 'training': {}}
        is_valid, errors = validate_config(config)

        assert is_valid is False
        assert any('algorithm' in err for err in errors)

    def test_validate_config_missing_env(self):
        """Test validation fails when env is missing."""
        config = {'algorithm': 'ppo', 'training': {}}
        is_valid, errors = validate_config(config)

        assert is_valid is False
        assert any('env' in err for err in errors)

    def test_validate_config_missing_training(self):
        """Test validation fails when training is missing."""
        config = {'algorithm': 'ppo', 'env': {}}
        is_valid, errors = validate_config(config)

        assert is_valid is False
        assert any('training' in err for err in errors)

    def test_validate_config_invalid_learning_rate(self):
        """Test validation fails for invalid learning rate."""
        config = get_default_config('ppo')
        config['learning_rate'] = -0.001
        is_valid, errors = validate_config(config)

        assert is_valid is False
        assert any('learning_rate' in err for err in errors)

    def test_validate_config_invalid_gamma(self):
        """Test validation fails for invalid gamma."""
        config = get_default_config('ppo')
        config['gamma'] = 1.5
        is_valid, errors = validate_config(config)

        assert is_valid is False
        assert any('gamma' in err for err in errors)

    def test_validate_config_invalid_initial_capital(self):
        """Test validation fails for invalid initial capital."""
        config = get_default_config('ppo')
        config['env']['initial_capital'] = -1000
        is_valid, errors = validate_config(config)

        assert is_valid is False
        assert any('initial_capital' in err for err in errors)

    def test_validate_config_invalid_transaction_cost(self):
        """Test validation fails for invalid transaction cost."""
        config = get_default_config('ppo')
        config['env']['transaction_cost'] = 1.5
        is_valid, errors = validate_config(config)

        assert is_valid is False
        assert any('transaction_cost' in err for err in errors)

    def test_validate_config_invalid_total_timesteps(self):
        """Test validation fails for invalid total timesteps."""
        config = get_default_config('ppo')
        config['training']['total_timesteps'] = -1000
        is_valid, errors = validate_config(config)

        assert is_valid is False
        assert any('total_timesteps' in err for err in errors)

    def test_config_immutability(self):
        """Test that getting config doesn't mutate defaults."""
        original_ppo = PPO_PARAMS.copy()
        config = get_default_config('ppo')
        config['learning_rate'] = 999

        # Original should be unchanged
        assert PPO_PARAMS == original_ppo

    def test_all_algorithms_in_mapping(self):
        """Test that all algorithm params are in ALGORITHM_PARAMS."""
        assert 'ppo' in ALGORITHM_PARAMS
        assert 'dqn' in ALGORITHM_PARAMS
        assert 'a2c' in ALGORITHM_PARAMS
        assert 'sac' in ALGORITHM_PARAMS
        assert 'td3' in ALGORITHM_PARAMS
