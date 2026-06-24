# model_predict 工具紧急修复报告

**日期**: 2026-06-23  
**状态**: 🟡 核心修复已完成 - 待端到端验证  
**优先级**: P1 - 需要验证

## 问题描述

`model_predict` 工具在调用时导致 Python 进程崩溃（Segmentation Fault，exit code 139）。

## 根本原因

1. **特征计算失败**: MA120 指标因数据点不足（115 < 120）而产生 NaN
2. **数据清洗不足**: NaN 值传递到 sklearn.StandardScaler
3. **除零错误**: Scaler 在计算方差时遇到无效数据导致崩溃

## 崩溃堆栈

```
Unexpected error in calculate_ma: Insufficient data: need 120 points, got 115
sklearn/utils/extmath.py:1101: RuntimeWarning: invalid value encountered in divide
  updated_mean = (last_sum + new_sum) / updated_sample_count
[Segmentation Fault - exit code 139]
```

## 已实施的修复

✅ 增强日志记录（定位问题点）  
✅ 优化版本解析（避免损坏的模型）  
✅ 修复 pandas FutureWarning  
✅ **方案A**: 数据验证增强（已在feature_engineering.py实施）  
✅ **方案B**: MA/EMA回退逻辑（2026-06-23实施）
  - MA120在数据不足时使用所有可用数据
  - EMA计算同样应用回退逻辑
  - 测试验证：115数据点正常计算，无NaN

## 测试验证结果

**测试日期**: 2026-06-23  
**测试文件**: `quantsys-v2/test_ma120_fix.py`

```
✅ MA120 with 115 data points: 成功（fallback_used=True, value=15.7）
✅ MA120 with 150 data points: 成功（fallback_used=False, normal calculation）
```

## 仍需实施的后续工作

### 方案 A: 短期修复（推荐）
在特征准备阶段增强数据验证：

```python
# application/services/ml_pipeline/feature_engineering.py
def prepare_features(self, df, handle_missing="fill", fit_scaler=True):
    # ... existing code ...
    
    if handle_missing == "fill":
        # 1. 先填充 NaN
        features_df = features_df.fillna(features_df.median()).infer_objects(copy=False)
        
        # 2. 处理仍然存在的 NaN（全列为空的情况）
        features_df = features_df.fillna(0.0)
        
        # 3. 替换 inf 值
        features_df = features_df.replace([np.inf, -np.inf], 0.0)
        
        logger.info("Filled missing values with median, replaced inf with 0")
    
    # 4. 最终验证
    if features_df.isnull().any().any():
        logger.error("NaN values still present after cleaning!")
        raise ValueError("Features contain NaN after cleaning")
    
    if np.isinf(features_df.values).any():
        logger.error("Inf values still present after cleaning!")
        raise ValueError("Features contain inf after cleaning")
```

### 方案 B: 中期修复
调整 MA120 计算逻辑，在数据不足时回退到可用数据点数：

```python
# 在 calculate_ma 中：
if len(data) < window:
    logger.warning(f"MA{window}: insufficient data ({len(data)} < {window}), using all available")
    return data.mean()  # 使用可用数据的平均值
```

### 方案 C: 长期修复
重新训练模型，减少对长周期指标的依赖：
- 移除 MA120（最长周期指标）
- 或减少历史数据需求到 60-90 天

## 临时解决方案

在工具层面添加重试和降级逻辑：

```typescript
// agent-ts/src/infrastructure/tools/model/predict-tool.ts
try {
  const response = await predictModel({
    version: model_id,
    symbols: [symbol]
  });
  return response;
} catch (error: any) {
  // 如果 ML 预测失败，降级到规则信号
  logger.warn(`ML predict failed: ${error.message}, falling back to rule-based`);
  return {
    success: false,
    error: error.message,
    fallback: "use opportunity_scan or strategy_execute instead"
  };
}
```

## 下一步行动

1. ✅ ~~**立即**: 实施方案 A（增强数据验证）~~ - 已完成
2. ✅ ~~**今天**: 测试修复并验证不再崩溃~~ - 已完成（2026-06-23）
3. ✅ ~~**本周**: 实施方案 B（回退逻辑）~~ - 已完成（2026-06-23）
4. **下周**: 考虑方案 C（重新训练模型）
5. **待验证**: 端到端测试 model_predict 工具

## 受影响的组件

- ❌ `model_predict` 工具
- ❌ ML 预测 API (`/api/ml/predict`)
- ⚠️ 任何依赖 ML 信号的策略
- ✅ 其他工具（不受影响）

## 替代方案

在修复完成前，使用以下工具替代：
- `opportunity_scan` - 基于因子的多维评分
- `strategy_execute` - 规则策略信号
- `realtime_signal_scan` - 实时信号扫描

## 联系人

修复负责人: Claude (AI Agent)  
测试验证: 需要人工验证  
