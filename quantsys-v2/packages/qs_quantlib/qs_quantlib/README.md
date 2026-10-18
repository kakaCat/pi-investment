# QuantLib - Quantitative Finance Technical Library

**领域职责**: 纯技术计算库，提供金融量化计算的基础工具和算法

---

## 概述

QuantLib 是一个纯技术计算库，不包含业务逻辑。它提供衍生品定价、固定收益计算、投资组合优化、时间序列分析等金融量化计算工具。

**重构说明**: 2026-08-23 完成重构，从原 209 文件减至 77 文件（↓63%）。回测、风险、因子模块已独立为业务域。

**核心能力**:
- ✅ 衍生品定价（期权、波动率曲面、Greeks）
- ✅ 固定收益（债券定价、久期、凸度、收益率曲线）
- ✅ 投资组合优化（均值方差、Black-Litterman、风险平价）
- ✅ 时间序列分析（ARIMA、GARCH、协整、季节性）
- ✅ 统计工具（分布拟合、假设检验、蒙特卡洛）
- ✅ 技术指标（移动平均、动量、趋势、波动率）
- ✅ 机器学习集成（特征工程、因子挖掘、收益预测）- 惰性加载
- ✅ 强化学习（FinRL、Qlib 集成）- 惰性加载

---

## 架构定位

### 不属于此库的内容（已迁移）

```python
# ❌ 回测引擎 → domain.backtest
from domain.backtest.engine import BreakoutStrategy

# ❌ 风险管理 → domain.risk
from domain.risk.var import VaRCalculator

# ❌ 因子计算 → domain.factors
from domain.factors.library.momentum import MomentumFactors
```

### 属于此库的内容

```python
# ✅ 衍生品定价
from domain.quantlib.derivatives import BlackScholesCalculator

# ✅ 债券计算
from domain.quantlib.fixed_income import BondPricer

# ✅ 投资组合优化
from domain.quantlib.portfolio import MeanVarianceOptimizer

# ✅ 时间序列分析
from domain.quantlib.timeseries import ARIMAModel
```

---

## 目录结构

```
quantlib/
├── __init__.py                    # 领域入口（惰性加载 ML/RL）
├── base_calculator.py             # 计算器基类
├── data_validator.py              # 数据验证器
├── exceptions.py                  # 异常定义
├── rate_calculations.py           # 利率计算
│
├── derivatives/            (16)   # 衍生品定价
│   ├── black_scholes.py           # Black-Scholes 期权定价
│   ├── binomial_tree.py           # 二叉树模型
│   ├── monte_carlo.py             # 蒙特卡洛定价
│   ├── implied_volatility.py      # 隐含波动率
│   ├── volatility_surface.py      # 波动率曲面
│   ├── greeks.py                  # Greeks 计算
│   └── ... (其他衍生品)
│
├── fixed_income/           (7)    # 固定收益
│   ├── bond_pricer.py             # 债券定价
│   ├── duration.py                # 久期计算
│   ├── convexity.py               # 凸度计算
│   ├── yield_curve.py             # 收益率曲线
│   └── ... (其他)
│
├── portfolio/              (7)    # 投资组合优化
│   ├── mean_variance.py           # 均值方差优化
│   ├── black_litterman.py         # Black-Litterman 模型
│   ├── risk_parity.py             # 风险平价
│   ├── efficient_frontier.py      # 有效前沿
│   └── ... (其他)
│
├── timeseries/             (8)    # 时间序列分析
│   ├── arima.py                   # ARIMA 模型
│   ├── garch.py                   # GARCH 波动率模型
│   ├── cointegration.py           # 协整检验
│   ├── seasonality.py             # 季节性分析
│   ├── analyzer.py                # 综合分析器
│   └── ... (其他)
│
├── ml/                    (10)    # 机器学习集成（惰性加载）
│   ├── feature_engineering.py     # 特征工程
│   ├── factor_mining.py           # 因子挖掘
│   ├── return_prediction.py       # 收益预测
│   ├── risk_prediction.py         # 风险预测
│   ├── anomaly_detection.py       # 异常检测
│   └── ... (其他)
│
├── rl/                     (3)    # 强化学习基础
│   ├── base_agent.py              # RL Agent 基类
│   └── base_environment.py        # RL Environment 基类
│
├── finrl/                  (6)    # FinRL 框架集成（惰性加载）
│   ├── finrl_agent.py             # FinRL Agent
│   ├── stock_trading_env.py       # 股票交易环境
│   └── ... (5 个算法实现)
│
├── qlib/                   (4)    # Qlib RL 框架（惰性加载）
│   ├── qlib_agent.py              # Qlib RL Agent
│   └── qlib_trading_env.py        # Qlib 交易环境
│
├── statistics/             (1)    # 统计工具
│   └── distributions.py           # 分布拟合、假设检验
│
├── technical/              (2)    # 技术指标
│   ├── indicators.py              # 技术指标计算
│   └── patterns.py                # 形态识别
│
└── tools/                  (1)    # 辅助工具
    └── helpers.py                 # 数据转换、缓存
```

---

## 快速开始

### 1. 期权定价

```python
from domain.quantlib.derivatives import BlackScholesCalculator

# 创建 Black-Scholes 计算器
bs = BlackScholesCalculator()

# 计算欧式看涨期权价格
call_price = bs.call_option_price(
    spot=100,           # 标的价格
    strike=105,         # 行权价
    time_to_maturity=0.5,  # 到期时间（年）
    risk_free_rate=0.05,   # 无风险利率
    volatility=0.25        # 波动率
)

# 计算 Greeks
greeks = bs.calculate_greeks(
    spot=100, strike=105, time_to_maturity=0.5,
    risk_free_rate=0.05, volatility=0.25
)

print(f"Call Price: {call_price:.2f}")
print(f"Delta: {greeks.delta:.4f}")
print(f"Gamma: {greeks.gamma:.4f}")
print(f"Vega: {greeks.vega:.4f}")
print(f"Theta: {greeks.theta:.4f}")
```

### 2. 债券定价

```python
from domain.quantlib.fixed_income import BondPricer

# 创建债券定价器
pricer = BondPricer()

# 计算债券价格
bond_price = pricer.price_bond(
    face_value=1000,        # 面值
    coupon_rate=0.05,       # 票面利率
    years_to_maturity=5,    # 到期年限
    yield_to_maturity=0.06, # 到期收益率
    frequency=2             # 付息频率（半年付）
)

# 计算久期
duration = pricer.calculate_duration(
    face_value=1000,
    coupon_rate=0.05,
    years_to_maturity=5,
    yield_to_maturity=0.06
)

print(f"Bond Price: {bond_price:.2f}")
print(f"Duration: {duration:.2f} years")
```

### 3. 投资组合优化

```python
from domain.quantlib.portfolio import MeanVarianceOptimizer

# 创建均值方差优化器
optimizer = MeanVarianceOptimizer()

# 计算最优权重
optimal_weights = optimizer.optimize(
    expected_returns=returns_mean,  # 预期收益
    covariance_matrix=returns_cov,  # 协方差矩阵
    target_return=0.15,             # 目标收益率
    constraints={'max_weight': 0.3} # 约束条件
)

# 计算有效前沿
efficient_frontier = optimizer.efficient_frontier(
    expected_returns=returns_mean,
    covariance_matrix=returns_cov,
    n_points=100
)

print(f"Optimal Weights: {optimal_weights}")
print(f"Expected Return: {optimizer.portfolio_return(optimal_weights):.2%}")
print(f"Portfolio Risk: {optimizer.portfolio_risk(optimal_weights):.2%}")
```

### 4. 时间序列分析

```python
from domain.quantlib.timeseries import ARIMAModel

# 创建 ARIMA 模型
model = ARIMAModel(order=(1, 1, 1))

# 拟合数据
model.fit(time_series_data)

# 预测
forecast = model.forecast(steps=30)

# 诊断
diagnostics = model.diagnostics()
print(f"AIC: {diagnostics.aic:.2f}")
print(f"BIC: {diagnostics.bic:.2f}")

# GARCH 波动率建模
from domain.quantlib.timeseries import GARCHModel

garch = GARCHModel(p=1, q=1)
garch.fit(returns)
volatility_forecast = garch.forecast_volatility(horizon=10)
```

---

## 核心模块详解

### 衍生品定价 (derivatives/)

**Black-Scholes 模型**:
- 欧式期权定价
- 隐含波动率计算
- Greeks 敏感性分析

**数值方法**:
- 二叉树/三叉树
- 蒙特卡洛模拟
- 有限差分法

**波动率建模**:
- 波动率曲面拟合
- SABR 模型
- Heston 随机波动率

---

### 固定收益 (fixed_income/)

**债券分析**:
- 价格计算（折现现金流）
- 久期和凸度
- 应计利息

**收益率曲线**:
- 插值方法（线性、样条）
- 零息利率提取
- 远期利率计算

---

### 投资组合优化 (portfolio/)

**优化方法**:
- 均值方差优化（Markowitz）
- Black-Litterman 模型（融合主观观点）
- 风险平价（Risk Parity）
- 最小方差组合

**约束条件**:
- 权重约束（多头、多空）
- 行业/板块约束
- 换手率约束

---

### 时间序列分析 (timeseries/)

**线性模型**:
- ARIMA（自回归移动平均）
- SARIMA（季节性 ARIMA）
- VAR（向量自回归）

**波动率模型**:
- GARCH（广义自回归条件异方差）
- EGARCH（指数 GARCH）
- GJR-GARCH

**协整分析**:
- Engle-Granger 两步法
- Johansen 检验
- 误差修正模型（ECM）

---

### 机器学习集成 (ml/) - 惰性加载

**特征工程**:
```python
# ⚠️ 首次导入会加载 torch/mlflow 等重依赖
from domain.quantlib import FeatureEngineeringCalculator

calculator = FeatureEngineeringCalculator()
features = calculator.engineer_features(data)
```

**惰性加载机制**:
- ML/RL 模块使用 PEP 562 `__getattr__` 按需加载
- 避免被动引入 torch/mlflow/transformers 等重依赖
- 只做衍生品/债券/投组计算的进程不会加载 ML 栈

**包含模块**:
- 特征工程（自动化特征生成）
- 因子挖掘（自动发现有效因子）
- 收益预测（回归模型）
- 风险预测（分类模型）
- 异常检测（Isolation Forest、AutoEncoder）

---

### 强化学习 (rl/, finrl/, qlib/) - 惰性加载

**基础框架**:
```python
from domain.quantlib import BaseRLAgent, BaseRLEnvironment

# 自定义 RL Agent
class MyAgent(BaseRLAgent):
    def train(self, env):
        # 训练逻辑
        pass
```

**FinRL 集成**:
- 内置 5 个算法（PPO、A2C、DDPG、SAC、TD3）
- 股票交易环境
- 多账户支持

**Qlib 集成**:
- Qlib RL 框架适配
- 高频交易环境
- 市场微观结构建模

---

## 设计原则

### 1. 纯技术计算

```python
# ✅ 正确：domain 层不依赖 application
from domain.quantlib import BaseCalculator

# ❌ 错误：不应依赖应用服务
from application.services import SomeService  # 违反架构
```

### 2. 依赖注入

```python
# ✅ 通过参数传递配置
calculator = BlackScholesCalculator(config=my_config)

# ❌ 不直接导入配置
from infrastructure.config import get_config  # 违反分层
```

### 3. 单一职责

每个计算器只负责一类计算：
- `BlackScholesCalculator` - 只做 BS 期权定价
- `BondPricer` - 只做债券定价
- `MeanVarianceOptimizer` - 只做均值方差优化

### 4. 可测试性

所有计算器都有明确的输入输出，便于单元测试：

```python
def test_black_scholes():
    bs = BlackScholesCalculator()
    price = bs.call_option_price(
        spot=100, strike=100, time_to_maturity=1,
        risk_free_rate=0.05, volatility=0.2
    )
    assert 9 < price < 11  # 近似值检查
```

---

## 性能优化

### 向量化计算

```python
# ❌ 慢：循环
for i in range(len(strikes)):
    prices[i] = bs.call_option_price(spot, strikes[i], ...)

# ✅ 快：向量化
prices = bs.call_option_price_vectorized(
    spot=spot,
    strikes=strikes_array,  # NumPy 数组
    ...
)
```

### 缓存

```python
from domain.quantlib import cache_result

@cache_result(ttl=3600)
def expensive_calculation(params):
    # 昂贵的计算
    return result
```

### Numba 加速

```python
from numba import jit

@jit(nopython=True)
def monte_carlo_simulation(params):
    # 蒙特卡洛模拟
    # Numba 会编译为机器码
    return result
```

---

## 惰性加载说明

### 为什么需要惰性加载？

ML/RL 模块会引入重依赖（torch、mlflow、transformers），它们各自携带 OpenMP 运行时。与 lightgbm/xgboost 的 Homebrew libomp 混载后可能触发 OpenMP worker 线程段错误。

### 如何使用？

```python
# ✅ 只导入 BaseCalculator，不会加载 ML 栈
from domain.quantlib import BaseCalculator, DataValidator

# ✅ 首次使用 ML 模块时才加载
from domain.quantlib import FeatureEngineeringCalculator  # 此时加载 torch 等
```

### 检查加载状态

```python
import sys
from domain.quantlib import BaseCalculator

# ML 模块未加载
assert 'torch' not in sys.modules
assert 'mlflow' not in sys.modules

# 使用 ML 功能后才加载
from domain.quantlib import FeatureEngineeringCalculator
assert 'torch' in sys.modules
```

参考: [memory/polars-numpy-malloc-crash.md](../../.claude/projects/-Users-yunpeng-pi-investment/memory/polars-numpy-malloc-crash.md)

---

## 测试

```bash
# 运行 quantlib 测试
pytest tests/domain/quantlib/ -v

# 测试特定模块
pytest tests/domain/quantlib/test_derivatives.py -v
pytest tests/domain/quantlib/test_fixed_income.py -v
pytest tests/domain/quantlib/test_portfolio.py -v

# 跳过 ML/RL 测试（需要重依赖）
pytest tests/domain/quantlib/ -v -m "not ml and not rl"
```

---

## 迁移指南

如果你的代码还在使用旧的 quantlib 路径，请参考以下迁移：

### 回测引擎

```python
# 旧
from domain.quantlib.backtest_engine import BacktestEngine

# 新
from domain.backtest.engine import BreakoutStrategy, StrategyRunner
```

### 风险管理

```python
# 旧
from domain.quantlib.risk import RiskAttributionCalculator

# 新
from domain.risk.attribution import RiskAttributionCalculator
```

### 因子计算

```python
# 旧
from domain.quantlib.factors import MomentumFactors

# 新
from domain.factors.library.momentum import MomentumFactors
```

### 基础设施

```python
# 旧
from domain.quantlib.adapters import get_factor_adapter

# 新
from infrastructure.quantlib.adapters import get_factor_adapter
# 或直接从实际位置导入（推荐）
from adapters.outbound.datasources.providers.quantlib import get_factor_adapter
```

---

## 相关文档

- [回测领域](../backtest/README.md) - 策略回测引擎
- [风险领域](../risk/README.md) - 风险管理
- [因子领域](../factors/README.md) - 因子计算与分析
- [重构完成报告](../../docs/work-logs/2026-08/quantlib-refactoring-complete.md)
- [重构计划](../../docs/quantlib-refactoring-plan-2026-08.md)

---

## 贡献指南

### 添加新计算器

1. 继承 `BaseCalculator`
2. 实现核心计算方法
3. 添加输入验证（使用 `DataValidator`）
4. 编写单元测试
5. 添加文档字符串

### 代码规范

- 使用类型提示（Type Hints）
- 遵循 NumPy 文档字符串格式
- 向量化计算优先于循环
- 避免依赖 application 层

---

**维护者**: QuantSys V2 Team  
**最后更新**: 2026-08-23  
**版本**: v2.0 (重构后)  
**重构历史**: 
- 2026-08-23: Phase 1-4 完成，从 209 文件降至 77 文件
- 2026-08-23: 拆分出 backtest/risk/factors 三个独立业务域
- 2026-08-23: 修复循环依赖，引入惰性加载机制
