"""Price adjustment (复权) module for stock data.

This module handles forward adjustment (前复权, qfq) and backward adjustment (后复权, hfq)
for stock prices to account for corporate actions like dividends and stock splits.
"""

from __future__ import annotations

from typing import Literal, Optional

import pandas as pd
import numpy as np


AdjustType = Literal["qfq", "hfq", ""]


class PriceAdjuster:
    """Handle price adjustment (复权) for stock data.

    Forward adjustment (前复权, qfq): Adjusts historical prices based on current price
    Backward adjustment (后复权, hfq): Adjusts current price based on historical prices
    """

    def __init__(self):
        """Initialize the price adjuster."""
        pass

    def adjust_prices(
        self,
        df: pd.DataFrame,
        adjust_type: AdjustType = "qfq",
        adjust_factors: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Adjust stock prices for corporate actions.

        Args:
            df: DataFrame with columns [date, open, high, low, close, volume, amount]
            adjust_type: "qfq" (forward), "hfq" (backward), "" (none)
            adjust_factors: Optional DataFrame with adjustment factors [date, factor]
                          If None, will calculate from price data

        Returns:
            DataFrame with adjusted prices

        Raises:
            ValueError: If required columns are missing or adjust_type is invalid
        """
        if adjust_type == "":
            return df.copy()

        if adjust_type not in ["qfq", "hfq"]:
            raise ValueError(f"Invalid adjust_type: {adjust_type}. Must be 'qfq', 'hfq', or ''")

        required_cols = ["date", "open", "high", "low", "close"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        if df.empty:
            return df.copy()

        # Make a copy to avoid modifying original
        result = df.copy()
        result = result.sort_values("date").reset_index(drop=True)

        # Calculate or use provided adjustment factors
        if adjust_factors is None:
            factors = self._calculate_adjust_factors(result, adjust_type)
        else:
            factors = adjust_factors.copy()

        # Merge factors with price data
        result = result.merge(factors, on="date", how="left")
        result["factor"] = result["factor"].fillna(1.0)

        # Apply adjustment to price columns
        price_cols = ["open", "high", "low", "close"]
        for col in price_cols:
            if col in result.columns:
                result[col] = result[col] * result["factor"]

        # Volume should be inversely adjusted (if stock split 1:2, volume doubles)
        if "volume" in result.columns:
            result["volume"] = result["volume"] / result["factor"]

        # Drop the factor column
        result = result.drop(columns=["factor"])

        return result

    def _calculate_adjust_factors(
        self,
        df: pd.DataFrame,
        adjust_type: AdjustType,
    ) -> pd.DataFrame:
        """Calculate adjustment factors from price data.

        This detects price gaps that indicate corporate actions (dividends, splits)
        and calculates appropriate adjustment factors.

        Args:
            df: DataFrame sorted by date with close prices
            adjust_type: "qfq" or "hfq"

        Returns:
            DataFrame with columns [date, factor]
        """
        if df.empty or "close" not in df.columns:
            return pd.DataFrame({"date": [], "factor": []})

        df = df.sort_values("date").reset_index(drop=True)

        # Calculate daily returns
        df["prev_close"] = df["close"].shift(1)
        df["return"] = df["close"] / df["prev_close"] - 1

        # Detect abnormal gaps (likely corporate actions)
        # A gap > 15% or < -15% in one day is suspicious
        threshold = 0.15
        df["is_gap"] = (df["return"].abs() > threshold) & df["return"].notna()

        # Calculate cumulative adjustment factor
        factors = []
        cumulative_factor = 1.0

        for idx, row in df.iterrows():
            if idx == 0:
                factors.append(1.0)
                continue

            if row["is_gap"]:
                # Detected a corporate action
                # Adjustment ratio = new_price / old_price
                adjustment_ratio = row["close"] / row["prev_close"]

                if adjust_type == "qfq":
                    # Forward adjustment: adjust historical prices upward
                    cumulative_factor = cumulative_factor / adjustment_ratio
                else:  # hfq
                    # Backward adjustment: adjust future prices downward
                    cumulative_factor = cumulative_factor * adjustment_ratio

            factors.append(cumulative_factor)

        # For backward adjustment, reverse the factors
        if adjust_type == "hfq":
            factors = [f / factors[-1] for f in factors]

        result = pd.DataFrame({
            "date": df["date"],
            "factor": factors,
        })

        return result

    def calculate_split_ratio(
        self,
        old_price: float,
        new_price: float,
        old_volume: float,
        new_volume: float,
    ) -> float:
        """Calculate stock split ratio from price and volume changes.

        Args:
            old_price: Price before split
            new_price: Price after split
            old_volume: Volume before split
            new_volume: Volume after split

        Returns:
            Split ratio (e.g., 2.0 for 1:2 split, 0.5 for 2:1 reverse split)
        """
        if old_price <= 0 or new_price <= 0:
            return 1.0

        price_ratio = old_price / new_price
        volume_ratio = new_volume / old_volume if old_volume > 0 else 1.0

        # Split ratio should be consistent between price and volume
        # Use price ratio as primary indicator
        return price_ratio

    def detect_corporate_actions(
        self,
        df: pd.DataFrame,
        threshold: float = 0.15,
    ) -> pd.DataFrame:
        """Detect corporate actions (dividends, splits) from price data.

        Args:
            df: DataFrame with columns [date, close, volume]
            threshold: Minimum price change ratio to consider as corporate action

        Returns:
            DataFrame with detected corporate actions [date, type, ratio]
        """
        if df.empty or "close" not in df.columns:
            return pd.DataFrame({"date": [], "type": [], "ratio": []})

        df = df.sort_values("date").reset_index(drop=True)
        df["prev_close"] = df["close"].shift(1)
        df["return"] = df["close"] / df["prev_close"] - 1

        # Detect gaps
        gaps = df[df["return"].abs() > threshold].copy()

        if gaps.empty:
            return pd.DataFrame({"date": [], "type": [], "ratio": []})

        # Classify corporate action type
        actions = []
        for _, row in gaps.iterrows():
            ratio = row["close"] / row["prev_close"]

            if ratio < 0.5:
                action_type = "split"  # Stock split (e.g., 1:2)
            elif ratio > 1.5:
                action_type = "reverse_split"  # Reverse split (e.g., 2:1)
            elif ratio < 1:
                action_type = "dividend"  # Dividend payment
            else:
                action_type = "unknown"

            actions.append({
                "date": row["date"],
                "type": action_type,
                "ratio": ratio,
            })

        return pd.DataFrame(actions)

    def verify_adjustment(
        self,
        original_df: pd.DataFrame,
        adjusted_df: pd.DataFrame,
    ) -> dict:
        """Verify that price adjustment was applied correctly.

        Args:
            original_df: Original DataFrame before adjustment
            adjusted_df: DataFrame after adjustment

        Returns:
            Dict with verification results: {
                "is_valid": bool,
                "price_ratio_consistent": bool,
                "volume_ratio_consistent": bool,
                "errors": list[str]
            }
        """
        errors = []

        if len(original_df) != len(adjusted_df):
            errors.append("DataFrames have different lengths")
            return {
                "is_valid": False,
                "price_ratio_consistent": False,
                "volume_ratio_consistent": False,
                "errors": errors,
            }

        # Check that relative price changes are preserved
        orig_returns = original_df["close"].pct_change()
        adj_returns = adjusted_df["close"].pct_change()

        # Returns should be identical (within floating point tolerance)
        returns_match = np.allclose(
            orig_returns.dropna(),
            adj_returns.dropna(),
            rtol=1e-5,
            atol=1e-8,
        )

        if not returns_match:
            errors.append("Price returns are not preserved after adjustment")

        # Check volume adjustment (inverse of price adjustment)
        if "volume" in original_df.columns and "volume" in adjusted_df.columns:
            # Total volume * price should be approximately preserved
            orig_value = (original_df["close"] * original_df["volume"]).sum()
            adj_value = (adjusted_df["close"] * adjusted_df["volume"]).sum()

            value_match = np.isclose(orig_value, adj_value, rtol=0.01)
            if not value_match:
                errors.append(f"Total value not preserved: {orig_value:.2f} vs {adj_value:.2f}")
        else:
            value_match = True

        return {
            "is_valid": len(errors) == 0,
            "price_ratio_consistent": returns_match,
            "volume_ratio_consistent": value_match,
            "errors": errors,
        }
