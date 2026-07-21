"""Tests for DataPipelineService."""

import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime
import yaml

from application.services.data_pipeline_service import DataPipelineService
from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult


class TestDataPipelineService:
    """Test suite for DataPipelineService."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration data."""
        return {
            'pipeline': {
                'name': 'daily_data_update',
                'sources': ['akshare', 'tushare'],
                'calendar': 'SSE',
                'timezone': 'Asia/Shanghai',
                'conflict_strategy': 'priority',
                'execution': {
                    'mode': 'incremental',
                    'batch_size': 50,
                    'parallel': True,
                    'max_workers': 4
                },
                'quality': {
                    'min_score': 60,
                    'max_error_rate': 0.1,
                    'price_jump_threshold': 0.5,
                    'volume_zscore_threshold': 3.0
                },
                'imputation': {
                    'price_method': 'ffill',
                    'volume_method': 'zero'
                },
                'failure_handling': {
                    'on_all_sources_fail': 'use_cache',
                    'on_quality_threshold_breach': 'log_warning',
                    'stale_data_max_age_days': 7
                }
            }
        }

    @pytest.fixture
    def service(self, mock_config):
        """Create DataPipelineService with mocked config."""
        yaml_content = yaml.dump(mock_config)
        with patch('builtins.open', mock_open(read_data=yaml_content)):
            return DataPipelineService()

    def test_init_loads_config(self, mock_config):
        """Test that __init__ loads configuration from YAML file."""
        yaml_content = yaml.dump(mock_config)
        with patch('builtins.open', mock_open(read_data=yaml_content)) as mock_file:
            service = DataPipelineService()

            # Verify file was opened
            mock_file.assert_called_once_with('config/data_pipeline.yaml', 'r')

            # Verify config was loaded
            assert service.config == mock_config['pipeline']
            assert service.config['sources'] == ['akshare', 'tushare']
            assert service.config['calendar'] == 'SSE'

    def test_init_with_custom_config_path(self, mock_config):
        """Test initialization with custom config path."""
        yaml_content = yaml.dump(mock_config)
        custom_path = '/custom/path/config.yaml'

        with patch('builtins.open', mock_open(read_data=yaml_content)) as mock_file:
            service = DataPipelineService(config_path=custom_path)

            mock_file.assert_called_once_with(custom_path, 'r')
            assert service.config == mock_config['pipeline']

    def test_init_raises_on_missing_config_file(self):
        """Test that __init__ raises FileNotFoundError if config file is missing."""
        with patch('builtins.open', side_effect=FileNotFoundError("Config not found")):
            with pytest.raises(FileNotFoundError):
                DataPipelineService()

    def test_init_raises_on_invalid_yaml(self):
        """Test that __init__ raises yaml.YAMLError on invalid YAML."""
        with patch('builtins.open', mock_open(read_data="invalid: yaml: content:")):
            with pytest.raises(yaml.YAMLError):
                DataPipelineService()

    def test_init_raises_on_missing_pipeline_key(self):
        """Test that __init__ raises ValueError if config missing 'pipeline' key."""
        yaml_content = yaml.dump({'other_key': 'value'})
        with patch('builtins.open', mock_open(read_data=yaml_content)):
            with pytest.raises(ValueError, match="pipeline"):
                DataPipelineService()

    @patch('services.data_pipeline_service.DataFetchStage')
    @patch('services.data_pipeline_service.DeduplicationStage')
    @patch('services.data_pipeline_service.TimeAlignmentStage')
    @patch('services.data_pipeline_service.AnomalyDetectionStage')
    @patch('services.data_pipeline_service.ConflictResolutionStage')
    @patch('services.data_pipeline_service.ImputationStage')
    @patch('services.data_pipeline_service.StorageStage')
    @patch('services.data_pipeline_service.FactorComputeStage')
    def test_run_daily_update_builds_pipeline_with_all_stages(
        self,
        mock_factor_stage,
        mock_storage_stage,
        mock_imputation_stage,
        mock_conflict_stage,
        mock_anomaly_stage,
        mock_time_stage,
        mock_dedup_stage,
        mock_fetch_stage,
        service
    ):
        """Test that run_daily_update builds pipeline with all 8 stages."""
        # Setup mock stages
        mock_stages = [
            mock_fetch_stage.return_value,
            mock_dedup_stage.return_value,
            mock_time_stage.return_value,
            mock_anomaly_stage.return_value,
            mock_conflict_stage.return_value,
            mock_imputation_stage.return_value,
            mock_storage_stage.return_value,
            mock_factor_stage.return_value
        ]

        # Mock execute to return success
        for stage in mock_stages:
            stage.execute.return_value = PipelineResult(
                success=True,
                data={'test': 'data'},
                metadata={'stage': 'completed'}
            )

        # Execute
        result = service.run_daily_update(
            symbols=['000001.SH', '000001.SZ'],
            date='2026-05-27'
        )

        # Verify all stages were instantiated
        mock_fetch_stage.assert_called_once()
        mock_dedup_stage.assert_called_once()
        mock_time_stage.assert_called_once()
        mock_anomaly_stage.assert_called_once()
        mock_conflict_stage.assert_called_once()
        mock_imputation_stage.assert_called_once()
        mock_storage_stage.assert_called_once()
        mock_factor_stage.assert_called_once()

        # Verify all stages were executed
        for stage in mock_stages:
            stage.execute.assert_called_once()

        # Verify result
        assert result.success is True
        assert result.data == {'test': 'data'}

    @patch('services.data_pipeline_service.DataFetchStage')
    def test_run_daily_update_passes_correct_params_to_fetch_stage(
        self,
        mock_fetch_stage,
        service
    ):
        """Test that DataFetchStage receives correct parameters."""
        mock_stage = Mock()
        mock_stage.execute.return_value = PipelineResult(
            success=True,
            data={},
            metadata={}
        )
        mock_fetch_stage.return_value = mock_stage

        symbols = ['000001.SH', '000001.SZ']
        date = '2026-05-27'

        service.run_daily_update(symbols=symbols, date=date)

        # Verify DataFetchStage was called with correct parameters
        call_args = mock_fetch_stage.call_args
        assert call_args[1]['sources'] == ['akshare', 'tushare']
        assert call_args[1]['symbols'] == symbols
        assert call_args[1]['date_range'] == (date, date)

    @patch('services.data_pipeline_service.DataFetchStage')
    @patch('services.data_pipeline_service.DeduplicationStage')
    def test_run_daily_update_stops_on_stage_failure(
        self,
        mock_dedup_stage,
        mock_fetch_stage,
        service
    ):
        """Test that pipeline stops when a stage fails."""
        # First stage succeeds
        mock_fetch = Mock()
        mock_fetch.execute.return_value = PipelineResult(
            success=True,
            data={'source1': 'data'},
            metadata={}
        )
        mock_fetch_stage.return_value = mock_fetch

        # Second stage fails
        mock_dedup = Mock()
        mock_dedup.execute.return_value = PipelineResult(
            success=False,
            data={},
            errors=[{'stage': 'deduplication', 'error': 'Failed to deduplicate'}],
            metadata={}
        )
        mock_dedup_stage.return_value = mock_dedup

        # Execute
        result = service.run_daily_update(
            symbols=['000001.SH'],
            date='2026-05-27'
        )

        # Verify pipeline stopped at failure
        assert result.success is False
        assert len(result.errors) > 0
        mock_fetch.execute.assert_called_once()
        mock_dedup.execute.assert_called_once()

    @patch('services.data_pipeline_service.DataFetchStage')
    @patch('services.data_pipeline_service.DeduplicationStage')
    @patch('services.data_pipeline_service.TimeAlignmentStage')
    @patch('services.data_pipeline_service.AnomalyDetectionStage')
    @patch('services.data_pipeline_service.ConflictResolutionStage')
    @patch('services.data_pipeline_service.ImputationStage')
    @patch('services.data_pipeline_service.StorageStage')
    @patch('services.data_pipeline_service.FactorComputeStage')
    def test_run_full_rebuild_processes_date_range(
        self,
        mock_factor_stage,
        mock_storage_stage,
        mock_imputation_stage,
        mock_conflict_stage,
        mock_anomaly_stage,
        mock_time_stage,
        mock_dedup_stage,
        mock_fetch_stage,
        service
    ):
        """Test that run_full_rebuild processes a date range."""
        # Setup mock stages
        mock_stages = [
            mock_fetch_stage.return_value,
            mock_dedup_stage.return_value,
            mock_time_stage.return_value,
            mock_anomaly_stage.return_value,
            mock_conflict_stage.return_value,
            mock_imputation_stage.return_value,
            mock_storage_stage.return_value,
            mock_factor_stage.return_value
        ]

        for stage in mock_stages:
            stage.execute.return_value = PipelineResult(
                success=True,
                data={'test': 'data'},
                metadata={}
            )

        # Execute
        result = service.run_full_rebuild(
            symbols=['000001.SH'],
            start_date='2026-05-01',
            end_date='2026-05-27'
        )

        # Verify DataFetchStage received date range
        call_args = mock_fetch_stage.call_args
        assert call_args[1]['date_range'] == ('2026-05-01', '2026-05-27')

        # Verify result
        assert result.success is True

    def test_run_daily_update_validates_symbols(self, service):
        """Test that run_daily_update validates symbols parameter."""
        with pytest.raises(ValueError, match="symbols.*cannot be empty"):
            service.run_daily_update(symbols=[], date='2026-05-27')

    def test_run_daily_update_validates_date(self, service):
        """Test that run_daily_update validates date parameter."""
        with pytest.raises(ValueError, match="date.*required"):
            service.run_daily_update(symbols=['000001.SH'], date='')

    def test_run_full_rebuild_validates_date_range(self, service):
        """Test that run_full_rebuild validates date range."""
        with pytest.raises(ValueError, match="start_date.*required"):
            service.run_full_rebuild(
                symbols=['000001.SH'],
                start_date='',
                end_date='2026-05-27'
            )

        with pytest.raises(ValueError, match="end_date.*required"):
            service.run_full_rebuild(
                symbols=['000001.SH'],
                start_date='2026-05-01',
                end_date=''
            )

    @patch('services.data_pipeline_service.DataFetchStage')
    def test_pipeline_context_includes_config(
        self,
        mock_fetch_stage,
        service
    ):
        """Test that pipeline context includes configuration."""
        mock_stage = Mock()

        def check_context(context):
            # Verify context has config
            assert isinstance(context, PipelineContext)
            assert 'sources' in context.config
            assert context.config['sources'] == ['akshare', 'tushare']
            return PipelineResult(success=True, data={}, metadata={})

        mock_stage.execute.side_effect = check_context
        mock_fetch_stage.return_value = mock_stage

        service.run_daily_update(symbols=['000001.SH'], date='2026-05-27')

        mock_stage.execute.assert_called_once()
