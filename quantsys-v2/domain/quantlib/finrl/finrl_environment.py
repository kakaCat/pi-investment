"""
FinRL Stock Trading Environment
================================

Concrete implementation of BaseRLEnvironment for stock trading simulation.
Provides a realistic trading environment with transaction costs, portfolio
tracking, and reward calculation based on portfolio value changes.

Author: RL Migration Team
Date: 2026-05-25
"""

from typing import Any, Dict, Optional, Tuple
import numpy as np
import pandas as pd
from domain.quantlib.rl.base_environment import BaseRLEnvironment


class StockTradingEnv(BaseRLEnvironment):
    """
    Stock trading environment for reinforcement learning.

    This environment simulates a realistic stock trading scenario where an agent
    can buy, hold, or sell a single stock. The environment tracks portfolio value,
    applies transaction costs, and calculates rewards based on portfolio performance.

    Action Space:
        Discrete(3): [0=sell, 1=hold, 2=buy]

    Observation Space:
        Box: [open, high, low, close, volume, balance, holdings, portfolio_value]

    Reward:
        Change in portfolio value from previous step

    Episode Termination:
        - Data exhausted (reached end of price history)
        - Portfolio value <= 0 (bankruptcy)

    Attributes:
        df: DataFrame with price data (columns: date, open, high, low, close, volume)
        initial_balance: Starting cash amount
        transaction_cost: Transaction fee as decimal (0.001 = 0.1%)
        balance: Current cash balance
        holdings: Current number of shares held
        portfolio_value: Total portfolio value (balance + holdings * current_price)
        current_step: Current time step in the episode
        previous_portfolio_value: Portfolio value from previous step (for reward calculation)

    Example:
        >>> df = pd.DataFrame({
        ...     'date': pd.date_range('2024-01-01', periods=100),
        ...     'open': np.random.randn(100) + 100,
        ...     'high': np.random.randn(100) + 101,
        ...     'low': np.random.randn(100) + 99,
        ...     'close': np.random.randn(100) + 100,
        ...     'volume': np.random.randint(1000000, 10000000, 100)
        ... })
        >>> env = StockTradingEnv(df, initial_balance=100000, transaction_cost=0.001)
        >>> obs, info = env.reset(seed=42)
        >>> obs, reward, terminated, truncated, info = env.step(action=2)  # Buy
        >>> env.close()
    """

    def __init__(
        self,
        df: pd.DataFrame,
        initial_balance: float = 100000,
        transaction_cost: float = 0.001
    ):
        """
        Initialize stock trading environment.

        Args:
            df: DataFrame with columns [date, open, high, low, close, volume]
            initial_balance: Starting cash amount (default: 100000)
            transaction_cost: Transaction fee as decimal (default: 0.001 = 0.1%)

        Raises:
            ValueError: If df is empty or missing required columns
        """
        super().__init__()

        # Validate input data
        if df is None or len(df) == 0:
            raise ValueError("DataFrame cannot be empty")

        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"DataFrame missing required columns: {missing_columns}")

        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.transaction_cost = transaction_cost

        # Define action space: 0=sell, 1=hold, 2=buy
        self.action_space = {
            'type': 'discrete',
            'n': 3
        }

        # Define observation space: [open, high, low, close, volume, balance, holdings, portfolio_value]
        self.observation_space = {
            'type': 'box',
            'shape': (8,),  # 5 price features + 3 portfolio features
            'low': np.array([0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32),
            'high': np.array([np.inf] * 8, dtype=np.float32)
        }

        # Portfolio state (initialized in reset)
        self.balance: float = 0
        self.holdings: float = 0
        self.portfolio_value: float = 0
        self.current_step: int = 0
        self.previous_portfolio_value: float = 0

        # Flag to track if reset has been called
        self._reset_called: bool = False

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reset environment to initial state.

        Args:
            seed: Random seed for reproducibility
            options: Optional configuration dict (unused)

        Returns:
            observation: Initial observation [open, high, low, close, volume, balance, holdings, portfolio_value]
            info: Dictionary with metadata {'step': 0}
        """
        if seed is not None:
            self.seed(seed)

        # Reset portfolio state
        self.balance = self.initial_balance
        self.holdings = 0
        self.portfolio_value = self.initial_balance
        self.current_step = 0
        self.previous_portfolio_value = self.initial_balance
        self._reset_called = True

        # Get initial observation
        observation = self._get_observation()
        self.state = observation

        info = {
            'step': self.current_step
        }

        return observation, info

    def step(
        self,
        action: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Execute one step in the environment.

        Args:
            action: Action to execute (0=sell, 1=hold, 2=buy)

        Returns:
            observation: New observation after executing action
            reward: Reward (change in portfolio value)
            terminated: Whether episode ended naturally (bankruptcy or data exhausted)
            truncated: Whether episode ended due to time limit (always False here)
            info: Dictionary with metadata

        Raises:
            RuntimeError: If called before reset()
            ValueError: If action is invalid
        """
        if not self._reset_called:
            raise RuntimeError("Environment must be reset before calling step(). Call reset() first.")

        if action not in [0, 1, 2]:
            raise ValueError(f"Invalid action: {action}. Must be 0 (sell), 1 (hold), or 2 (buy).")

        # Get current price
        current_price = self.df.iloc[self.current_step]['close']

        # Execute action
        if action == 2:  # Buy
            self._execute_buy(current_price)
        elif action == 0:  # Sell
            self._execute_sell(current_price)
        # action == 1 (hold) does nothing

        # Move to next step
        self.current_step += 1

        # Calculate portfolio value
        if self.current_step < len(self.df):
            next_price = self.df.iloc[self.current_step]['close']
            self.portfolio_value = self.balance + self.holdings * next_price
        else:
            # End of data, use last known price
            self.portfolio_value = self.balance + self.holdings * current_price

        # Calculate reward (change in portfolio value)
        reward = self.portfolio_value - self.previous_portfolio_value
        self.previous_portfolio_value = self.portfolio_value

        # Check termination conditions
        terminated = False
        truncated = False

        # Terminate if portfolio value <= 0 (bankruptcy)
        if self.portfolio_value <= 0:
            terminated = True

        # Terminate if we've reached the end of the data
        if self.current_step >= len(self.df):
            terminated = True

        # Get new observation
        observation = self._get_observation()
        self.state = observation

        # Build info dict
        info = {
            'step': self.current_step,
            'portfolio_value': self.portfolio_value,
            'balance': self.balance,
            'holdings': self.holdings
        }

        return observation, reward, terminated, truncated, info

    def _execute_buy(self, price: float):
        """
        Execute buy action.

        Buys as many shares as possible with current balance, accounting
        for transaction costs.

        Args:
            price: Current stock price
        """
        # Calculate how many shares we can buy
        # balance = shares * price * (1 + transaction_cost)
        # shares = balance / (price * (1 + transaction_cost))
        max_shares = self.balance / (price * (1 + self.transaction_cost))

        if max_shares > 0:
            # Buy shares
            shares_to_buy = int(max_shares)  # Buy whole shares only
            if shares_to_buy > 0:
                cost = shares_to_buy * price * (1 + self.transaction_cost)
                self.balance -= cost
                self.holdings += shares_to_buy

    def _execute_sell(self, price: float):
        """
        Execute sell action.

        Sells all holdings, accounting for transaction costs.

        Args:
            price: Current stock price
        """
        if self.holdings > 0:
            # Sell all holdings
            proceeds = self.holdings * price * (1 - self.transaction_cost)
            self.balance += proceeds
            self.holdings = 0

    def _get_observation(self) -> np.ndarray:
        """
        Get current observation from environment state.

        Returns:
            Observation array: [open, high, low, close, volume, balance, holdings, portfolio_value]
        """
        if self.current_step >= len(self.df):
            # If we've exhausted data, return last observation
            step = len(self.df) - 1
        else:
            step = self.current_step

        row = self.df.iloc[step]

        observation = np.array([
            row['open'],
            row['high'],
            row['low'],
            row['close'],
            row['volume'],
            self.balance,
            self.holdings,
            self.portfolio_value
        ], dtype=np.float32)

        return observation

    def render(self) -> str:
        """
        Render the environment state as a string.

        Returns:
            String representation of current state
        """
        if self.current_step >= len(self.df):
            step = len(self.df) - 1
        else:
            step = self.current_step

        current_price = self.df.iloc[step]['close']

        output = (
            f"Step: {self.current_step}/{len(self.df)}\n"
            f"Current Price: ${current_price:.2f}\n"
            f"Balance: ${self.balance:.2f}\n"
            f"Holdings: {self.holdings:.0f} shares\n"
            f"Portfolio Value: ${self.portfolio_value:.2f}\n"
            f"Return: {((self.portfolio_value / self.initial_balance - 1) * 100):.2f}%"
        )

        return output

    def close(self):
        """
        Clean up environment resources.

        Resets state to None to indicate environment is closed.
        """
        self.state = None
        self._reset_called = False
