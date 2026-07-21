# Phase 3 工作计划

**日期**: 2026-06-19 23:50  
**阶段**: Phase 3 - IR优化与完全达标  
**状态**: 🔄 进行中

---

## Phase 3 目标

基于V6的成功（IC=0.25），Phase 3专注于提升IR稳定性：

**目标指标**:
- IC > 0.04 ✅ (V6已达0.25)
- IR > 1.5 ❌ (V6为0.48，需提升3倍)
- 至少2/4窗口达标

---

## V6 → V7 改进策略

### 问题诊断

**V6结果分析**:
```
窗口1: IC=0.27, IR=0.71
窗口2: IC=0.24, IR=0.41
窗口3: IC=0.21, IR=0.10 ← 极低
窗口4: IC=0.28, IR=0.70

平均: IC=0.25, IR=0.48
```

**核心问题**: 
- IC已足够高（预测方向正确）
- IR不足源于稳定性差（窗口3的IR=0.10拉低平均）

**原因推测**:
1. 只有技术因子（财务数据获取失败）
2. 参数未优化（使用固定参数）
3. 市场环境变化大

### V7改进方案

#### 改进1: 财务数据集成 (P0)

**V6问题**: akshare SSL错误，未获取任何财务数据

**V7方案**: 从数据库获取
```python
# 查询已有的财务指标表
SELECT roe, roa, gross_margin, net_margin, debt_ratio, current_ratio
FROM quant.financial_indicators
WHERE symbol = ANY(symbols)
```

**预期**:
- 覆盖率取决于数据库现有数据
- 即使部分覆盖也能提升稳定性
- 基本面因子通常IR更高

#### 改进2: 贝叶斯参数优化 (P1)

**V6问题**: 使用固定参数
```python
# V6固定参数
params = {
    'max_depth': 5,
    'learning_rate': 0.05,
    'n_estimators': 100,
    ...
}
```

**V7方案**: 复用V2的贝叶斯优化
```python
# V7贝叶斯优化（30次迭代）
best_params = bayesian_optimize_xgb(X_train, y_train, n_trials=30)
```

**预期**:
- IC提升5-10%
- IR提升10-20%
- 总耗时增加5-10分钟

#### 改进3: 继续因子筛选

**V6成功经验**: 因子筛选使IC从-0.003提升到0.25

**V7延续**:
- 继续使用IC筛选（|IC| > 0.02）
- 可能发现基本面有效因子
- 技术+基本面组合

---

## 预期结果场景

### 场景A: 完全成功 (概率40%)

**条件**:
- 数据库有足够财务数据（>50%覆盖）
- 基本面因子有效（IC > 0.03）
- 参数优化成功

**结果**:
- IC: 0.25-0.30 ✅
- IR: 1.5-2.0 ✅
- 达标窗口: 3-4/4 ✅

**下一步**: 模型部署，实盘准备

### 场景B: 部分改善 (概率45%)

**条件**:
- 财务数据覆盖不足（20-50%）
- 或基本面因子效果一般
- 参数优化有效

**结果**:
- IC: 0.25-0.28 ✅
- IR: 0.8-1.2 ⚠️
- 达标窗口: 0-1/4 ❌

**下一步**: V8迭代（市场环境分类）

### 场景C: 无明显改善 (概率15%)

**条件**:
- 数据库财务数据太少（<20%）
- 参数优化无效
- 市场非平稳性太强

**结果**:
- IC: 0.22-0.26 ✅
- IR: 0.45-0.6 ❌
- 达标窗口: 0/4 ❌

**下一步**: 备选方案（降低目标或改用深度学习）

---

## V7实现细节

### 代码结构

```python
# V7复用V6的成功模块
from train_ml_v6_optimized import (
    get_stocks,                # 获取股票列表
    fetch_kline_data,          # 获取K线数据
    calculate_market_return,   # 计算市场基准
    calculate_technical_factors, # 计算技术因子
    prepare_labels,            # 准备标签
    analyze_factor_ic,         # 因子IC分析
    train_rolling_windows      # 滚动窗口训练
)

# V7新增模块
fetch_financial_from_database()  # 从数据库获取财务数据
merge_financial_factors()        # 合并财务因子（前向填充）
bayesian_optimize_xgb()          # 贝叶斯参数优化
```

### 关键改进

1. **财务数据查询**
```python
query = '''
    SELECT symbol, report_date, roe, roa, gross_margin, 
           net_margin, debt_ratio, current_ratio
    FROM quant.financial_indicators
    WHERE symbol = ANY(%s)
'''
```

2. **前向填充防止未来信息泄露**
```python
# 每个交易日使用最近的已公布财报
for trade_date in trading_dates:
    available_reports = financial_df[financial_df['report_date'] <= trade_date]
    latest_report = available_reports.iloc[-1]
    # 使用latest_report的财务指标
```

3. **贝叶斯优化**
```python
# 参数空间
pbounds = {
    'max_depth': (3, 8),
    'learning_rate': (0.01, 0.3),
    'n_estimators': (50, 200),
    'subsample': (0.6, 1.0),
    ...
}

# 优化目标：最大化交叉验证IC
optimizer.maximize(init_points=5, n_iter=25)
```

---

## 时间预估

| 步骤 | 预计耗时 | 说明 |
|------|----------|------|
| 数据准备 | 2-3分钟 | K线、市场基准、技术因子 |
| 财务数据查询 | 1分钟 | 数据库查询 |
| 因子IC分析 | 3-4分钟 | 分析所有因子 |
| 贝叶斯优化 | 10-15分钟 | 30次迭代 |
| 滚动窗口训练 | 3-5分钟 | 4个窗口 |
| **总计** | **19-28分钟** | - |

**V6耗时**: 8分钟  
**V7增加**: 11-20分钟（主要是贝叶斯优化）

---

## 成功标准

### 最低目标

- IC > 0.04 (V6已达标)
- IR > 0.8 (V6的0.48提升67%)
- 至少1/4窗口达标

### 理想目标

- IC > 0.04 ✅
- IR > 1.5 ✅
- 至少2/4窗口达标 ✅

### 延展目标

- IC > 0.25 (保持V6水平)
- IR > 2.0 (超越目标)
- 3-4/4窗口达标

---

## 备选方案（如果V7仍未达标）

### V8方案1: 市场环境分类

**思路**: 牛市/熊市/震荡市分别训练

```python
def detect_market_regime(df):
    # 市场波动率
    volatility = df['market_return'].rolling(20).std()
    
    # 市场趋势
    trend = df['market_avg_close'].rolling(60).mean().pct_change()
    
    if volatility > 0.03:
        return "high_volatility"
    elif trend > 0.01:
        return "bull"
    else:
        return "bear"

# 分环境训练
models = {}
for regime in ['bull', 'bear', 'high_vol']:
    data_regime = data_df[data_df['regime'] == regime]
    models[regime] = train(data_regime)
```

**预期**: IR提升20-30%

### V8方案2: 集成学习

**思路**: 多模型加权平均

```python
from lightgbm import LGBMRegressor
from catboost import CatBoostRegressor

models = [
    XGBRegressor(**xgb_params),
    LGBMRegressor(**lgb_params),
    CatBoostRegressor(**cat_params)
]

# 训练
for model in models:
    model.fit(X_train, y_train)

# 加权预测
weights = [0.4, 0.3, 0.3]
predictions = sum(w * m.predict(X_test) for w, m in zip(weights, models))
```

**预期**: IR提升10-15%

### V8方案3: 深度学习

**思路**: LSTM或Transformer时序模型

```python
import torch
import torch.nn as nn

class StockPredictor(nn.Module):
    def __init__(self, input_dim, hidden_dim=64):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, 1)
    
    def forward(self, x):
        _, (h_n, _) = self.lstm(x)
        return self.fc(h_n[-1])
```

**预期**: 可能更强的时序建模能力

---

## 风险评估

### 高风险

1. **数据库财务数据不足**
   - 概率: 中等
   - 影响: 高（V7主要改进点）
   - 应对: 降级到只参数优化

2. **贝叶斯优化无效**
   - 概率: 低
   - 影响: 中等
   - 应对: 使用网格搜索

### 中风险

1. **市场非平稳性太强**
   - 概率: 中等
   - 影响: 中等
   - 应对: V8市场环境分类

2. **基本面因子无效**
   - 概率: 低
   - 影响: 中等
   - 应对: 继续使用纯技术因子

### 低风险

1. **代码bug**
   - 概率: 低
   - 影响: 低
   - 应对: 单元测试，人工review

---

## 里程碑

### M1: V7训练完成 (今晚23:50-00:20)

- ✅ V7脚本创建
- 🔄 V7训练运行中
- ⏳ V7结果分析

### M2: 结果评估 (00:20-00:30)

- 对比V6 vs V7
- 判断是否达标
- 决定下一步方向

### M3A: 如果达标 (00:30-01:00)

- 模型保存
- 部署文档
- Phase 3总结

### M3B: 如果未达标 (00:30-02:00)

- V8方案选择
- V8实现
- 继续迭代

---

## 成功概率评估

基于V6的突破和V7的改进：

- **完全达标 (IC>0.04, IR>1.5)**: 40%
- **部分改善 (IC>0.04, IR>0.8)**: 45%
- **无明显改善**: 15%

**综合成功率: 85%** (完全或部分)

---

**创建时间**: 2026-06-19 23:50  
**V7训练状态**: 🔄 运行中  
**预计完成**: 2026-06-20 00:15
