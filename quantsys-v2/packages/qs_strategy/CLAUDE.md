# qs_strategy — 策略生命周期包

> 抽离记录：quantsys-v2 单体 S6（2026-10-18）。方案卡：`docs/plans/package-boundaries-import-linter.md` §11.4 S6。

## 本包是什么

**AI 工作区 L2**：本目录=「策略」项目（策略全生命周期）。上下文只要本文件，不要去根工作区。

- **定位**：用户策略 CRUD 与代码执行（strategy_code_service，dual 沙箱列注入）、策略引擎（strategy_engine：因子选择/ML 过滤/轮动）、回测编排（strategy_backtest/combo）、参数优化（strategy_optimizer）、进化/验证/评估/生命周期管理、25 个内置策略域模型
- `strategy_code_service` 瘦身在此（卡 S6 定案）：代码校验/模板/沙箱列注入收敛本包
- **上游**：`qs_market_data`（行情）、`qs_intel`（风格/情绪 read-only，白名单边）、`qs_quantlib`（指标计算）
- 让 **trading** 执行它产的信号；自身不发单

## 目录结构

```
qs_strategy/
├── application/services/          22 服务 + engine 子包
│   ├── strategy_code_service.py   用户策略代码 CRUD/校验/执行（瘦身目标）
│   ├── strategy_code_validator.py / strategy_code_service_factor_patch.py
│   ├── strategy_engine/           代码引擎（engine/factor_selection/ml_filter/sector_rotation）
│   ├── strategy_backtest_service.py / combo_strategy_backtest_service.py 回测编排
│   ├── strategy_optimizer.py      参数搜索（调用 POST /api/strategies/optimize 链路）
│   ├── strategy_execution_service.py / strategy_executor.py 执行编排
│   ├── strategy_lifecycle_service.py / strategy_validation_service.py / strategy_evaluation_service.py
│   ├── strategy_evolution_service.py / strategy_discovery_service.py 进化与发现
│   ├── strategy_circuit_breaker.py / strategy_weight_adjuster.py / strategy_rotation_engine.py
│   ├── strategy_analyzer.py / strategy_performance_stats.py / strategy_status.py
│   └── strategy_service.py / strategy_service_types.py
└── domain/strategies/             策略域（12 文件）
    ├── base_strategy.py（BaseStrategy/Signal/StrategyConfig）
    ├── strategy_registry.py / strategy_factory.py
    ├── strategy_272.py / strategy_273.py / strategy_274_ml.py / xgboost_strategy.py
    └── value_objects/
```

## 依赖边界（方案卡 §11.3）

- 允许：本包 → kernel（`domain.ports` / `infrastructure.persistence`）、→ `qs_market_data`（行情）、→ `qs_intel`（style/sentiment 只读，**白名单边，2026-10-18 登记**）、→ `qs_quantlib`
- 暂留 L1 引用（后续归属阶段收口）：`live_trading` 本地模块、`repositories/strategy_repository` 等 L1 仓储、infrastructure 两套 DI 反向装配
- 排除件：`scheduler_tasks_strategy.py`（调度装配归 ops，仍 L1）；`strategy_code_service.py.backup-2026-06-04` 与 `core_plan_service.py.backup-e2e` 为 git 跟踪的备份垃圾，留待清理 pass
- 旧路径兼容 shim 在 L1：`application/services/<22 模块名>.py`（sys.modules 别名）、`application/services/strategy_engine/`（__path__ 转发）、`domain/strategies/__init__.py`（__path__ 转发），30 天观察期后删除

## 常见任务路径

- **加用户策略能力** → `strategy_code_service.py`（5 种 code_type 模板在卡 §策略模板类型）
- **改回测编排** → `strategy_backtest_service.py`（引擎在 quantlib 包）
- **参数寻优** → `strategy_optimizer.py`（SearchSpace + 并行回测打分）
- **加内置策略** → `domain/strategies/`（继承 BaseStrategy，注册 strategy_registry）
