# 时间序列扩展模块文档

## 概述

时间序列扩展模块为 QuantSys V2 提供了高级时间序列建模和预测功能，包括 ARIMA、GARCH、VAR 模型以及协整检验。

**版本**: v2.4.0  
**创建日期**: 2024  
**模块路径**: `quantsys-v2/quant/timeseries/__init__.py`

## 新增功能

### 1. ARIMA 模型 (自回归移动平均模型)

ARIMA 模型用于时间序列预测，适用于具有趋势和季节性的数据。

#### 方法

##### `fit_arima(data, order=(1,1,1), seasonal_order=None, auto_select=False)`

拟合 ARIMA 模型到时间序列数据。

**参数**:
- `data` (array-like): 时间序列数据
- `order` (tuple): ARIMA 阶数 (p, d, q)
  - p: 自回归项数
  - d: 差分阶数
  - q: 移动平均项数
- `seasonal_order` (tuple, optional): 季节性 ARIMA 阶数 (P, D, Q, s)
- `auto_select` (bool): 是否自动选择最优阶数 (默认 False)

**返回**:
- `CalculationResult`: 包含拟合模型、参数、AIC/BIC、残差诊断

**示例**:
```python
from quant.timeseries import TimeSeriesAnalyzer

analyzer = TimeSeriesAnalyzer()

# 基础 ARIMA 模型
result = analyzer.fit_arima(data, order=(1, 1, 1))
print(f"AIC: {result.metadata['aic']}")
print(f"BIC: {result.metadata['bic']}")
print(f"Parameters: {result.value['parameters']}")

# 季节性 ARIMA 模型
result = analyzer.fit_arima(
    data, 
    order=(1, 1, 1),
    seasonal_order=(1, 1, 1, 12)  # 12个月季节性
)
```

##### `predict_arima(fitted_model, steps=10, confidence_level=0.95)`

使用拟合的 ARIMA 模型进行预测。

**参数**:
- `fitted_model`: 拟合的 ARIMA 模型对象
- `steps` (int): 预测步数
- `confidence_level` (float): 置信水平 (0-1)

**返回**:
- `CalculationResult`: 包含预测值、置信区间上下界

**示例**:
```python
# 拟合模型
fit_result = analyzer.fit_arima(data, order=(1, 1, 1))
fitted_model = fit_result.value['model']

# 预测未来10期
pred_result = analyzer.predict_arima(fitted_model, steps=10)
print(f"Forecast: {pred_result.value['forecast']}")
print(f"Lower bound: {pred_result.value['lower_bound']}")
print(f"Upper bound: {pred_result.value['upper_bound']}")
```

---

### 2. GARCH 模型 (广义自回归条件异方差模型)

GARCH 模型用于建模和预测金融时间序列的波动率。

#### 方法

##### `fit_garch(returns, p=1, q=1)`

拟合 GARCH 模型到收益率序列。

**参数**:
- `returns` (array-like): 收益率序列 (百分比形式，如 0.01 表示 1%)
- `p` (int): GARCH 项数 (默认 1)
- `q` (int): ARCH 项数 (默认 1)

**返回**:
- `CalculationResult`: 包含拟合模型、参数、条件波动率、预测波动率

**示例**:
```python
# 计算收益率
returns = np.diff(np.log(prices)) * 100  # 对数收益率 (%)

# 拟合 GARCH(1,1) 模型
result = analyzer.fit_garch(returns, p=1, q=1)
print(f"Parameters: {result.value['parameters']}")
print(f"Conditional volatility: {result.value['conditional_volatility'][:5]}")
print(f"Forecast volatility: {result.value['forecast_volatility']}")

# 拟合 GARCH(2,2) 模型
result = analyzer.fit_garch(returns, p=2, q=2)
```

**注意事项**:
- 输入必须是收益率序列，不是价格序列
- 收益率应为百分比形式 (如 1% = 0.01)
- 至少需要 100 个数据点

---

### 3. VAR 模型 (向量自回归模型)

VAR 模型用于多变量时间序列分析，捕捉变量之间的动态关系。

#### 方法

##### `fit_var(data, maxlags=5, ic='aic')`

拟合 VAR 模型到多变量时间序列。

**参数**:
- `data` (array-like): 多变量时间序列数据 (n_samples, n_variables)
- `maxlags` (int): 最大滞后阶数 (默认 5)
- `ic` (str): 信息准则 ('aic', 'bic', 'hqic', 'fpe')

**返回**:
- `CalculationResult`: 包含拟合模型、最优滞后阶数、参数、Granger 因果检验

**示例**:
```python
# 准备多变量数据 (例如：股票A和股票B的收益率)
data = np.column_stack([returns_A, returns_B])

# 拟合 VAR 模型
result = analyzer.fit_var(data, maxlags=5, ic='aic')
print(f"Optimal lags: {result.value['optimal_lags']}")
print(f"Parameters: {result.value['parameters']}")

# Granger 因果检验
granger = result.metadata['granger_causality']
print(f"Granger causality test: {granger}")
```

**注意事项**:
- 至少需要 2 个变量
- 数据应为平稳序列或已差分
- 至少需要 50 个数据点

---

### 4. 协整检验

协整检验用于检测两个非平稳时间序列之间是否存在长期均衡关系。

#### 方法

##### `cointegration_test(series1, series2, method='engle-granger')`

对两个时间序列进行协整检验。

**参数**:
- `series1` (array-like): 第一个时间序列
- `series2` (array-like): 第二个时间序列
- `method` (str): 检验方法 ('engle-granger' 或 'johansen')

**返回**:
- `CalculationResult`: 包含检验统计量、p值、临界值、是否协整

**示例**:
```python
# Engle-Granger 协整检验
result = analyzer.cointegration_test(price_A, price_B, method='engle-granger')
print(f"Cointegrated: {result.value['cointegrated']}")
print(f"Test statistic: {result.value['test_statistic']}")
print(f"P-value: {result.value['pvalue']}")
print(f"Critical values: {result.value['critical_values']}")

# Johansen 协整检验
result = analyzer.cointegration_test(price_A, price_B, method='johansen')
```

**应用场景**:
- 配对交易策略
- 统计套利
- 长期均衡关系分析

---

## 依赖项

时间序列扩展模块需要以下额外依赖：

```bash
pip install statsmodels arch
```

- `statsmodels`: ARIMA、VAR、协整检验
- `arch`: GARCH 模型

---

## 测试

模块包含 17 个单元测试，覆盖所有功能：

```bash
pytest tests/test_timeseries_extended.py -v
```

**测试覆盖**:
- ARIMA 模型拟合和预测
- GARCH 模型拟合
- VAR 模型拟合
- 协整检验
- 边界条件和错误处理

**测试结果**: ✅ 17 passed, 1 warning

---

## 最佳实践

### 1. ARIMA 模型选择

```python
# 方法1: 手动指定阶数
result = analyzer.fit_arima(data, order=(1, 1, 1))

# 方法2: 自动选择最优阶数 (需要更长时间)
result = analyzer.fit_arima(data, auto_select=True)

# 检查模型质量
print(f"AIC: {result.metadata['aic']}")  # 越小越好
print(f"BIC: {result.metadata['bic']}")  # 越小越好
print(f"Ljung-Box p-value: {result.metadata['ljung_box_pvalue']}")  # >0.05 表示残差无自相关
```

### 2. GARCH 波动率预测

```python
# 计算对数收益率
log_returns = np.diff(np.log(prices)) * 100

# 拟合 GARCH 模型
result = analyzer.fit_garch(log_returns, p=1, q=1)

# 获取条件波动率 (历史)
cond_vol = result.value['conditional_volatility']

# 获取预测波动率 (未来1期)
forecast_vol = result.value['forecast_volatility']

# 年化波动率 (假设日频数据)
annual_vol = forecast_vol * np.sqrt(252)
print(f"Annual volatility: {annual_vol:.2f}%")
```

### 3. VAR 模型和 Granger 因果

```python
# 准备多变量数据
data = np.column_stack([returns_A, returns_B, returns_C])

# 拟合 VAR 模型
result = analyzer.fit_var(data, maxlags=5, ic='aic')

# 检查 Granger 因果关系
# "变量 i 是否 Granger 导致变量 j"
granger = result.metadata['granger_causality']
for test in granger:
    print(f"{test['caused_by']} -> {test['variable']}: p-value = {test['pvalue']}")
```

### 4. 配对交易策略

```python
# 步骤1: 协整检验
coint_result = analyzer.cointegration_test(price_A, price_B)

if coint_result.value['cointegrated']:
    print("两个序列协整，可以进行配对交易")
    
    # 步骤2: 计算价差
    spread = price_A - coint_result.value['hedge_ratio'] * price_B
    
    # 步骤3: 对价差进行 ARIMA 建模
    arima_result = analyzer.fit_arima(spread, order=(1, 0, 1))
    
    # 步骤4: 预测价差
    pred_result = analyzer.predict_arima(arima_result.value['model'], steps=5)
    
    # 步骤5: 交易信号
    current_spread = spread[-1]
    predicted_spread = pred_result.value['forecast'][0]
    
    if current_spread > predicted_spread:
        print("做空价差: 卖出A，买入B")
    else:
        print("做多价差: 买入A，卖出B")
```

---

## 错误处理

所有方法都使用统一的异常处理框架：

- `DataValidationError`: 输入数据验证失败
- `InsufficientDataError`: 数据点不足
- `ModelFitError`: 模型拟合失败
- `CalculationError`: 计算错误

**示例**:
```python
from core.exceptions import ModelFitError, InsufficientDataError

try:
    result = analyzer.fit_arima(data, order=(1, 1, 1))
except InsufficientDataError as e:
    print(f"数据不足: {e}")
except ModelFitError as e:
    print(f"模型拟合失败: {e}")
```

---

## 性能考虑

- **ARIMA**: 拟合时间 O(n²)，适用于中等长度序列 (< 10,000 点)
- **GARCH**: 拟合时间 O(n)，适用于长序列
- **VAR**: 拟合时间 O(n·k²)，k 为变量数，适用于少量变量 (< 10)
- **协整检验**: 时间 O(n)，快速

**优化建议**:
- 对于长序列，考虑降采样或滚动窗口
- 使用 `auto_select=False` 手动指定 ARIMA 阶数
- 缓存拟合结果，避免重复计算

---

## 与现有模块的集成

时间序列扩展模块与现有模块无缝集成：

```python
# 与因子计算集成
from quant.engine.technical_factors import TechnicalFactors

factors = TechnicalFactors()
momentum = factors.calculate_momentum(prices)

# 对因子进行 ARIMA 预测
analyzer = TimeSeriesAnalyzer()
result = analyzer.fit_arima(momentum, order=(1, 1, 1))
forecast = analyzer.predict_arima(result.value['model'], steps=5)

# 与回测引擎集成
from quant.engine.backtest_engine import BacktestEngine

# 使用 GARCH 波动率进行动态仓位管理
garch_result = analyzer.fit_garch(returns)
volatility = garch_result.value['forecast_volatility']
position_size = 1.0 / volatility  # 波动率倒数加权
```

---

## 未来扩展

计划中的功能：

1. **ARIMAX**: 带外生变量的 ARIMA
2. **EGARCH**: 指数 GARCH (捕捉杠杆效应)
3. **状态空间模型**: Kalman 滤波
4. **小波分析**: 多尺度时间序列分解
5. **Prophet**: Facebook 时间序列预测库集成

---

## 参考资料

- [statsmodels ARIMA 文档](https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html)
- [arch GARCH 文档](https://arch.readthedocs.io/en/latest/univariate/univariate_volatility_modeling.html)
- [statsmodels VAR 文档](https://www.statsmodels.org/stable/vector_ar.html)
- [协整检验理论](https://en.wikipedia.org/wiki/Cointegration)

---

## 联系方式

如有问题或建议，请联系开发团队或提交 Issue。
