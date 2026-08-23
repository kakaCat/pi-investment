"""ImputationStage - Fill missing values (Priority 4).

This stage fills missing values in the cleaned data using appropriate strategies:
- Forward-fill for price columns (close, open, high, low) - uses last known value
- Zero-fill for volume - missing volume means no trading occurred

Features:
- Group-wise forward fill (respects symbol boundaries)
- Statistics tracking (missing counts, filled counts)
- Warning for symbols with >50% missing values
- DataFrame immutability (uses .copy())
"""

import logging
import pandas as pd
from typing import Dict, List, Set

from domain.backtest.stages.data_pipeline import PipelineContext, PipelineResult

logger = logging.getLogger(__name__)


class ImputationStage:
    """Fill missing values in cleaned data."""

    # Price columns to forward-fill
    PRICE_COLUMNS = ['close', 'open', 'high', 'low']

    # Volume column to zero-fill
    VOLUME_COLUMN = 'volume'

    # Required columns
    REQUIRED_COLUMNS = ['symbol', 'close', 'volume', 'open', 'high', 'low']

    def execute(self, context: PipelineContext) -> PipelineResult:
        """
        Fill missing values in the data.

        Args:
            context: PipelineContext with:
                - data: pd.DataFrame - Single merged DataFrame
                - config: Dict (optional)

        Returns:
            PipelineResult with:
                - success: True if imputation successful
                - data: DataFrame with missing values filled
                - errors: List of error dicts
                - metadata: Imputation statistics
        """
        # Validate input type
        if not isinstance(context.data, pd.DataFrame):
            return PipelineResult(
                success=False,
                data=pd.DataFrame(),
                errors=[{'error': 'Input data is not a DataFrame'}],
                metadata={}
            )

        # Validate input is not empty
        if context.data.empty:
            return PipelineResult(
                success=False,
                data=pd.DataFrame(),
                errors=[{'error': 'Input data is empty'}],
                metadata={}
            )

        # Validate required columns
        missing_cols = [col for col in self.REQUIRED_COLUMNS if col not in context.data.columns]
        if missing_cols:
            return PipelineResult(
                success=False,
                data=pd.DataFrame(),
                errors=[{'error': f'Missing required columns: {missing_cols}'}],
                metadata={}
            )

        # Copy DataFrame to prevent mutation
        df = context.data.copy()

        # Track statistics before imputation
        missing_before = self._count_missing(df)
        symbols_with_missing = self._get_symbols_with_missing(df)

        # Step 1: Forward-fill price columns (group by symbol)
        for col in self.PRICE_COLUMNS:
            if col in df.columns:
                df[col] = df.groupby('symbol')[col].ffill()

        # Step 2: Zero-fill volume
        if self.VOLUME_COLUMN in df.columns:
            df[self.VOLUME_COLUMN] = df[self.VOLUME_COLUMN].fillna(0)

        # Track statistics after imputation
        missing_after = self._count_missing(df)
        filled_count = {
            col: missing_before.get(col, 0) - missing_after.get(col, 0)
            for col in missing_before.keys()
        }

        # Check for symbols with many missing values (>50%)
        warnings = self._check_high_missing_rate(context.data, symbols_with_missing)

        # Build metadata
        metadata = {
            'missing_before': missing_before,
            'missing_after': missing_after,
            'filled_count': filled_count,
            'symbols_with_missing': list(symbols_with_missing),
            'warnings': warnings
        }

        logger.info(
            f"Imputation complete: filled {sum(filled_count.values())} values "
            f"across {len(symbols_with_missing)} symbols"
        )

        if warnings:
            for warning in warnings:
                logger.warning(warning)

        return PipelineResult(
            success=True,
            data=df,
            errors=[],
            metadata=metadata
        )

    def _count_missing(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        Count missing values for each column.

        Args:
            df: DataFrame to check

        Returns:
            Dict mapping column name to missing count
        """
        missing_counts = {}

        for col in self.PRICE_COLUMNS + [self.VOLUME_COLUMN]:
            if col in df.columns:
                missing_counts[col] = int(df[col].isna().sum())

        return missing_counts

    def _get_symbols_with_missing(self, df: pd.DataFrame) -> Set[str]:
        """
        Get set of symbols that have missing values.

        Args:
            df: DataFrame to check

        Returns:
            Set of symbol strings
        """
        symbols_with_missing = set()

        for col in self.PRICE_COLUMNS + [self.VOLUME_COLUMN]:
            if col in df.columns:
                symbols_with_na = df[df[col].isna()]['symbol'].unique()
                symbols_with_missing.update(symbols_with_na)

        return symbols_with_missing

    def _check_high_missing_rate(
        self,
        df: pd.DataFrame,
        symbols_with_missing: Set[str]
    ) -> List[str]:
        """
        Check for symbols with >50% missing values and generate warnings.

        Args:
            df: Original DataFrame (before imputation)
            symbols_with_missing: Set of symbols with missing values

        Returns:
            List of warning strings
        """
        warnings = []

        for symbol in symbols_with_missing:
            symbol_df = df[df['symbol'] == symbol]
            total_records = len(symbol_df)

            if total_records == 0:
                continue

            # Check each price column
            for col in self.PRICE_COLUMNS:
                if col in df.columns:
                    missing_count = symbol_df[col].isna().sum()
                    missing_rate = missing_count / total_records

                    if missing_rate > 0.5:
                        warning = (
                            f"Symbol {symbol} has {missing_rate:.1%} missing values "
                            f"in column '{col}' ({missing_count}/{total_records} records)"
                        )
                        warnings.append(warning)

        return warnings
