# ML 模型重训练脚本使用指南

## 概述

`ml_retrain.py` 是一个完整的机器学习模型重训练脚本，用于从数据库读取历史数据、训练模型并评估性能。

## 功能特性

1. **数据准备**
   - 从 `daily_klines` 表读取历史K线数据
   - 从 `factor_values` 表读取技术因子
   - 自动构建训练集（特征 + 标签）
   - 标签：未来N天的涨跌幅

2. **时间序列交叉验证**
   - 使用 `TimeSeriesSplit` 进行交叉验证
   - 避免数据泄露（不使用未来数据）
   - 计算多个验证集指标

3. **模型训练**
   - 支持三种模型：XGBoost, LightGBM, RandomForest
   - 可选超参数优化（使用 Optuna）
   - 自动保存最佳模型

4. **模型评估**
   - 准确率、精确率、召回率、F1分数
   - AUC-ROC
   - 混淆矩阵
   - 特征重要性分析

5. **模型保存**
   - 保存训练好的模型到 `quantsys/ml/models/`
   - 保存训练日志和指标到 JSON 文件
   - 模型版本管理（带时间戳）

## 使用方法

### 基本用法

```bash
# 使用默认参数训练 XGBoost 模型
python scripts/ml_retrain.py

# 使用 180 天历史数据
python scripts/ml_retrain.py --days 180

# 训练 LightGBM 模型
python scripts/ml_retrain.py --model lightgbm

# 训练 RandomForest 模型
python scripts/ml_retrain.py --model randomforest
```

### 超参数优化

```bash
# 启用超参数优化（50次试验）
python scripts/ml_retrain.py --tune

# 自定义试验次数
python scripts/ml_retrain.py --tune --trials 100

# LightGBM + 超参数优化
python scripts/ml_retrain.py --model lightgbm --tune --trials 100
```

### 自定义参数

```bash
# 使用 365 天历史数据，未来 10 天标签，涨幅阈值 3%
python scripts/ml_retrain.py --days 365 --future-days 10 --threshold 0.03

# 自定义交叉验证折数
python scripts/ml_retrain.py --cv-splits 10

# 指定数据库路径
python scripts/ml_retrain.py --db-path /path/to/stocks.db
```

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--days` | int | 180 | 使用多少天的历史数据 |
| `--future-days` | int | 5 | 未来N天用于计算标签 |
| `--threshold` | float | 0.05 | 涨幅阈值（5%），超过此值为正样本 |
| `--model` | str | xgboost | 模型类型：xgboost, lightgbm, randomforest |
| `--tune` | flag | False | 是否进行超参数优化 |
| `--trials` | int | 50 | 超参数优化试验次数 |
| `--cv-splits` | int | 5 | 交叉验证折数 |
| `--db-path` | str | 自动检测 | 数据库路径 |

## 输出文件

训练完成后，会生成以下文件：

```
quantsys/ml/models/
├── xgboost_model_20260518_143000.pkl          # 带时间戳的模型文件
├── xgboost_latest.pkl                         # 最新模型（符号链接）
├── training_report_20260518_143000.json       # 训练报告
└── training_report_latest.json                # 最新报告
```

## 训练报告示例

```json
{
  "success": true,
  "model_type": "xgboost",
  "timestamp": "2026-05-18T14:30:00",
  "data": {
    "total_samples": 5000,
    "train_samples": 4000,
    "test_samples": 1000,
    "n_features": 42,
    "positive_samples": 1500,
    "negative_samples": 3500,
    "class_balance": 0.3
  },
  "cv_results": {
    "mean_scores": {
      "accuracy": 0.6234,
      "precision": 0.6012,
      "recall": 0.5834,
      "f1": 0.5921,
      "auc": 0.6543
    },
    "std_scores": {
      "accuracy": 0.0234,
      "precision": 0.0312,
      "recall": 0.0289,
      "f1": 0.0298,
      "auc": 0.0267
    }
  },
  "test_metrics": {
    "accuracy": 0.6180,
    "precision": 0.5950,
    "recall": 0.5720,
    "f1": 0.5833,
    "auc": 0.6421,
    "confusion_matrix": [[650, 150], [278, 222]]
  },
  "feature_importance": [0.05, 0.08, 0.03, ...],
  "model_path": "quantsys/ml/models/xgboost_model_20260518_143000.pkl"
}
```

## 性能要求

- **最少历史数据**: 100 天
- **最少样本数**: 100 个
- **目标准确率**: > 55%
- **训练时间**: 通常 5-30 分钟（取决于数据量和是否优化）

## 注意事项

1. **数据要求**
   - 确保 `daily_klines` 表有足够的历史数据
   - 确保 `factor_values` 表已计算因子（运行 `calculate_factors.py`）
   - 数据质量直接影响模型性能

2. **类别平衡**
   - 如果正负样本比例严重失衡（< 10% 或 > 90%），考虑调整 `--threshold` 参数
   - 建议正样本比例在 20%-40% 之间

3. **超参数优化**
   - 超参数优化会显著增加训练时间（10-30分钟）
   - 建议首次训练时使用默认参数，性能不佳时再启用优化
   - 可以先用较少的试验次数（如 `--trials 20`）快速测试

4. **模型选择**
   - **XGBoost**: 默认选择，性能稳定，速度快
   - **LightGBM**: 大数据集上更快，内存占用更少
   - **RandomForest**: 更稳健，但训练速度较慢

5. **定期重训练**
   - 建议每周重训练一次模型
   - 使用最新的历史数据可以提高预测准确性
   - 可以通过 cron 或调度器自动化执行

## 故障排查

### 错误：样本数量不足

```
ValueError: 样本数量不足: 50 < 100
```

**解决方案**:
- 增加 `--days` 参数（如 `--days 365`）
- 确保数据库中有足够的历史数据
- 运行 `fetch_hs300_data.py` 获取更多数据

### 错误：准确率低于 55%

```
⚠️  警告: 模型准确率低于55%
```

**解决方案**:
1. 增加训练数据：`--days 365`
2. 调整涨幅阈值：`--threshold 0.03` 或 `--threshold 0.08`
3. 启用超参数优化：`--tune --trials 100`
4. 尝试其他模型：`--model lightgbm` 或 `--model randomforest`

### 错误：类别严重不平衡

```
⚠️  类别严重不平衡: 5.2% 正样本
```

**解决方案**:
- 降低涨幅阈值：`--threshold 0.02` 或 `--threshold 0.03`
- 增加未来天数：`--future-days 10`

## 集成到调度器

在 `scripts/scheduler.py` 中添加每周重训练任务：

```python
# 每周日凌晨 2 点重训练模型
schedule.every().sunday.at("02:00").do(run_ml_retrain)

def run_ml_retrain():
    """运行 ML 模型重训练"""
    logger.info("开始 ML 模型重训练...")
    result = subprocess.run(
        ['python3', 'scripts/ml_retrain.py', '--days', '180', '--model', 'xgboost'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        logger.info("✅ ML 模型重训练完成")
    else:
        logger.error(f"❌ ML 模型重训练失败: {result.stderr}")
```

## 相关脚本

- `calculate_factors.py`: 计算技术因子（重训练前需要运行）
- `ml_predict.py`: 使用训练好的模型进行预测
- `generate_signals.py`: 生成交易信号

## 示例工作流

```bash
# 1. 获取最新数据
python scripts/fetch_hs300_data.py

# 2. 计算因子
python scripts/calculate_factors.py

# 3. 训练模型（使用超参数优化）
python scripts/ml_retrain.py --days 180 --model xgboost --tune --trials 50

# 4. 使用模型预测
python scripts/ml_predict.py

# 5. 生成交易信号
python scripts/generate_signals.py
```

## 日志文件

训练日志会同时输出到：
- 控制台（实时查看）
- `ml_retrain.log` 文件（持久化保存）

查看日志：
```bash
tail -f ml_retrain.log
```
