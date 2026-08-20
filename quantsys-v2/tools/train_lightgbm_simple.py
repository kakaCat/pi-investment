#!/usr/bin/env python3
"""简化版模型训练（直接调用服务，避免HTTP超时）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from infrastructure.services.service_factory import get_data_service
from adapters.outbound.repositories.stock_repository import StockORMRepository
from application.services.ml_pipeline.feature_engineering import FeatureEngineer
from application.services.ml_pipeline.predictor import MLPredictor
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

# 训练参数
MODEL_TYPE = "lightgbm"
START_DATE = "2025-09-04"
END_DATE = "2026-08-20"
SYMBOLS_LIMIT = 100  # 先用100只股票快速验证，成功后可扩展到500
TEST_SIZE = 0.2

print(f"=== 模型训练（{MODEL_TYPE}） ===")
print(f"数据范围: {START_DATE} ~ {END_DATE}")
print(f"样本数: {SYMBOLS_LIMIT} 只股票\n")

# 1. 获取股票列表
repo = StockORMRepository()
stocks = repo.get_all(limit=SYMBOLS_LIMIT)
symbols = [s['symbol'] for s in stocks]
print(f"实际训练股票: {len(symbols)} 只\n")

# 2. 获取K线数据
ds = get_data_service()
klines_dict = {}
print("加载K线数据...")
for i, symbol in enumerate(symbols):
    try:
        rows = ds.kline.get_daily_klines(symbol, START_DATE, END_DATE)
        if rows is not None and not rows.is_empty():
            klines_dict[symbol] = rows.to_dicts()
        if (i+1) % 20 == 0:
            print(f"  已加载 {i+1}/{len(symbols)}")
    except Exception as e:
        logger.warning(f"Skip {symbol}: {e}")

print(f"成功加载 {len(klines_dict)} 只股票的K线数据\n")

# 3. 特征工程
print("特征工程...")
engineer = FeatureEngineer()
features_df = engineer.extract_features(klines_dict)
print(f"  特征维度: {features_df.shape}")

metadata, X = engineer.prepare_features(features_df, handle_missing="fill", fit_scaler=True)
print(f"  准备完成: {X.shape[0]} 样本 × {X.shape[1]} 特征\n")

# 4. 训练模型
print(f"训练 {MODEL_TYPE} 模型...")
predictor = MLPredictor(model_type=MODEL_TYPE)

from sklearn.model_selection import train_test_split
y = metadata["target"].values
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, random_state=42)

predictor.train(X_train, y_train)
print(f"  训练完成\n")

# 5. 评估
train_acc = predictor.score(X_train, y_train)
test_acc = predictor.score(X_test, y_test)
print(f"训练集准确率: {train_acc:.4f}")
print(f"测试集准确率: {test_acc:.4f}\n")

# 6. 保存模型
version = datetime.now().strftime("%Y%m%d_%H%M%S")
predictor.save_model(version=version)
print(f"模型已保存: {MODEL_TYPE}_{version}\n")

# 7. 测试预测（验证退化是否修复）
print("测试预测（验证退化修复）...")
test_symbols_raw = ["600519", "000001", "600737"]
test_klines = {}
for sym in test_symbols_raw:
    try:
        rows = ds.kline.get_daily_klines(sym, START_DATE, END_DATE)
        if rows is not None and not rows.is_empty():
            test_klines[sym] = rows.to_dicts()
    except:
        pass

if test_klines:
    test_features = engineer.extract_features(test_klines)
    test_meta, test_X = engineer.prepare_features(test_features, handle_missing="fill", fit_scaler=True)
    
    missing = set(predictor.feature_names) - set(test_X.columns)
    if missing:
        for col in missing:
            test_X[col] = 0.0
    test_X_ordered = test_X[predictor.feature_names]
    
    preds = predictor.predict(test_X_ordered, return_proba=True)
    
    print("\n预测结果:")
    for idx, row in test_meta.iterrows():
        prob = preds.iloc[idx]["prob_up"] if "prob_up" in preds.columns else 0.5
        pred_class = int(preds.iloc[idx]["prediction"])
        print(f"  {row['symbol']}: prob={prob:.4f}, class={pred_class}")
    
    probs = [preds.iloc[i]["prob_up"] for i in range(len(preds))]
    if len(set(probs)) == 1:
        print(f"\n❌ 模型仍退化：所有预测相同 (prob={probs[0]})")
    else:
        print(f"\n✅ 退化已修复：预测有差异")
else:
    print("⚠️ 测试数据不足，跳过预测验证")

print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
