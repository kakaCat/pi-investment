"""DataPipelineService - Orchestrates the 8-stage data processing pipeline."""

import structlog
from typing import List, Optional
import yaml

from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult
from domain.quantlib.stages.data_pipeline.data_fetch_stage import DataFetchStage
from domain.quantlib.stages.data_pipeline.deduplication_stage import DeduplicationStage
from domain.quantlib.stages.data_pipeline.time_alignment_stage import TimeAlignmentStage
from domain.quantlib.stages.data_pipeline.anomaly_detection_stage import AnomalyDetectionStage
from domain.quantlib.stages.data_pipeline.conflict_resolution_stage import ConflictResolutionStage
from domain.quantlib.stages.data_pipeline.imputation_stage import ImputationStage
from domain.quantlib.stages.data_pipeline.storage_stage import StorageStage
from domain.quantlib.stages.data_pipeline.factor_compute_stage import FactorComputeStage
from domain.quantlib.data_validator import DataValidator
from adapters.outbound.repositories import KlineORMRepository, FactorORMRepository

logger = structlog.get_logger(__name__)


class DataPipelineService:
    """Orchestration service for the 8-stage data processing pipeline.

    This service combines all pipeline stages into a cohesive workflow:
    1. DataFetchStage - Multi-source data acquisition
    2. DeduplicationStage - Remove duplicates
    3. TimeAlignmentStage - Calendar and timezone alignment
    4. AnomalyDetectionStage - Data quality checks
    5. ConflictResolutionStage - Multi-source conflict resolution
    6. ImputationStage - Fill missing values
    7. StorageStage - Three-layer database writes
    8. FactorComputeStage - Trigger factor computation

    Usage:
        >>> service = DataPipelineService()
        >>> result = service.run_daily_update(
        ...     symbols=['600000.SH', '000001.SZ'],
        ...     date='2026-05-27'
        ... )
        >>> print(f"Success: {result.success}")
    """

    def __init__(self, config_path: str = 'config/data_pipeline.yaml'):
        """Initialize DataPipelineService.

        Args:
            config_path: Path to pipeline configuration YAML file

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid YAML
        """
        self.config_path = config_path
        self.config = self._load_config()
        logger.info(f"DataPipelineService initialized with config from {config_path}")

    def _load_config(self) -> dict:
        """Load pipeline configuration from YAML file.

        Returns:
            Dictionary containing pipeline configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid YAML
            ValueError: If 'pipeline' key missing from config
        """
        try:
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
                return config_data['pipeline']
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in config file: {e}")
            raise
        except KeyError:
            logger.error("Config file missing 'pipeline' key")
            raise ValueError("Config file must contain 'pipeline' key")

    def run_daily_update(
        self,
        symbols: List[str],
        date: str
    ) -> PipelineResult:
        """Run daily data update for specific symbols and date.

        This method builds and executes the full 8-stage pipeline for a single date.

        Args:
            symbols: List of stock symbols (e.g., ['600000.SH', '000001.SZ'])
            date: Date string in 'YYYY-MM-DD' format

        Returns:
            PipelineResult with success status, data, errors, and metadata

        Raises:
            ValueError: If symbols is empty or date is invalid
        """
        # Validate inputs
        if not symbols:
            raise ValueError("symbols list cannot be empty")
        if not date:
            raise ValueError("date parameter is required")

        logger.info(f"Starting daily update for {len(symbols)} symbols on {date}")

        # Build pipeline with all 8 stages
        pipeline_stages = self._build_pipeline(
            symbols=symbols,
            date_range=(date, date)
        )

        # Execute pipeline
        result = self._execute_pipeline(pipeline_stages)

        if result.success:
            logger.info(f"Daily update completed successfully for {date}")
        else:
            logger.error(f"Daily update failed for {date}: {result.errors}")

        return result

    def run_full_rebuild(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> PipelineResult:
        """Run full rebuild for date range.

        This method processes historical data for a date range, useful for
        backfilling or rebuilding factors.

        Args:
            symbols: List of stock symbols
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format

        Returns:
            PipelineResult with success status, data, errors, and metadata

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate inputs
        if not symbols:
            raise ValueError("symbols list cannot be empty")
        if not start_date:
            raise ValueError("start_date parameter is required")
        if not end_date:
            raise ValueError("end_date parameter is required")

        logger.info(
            f"Starting full rebuild for {len(symbols)} symbols "
            f"from {start_date} to {end_date}"
        )

        # Build pipeline with all 8 stages
        pipeline_stages = self._build_pipeline(
            symbols=symbols,
            date_range=(start_date, end_date)
        )

        # Execute pipeline
        result = self._execute_pipeline(pipeline_stages)

        if result.success:
            logger.info(f"Full rebuild completed successfully")
        else:
            logger.error(f"Full rebuild failed: {result.errors}")

        return result

    def _build_pipeline(
        self,
        symbols: List[str],
        date_range: tuple
    ) -> List:
        """Build pipeline with all 8 stages.

        Args:
            symbols: List of stock symbols
            date_range: Tuple of (start_date, end_date)

        Returns:
            List of pipeline stage instances
        """
        stages = []

        # Stage 1: Data Fetch
        stages.append(DataFetchStage(
            sources=self.config.get('sources', ['akshare']),
            symbols=symbols,
            date_range=date_range
        ))

        # Stage 2: Deduplication
        stages.append(DeduplicationStage())

        # Stage 3: Time Alignment
        stages.append(TimeAlignmentStage(
            calendar=self.config.get('calendar', 'SSE'),
            timezone=self.config.get('timezone', 'Asia/Shanghai')
        ))

        # Stage 4: Anomaly Detection
        # Create DataValidator (uses default rules from config)
        validator = DataValidator(strict_mode=False)
        stages.append(AnomalyDetectionStage(validator=validator))

        # Stage 5: Conflict Resolution
        stages.append(ConflictResolutionStage())

        # Stage 6: Imputation
        stages.append(ImputationStage())

        # Stage 7: Storage (Application 层注入具体仓储,domain 只依赖接口)
        kline_repo = KlineORMRepository()
        stages.append(StorageStage(kline_repo=kline_repo))

        # Stage 8: Factor Compute
        stages.append(FactorComputeStage(
            kline_repo=kline_repo,
            factor_repo=FactorORMRepository()
        ))

        logger.info(f"Built pipeline with {len(stages)} stages")
        return stages

    def _execute_pipeline(self, stages: List) -> PipelineResult:
        """Execute pipeline stages sequentially.

        Args:
            stages: List of pipeline stage instances

        Returns:
            PipelineResult from the final stage or first failed stage
        """
        # Initialize context with config
        context = PipelineContext(
            data={},
            config=self.config,
            metadata={}
        )

        # Execute each stage
        for i, stage in enumerate(stages):
            stage_name = stage.__class__.__name__
            logger.info(f"Executing stage {i+1}/{len(stages)}: {stage_name}")

            try:
                result = stage.execute(context)

                if not result.success:
                    logger.error(f"Stage {stage_name} failed: {result.errors}")
                    return result

                # Update context for next stage
                context = PipelineContext(
                    data=result.data,
                    config=context.config,
                    metadata={**context.metadata, **result.metadata}
                )

                logger.info(f"Stage {stage_name} completed successfully")

            except Exception as e:
                logger.exception(f"Stage {stage_name} raised exception: {e}")
                return PipelineResult(
                    success=False,
                    data=context.data,
                    errors=[{
                        'stage': stage_name,
                        'error': str(e),
                        'type': type(e).__name__
                    }],
                    metadata=context.metadata
                )

        # All stages succeeded
        return PipelineResult(
            success=True,
            data=context.data,
            errors=[],
            metadata=context.metadata
        )
