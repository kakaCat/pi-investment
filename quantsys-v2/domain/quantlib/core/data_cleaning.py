"""
数据清洗Pipeline - Team D
数据质量保证和清洗
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from docs.interfaces.quality_interface import IDataCleaner
import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class DataCleaningPipeline(IDataCleaner):
    """
    数据清洗Pipeline

    功能:
    1. 去重
    2. 缺失值处理
    3. 异常值检测
    4. 数据验证
    """

    def __init__(self,
                 outlier_method: str = 'iqr',
                 outlier_threshold: float = 3.0):
        """
        Args:
            outlier_method: 异常值检测方法 ('iqr', 'zscore', 'isolation_forest')
            outlier_threshold: 异常值阈值
        """
        self.outlier_method = outlier_method
        self.outlier_threshold = outlier_threshold

        logger.info(f"DataCleaningPipeline initialized: method={outlier_method}")

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗数据

        执行顺序:
        1. 去重
        2. 缺失值处理
        3. 异常值检测和处理
        """
        logger.info(f"Starting data cleaning: {len(df)} rows")

        # 1. 去重
        df = self._remove_duplicates(df)

        # 2. 缺失值处理
        df = self._handle_missing_values(df)

        # 3. 异常值处理
        df = self._handle_outliers(df)

        logger.info(f"Data cleaning completed: {len(df)} rows remaining")

        return df

    def validate(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        验证数据质量

        Returns:
            {
                'has_duplicates': bool,
                'has_missing': bool,
                'has_outliers': bool,
                'is_valid': bool
            }
        """
        has_duplicates = df.duplicated().any()
        has_missing = df.isnull().any().any()
        has_outliers = self._detect_outliers(df).any()

        is_valid = not (has_duplicates or has_missing or has_outliers)

        result = {
            'has_duplicates': bool(has_duplicates),
            'has_missing': bool(has_missing),
            'has_outliers': bool(has_outliers),
            'is_valid': bool(is_valid)
        }

        logger.info(f"Data validation: {result}")

        return result

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """去重"""
        before = len(df)

        # 如果有symbol和date列，基于这两列去重
        if 'symbol' in df.columns and 'date' in df.columns:
            df = df.drop_duplicates(subset=['symbol', 'date'], keep='last')
        else:
            df = df.drop_duplicates(keep='last')

        after = len(df)
        removed = before - after

        if removed > 0:
            logger.info(f"Removed {removed} duplicate rows")

        return df

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理缺失值"""
        # 价格字段：前向填充
        price_cols = [col for col in ['open', 'high', 'low', 'close', 'price']
                     if col in df.columns]
        if price_cols:
            df[price_cols] = df[price_cols].ffill()
            df[price_cols] = df[price_cols].bfill()

        # 成交量：填充0
        volume_cols = [col for col in ['volume', 'amount']
                      if col in df.columns]
        if volume_cols:
            df[volume_cols] = df[volume_cols].fillna(0)

        # 其他数值列：填充中位数
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col not in price_cols + volume_cols:
                df[col] = df[col].fillna(df[col].median())

        # 删除仍有缺失值的行
        before = len(df)
        df = df.dropna()
        after = len(df)

        if before > after:
            logger.info(f"Dropped {before - after} rows with missing values")

        return df

    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理异常值"""
        outlier_mask = self._detect_outliers(df)

        if outlier_mask.any():
            n_outliers = outlier_mask.sum()
            logger.info(f"Detected {n_outliers} outlier rows")

            # 删除异常值行
            df = df[~outlier_mask]

        return df

    def _detect_outliers(self, df: pd.DataFrame) -> pd.Series:
        """
        检测异常值

        Returns:
            布尔Series，True表示异常值
        """
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        if len(numeric_cols) == 0:
            return pd.Series([False] * len(df), index=df.index)

        if self.outlier_method == 'iqr':
            return self._detect_outliers_iqr(df[numeric_cols])
        elif self.outlier_method == 'zscore':
            return self._detect_outliers_zscore(df[numeric_cols])
        elif self.outlier_method == 'isolation_forest':
            return self._detect_outliers_isolation_forest(df[numeric_cols])
        else:
            logger.warning(f"Unknown outlier method: {self.outlier_method}")
            return pd.Series([False] * len(df), index=df.index)

    def _detect_outliers_iqr(self, df: pd.DataFrame) -> pd.Series:
        """IQR方法检测异常值"""
        outlier_mask = pd.Series([False] * len(df), index=df.index)

        for col in df.columns:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1

            lower_bound = Q1 - self.outlier_threshold * IQR
            upper_bound = Q3 + self.outlier_threshold * IQR

            col_outliers = (df[col] < lower_bound) | (df[col] > upper_bound)
            outlier_mask = outlier_mask | col_outliers

        return outlier_mask

    def _detect_outliers_zscore(self, df: pd.DataFrame) -> pd.Series:
        """Z-score方法检测异常值"""
        outlier_mask = pd.Series([False] * len(df), index=df.index)

        for col in df.columns:
            z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
            col_outliers = z_scores > self.outlier_threshold
            outlier_mask = outlier_mask | col_outliers

        return outlier_mask

    def _detect_outliers_isolation_forest(self, df: pd.DataFrame) -> pd.Series:
        """Isolation Forest方法检测异常值"""
        try:
            from sklearn.ensemble import IsolationForest

            clf = IsolationForest(contamination=0.01, random_state=42)
            outlier_labels = clf.fit_predict(df)

            # -1表示异常值
            outlier_mask = pd.Series(outlier_labels == -1, index=df.index)

            return outlier_mask
        except ImportError:
            logger.warning("sklearn not available, falling back to IQR method")
            return self._detect_outliers_iqr(df)

    def get_cleaning_report(self, df_before: pd.DataFrame,
                           df_after: pd.DataFrame) -> Dict:
        """
        生成清洗报告

        Returns:
            {
                'rows_before': int,
                'rows_after': int,
                'rows_removed': int,
                'removal_rate': float,
                'columns': int,
                'missing_before': int,
                'missing_after': int
            }
        """
        rows_before = len(df_before)
        rows_after = len(df_after)
        rows_removed = rows_before - rows_after

        return {
            'rows_before': rows_before,
            'rows_after': rows_after,
            'rows_removed': rows_removed,
            'removal_rate': rows_removed / rows_before if rows_before > 0 else 0,
            'columns': len(df_after.columns),
            'missing_before': int(df_before.isnull().sum().sum()),
            'missing_after': int(df_after.isnull().sum().sum())
        }
