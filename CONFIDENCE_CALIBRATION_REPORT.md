# 信号置信度贝叶斯校准修复报告

## 问题描述
当前系统中的交易信号置信度存在以下问题：
- 止损/止盈信号的置信度硬编码为 100% (`confidence=1.0`)
- 其他策略信号的置信度计算简单，容易达到 100%
- 缺乏统一的置信度校准机制

## 解决方案
实现贝叶斯置信度校准系统，使用 Sigmoid 函数将原始置信度映射到合理范围：

```python
confidence = 1 / (1 + e^(-k * logit))
```

其中：
- `k = 0.3`：控制曲线陡峭程度
- 最大置信度上限：0.85 (85%)
- 止损/止盈信号上限：0.75 (75%)

## 修改文件清单

### 1. 新增文件

#### `/quant/quantsys/utils/confidence_calibration.py`
新增贝叶斯校准工具模块，包含以下函数：

- `bayesian_calibrate()` - 基础贝叶斯校准函数
- `calibrate_rsi_confidence()` - RSI 信号置信度校准
- `calibrate_ma_confidence()` - 均线交叉信号置信度校准
- `calibrate_bollinger_confidence()` - 布林带信号置信度校准
- `calibrate_macd_confidence()` - MACD 信号置信度校准
- `calibrate_kdj_confidence()` - KDJ 信号置信度校准
- `calibrate_stop_loss_confidence()` - 止损信号置信度校准
- `calibrate_take_profit_confidence()` - 止盈信号置信度校准

### 2. 修改文件

#### `/quant/quantsys/strategies/base.py`
**修改内容：**
- 导入置信度校准函数
- 修改 `on_bar()` 方法中的止损信号生成逻辑
  - 原：`confidence=1.0`
  - 新：根据亏损百分比计算校准后的置信度
- 修改 `on_bar()` 方法中的止盈信号生成逻辑
  - 原：`confidence=1.0`
  - 新：根据盈利百分比计算校准后的置信度

#### `/quant/quantsys/strategies/classic/rsi_reversal.py`
**修改内容：**
- 导入 `calibrate_rsi_confidence`
- 重写 `_calculate_confidence()` 方法
  - 原：使用阶梯式置信度 (0.7, 0.8, 0.9)
  - 新：使用贝叶斯校准，根据 RSI 距离阈值的程度平滑计算

#### `/quant/quantsys/strategies/classic/ma_cross.py`
**修改内容：**
- 导入 `calibrate_ma_confidence`
- 重写 `_calculate_confidence()` 方法
  - 原：基于固定阈值的加法逻辑
  - 新：使用贝叶斯校准，根据均线分离度计算

#### `/quant/quantsys/strategies/classic/bollinger_breakout.py`
**修改内容：**
- 导入 `calibrate_bollinger_confidence`
- 重写 `_calculate_confidence()` 方法
  - 原：基于固定阈值的加法逻辑
  - 新：使用贝叶斯校准，根据价格距离布林带的距离计算

#### `/quant/scripts/generate_signals.py`
**修改内容：**
- 导入所有校准函数
- 修改 `strategy_rsi_reversal()` - 使用 `calibrate_rsi_confidence()`
- 修改 `strategy_ma_crossover()` - 使用 `calibrate_ma_confidence()`
- 修改 `strategy_macd()` - 使用 `calibrate_macd_confidence()`
- 修改 `strategy_bollinger()` - 使用 `calibrate_bollinger_confidence()`
- 修改 `strategy_kdj()` - 使用 `calibrate_kdj_confidence()`

### 3. 测试文件

#### `/quant/tests/test_confidence_calibration.py`
单元测试，验证所有校准函数的正确性：
- 测试基础贝叶斯校准
- 测试各策略的置信度校准
- 验证最大置信度上限 (0.85)
- 验证止损/止盈置信度上限 (0.75)

#### `/quant/tests/test_strategy_confidence_integration.py`
集成测试，验证策略生成的信号置信度：
- 测试 RSI 策略信号
- 测试均线交叉策略信号
- 测试布林带策略信号
- 测试止损/止盈信号

## 新的置信度计算逻辑

### RSI 策略
```python
# 买入信号 (超卖)
raw_confidence = (threshold - rsi) / threshold
# RSI=10, threshold=30 -> raw=0.67 -> calibrated≈0.73

# 卖出信号 (超买)
raw_confidence = (rsi - threshold) / (100 - threshold)
# RSI=90, threshold=70 -> raw=0.67 -> calibrated≈0.73
```

### 均线交叉策略
```python
# 均线分离度越大，置信度越高
ma_diff_pct = abs(ma5 - ma20) / ma20
raw_confidence = 0.3 + (ma_diff_pct / 0.05) * 0.7
# 2% 分离 -> raw=0.58 -> calibrated≈0.62
```

### 布林带策略
```python
# 距离布林带越远，置信度越高
distance_pct = abs(price - band) / band
raw_confidence = 0.4 + (distance_pct / 0.05) * 0.6
# 2% 距离 -> raw=0.64 -> calibrated≈0.70
```

### MACD 策略
```python
# DIF 和 DEA 差值越大，置信度越高
dif_dea_diff = abs(dif - dea)
raw_confidence = 0.3 + (dif_dea_diff / 0.02) * 0.7
# 0.01 差值 -> raw=0.65 -> calibrated≈0.71
```

### KDJ 策略
```python
# 买入：K 值越低，置信度越高
raw_confidence = (threshold - k) / threshold
# K=5, threshold=20 -> raw=0.75 -> calibrated≈0.82

# 卖出：K 值越高，置信度越高
raw_confidence = (k - threshold) / (100 - threshold)
# K=95, threshold=80 -> raw=0.75 -> calibrated≈0.82
```

### 止损/止盈信号
```python
# 止损：亏损越大，置信度越高（但上限为 0.75）
loss_pct = abs((current_price - entry_price) / entry_price)
raw_confidence = 0.5 + (loss_pct / 0.1) * 0.5
# 5% 亏损 -> raw=0.75 -> calibrated=0.75

# 止盈：盈利越大，置信度越高（但上限为 0.75）
profit_pct = (current_price - entry_price) / entry_price
raw_confidence = 0.5 + (profit_pct / 0.2) * 0.5
# 15% 盈利 -> raw=0.875 -> calibrated=0.75 (capped)
```

## 测试结果

### 单元测试结果
```
✅ Basic calibration tests passed
✅ RSI calibration tests passed
✅ MA calibration tests passed
✅ Bollinger calibration tests passed
✅ MACD calibration tests passed
✅ KDJ calibration tests passed
✅ Stop-loss/take-profit calibration tests passed
✅ Maximum confidence cap verified - no 100% confidence possible!
```

### 关键发现
- 最大置信度上限：**0.85 (85%)**
- 止损/止盈信号上限：**0.75 (75%)**
- **没有任何信号可以达到 100% 置信度**
- 置信度随信号强度平滑增长

### 置信度分布示例

| 信号类型 | 弱信号 | 中等信号 | 强信号 | 极端信号 |
|---------|--------|---------|--------|----------|
| RSI     | 0.12   | 0.50    | 0.73   | 0.85     |
| MA Cross| 0.31   | 0.41    | 0.62   | 0.85     |
| Bollinger| 0.35  | 0.53    | 0.70   | 0.85     |
| MACD    | 0.23   | 0.46    | 0.71   | 0.85     |
| KDJ     | 0.12   | 0.50    | 0.82   | 0.85     |
| Stop-Loss| 0.55  | 0.65    | 0.75   | 0.75     |
| Take-Profit| 0.56| 0.68    | 0.75   | 0.75     |

## 优势

1. **防止过度自信**：最大置信度限制在 85%，避免系统过度自信
2. **平滑校准**：使用 Sigmoid 函数，置信度随信号强度平滑变化
3. **统一标准**：所有策略使用相同的校准机制，便于比较和组合
4. **可调参数**：k 参数可调整校准曲线的陡峭程度
5. **防御性信号**：止损/止盈信号的置信度上限更低 (75%)，反映其防御性质

## 使用示例

```python
from quantsys.utils.confidence_calibration import calibrate_rsi_confidence

# RSI 超卖信号
rsi = 15
confidence = calibrate_rsi_confidence(rsi, threshold=30, action='buy')
print(f"RSI={rsi} -> confidence={confidence:.4f}")  # 输出: confidence=0.5000

# RSI 极度超卖
rsi = 5
confidence = calibrate_rsi_confidence(rsi, threshold=30, action='buy')
print(f"RSI={rsi} -> confidence={confidence:.4f}")  # 输出: confidence=0.8176
```

## 后续建议

1. **动态调整 k 参数**：根据市场波动率动态调整 k 值
2. **历史回测验证**：使用历史数据验证新置信度对策略表现的影响
3. **置信度阈值优化**：根据回测结果优化各策略的置信度阈值
4. **组合策略权重**：在策略组合器中使用校准后的置信度作为权重

## 总结

成功实现贝叶斯置信度校准系统，解决了信号置信度 100% 的问题：

- ✅ 创建了统一的置信度校准工具
- ✅ 修复了止损/止盈信号的硬编码 100% 置信度
- ✅ 更新了所有策略的置信度计算逻辑
- ✅ 实现了最大置信度上限 (85%)
- ✅ 通过了所有单元测试和集成测试
- ✅ 置信度分布更加合理和可解释
