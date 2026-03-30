# ML Pipeline Risk Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ML 回测引擎增加最小可用的止损、止盈和仓位管理能力，并通过回测测试与命令验证。

**Architecture:** 在 `backtesting` 包中新增独立 `RiskManager`，负责止损、止盈和最大仓位计算；`BacktestEngine` 仅在持仓期间调用它决定是否提前卖出，并在买入时限制仓位。保持 CLI 行为不变，仅让 `backtest` 命令自动走新风控逻辑。

**Tech Stack:** Python, pandas, unittest

---

### Task 1: 风险管理器

**Files:**
- Create: `ml-pipeline/backtesting/risk_manager.py`
- Test: `ml-pipeline/tests/test_backtest_engine.py`

- [ ] **Step 1: Write the failing test**
  为止损、止盈、仓位计算补充最小行为测试。

- [ ] **Step 2: Run test to verify it fails**
  Run: `python -m pytest ml-pipeline/tests/test_backtest_engine.py -q`

- [ ] **Step 3: Write minimal implementation**
  创建 `RiskManager`，提供 `should_stop_loss`、`should_take_profit`、`calculate_position_size`。

- [ ] **Step 4: Run test to verify it passes**
  Run: `python -m pytest ml-pipeline/tests/test_backtest_engine.py -q`

### Task 2: 集成回测引擎

**Files:**
- Modify: `ml-pipeline/backtesting/engine.py`
- Test: `ml-pipeline/tests/test_backtest_engine.py`

- [ ] **Step 1: Write the failing test**
  为止损卖出、止盈卖出、最大仓位买入补充失败测试。

- [ ] **Step 2: Run test to verify it fails**
  Run: `python -m pytest ml-pipeline/tests/test_backtest_engine.py -q`

- [ ] **Step 3: Write minimal implementation**
  在 `BacktestEngine` 中注入 `RiskManager`，优先检查风控卖出，再处理买入和最后一日平仓。

- [ ] **Step 4: Run test to verify it passes**
  Run: `python -m pytest ml-pipeline/tests/test_backtest_engine.py -q`

### Task 3: 验证回测命令

**Files:**
- Test: `ml-pipeline/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**
  确认 `backtest` 命令仍能完成基本执行并输出结果。

- [ ] **Step 2: Run test to verify it fails if needed**
  Run: `python -m pytest ml-pipeline/tests/test_cli.py -q`

- [ ] **Step 3: Keep implementation minimal**
  仅在现有命令路径上验证集成，不新增 CLI 参数。

- [ ] **Step 4: Run test to verify it passes**
  Run: `python -m pytest ml-pipeline/tests/test_cli.py -q`
