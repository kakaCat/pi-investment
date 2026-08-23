"""AnomalyDetectionStage - Data quality checks (Priority 2).

This stage integrates with the existing DataValidator to detect anomalies
and assess data quality for each data source in the pipeline.

Features:
- Price jump detection (>50% changes)
- Volume spike detection (Z-score > 3)
- Quality score assignment
- Comprehensive quality reports
"""

import logging
import pandas as pd
from typing import Dict

from domain.backtest.stages.data_pipeline import PipelineContext, PipelineResult
from domain.quantlib.data_validator import DataValidator

logger = logging.getLogger(__name__)


class AnomalyDetectionStage:
    """Detect anomalies and assess data quality using DataValidator."""

    def __init__(self, validator: DataValidator):
        """
        Initialize the anomaly detection stage.

        Args:
            validator: DataValidator instance for quality checks
        """
        self.validator = validator

    def execute(self, context: PipelineContext) -> PipelineResult:
        """
        Execute anomaly detection on all data sources.

        Args:
            context: Pipeline context containing data from multiple sources

        Returns:
            PipelineResult with cleaned data and quality reports
        """
        results = {}
        quality_reports = {}

        for source, df in context.data.items():
            try:
                # Validate price data using existing DataValidator
                cleaned_df, report = self.validator.validate_financial_data(
                    df,
                    data_type='prices',
                    data_name=f"{source}_klines"
                )

                # Add quality score to each record
                cleaned_df['quality_score'] = report.quality_score

                results[source] = cleaned_df
                quality_reports[source] = report.to_dict()

                # Log critical issues
                for issue in report.issues:
                    if issue['severity'] in ['high', 'critical']:
                        logger.warning(f"{source}: {issue['description']}")

                logger.info(f"{source}: Quality score = {report.quality_score:.1f}")

            except Exception as e:
                logger.error(f"Error processing {source}: {str(e)}")
                # On error, pass through original data with low quality score
                if isinstance(df, pd.DataFrame):
                    df['quality_score'] = 0.0
                    results[source] = df
                else:
                    # If not a DataFrame, create an empty one
                    results[source] = pd.DataFrame()

                quality_reports[source] = {
                    'data_name': f"{source}_klines",
                    'quality_score': 0.0,
                    'issues': [{'type': 'processing_error', 'description': str(e), 'severity': 'critical'}],
                    'warnings': [],
                    'statistics': {},
                    'recommendations': ['Fix processing error before using data']
                }

        return PipelineResult(
            success=True,
            data=results,
            errors=[],
            metadata={'quality_reports': quality_reports}
        )
