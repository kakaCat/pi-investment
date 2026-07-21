"""
数据清洗Pipeline测试 - Team D
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from domain.quantlib.core.data_cleaning import DataCleaningPipeline


class TestDataCleaningPipeline:
    """数据清洗Pipeline测试"""

    @pytest.fixture
    def pipeline(self):
        """创建Pipeline实例"""
        return DataCleaningPipeline(outlier_method='iqr')

    @pytest.fixture
    def dirty_data(self):
        """创建脏数据"""
        np.random.seed(42)
        data = {
            'symbol': ['000001'] * 100,
            'date': pd.date_range('2024-01-01', periods=100),
            'close': np.random.normal(100, 10, 100),
            'volume': np.random.randint(1000, 10000, 100)
        }
        df = pd.DataFrame(data)

        # 添加重复行
        df = pd.concat([df, df.iloc[:5]], ignore_index=True)

        # 添加缺失值
        df.loc[10:15, 'close'] = np.nan

        # 添加异常值
        df.loc[20, 'close'] = 1000  # 极端值

        return df

    def test_initialization(self, pipeline):
        """测试初始化"""
        assert pipeline is not None
        assert pipeline.outlier_method == 'iqr'

    def test_clean_removes_duplicates(self, pipeline, dirty_data):
        """测试去重"""
        before = len(dirty_data)
        cleaned = pipeline.clean(dirty_data)
        after = len(cleaned)

        assert after < before
        assert not cleaned.duplicated().any()

    def test_clean_handles_missing(self, pipeline):
        """测试缺失值处理"""
        df = pd.DataFrame({
            'close': [100, np.nan, 102, 103],
            'volume': [1000, 2000, np.nan, 3000]
        })

        cleaned = pipeline.clean(df)

        assert not cleaned.isnull().any().any()

    def test_validate(self, pipeline, dirty_data):
        """测试数据验证"""
        result = pipeline.validate(dirty_data)

        assert 'has_duplicates' in result
        assert 'has_missing' in result
        assert 'has_outliers' in result
        assert 'is_valid' in result

        assert result['has_duplicates'] is True
        assert result['has_missing'] is True

    def test_validate_clean_data(self, pipeline, dirty_data):
        """测试清洗后的数据验证"""
        cleaned = pipeline.clean(dirty_data)
        result = pipeline.validate(cleaned)

        assert result['has_duplicates'] is False
        assert result['has_missing'] is False

    def test_get_cleaning_report(self, pipeline, dirty_data):
        """测试清洗报告"""
        cleaned = pipeline.clean(dirty_data)
        report = pipeline.get_cleaning_report(dirty_data, cleaned)

        assert 'rows_before' in report
        assert 'rows_after' in report
        assert 'rows_removed' in report
        assert report['rows_removed'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
