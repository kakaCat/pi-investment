#!/usr/bin/env python3
"""
ML 模型重训练脚本

功能：
1. 从数据库读取历史K线和因子数据
2. 构建训练集（特征 + 标签）
3. 时间序列交叉验证
4. 模型训练（XGBoost, LightGBM, RandomForest）
5. 模型评估和保存
6. 支持超参数优化

运行方式：
    python scripts/ml_retrain.py --days 180 --model xgboost --tune
"""

import os
import sys
import json
import time
import pickle
import logging
import argparse
import re
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ml_retrain.log')
    ]
)
logger = logging.getLogger(__name__)


def normalize_symbol(symbol: str) -> str:
    """Normalize common exchange prefixes/suffixes."""
    value = str(symbol).strip()
    value = re.sub(r'^(sh|sz|bj)', '', value, flags=re.IGNORECASE)
    value = re.sub(r'\.(SH|SZ|BJ|HK)$', '', value, flags=re.IGNORECASE)
    return value


def parse_symbols(raw_symbols: str = None) -> Optional[List[str]]:
    """Parse comma/whitespace separated symbols."""
    if not raw_symbols:
        return None
    symbols = [
        normalize_symbol(symbol)
        for symbol in re.split(r'[\s,，]+', raw_symbols)
        if symbol.strip()
    ]
    return list(dict.fromkeys(symbols))


class MLRetrainer:
    """ML 模型重训练器"""

    def __init__(
        self,
        db_path: str,
        model_dir: str = None,
        min_history_days: int = 100
    ):
        """
        Args:
            db_path: 数据库路径
            model_dir: 模型保存目录
            min_history_days: 最少历史数据天数
        """
        self.db = Database(db_path)
        self.model_dir = model_dir or os.path.join(
            os.path.dirname(db_path), '..', 'ml', 'models'
        )
        self.min_history_days = min_history_days

        os.makedirs(self.model_dir, exist_ok=True)

    def load_training_data(
        self,
        days: int = 180,
        future_days: int = 5,
        return_threshold: float = 0.05,
        symbols: Optional[List[str]] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        从数据库加载训练数据

        Args:
            days: 加载多少天的历史数据
            future_days: 未来N天用于计算标签
            return_threshold: 涨幅阈值（默认5%）

        Returns:
            (features_df, labels_df)
        """
        logger.info("=" * 60)
        logger.info("加载训练数据")
        logger.info("=" * 60)

        # 1. 获取日期范围
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        logger.info(f"数据起始日期: {cutoff_date}")

        # 2. 加载K线数据
        logger.info("加载K线数据...")
        klines_df, factors_df = self.db.load_model_training_frames(cutoff_date)
        klines_df, factors_df = self.filter_training_frames(klines_df, factors_df, symbols)
        logger.info(f"  加载 {len(klines_df)} 条K线记录")

        # 3. 加载因子数据
        logger.info("加载因子数据...")
        logger.info(f"  加载 {len(factors_df)} 条因子记录")

        # 4. 转换因子数据为宽表格式
        logger.info("转换因子数据格式...")
        factors_pivot = factors_df.pivot_table(
            index=['symbol', 'date'],
            columns='factor_name',
            values='factor_value',
            aggfunc='first'
        ).reset_index()

        # 5. 合并K线和因子数据
        logger.info("合并K线和因子数据...")
        merged_df = pd.merge(
            klines_df,
            factors_pivot,
            on=['symbol', 'date'],
            how='inner'
        )
        logger.info(f"  合并后 {len(merged_df)} 条记录")

        # 6. 计算标签（未来收益率）
        logger.info(f"计算标签（未来{future_days}天收益率）...")
        merged_df = merged_df.sort_values(['symbol', 'date'])

        # 为每只股票计算未来收益率
        merged_df['future_close'] = merged_df.groupby('symbol')['close'].shift(-future_days)
        merged_df['future_return'] = (merged_df['future_close'] - merged_df['close']) / merged_df['close']
        merged_df['label'] = (merged_df['future_return'] > return_threshold).astype(int)

        # 调试：打印列名
        logger.info(f"  合并后的列: {list(merged_df.columns)[:10]}...")  # 只打印前10个

        # 7. 移除没有未来数据的行
        merged_df = merged_df.dropna(subset=['future_return'])
        logger.info(f"  有效样本数: {len(merged_df)}")

        if len(merged_df) == 0:
            raise ValueError("没有有效样本。请检查数据质量或调整参数。")

        # 8. 分离特征和标签
        feature_cols = [col for col in merged_df.columns if col not in [
            'symbol', 'date', 'future_close', 'future_return', 'label'
        ]]

        features_df = merged_df[['symbol', 'date'] + feature_cols].copy()
        labels_df = merged_df[['symbol', 'date', 'label', 'future_return']].copy()

        # 9. 统计信息
        logger.info("")
        logger.info("数据统计:")
        logger.info(f"  样本数: {len(features_df)}")
        logger.info(f"  特征数: {len(feature_cols)}")
        logger.info(f"  股票数: {features_df['symbol'].nunique()}")
        logger.info(f"  日期范围: {features_df['date'].min()} ~ {features_df['date'].max()}")
        logger.info(f"  正样本: {labels_df['label'].sum()} ({labels_df['label'].mean()*100:.1f}%)")
        logger.info(f"  负样本: {len(labels_df) - labels_df['label'].sum()} ({(1-labels_df['label'].mean())*100:.1f}%)")
        logger.info("")

        return features_df, labels_df

    def filter_training_frames(
        self,
        klines_df: pd.DataFrame,
        factors_df: pd.DataFrame,
        symbols: Optional[List[str]] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Limit training frames to selected symbols when provided."""
        if not symbols:
            return klines_df, factors_df

        normalized_symbols = set(parse_symbols(",".join(symbols)) or [])
        if not normalized_symbols:
            return klines_df.iloc[0:0], factors_df.iloc[0:0]

        filtered_klines = klines_df[klines_df['symbol'].astype(str).map(normalize_symbol).isin(normalized_symbols)].copy()
        filtered_factors = factors_df[factors_df['symbol'].astype(str).map(normalize_symbol).isin(normalized_symbols)].copy()
        logger.info(f"  训练股票范围: {', '.join(sorted(normalized_symbols))}")
        return filtered_klines, filtered_factors

    def prepare_features(
        self,
        features_df: pd.DataFrame,
        labels_df: pd.DataFrame,
        use_feature_engineering: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        准备训练特征

        Args:
            features_df: 特征数据框
            labels_df: 标签数据框
            use_feature_engineering: 是否使用 FeatureEngineer 生成高级特征

        Returns:
            (X, y, feature_names)
        """
        logger.info("准备训练特征...")
        logger.info(f"  使用特征工程: {use_feature_engineering}")

        if use_feature_engineering:
            # 使用 FeatureEngineer 生成高级特征
            from quantsys.ml.features import FeatureEngineer

            logger.info("  使用 FeatureEngineer 提取高级特征...")
            engineer = FeatureEngineer()

            # 字段名映射：数据库字段名 -> FeatureEngineer 期望的字段名
            field_mapping = {
                'RSI6': 'rsi',  # 使用 RSI6 作为主要 RSI
                'RSI12': 'rsi_12',
                'RSI24': 'rsi_24',
                'MACD_macd_histogram': 'macd_histogram',
                'MACD_macd_dif': 'macd_dif',
                'MACD_macd_dea': 'macd_dea',
                'MA5': 'ma5',
                'MA10': 'ma10',
                'MA20': 'ma20',
                'MA60': 'ma60',
                'BOLL_bb_upper': 'bollinger_upper',
                'BOLL_bb_middle': 'bollinger_middle',
                'BOLL_bb_lower': 'bollinger_lower',
                'BOLL_bb_width': 'bollinger_width',
                'BOLL_bb_percent': 'bollinger_percent',
                'KDJ_k': 'kdj_k',
                'KDJ_d': 'kdj_d',
                'KDJ_j': 'kdj_j',
                'ATR14': 'atr',
                'OBV': 'obv',
                'volume': 'volume',
                'close': 'close',
                'open': 'open',
                'high': 'high',
                'low': 'low'
            }

            all_features = []
            valid_indices = []

            for idx, row in features_df.iterrows():
                try:
                    # 转换字段名
                    row_dict = row.to_dict()
                    mapped_indicators = {}
                    for db_name, fe_name in field_mapping.items():
                        if db_name in row_dict and pd.notna(row_dict[db_name]):
                            mapped_indicators[fe_name] = row_dict[db_name]

                    # 保留未映射的字段（小写）
                    for key, value in row_dict.items():
                        if key not in field_mapping and pd.notna(value):
                            mapped_indicators[key.lower()] = value

                    # 构造信号字典
                    signal = {
                        'indicators': mapped_indicators,
                        'date': str(row['date']),
                        'price': float(row.get('close', 0)),
                        'action': 'buy'  # 默认值
                    }

                    # 提取特征
                    features = engineer.extract_features(signal)
                    all_features.append(features)
                    valid_indices.append(idx)

                except Exception as e:
                    logger.warning(f"  跳过索引 {idx}: {e}")
                    continue

            if not all_features:
                raise ValueError("没有成功提取任何特征")

            # 转换为矩阵
            feature_names = engineer.get_feature_names()
            X = np.array([
                [features.get(name, 0) for name in feature_names]
                for features in all_features
            ])

            # 对应的标签
            y = labels_df.loc[valid_indices, 'label'].values

            logger.info(f"  提取了 {len(feature_names)} 个高级特征")

        else:
            # 使用原始特征（保持向后兼容）
            logger.info("  使用原始数据库特征...")
            feature_cols = [col for col in features_df.columns if col not in ['symbol', 'date']]

            # 填充缺失值
            X = features_df[feature_cols].fillna(0).values
            y = labels_df['label'].values
            feature_names = feature_cols

        # 检查无穷值
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        logger.info(f"  特征矩阵: {X.shape}")
        logger.info(f"  标签向量: {y.shape}")
        logger.info(f"  特征名称: {len(feature_names)}")

        return X, y, feature_names

    def train_model(
        self,
        X: np.ndarray,
        y: np.ndarray,
        model_type: str = 'xgboost',
        tune_hyperparams: bool = False,
        n_trials: int = 50,
        cv_splits: int = 5
    ) -> Dict[str, Any]:
        """
        训练模型

        Args:
            X: 特征矩阵
            y: 标签向量
            model_type: 模型类型 ('xgboost', 'lightgbm', 'randomforest')
            tune_hyperparams: 是否进行超参数优化
            n_trials: 优化试验次数
            cv_splits: 交叉验证折数

        Returns:
            训练报告
        """
        logger.info("=" * 60)
        logger.info(f"训练 {model_type.upper()} 模型")
        logger.info("=" * 60)

        from quantsys.ml.training.trainer import ModelTrainer

        # 检查样本数量
        if len(X) < 100:
            raise ValueError(f"样本数量不足: {len(X)} < 100")

        # 检查类别平衡
        positive_ratio = y.sum() / len(y)
        if positive_ratio < 0.05 or positive_ratio > 0.95:
            logger.warning(
                f"⚠️  类别严重不平衡: {positive_ratio*100:.1f}% 正样本"
            )

        # 创建训练器
        trainer = ModelTrainer(
            model_type=model_type,
            tune_hyperparams=tune_hyperparams,
            n_trials=n_trials,
            cv_splits=cv_splits
        )

        # 训练模型
        training_report = trainer.train(X, y)

        # 保存模型
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_filename = f"{model_type}_model_{timestamp}.pkl"
        model_path = os.path.join(self.model_dir, model_filename)
        trainer.save_model(model_path)

        # 同时保存为最新模型
        latest_model_path = os.path.join(self.model_dir, f"{model_type}_latest.pkl")
        trainer.save_model(latest_model_path)

        training_report['model_path'] = model_path
        training_report['latest_model_path'] = latest_model_path

        return training_report

    def save_training_report(
        self,
        report: Dict[str, Any],
        feature_names: List[str],
        start_time: datetime = None,
        end_time: datetime = None
    ):
        """保存训练报告"""
        report['feature_names'] = feature_names
        report['n_features'] = len(feature_names)

        # 添加时长信息
        if start_time and end_time:
            report['start_time'] = start_time.isoformat()
            report['end_time'] = end_time.isoformat()
            report['duration_seconds'] = (end_time - start_time).total_seconds()

        # 保存为JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"training_report_{timestamp}.json"
        report_path = os.path.join(self.model_dir, report_filename)

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"训练报告已保存: {report_path}")

        # 同时保存为最新报告
        latest_report_path = os.path.join(self.model_dir, 'training_report_latest.json')
        with open(latest_report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"最新报告已保存: {latest_report_path}")

    def print_summary(self, report: Dict[str, Any]):
        """打印训练摘要"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("训练摘要")
        logger.info("=" * 60)
        logger.info(f"模型类型: {report['model_type']}")
        logger.info(f"训练时间: {report['timestamp']}")
        logger.info("")
        logger.info("数据统计:")
        logger.info(f"  总样本数: {report['data']['total_samples']}")
        logger.info(f"  训练样本: {report['data']['train_samples']}")
        logger.info(f"  测试样本: {report['data']['test_samples']}")
        logger.info(f"  特征数量: {report['data']['n_features']}")
        logger.info(f"  正样本数: {report['data']['positive_samples']}")
        logger.info(f"  负样本数: {report['data']['negative_samples']}")
        logger.info(f"  类别平衡: {report['data']['class_balance']*100:.1f}%")
        logger.info("")
        logger.info("交叉验证结果:")
        for metric, score in report['cv_results']['mean_scores'].items():
            std = report['cv_results']['std_scores'][metric]
            logger.info(f"  {metric:12s}: {score:.4f} ± {std:.4f}")
        logger.info("")
        logger.info("测试集结果:")
        for metric, score in report['test_metrics'].items():
            if metric != 'confusion_matrix':
                logger.info(f"  {metric:12s}: {score:.4f}")
        logger.info("")
        logger.info("混淆矩阵:")
        cm = report['test_metrics']['confusion_matrix']
        logger.info(f"  TN={cm[0][0]:4d}  FP={cm[0][1]:4d}")
        logger.info(f"  FN={cm[1][0]:4d}  TP={cm[1][1]:4d}")
        logger.info("")
        logger.info(f"模型已保存: {report['model_path']}")
        logger.info("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='ML 模型重训练脚本')

    parser.add_argument(
        '--symbols',
        type=str,
        default=None,
        help='股票代码列表，逗号分隔；不传则使用全部股票'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=180,
        help='使用多少天的历史数据, 默认180天'
    )

    parser.add_argument(
        '--future-days',
        type=int,
        default=5,
        help='未来N天用于计算标签, 默认5天'
    )

    parser.add_argument(
        '--threshold',
        type=float,
        default=0.05,
        help='涨幅阈值, 超过此值为正样本, 默认0.05即5%%'
    )

    parser.add_argument(
        '--model',
        type=str,
        default='xgboost',
        choices=['xgboost', 'lightgbm', 'randomforest'],
        help='模型类型, 默认xgboost'
    )

    parser.add_argument(
        '--tune',
        action='store_true',
        help='是否进行超参数优化'
    )

    parser.add_argument(
        '--trials',
        type=int,
        default=50,
        help='超参数优化试验次数, 默认50'
    )

    parser.add_argument(
        '--cv-splits',
        type=int,
        default=5,
        help='交叉验证折数, 默认5'
    )

    parser.add_argument(
        '--db-path',
        type=str,
        default=None,
        help='数据库路径, 默认自动检测'
    )

    parser.add_argument(
        '--use-feature-engineering',
        action='store_true',
        help='使用 FeatureEngineer 生成高级特征 (56个), 默认使用原始特征 (38个)'
    )

    parser.add_argument(
        '--job-id',
        type=str,
        default=None,
        help='异步任务ID（由 Flask API 传入），用于状态追踪'
    )

    args = parser.parse_args()

    # 任务状态追踪
    def _job_status(status: str, **kwargs):
        if not args.job_id:
            return
        jobs_dir = Path.home() / '.pi-invest' / 'jobs'
        jobs_dir.mkdir(parents=True, exist_ok=True)
        job_file = jobs_dir / f"{args.job_id}.json"
        job = {}
        if job_file.exists():
            import json
            with open(job_file) as f:
                job = json.load(f)
        job['status'] = status
        job.update(kwargs)
        if status in ('completed', 'failed'):
            job['completed_at'] = time.time()
        with open(job_file, 'w') as f:
            import json
            json.dump(job, f, indent=2)

    if args.job_id:
        _job_status('running', started_at=datetime.now().timestamp())

    # 确定数据库路径
    if args.db_path:
        db_path = args.db_path
    else:
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '.pi-invest', 'stock-db', 'stocks.db'
        )

    if not os.path.exists(db_path):
        logger.error(f"❌ 数据库不存在: {db_path}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("ML 模型重训练任务")
    logger.info("=" * 60)
    start_time = datetime.now()
    logger.info(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"数据库: {db_path}")
    logger.info(f"历史天数: {args.days}")
    if args.symbols:
        logger.info(f"股票范围: {args.symbols}")
    logger.info(f"未来天数: {args.future_days}")
    logger.info(f"涨幅阈值: {args.threshold*100:.1f}%")
    logger.info(f"模型类型: {args.model}")
    logger.info(f"特征工程: {'高级特征 (FeatureEngineer)' if args.use_feature_engineering else '原始特征 (数据库)'}")
    logger.info(f"超参数优化: {'是' if args.tune else '否'}")
    if args.tune:
        logger.info(f"优化试验: {args.trials}")
    logger.info(f"交叉验证: {args.cv_splits} 折")
    logger.info("")

    try:
        # 创建重训练器
        retrainer = MLRetrainer(db_path)

        # 1. 加载数据
        features_df, labels_df = retrainer.load_training_data(
            days=args.days,
            future_days=args.future_days,
            return_threshold=args.threshold,
            symbols=parse_symbols(args.symbols)
        )

        # 2. 准备特征
        X, y, feature_names = retrainer.prepare_features(
            features_df,
            labels_df,
            use_feature_engineering=args.use_feature_engineering
        )

        # 3. 训练模型
        training_report = retrainer.train_model(
            X, y,
            model_type=args.model,
            tune_hyperparams=args.tune,
            n_trials=args.trials,
            cv_splits=args.cv_splits
        )

        # 4. 保存报告
        end_time = datetime.now()
        retrainer.save_training_report(training_report, feature_names, start_time, end_time)

        # 5. 打印摘要
        retrainer.print_summary(training_report)

        # 6. 检查模型性能
        test_accuracy = training_report['test_metrics']['accuracy']
        if test_accuracy < 0.55:
            logger.warning("")
            logger.warning("⚠️  警告: 模型准确率低于55%")
            logger.warning("建议:")
            logger.warning("  1. 增加训练数据（--days 参数）")
            logger.warning("  2. 调整涨幅阈值（--threshold 参数）")
            logger.warning("  3. 尝试超参数优化（--tune 参数）")
            logger.warning("  4. 尝试其他模型类型（--model 参数）")
            logger.warning("")

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ 训练任务完成")
        logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        if args.job_id:
            _job_status('completed', result={
                'accuracy': training_report['test_metrics']['accuracy'],
                'auc': training_report['test_metrics']['auc'],
                'model_type': args.model,
                'n_features': len(feature_names),
            })

    except Exception as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error("❌ 训练任务失败")
        logger.error(f"错误: {e}")
        logger.error("=" * 60)
        import traceback
        logger.error(traceback.format_exc())

        if args.job_id:
            _job_status('failed', error={'message': str(e)})

        sys.exit(1)


if __name__ == '__main__':
    main()
