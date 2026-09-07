"""DeduplicationStage - Remove duplicate records."""

import logging
import pandas as pd
from typing import Dict, List

from domain.backtest.stages.data_pipeline import PipelineContext, PipelineResult

logger = logging.getLogger(__name__)


class DeduplicationStage:
    """Remove duplicate records within each data source."""

    def execute(self, context: PipelineContext) -> PipelineResult:
        """
        Remove duplicates based on (symbol, trade_date), keeping latest fetch_time.

        Args:
            context: PipelineContext with data as Dict[source_name, DataFrame]

        Returns:
            PipelineResult with deduplicated data
        """
        results: Dict[str, pd.DataFrame] = {}
        stats: Dict[str, Dict[str, int]] = {}
        errors: List[Dict[str, str]] = []

        for source, df in context.data.items():
            original_count = len(df)

            # Validate required columns
            required_cols = ['symbol', 'trade_date']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                error_msg = f"Missing required columns: {missing_cols}"
                logger.error(f"{source}: {error_msg}")
                errors.append({'source': source, 'error': error_msg})
                continue  # Skip this source

            # Sort by fetch_time and keep last (most recent)
            if 'fetch_time' in df.columns:
                df_sorted = df.sort_values('fetch_time')
            else:
                df_sorted = df.copy()  # Prevent mutation of input data

            # Deduplicate by (symbol, trade_date)
            df_dedup = df_sorted.drop_duplicates(
                subset=['symbol', 'trade_date'],
                keep='last'
            )

            duplicates_removed = original_count - len(df_dedup)
            results[source] = df_dedup
            stats[source] = {
                'original': original_count,
                'after_dedup': len(df_dedup),
                'removed': duplicates_removed
            }

            if duplicates_removed > 0:
                logger.info(f"{source}: Removed {duplicates_removed} duplicates")

        return PipelineResult(
            success=len(errors) == 0,
            data=results,
            errors=errors,
            metadata={'deduplication_stats': stats}
        )
