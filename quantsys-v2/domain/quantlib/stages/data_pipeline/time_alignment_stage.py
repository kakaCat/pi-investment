"""TimeAlignmentStage - Time and calendar alignment (Priority 1)."""

import logging
import pandas as pd
from typing import Dict, Set
from datetime import date

from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult
from infrastructure.persistence.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class TimeAlignmentStage:
    """Align timestamps to trading calendar and timezone."""

    def __init__(self, calendar: str = 'SSE', timezone: str = 'Asia/Shanghai'):
        """
        Initialize TimeAlignmentStage.

        Args:
            calendar: Exchange calendar to use (SSE, SZSE)
            timezone: Target timezone for alignment
        """
        self.calendar = calendar
        self.timezone = timezone
        self.trading_calendar = self._load_trading_calendar()

    def execute(self, context: PipelineContext) -> PipelineResult:
        """
        Execute time alignment stage.

        Filters non-trading days and marks suspensions (zero volume).

        Args:
            context: Pipeline context with data from previous stages

        Returns:
            PipelineResult with aligned data and statistics
        """
        results = {}
        stats = {}

        for source, df in context.data.items():
            if df is None or len(df) == 0:
                results[source] = df
                stats[source] = {
                    'original': 0,
                    'after_alignment': 0,
                    'filtered': 0,
                    'suspensions': 0
                }
                continue

            original_count = len(df)

            # Ensure trade_date is date type
            if 'trade_date' in df.columns:
                if not pd.api.types.is_datetime64_any_dtype(df['trade_date']):
                    # If already date objects, keep as is
                    if not all(isinstance(d, date) for d in df['trade_date'].dropna()):
                        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
                else:
                    # Convert datetime to date
                    df = df.copy()
                    df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date

            # Filter non-trading days
            df = df[df['trade_date'].isin(self.trading_calendar)]

            # Mark suspensions (zero volume on trading days)
            if 'volume' in df.columns:
                df = df.copy()
                df['is_suspended'] = (df['volume'] == 0) | df['volume'].isna()
            else:
                df = df.copy()
                df['is_suspended'] = False

            filtered_count = original_count - len(df)
            results[source] = df
            stats[source] = {
                'original': original_count,
                'after_alignment': len(df),
                'filtered': filtered_count,
                'suspensions': int(df['is_suspended'].sum()) if 'is_suspended' in df.columns else 0
            }

        return PipelineResult(
            success=True,
            data=results,
            errors=[],
            metadata={'alignment_stats': stats}
        )

    def _load_trading_calendar(self) -> Set[date]:
        """
        Load trading calendar from database.

        Returns:
            Set of trading dates for the specified exchange
        """
        try:
            repo = BaseRepository()
            if not repo.db:
                logger.warning("Database connection not available. Using empty calendar.")
                return set()

            cursor = repo.cursor()

            query = """
                SELECT trade_date
                FROM quant.trading_calendar
                WHERE exchange = %s AND is_trading_day = TRUE
            """
            cursor.execute(query, (self.calendar,))

            results = cursor.fetchall()
            if results and isinstance(results[0], dict):
                dates = {row['trade_date'] for row in results}
            elif results:
                dates = {row[0] for row in results}
            else:
                dates = set()
            cursor.close()

            logger.info(f"Loaded {len(dates)} trading days for {self.calendar}")
            return dates

        except Exception as e:
            logger.warning(f"Failed to load trading calendar: {e}. Using empty set.")
            return set()
