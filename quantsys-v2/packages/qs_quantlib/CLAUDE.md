# qs_quantlib（量化计算库）

量化域的纯计算核心：技术指标、时间序列（Kalman/GARCH/ARIMA/协整/Granger）、衍生品定价、ML 预测器（FinRL/Qlib/RL 基类）、组合优化、回测引擎、代码校验器、GPU 加速因子。

**2026-10-18 由 `domain/quantlib` 整体抽离迁移而来**（方案卡：`docs/plans/package-boundaries-import-linter.md` §6 P1）。分支 `feat/qs-quantlib-package`。

## 规则

- **零应用依赖**：只允许 `numpy/pandas/scipy/statsmodels` 等科学计算库；**禁止** import `domain/*`、`application/*`、`adapters/*`、`infrastructure/*`、`services/*`、`repositories/*`（import-linter 契约 `quantlib-independence`）。
- 对外只暴露顶层 API；包内相对 import 自由。
- 数据访问（K 线、行情）不在本包职责内——由调用方注入 DataFrame。

## 常用任务路径

| 任务 | 从哪改 |
|---|---|
| 新增技术/时间序列指标 | `qs_quantlib/technical/` 或 `timeseries/`，基类 `base_calculator.BaseCalculator` |
| 异常类型 | `qs_quantlib/exceptions.py`（DataValidationError / CalculationError / ConfigurationError / ConvergenceError / DependencyError） |
| RL 环境/训练 | `finrl/`（SB3 封装）、`qlib/`（MS Qlib 封装）、`rl/`（抽象基类） |
| 策略代码安全校验 | `engine/code_validator.py` |
| 组合优化 | `portfolio/`（MeanVarianceOptimizer 等） |
| 因子库 | `factors/`、`gpu_acceleration/gpu_factors` |

## 开发

```bash
# 安装（editable，随主 venv）
pip install -e ./packages/qs_quantlib

# 测试（本包不依赖 DB）
pytest packages/qs_quantlib/../../tests # 主仓 tests 中相关子集
```

## 已知边界

- `infrastructure/quantlib/`（adapters shim ↔ adapters.outbound.datasources.providers.quantlib）是**基础设施层数据适配**，不属本包；包化后其归属裁决待定（见方案卡 §3.1 注）。
- 旧引用路径 `domain.quantlib.*` 由 `domain/quantlib/__init__.py` shim 吸收，需在本目录下留意 0 违规演进。
