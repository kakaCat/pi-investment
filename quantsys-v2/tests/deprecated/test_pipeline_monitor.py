"""Tests for DataPipelineMonitor."""

import pytest
from datetime import datetime, timedelta
from infrastructure.pipeline.monitor import DataPipelineMonitor
from infrastructure.events.event_bus import EventBus


class TestDataPipelineMonitor:
    """Test DataPipelineMonitor."""

    def test_monitor_initialization(self):
        """Test monitor initialization."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        assert monitor.event_bus is event_bus
        assert monitor.metrics == {}

    def test_on_stage_start(self):
        """Test stage start tracking."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        monitor.on_stage_start('DataFetchStage')

        assert 'DataFetchStage' in monitor.metrics
        assert 'start_time' in monitor.metrics['DataFetchStage']
        assert monitor.metrics['DataFetchStage']['status'] == 'running'

    def test_on_stage_complete_success(self):
        """Test stage completion tracking for success."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        # Start stage
        monitor.on_stage_start('DataFetchStage')
        start_time = monitor.metrics['DataFetchStage']['start_time']

        # Complete stage
        result = type('Result', (), {'success': True, 'data': {}, 'errors': []})()
        monitor.on_stage_complete('DataFetchStage', result)

        assert monitor.metrics['DataFetchStage']['status'] == 'success'
        assert 'duration' in monitor.metrics['DataFetchStage']
        assert monitor.metrics['DataFetchStage']['duration'] >= 0

    def test_on_stage_complete_failure(self):
        """Test stage completion tracking for failure."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        # Start stage
        monitor.on_stage_start('StorageStage')

        # Complete stage with failure
        result = type('Result', (), {'success': False, 'data': {}, 'errors': ['DB error']})()
        monitor.on_stage_complete('StorageStage', result)

        assert monitor.metrics['StorageStage']['status'] == 'failed'
        assert 'duration' in monitor.metrics['StorageStage']

    def test_event_publishing(self):
        """Test that events are published to event bus."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        # Track published events
        published_events = []
        def capture_event(data):
            published_events.append(data)

        event_bus.subscribe('pipeline.stage.completed', capture_event)

        # Run stage
        monitor.on_stage_start('DataFetchStage')
        result = type('Result', (), {'success': True, 'data': {}, 'errors': []})()
        monitor.on_stage_complete('DataFetchStage', result)

        # Check event was published
        assert len(published_events) == 1
        assert published_events[0]['stage'] == 'DataFetchStage'
        assert 'metrics' in published_events[0]

    def test_get_metrics(self):
        """Test getting all metrics."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        # Run multiple stages
        for stage in ['DataFetchStage', 'DeduplicationStage', 'StorageStage']:
            monitor.on_stage_start(stage)
            result = type('Result', (), {'success': True, 'data': {}, 'errors': []})()
            monitor.on_stage_complete(stage, result)

        metrics = monitor.get_metrics()
        assert len(metrics) == 3
        assert 'DataFetchStage' in metrics
        assert 'DeduplicationStage' in metrics
        assert 'StorageStage' in metrics

    def test_get_stage_metrics(self):
        """Test getting metrics for specific stage."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        monitor.on_stage_start('DataFetchStage')
        result = type('Result', (), {'success': True, 'data': {}, 'errors': []})()
        monitor.on_stage_complete('DataFetchStage', result)

        stage_metrics = monitor.get_stage_metrics('DataFetchStage')
        assert stage_metrics is not None
        assert stage_metrics['status'] == 'success'
        assert 'duration' in stage_metrics

    def test_reset_metrics(self):
        """Test resetting metrics."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        monitor.on_stage_start('DataFetchStage')
        assert len(monitor.metrics) == 1

        monitor.reset_metrics()
        assert len(monitor.metrics) == 0

    def test_monitor_without_event_bus(self):
        """Test monitor works without event bus (logging only)."""
        monitor = DataPipelineMonitor(event_bus=None)

        # Should not raise error
        monitor.on_stage_start('DataFetchStage')
        result = type('Result', (), {'success': True, 'data': {}, 'errors': []})()
        monitor.on_stage_complete('DataFetchStage', result)

        assert 'DataFetchStage' in monitor.metrics
        assert monitor.metrics['DataFetchStage']['status'] == 'success'

    def test_on_stage_error(self):
        """Test stage error tracking."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        monitor.on_stage_start('DataFetchStage')
        error = Exception("Network timeout")
        monitor.on_stage_error('DataFetchStage', error)

        assert monitor.metrics['DataFetchStage']['status'] == 'error'
        assert 'error' in monitor.metrics['DataFetchStage']
        assert monitor.metrics['DataFetchStage']['error'] == str(error)

    def test_records_processed_tracking(self):
        """Test tracking records processed."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        monitor.on_stage_start('DataFetchStage')
        monitor.track_records_processed('DataFetchStage', 150)

        assert monitor.metrics['DataFetchStage']['records_processed'] == 150

    def test_pipeline_summary(self):
        """Test getting pipeline summary."""
        event_bus = EventBus()
        monitor = DataPipelineMonitor(event_bus)

        # Run pipeline stages
        stages = ['DataFetchStage', 'DeduplicationStage', 'StorageStage']
        for stage in stages:
            monitor.on_stage_start(stage)
            result = type('Result', (), {'success': True, 'data': {}, 'errors': []})()
            monitor.on_stage_complete(stage, result)

        summary = monitor.get_pipeline_summary()
        assert summary['total_stages'] == 3
        assert summary['successful_stages'] == 3
        assert summary['failed_stages'] == 0
        assert 'total_duration' in summary
