#!/usr/bin/env python3
"""
模型重训练脚本（R2回填后 + R3修复）

目的：使用R0+R1修复后的新鲜因子重新训练模型，修复退化问题
策略：
- 使用回填后的250天历史数据
- 训练样本：500只股票（回填覆盖的股票）
- 时间范围：2025-09-04 ~ 2026-08-20（回填范围）
- 模型类型：lightgbm（比xgboost更快，效果相近）
- 验证：训练后立即评估，确认不再返回恒定值
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)

BASE_URL = "http://localhost:5001"


def train_model(
    model_type: str = "lightgbm",
    start_date: str = "2025-09-04",
    end_date: str = "2026-08-20",
    symbols_limit: int = 500,
    test_size: float = 0.2,
) -> dict:
    """
    训练新模型
    
    Args:
        model_type: 模型类型（lightgbm推荐，更快）
        start_date: 训练数据起始日期（回填起始）
        end_date: 训练数据结束日期
        symbols_limit: 训练样本股票数
        test_size: 测试集比例
    
    Returns:
        训练结果
    """
    logger.info(f"开始训练 {model_type} 模型")
    logger.info(f"数据范围: {start_date} ~ {end_date}")
    logger.info(f"样本数: {symbols_limit} 只股票")
    
    # 获取股票列表（与回填相同的500只）
    from adapters.outbound.repositories.stock_repository import StockORMRepository
    
    repo = StockORMRepository()
    stocks = repo.get_all(limit=symbols_limit)
    symbols = [s['symbol'] for s in stocks]
    
    logger.info(f"实际训练股票: {len(symbols)} 只")
    
    # 调用训练API
    payload = {
        "model_type": model_type,
        "start_date": start_date,
        "end_date": end_date,
        "symbols": symbols,
        "test_size": test_size,
    }
    
    response = requests.post(f"{BASE_URL}/api/ml/train", json=payload, timeout=600)
    
    if response.status_code != 200:
        logger.error(f"训练失败: HTTP {response.status_code}")
        return {"success": False, "error": f"HTTP {response.status_code}"}
    
    result = response.json()
    return result


def test_prediction(model_type: str, test_symbols: list = None) -> dict:
    """
    测试模型预测（验证是否修复退化）
    
    Args:
        model_type: 模型类型
        test_symbols: 测试股票列表
    
    Returns:
        预测结果
    """
    if test_symbols is None:
        test_symbols = ["600519", "000001", "600737"]
    
    logger.info(f"测试 {model_type} 模型预测")
    
    payload = {
        "model_type": model_type,
        "symbols": test_symbols,
        "version": "latest",
    }
    
    response = requests.post(f"{BASE_URL}/api/ml/predict", json=payload, timeout=60)
    
    if response.status_code != 200:
        logger.error(f"预测失败: HTTP {response.status_code}")
        return {"success": False, "error": f"HTTP {response.status_code}"}
    
    result = response.json()
    
    # 检查是否所有预测都相同（退化症状）
    if result.get("success") and result.get("data", {}).get("predictions"):
        preds = result["data"]["predictions"]
        probs = [p["probability"] for p in preds]
        
        if len(set(probs)) == 1:
            logger.warning(f"⚠️ 模型仍退化：所有预测相同 (prob={probs[0]})")
        else:
            logger.info(f"✓ 模型正常：预测有差异 (probs={probs})")
    
    return result


def main():
    """主流程：训练 → 测试 → 报告"""
    print("=== 模型重训练（R2回填后 + R3修复） ===\n")
    
    # 1. 训练新模型
    print("步骤1：训练新模型（lightgbm）")
    train_result = train_model(
        model_type="lightgbm",
        start_date="2025-09-04",
        end_date="2026-08-20",
        symbols_limit=500,
        test_size=0.2,
    )
    
    print(f"\n训练结果:")
    print(f"  success: {train_result.get('success')}")
    if train_result.get('success'):
        data = train_result.get('data', {})
        print(f"  version: {data.get('version')}")
        print(f"  train_accuracy: {data.get('train_accuracy', 'N/A')}")
        print(f"  test_accuracy: {data.get('test_accuracy', 'N/A')}")
        print(f"  samples: {data.get('train_samples', 'N/A')}")
    else:
        print(f"  error: {train_result.get('error')}")
        return
    
    # 2. 测试预测（验证修复）
    print("\n步骤2：测试预测（验证退化是否修复）")
    test_result = test_prediction("lightgbm", ["600519", "000001", "600737"])
    
    if test_result.get("success"):
        preds = test_result.get("data", {}).get("predictions", [])
        print(f"\n预测结果:")
        for p in preds:
            print(f"  {p['symbol']}: prob={p['probability']}, class={p['predicted_class']}, conf={p['confidence']}")
        
        # 判断是否修复
        probs = [p["probability"] for p in preds]
        if len(set(probs)) == 1:
            print(f"\n❌ 退化未修复：所有预测仍相同 (prob={probs[0]})")
        else:
            print(f"\n✅ 退化已修复：预测有差异")
    else:
        print(f"  预测失败: {test_result.get('error')}")
    
    # 3. 清理旧模型（可选）
    print("\n提示：如需清理旧xgboost模型，手动删除 live_trading/models/xgboost_*.pkl")
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
