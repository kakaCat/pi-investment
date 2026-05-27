# P0 Implementation Plan: 量化投资核心能力暴露

> **适用场景**: A股 + 港股
> **目标**: 将 `quantsys-v2/quantlib/` 中已实现的 4 个核心模块暴露给 AI Agent（TypeScript 侧），使其在投资分析中可直接调用
> **计划日期**: 2026-05-25

---

## 总览

### 现状

| P0 模块 | Python 实现 | API 端点 | quant_cli 命令 | Agent 可调用 |
|--------|-----------|---------|---------------|-------------|
| P0-1 投组优化 (Markowitz/BL/RiskParity) | ✅ quantlib/portfolio/ | ❌ 旧版桥接（未用新实现） | ❌ 只有简化版 `portfolio.optimize` | ⚠️ 半成品 |
| P0-2 LSTM/Transformer 训练 | ✅ quantlib/ml/ | ❌ 只支持 XGBoost/LightGBM | ❌ model_train 不支持 | ⚠️ 半成品 |
| P0-3 时间序列 (ARIMA/GARCH/Kalman) | ✅ quantlib/timeseries/ | ❌ 完全不存在 | ❌ 完全不存在 | ❌ |
| P0-4 因子模型 (Barra/FF) | ✅ quantlib/factor_models/ | ❌ 完全不存在 | ❌ 完全不存在 | ❌ |

### 实现路径

四块共用一个模式：

```
Python quantlib 模块
    ↓
新 API 路由 (quantsys-v2/api/routes/)
    ↓
注册到 server.py Blueprint
    ↓
新增 quant_cli 命令定义 (quant-cli-tool.ts)
    ↓
Agent 通过 quant_cli 工具调用
```

### 实现优先级

**P0-3 (时间序列) 和 P0-4 (因子模型) 优先** — 完全无 API 暴露，从零建最快。
**P0-1 次之** — 需要改造已有 API，理解旧代码后再替换。
**P0-2 最后** — 涉及深度学习训练 pipeline，最复杂。

---

## P0-3: 时间序列分析 (ARIMA / GARCH / Kalman)

### 1. 现有代码

| 文件 | 内容 |
|------|------|
| `quantsys-v2/quantlib/timeseries/arima.py` | `ARIMACalculator` — fit(series, order), forecast(steps), auto_select_order, diagnose_residuals |
| `quantsys-v2/quantlib/timeseries/garch.py` | `GARCHCalculator` — fit(returns, p, q), forecast_volatility(steps), calculate_var, detect_volatility_clustering |
| `quantsys-v2/quantlib/timeseries/kalman.py` | `KalmanFilterCalculator` — filter(obs, F, H, Q, R), smooth, predict, fit_local_level |
| `quantsys-v2/quantlib/timeseries/cointegration.py` | `CointegrationCalculator` — 协整检验、配对交易 |
| `quantsys-v2/quantlib/timeseries/causality.py` | `GrangerCausalityCalculator` — 格兰杰因果检验 |

所有 Calculator 继承 `BaseCalculator`，统一接口 `.calculate()` 和 `.fit()` / `.forecast()`。

### 2. 需要创建/修改的文件

#### Step 2.1: 新 API 蓝图 — `quantsys-v2/api/routes/timeseries.py`

新建文件，提供以下端点：

```python
# 路由蓝图
timeseries_bp = Blueprint('timeseries', __name__)

# ARIMA
POST /api/timeseries/arima/fit
POST /api/timeseries/arima/forecast
POST /api/timeseries/arima/auto-order    # 自动选参 (AIC/BIC)

# GARCH
POST /api/timeseries/garch/fit
POST /api/timeseries/garch/forecast
POST /api/timeseries/garch/var            # Value at Risk

# Kalman
POST /api/timeseries/kalman/filter
POST /api/timeseries/kalman/smooth
POST /api/timeseries/kalman/local-level   # 局部水平模型（趋势提取）

# 协整 & 因果 (bonus)
POST /api/timeseries/cointegration/test   # 配对协整检验
POST /api/timeseries/causality/test       # 格兰杰因果检验
```

**实现要点**:

```python
from quantlib.timeseries import (
    ARIMACalculator,
    GARCHCalculator,
    KalmanFilterCalculator,
    CointegrationCalculator,
    GrangerCausalityCalculator
)

# 示例：ARIMA 拟合
@timeseries_bp.route('/api/timeseries/arima/fit', methods=['POST'])
@handle_api_error
def arima_fit():
    data = request.get_json()
    calc = ARIMACalculator()
    # data['series'] 传入价格序列，data['order'] 可选 (p,d,q)
    result = calc.fit(
        data=data['series'],
        order=tuple(data.get('order', (1, 1, 1))),
        seasonal_order=tuple(data['seasonal_order']) if data.get('seasonal_order') else None
    )
    return api_response(result)
```

#### Step 2.2: 注册蓝图 — `quantsys-v2/api/server.py`

在 `create_app()` 中添加两行：

```python
from api.routes.timeseries import timeseries_bp    # 新增
app.register_blueprint(timeseries_bp)                # 新增
```

#### Step 2.3: 新增 quant_cli 命令 — `src/infrastructure/tools/core/quant-cli-tool.ts`

在 `COMMANDS` 对象中添加以下命令定义：

```typescript
// ARIMA
"timeseries.arima": {
  domain: "timeseries",
  action: "arima",
  description: "ARIMA时间序列建模：拟合、预测、自动选参。用于预测股价趋势、识别季节性模式。",
  params: {
    symbols: { required: true, type: "string" },
    action_type: { type: "string", enum: ["fit", "forecast", "auto_order"] },
    order: { type: "string" },           // "1,1,1"
    forecast_steps: { type: "integer" },
    start_date: { type: "string" },       // "YYYYMMDD"
    end_date: { type: "string" },
  },
  example: { symbols: "600519", action_type: "forecast", order: "1,1,1", forecast_steps: 10 },
},

// GARCH
"timeseries.garch": {
  domain: "timeseries",
  action: "garch",
  description: "GARCH波动率建模：拟合、波动率预测、VaR计算。用于评估风险、设定止损。",
  params: {
    symbols: { required: true, type: "string" },
    action_type: { type: "string", enum: ["fit", "forecast", "var"] },
    p: { type: "integer" },
    q: { type: "integer" },
    forecast_steps: { type: "integer" },
    confidence: { type: "number" },       // VaR 置信度
    start_date: { type: "string" },
    end_date: { type: "string" },
  },
  example: { symbols: "600519", action_type: "forecast", p: 1, q: 1, forecast_steps: 5 },
},

// Kalman
"timeseries.kalman": {
  domain: "timeseries",
  action: "kalman",
  description: "卡尔曼滤波：状态估计、趋势提取、平滑。用于去噪信号、估计隐藏趋势。",
  params: {
    symbols: { required: true, type: "string" },
    action_type: { type: "string", enum: ["filter", "smooth", "local_level"] },
    start_date: { type: "string" },
    end_date: { type: "string" },
  },
  example: { symbols: "600519", action_type: "local_level" },
},
```

同时在底部的 `常用命令` 列表字符串中补充这三个命令名。

#### Step 2.4: 注册到 quant_v2_client.ts 白名单

检查 `src/infrastructure/quant/quant-v2-client.ts` 中 `V2_COMMAND_LIST` 的白名单，确认新命令可以被路由。

### 3. 验收标准

- [ ] `quant_cli` 执行 `timeseries.arima` 返回 ARIMA 拟合结果（系数、AIC/BIC、残差诊断）
- [ ] `quant_cli` 执行 `timeseries.garch` 返回 GARCH 波动率预测和 VaR 值
- [ ] `quant_cli` 执行 `timeseries.kalman` 返回卡尔曼滤波后的趋势序列
- [ ] Agent 在分析股票时可以调用这些命令（通过 quant_cli 桥接）
- [ ] 所有端点返回 JSON 格式，与现有 `api_response()` 一致

### 4. 测试用例

```
# 用例 1: ARIMA 自动选参 + 预测
quant_cli({
  command: "timeseries.arima",
  params: { symbols: "600519", action_type: "auto_order", forecast_steps: 10 }
})
期望: 返回最优 (p,d,q) 阶数、AIC 值、10 步预测值和置信区间

# 用例 2: GARCH 波动率预测
quant_cli({
  command: "timeseries.garch",
  params: { symbols: "600519", action_type: "forecast", p: 1, q: 1, forecast_steps: 5 }
})
期望: 返回条件波动率序列、5 步预测波动率、95% VaR

# 用例 3: Kalman 趋势提取
quant_cli({
  command: "timeseries.kalman",
  params: { symbols: "600519", action_type: "local_level" }
})
期望: 返回滤波后的趋势线、原始 vs 滤波对比
```

---

## P0-4: 因子模型 (Barra / Fama-French)

### 1. 现有代码

| 文件 | 内容 |
|------|------|
| `quantsys-v2/quantlib/factor_models/fama_french.py` | `FamaFrench3FactorCalculator`, `FamaFrench5FactorCalculator`, `FamaFrenchFactorBuilder` |
| `quantsys-v2/quantlib/factor_models/barra.py` | `BarraRiskModelCalculator`, `BarraFactorBuilder` |
| `quantsys-v2/quantlib/factor_models/carhart.py` | `CarhartFourFactorCalculator`, `MomentumFactorBuilder` |
| `quantsys-v2/quantlib/factor_models/factor_exposure.py` | `FactorExposureCalculator` |

**FF3 接口**: `calculate(asset_returns, market_returns, risk_free_rate, smb_factor, hml_factor)` → alpha, beta_mkt, beta_smb, beta_hml, r_squared, t_stats, p_values

**Barra 接口**: `calculate(returns, factor_exposures, industry_exposures, portfolio_weights)` → factor_risk, specific_risk, total_risk, risk_decomposition

### 2. 实现策略: 两层 API

**层 1 — 原始因子数据获取**（给 Agent 提供因子值）:
- 需要数据源提供 A 股的 MKT, SMB, HML, RMW, CMA 因子日频数据
- 可以从 A 股全市场日频收益率构建

**层 2 — 单股/组合因子归因**（Agent 传入收益率序列）:
- 用户已有持仓/关注的股票的收益率 → 回归到因子 → 输出暴露系数和 alpha

第一期实现**层 2（归因）**，因子数据由 Calculator 内部从全市场自建。

### 3. 需要创建/修改的文件

#### Step 3.1: 新 API 蓝图 — `quantsys-v2/api/routes/factor_models.py`

```python
factor_models_bp = Blueprint('factor_models', __name__)

# Fama-French
POST /api/factor-models/fama-french/3-factor     # 3因子归因
POST /api/factor-models/fama-french/5-factor     # 5因子归因
POST /api/factor-models/fama-french/build-factors # 自建因子（从全市场数据）

# Barra
POST /api/factor-models/barra/decompose          # 风险分解
POST /api/factor-models/barra/estimate           # 估计因子协方差

# 因子暴露
POST /api/factor-models/exposure                 # 计算因子暴露
```

**实现要点**: 因子自建逻辑

```python
from quantlib.factor_models import (
    FamaFrench3FactorCalculator,
    FamaFrench5FactorCalculator,
    BarraRiskModelCalculator,
    FactorExposureCalculator
)

@factor_models_bp.route('/api/factor-models/fama-french/3-factor', methods=['POST'])
@handle_api_error
def ff3_factor():
    """对指定股票/组合做 Fama-French 3因子归因"""
    data = request.get_json()
    
    # 1. 获取股票日频收益率
    symbol = data['symbol']
    klines = ds.kline.get_daily_klines(symbol, data.get('start_date'), data.get('end_date'))
    returns = compute_daily_returns(klines)  # (p_t - p_{t-1}) / p_{t-1}
    
    # 2. 自建 A 股 Fama-French 因子（从全市场市值/账面比分组）
    builder = FamaFrenchFactorBuilder()
    factors = builder.build_factors(start_date, end_date)  # {mkt, smb, hml}
    
    # 3. 归因
    calc = FamaFrench3FactorCalculator()
    result = calc.calculate(
        asset_returns=returns,
        market_returns=factors['mkt'],
        risk_free_rate=data.get('risk_free_rate', 0.02),
        smb_factor=factors['smb'],
        hml_factor=factors['hml']
    )
    return api_response(result)
```

#### Step 3.2: 注册蓝图 — `quantsys-v2/api/server.py`

```python
from api.routes.factor_models import factor_models_bp
app.register_blueprint(factor_models_bp)
```

#### Step 3.3: 新增 quant_cli 命令 — `src/infrastructure/tools/core/quant-cli-tool.ts`

```typescript
"factor.fama_french": {
  domain: "factor",
  action: "fama_french",
  description: "Fama-French 多因子归因：分析股票收益受市场、规模、价值等因子影响的程度。A股模型(Grinold-Kahn): alpha、beta、因子暴露、R²。",
  params: {
    symbols: { required: true, type: "string" },
    model: { type: "string", enum: ["3factor", "5factor"] },
    start_date: { type: "string" },
    end_date: { type: "string" },
    risk_free_rate: { type: "number" },
  },
  example: { symbols: "600519", model: "3factor", start_date: "20250101", end_date: "20250525" },
},

"factor.barra": {
  domain: "factor",
  action: "barra",
  description: "Barra 多因子风险模型：分解组合风险为因子风险和特异性风险。用于理解风险来源。",
  params: {
    symbols: { required: true, type: "string" },
    start_date: { type: "string" },
    end_date: { type: "string" },
  },
  example: { symbols: "600519,000858,601318", start_date: "20250101" },
},
```

### 4. 验收标准

- [ ] `quant_cli` 执行 `factor.fama_french` 返回 alpha、各因子 beta、t 统计量、p 值、R²
- [ ] `quant_cli` 执行 `factor.barra` 返回因子风险、特异性风险、风险贡献度
- [ ] Agent 可以问"600519 最近受什么因子驱动？" — 得到因子归因结果
- [ ] 因子自建逻辑正常工作（不需要外部数据源，从 A 股全市场收益率构建）

### 5. 测试用例

```
# 用例 1: 单股 FF3因子归因
quant_cli({
  command: "factor.fama_french",
  params: { symbols: "600519", model: "3factor", start_date: "20250101" }
})
期望: 返回 {"alpha": 0.0012, "beta_mkt": 0.85, "beta_smb": -0.3, "beta_hml": 0.1, "r_squared": 0.45, ...}

# 用例 2: 组合 Barra 风险分解
quant_cli({
  command: "factor.barra",
  params: { symbols: "600519,000858,601318", start_date: "20250101" }
})
期望: 返回 {"factor_risk": 0.15, "specific_risk": 0.05, "total_risk": 0.20, "decomposition": {...}}
```

---

## P0-1: 投组优化 (Markowitz / Black-Litterman / Risk Parity)

### 1. 现有代码 vs 暴露状态

| 实现 | 位置 | API 暴露 | quant_cli |
|------|------|---------|-----------|
| `MarkowitzOptimizer` (min_variance, max_sharpe, target_return) | `quantlib/portfolio/markowitz.py` | ❌ | ❌ |
| `BlackLittermanOptimizer` (主观观点 + 市场均衡) | `quantlib/portfolio/black_litterman.py` | ❌ | ❌ |
| `RiskParityOptimizer` (等风险贡献) | `quantlib/portfolio/risk_parity.py` | ❌ | ❌ |
| `EfficientFrontierCalculator` | `quantlib/portfolio/efficient_frontier.py` | ❌ | ❌ |
| `ConstraintManager` (权重上下界约束) | `quantlib/portfolio/constraints.py` | ❌ | ❌ |

**现有 `portfolio.optimize` 调用路径**:
```
quant_cli("portfolio.optimize")
  → quant-v2-client.ts
    → POST /api/portfolio/optimize
      → OLD quant/quantsys/cli/portfolio_analytics.py  ← 未用新实现！
```

### 2. 改造策略

**不修改旧端点**（兼容性），新增 `/api/portfolio/v2/` 端点：

#### Step 2.1: 新建 API 路由 — `quantsys-v2/api/routes/portfolio_v2.py`

```python
portfolio_v2_bp = Blueprint('portfolio_v2', __name__)

from quantlib.portfolio import (
    MarkowitzOptimizer,
    BlackLittermanOptimizer,
    RiskParityOptimizer,
    EfficientFrontierCalculator,
    ConstraintManager
)

# 核心端点
POST /api/portfolio/v2/markowitz      # Markowitz 优化
POST /api/portfolio/v2/black-litterman # Black-Litterman 优化
POST /api/portfolio/v2/risk-parity     # Risk Parity 优化
POST /api/portfolio/v2/efficient-frontier # 有效前沿
```

**Markowitz 端点实现**:
```python
@portfolio_v2_bp.route('/api/portfolio/v2/markowitz', methods=['POST'])
@handle_api_error
def markowitz():
    data = request.get_json()
    
    # data 中传入:
    #   symbols: ["600519", "000858", ...]
    #   objective: "max_sharpe" | "min_variance" | "target_return"
    #   target_return: 0.15 (for target_return objective)
    #   risk_free_rate: 0.02
    #   lower_bound: 0.0
    #   upper_bound: 0.4
    #   start_date, end_date
    
    # 1. 获取各标的收益率 → 计算 mean, cov
    returns_dict = {}
    for sym in data['symbols']:
        klines = ds.kline.get_daily_klines(sym, data.get('start_date'), data.get('end_date'))
        returns_dict[sym] = compute_daily_returns(klines)
    
    returns_df = pd.DataFrame(returns_dict).dropna()
    mu = returns_df.mean().values
    Sigma = returns_df.cov().values
    
    # 2. 设置约束
    cm = ConstraintManager()
    cm.set_bounds(lower=data.get('lower_bound', 0.0), upper=data.get('upper_bound', 1.0))
    
    # 3. 优化
    opt = MarkowitzOptimizer(risk_free_rate=data.get('risk_free_rate', 0.02))
    result = opt.optimize(
        expected_returns=mu,
        cov_matrix=Sigma,
        objective=data.get('objective', 'max_sharpe'),
        target_return=data.get('target_return'),
        lower_bound=data.get('lower_bound', 0.0),
        upper_bound=data.get('upper_bound', 1.0)
    )
    
    # 4. 映射回 symbol
    result['symbols'] = data['symbols']
    result['weights_map'] = {sym: w for sym, w in zip(data['symbols'], result['value']['weights'])}
    return api_response(result)
```

**Black-Litterman 端点**（关键差异化能力）:
```python
@portfolio_v2_bp.route('/api/portfolio/v2/black-litterman', methods=['POST'])
@handle_api_error
def black_litterman():
    data = request.get_json()
    
    # views: [
    #   {"assets": [0, 1], "return": 0.05, "confidence": 0.5},  # 相对观点
    #   {"assets": [2], "return": 0.03, "confidence": 0.8}      # 绝对观点
    # ]
    
    opt = BlackLittermanOptimizer()
    result = opt.optimize(
        market_weights=data['market_weights'],   # 市场基准权重
        cov_matrix=cov,
        views=data.get('views', []),             # 主观观点！
        risk_aversion=data.get('risk_aversion', 2.5),
        tau=data.get('tau', 0.025)
    )
    return api_response(result)
```

#### Step 2.2: 注册蓝图 — `quantsys-v2/api/server.py`

```python
from api.routes.portfolio_v2 import portfolio_v2_bp
app.register_blueprint(portfolio_v2_bp)
```

#### Step 2.3: 新增/修改 quant_cli 命令

**方案 A — 新增独立命令（推荐）**:
```typescript
"portfolio.markowitz": {
  domain: "portfolio",
  action: "markowitz",
  description: "Markowitz 均值-方差优化：最小方差、最大夏普、目标收益。支持约束上下界。",
  params: {
    symbols: { required: true, type: "string" },
    objective: { type: "string", enum: ["min_variance", "max_sharpe", "target_return"] },
    target_return: { type: "number" },
    risk_free_rate: { type: "number" },
    lower_bound: { type: "number" },
    upper_bound: { type: "number" },
    start_date: { type: "string" },
    end_date: { type: "string" },
  },
  example: { symbols: "600519,000858,601318", objective: "max_sharpe", risk_free_rate: 0.02 },
},

"portfolio.black_litterman": {
  domain: "portfolio",
  action: "black_litterman",
  description: "Black-Litterman 模型：结合市场均衡收益与主观观点，用贝叶斯更新得到后验收益和最优权重。适合 Agent 表达主观判断后优化。",
  params: {
    symbols: { required: true, type: "string" },
    market_weights: { type: "string" },    // 市场基准权重 "0.4,0.3,0.3"
    views: { type: "string" },             // JSON 字符串化的 views 数组
    risk_aversion: { type: "number" },
    tau: { type: "number" },
    start_date: { type: "string" },
    end_date: { type: "string" },
  },
  example: {
    symbols: "600519,000858",
    market_weights: "0.5,0.5",
    views: '[{"assets":[0],"return":0.08,"confidence":0.6}]',
    risk_aversion: 2.5
  },
},

"portfolio.risk_parity_v2": {
  domain: "portfolio",
  action: "risk_parity_v2",
  description: "Risk Parity 优化：等风险贡献分配，或自定义目标风险贡献。使用 quantlib v2 实现。",
  params: {
    symbols: { required: true, type: "string" },
    target_risk: { type: "string" },       // "0.4,0.3,0.3" 自定义风险贡献
    target_volatility: { type: "number" }, // 目标组合波动率
    start_date: { type: "string" },
    end_date: { type: "string" },
  },
  example: { symbols: "600519,000858,601318", target_volatility: 0.15 },
},

"portfolio.efficient_frontier": {
  domain: "portfolio",
  action: "efficient_frontier",
  description: "计算并返回有效前沿：风险-收益曲线上的最优组合集合。",
  params: {
    symbols: { required: true, type: "string" },
    n_portfolios: { type: "integer" },     // 前沿上采样点数
    risk_free_rate: { type: "number" },
    start_date: { type: "string" },
    end_date: { type: "string" },
  },
  example: { symbols: "600519,000858,601318", n_portfolios: 50 },
},
```

### 3. 验收标准

- [ ] Agent 可以通过 `portfolio.markowitz(objective="max_sharpe")` 获得最优权重
- [ ] Agent 可以通过 `portfolio.black_litterman(views=...)` 注入主观观点并得到融合后的权重
- [ ] Agent 可以通过 `portfolio.risk_parity_v2` 得到等风险贡献权重
- [ ] 返回结果包含每个 symbol 的权重映射 + 组合风险/收益指标
- [ ] 旧 `portfolio.optimize` 命令不受影响

### 4. 测试用例

```
# 用例 1: Markowitz 最大夏普
quant_cli({
  command: "portfolio.markowitz",
  params: { symbols: "600519,000858,002415", objective: "max_sharpe", risk_free_rate: 0.02 }
})
期望: 返回 {"symbols": [...], "weights_map": {"600519": 0.35, ...}, "expected_return": 0.12, "risk": 0.18, "sharpe": 0.56}

# 用例 2: Black-Litterman with view
quant_cli({
  command: "portfolio.black_litterman",
  params: {
    symbols: "600519,000858",
    views: '[{"assets":[0],"return":0.10,"confidence":0.7}]',  // 看好茅台跑赢 10%
    market_weights: "0.5,0.5"
  }
})
期望: 后验权重偏向前者（大于 0.5）

# 用例 3: Risk Parity
quant_cli({
  command: "portfolio.risk_parity_v2",
  params: { symbols: "600519,000858,601318" }
})
期望: 各标的的风险贡献度接近均等
```

---

## P0-2: LSTM / Transformer 深度学习模型

### 1. 现有代码

| 文件 | 内容 |
|------|------|
| `quantlib/ml/lstm_predictor.py` | `LSTMPredictor` — predict(features), predict_proba, prepare_sequences, get_feature_importance |
| `quantlib/ml/transformer_predictor.py` | `TransformerPredictor` — predict, predict_proba, get_attention_weights |
| `quantlib/ml/feature_engineering.py` | `FeatureEngineeringCalculator` — 特征工程 |
| `quantlib/ml/return_prediction.py` | `ReturnPredictionCalculator` — 多模型集成预测 |

**model_train 当前调用链**:
```
model_train tool (TS)
  → callQuantSysDaemon("train_model", {model_type: "xgboost"})
    → /api/training/start
      → services.ml_pipeline.trainer.MLTrainer  ← 只支持 xgboost/lightgbm
```

### 2. 改造策略: 扩展 training 端点

#### Step 2.1: 创建 DL 训练器 — `quantsys-v2/services/ml_pipeline/dl_trainer.py`

新建文件，封装 LSTM/Transformer 的训练流程：

```python
"""
Deep Learning Trainer for LSTM and Transformer models.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any
from quantlib.ml import LSTMPredictor, TransformerPredictor

class DLModelTrainer:
    def __init__(self, model_type: str = 'lstm', **hyperparams):
        self.model_type = model_type
        self.hyperparams = hyperparams
    
    def train(self, X: np.ndarray, y: np.ndarray, val_split: float = 0.2) -> Dict[str, Any]:
        """训练深度学习模型"""
        if self.model_type == 'lstm':
            model = LSTMPredictor(
                input_size=X.shape[2],
                hidden_size=self.hyperparams.get('hidden_size', 64),
                num_layers=self.hyperparams.get('num_layers', 2),
                dropout=self.hyperparams.get('dropout', 0.2),
                sequence_length=X.shape[1]
            )
        elif self.model_type == 'transformer':
            model = TransformerPredictor(
                input_size=X.shape[2],
                d_model=self.hyperparams.get('d_model', 128),
                nhead=self.hyperparams.get('nhead', 8),
                num_layers=self.hyperparams.get('num_layers', 3),
                sequence_length=X.shape[1]
            )
        
        # 训练逻辑 (如果 PyTorch 可用)
        # ...
        
        return {
            'model_type': self.model_type,
            'architecture': self._get_arch_summary(model),
            # ...
        }
```

#### Step 2.2: 扩展训练路由 — `quantsys-v2/api/routes/training.py`

修改 `training_start()` 函数，在 `model_type` 为 `"lstm"` 或 `"transformer"` 时分流：

```python
if model_type in ('lstm', 'transformer'):
    # 使用 DL 训练器
    from services.ml_pipeline.dl_trainer import DLModelTrainer
    
    # 准备序列数据
    lstm_predictor = LSTMPredictor(sequence_length=20)
    X_seq, y_seq = lstm_predictor.prepare_sequences(features_df, target_col='roc_5')
    
    trainer = DLModelTrainer(model_type=model_type, **data.get('hyperparams', {}))
    training_results = trainer.train(X_seq, y_seq)
else:
    # 现有 XGBoost/LightGBM 路径（不变）
    trainer = MLTrainer(model_type=model_type)
    training_results = trainer.train(scaled_features, target, ...)
```

#### Step 2.3: 扩展 model_train 工具 — `src/infrastructure/tools/model/train-tool.ts`

修改 `TrainModelParams` 接口：

```typescript
interface TrainModelParams {
  model_type?: "xgboost" | "lightgbm" | "lstm" | "transformer";  // 新增 lstm, transformer
  days?: number;
  future_days?: number;
  return_threshold?: number;
  symbols?: string[];
  cv_splits?: number;
  hyperparams?: {                        // 新增：深度学习超参数
    hidden_size?: number;                // LSTM 隐藏层维度 (默认 64)
    num_layers?: number;                 // 层数 (默认 2)
    d_model?: number;                    // Transformer 模型维度 (默认 128)
    nhead?: number;                      // 注意力头数 (默认 8)
    dropout?: number;                    // Dropout (默认 0.2)
  };
}
```

### 3. 验收标准

- [ ] `model_train(model_type="lstm")` 成功训练 LSTM 并返回报告
- [ ] `model_train(model_type="transformer")` 成功训练 Transformer 并返回报告
- [ ] 训练报告格式与现有 xgboost/lightgbm 一致（metrics, cv_results, feature_importance）
- [ ] PyTorch 不可用时返回明确错误信息（不崩溃）
- [ ] 现有 model_predict 工具可以加载 DL 模型做预测

### 4. 注意事项

- **PyTorch 依赖**: 需要确认服务器环境安装了 PyTorch。`LSTMPredictor` 和 `TransformerPredictor` 代码中已经有 `try/except` 优雅降级，但训练需要完整 PyTorch
- **训练时间**: LSTM/Transformer 训练时间远长于 XGBoost，建议设置超时
- **数据量要求**: 深度学习需要更多样本（建议 days >= 365）
- **GPU**: 如果环境有 CUDA GPU，Trainer 应自动检测并使用

---

## 跨模块关注点

### 命令命名规范

| 层级 | 命名格式 | 示例 |
|------|---------|------|
| L1 数据 | `data_*` | `data_fetch_stock` |
| L2 因子 | `factor_*` | `factor_calculate` |
| L3 模型 | `model_*` | `model_train` |
| **quant_cli** | `domain.action` | `timeseries.arima`, `portfolio.markowitz` |

新的 quant_cli 命令按现有 `domain.action` 格式添加，与已有 80+ 命令一致。

### 数据管线依赖

建议实现**函数封装**避免在每个 API 路由中重复编写"获取 K 线 → 计算收益率 → 构建矩阵"的逻辑：

```python
# quantsys-v2/api/shared/data_utils.py

def get_returns_matrix(symbols: list, start_date: str, end_date: str) -> pd.DataFrame:
    """获取多标的日收益率矩阵"""
    ...

def get_price_series(symbol: str, start_date: str, end_date: str) -> pd.Series:
    """获取单标的价格序列"""
    ...
```

### 错误处理标准

所有新 API 端点必须：
1. 使用 `@handle_api_error` 装饰器
2. 返回格式与现有 `api_response()` 一致：`{"success": true, "data": {...}}` 或 `{"success": false, "error": "..."}`
3. 参数验证放在端点入口处

### 工作量估算

| 模块 | 新建文件数 | 修改文件数 | 预估工时 |
|------|----------|----------|---------|
| P0-3 时间序列 | 1 (`timeseries.py` route) | 1 (`server.py`), 1 (`quant-cli-tool.ts`) | 4h |
| P0-4 因子模型 | 1 (`factor_models.py` route) | 1 (`server.py`), 1 (`quant-cli-tool.ts`) | 6h (因子自建逻辑复杂) |
| P0-1 投组优化 | 1 (`portfolio_v2.py` route) | 1 (`server.py`), 1 (`quant-cli-tool.ts`) | 4h |
| P0-2 DL 训练 | 1 (`dl_trainer.py`) | 1 (`training.py`), 1 (`train-tool.ts`) | 8h (训练逻辑最复杂) |
| 公共工具 | 1 (`data_utils.py`) | 0 | 2h |
| **总计** | **5 个新文件** | **5 个修改文件** | **~24h** |

### 实现顺序建议

```
Day 1: P0-3 (时间序列) — 最快、最独立、立即可用
Day 2: P0-4 (因子模型) — 中等复杂度、需要因子自建
Day 3: P0-1 (投组优化) — 需要改已有端点，小心兼容性
Day 4: P0-2 (DL 训练) — 最复杂、依赖 PyTorch 环境
```
