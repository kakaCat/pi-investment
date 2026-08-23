# Factors Domain - 因子计算与分析

**领域职责**: 因子库、因子分析、多因子模型

---

## 概述

Factors 领域提供完整的因子工程基础设施，包括 13 类因子库、因子分析工具、多因子模型（BARRA、Fama-French、Carhart）等。

**核心能力**:
- ✅ 13 类因子库（动量、趋势、波动率、成交量、反转、均线等）
- ✅ 因子分析工具（IC 分析、分层回测、正交化）
- ✅ 多因子模型（BARRA、Fama-French 三/五因子、Carhart 四因子）
- ✅ 另类因子（情绪因子）
- ✅ 因子暴露计算与归因分析
- ✅ 因子监控与降维

---

## 目录结构

```
factors/
├── __init__.py                    # 领域入口
│
├── library/                 (13)  # 因子库
│   ├── __init__.py
│   ├── base.py                    # 因子基类 (TechnicalFactorCalculator)
│   ├── momentum.py                # 动量因子（RS、MACD、威廉 %R）
│   ├── trend.py                   # 趋势因子（ADX、抛物线 SAR、DI）
│   ├── volatility.py              # 波动率因子（ATR、布林带宽度、历史波动率）
│   ├── volume.py                  # 成交量因子（OBV、CMF、VWAP）
│   ├── reversal.py                # 反转因子（RSI、随机指标、CCI）
│   ├── moving_average.py          # 均线因子（SMA、EMA、距离）
│   ├── cycle.py                   # 周期因子（希尔伯特变换、主导周期）
│   ├── pattern_recognition.py     # 形态识别（K线形态、图表模式）
│   ├── advanced.py                # 高级因子（分形维度、混沌理论、小波变换）
│   ├── fundamental.py             # 基本面因子（PE、PB、ROE、增长率）
│   └── other.py                   # 其他因子（β、相关性、信息系数）
│
├── analysis/                 (5)  # 因子分析
│   ├── __init__.py
│   ├── ic_analyzer.py             # IC 分析（信息系数、ICIR、IC 衰减）
│   ├── layering_backtest.py       # 分层回测（十分位组合、多空收益）
│   ├── orthogonalizer.py          # 因子正交化（施密特正交、PCA）
│   └── factor_monitor.py          # 因子监控（有效性跟踪、降维）
│
├── models/                   (6)  # 多因子模型
│   ├── __init__.py
│   ├── barra.py                   # BARRA 风险模型（CNE5、CNE6）
│   ├── fama_french.py             # Fama-French 三因子/五因子模型
│   ├── carhart.py                 # Carhart 四因子模型（加动量因子）
│   ├── factor_exposure.py         # 因子暴露计算
│   └── examples.py                # 使用示例
│
└── alternative/              (2)  # 另类因子
    ├── __init__.py
    └── sentiment_factors.py       # 情绪因子（社交媒体、新闻情绪）
```

---

## 快速开始

### 1. 计算单个因子

```python
from domain.factors.library.momentum import MomentumFactors

# 创建因子计算器
calculator = MomentumFactors()

# 计算相对强弱指标（RS）
rs = calculator.calculate_rs(
    prices=stock_prices,
    periods=[5, 10, 20, 60]  # 多周期
)

# 计算 MACD
macd = calculator.calculate_macd(
    prices=stock_prices,
    fast_period=12,
    slow_period=26,
    signal_period=9
)

# 结果是 DataFrame，可以直接使用
print(rs.head())
```

### 2. 批量计算多个因子

```python
from domain.factors.library import (
    MomentumFactors,
    VolatilityFactors,
    VolumeFactors
)

# 创建多个因子计算器
momentum = MomentumFactors()
volatility = VolatilityFactors()
volume = VolumeFactors()

# 批量计算
factors = {}
factors['momentum_20'] = momentum.calculate_rs(prices, periods=[20])
factors['volatility'] = volatility.calculate_atr(prices, period=14)
factors['volume_obv'] = volume.calculate_obv(prices, volumes)

# 合并为因子矩阵
import pandas as pd
factor_matrix = pd.concat(factors, axis=1)
```

### 3. IC 分析

```python
from domain.factors.analysis.ic_analyzer import ICAnalyzer

# 创建 IC 分析器
analyzer = ICAnalyzer()

# 计算因子 IC（信息系数）
ic_result = analyzer.calculate_ic(
    factor_values=factor_matrix,
    forward_returns=future_returns,
    method='rank'  # 'rank' 或 'normal'
)

print(f"平均 IC: {ic_result.mean_ic:.4f}")
print(f"IC IR: {ic_result.ic_ir:.4f}")
print(f"IC 胜率: {ic_result.win_rate:.2%}")

# IC 时序图
analyzer.plot_ic_series(ic_result)
```

### 4. 分层回测

```python
from domain.factors.analysis.layering_backtest import LayeringBacktest

# 创建分层回测
backtest = LayeringBacktest(n_quantiles=10)

# 执行分层回测
result = backtest.run(
    factor_values=factor_matrix['momentum_20'],
    prices=stock_prices,
    start_date='2023-01-01',
    end_date='2023-12-31'
)

# 查看结果
print("各分位组合收益率:")
print(result.quantile_returns)
print(f"\n多空收益: {result.long_short_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
```

### 5. 因子正交化

```python
from domain.factors.analysis.orthogonalizer import Orthogonalizer

# 创建正交化器
ortho = Orthogonalizer(method='schmidt')

# 对因子进行正交化（去除共线性）
orthogonal_factors = ortho.orthogonalize(
    factors=factor_matrix,
    base_factors=['market_beta', 'size']  # 基准因子
)

# 检查相关性矩阵
correlation = orthogonal_factors.corr()
print("正交化后的因子相关性:")
print(correlation)
```

### 6. 使用多因子模型

```python
from domain.factors.models.fama_french import FamaFrenchModel

# 创建 Fama-French 三因子模型
model = FamaFrenchModel(n_factors=3)

# 拟合模型
model.fit(
    returns=stock_returns,
    market_returns=market_returns,
    risk_free_rate=rf_rate
)

# 获取因子暴露
exposures = model.get_exposures()
print("因子暴露:")
print(exposures)

# 因子收益归因
attribution = model.attribute_returns(portfolio_returns)
print("\n收益归因:")
print(f"市场因子贡献: {attribution['market']:.2%}")
print(f"规模因子贡献: {attribution['size']:.2%}")
print(f"价值因子贡献: {attribution['value']:.2%}")
```

---

## 因子库详解

### 动量因子 (momentum.py)

**定义**: 衡量价格趋势的延续性

**包含因子**:
- `calculate_rs()` - 相对强弱指标（Relative Strength）
- `calculate_macd()` - MACD（Moving Average Convergence Divergence）
- `calculate_williams_r()` - 威廉 %R
- `calculate_roc()` - 变化率（Rate of Change）

**使用场景**: 趋势跟踪、动量策略

---

### 趋势因子 (trend.py)

**定义**: 识别价格趋势的方向和强度

**包含因子**:
- `calculate_adx()` - ADX 趋势强度指标
- `calculate_parabolic_sar()` - 抛物线 SAR
- `calculate_directional_indicators()` - +DI / -DI
- `calculate_aroon()` - 阿隆指标

**使用场景**: 趋势判断、入场时机选择

---

### 波动率因子 (volatility.py)

**定义**: 衡量价格波动的剧烈程度

**包含因子**:
- `calculate_atr()` - 平均真实波幅（Average True Range）
- `calculate_bollinger_bandwidth()` - 布林带宽度
- `calculate_historical_volatility()` - 历史波动率
- `calculate_parkinson()` - Parkinson 波动率估计

**使用场景**: 风险管理、止损设置、期权定价

---

### 成交量因子 (volume.py)

**定义**: 结合成交量的价格行为分析

**包含因子**:
- `calculate_obv()` - 能量潮（On-Balance Volume）
- `calculate_cmf()` - 资金流量指标（Chaikin Money Flow）
- `calculate_vwap()` - 成交量加权平均价
- `calculate_volume_ratio()` - 量比

**使用场景**: 验证价格趋势、判断买卖力量

---

### 反转因子 (reversal.py)

**定义**: 识别价格反转信号

**包含因子**:
- `calculate_rsi()` - 相对强弱指数（RSI）
- `calculate_stochastic()` - 随机指标（KDJ）
- `calculate_cci()` - 顺势指标（CCI）
- `calculate_mfi()` - 资金流量指数（MFI）

**使用场景**: 超买超卖判断、反转交易

---

### 均线因子 (moving_average.py)

**定义**: 基于移动平均线的因子

**包含因子**:
- `calculate_sma()` - 简单移动平均
- `calculate_ema()` - 指数移动平均
- `calculate_distance_from_ma()` - 与均线的距离
- `calculate_ma_cross()` - 均线交叉信号

**使用场景**: 趋势跟踪、支撑阻力

---

### 基本面因子 (fundamental.py)

**定义**: 基于财务数据的基本面因子

**包含因子**:
- `calculate_pe_ratio()` - 市盈率
- `calculate_pb_ratio()` - 市净率
- `calculate_roe()` - 净资产收益率
- `calculate_growth_rate()` - 增长率（收入/利润）

**使用场景**: 价值投资、基本面选股

---

### 高级因子 (advanced.py)

**定义**: 基于复杂数学理论的因子

**包含因子**:
- `calculate_fractal_dimension()` - 分形维度
- `calculate_hurst_exponent()` - 赫斯特指数
- `calculate_wavelet_transform()` - 小波变换
- `calculate_entropy()` - 信息熵

**使用场景**: 市场微观结构研究、高频交易

---

## 因子分析工具

### IC 分析（信息系数）

**定义**: 因子预测能力的度量

```python
from domain.factors.analysis.ic_analyzer import ICAnalyzer

analyzer = ICAnalyzer()

# 计算 IC
ic = analyzer.calculate_ic(factor, returns)

# 关键指标
ic.mean_ic      # 平均 IC（越大越好，>0.05 有效）
ic.ic_ir        # IC IR（信息比率，>0.5 较好）
ic.win_rate     # IC 胜率（>50% 稳定）
ic.decay        # IC 衰减（衰减慢说明持续性好）
```

**判断标准**:
- Mean IC > 0.05: 因子有效
- IC IR > 0.5: 因子稳定
- Win Rate > 50%: 预测一致性好

---

### 分层回测

**定义**: 按因子值分组，验证单调性

```python
from domain.factors.analysis.layering_backtest import LayeringBacktest

backtest = LayeringBacktest(n_quantiles=10)
result = backtest.run(factor, prices)

# 检查单调性
result.plot_quantile_returns()  # 应呈现单调递增/递减

# 多空收益
result.long_short_return  # Q10 - Q1 的收益差
```

**理想结果**: 
- 分位组合收益呈现单调性
- 多空收益显著 (>10% 年化)
- 夏普比率 > 1.0

---

### 因子正交化

**目的**: 去除因子间的共线性

```python
from domain.factors.analysis.orthogonalizer import Orthogonalizer

# 施密特正交化
ortho = Orthogonalizer(method='schmidt')
orth_factors = ortho.orthogonalize(factors, base=['market_beta'])

# PCA 降维
ortho = Orthogonalizer(method='pca')
pca_factors = ortho.orthogonalize(factors, n_components=5)
```

**使用场景**:
- 多因子模型构建前
- 避免因子冗余
- 提高模型稳定性

---

## 多因子模型

### Fama-French 模型

**三因子**: Market（市场）、SMB（规模）、HML（价值）
**五因子**: 三因子 + RMW（盈利）+ CMA（投资）

```python
from domain.factors.models.fama_french import FamaFrenchModel

# 三因子模型
model = FamaFrenchModel(n_factors=3)
model.fit(returns, market_returns, rf_rate)

# 因子收益
factor_returns = model.get_factor_returns()

# 归因分析
attribution = model.attribute_returns(portfolio_returns)
```

---

### BARRA 模型

**因子类型**: 风格因子 + 行业因子

```python
from domain.factors.models.barra import BARRAModel

# CNE6 模型（中国 A 股）
model = BARRAModel(model_type='CNE6')
model.fit(returns, factor_exposures)

# 风险分解
risk_decomp = model.decompose_risk(portfolio)
print(f"因子风险: {risk_decomp.factor_risk}")
print(f"特质风险: {risk_decomp.specific_risk}")
```

---

### Carhart 四因子

**因子**: Market + SMB + HML + MOM（动量）

```python
from domain.factors.models.carhart import CarhartModel

model = CarhartModel()
model.fit(returns, market_returns, rf_rate)

# Alpha 计算
alpha = model.calculate_alpha(portfolio_returns)
print(f"Four-Factor Alpha: {alpha:.4f}")
```

---

## 因子开发流程

```
1. 因子设计
   ├── 提出因子假设
   ├── 数学公式定义
   └── 实现计算函数

2. 因子验证
   ├── IC 分析（预测能力）
   ├── 分层回测（单调性）
   ├── 相关性检查（冗余度）
   └── 稳定性测试（时间窗口）

3. 因子优化
   ├── 参数调优
   ├── 正交化处理
   └── 组合因子

4. 生产部署
   ├── 性能优化
   ├── 实时计算
   └── 监控预警
```

---

## 最佳实践

### 1. 因子标准化

```python
# Z-Score 标准化
factor_std = (factor - factor.mean()) / factor.std()

# 排序标准化（推荐）
factor_rank = factor.rank(pct=True)  # 0-1 区间
```

### 2. 极值处理

```python
# MAD 去极值（推荐）
median = factor.median()
mad = (factor - median).abs().median()
factor_winsorized = factor.clip(
    lower=median - 3*mad,
    upper=median + 3*mad
)
```

### 3. 缺失值处理

```python
# 前向填充（适合日度数据）
factor_filled = factor.fillna(method='ffill', limit=5)

# 行业中位数填充
factor_filled = factor.groupby('industry').transform(
    lambda x: x.fillna(x.median())
)
```

### 4. 因子合成

```python
# 等权合成
composite = (factor1 + factor2 + factor3) / 3

# IC 加权合成
ic_weights = calculate_ic_weights([factor1, factor2, factor3])
composite = sum(f * w for f, w in zip(factors, ic_weights))

# 秩相关合成（推荐）
composite = (factor1.rank() + factor2.rank() + factor3.rank()).rank()
```

---

## 性能优化

### 向量化计算

```python
# ❌ 慢：循环计算
for i in range(len(data)):
    result[i] = (data[i] - data[i-20:i].mean()) / data[i-20:i].std()

# ✅ 快：向量化
result = (data - data.rolling(20).mean()) / data.rolling(20).std()
```

### 批量计算

```python
# 一次性计算多个周期
periods = [5, 10, 20, 60, 120]
momentum_factors = {
    f'momentum_{p}': calculate_momentum(prices, period=p)
    for p in periods
}
```

---

## 测试

```bash
# 运行因子领域测试
pytest tests/domain/factors/ -v

# 测试特定因子
pytest tests/domain/factors/test_momentum_factors.py -v

# IC 分析测试
pytest tests/domain/factors/test_ic_analyzer.py -v
```

---

## 相关文档

- [QuantLib 技术计算库](../quantlib/README.md)
- [回测领域](../backtest/README.md)
- [风险领域](../risk/README.md)

---

## 贡献指南

### 添加新因子

1. 在 `library/` 对应文件中实现
2. 继承 `TechnicalFactorCalculator` 基类
3. 编写单元测试（包含 IC 测试）
4. 更新本文档

### 添加新模型

1. 在 `models/` 中创建新文件
2. 实现 `fit()` 和 `predict()` 方法
3. 添加归因分析接口
4. 编写使用示例

---

**维护者**: QuantSys V2 Team  
**最后更新**: 2026-08-23  
**版本**: v2.0 (quantlib 重构后)
