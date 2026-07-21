"""ConflictResolutionStage - Merge multi-source data and resolve conflicts (Priority 3).

This stage merges data from multiple sources (e.g., akshare, tushare) and resolves
conflicts using a priority-based approach. The first source in the config list has
the highest priority.

Features:
- Multi-source concatenation with source tracking
- Priority-based conflict resolution
- Conflict detection and reporting
- Value difference analysis (close, volume)
"""

import logging
import pandas as pd
from typing import Dict, List, Set, Tuple

from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult

logger = logging.getLogger(__name__)


class ConflictResolutionStage:
    """Merge data from multiple sources and resolve conflicts by priority."""

    def execute(self, context: PipelineContext) -> PipelineResult:
        """
        Merge multi-source data and resolve conflicts.

        Args:
            context: PipelineContext with:
                - data: Dict[str, pd.DataFrame] - Multiple source DataFrames
                - config['sources']: List[str] - Source priority order

        Returns:
            PipelineResult with:
                - success: True if merge successful
                - data: Single merged DataFrame (not dict)
                - errors: List of error dicts
                - metadata: Conflict statistics and details
        """
        # Validate input
        if not context.data:
            return PipelineResult(
                success=False,
                data=pd.DataFrame(),
                errors=[{'error': 'Input data is empty'}],
                metadata={}
            )

        if 'sources' not in context.config:
            return PipelineResult(
                success=False,
                data=pd.DataFrame(),
                errors=[{'error': 'Missing required config key: sources'}],
                metadata={}
            )

        sources_config: List[str] = context.config['sources']
        data_dict: Dict[str, pd.DataFrame] = context.data

        # Check for missing sources and log warnings
        warnings: List[str] = []
        available_sources = []
        for source in sources_config:
            if source not in data_dict:
                warning = f"Source '{source}' in config but not in data"
                warnings.append(warning)
                logger.warning(warning)
            else:
                available_sources.append(source)

        if not available_sources:
            return PipelineResult(
                success=False,
                data=pd.DataFrame(),
                errors=[{'error': 'No available sources to merge'}],
                metadata={'warnings': warnings}
            )

        # Step 1: Detect conflicts before merging
        conflicts = self._detect_conflicts(data_dict, available_sources)

        # Step 2: Concatenate all source DataFrames
        dfs_to_concat = []
        for source in available_sources:
            df = data_dict[source].copy()  # Prevent mutation
            # Ensure source column exists
            if 'source' not in df.columns:
                df['source'] = source
            dfs_to_concat.append(df)

        if not dfs_to_concat:
            return PipelineResult(
                success=False,
                data=pd.DataFrame(),
                errors=[{'error': 'No DataFrames to concatenate'}],
                metadata={'warnings': warnings}
            )

        merged_df = pd.concat(dfs_to_concat, ignore_index=True)

        # Step 3: Create priority mapping (lower index = higher priority)
        source_priority = {source: idx for idx, source in enumerate(available_sources)}
        merged_df['_priority'] = merged_df['source'].map(source_priority)

        # Step 4: Sort by priority (ascending = higher priority first)
        merged_df = merged_df.sort_values('_priority')

        # Step 5: Drop duplicates, keeping first (highest priority)
        if 'symbol' in merged_df.columns and 'trade_date' in merged_df.columns:
            final_df = merged_df.drop_duplicates(
                subset=['symbol', 'trade_date'],
                keep='first'
            )
        else:
            logger.warning("Missing symbol or trade_date columns, skipping deduplication")
            final_df = merged_df

        # Step 6: Clean up temporary columns
        final_df = final_df.drop(columns=['_priority'])

        # Step 7: Build metadata
        metadata = {
            'conflicts_detected': len(conflicts),
            'conflict_details': conflicts,
            'sources_merged': available_sources,
            'total_records': len(final_df),
            'warnings': warnings
        }

        logger.info(
            f"Merged {len(available_sources)} sources: "
            f"{len(final_df)} records, {len(conflicts)} conflicts"
        )

        return PipelineResult(
            success=True,
            data=final_df,
            errors=[],
            metadata=metadata
        )

    def _detect_conflicts(
        self,
        data_dict: Dict[str, pd.DataFrame],
        sources: List[str]
    ) -> List[Dict]:
        """
        Detect conflicts where multiple sources have different values for same (symbol, trade_date).

        Args:
            data_dict: Dict of source name to DataFrame
            sources: List of source names to check

        Returns:
            List of conflict dicts with details
        """
        conflicts = []

        # Build a mapping of (symbol, trade_date) -> List[source_data]
        key_to_sources: Dict[Tuple[str, str], List[Dict]] = {}

        for source in sources:
            df = data_dict[source]
            if 'symbol' not in df.columns or 'trade_date' not in df.columns:
                continue

            for row in df.itertuples(index=False):
                key = (row.symbol, row.trade_date)
                if key not in key_to_sources:
                    key_to_sources[key] = []

                key_to_sources[key].append({
                    'source': source,
                    'close': getattr(row, 'close', None),
                    'volume': getattr(row, 'volume', None),
                })

        # Check for conflicts (multiple sources with different values)
        for (symbol, trade_date), source_data_list in key_to_sources.items():
            if len(source_data_list) < 2:
                continue  # No conflict if only one source

            # Check if values differ
            close_values = [d['close'] for d in source_data_list if d['close'] is not None]
            volume_values = [d['volume'] for d in source_data_list if d['volume'] is not None]

            # Detect conflict: different close prices or volumes
            has_conflict = False
            close_diff = None
            volume_diff = None

            # Check close prices with tolerance for float comparison
            if close_values and len(close_values) > 1:
                max_close = max(close_values)
                min_close = min(close_values)
                if max_close - min_close > 1e-6:  # Use tolerance for float comparison
                    has_conflict = True
                    close_diff = max_close - min_close

            # Check volumes (integers, no tolerance needed)
            if volume_values and len(volume_values) > 1:
                if len(set(volume_values)) > 1:
                    has_conflict = True
                    volume_diff = max(volume_values) - min(volume_values)

            if has_conflict:
                conflict_detail = {
                    'symbol': symbol,
                    'trade_date': trade_date,
                    'sources': [d['source'] for d in source_data_list],
                }

                if close_diff is not None:
                    conflict_detail['close_diff'] = close_diff

                if volume_diff is not None:
                    conflict_detail['volume_diff'] = volume_diff

                conflicts.append(conflict_detail)

        return conflicts
