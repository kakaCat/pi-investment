#!/usr/bin/env python3
"""
ML 重训练脚本快速测试

测试基本功能：
1. 数据加载
2. 特征准备
3. 模型训练（小数据集）
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.ml_retrain import MLRetrainer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_ml_retrain():
    """测试 ML 重训练流程"""

    logger.info("=" * 60)
    logger.info("ML 重训练脚本测试")
    logger.info("=" * 60)

    # 数据库路径
    db_path = os.path.join(
        os.path.expanduser('~'),
        '.pi-invest', 'stock-db', 'stocks.db'
    )

    if not os.path.exists(db_path):
        logger.error(f"❌ 数据库不存在: {db_path}")
        return False

    try:
        # 检查数据库状态
        import sqlite3
        conn = sqlite3.connect(db_path)

        cursor = conn.execute("SELECT COUNT(DISTINCT date) FROM factor_values")
        factor_dates = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM factor_values")
        factor_records = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM daily_klines")
        kline_records = cursor.fetchone()[0]

        conn.close()

        logger.info(f"\n数据库状态:")
        logger.info(f"  K线记录数: {kline_records}")
        logger.info(f"  因子记录数: {factor_records}")
        logger.info(f"  因子日期数: {factor_dates}")

        if factor_dates < 10:
            logger.warning("\n⚠️  因子数据不足（需要至少10天的历史因子数据）")
            logger.info("\n请先运行以下命令生成历史因子数据:")
            logger.info("  python scripts/calculate_factors.py")
            logger.info("\n注意: calculate_factors.py 默认只计算最新一天的因子")
            logger.info("      如需历史因子，需要修改脚本循环计算多天")
            logger.info("\n跳过完整训练测试，仅测试基本功能...")

            # 仅测试重训练器创建
            retrainer = MLRetrainer(db_path)
            logger.info("✅ 重训练器创建成功")
            logger.info("✅ 基本功能测试通过")
            return True

        # 创建重训练器
        retrainer = MLRetrainer(db_path)
        logger.info("✅ 重训练器创建成功")

        # 测试数据加载（使用较少天数）
        logger.info("\n测试数据加载...")
        features_df, labels_df = retrainer.load_training_data(
            days=60,  # 使用较少天数进行测试
            future_days=5,
            return_threshold=0.05
        )

        if len(features_df) < 10:
            logger.warning(f"⚠️  样本数量太少: {len(features_df)}")
            logger.info("提示: 需要更多历史因子数据")
            return False

        logger.info(f"✅ 数据加载成功: {len(features_df)} 个样本")

        # 测试特征准备
        logger.info("\n测试特征准备...")
        X, y, feature_names = retrainer.prepare_features(features_df, labels_df)
        logger.info(f"✅ 特征准备成功: {X.shape}")
        logger.info(f"   特征数: {len(feature_names)}")
        logger.info(f"   样本数: {len(X)}")
        logger.info(f"   正样本: {y.sum()} ({y.sum()/len(y)*100:.1f}%)")

        # 如果样本数足够，测试模型训练
        if len(X) >= 100:
            logger.info("\n测试模型训练（不进行超参数优化）...")
            training_report = retrainer.train_model(
                X, y,
                model_type='xgboost',
                tune_hyperparams=False,
                cv_splits=3  # 使用较少折数加快测试
            )

            logger.info("✅ 模型训练成功")
            logger.info(f"   CV 准确率: {training_report['cv_results']['mean_scores']['accuracy']:.4f}")
            logger.info(f"   测试准确率: {training_report['test_metrics']['accuracy']:.4f}")
            logger.info(f"   模型路径: {training_report['model_path']}")

            # 保存报告
            retrainer.save_training_report(training_report, feature_names)
            logger.info("✅ 训练报告已保存")

        else:
            logger.warning(f"⚠️  样本数不足 ({len(X)} < 100)，跳过模型训练测试")
            logger.info("提示: 需要更多历史数据")

        logger.info("\n" + "=" * 60)
        logger.info("✅ 所有测试通过")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == '__main__':
    success = test_ml_retrain()
    sys.exit(0 if success else 1)
