# 统计分析模块文档

**模块**: `quant.statistics`  
**版本**: v2.3.0  
**创建日期**: 2026-05-24

---

## 📋 目录

1. [概述](#概述)
2. [安装与导入](#安装与导入)
3. [核心功能](#核心功能)
4. [API 参考](#api-参考)
5. [使用示例](#使用示例)
6. [最佳实践](#最佳实践)
7. [性能考虑](#性能考虑)

---

## 概述

统计分析模块提供了一套完整的统计推断工具，包括：

- **Bootstrap 重采样** - 估计统计量的抽样分布
- **假设检验** - t检验、Mann-Whitney U检验
- **置信区间** - 参数和非参数方法
- **正态性检验** - Shapiro-Wilk检验

所有功能都继承自 `BaseCalculator`，提供统一的接口和错误处理。

---

## 安装与导入

### 依赖

```bash
pip install numpy scipy pandas
```

### 导入

```python
from quant.statistics import StatisticalAnalyzer
```

---

## 核心功能

### 1. Bootstrap 重采样

Bootstrap 是一种重采样技术，用于估计统计量的抽样分布和置信区间。

**支持的统计量**:
- `mean` - 均值
- `median` - 中位数
- `std` - 标准差
- `sharpe` - 夏普比率

**方法**: `bootstrap_resample()`

### 2. 假设检验

#### 参数检验
- **单样本 t检验** - 检验样本均值是否等于某个值
- **双样本 t检验** - 比较两个样本的均值
- **配对 t检验** - 比较配对样本的差异

#### 非参数检验
- **Mann-Whitney U检验** - 非参数版本的双样本t检验
- **Wilcoxon检验** - 非参数版本的配对t检验

### 3. 正态性检验

- **Shapiro-Wilk检验** - 检验数据是否服从正态分布

### 4. 置信区间

- **t分布方法** - 基于t分布的置信区间
- **Bootstrap方法** - 基于Bootstrap的置信区间

---

## API 参考

### StatisticalAnalyzer

```python
class StatisticalAnalyzer(BaseCalculator):
    """统计分析计算器"""
```

---

### bootstrap_resample()

执行Bootstrap重采样以估计统计量的抽样分布。

```python
def bootstrap_resample(
    data: Union[List, np.ndarray, pd.Series],
    statistic: Literal['mean', 'median', 'std', 'sharpe'] = 'mean',
    n_iterations: int = 10000,
    confidence_level: float = 0.95,
    random_seed: Optional[int] = None
) -> Dict
```

**参数**:
- `data`: 样本数据
- `statistic`: 要计算的统计量
- `n_iterations`: Bootstrap迭代次数（至少100）
- `confidence_level`: 置信水平（0-1）
- `random_seed`: 随机种子（可选）

**返回**:
```python
{
    'value': {
        'statistic': 0.123,           # 原始统计量
        'confidence_interval': [0.1, 0.15],  # 置信区间
        'standard_error': 0.012       # 标准误
    },
    'metadata': {
        'bootstrap_distribution': [...],  # Bootstrap分布
        'bootstrap_mean': 0.124,
        'bootstrap_std': 0.012,
        'bias': 0.001                 # 偏差
    }
}
```

**示例**:
```python
analyzer = StatisticalAnalyzer()

# Bootstrap均值
result = analyzer.bootstrap_resample(
    returns,
    statistic='mean',
    n_iterations=10000,
    confidence_level=0.95,
    random_seed=42
)

print(f"Mean: {result['value']['statistic']:.4f}")
print(f"95% CI: {result['value']['confidence_interval']}")
print(f"SE: {result['value']['standard_error']:.4f}")
```

---

### t_test()

执行t检验（单样本或双样本）。

```python
def t_test(
    sample1: Union[List, np.ndarray, pd.Series],
    sample2: Optional[Union[List, np.ndarray, pd.Series]] = None,
    mu: float = 0.0,
    alternative: Literal['two-sided', 'less', 'greater'] = 'two-sided'
) -> Dict
```

**参数**:
- `sample1`: 第一个样本
- `sample2`: 第二个样本（None表示单样本检验）
- `mu`: 假设的均值（单样本检验）
- `alternative`: 备择假设
  - `'two-sided'`: μ ≠ μ₀
  - `'less'`: μ < μ₀
  - `'greater'`: μ > μ₀

**返回**:
```python
{
    'value': {
        't_statistic': 2.345,
        'p_value': 0.023,
        'degrees_of_freedom': 48
    },
    'metadata': {
        'is_significant': True,       # p < 0.05
        'alpha': 0.05,
        'effect_size': 0.67,          # Cohen's d
        'interpretation': 'medium',   # 效应量解释
        'sample1_mean': 5.2,
        'sample2_mean': 4.8
    }
}
```

**示例**:
```python
# 单样本t检验
result = analyzer.t_test(returns, mu=0.0)
print(f"t = {result['value']['t_statistic']:.3f}")
print(f"p = {result['value']['p_value']:.4f}")

# 双样本t检验
result = analyzer.t_test(strategy_a_returns, strategy_b_returns)
print(f"Effect size: {result['metadata']['effect_size']:.3f}")
print(f"Interpretation: {result['metadata']['interpretation']}")
```

---

### paired_t_test()

执行配对t检验。

```python
def paired_t_test(
    before: Union[List, np.ndarray, pd.Series],
    after: Union[List, np.ndarray, pd.Series],
    alternative: Literal['two-sided', 'less', 'greater'] = 'two-sided'
) -> Dict
```

**参数**:
- `before`: 处理前的测量值
- `after`: 处理后的测量值
- `alternative`: 备择假设

**返回**: 与 `t_test()` 类似，额外包含：
```python
{
    'metadata': {
        'mean_difference': 0.5,       # 平均差异
        'std_difference': 0.2,        # 差异标准差
        'before_mean': 10.0,
        'after_mean': 10.5
    }
}
```

**示例**:
```python
# 比较策略调整前后的表现
result = analyzer.paired_t_test(
    returns_before_adjustment,
    returns_after_adjustment,
    alternative='greater'  # 检验是否改进
)

if result['metadata']['is_significant']:
    print(f"策略调整显著改进了表现")
    print(f"平均改进: {result['metadata']['mean_difference']:.4f}")
```

---

### mann_whitney_test()

执行Mann-Whitney U检验（非参数检验）。

```python
def mann_whitney_test(
    sample1: Union[List, np.ndarray, pd.Series],
    sample2: Union[List, np.ndarray, pd.Series],
    alternative: Literal['two-sided', 'less', 'greater'] = 'two-sided'
) -> Dict
```

**参数**:
- `sample1`: 第一个样本
- `sample2`: 第二个样本
- `alternative`: 备择假设

**返回**:
```python
{
    'value': {
        'u_statistic': 450.0,
        'p_value': 0.034
    },
    'metadata': {
        'is_significant': True,
        'effect_size': 0.23,          # 秩双列相关
        'sample1_median': 5.1,
        'sample2_median': 4.7,
        'test_type': 'non_parametric'
    }
}
```

**何时使用**:
- 数据不满足正态性假设
- 存在异常值
- 样本量较小

**示例**:
```python
# 检验正态性
normality = analyzer.shapiro_test(returns)

if not normality['metadata']['is_normal']:
    # 使用非参数检验
    result = analyzer.mann_whitney_test(strategy_a, strategy_b)
else:
    # 使用参数检验
    result = analyzer.t_test(strategy_a, strategy_b)
```

---

### shapiro_test()

执行Shapiro-Wilk正态性检验。

```python
def shapiro_test(
    data: Union[List, np.ndarray, pd.Series]
) -> Dict
```

**参数**:
- `data`: 样本数据

**返回**:
```python
{
    'value': {
        'w_statistic': 0.987,
        'p_value': 0.234
    },
    'metadata': {
        'is_normal': True,            # p > 0.05
        'alpha': 0.05,
        'conclusion': 'normal',
        'recommendation': '数据呈正态分布。参数检验（t检验）是合适的。'
    }
}
```

**示例**:
```python
result = analyzer.shapiro_test(returns)

if result['metadata']['is_normal']:
    print("数据呈正态分布")
    print(result['metadata']['recommendation'])
else:
    print("数据可能不呈正态分布")
    print(result['metadata']['recommendation'])
```

---

### calculate_confidence_interval()

计算均值的置信区间。

```python
def calculate_confidence_interval(
    data: Union[List, np.ndarray, pd.Series],
    confidence_level: float = 0.95,
    method: Literal['t', 'bootstrap'] = 't'
) -> Dict
```

**参数**:
- `data`: 样本数据
- `confidence_level`: 置信水平（0-1）
- `method`: 方法
  - `'t'`: t分布方法（假设正态性）
  - `'bootstrap'`: Bootstrap方法（无分布假设）

**返回**:
```python
{
    'value': {
        'mean': 0.05,
        'confidence_interval': [0.03, 0.07],
        'margin_of_error': 0.02
    },
    'metadata': {
        'standard_error': 0.01,
        'standard_deviation': 0.15,
        'interval_width': 0.04
    }
}
```

**示例**:
```python
# t分布方法（快速）
result_t = analyzer.calculate_confidence_interval(
    returns,
    confidence_level=0.95,
    method='t'
)

# Bootstrap方法（更稳健）
result_boot = analyzer.calculate_confidence_interval(
    returns,
    confidence_level=0.95,
    method='bootstrap'
)

print(f"Mean: {result_t['value']['mean']:.4f}")
print(f"95% CI (t): {result_t['value']['confidence_interval']}")
print(f"95% CI (boot): {result_boot['value']['confidence_interval']}")
```

---

## 使用示例

### 示例 1: 策略回报率分析

```python
import numpy as np
from quant.statistics import StatisticalAnalyzer

# 模拟策略回报率
np.random.seed(42)
strategy_returns = np.random.randn(252) * 0.02 + 0.001  # 日回报率

analyzer = StatisticalAnalyzer()

# 1. 检验回报率是否显著大于0
t_test_result = analyzer.t_test(
    strategy_returns,
    mu=0.0,
    alternative='greater'
)

print(f"策略回报率是否显著 > 0: {t_test_result['metadata']['is_significant']}")
print(f"p-value: {t_test_result['value']['p_value']:.4f}")

# 2. 计算回报率的置信区间
ci_result = analyzer.calculate_confidence_interval(
    strategy_returns,
    confidence_level=0.95,
    method='bootstrap'
)

print(f"平均日回报率: {ci_result['value']['mean']:.4f}")
print(f"95% 置信区间: {ci_result['value']['confidence_interval']}")

# 3. Bootstrap夏普比率
sharpe_result = analyzer.bootstrap_resample(
    strategy_returns,
    statistic='sharpe',
    n_iterations=10000,
    confidence_level=0.95
)

print(f"夏普比率: {sharpe_result['value']['statistic']:.3f}")
print(f"95% CI: {sharpe_result['value']['confidence_interval']}")
```

---

### 示例 2: 比较两个策略

```python
# 两个策略的回报率
strategy_a = np.random.randn(200) * 0.02 + 0.0015
strategy_b = np.random.randn(200) * 0.02 + 0.0010

analyzer = StatisticalAnalyzer()

# 1. 检验正态性
norm_a = analyzer.shapiro_test(strategy_a)
norm_b = analyzer.shapiro_test(strategy_b)

print(f"策略A正态性: {norm_a['metadata']['is_normal']}")
print(f"策略B正态性: {norm_b['metadata']['is_normal']}")

# 2. 选择合适的检验
if norm_a['metadata']['is_normal'] and norm_b['metadata']['is_normal']:
    # 参数检验
    result = analyzer.t_test(strategy_a, strategy_b, alternative='two-sided')
    test_name = "t检验"
else:
    # 非参数检验
    result = analyzer.mann_whitney_test(strategy_a, strategy_b, alternative='two-sided')
    test_name = "Mann-Whitney U检验"

print(f"\n{test_name}结果:")
print(f"p-value: {result['value']['p_value']:.4f}")
print(f"显著差异: {result['metadata']['is_significant']}")
print(f"效应量: {result['metadata']['effect_size']:.3f}")
print(f"解释: {result['metadata']['interpretation']}")
```

---

### 示例 3: 策略调整前后对比

```python
# 策略调整前后的回报率（配对数据）
before = np.random.randn(100) * 0.02 + 0.0008
after = before + np.random.randn(100) * 0.005 + 0.0005  # 略有改进

analyzer = StatisticalAnalyzer()

# 配对t检验
result = analyzer.paired_t_test(
    before,
    after,
    alternative='less'  # 检验 before < after
)

print(f"策略调整是否显著改进: {result['metadata']['is_significant']}")
print(f"平均改进: {result['metadata']['mean_difference']:.6f}")
print(f"效应量: {result['metadata']['effect_size']:.3f}")
print(f"解释: {result['metadata']['interpretation']}")

# 可视化差异
differences = after - before
print(f"\n差异统计:")
print(f"  均值: {np.mean(differences):.6f}")
print(f"  中位数: {np.median(differences):.6f}")
print(f"  标准差: {np.std(differences):.6f}")
```

---

### 示例 4: 风险指标的置信区间

```python
# 计算多个风险指标的置信区间
returns = np.random.randn(252) * 0.02 + 0.001

analyzer = StatisticalAnalyzer()

# 均值
mean_ci = analyzer.calculate_confidence_interval(returns, method='bootstrap')

# 标准差
std_result = analyzer.bootstrap_resample(
    returns,
    statistic='std',
    n_iterations=10000
)

# 夏普比率
sharpe_result = analyzer.bootstrap_resample(
    returns,
    statistic='sharpe',
    n_iterations=10000
)

print("风险指标 (95% 置信区间):")
print(f"均值: {mean_ci['value']['mean']:.4f} {mean_ci['value']['confidence_interval']}")
print(f"标准差: {std_result['value']['statistic']:.4f} {std_result['value']['confidence_interval']}")
print(f"夏普比率: {sharpe_result['value']['statistic']:.3f} {sharpe_result['value']['confidence_interval']}")
```

---

## 最佳实践

### 1. 选择合适的检验

```python
# 决策树
def choose_test(data1, data2=None):
    analyzer = StatisticalAnalyzer()
    
    # 检验正态性
    norm1 = analyzer.shapiro_test(data1)
    is_normal = norm1['metadata']['is_normal']
    
    if data2 is not None:
        norm2 = analyzer.shapiro_test(data2)
        is_normal = is_normal and norm2['metadata']['is_normal']
    
    if is_normal:
        return 't_test'  # 参数检验
    else:
        return 'mann_whitney_test'  # 非参数检验
```

### 2. 报告完整结果

```python
def report_test_results(result, test_name):
    """报告检验结果"""
    print(f"\n{test_name}结果:")
    print(f"  统计量: {list(result['value'].values())[0]:.4f}")
    print(f"  p-value: {result['value']['p_value']:.4f}")
    print(f"  显著性: {'是' if result['metadata']['is_significant'] else '否'}")
    
    if 'effect_size' in result['metadata']:
        print(f"  效应量: {result['metadata']['effect_size']:.3f}")
        print(f"  解释: {result['metadata']['interpretation']}")
```

### 3. 使用Bootstrap进行稳健估计

```python
# 对于非正态数据或小样本，使用Bootstrap
if len(data) < 30 or not is_normal:
    # Bootstrap置信区间
    ci_result = analyzer.calculate_confidence_interval(
        data,
        method='bootstrap'
    )
else:
    # t分布置信区间（更快）
    ci_result = analyzer.calculate_confidence_interval(
        data,
        method='t'
    )
```

### 4. 多重比较校正

```python
# 当进行多次检验时，调整显著性水平
n_tests = 5
alpha_adjusted = 0.05 / n_tests  # Bonferroni校正

for i, (data1, data2) in enumerate(test_pairs):
    result = analyzer.t_test(data1, data2)
    is_significant = result['value']['p_value'] < alpha_adjusted
    print(f"Test {i+1}: p={result['value']['p_value']:.4f}, "
          f"significant={is_significant}")
```

---

## 性能考虑

### Bootstrap迭代次数

| 迭代次数 | 精度 | 执行时间 (100点) |
|---------|------|-----------------|
| 1,000 | 低 | ~5ms |
| 10,000 | 中 | ~50ms |
| 100,000 | 高 | ~500ms |

**建议**:
- 探索性分析: 1,000-5,000次
- 最终报告: 10,000次
- 发表论文: 100,000次

### 样本量要求

| 检验 | 最小样本量 | 推荐样本量 |
|------|-----------|-----------|
| t检验 | 3 | 30+ |
| Mann-Whitney | 3 | 20+ |
| Shapiro-Wilk | 3 | 20-5000 |
| Bootstrap | 10 | 50+ |

### 内存使用

```python
# Bootstrap会存储所有迭代结果
n_iterations = 10000
data_size = 1000
memory_mb = (n_iterations * data_size * 8) / (1024 * 1024)
# ≈ 76 MB

# 如果内存受限，减少迭代次数或不保存分布
```

---

## 常见问题

### Q1: 何时使用参数检验 vs 非参数检验？

**参数检验** (t检验):
- ✅ 数据呈正态分布
- ✅ 样本量较大 (n > 30)
- ✅ 更高的统计功效

**非参数检验** (Mann-Whitney):
- ✅ 数据不呈正态分布
- ✅ 存在异常值
- ✅ 样本量较小
- ✅ 更稳健

### Q2: Bootstrap vs t分布置信区间？

**Bootstrap**:
- ✅ 无分布假设
- ✅ 适用于任何统计量
- ⚠️ 计算密集

**t分布**:
- ✅ 快速
- ✅ 理论基础
- ⚠️ 假设正态性

### Q3: 如何解释效应量？

**Cohen's d**:
- < 0.2: 可忽略
- 0.2-0.5: 小
- 0.5-0.8: 中
- > 0.8: 大

---

## 参考资料

- Efron, B., & Tibshirani, R. J. (1994). *An Introduction to the Bootstrap*
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences*
- Wilcox, R. R. (2012). *Introduction to Robust Estimation and Hypothesis Testing*

---

**文档版本**: 1.0  
**最后更新**: 2026-05-24  
**作者**: Claude (Kiro)
