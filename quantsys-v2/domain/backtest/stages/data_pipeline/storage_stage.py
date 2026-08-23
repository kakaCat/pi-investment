"""StorageStage - Write cleaned and imputed data to database (Priority 7).

This stage writes processed data to the database using a three-layer architecture:
1. raw_klines - Original fetched data with source tracking
2. daily_klines - Cleaned, merged, production-ready data
3. factors - Computed factors (handled by FactorComputeStage)

Features:
- Batch upsert to raw_klines and daily_klines tables
- Configurable batch size (default 1000)
- Graceful error handling with partial success support
- Statistics tracking (records written, batches processed)
- DataFrame immutability (pass-through)

DDD Architecture:
- Depends on IKlineRepository interface
- Application layer injects concrete implementation
"""

import logging
import pandas as pd
from typing import Dict, List, Optional

from domain.backtest.stages.data_pipeline import PipelineContext, PipelineResult
from domain.ports import IKlineRepository

logger = logging.getLogger(__name__)


class StorageStage:
    """Write cleaned data to database tables."""

    def __init__(self, kline_repo: Optional[IKlineRepository] = None):
        """
        Initialize StorageStage.

        Args:
            kline_repo: KlineRepository interface (injected by Application layer)

        Raises:
            ValueError: kline_repo 未注入。domain 层不再自行创建 adapters
                具体仓储(六边形架构依赖方向),请由 Application/CLI 层注入。
        """
        if kline_repo is None:
            raise ValueError(
                "StorageStage requires kline_repo injection "
                "(e.g. KlineORMRepository from adapters.outbound.repositories, "
                "wired by the Application layer)"
            )

        self.kline_repo = kline_repo

    def execute(self, context: PipelineContext) -> PipelineResult:
        """
        Write data to raw_klines and daily_klines tables.

        Args:
            context: PipelineContext with:
                - data: pd.DataFrame with cleaned data
                - config['batch_size']: Optional batch size (default 1000)

        Returns:
            PipelineResult with:
                - success: True if at least daily_klines write succeeds
                - data: Same DataFrame (pass-through)
                - errors: List of error dicts
                - metadata: Storage statistics
        """
        df: pd.DataFrame = context.data
        batch_size: int = context.config.get('batch_size', 1000)

        # Handle empty DataFrame
        if df.empty:
            logger.info("Empty DataFrame, skipping storage")
            return PipelineResult(
                success=True,
                data=df,
                errors=[],
                metadata={
                    'daily_klines_written': 0,
                    'total_records': 0,
                    'batch_size': batch_size
                }
            )

        errors: List[Dict] = []
        metadata: Dict = {
            'total_records': len(df),
            'batch_size': batch_size
        }

        # Write to raw_klines if source column exists
        raw_klines_written = 0
        if 'source' in df.columns:
            try:
                raw_klines_written = self._write_raw_klines(df)
                metadata['raw_klines_written'] = raw_klines_written
                logger.info(f"Wrote {raw_klines_written} records to raw_klines")
            except Exception as e:
                error_msg = f"Failed to write to raw_klines: {str(e)}"
                logger.error(error_msg)
                errors.append({'table': 'raw_klines', 'error': str(e)})

        # Write to daily_klines (always)
        try:
            daily_klines_written = self._write_daily_klines(df)
            metadata['daily_klines_written'] = daily_klines_written
            logger.info(f"Wrote {daily_klines_written} records to daily_klines")

            # Success if daily_klines write succeeds
            return PipelineResult(
                success=True,
                data=df,  # Pass-through unchanged
                errors=errors,
                metadata=metadata
            )

        except Exception as e:
            error_msg = f"Failed to write to daily_klines: {str(e)}"
            logger.error(error_msg)
            errors.append({'table': 'daily_klines', 'error': str(e)})

            # Failure if daily_klines write fails
            return PipelineResult(
                success=False,
                data=df,
                errors=errors,
                metadata=metadata
            )

    def _write_raw_klines(self, df: pd.DataFrame) -> int:
        """
        Write data to raw_klines table.

        Args:
            df: DataFrame with source column

        Returns:
            Number of records written
        """
        # Select required columns for raw_klines
        required_cols = ['source', 'symbol', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
        optional_cols = ['amount']

        # Build column list
        cols = [c for c in required_cols if c in df.columns]
        cols.extend([c for c in optional_cols if c in df.columns])

        # Convert to list of dicts
        records = df[cols].to_dict('records')

        # Write to database
        return self.kline_repo.save_raw_klines(records)

    def _write_daily_klines(self, df: pd.DataFrame) -> int:
        """
        Write data to daily_klines table.

        Args:
            df: DataFrame with cleaned data

        Returns:
            Number of records written
        """
        # Select required columns for daily_klines
        required_cols = ['symbol', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
        optional_cols = ['amount', 'turnover_rate', 'quality_score', 'is_suspended']

        # Build column list
        cols = [c for c in required_cols if c in df.columns]
        cols.extend([c for c in optional_cols if c in df.columns])

        # Normalize symbols: strip .SZ/.SH/.HK suffix for consistency with quant.stocks
        df_normalized = df.copy()
        if 'symbol' in df_normalized.columns:
            df_normalized['symbol'] = df_normalized['symbol'].astype(str).str.replace(
                r'\.(SZ|SH|HK)$', '', regex=True
            )

        # Convert to list of dicts
        records = df_normalized[cols].to_dict('records')

        # Write to database
        return self.kline_repo.save_daily_klines(records)
