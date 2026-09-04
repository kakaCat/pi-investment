# Strategy Architecture Refactoring

## 当前架构（问题）

```mermaid
graph TB
    subgraph "Domain Layer (领域层)"
        BS[BaseStrategy<br/>纯接口]
        V13[V13Strategy<br/>❌ 混合了业务配置+基础设施]
        V14[V14Strategy<br/>❌ 混合了业务配置+基础设施]
        SR[StrategyRegistry]
        SF[StrategyFactory]
    end

    subgraph "Infrastructure Layer (基础设施层)"
        ST[SimulationTrader<br/>模拟交易器]
        MODEL[v13_model.json<br/>v14_p0_model.json]
    end

    subgraph "Application Layer (应用层)"
        JOBS[Jobs<br/>定时任务]
        SVC[Services<br/>业务服务]
    end

    BS --> V13
    BS --> V14
    V13 -->|直接依赖❌| ST
    V14 -->|直接依赖❌| ST
    ST --> MODEL
    JOBS --> V13
    JOBS --> V14
    SVC --> SR
    SR --> V13
    SR --> V14

    style V13 fill:#ff6b6b,color:#fff
    style V14 fill:#ff6b6b,color:#fff
```

## 问题分析

| 层 | V13/V14 当前位置 | 违反原则 |
|---|---|---|
| Domain | ✅ 在这里 | ❌ 但依赖了 Infrastructure |
| Domain | ❌ | ❌ 包含业务配置（调仓天数、持仓数） |
| Domain | ❌ | ❌ 包含业务编排（initialize、run_daily_check） |

---

## 重构后架构（正确）

```mermaid
graph TB
    subgraph "Domain Layer (领域层) - 纯业务规则"
        BS[BaseStrategy<br/>纯接口]
        XGB[XGBoostStrategy<br/>✅ 纯算法：因子计算+信号生成]
        SR[StrategyRegistry]
        SIG[Signal<br/>值对象]
        CFG[StrategyConfig<br/>值对象]
    end

    subgraph "Application Layer (应用层) - 业务编排"
        V13[V13 Use Case<br/>✅ 业务配置：5日/8只/特定模型]
        V14[V14 Use Case<br/>✅ 业务配置：30日/15只/优化参数]
        SC[StrategyConfigManager<br/>配置管理]
    end

    subgraph "Infrastructure Layer (基础设施层) - 技术实现"
        ST[SimulationTrader<br/>模拟交易器]
        MODEL[Model Files<br/>模型文件]
        DB[(Database)]
    end

    subgraph "Interface Layer (接口层)"
        API[REST API]
        WS[WebSocket]
        CLI[CLI]
        JOBS[定时任务]
    end

    BS --> XGB
    XGB --> SIG
    XGB --> CFG
    SR --> BS

    V13 -->|使用| XGB
    V14 -->|使用| XGB
    V13 -->|配置| CFG
    V14 -->|配置| CFG
    SC --> V13
    SC --> V14

    V13 -->|调用| ST
    V14 -->|调用| ST
    ST --> MODEL
    ST --> DB

    API --> SC
    WS --> SC
    CLI --> SC
    JOBS --> SC

    style XGB fill:#51cf66,color:#fff
    style V13 fill:#339af0,color:#fff
    style V14 fill:#339af0,color:#fff
```

---

## 详细分层说明

```mermaid
graph LR
    subgraph "Domain (纯业务)"
        D1[BaseStrategy<br/>抽象接口]
        D2[XGBoostStrategy<br/>因子计算]
        D3[Signal<br/>交易信号]
        D4[StrategyConfig<br/>策略配置]
    end

    subgraph "Application (业务编排)"
        A1[V13UseCase<br/>5日调仓/8只持仓]
        A2[V14UseCase<br/>30日调仓/15只持仓]
        A3[StrategyConfigManager<br/>配置加载/切换]
    end

    subgraph "Infrastructure (技术实现)"
        I1[SimulationTrader<br/>模拟交易]
        I2[FactorCalculator<br/>因子计算]
        I3[ModelLoader<br/>模型加载]
    end

    D1 --> D2
    D2 --> D3
    D2 --> D4

    A1 -->|继承/实现| D1
    A2 -->|继承/实现| D1
    A1 -->|注入配置| D4
    A2 -->|注入配置| D4

    A1 -->|调用| I1
    A2 -->|调用| I1
    I1 --> I2
    I1 --> I3

    style D1 fill:#f8f9fa
    style D2 fill:#51cf66,color:#fff
    style D3 fill:#51cf66,color:#fff
    style D4 fill:#51cf66,color:#fff
    style A1 fill:#339af0,color:#fff
    style A2 fill:#339af0,color:#fff
    style A3 fill:#339af0,color:#fff
    style I1 fill:#ffd43b
    style I2 fill:#ffd43b
    style I3 fill:#ffd43b
```

---

## 代码结构对比

```
当前（错误）                          重构后（正确）
══════════════════════════════════════════════════════════════

domain/strategies/                   domain/strategies/
├── __init__.py                      ├── __init__.py
├── base_strategy.py        →        ├── base_strategy.py
├── v13_strategy.py         ✗        ├── xgboost_strategy.py    ← 新增：纯算法
├── v14_strategy.py         ✗        ├── signal.py               ← 新增：值对象
├── strategy_registry.py             ├── strategy_config.py     ← 新增：配置值对象
├── strategy_factory.py              ├── strategy_registry.py
├── strategy_272.py                  └── strategy_factory.py
├── strategy_273.py
├── strategy_274_ml.py        application/strategies/
                              →      ├── __init__.py
live_trading/                        ├── v13_use_case.py        ← 新增：V13业务用例
├── simulation_trader.py             ├── v14_use_case.py        ← 新增：V14业务用例
├── v13_factors.py                   ├── config_manager.py      ← 新增：配置管理
├── v14_factor_calculator.py         └── trading_orchestrator.py ← 新增：交易编排
├── train_v14_model.py
└── ...                       live_trading/
                              (保留，但不再被domain直接依赖)
```

---

## 依赖关系变化

```mermaid
graph TD
    subgraph "Before (依赖混乱)"
        direction TB
        V13_OLD[V13Strategy] -->|❌ 直接依赖| ST_OLD[SimulationTrader]
        V13_OLD -->|❌ 包含| CFG_OLD[业务配置]
        V13_OLD -->|❌ 包含| ORC_OLD[业务编排]
    end

    subgraph "After (依赖清晰)"
        direction TB
        V13_NEW[V13UseCase] -->|✅ 依赖接口| XGB_NEW[XGBoostStrategy]
        V13_NEW -->|✅ 注入配置| CFG_NEW[StrategyConfig]
        V13_NEW -->|✅ 调用| ST_NEW[SimulationTrader]
    end

    style V13_OLD fill:#ff6b6b,color:#fff
    style V13_NEW fill:#51cf66,color:#fff
```

---

## 重构步骤

```mermaid
graph TD
    START[开始重构] --> S1[1. 提取纯策略逻辑<br/>XGBoostStrategy]
    S1 --> S2[2. 定义值对象<br/>Signal, StrategyConfig]
    S2 --> S3[3. 创建V13/V14业务用例<br/>application/strategies/]
    S3 --> S4[4. 迁移配置参数<br/>从业务用例注入]
    S4 --> S5[5. 重构Registry<br/>使用新的策略类型]
    S5 --> S6[6. 更新定时任务<br/>使用业务用例]
    S6 --> S7[7. 删除旧代码<br/>v13_strategy.py, v14_strategy.py]
    S7 --> S8[8. 测试验证<br/>确保功能不变]

    style START fill:#ffd43b
    style S8 fill:#51cf66,color:#fff
```
