# SignalGenerator 100% 实现计划

**基于设计**: [2026-03-30-signal-generator-100-design.md](../specs/2026-03-30-signal-generator-100-design.md)

---

## 实现步骤

### Phase 1: 卖出信号检测（TS）

**目标**: 让 `SignalGenerator.scan()` 能检测卖出信号

**文件**: `src/services/quant/signal-generator.ts`

**变更**:
1. 修改 `checkStock()` 方法，在买入信号检测后新增卖出信号检测逻辑
2. 检查 `strategy.exit.conditions` 是否存在且非空
3. 调用 `matchConditions(tech, strategy.exit.conditions, 'OR')`
4. 如果匹配，返回 `action: 'sell'` 的信号

**测试**: 创建单元测试 `signal-generator.test.ts`，mock tech 数据验证卖出信号触发

---

### Phase 2: 冷启动置信度（TS）

**目标**: 实现规则计数 + 强信号 bonus 的置信度计算

**文件**: `src/services/quant/signal-generator.ts`

**变更**:
1. 新增私有方法 `calculateRuleConfidence(tech, conditions, action)`
2. 计算基础分 = 匹配条件数 / 总条件数
3. 检测强信号并加 bonus:
   - 买入: RSI < 30 (+0.1), 布林下轨触碰 (+0.1)
   - 卖出: RSI > 70 (+0.1), 布林上轨触碰 (+0.1)
4. 返回 `min(基础分 + bonus, 1.0)`
5. 在 `checkStock()` 中调用此方法替换 hardcoded `0.8`

**测试**: 单元测试验证 RSI<30 时 bonus 生效

---

### Phase 3: Python ML 基础设施

**目标**: 创建 XGBoost 训练和预测模块

**新增文件**:
- `python/ml/__init__.py` — 空文件
- `python/ml/signal_predictor.py` — 预测模块
- `python/ml/signal_trainer.py` — 训练脚本

**signal_predictor.py 实现**:
```python
import pickle
import os
import numpy as np

MODEL_PATH = '.pi-invest/quant/models/signal_confidence.pkl'

def predict(features: dict) -> dict:
    """预测置信度，返回 {confidence: float, model: str}"""
    if not os.path.exists(MODEL_PATH):
        return {"confidence": None, "model": "none"}

    with open(MODEL_PATH, 'rb') as f:
        model = pickle.load(f)

    # 特征顺序必须和训练时一致
    X = np.array([[
        features['rsi'],
        features['ma5_ma20_ratio'],
        features['ma20_ma60_ratio'],
        features['macd_histogram'],
        features['bb_position'],
        features['volume_ratio'],
        features['conditions_matched_ratio'],
        features['action']
    ]])

    proba = model.predict_proba(X)[0][1]  # 正类概率
    return {"confidence": float(proba), "model": "xgboost"}
```

**signal_trainer.py 实现**:
- 读取 `.pi-invest/quant/signals/*.json`
- 从 StockDB kline 缓存取后5日收盘价
- 计算涨幅，生成标签（涨幅>2% → 1）
- 至少50条样本才训练
- 保存模型到 `.pi-invest/quant/models/signal_confidence.pkl`

---

### Phase 4: Bridge 扩展

**目标**: 在 `akshare_bridge.py` 中新增 `predict_signal_confidence` 函数

**文件**: `python/akshare_bridge.py`

**变更**:
1. 在文件顶部 import: `from ml.signal_predictor import predict as ml_predict`
2. 新增函数:
```python
def predict_signal_confidence(symbol, indicators, action):
    features = {
        'rsi': indicators.get('rsi', 50),
        'ma5_ma20_ratio': indicators.get('ma5', 0) / max(indicators.get('ma20', 1), 1),
        'ma20_ma60_ratio': indicators.get('ma20', 0) / max(indicators.get('ma60', 1), 1),
        'macd_histogram': indicators.get('macd_histogram', 0),
        'bb_position': _calc_bb_position(indicators),
        'volume_ratio': 1.0,  # 占位
        'conditions_matched_ratio': indicators.get('conditions_matched_ratio', 0),
        'action': 0 if action == 'buy' else 1
    }
    return ml_predict(features)
```
3. 在 `FUNCTIONS` 字典中注册: `"predict_signal_confidence": predict_signal_confidence`

---

### Phase 5: TS 调用 ML 预测

**目标**: `SignalGenerator` 优先使用 XGBoost，回退到规则

**文件**: `src/services/quant/signal-generator.ts`

**变更**:
1. 在 `checkStock()` 中，计算置信度时:
   - 先调用 `TS_FUNCTIONS['predict_signal_confidence']({symbol, indicators: tech, action})`
   - 解析返回的 `{confidence, model}`
   - 如果 `model === "xgboost"`，使用 ML 置信度
   - 否则回退到 `calculateRuleConfidence()`
2. Signal 输出新增 `model` 字段

---

### Phase 6: 训练工具

**目标**: 新增 Agent 工具 `train_signal_model`

**文件**: `src/services/quant/quant-tools.ts`

**变更**:
1. 新增 `trainSignalModelTool`:
   - `action: 'train'` — 调用 Python `signal_trainer.py` 训练
   - `action: 'status'` — 读取模型文件，返回样本数、准确率、最后训练时间
2. 添加到 `quantTools` 数组导出

---

## 验证清单

- [ ] Phase 1: 创建含 `exit.conditions` 的策略，`scan` 后出现 `sell` 信号
- [ ] Phase 2: 无模型时，置信度使用规则计数，RSI<30 有 bonus
- [ ] Phase 3-5: 积累50条信号，训练模型，再次 `scan` 置信度来源变为 `xgboost`
- [ ] Phase 6: `train_signal_model action=status` 显示模型状态

---

## 依赖

- Python 包: `xgboost`, `scikit-learn`, `numpy`
- 安装: `pip install xgboost scikit-learn numpy`
