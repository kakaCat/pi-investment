# quantsys-v2 领域数量分析报告

**分析日期**: 2026-08-23  
**分析对象**: quantsys-v2/domain/ 目录结构  
**结论**: **6 个真实业务领域** + 1 个技术工具库（quantlib）

---

## 执行摘要

quantsys-v2 的 `domain/` 目录包含 **9 个顶层子目录**，但并非所有都是真正的业务领域。经过分析，实际有：

- **6 个业务领域**（核心业务 4 个 + 技术支撑 2 个）
- **1 个技术工具库**（quantlib，包含 27 个子模块）
- **2 个基础设施模块**（ports, models）

---

## 一、顶层目录清单（9 个）

| 目录 | 文件数 | 子目录数 | 分类 |
|------|--------|---------|------|
| quantlib/ | 209 | 27 | 技术工具库 |
| chan/ | 14 | 0 | 核心业务领域 |
| brokers/ | 9 | 2 | 核心业务领域 |
| strategies/ | 9 | 0 | 核心业务领域 |
| benchmarks/ | 7 | 1 | 技术支撑领域 |
| memory/ | 6 | 0 | 技术支撑领域 |
| ports/ | 6 | 0 | 基础设施 |
| chip_distribution/ | 3 | 0 | 核心业务领域 |
| models/ | 2 | 0 | 基础设施 |

**总计**: 265 个 Python 文件

---

## 二、领域分类详解

### 2.1 核心业务领域（4 个）

这些是 quantsys-v2 的**核心业务能力**，代表系统解决的主要业务问题。

#### 1. strategies（策略领域）

```
domain/strategies/
├── base_strategy.py          # 策略基类
├── strategy_272.py           # v13 策略实现
├── strategy_273.py           # v14 策略实现
├── strategy_274_ml.py        # ML 策略
├── strategy_factory.py       # 策略工厂
└── strategy_registry.py      # 策略注册表
```

**职责**:
- 定义策略接口和抽象基类
- 实现具体交易策略（v13, v14 等）
- 策略的创建、注册和管理

**业务含义**: 策略是量化系统的核心，定义了"如何交易"的规则。

#### 2. brokers（券商/经纪人领域）

```
domain/brokers/
├── base_broker.py            # 券商接口抽象
├── broker_registry.py        # 券商注册表
├── trading_types.py          # 交易类型定义
├── adapters/
│   └── __init__.py           # 券商适配器（⚠️ 错位）
└── types/
    └── __init__.py           # 类型定义
```

**职责**:
- 定义统一的券商接口（下单、查询、撤单等）
- 管理多券商适配器的注册和切换
- 定义交易相关类型（订单、持仓等）

**业务含义**: 抽象不同券商的交易接口，支持多券商接入。

**问题**: `brokers/adapters/` 和 `broker_registry.py` 导入了 `adapters/` 层的具体实现，违反依赖规则。

#### 3. chan（缠论技术分析领域）

```
domain/chan/
├── bi_divergence_detector.py      # 笔背驰检测
├── bi_identifier.py               # 笔识别
├── bi_trend_analyzer.py           # 笔趋势分析
├── bi_zhongshu_identifier.py      # 笔中枢识别
├── buypoint_detector.py           # 买点检测
├── chan_analyzer.py               # 缠论分析器
├── converter.py                   # 数据转换
├── duan_identifier.py             # 段识别
├── fenxing_identifier.py          # 分型识别
├── kline_merger.py                # K线合并
├── types.py                       # 缠论类型定义
├── utils.py                       # 工具函数
├── zhongshu_identifier.py         # 中枢识别
└── zhongshu_tracker.py            # 中枢跟踪
```

**职责**:
- 实现缠中说禅的技术分析理论
- 识别分型、笔、段、中枢
- 检测买卖点和背驰

**业务含义**: 缠论是一套完整的技术分析方法论，用于辅助交易决策。

**评价**: 这是一个**边界清晰、职责单一**的优秀领域设计案例。

#### 4. chip_distribution（筹码分布领域）

```
domain/chip_distribution/
├── calculator.py             # 筹码计算器
├── service.py                # 筹码服务
└── __init__.py
```

**职责**:
- 计算股票的成本分布
- 分析筹码集中度和获利盘比例
- 支持筹码分布可视化

**业务含义**: 筹码分布是市场微观结构分析的重要工具，反映持仓成本分布。

---

### 2.2 技术支撑领域（2 个）

这些领域提供**跨业务的技术能力**，但仍属于业务相关的领域逻辑。

#### 5. memory（记忆系统领域）

```
domain/memory/
├── distiller.py              # 经验蒸馏（⚠️ 违规）
├── embedding.py              # 向量嵌入（⚠️ 违规）
├── hybrid_search.py          # 混合检索
├── models.py                 # 记忆模型
├── service.py                # 记忆服务（⚠️ 违规）
└── __init__.py
```

**职责**:
- 存储 AI agent 的决策记忆
- 向量化和检索相似经验
- 经验蒸馏和学习

**业务含义**: 支持 agent 的自我进化和经验学习。

**问题**: 多个文件导入 `infrastructure.config` 和 `adapters` 层，破坏了 domain 纯净性。

#### 6. benchmarks（基准测试领域）

```
domain/benchmarks/
├── benchmark_backtest.py            # 回测基准（⚠️ 违规）
├── benchmark_backtest_optimized.py  # 优化版回测
├── benchmark_cache.py               # 缓存基准（⚠️ 违规）
├── benchmark_factors.py             # 因子基准
├── benchmark_ml.py                  # ML 基准
├── run_all_benchmarks.py            # 运行脚本（⚠️ 错位）
└── results/
```

**职责**:
- 定义各类性能基准测试
- 评估回测、因子、ML 模型的性能
- 缓存和管理基准结果

**业务含义**: 量化系统的质量保证，确保算法改进不退化。

**问题**: 
- `benchmark_cache.py` 导入 `infrastructure.config`
- `run_all_benchmarks.py` 导入 `application.services`，应该移到 `scripts/`

---

### 2.3 基础设施模块（2 个）

这两个不是业务领域，而是**架构基础设施**。

#### 7. ports（端口/接口）

```
domain/ports/
├── data_provider_port.py          # 数据提供者接口
├── datasource_ports.py            # 数据源接口
├── ml_model_port.py               # ML 模型接口
├── repository_ports.py            # 仓储接口
└── repository_ports_extended.py   # 扩展仓储接口
```

**职责**: 定义外部依赖的抽象接口（Port），供 domain 层依赖。

**评价**: ✅ **正确的位置**。Domain 层定义接口，外层提供实现，符合依赖倒置原则。

#### 8. models（领域模型）

```
domain/models/
├── market_data.py            # 市场数据模型
└── __init__.py
```

**职责**: 定义跨领域共享的核心领域模型。

**问题**: 
- 如果是 ORM 模型，应该在 `infrastructure/`
- 如果是领域模型，应该分散到各业务领域内部
- 当前只有 `market_data.py`，建议合并到使用它的领域

---

### 2.4 技术工具库（1 个）

#### 9. quantlib（量化计算工具库）

```
domain/quantlib/
├── engine/            (52 文件)  # 回测引擎
├── risk/              (20 文件)  # 风险管理
├── derivatives/       (16 文件)  # 衍生品定价
├── factors/           (13 文件)  # 因子库
├── stages/            (14 文件)  # 回测阶段
├── ml/                (10 文件)  # 机器学习
├── core/              (9 文件)   # 核心计算
├── portfolio/         (7 文件)   # 组合管理
├── timeseries/        (8 文件)   # 时间序列
├── fixed_income/      (7 文件)   # 固定收益
├── adapters/          (7 文件)   # 适配器（⚠️ 错位）
├── finrl/             (6 文件)   # FinRL 集成
├── factor_models/     (6 文件)   # 因子模型
├── factor_analysis/   (4 文件)   # 因子分析
├── qlib/              (4 文件)   # Qlib 集成
├── rl/                (3 文件)   # 强化学习
├── pipeline/          (3 文件)   # 数据管道
├── cross_asset_strategies/  (2 文件)
├── gpu_acceleration/  (2 文件)   # GPU 加速
├── hft_strategies/    (2 文件)   # 高频策略
├── technical/         (2 文件)   # 技术指标
├── backtest/          (2 文件)   # 回测基础
├── futures/           (1 文件)   # 期货
├── statistics/        (1 文件)   # 统计
├── tools/             (1 文件)   # 工具
├── examples/          (1 文件)   # 示例
└── alternative_factors/ (1 文件) # 另类因子
```

**文件数**: 209 个（占 domain 层 78%）  
**子模块数**: 27 个

**职责**: 提供量化计算的各种技术能力。

**性质**: quantlib 不是一个业务领域，而是一个**跨领域的技术工具库**，类似于：
- NumPy（数值计算库）
- pandas（数据分析库）
- scikit-learn（机器学习库）

**关键问题**:

1. **体积过大**: 209 个文件，占据 domain 层近 80%
2. **职责混乱**: 既有纯技术计算（statistics, technical），又有业务逻辑（engine, strategies）
3. **层次混乱**: `quantlib/adapters/` 不应该在 domain 层
4. **边界模糊**: 27 个子模块之间职责重叠（如 backtest, engine, stages）

---

## 三、领域边界问题总结

### 问题 1: quantlib 过于庞大和混乱

**现状**:
- 209 文件，27 子模块
- 混合了技术库（statistics, technical）和业务逻辑（engine, strategies）
- 许多子模块职责重叠

**影响**:
- 修改困难，牵一发动全身
- 测试困难，依赖关系复杂
- 职责不清，新功能不知道放哪

**建议**:
1. **拆分为独立技术库项目**（类似 NumPy）
2. **或者** 按职责重组为多个小的领域：
   - `domain/backtest/` - 回测引擎（engine, stages, backtest）
   - `domain/risk/` - 风险管理
   - `domain/factors/` - 因子计算
   - 纯技术计算移到 `utils/` 或独立库

### 问题 2: 适配器错位

**违规文件**:
- `domain/quantlib/adapters/` - 整个目录应该在 `infrastructure/` 或 `adapters/`
- `domain/brokers/adapters/` - 同上

**修复**: 移动到正确的层级。

### 问题 3: models 目录定位不清

**问题**:
- `domain/models/` 只有 1 个文件（market_data.py）
- 不清楚是 ORM 模型还是领域模型

**建议**:
- 如果是 ORM 模型 → 移到 `infrastructure/persistence/orm/`
- 如果是领域模型 → 合并到使用它的具体领域

### 问题 4: 脚本错位

**违规文件**:
- `domain/benchmarks/run_all_benchmarks.py` - 导入了 `application` 层

**修复**: 移动到 `scripts/` 或 `tools/`

---

## 四、标准答案

### ❓ quantsys-v2 有多少个领域？

**答案取决于如何定义"领域"**:

#### 回答 1: 严格的业务领域定义
**6 个真实业务领域**

1. **strategies** - 策略领域
2. **brokers** - 券商领域
3. **chan** - 缠论技术分析领域
4. **chip_distribution** - 筹码分布领域
5. **memory** - 记忆系统领域
6. **benchmarks** - 基准测试领域

*不包括 quantlib（技术库）、ports（接口）、models（基础设施）*

#### 回答 2: 包含技术工具库
**7 个领域**

6 个业务领域 + 1 个技术工具库（quantlib）

#### 回答 3: 完全展开 quantlib
**32 个领域**

6 个业务领域 + 27 个 quantlib 子模块 - 1（去掉 quantlib 父级）

但这不合理，因为 quantlib 子模块职责边界不清晰。

---

## 五、推荐的领域架构

### 现状架构（不推荐）

```
domain/
├── strategies/          ✅ 业务领域
├── brokers/             ✅ 业务领域
├── chan/                ✅ 业务领域
├── chip_distribution/   ✅ 业务领域
├── memory/              ✅ 业务领域
├── benchmarks/          ✅ 业务领域
├── quantlib/            ❌ 过于庞大的技术库（209 文件）
├── ports/               ⚠️  基础设施，但位置合理
└── models/              ⚠️  定位不清
```

### 推荐架构 A: 拆分 quantlib

```
domain/
├── strategies/          # 策略领域
├── brokers/             # 券商领域
├── chan/                # 缠论领域
├── chip_distribution/   # 筹码分布领域
├── memory/              # 记忆系统领域
├── benchmarks/          # 基准测试领域
├── backtest/            # 回测领域（从 quantlib 拆出）
├── risk/                # 风险管理领域（从 quantlib 拆出）
├── factors/             # 因子领域（从 quantlib 拆出）
└── ports/               # 端口接口

# 技术库独立
libs/
└── quantlib/            # 纯技术计算库
    ├── statistics/
    ├── technical/
    ├── timeseries/
    └── ...
```

### 推荐架构 B: quantlib 整体外移

```
domain/
├── strategies/          # 策略领域
├── brokers/             # 券商领域
├── chan/                # 缠论领域
├── chip_distribution/   # 筹码分布领域
├── memory/              # 记忆系统领域
├── benchmarks/          # 基准测试领域
└── ports/               # 端口接口

# quantlib 作为独立技术库项目
../quantlib-py/          # 独立 Python 包
```

---

## 六、结论

### 领域数量总结

| 统计维度 | 数量 | 说明 |
|---------|------|------|
| 顶层目录 | 9 个 | domain/ 下的直接子目录 |
| **真实业务领域** | **6 个** | **推荐答案** |
| 业务领域 + 技术库 | 7 个 | 包含 quantlib |
| 完全展开 | 32 个 | 展开 quantlib 子模块（不推荐） |

### 架构健康度评估

**优点**:
- ✅ 核心业务领域边界清晰（strategies, brokers, chan, chip_distribution）
- ✅ 使用了 ports 模式进行依赖倒置
- ✅ chan 领域是优秀的设计案例

**问题**:
- ❌ quantlib 过于庞大（78% 的代码），职责不清
- ❌ domain 层存在 24 处依赖违规（见边界审计报告）
- ❌ 适配器、注册表等基础设施混入 domain 层
- ⚠️  models 目录定位不清

### 优先级建议

**P0 - 立即执行**:
1. 修复 domain 层的 24 处依赖违规
2. 移动错位的适配器和注册表

**P1 - 本季度**:
1. 重构 quantlib（拆分或外移）
2. 清理 models 目录

**P2 - 下季度**:
1. 建立架构测试防护机制
2. 完善领域文档

---

## 附录：领域职责矩阵

| 领域 | 核心职责 | 对外接口 | 依赖关系 | 状态 |
|------|---------|---------|---------|------|
| strategies | 定义和实现交易策略 | StrategyRegistry, BaseStrategy | 无 | ✅ 健康 |
| brokers | 券商接口抽象 | BaseBroker, BrokerRegistry | ⚠️  违规导入 adapters | ⚠️  需修复 |
| chan | 缠论技术分析 | ChanAnalyzer, 买卖点检测 | 无 | ✅ 健康 |
| chip_distribution | 筹码分布计算 | ChipCalculator, ChipService | 无 | ✅ 健康 |
| memory | 经验记忆和学习 | MemoryService, 混合检索 | ⚠️  违规导入 infrastructure | ⚠️  需修复 |
| benchmarks | 性能基准测试 | 各类 Benchmark | ⚠️  违规导入 infrastructure | ⚠️  需修复 |
| quantlib | 量化计算工具 | 27 个子模块 | ⚠️  过于庞大 | ❌ 需重构 |
| ports | 依赖倒置接口 | 各类 Port | 无 | ✅ 健康 |
| models | 领域模型 | MarketData | ⚠️  定位不清 | ⚠️  需澄清 |

---

**相关文档**:
- [领域边界审计报告](./domain-boundary-audit-2026-08.md) - 详细的架构违规分析
- [CLAUDE.md](../CLAUDE.md) - 项目架构概览
