"""Tests for PipelineErrorHandler."""

import pytest
from infrastructure.pipeline.error_handler import (
    PipelineErrorHandler,
    RetryStrategy,
    SkipStrategy,
    FailFastStrategy,
    ContinueStrategy,
    DataSourceTimeout,
    DataQualityError,
    DatabaseError,
)


class TestErrorStrategies:
    """Test error handling strategies."""

    def test_retry_strategy_creation(self):
        """Test RetryStrategy initialization."""
        strategy = RetryStrategy(max_retries=3, backoff_seconds=[5, 10, 20])
        assert strategy.max_retries == 3
        assert strategy.backoff_seconds == [5, 10, 20]
        assert strategy.strategy_type == 'retry'

    def test_skip_strategy_creation(self):
        """Test SkipStrategy initialization."""
        strategy = SkipStrategy(scope='symbol', log_level='warning')
        assert strategy.scope == 'symbol'
        assert strategy.log_level == 'warning'
        assert strategy.strategy_type == 'skip'

    def test_fail_fast_strategy_creation(self):
        """Test FailFastStrategy initialization."""
        strategy = FailFastStrategy(rollback=True)
        assert strategy.rollback is True
        assert strategy.strategy_type == 'fail_fast'

    def test_continue_strategy_creation(self):
        """Test ContinueStrategy initialization."""
        strategy = ContinueStrategy(log_level='error')
        assert strategy.log_level == 'error'
        assert strategy.strategy_type == 'continue'


class TestPipelineErrorHandler:
    """Test PipelineErrorHandler."""

    def test_handle_data_source_timeout(self):
        """Test handling DataSourceTimeout returns RetryStrategy."""
        handler = PipelineErrorHandler()
        error = DataSourceTimeout("API timeout")
        context = {'stage': 'DataFetchStage', 'symbol': '000001.SH'}

        strategy = handler.handle_stage_error('DataFetchStage', error, context)

        assert isinstance(strategy, RetryStrategy)
        assert strategy.max_retries == 3
        assert len(strategy.backoff_seconds) == 3

    def test_handle_data_quality_error(self):
        """Test handling DataQualityError returns SkipStrategy."""
        handler = PipelineErrorHandler()
        error = DataQualityError("Invalid price data")
        context = {'stage': 'AnomalyDetectionStage', 'symbol': '000001.SH'}

        strategy = handler.handle_stage_error('AnomalyDetectionStage', error, context)

        assert isinstance(strategy, SkipStrategy)
        assert strategy.scope == 'symbol'
        assert strategy.log_level == 'warning'

    def test_handle_database_error(self):
        """Test handling DatabaseError returns FailFastStrategy."""
        handler = PipelineErrorHandler()
        error = DatabaseError("Connection lost")
        context = {'stage': 'StorageStage'}

        strategy = handler.handle_stage_error('StorageStage', error, context)

        assert isinstance(strategy, FailFastStrategy)
        assert strategy.rollback is True

    def test_handle_generic_error(self):
        """Test handling generic Exception returns ContinueStrategy."""
        handler = PipelineErrorHandler()
        error = ValueError("Unexpected error")
        context = {'stage': 'ImputationStage'}

        strategy = handler.handle_stage_error('ImputationStage', error, context)

        assert isinstance(strategy, ContinueStrategy)
        assert strategy.log_level == 'error'

    def test_custom_error_mapping(self):
        """Test custom error type mapping."""
        custom_mapping = {
            ValueError: lambda ctx: SkipStrategy(scope='record', log_level='info')
        }
        handler = PipelineErrorHandler(error_mapping=custom_mapping)
        error = ValueError("Custom handling")
        context = {}

        strategy = handler.handle_stage_error('TestStage', error, context)

        assert isinstance(strategy, SkipStrategy)
        assert strategy.scope == 'record'


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_data_source_timeout_exception(self):
        """Test DataSourceTimeout exception."""
        error = DataSourceTimeout("Timeout after 30s")
        assert str(error) == "Timeout after 30s"
        assert isinstance(error, Exception)

    def test_data_quality_error_exception(self):
        """Test DataQualityError exception."""
        error = DataQualityError("Price out of range")
        assert str(error) == "Price out of range"
        assert isinstance(error, Exception)

    def test_database_error_exception(self):
        """Test DatabaseError exception."""
        error = DatabaseError("Connection refused")
        assert str(error) == "Connection refused"
        assert isinstance(error, Exception)
