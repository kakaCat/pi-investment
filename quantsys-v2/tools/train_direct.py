#!/usr/bin/env python3
"""直接训练（不通过HTTP，避免超时）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=== 模型训练（直接调用，20只股票快速验证） ===\n")

# 快速训练参数
SYMBOLS = ["600519","000001","600737","000002","600036","601318","600276","600887","601888","601398",
           "600028","601939","601012","600016","600030","600048","601166","600050","600104","600115"]
START_DATE = "2025-09-04"
END_DATE = "2026-08-20"

from adapters.shared.ml_helpers import _train_model_core
result = _train_model_core(
    model_type="lightgbm",
    symbols=SYMBOLS,
    start_date=START_DATE,
    end_date=END_DATE,
    test_size=0.2,
)

print("\n=== 训练结果 ===")
print(f"成功: {result.get('success')}")
if result.get('success'):
    print(f"版本: {result.get('version')}")
    print(f"训练准确率: {result.get('train_accuracy'):.4f}")
    print(f"测试准确率: {result.get('test_accuracy'):.4f}")
    print(f"样本数: {result.get('train_samples')}")
else:
    print(f"错误: {result.get('error')}")
