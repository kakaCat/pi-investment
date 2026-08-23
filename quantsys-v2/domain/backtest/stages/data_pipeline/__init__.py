# quant/stages/data/__init__.py
"""
Data processing stages for the pipeline.

Stages:
1. DataFetchStage - Multi-source data acquisition
2. DeduplicationStage - Remove duplicates
3. TimeAlignmentStage - Calendar and timezone alignment
4. AnomalyDetectionStage - Data quality checks
5. ConflictResolutionStage - Multi-source conflict resolution
6. ImputationStage - Fill missing values
7. StorageStage - Three-layer database writes
8. FactorComputeStage - Trigger factor computation
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PipelineContext:
    """Context passed between pipeline stages."""
    data: Any
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result returned by each pipeline stage."""
    success: bool
    data: Any
    errors: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = [
    'PipelineContext',
    'PipelineResult',
]
