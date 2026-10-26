# 测试用例（REQ-261020014122-d659）

> 双侧落位：后端 **pytest**（quantsys-v2/tests/）+ 工具侧 **vitest**（agent-dh/apps/web/tests/）。
> 纠正需求 §6 表述：quantsys-v2 用例不是 vitest，是 pytest。FR-4 故障注入纪律来自 lessons：「故障路径必须故障注入实测」。

## 被测对象与场景映射 `serves: FR-4`

| 用例 | 被测对象 | 类型 | serves |
|---|---|---|---|
| C1 | run_backtest_from_signals 开窗未平仓 | 故障注入 | FR-1, FR-2, FR-4 |
| C2 | run_backtest_from_signals 真无信号 | 回归 | FR-2, FR-4 |
| C3 | run_backtest_from_signals 正常往返 | 回归 | FR-1, FR-4 |
| C4 | EvolutionRunTool 降级（线上真实形状） | 故障注入 | FR-3, FR-4 |
| C5 | 实证回归：策略 202/002007 一年窗 | 实调验收 | FR-5 |

## 后端 pytest：`quantsys-v2/tests/test_backtest_forced_close.py`（新建）`serves: FR-4`

直接构造 `signals_df` 调 `StrategyBacktestService.run_backtest_from_signals`，不依赖数据库与行情源。

### C1 故障注入·开窗未平仓 `serves: FR-1, FR-2, FR-4`

- **构造**：≥5 根日 K；首日 `buy_tier1=1, buy_tier1_pct=0.5`；全程无 sell 信号。
- **断言**（任一失败即不通过）：
  - `metrics['total_trades'] == 1`
  - `metrics['forced_closes'] == 1`
  - `metrics['open_position_at_end'] is True`
  - `metrics['trades'][0]['forced_close'] is True`
  - `metrics['trades'][0]['exit_price'] == 末日收盘价`（锁 pnl 口径）
  - `metrics['trades'][0]['exit_date'] == 末日日期`

### C2 回归·真无信号 `serves: FR-2, FR-4`

- **构造**：无任何 buy/sell 信号。
- **断言**：`total_trades == 0`、`forced_closes == 0`、`open_position_at_end is False`。
- **意义**：MIN_TRADES 判据对真空窗仍降级，「真无信号」语义不被新逻辑稀释。

### C3 回归·正常往返 `serves: FR-1, FR-4`

- **构造**：首日买入；第三日 `sell_tier1=1, sell_tier1_pct=1.0` 全清。
- **断言**：`total_trades == 1`、`forced_closes == 0`、`open_position_at_end is False`、`trades[0]` 无 `forced_close` 键（旧形状不变）。

## 工具侧 vitest：`agent-dh/apps/web/tests/evolution-qv2-contract.test.ts`（改）`serves: FR-3, FR-4`

### C4 故障注入·降级显式 null（线上真实形状）`serves: FR-3, FR-4`

- **背景**：现有 `DEGRADED_RUN` mock **缺失** bestParams 等键，而线上 `_degraded_run`（strategy_evolution_service.py:487-505）返回**显式 null**——mock 形状与线不一致正是本缺陷漏测根因（lessons：「工具 schema 契约必须与线上数据模型对齐」）。
- **构造**：`{ success: true, dataSource: 'degraded', degradedReason: '基线回测零交易（total_trades=0，窗口 无信号）…', bestParams: null, bestMetrics: null, fitness: null, fitnessImprovement: null, proposals: [], totalVariants: 0, successVariants: 0, degradedVariants: 0, runAt: '…' }`
- **断言**：
  - 工具结果 `data.data_source === 'degraded'`；
  - `data.degraded_reason` 原文保留（含「零交易」字样）；
  - `'best_params' in data === false`、`'best_metrics' in data === false`、`'fitness' in data === false`、`'fitness_improvement' in data === false`（键整体省略）；
  - 若基建允许，将输出过一遍工具 output schema 校验（与 plugin-schema.smoke 同款绑定层），断言不抛 invalid output。
- **回归**：既有 REAL_RUN / DEGRADED_RUN（缺键形状）用例必须继续全绿——缺键与显式 null 两种形状都合法。

## 实证回归（FR-5，验收时实调）`serves: FR-5`

1. `strategy_execute(mode=backtest, strategy_id=202, symbol=002007, 2025-09-20~2026-09-20)`：返回 `total_trades ≥ 1` 且含 `forced_closes`/`open_position_at_end` 字段（修复前实测：equity 走向 768,184、末日持仓市值 768,042，`totalTrades=0`）。
2. `evolution_run(202, 002007, propose)`：返回 success（qv2_real 或 degraded 均可）；degraded 时 `degraded_reason` 非空、无 schema 硬错误。
3. `evolution_leaderboard(202)` 与 evolution_run 对同一降级事实的表述一致。

## 验收命令 `serves: FR-4, FR-5`

```bash
cd quantsys-v2 && python -m pytest tests/test_backtest_forced_close.py -v        # C1-C3 全绿
cd agent-dh && npx vitest run apps/web/tests/evolution-qv2-contract.test.ts      # C4 + 回归全绿
cd agent-dh && npx vitest run apps/web/tests/plugin-schema.smoke.test.ts         # schema 门禁回归
agent-dh/scripts/restart-with-build.sh                                           # 发版；构建后 grep dist 含新符号
```
