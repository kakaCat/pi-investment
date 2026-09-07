"""
Commission Models

Implements realistic commission and fee structures for different markets.
Covers A-shares, HK stocks, and customizable fee structures.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class CommissionModel(ABC):
    """Base class for commission models"""

    @abstractmethod
    def calculate_commission(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Calculate commission and fees for a trade.

        Args:
            price: Execution price
            shares: Number of shares
            side: 'buy' or 'sell'
            market_data: Additional market data

        Returns:
            Dictionary with fee breakdown:
            {
                'commission': float,
                'stamp_tax': float,
                'transfer_fee': float,
                'total': float
            }
        """
        pass


class AShareCommission(CommissionModel):
    """
    A-share (China mainland) commission model.

    Fee structure:
    - Commission: 0.03% (both sides, minimum 5 RMB)
    - Stamp tax: 0.1% (sell only)
    - Transfer fee: 0.001% (both sides)
    """

    def __init__(
        self,
        commission_rate: float = 0.0003,
        min_commission: float = 5.0,
        stamp_tax_rate: float = 0.001,
        transfer_fee_rate: float = 0.00001
    ):
        """
        Initialize A-share commission model.

        Args:
            commission_rate: Commission rate (default 0.03%)
            min_commission: Minimum commission (default 5 RMB)
            stamp_tax_rate: Stamp tax rate (default 0.1%, sell only)
            transfer_fee_rate: Transfer fee rate (default 0.001%)
        """
        if commission_rate < 0 or min_commission < 0:
            raise ValueError("Commission parameters must be non-negative")
        if stamp_tax_rate < 0 or transfer_fee_rate < 0:
            raise ValueError("Tax/fee rates must be non-negative")

        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.stamp_tax_rate = stamp_tax_rate
        self.transfer_fee_rate = transfer_fee_rate

        logger.info(
            f"AShareCommission initialized: commission={commission_rate:.4%}, "
            f"min={min_commission}, stamp_tax={stamp_tax_rate:.4%}, "
            f"transfer_fee={transfer_fee_rate:.5%}"
        )

    def calculate_commission(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Calculate A-share commission and fees.

        Returns breakdown of all fees.
        """
        trade_value = price * shares

        # Commission (both sides, with minimum)
        commission = max(trade_value * self.commission_rate, self.min_commission)

        # Stamp tax (sell only)
        stamp_tax = trade_value * self.stamp_tax_rate if side == 'sell' else 0.0

        # Transfer fee (both sides)
        transfer_fee = trade_value * self.transfer_fee_rate

        total = commission + stamp_tax + transfer_fee

        return {
            'commission': round(commission, 2),
            'stamp_tax': round(stamp_tax, 2),
            'transfer_fee': round(transfer_fee, 2),
            'total': round(total, 2)
        }


class HKStockCommission(CommissionModel):
    """
    Hong Kong stock commission model.

    Fee structure:
    - Commission: 0.25% (both sides, minimum 100 HKD)
    - Trading fee: 0.00565% (both sides)
    - Transaction levy: 0.0027% (both sides)
    - Stamp duty: 0.13% (both sides, minimum 1 HKD)
    """

    def __init__(
        self,
        commission_rate: float = 0.0025,
        min_commission: float = 100.0,
        trading_fee_rate: float = 0.0000565,
        transaction_levy_rate: float = 0.000027,
        stamp_duty_rate: float = 0.0013,
        min_stamp_duty: float = 1.0
    ):
        """
        Initialize HK stock commission model.

        Args:
            commission_rate: Commission rate (default 0.25%)
            min_commission: Minimum commission (default 100 HKD)
            trading_fee_rate: Trading fee rate (default 0.00565%)
            transaction_levy_rate: Transaction levy rate (default 0.0027%)
            stamp_duty_rate: Stamp duty rate (default 0.13%)
            min_stamp_duty: Minimum stamp duty (default 1 HKD)
        """
        if any(x < 0 for x in [commission_rate, min_commission, trading_fee_rate,
                                transaction_levy_rate, stamp_duty_rate, min_stamp_duty]):
            raise ValueError("All fee parameters must be non-negative")

        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.trading_fee_rate = trading_fee_rate
        self.transaction_levy_rate = transaction_levy_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.min_stamp_duty = min_stamp_duty

        logger.info(
            f"HKStockCommission initialized: commission={commission_rate:.4%}, "
            f"min={min_commission}, stamp_duty={stamp_duty_rate:.4%}"
        )

    def calculate_commission(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Calculate HK stock commission and fees.

        Returns breakdown of all fees.
        """
        trade_value = price * shares

        # Commission (with minimum)
        commission = max(trade_value * self.commission_rate, self.min_commission)

        # Trading fee
        trading_fee = trade_value * self.trading_fee_rate

        # Transaction levy
        transaction_levy = trade_value * self.transaction_levy_rate

        # Stamp duty (with minimum)
        stamp_duty = max(trade_value * self.stamp_duty_rate, self.min_stamp_duty)

        total = commission + trading_fee + transaction_levy + stamp_duty

        return {
            'commission': round(commission, 2),
            'trading_fee': round(trading_fee, 2),
            'transaction_levy': round(transaction_levy, 2),
            'stamp_duty': round(stamp_duty, 2),
            'total': round(total, 2)
        }


class FixedCommission(CommissionModel):
    """
    Simple fixed commission model.

    Applies a fixed percentage commission with optional minimum.
    Useful for US stocks or simplified backtesting.
    """

    def __init__(
        self,
        commission_rate: float = 0.001,
        min_commission: float = 0.0,
        per_share_fee: float = 0.0
    ):
        """
        Initialize fixed commission model.

        Args:
            commission_rate: Commission rate (default 0.1%)
            min_commission: Minimum commission (default 0)
            per_share_fee: Per-share fee (default 0)
        """
        if commission_rate < 0 or min_commission < 0 or per_share_fee < 0:
            raise ValueError("Commission parameters must be non-negative")

        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.per_share_fee = per_share_fee

        logger.info(
            f"FixedCommission initialized: rate={commission_rate:.4%}, "
            f"min={min_commission}, per_share={per_share_fee}"
        )

    def calculate_commission(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Calculate fixed commission.

        Returns simplified fee structure.
        """
        trade_value = price * shares

        # Percentage-based commission
        pct_commission = trade_value * self.commission_rate

        # Per-share fee
        share_fee = shares * self.per_share_fee

        # Total commission (with minimum)
        commission = max(pct_commission + share_fee, self.min_commission)

        return {
            'commission': round(commission, 2),
            'stamp_tax': 0.0,
            'transfer_fee': 0.0,
            'total': round(commission, 2)
        }


class ZeroCommission(CommissionModel):
    """
    Zero commission model.

    For testing or commission-free trading scenarios.
    """

    def __init__(self):
        logger.info("ZeroCommission initialized")

    def calculate_commission(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """No commission applied"""
        return {
            'commission': 0.0,
            'stamp_tax': 0.0,
            'transfer_fee': 0.0,
            'total': 0.0
        }


class TieredCommission(CommissionModel):
    """
    Tiered commission model.

    Commission rate decreases with trade size.
    Common for institutional or high-volume traders.
    """

    def __init__(
        self,
        tiers: list = None,
        min_commission: float = 5.0
    ):
        """
        Initialize tiered commission model.

        Args:
            tiers: List of (threshold, rate) tuples, e.g.,
                   [(0, 0.0003), (100000, 0.0002), (1000000, 0.0001)]
                   Default: A-share style tiers
            min_commission: Minimum commission (default 5)
        """
        if tiers is None:
            # Default A-share style tiers
            tiers = [
                (0, 0.0003),        # 0-100k: 0.03%
                (100000, 0.00025),  # 100k-1M: 0.025%
                (1000000, 0.0002),  # 1M+: 0.02%
            ]

        # Sort tiers by threshold
        self.tiers = sorted(tiers, key=lambda x: x[0])
        self.min_commission = min_commission

        logger.info(
            f"TieredCommission initialized: {len(self.tiers)} tiers, "
            f"min={min_commission}"
        )

    def calculate_commission(
        self,
        price: float,
        shares: int,
        side: str,
        market_data: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Calculate tiered commission.

        Uses the rate corresponding to trade value.
        """
        trade_value = price * shares

        # Find applicable tier
        rate = self.tiers[0][1]  # Default to first tier
        for threshold, tier_rate in self.tiers:
            if trade_value >= threshold:
                rate = tier_rate
            else:
                break

        commission = max(trade_value * rate, self.min_commission)

        return {
            'commission': round(commission, 2),
            'stamp_tax': 0.0,
            'transfer_fee': 0.0,
            'total': round(commission, 2)
        }


# Factory function for easy instantiation
def create_commission_model(model_type: str, **kwargs) -> CommissionModel:
    """
    Factory function to create commission models.

    Args:
        model_type: Type of commission model
                   ('ashare', 'hkstock', 'fixed', 'zero', 'tiered')
        **kwargs: Model-specific parameters

    Returns:
        CommissionModel instance

    Examples:
        >>> model = create_commission_model('ashare')
        >>> model = create_commission_model('fixed', commission_rate=0.001)
        >>> model = create_commission_model('tiered', tiers=[(0, 0.0003), (100000, 0.0002)])
    """
    models = {
        'ashare': AShareCommission,
        'hkstock': HKStockCommission,
        'fixed': FixedCommission,
        'zero': ZeroCommission,
        'tiered': TieredCommission,
    }

    model_type = model_type.lower()
    if model_type not in models:
        raise ValueError(
            f"Unknown commission model: {model_type}. "
            f"Available: {list(models.keys())}"
        )

    return models[model_type](**kwargs)
