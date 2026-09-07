"""TimeAlignmentStage - Time and calendar alignment (Priority 1)."""

import logging
import pandas as pd
from typing import Callable, Dict, Optional, Set
from datetime import date

from domain.backtest.stages.data_pipeline import PipelineContext, PipelineResult

logger = logging.getLogger(__name__)


class TimeAlignmentStage:
    """Align timestamps to trading calendar and timezone."""

    def __init__(
        self,
        calendar: str = 'SSE',
        timezone: str = 'Asia/Shanghai',
        calendar_loader: Optional[Callable[[str], Set[date]]] = None,
    ):
        """
        Initialize TimeAlignmentStage.

        Args:
            calendar: Exchange calendar to use (SSE, SZSE)
            timezone: Target timezone for alignment
            calendar_loader: 交易日历加载函数(由 Application 层注入),
                签名: (exchange: str) -> Set[date]。domain 层不直接访问
                数据库(六边形架构依赖方向);未注入时使用空日历。
        """
        self.calendar = calendar
        self.timezone = timezone
        self.calendar_loader = calendar_loader
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
        Load trading calendar via the injected calendar_loader.

        Returns:
            Set of trading dates for the specified exchange
        """
        if self.calendar_loader is None:
            logger.warning(
                "No calendar_loader injected. Using empty trading calendar."
            )
            return set()

        try:
            dates = self.calendar_loader(self.calendar) or set()
            logger.info(f"Loaded {len(dates)} trading days for {self.calendar}")
            return dates
        except Exception as e:
            logger.warning(f"Failed to load trading calendar: {e}. Using empty set.")
            return set()
