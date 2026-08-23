# Risk Domain - 风险管理

**领域职责**: 风险度量、归因分析、压力测试

---

## 概述

Risk 领域提供完整的风险管理基础设施，包括 VaR/CVaR 计算、风险归因、压力测试、极值理论、流动性风险等。

**核心能力**:
- ✅ VaR/CVaR 计算（历史模拟、参数法、蒙特卡洛）
- ✅ 风险归因（因子归因、风格归因）
- ✅ 压力测试与情景分析
- ✅ 极值理论（EVT）
- ✅ Copula 模型（相关性建模）
- ✅ 流动性风险、交易对手风险
- ✅ 监管指标（巴塞尔协议）

---

## 目录结构

```
risk/
├── __init__.py                    # 领域入口（空，避免循环导入）
├── var.py                         # VaR 计算
├── cvar.py                        # CVaR（条件风险价值）
├── attribution.py                 # 风险归因
├── drawdown.py                    # 回撤分析
├── market_risk.py                 # 市场风险
├── stress_test.py                 # 压力测试
├── stress_testing.py              # 压力测试框架
├── scenario_analysis.py           # 情景分析
├── backtesting.py                 # 回测验证（Basel II/III）
├── risk_monitor.py                # 风险监控
├── extreme_value.py               # 极值理论（EVT）
├── copula.py                      # Copula 模型
├── liquidity_risk.py              # 流动性风险
├── counterparty_risk.py           # 交易对手风险
├── regulatory.py                  # 监管指标
├── reporting.py                   # 风险报告
├── margining.py                   # 保证金管理
├── aggregation.py                 # 风险聚合
└── examples.py                    # 使用示例
```

**注意**: `__init__.py` 为空，用户需直接从子模块导入：

```python
# ✅ 正确
from domain.risk.var import VaRCalculator
from domain.risk.attribution import RiskAttributionCalculator

# ❌ 错误（会触发 AttributeError）
from domain.risk import VaRCalculator  # __init__ 未导出
```

---

## 快速开始

### 1. VaR 计算

```python
from domain.risk.var import VaRCalculator

# 创建 VaR 计算器
var_calc = VaRCalculator()

# 历史模拟法
var_historical = var_calc.calculate_historical_var(
    returns=portfolio_returns,
    confidence_level=0.95,
    horizon=1  # 1 日 VaR
)

# 参数法（假设正态分布）
var_parametric = var_calc.calculate_parametric_var(
    returns=portfolio_returns,
    confidence_level=0.95,
    horizon=1
)

# 蒙特卡洛模拟
var_mc = var_calc.calculate_monte_carlo_var(
    returns=portfolio_returns,
    confidence_level=0.95,
    horizon=1,
    n_simulations=10000
)

print(f"Historical VaR (95%): {var_historical:.2%}")
print(f"Parametric VaR (95%): {var_parametric:.2%}")
print(f"Monte Carlo VaR (95%): {var_mc:.2%}")
```

### 2. CVaR（条件风险价值）

```python
from domain.risk.cvar import CVaRCalculator

# 创建 CVaR 计算器
cvar_calc = CVaRCalculator()

# 计算 CVaR（超过 VaR 的平均损失）
cvar = cvar_calc.calculate_cvar(
    returns=portfolio_returns,
    confidence_level=0.95
)

# CVaR 比 VaR 更关注尾部风险
print(f"CVaR (95%): {cvar:.2%}")
print(f"VaR vs CVaR: CVaR 通常更大，衡量极端损失")
```

### 3. 风险归因

```python
from domain.risk.attribution import RiskAttributionCalculator

# 创建归因分析器
attribution = RiskAttributionCalculator()

# 因子归因
factor_attribution = attribution.factor_attribution(
    portfolio_returns=portfolio_returns,
    factor_returns=factor_returns,  # 市场、规模、价值等因子
    factor_exposures=exposures
)

print("因子贡献:")
for factor, contrib in factor_attribution.items():
    print(f"  {factor}: {contrib:.2%}")

# 风格归因
style_attribution = attribution.style_attribution(
    portfolio_returns=portfolio_returns,
    style_indices=style_indices  # 成长、价值、大盘、小盘
)
```

### 4. 压力测试

```python
from domain.risk.stress_test import StressTester

# 创建压力测试器
tester = StressTester()

# 历史情景（如 2008 金融危机）
crisis_scenario = tester.historical_scenario(
    portfolio=portfolio,
    scenario='2008_financial_crisis',
    start_date='2008-09-15',
    end_date='2009-03-09'
)

# 假设情景
hypothetical_scenario = tester.hypothetical_scenario(
    portfolio=portfolio,
    shocks={
        'market_index': -0.30,    # 市场下跌 30%
        'credit_spread': +0.05,   # 信用利差上升 500bp
        'vix': +0.50              # VIX 上升 50%
    }
)

print(f"2008 危机情景损失: {crisis_scenario.loss:.2%}")
print(f"假设情景损失: {hypothetical_scenario.loss:.2%}")
```

### 5. 回撤分析

```python
from domain.risk.drawdown import DrawdownAnalyzer

# 创建回撤分析器
analyzer = DrawdownAnalyzer()

# 计算最大回撤
max_drawdown = analyzer.calculate_max_drawdown(
    cumulative_returns=cumulative_returns
)

# 回撤持续期
drawdown_duration = analyzer.calculate_drawdown_duration(
    cumulative_returns=cumulative_returns
)

# 回撤序列
drawdown_series = analyzer.get_drawdown_series(
    cumulative_returns=cumulative_returns
)

print(f"最大回撤: {max_drawdown:.2%}")
print(f"回撤持续期: {drawdown_duration} 天")
```

---

## 核心模块详解

### VaR（风险价值）

**定义**: 在给定置信水平下，资产或投资组合在未来特定时间内的最大可能损失。

**三种方法**:

1. **历史模拟法**
   - 优点：不假设收益率分布
   - 缺点：依赖历史数据，无法捕捉新风险
   - 适用：数据充足、市场稳定时期

2. **参数法（方差-协方差法）**
   - 优点：计算快速，适合大组合
   - 缺点：假设正态分布，忽略尾部风险
   - 适用：线性产品、正态分布假设合理时

3. **蒙特卡洛模拟**
   - 优点：灵活，可模拟复杂产品
   - 缺点：计算量大
   - 适用：非线性产品、复杂衍生品

**巴塞尔协议标准**: 99% 置信水平，10 日 VaR

---

### CVaR（条件风险价值）

**定义**: 超过 VaR 的损失的平均值，也称 Expected Shortfall (ES)。

**优势**:
- 满足次可加性（Subadditivity），是一致性风险度量
- 更关注尾部风险
- 巴塞尔 III 推荐使用

**计算**:
```python
# CVaR 是超过 VaR 的条件期望
cvar = returns[returns <= var].mean()
```

---

### 风险归因

**因子归因**:
```
总风险² = Σ(因子暴露 × 因子风险)² + 特质风险²
```

**Brinson 归因**（主动管理）:
- 资产配置效应
- 证券选择效应
- 交互效应

**示例**:
```python
# 组合风险 = 市场风险 + 规模风险 + 价值风险 + 特质风险
total_risk = sqrt(
    beta_market² * sigma_market² +
    beta_size² * sigma_size² +
    beta_value² * sigma_value² +
    specific_risk²
)
```

---

### 压力测试

**历史情景**:
- 1987 黑色星期一
- 1998 俄罗斯债务危机
- 2008 全球金融危机
- 2020 新冠疫情

**假设情景**:
- 利率冲击（平移、扭曲、蝶式）
- 市场崩盘（-20%、-30%、-50%）
- 信用危机（信用利差扩大）
- 流动性枯竭

**反向压力测试**:
找出导致组合失败的最小冲击。

---

### 极值理论（EVT）

**POT（超阈值）方法**:
```python
from domain.risk.extreme_value import EVTCalculator

evt = EVTCalculator()

# 拟合广义 Pareto 分布（GPD）
gpd_params = evt.fit_gpd(
    returns=returns,
    threshold=-0.02  # 损失超过 2%
)

# 估计极端分位数
extreme_quantile = evt.estimate_extreme_quantile(
    gpd_params=gpd_params,
    probability=0.001  # 0.1% 分位数
)
```

**应用**:
- 估计超越 VaR 的极端损失
- 尾部风险保险定价

---

### Copula 模型

**定义**: 描述多个变量间的相关性结构，独立于边缘分布。

**常用 Copula**:
- Gaussian Copula（正态）
- t-Copula（带尾部相关）
- Clayton Copula（下尾相关）
- Gumbel Copula（上尾相关）

```python
from domain.risk.copula import CopulaModel

# 拟合 t-Copula
copula = CopulaModel(copula_type='t')
copula.fit(returns_matrix)

# 模拟相关场景
simulated_returns = copula.simulate(n_scenarios=10000)

# 计算尾部相关性
tail_dependence = copula.tail_dependence()
```

---

### 流动性风险

**度量指标**:
- 买卖价差（Bid-Ask Spread）
- 市场深度（Market Depth）
- 价格影响（Price Impact）
- 换手率（Turnover）

```python
from domain.risk.liquidity_risk import LiquidityRiskCalculator

calc = LiquidityRiskCalculator()

# 计算流动性调整 VaR
liquidity_adjusted_var = calc.liquidity_adjusted_var(
    var=var,
    position_size=position_size,
    avg_daily_volume=avg_volume,
    liquidation_horizon=5  # 5 日清仓
)
```

---

### 交易对手风险

**信用风险敞口**:
- 当前风险敞口（Current Exposure）
- 潜在未来风险敞口（Potential Future Exposure, PFE）
- 预期正敞口（Expected Positive Exposure, EPE）

**CVA（信用价值调整）**:
```python
from domain.risk.counterparty_risk import CounterpartyRiskCalculator

calc = CounterpartyRiskCalculator()

# 计算 CVA
cva = calc.calculate_cva(
    exposure_profile=exposure_profile,
    default_probability=pd,
    recovery_rate=0.4,
    discount_curve=discount_curve
)

# CVA 调整后的衍生品价值
adjusted_value = market_value - cva
```

---

## 风险监控

### 实时监控

```python
from domain.risk.risk_monitor import RiskMonitor

monitor = RiskMonitor()

# 设置风险限额
monitor.set_limits({
    'var_95': 0.02,           # VaR 不超过 2%
    'max_drawdown': 0.10,     # 最大回撤 10%
    'concentration': 0.20,    # 单一持仓不超过 20%
    'sector_exposure': 0.30   # 单一行业不超过 30%
})

# 检查违规
violations = monitor.check_violations(portfolio)

if violations:
    for v in violations:
        print(f"⚠️  风险违规: {v.limit_type} = {v.current_value:.2%} (限额: {v.limit:.2%})")
```

### 风险报告

```python
from domain.risk.reporting import RiskReporter

reporter = RiskReporter()

# 生成每日风险报告
report = reporter.daily_risk_report(
    portfolio=portfolio,
    date='2026-08-23'
)

# 导出 PDF
reporter.export_pdf(report, filename='risk_report_20260823.pdf')

# 报告内容
# - VaR/CVaR
# - 最大回撤
# - 行业暴露
# - 风格暴露
# - 集中度指标
# - 限额遵守情况
```

---

## 监管合规

### 巴塞尔协议

**巴塞尔 II/III 要求**:
- 市场风险：VaR (99%, 10 日)
- 信用风险：IRB 方法
- 操作风险：AMA 方法

```python
from domain.risk.regulatory import BaselCalculator

basel = BaselCalculator()

# 市场风险资本
market_risk_capital = basel.market_risk_capital(
    var_10day=var_10day,
    stressed_var=stressed_var,
    multiplier=3
)

# 信用风险资本
credit_risk_capital = basel.credit_risk_capital(
    exposure=exposure,
    pd=pd,  # 违约概率
    lgd=lgd,  # 违约损失率
    method='advanced_irb'
)

# 总资本要求
total_capital = market_risk_capital + credit_risk_capital + operational_risk_capital
```

### VaR 回测（Backtesting）

**监管要求**: 每日比较 VaR 预测与实际损失

```python
from domain.risk.backtesting import VaRBacktester

backtester = VaRBacktester()

# 执行回测
backtest_result = backtester.backtest(
    var_forecasts=var_forecasts,
    actual_returns=actual_returns,
    confidence_level=0.99
)

# 评估结果
print(f"违规次数: {backtest_result.n_violations}")
print(f"违规率: {backtest_result.violation_rate:.2%}")
print(f"预期违规率: {1 - 0.99:.2%}")

# Basel 交通灯系统
if backtest_result.n_violations <= 4:
    zone = "绿区"  # 模型可接受
elif backtest_result.n_violations <= 9:
    zone = "黄区"  # 需要改进
else:
    zone = "红区"  # 模型不可接受

print(f"巴塞尔区域: {zone}")
```

---

## 最佳实践

### 1. 多种方法交叉验证

```python
# 不要只依赖单一方法
var_historical = var_calc.calculate_historical_var(returns, 0.95)
var_parametric = var_calc.calculate_parametric_var(returns, 0.95)
var_mc = var_calc.calculate_monte_carlo_var(returns, 0.95)

# 比较结果
print(f"Historical: {var_historical:.2%}")
print(f"Parametric: {var_parametric:.2%}")
print(f"Monte Carlo: {var_mc:.2%}")

# 如果差异很大，需要调查原因
```

### 2. 考虑尾部风险

```python
# VaR 忽略尾部风险，建议同时计算 CVaR
var = var_calc.calculate_historical_var(returns, 0.95)
cvar = cvar_calc.calculate_cvar(returns, 0.95)

print(f"VaR (95%): {var:.2%}")
print(f"CVaR (95%): {cvar:.2%}")
print(f"尾部风险: CVaR - VaR = {cvar - var:.2%}")
```

### 3. 定期回测

```python
# 每月回测 VaR 模型
monthly_backtest = backtester.backtest(
    var_forecasts=var_forecasts,
    actual_returns=actual_returns
)

if monthly_backtest.violation_rate > 0.10:  # 违规率 > 10%
    print("⚠️  模型需要重新校准")
```

### 4. 压力测试补充

```python
# VaR 基于历史数据，无法预测黑天鹅
# 定期进行压力测试
stress_scenarios = [
    '2008_financial_crisis',
    'market_crash_30pct',
    'credit_spread_widening',
    'liquidity_shock'
]

for scenario in stress_scenarios:
    loss = tester.historical_scenario(portfolio, scenario)
    print(f"{scenario}: {loss:.2%}")
```

---

## 性能优化

### 向量化计算

```python
# ❌ 慢：循环计算 VaR
vars = []
for i in range(len(portfolios)):
    vars.append(var_calc.calculate_historical_var(portfolios[i]))

# ✅ 快：批量计算
vars = var_calc.calculate_historical_var_batch(portfolios)
```

### 并行计算

```python
from concurrent.futures import ProcessPoolExecutor

# 蒙特卡洛模拟使用多进程
with ProcessPoolExecutor(max_workers=4) as executor:
    results = executor.map(simulate_one_path, range(n_simulations))
```

---

## 测试

```bash
# 运行风险领域测试
pytest tests/domain/risk/ -v

# 测试特定模块
pytest tests/domain/risk/test_var.py -v
pytest tests/domain/risk/test_attribution.py -v
pytest tests/domain/risk/test_stress_test.py -v
```

---

## 相关文档

- [QuantLib 技术计算库](../quantlib/README.md)
- [回测领域](../backtest/README.md)
- [因子领域](../factors/README.md)

---

## 贡献指南

### 添加新风险度量

1. 在对应模块中实现计算方法
2. 编写单元测试（包含边界情况）
3. 添加回测验证
4. 更新本文档

### 添加新压力情景

1. 在 `stress_test.py` 中定义情景参数
2. 提供历史数据支持
3. 编写示例代码

---

**维护者**: QuantSys V2 Team  
**最后更新**: 2026-08-23  
**版本**: v2.0 (quantlib 重构后)
