# SignalGenerator 100% 完成设计

**日期**: 2026-03-30
**目标**: 将 SignalGenerator 从 90% 补全到 100%，新增卖出信号检测 + XGBoost 置信度模型

---

## 背景

当前 `SignalGenerator` 缺少两块能力：

1. **卖出信号**：只能生成 `buy` 信号，`exit.conditions` 从未被检测
2. **置信度**：hardcoded `0.8`，无统计依据

`BacktestEngine` 已有完整的卖出/止损逻辑，`SignalGenerator` 需要对齐。

---

## 设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 卖出信号是否读持仓 | 否 | 只做技术指标卖出，不依赖持仓成本 |
| 置信度方案 | XGBoost | 最科学，项目已有 Python bridge |
| 训练标签 | 买入后5日涨幅 > 2% | 短期有效性验证 |
| 冷启动兜底 | 规则计数（匹配条件数/总条件数） | 模型未训练时保证可用 |

---

## 架构

```
SignalGenerator.scan()
  ├── 买入信号（现有）
  │     └── matchConditions(entry.conditions)
  ├── 卖出信号（新增）
  │     └── matchConditions(exit.conditions)
  └── 置信度（新增）
        ├── 冷启动：ruleConfidence() → 匹配条件数/总条件数 + 强信号bonus
        └── 模型就绪：XGBoostPredictor.predict() → Python bridge

Python 侧（新增）
  ├── python/ml/signal_trainer.py   — 训练 XGBoost 模型
  └── python/ml/signal_predictor.py — 预测置信度（被 bridge 调用）

akshare_bridge.py（扩展）
  └── predict_signal_confidence(symbol, indicators) → float
```

---

## 详细设计

### 1. 卖出信号检测

在 `SignalGenerator.checkStock()` 中，现有逻辑只检查 `entry.conditions`。新增：

```typescript
// 检查卖出条件（技术指标，不读持仓）
if (strategy.exit.conditions?.length) {
  const sellSignal = this.matchConditions(tech, strategy.exit.conditions, 'OR');
  if (sellSignal) {
    return { ...signal, action: 'sell' };
  }
}
```

`exit.conditions` 使用和 `entry.conditions` 相同的 `matchCondition` 逻辑（RSI、MA交叉、MACD、布林带），无需新增指标类型。

### 2. 置信度计算

#### 冷启动规则（无模型时）

```
基础分 = 匹配条件数 / 总条件数
强信号bonus：
  - RSI < 30（买入）或 RSI > 70（卖出）：+0.1
  - 布林带触碰下轨（买入）或上轨（卖出）：+0.1
最终置信度 = min(基础分 + bonus, 1.0)
```

#### XGBoost 模型

**特征（8个）**：
- `rsi` — RSI(14)
- `ma5_ma20_ratio` — MA5/MA20（均线强度）
- `ma20_ma60_ratio` — MA20/MA60（中期趋势）
- `macd_histogram` — MACD柱
- `bb_position` — (price - bb_lower) / (bb_upper - bb_lower)（布林带位置，0-1）
- `volume_ratio` — 当日量/20日均量（暂用1.0占位，后续接入）
- `conditions_matched_ratio` — 匹配条件数/总条件数
- `action` — 0=buy, 1=sell（买卖方向编码）

**标签**：买入后5个交易日收盘价涨幅 > 2% → 1，否则 → 0

**训练流程**（`signal_trainer.py`）：
1. 读取 `.pi-invest/quant/signals/*.json` 历史信号
2. 对每个信号，从 kline 缓存取后5日收盘价，计算涨幅，生成标签
3. 训练 XGBoost 分类器（`n_estimators=100, max_depth=4`）
4. 保存模型到 `.pi-invest/quant/models/signal_confidence.pkl`
5. 需要至少 **50条** 有标签样本才训练，否则跳过

**预测流程**（`signal_predictor.py`）：
1. 加载模型（不存在则返回 `null`）
2. 输入8个特征，输出 `predict_proba` 的正类概率作为置信度

**bridge 扩展**（`akshare_bridge.py`）：
```python
# 新增函数
def predict_signal_confidence(args):
    # args: { symbol, indicators, action }
    # 返回: { confidence: float, model: "xgboost"|"rule" }
```

### 3. 训练触发

新增 `quant-tools.ts` 工具 `train_signal_model`：

```typescript
// action: train — 触发训练
// action: status — 查看模型状态（样本数、准确率、最后训练时间）
```

Agent 可以手动触发，也可以在每次 `scan` 后自动检查样本数是否达到阈值。

---

## 文件变更

### 修改
- `src/services/quant/signal-generator.ts` — 新增卖出信号 + 置信度逻辑
- `src/services/quant/quant-tools.ts` — 新增 `train_signal_model` 工具
- `python/akshare_bridge.py` — 新增 `predict_signal_confidence` 函数

### 新增
- `python/ml/signal_trainer.py` — XGBoost 训练脚本
- `python/ml/signal_predictor.py` — 预测模块

---

## 冷启动行为

| 状态 | 置信度来源 | 输出示例 |
|------|-----------|---------|
| 无模型，无历史信号 | 规则计数 | `confidence: 0.67, model: "rule"` |
| 有模型（≥50样本） | XGBoost | `confidence: 0.82, model: "xgboost"` |

Signal 输出新增 `model` 字段，让用户知道置信度来源。

---

## 验证计划

### 自动测试
- `signal-generator.test.ts`：mock tech 数据，验证卖出信号触发
- `signal-generator.test.ts`：验证冷启动规则置信度计算（RSI<30 bonus）
- `signal_trainer.py`：单元测试标签生成逻辑

### 手动验证
1. 创建含 `exit.conditions` 的策略，运行 `generate_signals scan`，确认出现 `sell` 信号
2. 运行 `train_signal_model action=status`，确认显示"模型未就绪，当前样本数: N"
3. 积累50条信号后，运行 `train_signal_model action=train`，确认模型生成
4. 再次 `scan`，确认置信度来源变为 `xgboost`
