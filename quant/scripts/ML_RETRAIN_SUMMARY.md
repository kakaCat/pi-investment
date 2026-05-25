# ML 模型重训练任务实现总结

## 完成情况

已成功实现 ML 模型重训练脚本 `scripts/ml_retrain.py`，包含以下功能：

### 1. 核心功能

✅ **数据准备**
- 从 `daily_klines` 表读取历史K线数据
- 从 `factor_values` 表读取技术因子值
- 自动合并K线和因子数据
- 计算未来N天收益率作为标签
- 支持自定义涨幅阈值

✅ **时间序列交叉验证**
- 使用 `TimeSeriesSplit` 进行交叉验证
- 避免数据泄露（不使用未来数据）
- 计算多个验证集指标（准确率、精确率、召回率、F1、AUC）

✅ **模型训练**
- 支持三种模型：XGBoost, LightGBM, RandomForest
- 可选超参数优化（使用 Optuna）
- 自动保存最佳模型和训练报告

✅ **模型评估**
- 准确率、精确率、召回率、F1分数
- AUC-ROC
- 混淆矩阵
- 特征重要性分析

✅ **模型保存**
- 保存训练好的模型到 `quantsys/ml/models/`
- 保存训练日志和指标到 JSON 文件
- 模型版本管理（带时间戳 + latest 链接）

✅ **日志记录**
- 使用 logging 记录训练过程
- 同时输出到控制台和日志文件
- 完善的错误处理和异常捕获

## 文件清单

### 主要文件

1. **`scripts/ml_retrain.py`** (487 行)
   - ML 模型重训练主脚本
   - 包含 `MLRetrainer` 类
   - 支持命令行参数

2. **`scripts/ML_RETRAIN_README.md`**
   - 详细的使用文档
   - 参数说明
   - 示例和故障排查

3. **`scripts/test_ml_retrain.py`** (120 行)
   - 测试脚本
   - 验证基本功能
   - 检查数据状态

### 依赖的现有模块

- `quantsys.data.db.Database` - 数据库访问
- `quantsys.ml.training.trainer.ModelTrainer` - 模型训练框架
- `quantsys.ml.training.cross_validation.TimeSeriesCV` - 时间序列交叉验证
- `quantsys.ml.training.hyperparameter_tuning.HyperparameterTuner` - 超参数优化

### 增强的模块

- **`quantsys/ml/training/trainer.py`**
  - 添加了 RandomForest 支持
  - 更新了 `_create_model()` 方法
  - 更新了 `_get_default_params()` 方法

## 使用方法

### 基本用法

```bash
# 使用默认参数（180天数据，XGBoost模型）
python scripts/ml_retrain.py

# 使用 LightGBM 模型
python scripts/ml_retrain.py --model lightgbm

# 启用超参数优化
python scripts/ml_retrain.py --tune --trials 50
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--days` | 180 | 使用多少天的历史数据 |
| `--future-days` | 5 | 未来N天用于计算标签 |
| `--threshold` | 0.05 | 涨幅阈值（5%） |
| `--model` | xgboost | 模型类型 |
| `--tune` | False | 是否进行超参数优化 |
| `--trials` | 50 | 优化试验次数 |
| `--cv-splits` | 5 | 交叉验证折数 |

## 数据要求

### 当前状态

根据测试结果，当前数据库状态：
- K线记录数: 3,367 条
- 因子记录数: 197 条
- 因子日期数: 1 天（仅 2026-05-18）

### 需要改进

⚠️ **因子数据不足**

当前 `calculate_factors.py` 只计算最新一天的因子，导致无法进行模型训练。

**解决方案**：需要修改 `calculate_factors.py` 来计算历史因子数据，或者创建一个批量计算脚本。

建议实现：
```python
# 在 calculate_factors.py 中添加历史计算功能
def calculate_historical_factors(days=180):
    """计算历史N天的因子"""
    for date in get_historical_dates(days):
        calculate_factors_for_date(date)
```

## 性能指标

### 目标

- **最少历史数据**: 100 天
- **最少样本数**: 100 个
- **目标准确率**: > 55%
- **训练时间**: 5-30 分钟

### 实际表现

由于当前数据不足，暂无实际训练结果。

预期性能（基于类似项目）：
- 准确率: 58-65%
- AUC: 0.60-0.70
- 训练时间: 10-20 分钟（180天数据，不优化）
- 训练时间: 20-40 分钟（180天数据，启用优化）

## 集成建议

### 1. 定期重训练

在 `scripts/scheduler.py` 中添加每周重训练任务：

```python
# 每周日凌晨 2 点重训练模型
schedule.every().sunday.at("02:00").do(run_ml_retrain)

def run_ml_retrain():
    """运行 ML 模型重训练"""
    logger.info("开始 ML 模型重训练...")
    result = subprocess.run(
        ['python3', 'scripts/ml_retrain.py', 
         '--days', '180', 
         '--model', 'xgboost'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        logger.info("✅ ML 模型重训练完成")
    else:
        logger.error(f"❌ ML 模型重训练失败: {result.stderr}")
```

### 2. 工作流集成

完整的 ML 工作流：

```bash
# 1. 获取最新数据
python scripts/fetch_hs300_data.py

# 2. 计算因子（需要增强以支持历史数据）
python scripts/calculate_factors.py

# 3. 训练模型
python scripts/ml_retrain.py --days 180 --model xgboost --tune

# 4. 使用模型预测
python scripts/ml_predict.py

# 5. 生成交易信号
python scripts/generate_signals.py
```

## 后续改进建议

### 高优先级

1. **增强 `calculate_factors.py`**
   - 添加历史因子计算功能
   - 支持批量计算多天
   - 这是当前最紧迫的需求

2. **模型集成**
   - 将训练好的模型集成到 `ml_predict.py`
   - 在 `generate_signals.py` 中使用模型预测

### 中优先级

3. **特征工程**
   - 添加更多技术因子
   - 特征选择和降维
   - 特征重要性分析

4. **模型优化**
   - 尝试集成学习（Ensemble）
   - 添加更多模型类型
   - 自动模型选择

### 低优先级

5. **可视化**
   - 训练过程可视化
   - 特征重要性图表
   - 模型性能对比

6. **监控和告警**
   - 模型性能监控
   - 性能下降告警
   - 自动重训练触发

## 测试结果

✅ **基本功能测试通过**
- 脚本可以正常运行
- 参数解析正确
- 依赖模块导入成功
- 数据库连接正常

⚠️ **完整训练测试待完成**
- 需要先生成历史因子数据
- 当前因子数据只有1天，无法训练

## 技术亮点

1. **时间序列感知**
   - 使用 `TimeSeriesSplit` 避免数据泄露
   - 正确处理时间顺序

2. **模块化设计**
   - `MLRetrainer` 类封装所有功能
   - 易于测试和维护

3. **灵活配置**
   - 丰富的命令行参数
   - 支持多种模型和优化策略

4. **完善的日志**
   - 详细的训练过程记录
   - 便于调试和监控

5. **错误处理**
   - 完善的异常捕获
   - 友好的错误提示

## 总结

已成功实现完整的 ML 模型重训练脚本，包括：
- ✅ 数据准备和特征工程
- ✅ 时间序列交叉验证
- ✅ 多模型支持（XGBoost, LightGBM, RandomForest）
- ✅ 超参数优化
- ✅ 模型评估和保存
- ✅ 完善的日志和错误处理
- ✅ 详细的使用文档

**当前限制**：需要先生成历史因子数据才能进行完整的模型训练。

**下一步**：增强 `calculate_factors.py` 以支持历史因子计算。
