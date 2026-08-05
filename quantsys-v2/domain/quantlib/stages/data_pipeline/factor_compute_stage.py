"""FactorComputeStage - Trigger factor computation on stored data (Priority 8).

This stage triggers factor computation for symbols in the stored data:
1. Extracts unique symbols and date range from DataFrame
2. Fetches kline data for each symbol (with lookback for technical indicators)
3. Calls FactorStage to compute factors
4. Writes computed factors to factor_repository
5. Tracks statistics (factors computed, symbols processed, errors)

Features:
- Batch processing of multiple symbols
- Configurable lookback period for technical indicators (default 120 days)
- Graceful error handling with partial success support
- Statistics tracking (factors computed, symbols processed, failed, skipped)
- DataFrame immutability (pass-through)

DDD Architecture:
- Depends on IKlineRepository, IFactorRepository interfaces
- Application layer injects concrete implementations
"""

import logging
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult
from domain.ports import IKlineRepository, IFactorRepository
from domain.quantlib.stages.factor_stage import FactorStage

logger = logging.getLogger(__name__)


class FactorComputeStage:
    """Trigger factor computation on stored data."""

    def __init__(
        self,
        kline_repo: Optional[IKlineRepository] = None,
        factor_repo: Optional[IFactorRepository] = None
    ):
        """
        Initialize FactorComputeStage.

        Args:
            kline_repo: KlineRepository interface (injected by Application layer)
            factor_repo: FactorRepository interface (injected by Application layer)

        Raises:
            ValueError: 任一 repository 未注入。domain 层不再自行创建 adapters
                具体仓储(六边形架构依赖方向),请由 Application/CLI 层注入。
        """
        if kline_repo is None or factor_repo is None:
            raise ValueError(
                "FactorComputeStage requires kline_repo and factor_repo injection "
                "(e.g. KlineORMRepository/FactorORMRepository from "
                "adapters.outbound.repositories, wired by the Application layer)"
            )

        self.kline_repo = kline_repo
        self.factor_repo = factor_repo
        self.factor_stage = FactorStage(name="factors")

    def execute(self, context: PipelineContext) -> PipelineResult:
        """
        Trigger factor computation for symbols in the data.

        Args:
            context: PipelineContext with:
                - data: pd.DataFrame with stored data
                - config['factor_lookback_days']: Optional lookback days (default 120)

        Returns:
            PipelineResult with:
                - success: True if factor computation completes (even with partial failures)
                - data: Same DataFrame (pass-through)
                - errors: List of error dicts
                - metadata: Factor computation statistics
        """
        df: pd.DataFrame = context.data
        lookback_days: int = context.config.get('factor_lookback_days', 120)

        # Handle empty DataFrame
        if df.empty:
            logger.info("Empty DataFrame, skipping factor computation")
            return PipelineResult(
                success=True,
                data=df,
                errors=[],
                metadata={
                    'factors_computed': 0,
                    'symbols_processed': 0,
                    'symbols_failed': 0,
                    'symbols_skipped': 0,
                    'total_records': 0
                }
            )

        errors: List[Dict] = []
        metadata: Dict = {
            'total_records': len(df),
            'lookback_days': lookback_days
        }

        # Extract unique symbols and date range
        symbols = df['symbol'].unique().tolist()
        min_date = df['trade_date'].min()
        max_date = df['trade_date'].max()

        # Extend start date for lookback (technical indicators need history)
        start_date = self._calculate_lookback_date(min_date, lookback_days)
        end_date = max_date

        logger.info(
            f"Computing factors for {len(symbols)} symbols, "
            f"date range: {start_date} to {end_date}"
        )

        # Process each symbol
        symbols_processed = 0
        symbols_failed = 0
        symbols_skipped = 0
        total_factors_computed = 0

        for symbol in symbols:
            try:
                # Fetch kline data with lookback
                klines = self.kline_repo.get_daily_klines(symbol, start_date, end_date)

                if not klines:
                    logger.warning(f"No kline data for {symbol}, skipping")
                    symbols_skipped += 1
                    continue

                # Compute factors using FactorStage
                result = self.factor_stage.process({
                    'symbol': symbol,
                    'klines': klines
                })

                factors = result.get('factors', {})

                if not factors:
                    logger.warning(f"No factors computed for {symbol}")
                    symbols_skipped += 1
                    continue

                # Get latest date from klines
                last_kline = klines[-1]
                latest_date = last_kline.get('trade_date') or last_kline.get('date', '')

                # Write factors to repository
                try:
                    self.factor_repo.save_factors(symbol, str(latest_date), factors)
                    total_factors_computed += len(factors)
                    symbols_processed += 1
                    logger.debug(
                        f"Computed {len(factors)} factors for {symbol} on {latest_date}"
                    )
                except Exception as e:
                    error_msg = f"Failed to write factors for {symbol}: {str(e)}"
                    logger.error(error_msg)
                    errors.append({
                        'symbol': symbol,
                        'stage': 'factor_write',
                        'error': str(e)
                    })
                    symbols_failed += 1

            except Exception as e:
                error_msg = f"Factor computation failed for {symbol}: {str(e)}"
                logger.error(error_msg)
                errors.append({
                    'symbol': symbol,
                    'stage': 'factor_compute',
                    'error': str(e)
                })
                symbols_failed += 1

        # Update metadata
        metadata.update({
            'symbols_processed': symbols_processed,
            'symbols_failed': symbols_failed,
            'symbols_skipped': symbols_skipped,
            'factors_computed': total_factors_computed
        })

        logger.info(
            f"Factor computation complete: {symbols_processed} processed, "
            f"{symbols_failed} failed, {symbols_skipped} skipped, "
            f"{total_factors_computed} factors computed"
        )

        # Always return success (partial failures are tracked in errors)
        return PipelineResult(
            success=True,
            data=df,  # Pass-through unchanged
            errors=errors,
            metadata=metadata
        )

    def _calculate_lookback_date(self, min_date: str, lookback_days: int) -> str:
        """
        Calculate start date with lookback for technical indicators.

        Args:
            min_date: Minimum date in DataFrame (YYYY-MM-DD)
            lookback_days: Number of days to look back

        Returns:
            Start date string (YYYY-MM-DD)
        """
        try:
            date_obj = datetime.strptime(str(min_date), '%Y-%m-%d')
            lookback_date = date_obj - timedelta(days=lookback_days)
            return lookback_date.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"Failed to calculate lookback date: {e}, using min_date")
            return str(min_date)
