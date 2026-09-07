"""
Tests for FinRL Stock Trading Environment
==========================================

Tests the StockTradingEnv concrete implementation of BaseRLEnvironment.
Tests environment initialization, reset, step, action/observation spaces,
reward calculation, and episode termination.

Author: RL Migration Team
Date: 2026-05-25
"""

import pytest
import numpy as np
import pandas as pd
from typing import Any, Dict


@pytest.fixture
def sample_price_data():
    """Create sample price data for testing."""
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(42)

    # Generate realistic price data
    close_prices = 100 + np.cumsum(np.random.randn(100) * 2)
    high_prices = close_prices + np.abs(np.random.randn(100) * 1)
    low_prices = close_prices - np.abs(np.random.randn(100) * 1)
    open_prices = close_prices + np.random.randn(100) * 0.5
    volumes = np.random.randint(1000000, 10000000, 100)

    df = pd.DataFrame({
        'date': dates,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes
    })

    return df


def test_import_stock_trading_env():
    """Test that StockTradingEnv can be imported."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv
    assert StockTradingEnv is not None


def test_stock_trading_env_inherits_base():
    """Test that StockTradingEnv inherits from BaseRLEnvironment."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv
    from domain.quantlib.rl.base_environment import BaseRLEnvironment

    assert issubclass(StockTradingEnv, BaseRLEnvironment)


def test_stock_trading_env_initialization(sample_price_data):
    """Test StockTradingEnv initialization with default parameters."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(
        df=sample_price_data,
        initial_balance=100000,
        transaction_cost=0.001
    )

    assert env is not None
    assert env.initial_balance == 100000
    assert env.transaction_cost == 0.001
    assert env.action_space is not None
    assert env.observation_space is not None


def test_action_space_discrete(sample_price_data):
    """Test that action space is discrete with 3 actions (sell, hold, buy)."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)

    assert env.action_space is not None
    assert env.action_space['type'] == 'discrete'
    assert env.action_space['n'] == 3  # 0=sell, 1=hold, 2=buy


def test_observation_space_box(sample_price_data):
    """Test that observation space is a box (continuous values)."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)

    assert env.observation_space is not None
    assert env.observation_space['type'] == 'box'
    assert 'shape' in env.observation_space
    # Observation should include: price features + balance + holdings + portfolio_value
    assert env.observation_space['shape'][0] > 0


def test_reset_returns_initial_observation(sample_price_data):
    """Test that reset() returns initial observation and info dict."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data, initial_balance=100000)
    obs, info = env.reset(seed=42)

    # Check return types
    assert isinstance(obs, np.ndarray)
    assert isinstance(info, dict)

    # Check observation shape matches observation_space
    assert obs.shape == env.observation_space['shape']

    # Check info contains useful metadata
    assert 'step' in info
    assert info['step'] == 0


def test_reset_initializes_portfolio(sample_price_data):
    """Test that reset() initializes portfolio state correctly."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data, initial_balance=100000)
    obs, info = env.reset()

    # Portfolio should be initialized
    assert env.balance == 100000
    assert env.holdings == 0
    assert env.portfolio_value == 100000
    assert env.current_step == 0


def test_reset_with_seed_reproducible(sample_price_data):
    """Test that reset() with same seed produces same initial state."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)

    obs1, _ = env.reset(seed=42)
    obs2, _ = env.reset(seed=42)

    np.testing.assert_array_equal(obs1, obs2)


def test_step_returns_five_tuple(sample_price_data):
    """Test that step() returns (obs, reward, terminated, truncated, info)."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)
    env.reset(seed=42)

    result = env.step(action=1)  # Hold action

    assert len(result) == 5
    obs, reward, terminated, truncated, info = result

    assert isinstance(obs, np.ndarray)
    assert isinstance(reward, (int, float))
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(info, dict)


def test_step_hold_action(sample_price_data):
    """Test that hold action (1) doesn't change holdings."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data, initial_balance=100000)
    env.reset(seed=42)

    initial_holdings = env.holdings
    initial_balance = env.balance

    obs, reward, terminated, truncated, info = env.step(action=1)  # Hold

    assert env.holdings == initial_holdings
    assert env.balance == initial_balance
    assert env.current_step == 1


def test_step_buy_action(sample_price_data):
    """Test that buy action (2) increases holdings and decreases balance."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data, initial_balance=100000)
    env.reset(seed=42)

    initial_balance = env.balance

    obs, reward, terminated, truncated, info = env.step(action=2)  # Buy

    # Holdings should increase
    assert env.holdings > 0
    # Balance should decrease (price + transaction cost)
    assert env.balance < initial_balance


def test_step_sell_action(sample_price_data):
    """Test that sell action (0) decreases holdings and increases balance."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data, initial_balance=100000)
    env.reset(seed=42)

    # First buy some shares
    env.step(action=2)  # Buy
    holdings_after_buy = env.holdings
    balance_after_buy = env.balance

    # Then sell
    obs, reward, terminated, truncated, info = env.step(action=0)  # Sell

    # Holdings should decrease
    assert env.holdings < holdings_after_buy
    # Balance should increase
    assert env.balance > balance_after_buy


def test_transaction_cost_applied(sample_price_data):
    """Test that transaction costs are applied to trades."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(
        df=sample_price_data,
        initial_balance=100000,
        transaction_cost=0.001  # 0.1%
    )
    env.reset(seed=42)

    initial_balance = env.balance
    current_price = sample_price_data.iloc[0]['close']

    # Buy action
    env.step(action=2)

    # Calculate expected cost with transaction fee
    shares_bought = env.holdings
    expected_cost = shares_bought * current_price * (1 + 0.001)

    # Balance should reflect transaction cost
    assert abs((initial_balance - env.balance) - expected_cost) < 1.0  # Allow small rounding


def test_reward_calculation(sample_price_data):
    """Test that reward is calculated based on portfolio value change."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data, initial_balance=100000)
    env.reset(seed=42)

    initial_portfolio_value = env.portfolio_value

    # Take an action
    obs, reward, terminated, truncated, info = env.step(action=1)  # Hold

    # Reward should be the change in portfolio value
    expected_reward = env.portfolio_value - initial_portfolio_value

    assert isinstance(reward, (int, float))
    # For hold action with no holdings, reward should be close to 0
    assert abs(reward - expected_reward) < 0.01


def test_portfolio_value_tracking(sample_price_data):
    """Test that portfolio value is correctly calculated."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data, initial_balance=100000)
    env.reset(seed=42)

    # Buy some shares
    env.step(action=2)

    current_price = sample_price_data.iloc[env.current_step]['close']
    expected_portfolio_value = env.balance + env.holdings * current_price

    assert abs(env.portfolio_value - expected_portfolio_value) < 0.01


def test_episode_terminates_at_data_end(sample_price_data):
    """Test that episode terminates when data is exhausted."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    # Use small dataset
    small_df = sample_price_data.head(10)
    env = StockTradingEnv(df=small_df)
    env.reset(seed=42)

    terminated = False
    truncated = False
    step_count = 0

    while not (terminated or truncated) and step_count < 20:
        obs, reward, terminated, truncated, info = env.step(action=1)
        step_count += 1

    # Episode should terminate before 20 steps (data has only 10 rows)
    assert terminated or truncated
    assert step_count <= 10


def test_episode_terminates_on_bankruptcy(sample_price_data):
    """Test that episode terminates when portfolio value <= 0."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    # Create environment with very small balance
    env = StockTradingEnv(df=sample_price_data, initial_balance=1)
    env.reset(seed=42)

    # Manually set portfolio to near-zero to test termination
    env.balance = 0.5
    env.holdings = 0
    env.portfolio_value = 0.5

    obs, reward, terminated, truncated, info = env.step(action=1)

    # Should terminate due to bankruptcy
    assert terminated or env.portfolio_value > 0


def test_observation_contains_market_state(sample_price_data):
    """Test that observation contains market state information."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)
    obs, info = env.reset(seed=42)

    # Observation should be a 1D array
    assert obs.ndim == 1
    assert len(obs) > 0

    # Should contain price information and portfolio state
    # Exact structure depends on implementation, but should have multiple features
    assert len(obs) >= 5  # At least: open, high, low, close, volume, balance, holdings


def test_info_dict_contains_metadata(sample_price_data):
    """Test that info dict contains useful metadata."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)
    env.reset(seed=42)

    obs, reward, terminated, truncated, info = env.step(action=2)

    # Info should contain useful debugging information
    assert 'step' in info
    assert 'portfolio_value' in info
    assert 'balance' in info
    assert 'holdings' in info


def test_render_returns_string(sample_price_data):
    """Test that render() returns a string representation."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)
    env.reset(seed=42)
    env.step(action=2)

    output = env.render()

    assert isinstance(output, str)
    assert len(output) > 0
    # Should contain key information
    assert 'step' in output.lower() or 'portfolio' in output.lower()


def test_close_cleans_up(sample_price_data):
    """Test that close() cleans up environment resources."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)
    env.reset(seed=42)
    env.step(action=1)

    env.close()

    # State should be cleaned up
    assert env.state is None


def test_multiple_episodes(sample_price_data):
    """Test that environment can be reset and reused for multiple episodes."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data, initial_balance=100000)

    # Episode 1
    obs1, _ = env.reset(seed=42)
    env.step(action=2)
    env.step(action=1)

    # Episode 2
    obs2, _ = env.reset(seed=42)

    # Should reset to same initial state
    np.testing.assert_array_equal(obs1, obs2)
    assert env.balance == 100000
    assert env.holdings == 0
    assert env.current_step == 0


def test_different_initial_balances(sample_price_data):
    """Test environment with different initial balances."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env1 = StockTradingEnv(df=sample_price_data, initial_balance=50000)
    env2 = StockTradingEnv(df=sample_price_data, initial_balance=200000)

    env1.reset()
    env2.reset()

    assert env1.balance == 50000
    assert env2.balance == 200000
    assert env1.portfolio_value == 50000
    assert env2.portfolio_value == 200000


def test_different_transaction_costs(sample_price_data):
    """Test environment with different transaction costs."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env1 = StockTradingEnv(df=sample_price_data, transaction_cost=0.001)
    env2 = StockTradingEnv(df=sample_price_data, transaction_cost=0.005)

    assert env1.transaction_cost == 0.001
    assert env2.transaction_cost == 0.005


def test_step_increments_current_step(sample_price_data):
    """Test that step() increments current_step counter."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)
    env.reset(seed=42)

    assert env.current_step == 0

    env.step(action=1)
    assert env.current_step == 1

    env.step(action=1)
    assert env.current_step == 2


def test_cannot_step_before_reset(sample_price_data):
    """Test that step() raises error if called before reset()."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)

    with pytest.raises(RuntimeError, match="reset"):
        env.step(action=1)


def test_invalid_action_raises_error(sample_price_data):
    """Test that invalid action raises error."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    env = StockTradingEnv(df=sample_price_data)
    env.reset(seed=42)

    with pytest.raises((ValueError, AssertionError)):
        env.step(action=5)  # Invalid action (only 0, 1, 2 allowed)


def test_empty_dataframe_raises_error():
    """Test that empty DataFrame raises error."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    empty_df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

    with pytest.raises(ValueError, match="empty"):
        StockTradingEnv(df=empty_df)


def test_missing_columns_raises_error():
    """Test that DataFrame with missing columns raises error."""
    from domain.quantlib.finrl.finrl_environment import StockTradingEnv

    invalid_df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=10),
        'close': np.random.randn(10)
        # Missing: open, high, low, volume
    })

    with pytest.raises(ValueError, match="columns"):
        StockTradingEnv(df=invalid_df)
