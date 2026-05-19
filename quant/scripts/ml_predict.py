#!/usr/bin/env python3
"""
ML预测脚本

功能：
1. 加载训练好的模型
2. 从数据库提取最新因子值
3. 使用模型预测涨跌概率
4. 保存预测结果到JSON文件
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
import numpy as np
import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class MLPredictor:
    """ML预测器"""

    def __init__(self, db: Database, model_path: str):
        self.db = db
        self.conn = db._get_connection()
        self.model_path = model_path
        self.model = None

    def load_model(self) -> bool:
        """加载训练好的模型"""
        if not os.path.exists(self.model_path):
            logger.error(f"❌ 模型文件不存在: {self.model_path}")
            logger.info("\n💡 提示:")
            logger.info("  1. 请先运行训练脚本生成模型")
            logger.info("  2. 或检查模型路径是否正确")
            logger.info(f"  3. 期望路径: {self.model_path}")
            return False

        try:
            import pickle
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)

            logger.info(f"✅ 模型加载成功: {self.model_path}")

            # 显示模型信息
            model_type = type(self.model).__name__
            logger.info(f"   模型类型: {model_type}")

            if hasattr(self.model, 'n_features_in_'):
                logger.info(f"   特征数量: {self.model.n_features_in_}")

            return True

        except Exception as e:
            logger.error(f"❌ 模型加载失败: {e}")
            return False

    def get_latest_date(self) -> Optional[str]:
        """获取最新数据日期"""
        try:
            cursor = self.conn.execute("SELECT MAX(date) FROM factor_values")
            date = cursor.fetchone()[0]
            return date
        except Exception as e:
            logger.error(f"获取最新日期失败: {e}")
            return None

    def get_stock_factors(self, symbol: str, date: str) -> Optional[Dict]:
        """获取股票的因子值"""
        try:
            cursor = self.conn.execute("""
                SELECT factor_name, factor_value
                FROM factor_values
                WHERE symbol = ? AND date = ?
            """, (symbol, date))

            factors = {}
            for row in cursor.fetchall():
                factors[row[0]] = row[1]

            if not factors:
                return None

            return factors

        except Exception as e:
            logger.warning(f"获取 {symbol} 因子失败: {e}")
            return None

    def get_stock_price(self, symbol: str, date: str) -> Optional[Dict]:
        """获取股票价格信息"""
        try:
            cursor = self.conn.execute("""
                SELECT open, high, low, close, volume
                FROM daily_klines
                WHERE symbol = ? AND date = ?
            """, (symbol, date))

            row = cursor.fetchone()
            if row:
                return {
                    'open': row[0],
                    'high': row[1],
                    'low': row[2],
                    'close': row[3],
                    'volume': row[4]
                }
            return None

        except Exception as e:
            logger.warning(f"获取 {symbol} 价格失败: {e}")
            return None

    def extract_features(self, factors: Dict, price: Dict) -> Optional[np.ndarray]:
        """
        从因子和价格数据中提取ML特征

        特征包括：
        - 技术因子: RSI, MACD, KDJ, CCI, WR
        - 价格特征: MA比率, 布林带位置
        - 成交量特征: 成交量比率, OBV, MFI
        """
        try:
            # 技术因子
            rsi = factors.get('RSI12', 50)
            macd_dif = factors.get('MACD_DIF', 0)
            macd_dea = factors.get('MACD_DEA', 0)
            macd_hist = factors.get('MACD_MACD', 0)
            kdj_k = factors.get('KDJ_K', 50)
            kdj_d = factors.get('KDJ_D', 50)
            kdj_j = factors.get('KDJ_J', 50)
            cci = factors.get('CCI14', 0)
            wr = factors.get('WR10', -50)

            # 价格特征
            ma5 = factors.get('MA5', price['close'])
            ma10 = factors.get('MA10', price['close'])
            ma20 = factors.get('MA20', price['close'])
            ma60 = factors.get('MA60', price['close'])

            close = price['close']

            # 计算MA比率
            ma5_ma20_ratio = ma5 / ma20 if ma20 > 0 else 1.0
            ma10_ma20_ratio = ma10 / ma20 if ma20 > 0 else 1.0
            ma20_ma60_ratio = ma20 / ma60 if ma60 > 0 else 1.0
            price_ma5_ratio = close / ma5 if ma5 > 0 else 1.0
            price_ma20_ratio = close / ma20 if ma20 > 0 else 1.0

            # 布林带位置
            bb_upper = factors.get('BOLL_UPPER', close * 1.02)
            bb_middle = factors.get('BOLL_MIDDLE', close)
            bb_lower = factors.get('BOLL_LOWER', close * 0.98)

            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0.04
            bb_position = (close - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else 0.5

            # 成交量特征
            volume_ratio = factors.get('VR', 1.0)
            obv = factors.get('OBV', 0)
            mfi = factors.get('MFI14', 50)

            # 波动率
            atr = factors.get('ATR14', 0)
            atr_ratio = atr / close if close > 0 else 0

            # 动量特征
            roc = factors.get('ROC12', 0)
            mom = factors.get('MOM12', 0)

            # 组合特征数组（25个特征）
            features = np.array([
                # 技术指标 (9)
                rsi,
                macd_dif,
                macd_dea,
                macd_hist,
                kdj_k,
                kdj_d,
                kdj_j,
                cci,
                wr,

                # 价格特征 (7)
                ma5_ma20_ratio,
                ma10_ma20_ratio,
                ma20_ma60_ratio,
                price_ma5_ratio,
                price_ma20_ratio,
                bb_position,
                bb_width,

                # 成交量特征 (3)
                volume_ratio,
                obv / 1e8,  # 归一化OBV
                mfi,

                # 波动率 (1)
                atr_ratio,

                # 动量 (2)
                roc,
                mom,

                # 价格变化 (3)
                (price['high'] - price['low']) / price['close'] if price['close'] > 0 else 0,
                (price['close'] - price['open']) / price['open'] if price['open'] > 0 else 0,
                price['volume'] / 1e8,  # 归一化成交量
            ])

            return features

        except Exception as e:
            logger.warning(f"特征提取失败: {e}")
            return None

    def predict_stock(self, symbol: str, date: str) -> Optional[Dict]:
        """预测单只股票的涨跌概率"""
        if self.model is None:
            logger.error("模型未加载")
            return None

        # 获取因子和价格
        factors = self.get_stock_factors(symbol, date)
        price = self.get_stock_price(symbol, date)

        if not factors or not price:
            return None

        # 提取特征
        features = self.extract_features(factors, price)
        if features is None:
            return None

        try:
            # 预测
            X = features.reshape(1, -1)

            # 获取预测概率
            if hasattr(self.model, 'predict_proba'):
                proba = self.model.predict_proba(X)[0]
                positive_prob = float(proba[1])  # 上涨概率
                negative_prob = float(proba[0])  # 下跌概率
            else:
                # 如果模型不支持概率预测，使用二分类结果
                prediction = self.model.predict(X)[0]
                positive_prob = 1.0 if prediction == 1 else 0.0
                negative_prob = 1.0 - positive_prob

            # 判断方向
            direction = 'UP' if positive_prob > 0.5 else 'DOWN'
            confidence = max(positive_prob, negative_prob)

            return {
                'symbol': symbol,
                'date': date,
                'direction': direction,
                'probability': positive_prob,
                'confidence': confidence,
                'price': price['close'],
                'probabilities': {
                    'up': positive_prob,
                    'down': negative_prob
                }
            }

        except Exception as e:
            logger.warning(f"预测 {symbol} 失败: {e}")
            return None

    def predict_all(self, symbols: List[str], date: str) -> List[Dict]:
        """预测所有股票"""
        predictions = []

        for i, symbol in enumerate(symbols, 1):
            try:
                prediction = self.predict_stock(symbol, date)
                if prediction:
                    predictions.append(prediction)

                    if i % 50 == 0:
                        logger.info(f"  进度: {i}/{len(symbols)}")

            except Exception as e:
                logger.warning(f"  ⚠️  {symbol} 预测失败: {e}")
                continue

        return predictions


def save_predictions(predictions: List[Dict], output_path: str):
    """保存预测结果到JSON文件"""
    # 按上涨概率排序
    predictions.sort(key=lambda x: x['probability'], reverse=True)

    # 统计信息
    up_predictions = [p for p in predictions if p['direction'] == 'UP']
    down_predictions = [p for p in predictions if p['direction'] == 'DOWN']

    # 高置信度预测（>0.7）
    high_confidence = [p for p in predictions if p['confidence'] > 0.7]

    output = {
        'generated_at': datetime.now().isoformat(),
        'date': predictions[0]['date'] if predictions else None,
        'summary': {
            'total': len(predictions),
            'up': len(up_predictions),
            'down': len(down_predictions),
            'high_confidence': len(high_confidence)
        },
        'predictions': predictions
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 预测结果已保存到: {output_path}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("ML预测任务开始")
    logger.info(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 数据库路径
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.pi-invest', 'stock-db', 'stocks.db'
    )

    # 模型路径
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'quantsys', 'ml', 'models', 'xgboost_model.pkl'
    )

    # 检查数据库
    if not os.path.exists(db_path):
        logger.error(f"❌ 数据库不存在: {db_path}")
        return

    db = Database(db_path)
    predictor = MLPredictor(db, model_path)

    # 加载模型
    if not predictor.load_model():
        logger.error("\n❌ 无法加载模型，任务终止")
        logger.info("\n💡 请先训练模型:")
        logger.info("   cd quant")
        logger.info("   python -m quantsys.ml.training.trainer")
        return

    # 获取最新日期
    latest_date = predictor.get_latest_date()
    if not latest_date:
        logger.error("❌ 无法获取最新数据日期")
        return

    logger.info(f"最新数据日期: {latest_date}")

    # 获取所有股票
    symbols = db.get_all_symbols(market='A')
    logger.info(f"共 {len(symbols)} 只股票需要预测")
    logger.info("")

    # 执行预测
    logger.info("开始预测...")
    predictions = predictor.predict_all(symbols, latest_date)

    logger.info("")
    logger.info("=" * 60)
    logger.info("预测完成")
    logger.info(f"成功预测: {len(predictions)} 只股票")
    logger.info("=" * 60)

    if not predictions:
        logger.warning("⚠️  没有生成任何预测结果")
        return

    # 保存结果
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.pi-invest'
    )
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, 'ml_predictions.json')
    save_predictions(predictions, output_path)

    # 显示统计信息
    up_predictions = [p for p in predictions if p['direction'] == 'UP']
    down_predictions = [p for p in predictions if p['direction'] == 'DOWN']
    high_confidence = [p for p in predictions if p['confidence'] > 0.7]

    logger.info(f"\n📊 预测统计:")
    logger.info(f"  总数: {len(predictions)}")
    logger.info(f"  看涨: {len(up_predictions)} ({len(up_predictions)/len(predictions)*100:.1f}%)")
    logger.info(f"  看跌: {len(down_predictions)} ({len(down_predictions)/len(predictions)*100:.1f}%)")
    logger.info(f"  高置信度 (>0.7): {len(high_confidence)}")

    # 显示Top 10看涨股票
    if up_predictions:
        logger.info("\n📈 Top 10 看涨股票:")
        for i, pred in enumerate(up_predictions[:10], 1):
            logger.info(f"  {i}. {pred['symbol']} | "
                       f"上涨概率: {pred['probability']:.2%} | "
                       f"置信度: {pred['confidence']:.2%} | "
                       f"价格: {pred['price']:.2f}")

    # 显示Top 10看跌股票
    if down_predictions:
        logger.info("\n📉 Top 10 看跌股票:")
        down_sorted = sorted(down_predictions, key=lambda x: x['probabilities']['down'], reverse=True)
        for i, pred in enumerate(down_sorted[:10], 1):
            logger.info(f"  {i}. {pred['symbol']} | "
                       f"下跌概率: {pred['probabilities']['down']:.2%} | "
                       f"置信度: {pred['confidence']:.2%} | "
                       f"价格: {pred['price']:.2f}")


if __name__ == '__main__':
    main()
