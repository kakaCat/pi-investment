# quantsys-v2 领域架构分析报告

**生成时间**: 2026-08-23  
**重构版本**: Phase 4 完成后  
**分析范围**: domain/ 层

---

## 1. 领域概览

### 1.1 领域列表（按文件数排序）

| 领域 | 文件数 | 占比 | 状态 | 核心职责 |
|------|--------|------|------|----------|
| **quantlib** | 77 | 30.3% | ✅ 重构后 | 纯技术计算库（衍生品、债券、投组优化、时间序列） |
| **backtest** | 72 | 28.3% | ✅ 新独立域 | 策略回测引擎、回测阶段、数据管道 |
| **factors** | 27 | 10.6% | ✅ 新独立域 | 因子库、因子分析、因子模型 |
| **risk** | 20 | 7.9% | ✅ 新独立域 | 风险管理（VaR、CVaR、归因、压力测试） |
| **chan** | 14 | 5.5% | ✅ 业务域 | 缠论分析（K线、分型、笔、段、中枢） |
| **strategies** | 9 | 3.5% | ✅ 业务域 | 策略基类、策略注册表 |
| **brokers** | 9 | 3.5% | ✅ 业务域 | 券商抽象层（接口统一、适配器模式） |
| **benchmarks** | 7 | 2.8% | ✅ 工具域 | 性能基准测试套件 |
| **ports** | 6 | 2.4% | ✅ 接口层 | 领域端口（Repository 接口定义） |
| **memory** | 6 | 2.4% | ✅ 业务域 | Agent 记忆服务（存储、检索） |
| **chip_distribution** | 3 | 1.2% | ✅ 业务域 | 筹码分布计算（成本分布、集中度） |
| **models** | 2 | 0.8% | ✅ 共享层 | 领域模型（共享实体、值对象） |

**总计**: 254 文件，12 个领域

---

## 2. 重构前后对比

### 2.1 文件数量变化

```
重构前（2026-08-23 之前）:
  domain/quantlib       209 文件 ⚠️  职责混杂，占 domain 层 78%
  其他领域               58 文件
  ────────────────────────────────
  总计                  267 文件

重构后（Phase 4 完成）:
  domain/quantlib        77 文件 ✓  ↓63%，纯技术计算
  domain/backtest        72 文件 ✓  新独立域（从 quantlib 拆出）
  domain/factors         27 文件 ✓  新独立域（从 quantlib 拆出）
  domain/risk            20 文件 ✓  新独立域（从 quantlib 拆出）
  其他领域               58 文件
  ────────────────────────────────
  总计                  254 文件    ↓5%
```

### 2.2 架构改善

**重构前的问题**:
- ❌ quantlib 占据 78% 代码量，职责边界模糊
- ❌ 回测、风险、因子混在技术计算中
- ❌ 业务逻辑与技术工具不分离
- ❌ 难以维护和扩展

**重构后的改善**:
- ✅ quantlib 降至 30.3%，职责清晰（纯技术计算）
- ✅ 3 个新业务域独立（backtest/risk/factors）
- ✅ 业务域 vs 技术库边界明确
- ✅ 架构符合 DDD 和六边形架构原则

---

## 3. 各领域详细分析

### 3.1 quantlib（纯技术计算库）

**文件数**: 77  
**定位**: 纯技术计算层，不包含业务逻辑  
**职责**: 提供金融量化计算的基础工具和算法

**子模块结构**:
```
quantlib/
├── derivatives/        (16) - 衍生品定价（期权、波动率曲面、Greeks）
├── ml/                 (10) - 机器学习集成（惰性加载）
├── timeseries/         (8)  - 时间序列分析（ARIMA、GARCH、协整）
├── portfolio/          (7)  - 投资组合优化（均值方差、Black-Litterman）
├── fixed_income/       (7)  - 固定收益（债券定价、久期、凸度）
├── finrl/              (6)  - FinRL 框架集成（惰性加载）
├── qlib/               (4)  - Qlib RL 框架（惰性加载）
├── rl/                 (3)  - 强化学习基础
├── cross_asset_strategies/ (2)
├── hft_strategies/     (2)
├── gpu_acceleration/   (2)
├── technical/          (2)
├── futures/            (1)
├── statistics/         (1)
├── tools/              (1)
└── 核心: base_calculator, data_validator, exceptions
```

**设计亮点**:
- 惰性加载机制（ML/RL 模块）避免重依赖被动引入
- 无 application 层依赖，保持纯技术性
- 基于 BaseCalculator 的统一计算器接口

---

### 3.2 backtest（回测引擎）

**文件数**: 72  
**定位**: 策略回测业务域  
**职责**: 执行策略回测、数据管道、性能报告

**子模块结构**:
```
backtest/
├── engine/             (52) - 回测引擎
│   ├── 52 个策略实现（ADX、布林带、突破、CCI、唐奇安、网格等）
│   ├── indicators/     - 技术指标管理器
│   ├── mixins/         - 因子、指标、ML 混入
│   └── backtrader/     - BackTrader 集成
├── stages/             (14) - 回测阶段
│   └── data_pipeline/  - 数据管道（获取、清洗、因子计算、存储）
├── pipeline/           (3)  - 管道监控、错误处理
└── core/               (2)  - 市场影响、Walk-Forward
```

**架构违规** (遗留问题):
- ⚠️ `backtest_report.py` 依赖 `application.services.risk_metrics_service`
- ⚠️ `ml_mixin.py` 依赖 `application.services.ml_pipeline.predictor`
- **建议**: 通过依赖注入解耦

---

### 3.3 factors（因子计算）

**文件数**: 27  
**定位**: 因子工程业务域  
**职责**: 因子库、因子分析、多因子模型

**子模块结构**:
```
factors/
├── library/            (13) - 因子库
│   ├── momentum        - 动量因子
│   ├── moving_average  - 均线因子
│   ├── trend           - 趋势因子
│   ├── volatility      - 波动率因子
│   ├── volume          - 成交量因子
│   ├── reversal        - 反转因子
│   ├── advanced        - 高级因子
│   ├── cycle           - 周期因子
│   ├── fundamental     - 基本面因子
│   └── pattern_recognition - 形态识别
├── models/             (6)  - 因子模型
│   ├── barra           - BARRA 模型
│   ├── fama_french     - Fama-French 三因子/五因子
│   ├── carhart         - Carhart 四因子
│   └── factor_exposure - 因子暴露计算
├── analysis/           (5)  - 因子分析
│   ├── ic_analyzer     - IC 分析
│   ├── layering_backtest - 分层回测
│   ├── orthogonalizer  - 正交化
│   └── factor_monitor  - 因子监控
└── alternative/        (2)  - 另类因子
    └── sentiment_factors - 情绪因子
```

**设计亮点**:
- 清晰的三层结构：library（计算） → analysis（分析） → models（建模）
- 基于 `TechnicalFactorCalculator` 的统一接口

---

### 3.4 risk（风险管理）

**文件数**: 20  
**定位**: 风险管理业务域  
**职责**: 风险度量、归因分析、压力测试

**模块列表**:
```
risk/
├── var.py              - VaR 计算（历史模拟、参数法、蒙特卡洛）
├── cvar.py             - CVaR（条件风险价值）
├── attribution.py      - 风险归因（因子归因、风格归因）
├── drawdown.py         - 回撤分析（最大回撤、回撤持续期）
├── market_risk.py      - 市场风险
├── stress_test.py      - 压力测试
├── stress_testing.py   - 压力测试框架
├── scenario_analysis.py - 情景分析
├── backtesting.py      - 回测验证
├── risk_monitor.py     - 风险监控
├── extreme_value.py    - 极值理论（EVT）
├── copula.py           - Copula 模型
├── liquidity_risk.py   - 流动性风险
├── counterparty_risk.py - 交易对手风险
├── regulatory.py       - 监管指标（巴塞尔协议）
├── reporting.py        - 风险报告
├── margining.py        - 保证金管理
├── aggregation.py      - 风险聚合
└── examples.py         - 示例代码
```

**设计亮点**:
- `__init__.py` 为空，避免循环导入
- 用户直接从子模块导入：`from domain.risk.var import VaRCalculator`

---

### 3.5 其他业务域

#### chan（缠论分析）
**文件数**: 14  
**职责**: 缠论技术分析（K线、分型、笔、段、中枢、走势类型）

#### strategies（策略基类）
**文件数**: 9  
**职责**: 策略抽象、策略注册表、Signal 信号定义

#### brokers（券商抽象）
**文件数**: 9  
**职责**: 统一券商接口、适配器模式、多券商支持

#### memory（记忆服务）
**文件数**: 6  
**职责**: Agent 记忆存储、检索、管理（支持自我进化）

#### chip_distribution（筹码分布）
**文件数**: 3  
**职责**: 筹码分布计算、成本分布、集中度分析

#### benchmarks（性能基准）
**文件数**: 7  
**职责**: 性能基准测试套件、回归检测

---

## 4. 架构原则遵循情况

### 4.1 依赖倒置原则（DIP）

✅ **端口定义**: `domain/ports/` 定义 Repository 接口  
✅ **接口隔离**: domain 层不依赖 infrastructure 实现  
⚠️ **部分违规**: backtest 依赖 application 层（2 处）

### 4.2 单一职责原则（SRP）

✅ **quantlib**: 纯技术计算  
✅ **backtest**: 回测引擎  
✅ **factors**: 因子工程  
✅ **risk**: 风险管理  
✅ **chan**: 缠论分析  

### 4.3 开放封闭原则（OCP）

✅ **策略扩展**: `StrategyRegistry` 支持动态注册  
✅ **券商扩展**: `BaseBroker` 适配器模式  
✅ **因子扩展**: `TechnicalFactorCalculator` 基类

### 4.4 DDD 战术模式

✅ **聚合根**: Strategy, Portfolio, Signal  
✅ **值对象**: KLine, FenXing, ChipDistribution  
✅ **领域服务**: RiskAttributionCalculator, FactorAnalyzer  
✅ **领域事件**: Signal 信号发布

---

## 5. 当前问题与改进建议

### 5.1 已发现问题

1. **架构违规** (P1)
   - `domain.backtest` 依赖 `application.services`（2 处）
   - **建议**: 通过依赖注入解耦，或将服务下沉到 domain

2. **待评估模块** (P2)
   - `cross_asset_strategies/` (2 文件) - 是否保留？
   - `hft_strategies/` (2 文件) - 是否保留？
   - `futures/` (1 文件) - 是否合并到其他模块？
   - `gpu_acceleration/` (2 文件) - 是否保留？

3. **文档缺失** (P2)
   - 部分领域缺少 README.md
   - 缺少领域间交互图

### 5.2 优化建议

**短期（P1）**:
1. 修复 backtest 的 application 依赖
2. 为主要领域添加 README.md（backtest, factors, risk, chan）
3. 删除 `domain/quantlib.backup/`（2.8M）

**中期（P2）**:
1. 评估并清理待定模块（cross_asset_strategies 等）
2. 统一领域事件机制
3. 添加领域集成测试

**长期（P3）**:
1. 引入聚合根边界保护
2. 实现领域事件溯源
3. 性能优化与缓存策略

---

## 6. 总结

### 6.1 重构成果

✅ **职责清晰**: 从 1 个庞大模块拆分为 12 个职责明确的领域  
✅ **架构改善**: quantlib 占比从 78% 降至 30.3%  
✅ **可维护性**: 业务域独立，便于并行开发  
✅ **可扩展性**: 清晰的接口和抽象层  

### 6.2 领域成熟度

| 领域 | 成熟度 | 说明 |
|------|--------|------|
| quantlib | ⭐⭐⭐⭐ | 重构后职责清晰，技术债务低 |
| backtest | ⭐⭐⭐ | 功能完整，但有架构违规 |
| factors | ⭐⭐⭐⭐ | 结构清晰，三层设计优秀 |
| risk | ⭐⭐⭐⭐ | 模块完整，覆盖全面 |
| chan | ⭐⭐⭐ | 业务域成熟，文档待补充 |
| strategies | ⭐⭐⭐ | 基础扎实，待扩展 |
| brokers | ⭐⭐⭐ | 适配器模式良好 |
| 其他 | ⭐⭐ | 功能性模块，待完善 |

### 6.3 总体评价

**优势**:
- ✅ 领域边界清晰，职责分离良好
- ✅ 重构后架构健康度显著提升
- ✅ 遵循 DDD 和六边形架构原则
- ✅ 技术债务大幅降低

**待改进**:
- ⚠️ 2 处架构违规需修复
- ⚠️ 部分模块文档缺失
- ⚠️ 4 个待评估模块需决策

**推荐等级**: ⭐⭐⭐⭐ (4/5)

---

**报告生成**: 2026-08-23  
**分析基准**: quantlib 重构 Phase 4 完成后  
**下次审查**: 建议 1 个月后（2026-09-23）
