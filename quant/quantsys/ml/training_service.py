"""
ML 模型训练服务

功能：
1. 从 PostgreSQL 读取历史K线和因子数据
2. 构建训练集（特征 + 标签）
3. 时间序列交叉验证
4. 模型训练（XGBoost, LightGBM, RandomForest）
5. 模型评估和保存到 PostgreSQL
"""

import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class MLTrainingService:
    """ML 模型训练服务"""

    def __init__(self, db_connection):
        """
        Args:
            db_connection: PostgreSQL 数据库连接
        """
        self.conn = db_connection
        self.model_dir = Path.home() / '.pi-invest' / 'ml' / 'models'
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def load_training_data(
        self,
        days: int = 180,
        future_days: int = 5,
        return_threshold: float = 0.05,
        symbols: Optional[List[str]] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        从 PostgreSQL 加载训练数据

        Args:
            days: 历史数据天数
            future_days: 未来N天用于计算标签
            return_threshold: 涨幅阈值（小数形式，如 0.05 表示 5%）
            symbols: 股票代码列表，None 表示全部

        Returns:
            (features_df, labels_df): 特征数据框和标签数据框
        """
        logger.info("=" * 60)
        logger.info("加载训练数据")
        logger.info("=" * 60)

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        logger.info(f"数据起始日期: {cutoff_date}")

        # 构建 SQL 查询
        symbol_filter = ""
        params = [cutoff_date]
        if symbols:
            symbol_filter = f"AND symbol = ANY(%s)"
            params.append(symbols)

        # 加载 K线数据
        logger.info("加载K线数据...")
        klines_query = f"""
            SELECT
                symbol,
                trade_date as date,
                open, high, low, close,
                volume, amount, turnover_rate
            FROM quant.daily_klines
            WHERE trade_date >= %s {symbol_filter}
            ORDER BY symbol, trade_date
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(klines_query, params)
            klines_data = cur.fetchall()

        klines_df = pd.DataFrame(klines_data)

        if symbols:
            logger.info(f"  训练股票范围: {', '.join(symbols)}")
        logger.info(f"  加载 {len(klines_df)} 条K线记录")

        # 加载因子数据
        logger.info("加载因子数据...")
        factors_query = f"""
            SELECT
                symbol,
                factor_date as date,
                factor_name,
                factor_value
            FROM quant.factor_values
            WHERE factor_date >= %s {symbol_filter}
            ORDER BY symbol, factor_date, factor_name
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(factors_query, params)
            factors_data = cur.fetchall()

        factors_df = pd.DataFrame(factors_data)
        logger.info(f"  加载 {len(factors_df)} 条因子记录")

        if len(factors_df) == 0:
            raise ValueError("没有找到因子数据，请先运行因子计算")

        # 调试：检查列名
        logger.info(f"  因子数据列名: {list(factors_df.columns)}")

        # 转换因子数据格式（长格式 → 宽格式）
        logger.info("转换因子数据格式...")
        factors_pivot = factors_df.pivot_table(
            index=['symbol', 'date'],
            columns='factor_name',
            values='factor_value',
            aggfunc='first'
        ).reset_index()

        # 合并 K线和因子数据
        logger.info("合并K线和因子数据...")
        merged_df = pd.merge(
            klines_df,
            factors_pivot,
            on=['symbol', 'date'],
            how='left'
        )
        logger.info(f"  合并后 {len(merged_df)} 条记录")

        # 计算标签（未来收益率）
        logger.info(f"计算标签（未来{future_days}天收益率）...")
        merged_df = merged_df.sort_values(['symbol', 'date'])
        merged_df['future_return'] = merged_df.groupby('symbol')['close'].shift(-future_days) / merged_df['close'] - 1
        merged_df['label'] = (merged_df['future_return'] > return_threshold).astype(int)

        # 移除无法计算标签的最后几行
        merged_df = merged_df.dropna(subset=['future_return'])

        valid_samples = len(merged_df)
        positive_samples = merged_df['label'].sum()
        negative_samples = len(merged_df) - positive_samples

        logger.info(f"  有效样本数: {valid_samples}")
        logger.info("")
        logger.info("数据统计:")
        logger.info(f"  样本数: {valid_samples}")
        logger.info(f"  特征数: {len(merged_df.columns) - 4}")  # 减去 symbol, date, future_return, label
        logger.info(f"  股票数: {merged_df['symbol'].nunique()}")
        logger.info(f"  日期范围: {merged_df['date'].min()} ~ {merged_df['date'].max()}")
        logger.info(f"  正样本: {positive_samples} ({positive_samples/valid_samples*100:.1f}%)")
        logger.info(f"  负样本: {negative_samples} ({negative_samples/valid_samples*100:.1f}%)")
        logger.info("")

        return merged_df, merged_df[['symbol', 'date', 'label', 'future_return']]

    def prepare_features(self, data_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        准备训练特征

        Args:
            data_df: 合并后的数据框

        Returns:
            (X, y, feature_names): 特征矩阵、标签向量、特征名称列表
        """
        logger.info("准备训练特征...")

        # 排除非特征列
        exclude_cols = ['symbol', 'date', 'label', 'future_return']
        feature_cols = [col for col in data_df.columns if col not in exclude_cols]

        X = data_df[feature_cols].values
        y = data_df['label'].values

        logger.info(f"  特征矩阵: {X.shape}")
        logger.info(f"  标签向量: {y.shape}")
        logger.info(f"  特征名称: {len(feature_cols)}")

        return X, y, feature_cols

    def train_xgboost(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        n_splits: int = 5
    ) -> Dict[str, Any]:
        """
        训练 XGBoost 模型

        Args:
            X: 特征矩阵
            y: 标签向量
            feature_names: 特征名称列表
            n_splits: 交叉验证折数

        Returns:
            训练报告字典
        """
        import xgboost as xgb
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

        logger.info("=" * 60)
        logger.info("训练 XGBOOST 模型")
        logger.info("=" * 60)

        # 超参数
        params = {
            'max_depth': 5,
            'n_estimators': 100,
            'learning_rate': 0.1,
            'min_child_weight': 3,
            'gamma': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
            'random_state': 42
        }

        # 时间序列交叉验证
        tscv = TimeSeriesSplit(n_splits=n_splits)
        cv_scores = {
            'accuracy': [],
            'precision': [],
            'recall': [],
            'f1': [],
            'auc': []
        }

        logger.info(f"时间序列交叉验证: {n_splits} 折")
        logger.info("")

        for fold, (train_idx, test_idx) in enumerate(tscv.split(X), 1):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            model = xgb.XGBClassifier(**params)
            model.fit(X_train, y_train, verbose=False)

            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test)[:, 1] if len(np.unique(y_test)) > 1 else None

            acc = accuracy_score(y_test, y_pred)
            prec = precision_score(y_test, y_pred, zero_division=0)
            rec = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)
            auc = roc_auc_score(y_test, y_proba) if y_proba is not None and len(np.unique(y_test)) > 1 else np.nan

            cv_scores['accuracy'].append(acc)
            cv_scores['precision'].append(prec)
            cv_scores['recall'].append(rec)
            cv_scores['f1'].append(f1)
            cv_scores['auc'].append(auc)

            logger.info(f"Fold {fold}/{n_splits}: Train={len(train_idx)}, Test={len(test_idx)}, Accuracy={acc:.3f}")

        logger.info("")

        # 在全部数据上训练最终模型
        logger.info("在全部数据上训练最终模型...")
        final_model = xgb.XGBClassifier(**params)
        final_model.fit(X, y, verbose=False)

        # 测试集评估（使用最后 20% 数据）
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        final_model.fit(X_train, y_train, verbose=False)
        y_pred = final_model.predict(X_test)
        y_proba = final_model.predict_proba(X_test)[:, 1] if len(np.unique(y_test)) > 1 else None

        test_metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'auc': roc_auc_score(y_test, y_proba) if y_proba is not None and len(np.unique(y_test)) > 1 else np.nan
        }

        logger.info("")
        logger.info("=" * 60)
        logger.info("HELD-OUT TEST SET RESULTS")
        logger.info("=" * 60)
        logger.info(f"Test samples: {len(y_test)}")
        logger.info(f"accuracy: {test_metrics['accuracy']:.4f}")
        logger.info(f"precision: {test_metrics['precision']:.4f}")
        logger.info(f"recall: {test_metrics['recall']:.4f}")
        logger.info(f"f1: {test_metrics['f1']:.4f}")
        logger.info(f"auc: {test_metrics['auc']}")
        logger.info("=" * 60)
        logger.info("")

        # 保存模型
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_path = self.model_dir / f'xgboost_model_{timestamp}.pkl'
        latest_model_path = self.model_dir / 'xgboost_latest.pkl'

        with open(model_path, 'wb') as f:
            pickle.dump(final_model, f)
        with open(latest_model_path, 'wb') as f:
            pickle.dump(final_model, f)

        logger.info(f"Model saved to {model_path}")
        logger.info(f"Model saved to {latest_model_path}")

        # 构建训练报告
        report = {
            'success': True,
            'model_type': 'xgboost',
            'timestamp': datetime.now().isoformat(),
            'data': {
                'total_samples': len(X),
                'train_samples': split_idx,
                'test_samples': len(X) - split_idx,
                'n_features': X.shape[1],
                'positive_samples': int(y.sum()),
                'negative_samples': int(len(y) - y.sum()),
                'class_balance': float(y.sum() / len(y))
            },
            'hyperparameters': params,
            'cv_results': {
                'mean_scores': {k: float(np.mean(v)) for k, v in cv_scores.items()},
                'std_scores': {k: float(np.std(v)) for k, v in cv_scores.items()}
            },
            'test_metrics': test_metrics,
            'feature_importance': final_model.feature_importances_.tolist(),
            'feature_names': feature_names,
            'n_features': len(feature_names),
            'model_path': str(model_path),
            'latest_model_path': str(latest_model_path)
        }

        return report

    def save_training_report(self, report: Dict[str, Any], job_id: str):
        """
        保存训练报告到 PostgreSQL

        Args:
            report: 训练报告字典
            job_id: 任务 ID
        """
        # 将 NaN 转换为 None（JSON null）
        def clean_nan(obj):
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nan(v) for v in obj]
            elif isinstance(obj, float) and np.isnan(obj):
                return None
            else:
                return obj

        report = clean_nan(report)

        # 同时保存到文件系统（向后兼容）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.model_dir / f'training_report_{timestamp}.json'
        latest_report_path = self.model_dir / 'training_report_latest.json'

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        with open(latest_report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"训练报告已保存: {report_path}")
        logger.info(f"最新报告已保存: {latest_report_path}")

        # 保存到 PostgreSQL jobs 表
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE quant.jobs
                SET result = %s, status = 'success', finished_at = NOW()
                WHERE id = %s
            """, (json.dumps(report), job_id))
        self.conn.commit()

        logger.info(f"训练报告已保存到 PostgreSQL (job_id: {job_id})")
