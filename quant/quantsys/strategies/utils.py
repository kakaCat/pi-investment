"""
Utility functions for strategy development.
"""
import numpy as np
import pandas as pd
from typing import Optional


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.03) -> float:
    """
    Calculate Sharpe ratio.

    Args:
        returns: Series of returns
        risk_free_rate: Annual risk-free rate (default 3%)

    Returns:
        Sharpe ratio
    """
    if len(returns) == 0 or returns.std() == 0:
        return 0.0

    excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """
    Calculate maximum drawdown.

    Args:
        equity_curve: Series of equity values

    Returns:
        Maximum drawdown as percentage
    """
    if len(equity_curve) == 0:
        return 0.0

    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    return abs(drawdown.min())


def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.03) -> float:
    """
    Calculate Sortino ratio (uses downside deviation).

    Args:
        returns: Series of returns
        risk_free_rate: Annual risk-free rate

    Returns:
        Sortino ratio
    """
    if len(returns) == 0:
        return 0.0

    excess_returns = returns - risk_free_rate / 252
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0 or downside_returns.std() == 0:
        return 0.0

    return np.sqrt(252) * excess_returns.mean() / downside_returns.std()


def calculate_calmar_ratio(returns: pd.Series, equity_curve: pd.Series) -> float:
    """
    Calculate Calmar ratio (annual return / max drawdown).

    Args:
        returns: Series of returns
        equity_curve: Series of equity values

    Returns:
        Calmar ratio
    """
    if len(returns) == 0:
        return 0.0

    annual_return = returns.mean() * 252
    max_dd = calculate_max_drawdown(equity_curve)

    if max_dd == 0:
        return 0.0

    return annual_return / max_dd


def calculate_win_rate(trades: list) -> float:
    """
    Calculate win rate from trades.

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Win rate as percentage
    """
    if not trades:
        return 0.0

    winning_trades = sum(1 for t in trades if t['pnl'] > 0)
    return winning_trades / len(trades)


def calculate_profit_factor(trades: list) -> float:
    """
    Calculate profit factor (gross profit / gross loss).

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Profit factor
    """
    if not trades:
        return 0.0

    gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))

    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def calculate_expectancy(trades: list) -> float:
    """
    Calculate expectancy (average profit per trade).

    Args:
        trades: List of trade dictionaries with 'pnl' key

    Returns:
        Expectancy
    """
    if not trades:
        return 0.0

    return sum(t['pnl'] for t in trades) / len(trades)


def calculate_kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Calculate Kelly criterion for position sizing.

    Args:
        win_rate: Win rate (0-1)
        avg_win: Average winning trade
        avg_loss: Average losing trade (positive value)

    Returns:
        Kelly percentage (0-1)
    """
    if avg_loss == 0 or win_rate == 0:
        return 0.0

    win_loss_ratio = avg_win / avg_loss
    kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio

    # Cap at 25% for safety (fractional Kelly)
    return max(0.0, min(kelly * 0.5, 0.25))


def calculate_position_size(
    capital: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss_price: float
) -> int:
    """
    Calculate position size based on risk management.

    Args:
        capital: Total capital
        risk_per_trade: Risk per trade as percentage (e.g., 0.02 for 2%)
        entry_price: Entry price
        stop_loss_price: Stop loss price

    Returns:
        Number of shares to buy
    """
    if entry_price <= stop_loss_price or entry_price == 0:
        return 0

    risk_amount = capital * risk_per_trade
    risk_per_share = entry_price - stop_loss_price
    position_size = int(risk_amount / risk_per_share)

    return max(0, position_size)


def calculate_atr_stop_loss(
    current_price: float,
    atr: float,
    multiplier: float = 2.0,
    direction: str = 'long'
) -> float:
    """
    Calculate ATR-based stop loss.

    Args:
        current_price: Current price
        atr: Average True Range
        multiplier: ATR multiplier (default 2.0)
        direction: 'long' or 'short'

    Returns:
        Stop loss price
    """
    if direction == 'long':
        return current_price - (atr * multiplier)
    else:
        return current_price + (atr * multiplier)


def calculate_risk_reward_ratio(
    entry_price: float,
    stop_loss: float,
    take_profit: float
) -> float:
    """
    Calculate risk/reward ratio.

    Args:
        entry_price: Entry price
        stop_loss: Stop loss price
        take_profit: Take profit price

    Returns:
        Risk/reward ratio
    """
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)

    if risk == 0:
        return 0.0

    return reward / risk


def generate_backtest_report(
    trades: list,
    equity_curve: pd.Series,
    initial_capital: float = 100000.0
) -> dict:
    """
    Generate comprehensive backtest report.

    Args:
        trades: List of trade dictionaries
        equity_curve: Series of equity values
        initial_capital: Initial capital

    Returns:
        Dictionary with backtest metrics
    """
    if not trades or len(equity_curve) == 0:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0
        }

    returns = equity_curve.pct_change().dropna()
    final_equity = equity_curve.iloc[-1]
    total_return = (final_equity - initial_capital) / initial_capital

    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] < 0]

    return {
        'total_trades': len(trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': calculate_win_rate(trades),
        'profit_factor': calculate_profit_factor(trades),
        'expectancy': calculate_expectancy(trades),
        'total_return': total_return,
        'total_pnl': sum(t['pnl'] for t in trades),
        'avg_win': sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0.0,
        'avg_loss': sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0.0,
        'max_win': max((t['pnl'] for t in trades), default=0.0),
        'max_loss': min((t['pnl'] for t in trades), default=0.0),
        'sharpe_ratio': calculate_sharpe_ratio(returns),
        'sortino_ratio': calculate_sortino_ratio(returns),
        'calmar_ratio': calculate_calmar_ratio(returns, equity_curve),
        'max_drawdown': calculate_max_drawdown(equity_curve),
        'avg_holding_period': sum(t['holding_period'] for t in trades) / len(trades) if trades else 0.0
    }
