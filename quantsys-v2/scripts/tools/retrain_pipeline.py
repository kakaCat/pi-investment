#!/usr/bin/env python3
"""
v2 原生 ML 重训练流水线
- 批量计算因子（存入 v2 PG）
- 训练 XGBoost 模型
- 保存模型文件到 quant/quantsys/ml/models/
"""
import sys, os, json, time, logging
from datetime import datetime, timedelta
from pathlib import Path

_V2_ROOT = Path(__file__).resolve().parents[1]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def main():
    from application.services.data_service import DataService
    from domain.quantlib.stages.factor_stage import FactorStage
    import numpy as np
    import pandas as pd

    ds = DataService()
    factor_stage = FactorStage(name="factors")

    # 1. 获取有足够 K 线的股票
    all_stocks = ds.stock.get_all(limit=200)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    valid_symbols = []
    for s in all_stocks:
        klines = ds.kline.get_daily_klines(s['symbol'], start_date, end_date)
        if len(klines) >= 120:
            valid_symbols.append(s['symbol'])

    logger.info(f"Valid stocks for training: {len(valid_symbols)}")

    # 2. 批量计算因子
    factor_records = []
    for sym in valid_symbols:
        try:
            klines = ds.kline.get_daily_klines(sym, start_date, end_date)
            if not klines or len(klines) < 60:
                continue
            # 对最近 120 个交易日计算因子
            for i in range(60, len(klines)):
                window = klines[i-60:i+1]
                result = factor_stage.process({'symbol': sym, 'klines': window})
                factors = result.get('factors', {})
                if factors:
                    last_row = window[-1]
                    date = str(last_row.get('trade_date') or last_row.get('date'))
                    for fname, fval in factors.items():
                        try:
                            factor_records.append((sym, date, fname, float(fval)))
                        except (TypeError, ValueError):
                            pass
        except Exception as e:
            logger.warning(f"Factor compute failed for {sym}: {e}")

    logger.info(f"Total factor records: {len(factor_records)}")

    # 3. 保存因子到 v2 PG
    if factor_records:
        ds.factor.save_factors_batch([
            {'symbol': r[0], 'date': r[1], 'factor_name': r[2], 'factor_value': r[3]}
            for r in factor_records
        ])
        logger.info("Factors saved to v2 PG")

    # 4. 构建训练数据
    logger.info("Building training dataset...")
    # 从已保存的因子中构建特征
    # 用最近日期的因子值作为特征，用 5 日后的涨跌作为标签
    
    # 按 symbol+date 聚合因子为宽表
    factor_dict = {}
    for r in factor_records:
        key = (r[0], r[1])
        if key not in factor_dict:
            factor_dict[key] = {}
        factor_dict[key][r[2]] = r[3]

    # 构建 DataFrame
    rows = []
    for (symbol, date), factors in factor_dict.items():
        row = {'symbol': symbol, 'date': date}
        row.update(factors)
        rows.append(row)
    
    if not rows:
        logger.error("No training data after factor computation!")
        return False

    df = pd.DataFrame(rows)
    logger.info(f"Training DataFrame: {df.shape}")

    # 5. 计算标签（未来 5 日收益 > 3% 为正样本）
    df = df.sort_values(['symbol', 'date'])
    df['close'] = None
    for sym in df['symbol'].unique():
        klines = ds.kline.get_daily_klines(sym, start_date, end_date)
        if not klines:
            continue
        price_map = {}
        for k in klines:
            d = str(k.get('trade_date') or k.get('date'))
            price_map[d] = float(k.get('close', 0))
        
        sym_mask = df['symbol'] == sym
        dates = df.loc[sym_mask, 'date'].values
        for i, d in enumerate(dates):
            # 找 5 日后的价格
            future_dates = sorted([pd for pd_ in price_map if pd_ > d])
            if len(future_dates) >= 5:
                future_close = price_map[future_dates[4]]
                current_close = price_map.get(d, 0)
                if current_close > 0:
                    ret = (future_close - current_close) / current_close
                    df.loc[(df['symbol'] == sym) & (df['date'] == d), 'future_return'] = ret
                    df.loc[(df['symbol'] == sym) & (df['date'] == d), 'close'] = current_close

    df['label'] = (df['future_return'] > 0.03).astype(int)
    df = df.dropna(subset=['label', 'future_return'])

    pos = df['label'].sum()
    neg = len(df) - pos
    logger.info(f"Samples: {len(df)}, Positive: {pos} ({pos/len(df)*100:.1f}%), Negative: {neg}")

    if len(df) < 100:
        logger.error(f"Not enough samples: {len(df)}")
        return False

    # 6. 准备特征
    exclude_cols = ['symbol', 'date', 'label', 'future_return', 'close', 'open', 'high', 'low', 'volume', 'amount']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    
    # 过滤非数值列
    numeric_cols = []
    for c in feature_cols:
        try:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            numeric_cols.append(c)
        except:
            pass
    
    X = df[numeric_cols].fillna(0).values
    y = df['label'].values
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    
    logger.info(f"Feature matrix: {X.shape}, features: {len(numeric_cols)}")

    # 7. 划分训练集/测试集（按时间）
    dates_sorted = sorted(df['date'].unique())
    split_date = dates_sorted[int(len(dates_sorted) * 0.8)]
    train_mask = df['date'] <= split_date
    test_mask = df['date'] > split_date

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]
    logger.info(f"Train: {X_train.shape}, Test: {X_test.shape}")

    # 8. 训练模型
    from xgboost import XGBClassifier
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
    from sklearn.metrics import roc_auc_score

    model = XGBClassifier(
        n_estimators=100, max_depth=5, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        random_state=42, eval_metric='logloss',
        scale_pos_weight=neg/pos if pos > 0 else 1
    )
    model.fit(X_train, y_train)

    # 9. 评估
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else None

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred).tolist()
    auc = roc_auc_score(y_test, y_proba) if y_proba is not None and len(set(y_test)) > 1 else 0.5

    logger.info(f"Test Accuracy: {acc:.4f}")
    logger.info(f"Test Precision: {prec:.4f}")
    logger.info(f"Test Recall: {rec:.4f}")
    logger.info(f"Test F1: {f1:.4f}")
    logger.info(f"Test AUC: {auc:.4f}")
    logger.info(f"Confusion Matrix: {cm}")

    # 10. 保存模型
    import joblib
    model_dir = _V2_ROOT.parent / 'quant' / 'quantsys' / 'ml' / 'models'
    model_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    model_path = model_dir / f'xgboost_model_{timestamp}.pkl'
    latest_path = model_dir / 'xgboost_latest.pkl'
    joblib.dump(model, model_path)
    joblib.dump(model, latest_path)

    # 11. 保存训练报告
    feature_importance = model.feature_importances_.tolist()
    report = {
        'success': True,
        'model_type': 'xgboost',
        'timestamp': datetime.now().isoformat(),
        'data': {
            'total_samples': len(df),
            'train_samples': int(train_mask.sum()),
            'test_samples': int(test_mask.sum()),
            'n_features': len(numeric_cols),
            'positive_samples': int(pos),
            'negative_samples': int(neg),
            'class_balance': float(pos / len(df)),
        },
        'test_metrics': {
            'accuracy': acc, 'precision': prec, 'recall': rec, 'f1': f1,
            'confusion_matrix': cm, 'auc': auc,
        },
        'feature_importance': feature_importance,
        'feature_names': numeric_cols,
        'model_path': str(model_path),
        'latest_model_path': str(latest_path),
    }
    
    report_path = model_dir / f'training_report_{timestamp}.json'
    latest_report_path = model_dir / 'training_report_latest.json'
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(latest_report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"Model saved to {model_path}")
    logger.info(f"Report saved to {report_path}")
    logger.info("✅ Retraining complete!")
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
