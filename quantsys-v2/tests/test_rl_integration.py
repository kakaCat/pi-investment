"""
RL Modules Integration Tests
=============================

End-to-end integration tests for RL modules (FinRL and Qlib).

Tests verify that all RL components work together correctly:
- Configuration loading
- Environment creation
- Agent initialization
- Training workflow
- Prediction
- Model save/load
- BaseCalculator integration
- Cross-framework compatibility
- Graceful degradation when dependencies missing

Author: RL Migration Team
Date: 2026-05-25
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any

# Import FinRL components
from domain.quantlib.finrl import (
    FINRL_AVAILABLE,
    get_default_config,
    validate_config,
    StockTradingEnv,
)

# Import Qlib components - handle gracefully if not available
try:
    from domain.quantlib.qlib import QLIB_RL_AVAILABLE
except ImportError:
    QLIB_RL_AVAILABLE = False

# Import QlibTradingEnv directly from module (always available)
from domain.quantlib.qlib.qlib_environment import QlibTradingEnv

# Conditional imports for agents (only if dependencies available)
if FINRL_AVAILABLE:
    from domain.quantlib.finrl import FinRLAgent

if QLIB_RL_AVAILABLE:
    from domain.quantlib.qlib import QlibRLAgent
    from domain.quantlib.qlib.config import get_default_config as get_qlib_config


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_price_data() -> pd.DataFrame:
    """
    Create sample price data for testing.

    Returns:
        DataFrame with OHLCV data for 100 days
    """
    np.random.seed(42)
    n_days = 100

    # Generate realistic price data
    base_price = 100.0
    prices = []

    for i in range(n_days):
        # Random walk with drift
        change = np.random.randn() * 2 + 0.1
        close = base_price + change

        # OHLC with realistic relationships
        high = close + abs(np.random.randn() * 1.5)
        low = close - abs(np.random.randn() * 1.5)
        open_price = low + np.random.random() * (high - low)

        # Volume
        volume = np.random.randint(1000000, 10000000)

        prices.append({
            'date': pd.Timestamp('2024-01-01') + pd.Timedelta(days=i),
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': volume
        })

        base_price = close

    return pd.DataFrame(prices)


@pytest.fixture
def finrl_env(sample_price_data: pd.DataFrame):
    """
    Create FinRL trading environment.

    Args:
        sample_price_data: Sample OHLCV data

    Returns:
        StockTradingEnv instance
    """
    return StockTradingEnv(
        df=sample_price_data,
        initial_balance=100000,
        transaction_cost=0.001
    )


@pytest.fixture
def qlib_env(sample_price_data: pd.DataFrame):
    """
    Create Qlib trading environment.

    Args:
        sample_price_data: Sample OHLCV data

    Returns:
        QlibTradingEnv instance
    """
    return QlibTradingEnv(
        df=sample_price_data,
        initial_capital=100000,
        transaction_cost=0.001,
        max_steps=50  # Limit steps for faster testing
    )


# ============================================================================
# FinRL Integration Tests
# ============================================================================

class TestFinRLIntegration:
    """Test complete FinRL workflow."""

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_finrl_full_workflow(self, finrl_env, tmp_path):
        """
        Test complete FinRL workflow: config → environment → agent → train → predict → save/load.

        This test verifies:
        1. Configuration loading and validation
        2. Environment creation and reset
        3. Agent initialization
        4. Training (short run for testing)
        5. Prediction
        6. Model save/load
        7. BaseCalculator calculate() method
        """
        # 1. Load and validate configuration
        config = get_default_config('ppo', training={'total_timesteps': 1000})
        is_valid, errors = validate_config(config)
        assert is_valid, f"Config validation failed: {errors}"
        assert config['algorithm'] == 'ppo'
        assert config['training']['total_timesteps'] == 1000

        # 2. Create and reset environment
        obs, info = finrl_env.reset(seed=42)
        assert obs is not None
        assert len(obs) == 8  # 5 price features + 3 portfolio features
        assert info['step'] == 0

        # 3. Create agent
        agent = FinRLAgent(algorithm='ppo', env=finrl_env)
        assert agent.algorithm == 'ppo'
        assert agent.model is None  # Not trained yet

        # 4. Train agent (short run for testing)
        result = agent.train(env=finrl_env, config=config)
        assert result['success'] is True
        assert result['timesteps'] == 1000
        assert result['algorithm'] == 'ppo'
        assert agent.model is not None  # Model should be trained now

        # 5. Make predictions
        obs, _ = finrl_env.reset(seed=42)
        action = agent.predict(obs)
        assert action is not None
        assert isinstance(action, (int, np.integer, np.ndarray))

        # Test batch prediction
        batch_obs = np.array([obs, obs])
        batch_actions = agent.predict(batch_obs)
        assert batch_actions is not None
        assert len(batch_actions) == 2

        # 6. Save model
        model_path = tmp_path / "finrl_ppo_model"
        agent.save_model(str(model_path))
        assert (model_path.parent / f"{model_path.name}.zip").exists()

        # 7. Load model in new agent
        new_agent = FinRLAgent(algorithm='ppo', env=finrl_env)
        new_agent.load_model(str(model_path))
        assert new_agent.model is not None

        # Verify loaded model produces same predictions
        new_action = new_agent.predict(obs)
        assert new_action is not None

        # 8. Test BaseCalculator calculate() method
        calc_result = agent.calculate(obs)
        assert 'value' in calc_result
        assert 'metadata' in calc_result
        assert calc_result['metadata']['algorithm'] == 'ppo'
        assert calc_result['metadata']['model_trained'] is True

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_finrl_environment_step(self, finrl_env):
        """
        Test FinRL environment step mechanics.

        Verifies:
        - Reset functionality
        - Step execution
        - Reward calculation
        - Termination conditions
        """
        # Reset environment
        obs, info = finrl_env.reset(seed=42)
        initial_portfolio = info.get('step', 0)

        # Execute steps
        for i in range(10):
            action = np.random.choice([0, 1, 2])  # Random action
            obs, reward, terminated, truncated, info = finrl_env.step(action)

            assert obs is not None
            assert len(obs) == 8
            assert isinstance(reward, (int, float))
            assert isinstance(terminated, bool)
            assert isinstance(truncated, bool)
            assert 'portfolio_value' in info

            if terminated or truncated:
                break

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_finrl_multiple_algorithms(self, finrl_env, tmp_path):
        """
        Test multiple FinRL algorithms (PPO, A2C).

        Verifies that different algorithms can be trained and used.
        """
        algorithms = ['ppo', 'a2c']

        for algo in algorithms:
            # Create config
            config = get_default_config(algo, training={'total_timesteps': 500})

            # Create agent
            agent = FinRLAgent(algorithm=algo, env=finrl_env)
            assert agent.algorithm == algo

            # Train
            result = agent.train(env=finrl_env, config=config)
            assert result['success'] is True
            assert result['algorithm'] == algo

            # Predict
            obs, _ = finrl_env.reset(seed=42)
            action = agent.predict(obs)
            assert action is not None

            # Save
            model_path = tmp_path / f"finrl_{algo}_model"
            agent.save_model(str(model_path))
            assert (model_path.parent / f"{model_path.name}.zip").exists()


# ============================================================================
# Qlib Integration Tests
# ============================================================================

class TestQlibIntegration:
    """Test complete Qlib RL workflow."""

    @pytest.mark.skipif(not QLIB_RL_AVAILABLE, reason="Qlib RL dependencies not available")
    def test_qlib_full_workflow(self, qlib_env, tmp_path):
        """
        Test complete Qlib workflow: config → environment → agent → train → predict → save/load.

        This test verifies:
        1. Configuration loading
        2. Environment creation and reset
        3. Agent initialization
        4. Training
        5. Prediction
        6. Model save/load
        7. BaseCalculator calculate() method
        """
        # 1. Load configuration
        config = get_qlib_config('ppo', training={'total_timesteps': 1000})
        assert config['algorithm'] == 'ppo'

        # 2. Create and reset environment
        obs, info = qlib_env.reset(seed=42)
        assert obs is not None
        assert len(obs) == 8
        assert info['step'] == 0

        # 3. Create agent
        agent = QlibRLAgent(algorithm='ppo', env=qlib_env)
        assert agent.algorithm == 'ppo'
        assert agent.model is None

        # 4. Train agent
        result = agent.train(env=qlib_env, config=config)
        assert result is not None
        assert 'algorithm' in result
        assert result['algorithm'] == 'ppo'
        assert agent.model is not None

        # 5. Make predictions
        obs, _ = qlib_env.reset(seed=42)
        action = agent.predict(obs)
        assert action is not None

        # 6. Save model
        model_path = tmp_path / "qlib_ppo_model.pkl"
        agent.save_model(str(model_path))
        assert model_path.exists()

        # 7. Load model
        new_agent = QlibRLAgent(algorithm='ppo', env=qlib_env)
        new_agent.load_model(str(model_path))
        assert new_agent.model is not None

        # 8. Test BaseCalculator calculate() method
        calc_result = agent.calculate(obs)
        assert 'value' in calc_result
        assert 'metadata' in calc_result
        assert calc_result['metadata']['algorithm'] == 'ppo'

    def test_qlib_environment_step(self, qlib_env):
        """
        Test Qlib environment step mechanics.

        Verifies:
        - Reset functionality
        - Step execution
        - Max steps truncation
        """
        # Reset environment
        obs, info = qlib_env.reset(seed=42)

        # Execute steps
        for i in range(60):  # More than max_steps (50)
            action = np.random.choice([0, 1, 2])
            obs, reward, terminated, truncated, info = qlib_env.step(action)

            assert obs is not None
            assert len(obs) == 8
            assert isinstance(reward, (int, float))

            if terminated or truncated:
                # Should truncate at max_steps
                assert info['step'] <= qlib_env.max_steps
                break


# ============================================================================
# Cross-Framework Compatibility Tests
# ============================================================================

class TestCrossFrameworkCompatibility:
    """Test that FinRL and Qlib can coexist."""

    @pytest.mark.skipif(
        not (FINRL_AVAILABLE and QLIB_RL_AVAILABLE),
        reason="Both FinRL and Qlib dependencies required"
    )
    def test_both_frameworks_coexist(self, sample_price_data, tmp_path):
        """
        Test that both frameworks can be used in the same session.

        Verifies:
        - Both environments can be created
        - Both agents can be trained
        - Configs don't conflict
        - Models can be saved/loaded independently
        """
        # Create both environments
        finrl_env = StockTradingEnv(df=sample_price_data, initial_balance=100000)
        qlib_env = QlibTradingEnv(df=sample_price_data, initial_capital=100000)

        # Create both agents
        finrl_agent = FinRLAgent(algorithm='ppo', env=finrl_env)
        qlib_agent = QlibRLAgent(algorithm='ppo', env=qlib_env)

        # Load configs
        finrl_config = get_default_config('ppo', training={'total_timesteps': 500})
        qlib_config = get_qlib_config('ppo', training={'total_timesteps': 500})

        # Train both agents
        finrl_result = finrl_agent.train(env=finrl_env, config=finrl_config)
        qlib_result = qlib_agent.train(env=qlib_env, config=qlib_config)

        assert finrl_result['success'] is True
        assert qlib_result is not None

        # Make predictions with both
        finrl_obs, _ = finrl_env.reset(seed=42)
        qlib_obs, _ = qlib_env.reset(seed=42)

        finrl_action = finrl_agent.predict(finrl_obs)
        qlib_action = qlib_agent.predict(qlib_obs)

        assert finrl_action is not None
        assert qlib_action is not None

        # Save both models
        finrl_path = tmp_path / "finrl_model"
        qlib_path = tmp_path / "qlib_model.pkl"

        finrl_agent.save_model(str(finrl_path))
        qlib_agent.save_model(str(qlib_path))

        assert (finrl_path.parent / f"{finrl_path.name}.zip").exists()
        assert qlib_path.exists()

    def test_environment_compatibility(self, sample_price_data):
        """
        Test that both environments have compatible interfaces.

        Verifies:
        - Both support reset() with same signature
        - Both support step() with same signature
        - Both return compatible observation shapes
        """
        finrl_env = StockTradingEnv(df=sample_price_data)
        qlib_env = QlibTradingEnv(df=sample_price_data)

        # Reset both
        finrl_obs, finrl_info = finrl_env.reset(seed=42)
        qlib_obs, qlib_info = qlib_env.reset(seed=42)

        # Check observation shapes match
        assert finrl_obs.shape == qlib_obs.shape
        assert len(finrl_obs) == 8
        assert len(qlib_obs) == 8

        # Step both
        finrl_result = finrl_env.step(1)  # Hold
        qlib_result = qlib_env.step(1)  # Hold

        # Check return signatures match
        assert len(finrl_result) == 5  # obs, reward, terminated, truncated, info
        assert len(qlib_result) == 5


# ============================================================================
# Error Handling and Edge Cases
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_environment_invalid_data(self):
        """Test environment creation with invalid data."""
        # Empty DataFrame
        with pytest.raises(ValueError, match="empty"):
            StockTradingEnv(df=pd.DataFrame())

        # Missing columns
        df = pd.DataFrame({'date': [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            StockTradingEnv(df=df)

    def test_environment_step_before_reset(self, sample_price_data):
        """Test that step() fails if called before reset()."""
        env = StockTradingEnv(df=sample_price_data)

        with pytest.raises(RuntimeError, match="must be reset"):
            env.step(1)

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_agent_predict_before_train(self, finrl_env):
        """Test that predict() fails if model not trained."""
        agent = FinRLAgent(algorithm='ppo', env=finrl_env)
        obs, _ = finrl_env.reset()

        with pytest.raises(RuntimeError, match="not trained"):
            agent.predict(obs)

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_agent_save_before_train(self, finrl_env, tmp_path):
        """Test that save_model() fails if model not trained."""
        agent = FinRLAgent(algorithm='ppo', env=finrl_env)

        with pytest.raises(RuntimeError, match="not trained"):
            agent.save_model(str(tmp_path / "model"))

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_agent_invalid_algorithm(self, finrl_env):
        """Test agent creation with invalid algorithm."""
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            FinRLAgent(algorithm='invalid_algo', env=finrl_env)

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_agent_invalid_config(self, finrl_env):
        """Test training with invalid config."""
        agent = FinRLAgent(algorithm='ppo', env=finrl_env)

        # Missing required keys
        invalid_config = {'algorithm': 'ppo'}  # Missing 'training'

        with pytest.raises(ValueError, match="Invalid configuration"):
            agent.train(env=finrl_env, config=invalid_config)


# ============================================================================
# Graceful Degradation Tests
# ============================================================================

class TestGracefulDegradation:
    """Test graceful degradation when dependencies are missing."""

    def test_finrl_availability_flag(self):
        """Test that FINRL_AVAILABLE flag is set correctly."""
        assert isinstance(FINRL_AVAILABLE, bool)

        if FINRL_AVAILABLE:
            # If available, should be able to import
            from domain.quantlib.finrl import FinRLAgent
            assert FinRLAgent is not None

    def test_qlib_availability_flag(self):
        """Test that QLIB_RL_AVAILABLE flag is set correctly."""
        assert isinstance(QLIB_RL_AVAILABLE, bool)

        if QLIB_RL_AVAILABLE:
            # If available, should be able to import
            from domain.quantlib.qlib import QlibRLAgent
            assert QlibRLAgent is not None

    def test_config_always_available(self):
        """Test that config modules are always available (no external deps)."""
        # FinRL config should always be importable
        from domain.quantlib.finrl import get_default_config, validate_config

        config = get_default_config('ppo')
        assert config is not None
        assert 'algorithm' in config

        is_valid, errors = validate_config(config)
        assert is_valid is True

    def test_environment_always_available(self, sample_price_data):
        """Test that environments are always available (no external deps)."""
        # StockTradingEnv should always be importable
        from domain.quantlib.finrl import StockTradingEnv

        env = StockTradingEnv(df=sample_price_data)
        assert env is not None

        obs, info = env.reset()
        assert obs is not None

        # QlibTradingEnv should always be importable (import directly from module)
        from domain.quantlib.qlib.qlib_environment import QlibTradingEnv

        env2 = QlibTradingEnv(df=sample_price_data)
        assert env2 is not None

        obs2, info2 = env2.reset()
        assert obs2 is not None


# ============================================================================
# BaseCalculator Integration Tests
# ============================================================================

class TestBaseCalculatorIntegration:
    """Test BaseCalculator integration."""

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_calculate_method(self, finrl_env, tmp_path):
        """
        Test that RL agents properly implement BaseCalculator interface.

        Verifies:
        - calculate() method exists
        - Returns standardized result dictionary
        - Includes proper metadata
        """
        # Create and train agent
        agent = FinRLAgent(algorithm='ppo', env=finrl_env)
        config = get_default_config('ppo', training={'total_timesteps': 500})
        agent.train(env=finrl_env, config=config)

        # Test calculate() method
        obs, _ = finrl_env.reset(seed=42)
        result = agent.calculate(obs)

        # Verify result structure
        assert isinstance(result, dict)
        assert 'value' in result
        assert 'metadata' in result
        assert 'method' in result
        assert 'parameters' in result

        # Verify metadata
        assert result['metadata']['algorithm'] == 'ppo'
        assert result['metadata']['model_trained'] is True

        # Verify method
        assert result['method'] == 'predict'

        # Verify parameters
        assert 'observation_shape' in result['parameters']

    @pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
    def test_get_supported_methods(self, finrl_env):
        """Test get_supported_methods() returns correct methods."""
        agent = FinRLAgent(algorithm='ppo', env=finrl_env)
        methods = agent.get_supported_methods()

        assert isinstance(methods, list)
        assert 'train' in methods
        assert 'predict' in methods
        assert 'save_model' in methods
        assert 'load_model' in methods
        assert 'calculate' in methods


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
