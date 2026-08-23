# quantlib 重构实施方案

**制定日期**: 2026-08-23  
**目标**: 解决 quantlib 占 domain 层 78% 代码、职责边界模糊的问题  
**影响范围**: domain/quantlib (209 文件), application/ (40+ 文件), adapters/ (若干文件)

---

## 执行摘要

### 问题诊断

1. **体积过大**: 209 文件（占 domain 层 78%）
2. **职责混乱**: 既有业务逻辑（回测引擎）又有纯技术计算（统计函数）
3. **层次违规**: quantlib/adapters, quantlib/engine 导入外部层
4. **边界模糊**: 27 个子模块职责重叠

### 推荐方案

**方案 B（渐进式重构）** - 平衡风险与收益

- 将业务逻辑部分提升为独立领域
- 纯技术计算保留在 domain/quantlib
- 基础设施部分下沉到 infrastructure
- 分 3 个阶段，每阶段独立验证

**预计工作量**: 2-3 周  
**风险等级**: 中等（渐进式，可回滚）

---

## 一、现状分析

### 1.1 quantlib 子模块统计

| 分类 | 子模块 | 文件数 | 性质 | 建议 |
|------|--------|--------|------|------|
| 回测引擎 | engine, backtest, stages, pipeline | 71 | 业务逻辑 | 提升为独立领域 |
| 风险管理 | risk | 20 | 业务逻辑 | 提升为独立领域 |
| 因子系统 | factors, factor_analysis, factor_models, alternative_factors | 24 | 业务逻辑 | 提升为独立领域 |
| 机器学习 | ml, rl, finrl, qlib | 23 | 技术能力 | 保留或独立库 |
| 资产类别 | derivatives, futures, fixed_income | 24 | 业务逻辑 | 合并到定价领域 |
| 投资组合 | portfolio, cross_asset_strategies, hft_strategies | 11 | 业务逻辑 | 合并到策略领域 |
| 纯技术计算 | statistics, technical, timeseries, gpu_acceleration, tools | 14 | 技术工具 | 保留在 quantlib |
| 基础设施 | core, adapters | 16 | 基础设施 | 下沉到 infrastructure |
| 示例 | examples | 1 | 文档 | 移到 docs/examples |

### 1.2 外部依赖分析

**被外部使用最多的模块**（需重点关注兼容性）:

1. **quantlib.factors** - 40 个文件使用
2. **quantlib.stages** - 17 个文件使用
3. **quantlib.engine** - 16 个文件使用
4. **quantlib.adapters** - 4 个文件使用
5. **quantlib.core** - 3 个文件使用

### 1.3 架构违规

**quantlib 内部对外层的依赖**:

- `quantlib/adapters` → 依赖 infrastructure + adapters 层
- `quantlib/core` → 依赖 infrastructure 层
- `quantlib/engine` → 依赖 adapters + application 层
- `quantlib/stages` → 依赖 adapters 层

---

## 二、重构方案对比

### 方案 A: 激进式 - 完全拆分

```
# 拆分后的结构
domain/
├── strategies/
├── brokers/
├── chan/
├── chip_distribution/
├── memory/
├── benchmarks/
├── backtest/          # 从 quantlib 拆出
├── risk/              # 从 quantlib 拆出
├── factors/           # 从 quantlib 拆出
├── pricing/           # 从 quantlib 拆出（derivatives, futures, fixed_income）
└── ports/

libs/
└── quantlib/          # 纯技术计算库
    ├── statistics/
    ├── technical/
    ├── timeseries/
    ├── ml/
    └── ...
```

**优点**:
- ✅ 彻底解决问题，领域边界清晰
- ✅ 每个领域职责单一
- ✅ 技术库可独立版本管理

**缺点**:
- ❌ 工作量大（3-4 周）
- ❌ 影响面广（需修改 100+ 文件）
- ❌ 风险高（一次性大重构）
- ❌ 需要解决大量导入路径变更

### 方案 B: 渐进式 - 分层重组 ✅ **推荐**

```
# 第一阶段：下沉基础设施
infrastructure/
└── quantlib/
    ├── adapters/      # 从 domain/quantlib 移动
    └── core/          # 从 domain/quantlib 移动

# 第二阶段：提升业务领域
domain/
├── backtest/          # 从 quantlib 提升
│   ├── engine/
│   ├── stages/
│   └── pipeline/
├── risk/              # 从 quantlib 提升
└── factors/           # 从 quantlib 提升

# 第三阶段：精简 quantlib
domain/
└── quantlib/          # 保留纯技术计算
    ├── statistics/
    ├── technical/
    ├── timeseries/
    ├── ml/            # 可选：保留或外移
    └── ...
```

**优点**:
- ✅ 分阶段实施，风险可控
- ✅ 每阶段独立验证，可回滚
- ✅ 渐进式迁移导入路径
- ✅ 工作量适中（2-3 周）

**缺点**:
- ⚠️  需要经历中间过渡状态
- ⚠️  需要维护兼容性层

### 方案 C: 保守式 - 就地重组

```
domain/
└── quantlib/
    ├── business/      # 业务逻辑子包
    │   ├── backtest/
    │   ├── risk/
    │   └── factors/
    ├── technical/     # 技术计算子包
    │   ├── statistics/
    │   ├── ml/
    │   └── timeseries/
    └── infra/         # 基础设施子包
        ├── core/
        └── adapters/
```

**优点**:
- ✅ 工作量最小（1 周）
- ✅ 不改变外部导入路径
- ✅ 风险最低

**缺点**:
- ❌ 治标不治本，quantlib 仍然庞大
- ❌ 没有解决层次违规问题
- ❌ 领域边界仍然不清晰

---

## 三、推荐方案详细设计（方案 B）

### 3.1 总体架构

```
quantsys-v2/
├── domain/
│   ├── strategies/           # 保持不变
│   ├── brokers/              # 保持不变
│   ├── chan/                 # 保持不变
│   ├── chip_distribution/    # 保持不变
│   ├── memory/               # 保持不变
│   ├── benchmarks/           # 保持不变
│   │
│   ├── backtest/             # 新增：回测领域
│   │   ├── __init__.py
│   │   ├── engine/           # 从 quantlib.engine 移动
│   │   ├── stages/           # 从 quantlib.stages 移动
│   │   ├── pipeline/         # 从 quantlib.pipeline 移动
│   │   └── backtest/         # 从 quantlib.backtest 移动
│   │
│   ├── risk/                 # 新增：风险管理领域
│   │   └── (从 quantlib.risk 移动)
│   │
│   ├── factors/              # 新增：因子领域
│   │   ├── __init__.py
│   │   ├── library/          # 从 quantlib.factors 移动
│   │   ├── analysis/         # 从 quantlib.factor_analysis 移动
│   │   ├── models/           # 从 quantlib.factor_models 移动
│   │   └── alternative/      # 从 quantlib.alternative_factors 移动
│   │
│   ├── quantlib/             # 精简后：纯技术计算库
│   │   ├── statistics/       # 保留
│   │   ├── technical/        # 保留
│   │   ├── timeseries/       # 保留
│   │   ├── ml/               # 保留（或外移）
│   │   ├── derivatives/      # 保留（定价模型）
│   │   ├── fixed_income/     # 保留
│   │   ├── portfolio/        # 保留（组合优化算法）
│   │   └── gpu_acceleration/ # 保留
│   │
│   └── ports/                # 保持不变
│
├── infrastructure/
│   └── quantlib/             # 新增：quantlib 基础设施
│       ├── adapters/         # 从 domain/quantlib.adapters 移动
│       └── core/             # 从 domain/quantlib.core 移动
│
└── application/
    └── services/
        └── (需更新导入路径)
```

### 3.2 领域划分原则

#### backtest 领域（回测领域）

**职责**: 策略回测的完整流程

**包含**:
- `engine/` - 回测引擎核心逻辑
- `stages/` - 回测阶段（数据准备、信号生成、执行、评估）
- `pipeline/` - 回测流水线
- `backtest/` - 回测基础类

**对外接口**:
```python
from domain.backtest import BacktestEngine, BacktestConfig
from domain.backtest.stages import DataStage, SignalStage, ExecutionStage
```

**理由**: 回测是完整的业务流程，涉及多个阶段的协调，属于业务逻辑而非技术工具。

#### risk 领域（风险管理领域）

**职责**: 风险度量、控制和报告

**包含**:
- 风险指标计算（VaR, CVaR, Sharpe, etc.）
- 风险限额管理
- 风险预警

**对外接口**:
```python
from domain.risk import RiskCalculator, RiskMetrics, RiskLimit
```

**理由**: 风险管理是独立的业务能力，有自己的业务规则和策略。

#### factors 领域（因子领域）

**职责**: 因子计算、分析和管理

**包含**:
- `library/` - 因子库（技术、基本面、另类因子）
- `analysis/` - 因子分析（IC, IR, 分层回测）
- `models/` - 因子模型（Fama-French, Barra）
- `alternative/` - 另类因子

**对外接口**:
```python
from domain.factors import FactorLibrary, FactorAnalyzer
from domain.factors.library import MomentumFactor, ValueFactor
```

**理由**: 因子是量化投资的核心概念，因子的选择、组合、权重分配是业务决策。

#### quantlib（精简后）

**职责**: 纯技术计算工具

**保留内容**:
- `statistics/` - 统计函数（均值、方差、相关性等）
- `technical/` - 技术指标（MA, MACD, RSI等）
- `timeseries/` - 时间序列工具
- `derivatives/` - 衍生品定价模型（Black-Scholes等）
- `fixed_income/` - 固定收益计算（久期、凸性等）
- `portfolio/` - 组合优化算法（均值方差优化等）
- `ml/` - 机器学习工具（特征工程、模型封装）
- `gpu_acceleration/` - GPU 加速

**对外接口**:
```python
from domain.quantlib.statistics import mean, std, correlation
from domain.quantlib.technical import SMA, MACD, RSI
from domain.quantlib.derivatives import black_scholes
```

**理由**: 这些是纯数学计算，没有业务决策，类似 NumPy、SciPy 的定位。

---

## 四、实施计划

### 阶段 0: 准备工作（1 天）

**目标**: 建立安全网和测试基线

#### 任务清单

- [ ] 建立完整的测试基线
  ```bash
  cd quantsys-v2
  pytest tests/ -v --tb=short > baseline_tests.log 2>&1
  ```

- [ ] 记录当前导入路径
  ```bash
  grep -r "from domain.quantlib" application/ adapters/ > import_baseline.txt
  ```

- [ ] 创建 feature 分支
  ```bash
  git checkout -b refactor/quantlib-restructure
  ```

- [ ] 备份当前 quantlib
  ```bash
  cp -r domain/quantlib domain/quantlib.backup
  ```

- [ ] 建立架构测试
  ```python
  # tests/architecture/test_quantlib_boundaries.py
  def test_quantlib_size():
      """quantlib 不应超过 domain 层 50% 的代码"""
      assert quantlib_file_count / total_domain_files < 0.5
  ```

---

### 阶段 1: 下沉基础设施（3-4 天）

**目标**: 将 quantlib 的基础设施部分移到 infrastructure 层

#### 1.1 移动 adapters（1 天）

```bash
# 1. 创建目标目录
mkdir -p infrastructure/quantlib

# 2. 移动 adapters
git mv domain/quantlib/adapters infrastructure/quantlib/

# 3. 更新 __init__.py
cat > infrastructure/quantlib/__init__.py << 'EOF'
"""
Quantlib infrastructure components
"""
from .adapters import *
EOF
```

**更新导入路径**:
```python
# 修改前
from domain.quantlib.adapters import FactorCalculatorAdapter

# 修改后
from infrastructure.quantlib.adapters import FactorCalculatorAdapter
```

**影响文件**: 4 个外部文件
- application/services/opportunity_scoring_service.py
- application/services/factor_layering_service.py
- application/services/ml_pipeline/feature_engineering.py

#### 1.2 移动 core（1 天）

```bash
# 移动 core
git mv domain/quantlib/core infrastructure/quantlib/
```

**更新导入路径**:
```python
# 修改前
from domain.quantlib.core import PortfolioCalculator

# 修改后
from infrastructure.quantlib.core import PortfolioCalculator
```

**影响文件**: 3 个外部文件

#### 1.3 建立兼容性层（可选，1 天）

如果影响面太大，可以先建立兼容性层：

```python
# domain/quantlib/adapters/__init__.py
"""
DEPRECATED: 此模块已移至 infrastructure.quantlib.adapters
为保持兼容性临时保留，将在 v3.0 移除
"""
import warnings
from infrastructure.quantlib.adapters import *  # noqa: F401, F403

warnings.warn(
    "domain.quantlib.adapters 已废弃，请使用 infrastructure.quantlib.adapters",
    DeprecationWarning,
    stacklevel=2
)
```

#### 1.4 验证（1 天）

```bash
# 运行测试
pytest tests/ -v

# 检查导入
python -c "from infrastructure.quantlib.adapters import FactorCalculatorAdapter"

# 架构测试
pytest tests/architecture/test_layer_boundaries.py
```

---

### 阶段 2: 提升业务领域（7-10 天）

**目标**: 将业务逻辑部分提升为独立领域

#### 2.1 提升 backtest 领域（3-4 天）

##### 步骤 1: 创建领域结构

```bash
# 1. 创建 backtest 领域
mkdir -p domain/backtest

# 2. 移动相关模块
git mv domain/quantlib/engine domain/backtest/
git mv domain/quantlib/stages domain/backtest/
git mv domain/quantlib/pipeline domain/backtest/
git mv domain/quantlib/backtest domain/backtest/core

# 3. 创建领域 __init__.py
cat > domain/backtest/__init__.py << 'EOF'
"""
回测领域 (Backtest Domain)

职责：
- 策略回测引擎
- 回测阶段管理
- 回测流水线
- 回测结果评估

核心接口：
- BacktestEngine: 回测引擎
- BacktestConfig: 回测配置
- BacktestResult: 回测结果
"""
from .engine import BacktestEngine
from .core import BacktestConfig, BacktestResult
from .stages import DataStage, SignalStage, ExecutionStage

__all__ = [
    'BacktestEngine',
    'BacktestConfig',
    'BacktestResult',
    'DataStage',
    'SignalStage',
    'ExecutionStage',
]
EOF
```

##### 步骤 2: 清理违规依赖

```bash
# 检查 backtest 领域的外部依赖
grep -r "from application" domain/backtest/
grep -r "from adapters" domain/backtest/
grep -r "from infrastructure" domain/backtest/
```

**修复示例**:
```python
# 修改前: domain/backtest/engine/backtest_report.py
from application.services.risk_metrics_service import RiskMetricsService

# 修改后: 使用依赖注入
class BacktestEngine:
    def __init__(self, risk_service: RiskMetricsServicePort):
        self.risk_service = risk_service
```

##### 步骤 3: 更新外部导入

影响文件：16 个 application 文件

```python
# 修改前
from domain.quantlib.engine import BacktestEngine
from domain.quantlib.stages import DataStage

# 修改后
from domain.backtest import BacktestEngine
from domain.backtest.stages import DataStage
```

##### 步骤 4: 验证

```bash
# 单元测试
pytest tests/domain/test_backtest*.py -v

# 集成测试
pytest tests/test_backtest*.py -v

# 回归测试
python scripts/run_backtest_regression.py
```

#### 2.2 提升 risk 领域（2 天）

```bash
# 1. 创建 risk 领域
mkdir -p domain/risk

# 2. 移动 risk 模块
git mv domain/quantlib/risk/* domain/risk/

# 3. 创建 __init__.py
cat > domain/risk/__init__.py << 'EOF'
"""
风险管理领域 (Risk Domain)

职责：
- 风险指标计算
- 风险限额管理
- 风险预警

核心接口：
- RiskCalculator: 风险计算器
- RiskMetrics: 风险指标
- RiskLimit: 风险限额
"""
from .calculator import RiskCalculator
from .metrics import RiskMetrics, Sharpe, MaxDrawdown, VaR, CVaR
from .limits import RiskLimit, RiskLimitChecker

__all__ = [
    'RiskCalculator',
    'RiskMetrics',
    'Sharpe',
    'MaxDrawdown',
    'VaR',
    'CVaR',
    'RiskLimit',
    'RiskLimitChecker',
]
EOF
```

**更新导入** (影响 1 个文件):
```python
# 修改前
from domain.quantlib.risk import RiskCalculator

# 修改后
from domain.risk import RiskCalculator
```

#### 2.3 提升 factors 领域（3-4 天）

```bash
# 1. 创建 factors 领域
mkdir -p domain/factors/{library,analysis,models,alternative}

# 2. 移动因子相关模块
git mv domain/quantlib/factors/* domain/factors/library/
git mv domain/quantlib/factor_analysis/* domain/factors/analysis/
git mv domain/quantlib/factor_models/* domain/factors/models/
git mv domain/quantlib/alternative_factors/* domain/factors/alternative/

# 3. 创建 __init__.py
cat > domain/factors/__init__.py << 'EOF'
"""
因子领域 (Factors Domain)

职责：
- 因子计算和管理
- 因子分析（IC, IR, 分层回测）
- 因子模型（Fama-French, Barra）
- 另类因子

核心接口：
- FactorLibrary: 因子库
- FactorAnalyzer: 因子分析器
- FactorModel: 因子模型
"""
from .library import FactorLibrary
from .analysis import FactorAnalyzer, ICAnalyzer, LayeredBacktest
from .models import FamaFrench3Factor, BarraModel

__all__ = [
    'FactorLibrary',
    'FactorAnalyzer',
    'ICAnalyzer',
    'LayeredBacktest',
    'FamaFrench3Factor',
    'BarraModel',
]
EOF
```

**更新导入** (影响 40 个文件):
```python
# 修改前
from domain.quantlib.factors import MomentumFactor, ValueFactor

# 修改后
from domain.factors.library import MomentumFactor, ValueFactor
```

**批量更新脚本**:
```bash
# scripts/update_factor_imports.sh
find application adapters -name "*.py" -exec sed -i '' \
  's/from domain\.quantlib\.factors/from domain.factors.library/g' {} \;
find application adapters -name "*.py" -exec sed -i '' \
  's/from domain\.quantlib\.factor_analysis/from domain.factors.analysis/g' {} \;
```

---

### 阶段 3: 精简 quantlib（2-3 天）

**目标**: 清理和优化剩余的 quantlib

#### 3.1 删除已迁移模块（1 天）

```bash
# 删除已移走的目录（确保已在 git mv 中完成）
# 此时应该只剩下纯技术计算模块

# 检查剩余内容
ls domain/quantlib/
# 预期输出：
# statistics/
# technical/
# timeseries/
# ml/
# derivatives/
# fixed_income/
# portfolio/
# gpu_acceleration/
# rl/
# finrl/
# qlib/
# examples/
```

#### 3.2 重组 quantlib __init__.py（1 天）

```python
# domain/quantlib/__init__.py
"""
Quantlib - 量化计算工具库

纯技术计算工具，不包含业务逻辑。
类似 NumPy、SciPy 的定位。

模块分类：
- statistics: 统计函数
- technical: 技术指标
- timeseries: 时间序列工具
- derivatives: 衍生品定价
- fixed_income: 固定收益计算
- portfolio: 组合优化算法
- ml: 机器学习工具
"""

# 统计模块
from .statistics import mean, std, correlation, covariance

# 技术指标
from .technical import SMA, EMA, MACD, RSI, BOLL

# 时间序列
from .timeseries import resample, fill_missing, align

# 衍生品定价
from .derivatives import black_scholes, implied_volatility

# 固定收益
from .fixed_income import duration, convexity, ytm

# 组合优化
from .portfolio import mean_variance_optimization, risk_parity

__all__ = [
    # Statistics
    'mean', 'std', 'correlation', 'covariance',
    # Technical
    'SMA', 'EMA', 'MACD', 'RSI', 'BOLL',
    # Timeseries
    'resample', 'fill_missing', 'align',
    # Derivatives
    'black_scholes', 'implied_volatility',
    # Fixed Income
    'duration', 'convexity', 'ytm',
    # Portfolio
    'mean_variance_optimization', 'risk_parity',
]
```

#### 3.3 处理 ML 模块（可选，1 天）

**选项 A: 保留在 quantlib**
```python
# domain/quantlib/ml/ 保持不变
from domain.quantlib.ml import FeatureEngineering, ModelWrapper
```

**选项 B: 外移到独立库**
```bash
# 创建独立的 ML 工具库项目
mkdir -p ../quantml
git mv domain/quantlib/ml ../quantml/
git mv domain/quantlib/rl ../quantml/
git mv domain/quantlib/finrl ../quantml/
git mv domain/quantlib/qlib ../quantml/

# 作为独立依赖
# pyproject.toml
[tool.poetry.dependencies]
quantml = {path = "../quantml", develop = true}
```

**推荐**: 先保留在 quantlib，等稳定后再考虑外移。

#### 3.4 清理示例代码（0.5 天）

```bash
# 移动示例到 docs
mkdir -p docs/examples/quantlib
git mv domain/quantlib/examples/* docs/examples/quantlib/

# 删除空目录
rm -rf domain/quantlib/examples
```

---

### 阶段 4: 验证与优化（2-3 天）

#### 4.1 完整测试（1 天）

```bash
# 1. 单元测试
pytest tests/ -v --cov=domain --cov=application --cov=infrastructure

# 2. 集成测试
pytest tests/integration/ -v

# 3. 回归测试
pytest tests/regression/ -v

# 4. 架构测试
pytest tests/architecture/ -v
```

#### 4.2 性能测试（0.5 天）

```bash
# 对比重构前后性能
python scripts/benchmark_before_after.py
```

预期：性能不应有明显下降（±5% 以内）

#### 4.3 文档更新（1 天）

更新以下文档：
- [ ] `quantsys-v2/CLAUDE.md` - 更新架构说明
- [ ] `domain/backtest/README.md` - 新增回测领域文档
- [ ] `domain/risk/README.md` - 新增风险领域文档
- [ ] `domain/factors/README.md` - 新增因子领域文档
- [ ] `domain/quantlib/README.md` - 更新 quantlib 定位说明
- [ ] `docs/architecture/domain-structure.md` - 更新领域结构文档

#### 4.4 迁移指南（0.5 天）

创建迁移指南帮助开发者更新代码：

```markdown
# quantlib 重构迁移指南

## 导入路径变更

| 旧路径 | 新路径 | 说明 |
|--------|--------|------|
| `domain.quantlib.engine` | `domain.backtest` | 回测引擎 |
| `domain.quantlib.stages` | `domain.backtest.stages` | 回测阶段 |
| `domain.quantlib.risk` | `domain.risk` | 风险管理 |
| `domain.quantlib.factors` | `domain.factors.library` | 因子库 |
| `domain.quantlib.factor_analysis` | `domain.factors.analysis` | 因子分析 |
| `domain.quantlib.adapters` | `infrastructure.quantlib.adapters` | 适配器 |
| `domain.quantlib.core` | `infrastructure.quantlib.core` | 核心基础设施 |

## 批量更新脚本

\`\`\`bash
# 运行自动更新脚本
python scripts/migrate_quantlib_imports.py --dry-run
python scripts/migrate_quantlib_imports.py --apply
\`\`\`

## 兼容性

- v2.8: 保留兼容性层，旧导入路径会触发 DeprecationWarning
- v2.9: 兼容性层继续保留
- v3.0: 删除兼容性层，旧导入路径会报 ImportError
```

---

## 五、风险控制

### 5.1 风险识别

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|---------|
| 测试覆盖不足，遗漏 bug | 中 | 高 | 建立测试基线，每阶段回归测试 |
| 导入路径遗漏，运行时报错 | 高 | 中 | 静态分析工具 + 全量运行测试 |
| 性能下降 | 低 | 中 | 性能基准测试对比 |
| 并行开发冲突 | 中 | 中 | 在独立分支进行，减少合并窗口 |
| 依赖循环引入 | 低 | 高 | 架构测试 + code review |

### 5.2 回滚计划

每个阶段完成后打 tag，出现问题立即回滚：

```bash
# 阶段 1 完成后
git tag refactor/quantlib-phase1
git push origin refactor/quantlib-phase1

# 如需回滚
git reset --hard refactor/quantlib-phase1
```

### 5.3 灰度发布

```python
# config.py
ENABLE_NEW_DOMAIN_STRUCTURE = os.getenv('USE_NEW_DOMAINS', 'false').lower() == 'true'

if ENABLE_NEW_DOMAIN_STRUCTURE:
    from domain.backtest import BacktestEngine
else:
    from domain.quantlib.engine import BacktestEngine
```

---

## 六、成功标准

### 6.1 定量指标

- [ ] quantlib 文件数 < 100（当前 209）
- [ ] quantlib 占 domain 层比例 < 40%（当前 78%）
- [ ] domain 层架构违规 = 0（当前 24）
- [ ] 测试覆盖率 > 80%
- [ ] 性能下降 < 5%

### 6.2 定性指标

- [ ] 每个领域职责清晰，可用一句话描述
- [ ] domain 层无外部依赖（除 ports）
- [ ] 新增功能有明确的归属领域
- [ ] 开发者能快速定位代码位置

---

## 七、时间线

| 阶段 | 任务 | 工作量 | 负责人 | 开始日期 | 完成日期 |
|------|------|--------|--------|----------|----------|
| Phase 0 | 准备工作 | 1 天 | TBD | 2026-08-26 | 2026-08-26 |
| Phase 1 | 下沉基础设施 | 3-4 天 | TBD | 2026-08-27 | 2026-08-30 |
| Phase 2 | 提升业务领域 | 7-10 天 | TBD | 2026-09-02 | 2026-09-13 |
| Phase 3 | 精简 quantlib | 2-3 天 | TBD | 2026-09-16 | 2026-09-18 |
| Phase 4 | 验证与优化 | 2-3 天 | TBD | 2026-09-19 | 2026-09-23 |
| **总计** |  | **15-21 天** |  | **2026-08-26** | **2026-09-23** |

---

## 八、后续优化（P2）

完成基本重构后，可以考虑进一步优化：

### 8.1 ML 模块独立化

将 `domain/quantlib/ml` 外移为独立库 `quantml`:
- 独立版本管理
- 可供其他项目使用
- 减少 quantsys-v2 复杂度

### 8.2 quantlib 发布为 PyPI 包

```bash
# 将 domain/quantlib 发布为独立包
pip install quantlib-py
```

好处：
- 版本独立管理
- 社区贡献
- 其他项目复用

### 8.3 定价模块独立领域

如果 derivatives/fixed_income/futures 未来扩展复杂，可考虑：
```
domain/
└── pricing/
    ├── derivatives/
    ├── fixed_income/
    └── futures/
```

---

## 九、FAQ

### Q1: 为什么不一次性完全拆分？

**A**: 渐进式重构风险更可控：
- 每阶段独立验证，可回滚
- 分散影响，避免"大爆炸"
- 团队有学习曲线

### Q2: 兼容性层会保留多久？

**A**: 
- v2.8: 引入新结构 + 兼容性层（DeprecationWarning）
- v2.9: 兼容性层继续保留
- v3.0: 删除兼容性层（强制迁移）

约 6-12 个月的迁移窗口期。

### Q3: 如果外部项目依赖 quantlib 怎么办？

**A**: 
1. 先不发布为 PyPI 包，保持内部使用
2. 如有外部依赖，建立兼容性层
3. 发布独立 quantlib-py 包（仅包含技术计算部分）

### Q4: 重构期间如何并行开发新功能？

**A**:
1. 在 feature 分支进行重构
2. 主分支正常开发
3. 每周从 main 合并到 feature 分支
4. 完成后一次性合并回 main

### Q5: 测试不通过怎么办？

**A**:
1. 修复明显的导入路径问题
2. 如果是业务逻辑 bug，回滚该阶段
3. 建立 issue，标记为 P0 bug
4. 修复后重新开始该阶段

---

## 十、总结

### 核心价值

1. **领域边界清晰**: 从 1 个臃肿领域变为 3 个清晰领域 + 1 个技术库
2. **职责单一**: 每个领域可用一句话描述
3. **架构健康**: 消除 domain 层违规
4. **可维护性**: 新功能有明确归属

### 关键成功因素

1. ✅ **渐进式**: 分阶段实施，风险可控
2. ✅ **测试先行**: 每阶段独立验证
3. ✅ **兼容性层**: 平滑过渡
4. ✅ **文档完善**: 迁移指南 + 架构文档

### 预期成果

**重构前**:
```
domain/
└── quantlib/ (209 文件, 27 子模块, 职责模糊)
```

**重构后**:
```
domain/
├── backtest/        (71 文件, 职责: 策略回测)
├── risk/            (20 文件, 职责: 风险管理)
├── factors/         (24 文件, 职责: 因子计算与分析)
└── quantlib/        (~80 文件, 职责: 纯技术计算)

infrastructure/
└── quantlib/
    ├── adapters/    (7 文件)
    └── core/        (9 文件)
```

**量化指标**:
- quantlib 从 209 文件降至 ~80 文件（↓ 62%）
- domain 层从 9 个目录增至 11 个（清晰的业务领域）
- 架构违规从 24 降至 0（↓ 100%）

---

**相关文档**:
- [领域边界审计报告](./domain-boundary-audit-2026-08.md)
- [领域数量分析](./domain-count-analysis-2026-08.md)
- [CLAUDE.md](../CLAUDE.md) - 项目架构概览

**批准**: 待用户确认后开始执行
