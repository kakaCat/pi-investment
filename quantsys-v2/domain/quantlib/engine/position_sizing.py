"""
Position Sizing Strategies

Implements various position sizing algorithms for portfolio management.
Controls how much capital to allocate to each trade.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import math

logger = logging.getLogger(__name__)


class PositionSizer(ABC):
    """Base class for position sizing strategies"""

    @abstractmethod
    def calculate_position_size(
        self,
        price: float,
        available_capital: float,
        total_equity: float,
        signal_data: Dict[str, Any] = None,
        portfolio_data: Dict[str, Any] = None
    ) -> int:
        """
        Calculate position size in shares.

        Args:
            price: Current price per share
            available_capital: Available cash
            total_equity: Total portfolio value
            signal_data: Signal information (confidence, etc.)
            portfolio_data: Portfolio state (positions, risk metrics, etc.)

        Returns:
            Number of shares to trade (rounded to lot size)
        """
        pass

    @staticmethod
    def _round_to_lot(shares: int, lot_size: int = 100) -> int:
        """
        Round shares to lot size.

        Args:
            shares: Raw share count
            lot_size: Lot size (default 100 for A-shares)

        Returns:
            Shares rounded down to nearest lot
        """
        return (shares // lot_size) * lot_size


class FixedPositionSizer(PositionSizer):
    """
    Fixed amount position sizer.

    Allocates a fixed dollar amount to each trade.
    Simple but doesn't scale with portfolio size.
    """

    def __init__(self, fixed_amount: float = 100000, lot_size: int = 100):
        """
        Initialize fixed position sizer.

        Args:
            fixed_amount: Fixed dollar amount per trade (default 100,000)
            lot_size: Lot size for rounding (default 100)
        """
        if fixed_amount <= 0:
            raise ValueError("Fixed amount must be positive")
        if lot_size <= 0:
            raise ValueError("Lot size must be positive")

        self.fixed_amount = fixed_amount
        self.lot_size = lot_size

        logger.info(
            f"FixedPositionSizer initialized: amount={fixed_amount:,.0f}, "
            f"lot_size={lot_size}"
        )

    def calculate_position_size(
        self,
        price: float,
        available_capital: float,
        total_equity: float,
        signal_data: Dict[str, Any] = None,
        portfolio_data: Dict[str, Any] = None
    ) -> int:
        """
        Calculate position size using fixed amount.

        Returns shares worth approximately fixed_amount.
        """
        if price <= 0:
            return 0

        # Use the lesser of fixed amount or available capital
        amount = min(self.fixed_amount, available_capital)

        shares = int(amount / price)
        return self._round_to_lot(shares, self.lot_size)


class FixedPercentSizer(PositionSizer):
    """
    Fixed percentage position sizer.

    Allocates a fixed percentage of total equity to each trade.
    Scales with portfolio size.
    """

    def __init__(
        self,
        percent: float = 0.1,
        lot_size: int = 100,
        max_percent: float = 0.3
    ):
        """
        Initialize fixed percent sizer.

        Args:
            percent: Percentage of equity per trade (default 10%)
            lot_size: Lot size for rounding (default 100)
            max_percent: Maximum percentage cap (default 30%)
        """
        if not 0 < percent <= 1:
            raise ValueError("Percent must be between 0 and 1")
        if not 0 < max_percent <= 1:
            raise ValueError("Max percent must be between 0 and 1")
        if lot_size <= 0:
            raise ValueError("Lot size must be positive")

        self.percent = percent
        self.lot_size = lot_size
        self.max_percent = max_percent

        logger.info(
            f"FixedPercentSizer initialized: percent={percent:.1%}, "
            f"max={max_percent:.1%}, lot_size={lot_size}"
        )

    def calculate_position_size(
        self,
        price: float,
        available_capital: float,
        total_equity: float,
        signal_data: Dict[str, Any] = None,
        portfolio_data: Dict[str, Any] = None
    ) -> int:
        """
        Calculate position size using fixed percentage of equity.

        Respects available capital and max percentage constraints.
        """
        if price <= 0 or total_equity <= 0:
            return 0

        # Target amount based on equity percentage
        target_amount = total_equity * self.percent

        # Cap at max percentage
        max_amount = total_equity * self.max_percent
        target_amount = min(target_amount, max_amount)

        # Respect available capital
        amount = min(target_amount, available_capital)

        shares = int(amount / price)
        return self._round_to_lot(shares, self.lot_size)


class KellyPositionSizer(PositionSizer):
    """
    Kelly Criterion position sizer.

    Optimal position sizing based on win rate and profit/loss ratio.
    Formula: f = (p * b - q) / b
    where:
        f = fraction of capital to bet
        p = win probability
        b = profit/loss ratio (avg_win / avg_loss)
        q = 1 - p (loss probability)

    Uses fractional Kelly to reduce risk.
    """

    def __init__(
        self,
        win_rate: float = 0.5,
        profit_loss_ratio: float = 2.0,
        kelly_fraction: float = 0.25,
        lot_size: int = 100,
        min_percent: float = 0.01,
        max_percent: float = 0.3
    ):
        """
        Initialize Kelly position sizer.

        Args:
            win_rate: Historical win rate (default 0.5)
            profit_loss_ratio: Avg win / avg loss (default 2.0)
            kelly_fraction: Fraction of Kelly to use (default 0.25 = quarter Kelly)
            lot_size: Lot size for rounding (default 100)
            min_percent: Minimum position size (default 1%)
            max_percent: Maximum position size (default 30%)
        """
        if not 0 < win_rate < 1:
            raise ValueError("Win rate must be between 0 and 1")
        if profit_loss_ratio <= 0:
            raise ValueError("Profit/loss ratio must be positive")
        if not 0 < kelly_fraction <= 1:
            raise ValueError("Kelly fraction must be between 0 and 1")
        if not 0 < min_percent < max_percent <= 1:
            raise ValueError("Invalid min/max percent bounds")
        if lot_size <= 0:
            raise ValueError("Lot size must be positive")

        self.win_rate = win_rate
        self.profit_loss_ratio = profit_loss_ratio
        self.kelly_fraction = kelly_fraction
        self.lot_size = lot_size
        self.min_percent = min_percent
        self.max_percent = max_percent

        # Calculate Kelly percentage
        self._update_kelly_percent()

        logger.info(
            f"KellyPositionSizer initialized: win_rate={win_rate:.2%}, "
            f"pl_ratio={profit_loss_ratio:.2f}, kelly_frac={kelly_fraction:.2f}, "
            f"kelly_pct={self.kelly_percent:.2%}"
        )

    def _update_kelly_percent(self):
        """Calculate Kelly percentage from parameters"""
        p = self.win_rate
        q = 1 - p
        b = self.profit_loss_ratio

        # Kelly formula: f = (p * b - q) / b
        kelly_full = (p * b - q) / b

        # Apply fractional Kelly
        kelly_pct = kelly_full * self.kelly_fraction

        # Clamp to bounds
        self.kelly_percent = max(
            self.min_percent,
            min(kelly_pct, self.max_percent)
        )

    def update_statistics(
        self,
        win_rate: float,
        profit_loss_ratio: float
    ):
        """
        Update Kelly parameters based on recent performance.

        Args:
            win_rate: Updated win rate
            profit_loss_ratio: Updated profit/loss ratio
        """
        if 0 < win_rate < 1 and profit_loss_ratio > 0:
            self.win_rate = win_rate
            self.profit_loss_ratio = profit_loss_ratio
            self._update_kelly_percent()

            logger.info(
                f"Kelly parameters updated: win_rate={win_rate:.2%}, "
                f"pl_ratio={profit_loss_ratio:.2f}, "
                f"new_kelly_pct={self.kelly_percent:.2%}"
            )

    def calculate_position_size(
        self,
        price: float,
        available_capital: float,
        total_equity: float,
        signal_data: Dict[str, Any] = None,
        portfolio_data: Dict[str, Any] = None
    ) -> int:
        """
        Calculate position size using Kelly criterion.

        Can adjust based on signal confidence if provided.
        """
        if price <= 0 or total_equity <= 0:
            return 0

        # Base Kelly percentage
        kelly_pct = self.kelly_percent

        # Adjust for signal confidence if available
        if signal_data and 'confidence' in signal_data:
            confidence = signal_data['confidence']
            if 0 <= confidence <= 1:
                # Scale Kelly by confidence
                kelly_pct *= confidence

        # Target amount
        target_amount = total_equity * kelly_pct

        # Respect available capital
        amount = min(target_amount, available_capital)

        shares = int(amount / price)
        return self._round_to_lot(shares, self.lot_size)


class RiskParitySizer(PositionSizer):
    """
    Risk parity position sizer.

    Sizes positions to equalize risk contribution across holdings.
    Uses volatility to adjust position sizes inversely.

    Position size ∝ 1 / volatility
    """

    def __init__(
        self,
        target_risk_percent: float = 0.02,
        lot_size: int = 100,
        default_volatility: float = 0.02,
        max_percent: float = 0.3
    ):
        """
        Initialize risk parity sizer.

        Args:
            target_risk_percent: Target risk per position (default 2% of equity)
            lot_size: Lot size for rounding (default 100)
            default_volatility: Default volatility if not provided (default 2%)
            max_percent: Maximum position size (default 30%)
        """
        if not 0 < target_risk_percent <= 1:
            raise ValueError("Target risk percent must be between 0 and 1")
        if default_volatility <= 0:
            raise ValueError("Default volatility must be positive")
        if not 0 < max_percent <= 1:
            raise ValueError("Max percent must be between 0 and 1")
        if lot_size <= 0:
            raise ValueError("Lot size must be positive")

        self.target_risk_percent = target_risk_percent
        self.lot_size = lot_size
        self.default_volatility = default_volatility
        self.max_percent = max_percent

        logger.info(
            f"RiskParitySizer initialized: target_risk={target_risk_percent:.2%}, "
            f"default_vol={default_volatility:.2%}, max={max_percent:.1%}"
        )

    def calculate_position_size(
        self,
        price: float,
        available_capital: float,
        total_equity: float,
        signal_data: Dict[str, Any] = None,
        portfolio_data: Dict[str, Any] = None
    ) -> int:
        """
        Calculate position size using risk parity.

        Position size = (target_risk * equity) / (price * volatility)

        Requires volatility in signal_data or portfolio_data.
        """
        if price <= 0 or total_equity <= 0:
            return 0

        # Get volatility from data
        volatility = self.default_volatility

        if signal_data and 'volatility' in signal_data:
            volatility = signal_data['volatility']
        elif portfolio_data and 'volatility' in portfolio_data:
            volatility = portfolio_data['volatility']

        if volatility <= 0:
            volatility = self.default_volatility

        # Calculate position size based on risk parity
        # target_risk = position_value * volatility
        # position_value = target_risk / volatility
        target_risk_amount = total_equity * self.target_risk_percent
        position_value = target_risk_amount / volatility

        # Cap at max percentage
        max_value = total_equity * self.max_percent
        position_value = min(position_value, max_value)

        # Respect available capital
        amount = min(position_value, available_capital)

        shares = int(amount / price)
        return self._round_to_lot(shares, self.lot_size)


class VolatilityTargetSizer(PositionSizer):
    """
    Volatility targeting position sizer.

    Adjusts position size to maintain constant portfolio volatility.
    Higher volatility → smaller positions.
    """

    def __init__(
        self,
        target_volatility: float = 0.15,
        lot_size: int = 100,
        default_volatility: float = 0.02,
        max_percent: float = 0.3
    ):
        """
        Initialize volatility target sizer.

        Args:
            target_volatility: Target portfolio volatility (default 15% annual)
            lot_size: Lot size for rounding (default 100)
            default_volatility: Default asset volatility (default 2%)
            max_percent: Maximum position size (default 30%)
        """
        if target_volatility <= 0:
            raise ValueError("Target volatility must be positive")
        if default_volatility <= 0:
            raise ValueError("Default volatility must be positive")
        if not 0 < max_percent <= 1:
            raise ValueError("Max percent must be between 0 and 1")
        if lot_size <= 0:
            raise ValueError("Lot size must be positive")

        self.target_volatility = target_volatility
        self.lot_size = lot_size
        self.default_volatility = default_volatility
        self.max_percent = max_percent

        logger.info(
            f"VolatilityTargetSizer initialized: target_vol={target_volatility:.2%}, "
            f"default_vol={default_volatility:.2%}, max={max_percent:.1%}"
        )

    def calculate_position_size(
        self,
        price: float,
        available_capital: float,
        total_equity: float,
        signal_data: Dict[str, Any] = None,
        portfolio_data: Dict[str, Any] = None
    ) -> int:
        """
        Calculate position size targeting constant volatility.

        Position weight = target_volatility / asset_volatility
        """
        if price <= 0 or total_equity <= 0:
            return 0

        # Get asset volatility
        volatility = self.default_volatility

        if signal_data and 'volatility' in signal_data:
            volatility = signal_data['volatility']
        elif portfolio_data and 'volatility' in portfolio_data:
            volatility = portfolio_data['volatility']

        if volatility <= 0:
            volatility = self.default_volatility

        # Calculate position weight
        position_weight = self.target_volatility / volatility

        # Cap at max percentage
        position_weight = min(position_weight, self.max_percent)

        # Target amount
        target_amount = total_equity * position_weight

        # Respect available capital
        amount = min(target_amount, available_capital)

        shares = int(amount / price)
        return self._round_to_lot(shares, self.lot_size)


# Factory function for easy instantiation
def create_position_sizer(sizer_type: str, **kwargs) -> PositionSizer:
    """
    Factory function to create position sizers.

    Args:
        sizer_type: Type of position sizer
                   ('fixed', 'percent', 'kelly', 'risk_parity', 'volatility_target')
        **kwargs: Sizer-specific parameters

    Returns:
        PositionSizer instance

    Examples:
        >>> sizer = create_position_sizer('fixed', fixed_amount=100000)
        >>> sizer = create_position_sizer('percent', percent=0.1)
        >>> sizer = create_position_sizer('kelly', win_rate=0.6, profit_loss_ratio=2.5)
        >>> sizer = create_position_sizer('risk_parity', target_risk_percent=0.02)
    """
    sizers = {
        'fixed': FixedPositionSizer,
        'percent': FixedPercentSizer,
        'kelly': KellyPositionSizer,
        'risk_parity': RiskParitySizer,
        'volatility_target': VolatilityTargetSizer,
    }

    sizer_type = sizer_type.lower()
    if sizer_type not in sizers:
        raise ValueError(
            f"Unknown position sizer: {sizer_type}. "
            f"Available: {list(sizers.keys())}"
        )

    return sizers[sizer_type](**kwargs)
