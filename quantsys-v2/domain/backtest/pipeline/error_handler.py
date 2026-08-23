"""Pipeline error handling strategies.

This module provides error handling strategies for the data pipeline:
- RetryStrategy: Retry with exponential backoff
- SkipStrategy: Skip failed item, continue with others
- FailFastStrategy: Stop immediately, rollback if needed
- ContinueStrategy: Log error, continue processing
"""

import logging
from typing import Dict, Any, Callable, Optional, List

logger = logging.getLogger(__name__)


# Custom Exception Classes
class DataSourceTimeout(Exception):
    """Raised when data source API times out."""
    pass


class DataQualityError(Exception):
    """Raised when data validation fails."""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail."""
    pass


# Strategy Classes
class RetryStrategy:
    """Retry strategy with exponential backoff."""

    def __init__(self, max_retries: int = 3, backoff_seconds: List[int] = None):
        """Initialize retry strategy.

        Args:
            max_retries: Maximum number of retry attempts
            backoff_seconds: List of backoff delays in seconds for each retry
        """
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds or [5, 10, 20]
        self.strategy_type = 'retry'


class SkipStrategy:
    """Skip strategy - skip failed item and continue."""

    def __init__(self, scope: str = 'symbol', log_level: str = 'warning'):
        """Initialize skip strategy.

        Args:
            scope: Scope of skip ('symbol', 'record', 'batch')
            log_level: Logging level for skipped items
        """
        self.scope = scope
        self.log_level = log_level
        self.strategy_type = 'skip'


class FailFastStrategy:
    """Fail fast strategy - stop immediately and rollback."""

    def __init__(self, rollback: bool = True):
        """Initialize fail fast strategy.

        Args:
            rollback: Whether to rollback changes on failure
        """
        self.rollback = rollback
        self.strategy_type = 'fail_fast'


class ContinueStrategy:
    """Continue strategy - log error and continue processing."""

    def __init__(self, log_level: str = 'error'):
        """Initialize continue strategy.

        Args:
            log_level: Logging level for errors
        """
        self.log_level = log_level
        self.strategy_type = 'continue'


class PipelineErrorHandler:
    """Pipeline error handler with configurable strategies.

    This handler maps error types to appropriate handling strategies:
    - DataSourceTimeout → RetryStrategy (retry with backoff)
    - DataQualityError → SkipStrategy (skip bad data)
    - DatabaseError → FailFastStrategy (stop and rollback)
    - Generic Exception → ContinueStrategy (log and continue)

    Usage:
        >>> handler = PipelineErrorHandler()
        >>> error = DataSourceTimeout("API timeout")
        >>> strategy = handler.handle_stage_error('DataFetchStage', error, {})
        >>> print(strategy.strategy_type)
        'retry'
    """

    def __init__(self, error_mapping: Optional[Dict[type, Callable]] = None):
        """Initialize error handler.

        Args:
            error_mapping: Custom error type to strategy mapping
        """
        self.error_mapping = error_mapping or self._default_error_mapping()

    def _default_error_mapping(self) -> Dict[type, Callable]:
        """Create default error type to strategy mapping.

        Returns:
            Dictionary mapping error types to strategy factory functions
        """
        return {
            DataSourceTimeout: lambda ctx: RetryStrategy(
                max_retries=3,
                backoff_seconds=[5, 10, 20]
            ),
            DataQualityError: lambda ctx: SkipStrategy(
                scope='symbol',
                log_level='warning'
            ),
            DatabaseError: lambda ctx: FailFastStrategy(
                rollback=True
            ),
        }

    def handle_stage_error(
        self,
        stage: str,
        error: Exception,
        context: Dict[str, Any]
    ):
        """Handle error from pipeline stage.

        Args:
            stage: Name of the pipeline stage
            error: Exception that occurred
            context: Context information (stage, symbol, etc.)

        Returns:
            Strategy instance (RetryStrategy, SkipStrategy, etc.)
        """
        error_type = type(error)

        # Check custom mapping first
        if error_type in self.error_mapping:
            strategy = self.error_mapping[error_type](context)
            logger.info(
                f"Stage '{stage}' error handled with {strategy.strategy_type} strategy: {error}"
            )
            return strategy

        # Default to ContinueStrategy for unknown errors
        logger.warning(
            f"Stage '{stage}' encountered unknown error type {error_type.__name__}: {error}"
        )
        return ContinueStrategy(log_level='error')
