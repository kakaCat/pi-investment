#!/usr/bin/env python3
"""
信号置信度模型训练器 - XGBoost

从历史信号生成训练数据，训练 XGBoost 分类器
"""
import json
import os
import pickle
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np


SIGNALS_DIR = '.pi-invest/quant/signals'
MODEL_DIR = '.pi-invest/quant/models'
MODEL_PATH = os.path.join(MODEL_DIR, 'signal_confidence.pkl')
MIN_SAMPLES = 50


def load_signals():
    """加载所有历史信号"""
    signals = []
    if not os.path.exists(SIGNALS_DIR):
        return signals

    for file in Path(SIGNALS_DIR).glob('*.json'):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    signals.extend(data)
        except Exception as e:
            print(f"加载 {file} 失败: {e}")

    return signals


def get_future_return(symbol: str, signal_date: str, days: int = 5) -> float:
    """
    计算信号后N日收益率

    从 StockDB kline 缓存读取历史数据
    """
    # 简化实现：从 kline 缓存读取
    kline_file = f'.pi-invest/stock-db/klines/{symbol}.json'
    if not os.path.exists(kline_file):
        return 0.0

    try:
        with open(kline_file, 'r') as f:
            klines = json.load(f)

        # 找到信号日期的索引
        signal_idx = None
        for i, bar in enumerate(klines):
            if bar['date'] == signal_date:
                signal_idx = i
                break

        if signal_idx is None or signal_idx + days >= len(klines):
            return 0.0

        entry_price = klines[signal_idx]['close']
        exit_price = klines[signal_idx + days]['close']

        return (exit_price - entry_price) / entry_price

    except Exception:
        return 0.0


def extract_features(signal: dict) -> dict:
    """从信号中提取特征"""
    indicators = signal.get('indicators', {})
    action = signal.get('action', 'buy')

    ma5 = indicators.get('ma5', 0)
    ma20 = indicators.get('ma20', 1)
    ma60 = indicators.get('ma60', 1)
    price = indicators.get('close', 0)
    bb_lower = indicators.get('bollinger_lower', 0)
    bb_upper = indicators.get('bollinger_upper', 1)

    return {
        'rsi': indicators.get('rsi', 50),
        'ma5_ma20_ratio': ma5 / max(ma20, 1),
        'ma20_ma60_ratio': ma20 / max(ma60, 1),
        'macd_histogram': indicators.get('macd_histogram', 0),
        'bb_position': (price - bb_lower) / max(bb_upper - bb_lower, 1) if bb_upper > bb_lower else 0.5,
        'volume_ratio': 1.0,  # 占位
        'conditions_matched_ratio': signal.get('confidence', 0.5),  # 用原始置信度近似
        'action': 0 if action == 'buy' else 1
    }


def train():
    """训练模型"""
    signals = load_signals()
    if len(signals) < MIN_SAMPLES:
        return {
            'success': False,
            'message': f'样本不足，需要至少 {MIN_SAMPLES} 条，当前 {len(signals)} 条'
        }

    # 生成训练数据
    X, y = [], []
    for signal in signals:
        if signal.get('action') != 'buy':  # 只用买入信号训练
            continue

        future_return = get_future_return(signal['symbol'], signal['date'], days=5)
        label = 1 if future_return > 0.02 else 0  # 5日涨幅 > 2%

        features = extract_features(signal)
        X.append([
            features['rsi'],
            features['ma5_ma20_ratio'],
            features['ma20_ma60_ratio'],
            features['macd_histogram'],
            features['bb_position'],
            features['volume_ratio'],
            features['conditions_matched_ratio'],
            features['action']
        ])
        y.append(label)

    if len(X) < MIN_SAMPLES:
        return {
            'success': False,
            'message': f'有效样本不足，需要至少 {MIN_SAMPLES} 条，当前 {len(X)} 条'
        }

    # 训练 XGBoost
    from xgboost import XGBClassifier
    model = XGBClassifier(n_estimators=100, max_depth=4, random_state=42)
    model.fit(X, y)

    # 保存模型
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)

    # 计算准确率
    y_pred = model.predict(X)
    accuracy = (y_pred == y).mean()

    return {
        'success': True,
        'samples': len(X),
        'accuracy': float(accuracy),
        'model_path': MODEL_PATH
    }


if __name__ == '__main__':
    result = train()
    print(json.dumps(result, ensure_ascii=False))

