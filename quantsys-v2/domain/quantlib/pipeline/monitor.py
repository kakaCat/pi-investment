"""Data pipeline monitoring and metrics tracking.

This module provides monitoring capabilities for the data pipeline:
- Track stage execution times
- Record success/failure status
- Count records processed
- Publish metrics to event bus
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DataPipelineMonitor:
    """Monitor for data pipeline execution.

    Tracks metrics for each pipeline stage:
    - Start/end times
    - Duration
    - Success/failure status
    - Records processed
    - Errors encountered

    Usage:
        >>> from infrastructure.events.event_bus import event_bus
        >>> monitor = DataPipelineMonitor(event_bus)
        >>> monitor.on_stage_start('DataFetchStage')
        >>> # ... stage execution ...
        >>> monitor.on_stage_complete('DataFetchStage', result)
        >>> print(monitor.get_metrics())
    """

    def __init__(self, event_bus=None):
        """Initialize pipeline monitor.

        Args:
            event_bus: Event bus for publishing metrics (optional)
        """
        self.event_bus = event_bus
        self.metrics: Dict[str, Dict[str, Any]] = {}

    def on_stage_start(self, stage_name: str):
        """Record stage start.

        Args:
            stage_name: Name of the pipeline stage
        """
        self.metrics[stage_name] = {
            'start_time': datetime.now(),
            'status': 'running'
        }
        logger.debug(f"Stage '{stage_name}' started")

    def on_stage_complete(self, stage_name: str, result):
        """Record stage completion.

        Args:
            stage_name: Name of the pipeline stage
            result: PipelineResult object with success status
        """
        if stage_name not in self.metrics:
            logger.warning(f"Stage '{stage_name}' completed but was never started")
            return

        # Calculate duration
        start_time = self.metrics[stage_name]['start_time']
        duration = (datetime.now() - start_time).total_seconds()

        # Update metrics
        self.metrics[stage_name].update({
            'duration': duration,
            'status': 'success' if result.success else 'failed'
        })

        logger.info(
            f"Stage '{stage_name}' completed in {duration:.2f}s "
            f"(status: {self.metrics[stage_name]['status']})"
        )

        # Publish event if event bus available
        if self.event_bus:
            self.event_bus.publish('pipeline.stage.completed', {
                'stage': stage_name,
                'metrics': self.metrics[stage_name]
            })

    def on_stage_error(self, stage_name: str, error: Exception):
        """Record stage error.

        Args:
            stage_name: Name of the pipeline stage
            error: Exception that occurred
        """
        if stage_name not in self.metrics:
            self.metrics[stage_name] = {'start_time': datetime.now()}

        # Calculate duration if stage was started
        start_time = self.metrics[stage_name].get('start_time')
        duration = None
        if start_time:
            duration = (datetime.now() - start_time).total_seconds()

        # Update metrics
        self.metrics[stage_name].update({
            'status': 'error',
            'error': str(error),
            'error_type': type(error).__name__
        })

        if duration is not None:
            self.metrics[stage_name]['duration'] = duration

        logger.error(f"Stage '{stage_name}' error: {error}")

        # Publish event if event bus available
        if self.event_bus:
            self.event_bus.publish('pipeline.stage.error', {
                'stage': stage_name,
                'error': str(error),
                'metrics': self.metrics[stage_name]
            })

    def track_records_processed(self, stage_name: str, count: int):
        """Track number of records processed by stage.

        Args:
            stage_name: Name of the pipeline stage
            count: Number of records processed
        """
        if stage_name not in self.metrics:
            logger.warning(f"Cannot track records for unknown stage '{stage_name}'")
            return

        self.metrics[stage_name]['records_processed'] = count
        logger.debug(f"Stage '{stage_name}' processed {count} records")

    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get all metrics.

        Returns:
            Dictionary of stage metrics
        """
        return self.metrics.copy()

    def get_stage_metrics(self, stage_name: str) -> Optional[Dict[str, Any]]:
        """Get metrics for specific stage.

        Args:
            stage_name: Name of the pipeline stage

        Returns:
            Stage metrics dictionary or None if stage not found
        """
        return self.metrics.get(stage_name)

    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get summary of entire pipeline execution.

        Returns:
            Dictionary with pipeline summary statistics
        """
        total_stages = len(self.metrics)
        successful_stages = sum(
            1 for m in self.metrics.values() if m.get('status') == 'success'
        )
        failed_stages = sum(
            1 for m in self.metrics.values() if m.get('status') == 'failed'
        )
        error_stages = sum(
            1 for m in self.metrics.values() if m.get('status') == 'error'
        )

        # Calculate total duration
        total_duration = sum(
            m.get('duration', 0) for m in self.metrics.values()
        )

        # Calculate total records processed
        total_records = sum(
            m.get('records_processed', 0) for m in self.metrics.values()
        )

        return {
            'total_stages': total_stages,
            'successful_stages': successful_stages,
            'failed_stages': failed_stages,
            'error_stages': error_stages,
            'total_duration': total_duration,
            'total_records_processed': total_records
        }

    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics.clear()
        logger.info("Pipeline metrics reset")
