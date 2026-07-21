"""
Slippage Models

Implements various slippage models for realistic backtesting.
Slippage represents the difference between expected and actual execution prices.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class SlippageModel(ABC):
    """Base class for slippage models"""

    @abstractmethod
    def calculate_slippage(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> float:
        """
        Calculate slippage for a trade.

        Args:
            price: Current market price
            shares: Number of shares to trade
            side: 'buy' or 'sell'
            market_data: Additional market data (volume, spread, etc.)

        Returns:
            Slippage amount (positive for adverse movement)
        """
        pass

    def apply_slippage(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> float:
        """
        Apply slippage to get execution price.

        Args:
            price: Current market price
            shares: Number of shares to trade
            side: 'buy' or 'sell'
            market_data: Additional market data

        Returns:
            Execution price after slippage
        """
        slippage = self.calculate_slippage(price, shares, side, market_data)

        if side == 'buy':
            # Buy at higher price (adverse)
            return price + slippage
        else:
            # Sell at lower price (adverse)
            return price - slippage


class FixedSlippage(SlippageModel):
    """
    Fixed slippage model.

    Applies a constant percentage slippage to all trades.
    Simple but unrealistic for large orders.
    """

    def __init__(self, slippage_pct: float = 0.001):
        """
        Initialize fixed slippage model.

        Args:
            slippage_pct: Fixed slippage percentage (default 0.1%)
        """
        if slippage_pct < 0:
            raise ValueError("Slippage percentage must be non-negative")

        self.slippage_pct = slippage_pct
        logger.info(f"FixedSlippage initialized: {slippage_pct:.4%}")

    def calculate_slippage(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> float:
        """Calculate fixed percentage slippage"""
        return price * self.slippage_pct


class ProportionalSlippage(SlippageModel):
    """
    Proportional slippage model.

    Slippage scales with order size relative to average volume.
    More realistic for varying order sizes.
    """

    def __init__(
        self,
        base_slippage_pct: float = 0.0005,
        volume_factor: float = 0.1
    ):
        """
        Initialize proportional slippage model.

        Args:
            base_slippage_pct: Base slippage percentage (default 0.05%)
            volume_factor: Multiplier for volume impact (default 0.1)
        """
        if base_slippage_pct < 0:
            raise ValueError("Base slippage must be non-negative")
        if volume_factor < 0:
            raise ValueError("Volume factor must be non-negative")

        self.base_slippage_pct = base_slippage_pct
        self.volume_factor = volume_factor
        logger.info(
            f"ProportionalSlippage initialized: base={base_slippage_pct:.4%}, "
            f"volume_factor={volume_factor}"
        )

    def calculate_slippage(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> float:
        """
        Calculate proportional slippage based on order size.

        If volume data is available, slippage increases with order size
        relative to average volume.
        """
        base_slippage = price * self.base_slippage_pct

        if market_data and 'volume' in market_data:
            avg_volume = market_data['volume']
            if avg_volume > 0:
                # Order size as fraction of average volume
                volume_ratio = shares / avg_volume
                # Additional slippage scales with volume ratio
                volume_impact = price * self.volume_factor * volume_ratio
                return base_slippage + volume_impact

        return base_slippage


class MarketImpactSlippage(SlippageModel):
    """
    Market impact slippage model.

    Models price impact based on order size, liquidity, and volatility.
    Most realistic but requires more market data.

    Uses square-root model: impact ∝ sqrt(order_size / volume)
    """

    def __init__(
        self,
        base_slippage_pct: float = 0.0003,
        impact_coefficient: float = 0.05,
        volatility_factor: float = 0.5,
        min_slippage_pct: float = 0.0001,
        max_slippage_pct: float = 0.02
    ):
        """
        Initialize market impact slippage model.

        Args:
            base_slippage_pct: Base slippage (bid-ask spread proxy, default 0.03%)
            impact_coefficient: Market impact coefficient (default 0.05)
            volatility_factor: Volatility multiplier (default 0.5)
            min_slippage_pct: Minimum slippage floor (default 0.01%)
            max_slippage_pct: Maximum slippage cap (default 2%)
        """
        if base_slippage_pct < 0:
            raise ValueError("Base slippage must be non-negative")
        if impact_coefficient < 0:
            raise ValueError("Impact coefficient must be non-negative")
        if min_slippage_pct < 0 or max_slippage_pct < min_slippage_pct:
            raise ValueError("Invalid slippage bounds")

        self.base_slippage_pct = base_slippage_pct
        self.impact_coefficient = impact_coefficient
        self.volatility_factor = volatility_factor
        self.min_slippage_pct = min_slippage_pct
        self.max_slippage_pct = max_slippage_pct

        logger.info(
            f"MarketImpactSlippage initialized: base={base_slippage_pct:.4%}, "
            f"impact_coef={impact_coefficient}, vol_factor={volatility_factor}"
        )

    def calculate_slippage(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> float:
        """
        Calculate market impact slippage.

        Uses square-root model for price impact:
        slippage = base + impact_coef * volatility * sqrt(order_size / volume)
        """
        # Base slippage (bid-ask spread)
        base_slippage = price * self.base_slippage_pct

        if not market_data:
            return base_slippage

        volume = market_data.get('volume', 0)
        if volume <= 0:
            return base_slippage

        # Calculate volume ratio
        volume_ratio = shares / volume

        # Square-root impact model
        impact_factor = (volume_ratio ** 0.5)

        # Adjust for volatility if available
        volatility = market_data.get('volatility', 1.0)
        volatility_adjustment = 1.0 + (volatility - 1.0) * self.volatility_factor

        # Total market impact
        market_impact = (
            price * self.impact_coefficient * impact_factor * volatility_adjustment
        )

        # Total slippage
        total_slippage = base_slippage + market_impact

        # Apply bounds
        min_slip = price * self.min_slippage_pct
        max_slip = price * self.max_slippage_pct
        total_slippage = max(min_slip, min(total_slippage, max_slip))

        return total_slippage


class NoSlippage(SlippageModel):
    """
    No slippage model.

    For testing or optimistic scenarios.
    """

    def __init__(self):
        logger.info("NoSlippage initialized")

    def calculate_slippage(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> float:
        """No slippage applied"""
        return 0.0


# Factory function for easy instantiation
def create_slippage_model(model_type: str, **kwargs) -> SlippageModel:
    """
    Factory function to create slippage models.

    Args:
        model_type: Type of slippage model ('fixed', 'proportional', 'market_impact', 'none')
        **kwargs: Model-specific parameters

    Returns:
        SlippageModel instance

    Examples:
        >>> model = create_slippage_model('fixed', slippage_pct=0.001)
        >>> model = create_slippage_model('market_impact', impact_coefficient=0.05)
    """
    models = {
        'fixed': FixedSlippage,
        'proportional': ProportionalSlippage,
        'market_impact': MarketImpactSlippage,
        'none': NoSlippage,
    }

    model_type = model_type.lower()
    if model_type not in models:
        raise ValueError(
            f"Unknown slippage model: {model_type}. "
            f"Available: {list(models.keys())}"
        )

    return models[model_type](**kwargs)
