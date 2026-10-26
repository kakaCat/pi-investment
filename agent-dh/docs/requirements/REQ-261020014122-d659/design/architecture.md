# 架构设计（REQ-261020014122-d659）

> 合一总览见同目录 design.md（已落章）；本份为模板五份之一的架构视角，内容与 design.md §1/§5 一致。

## 目标与总体方案 `serves: FR-1, FR-2, FR-3`

**问题**：策略补测/进化链路被两个缺陷阻塞——①回测「开仓未平仓」时 `total_trades=0`，被进化判据 MIN_TRADES=1 误读为「窗口无信号」（FR-1/FR-2）；②evolution_run 工具 schema 把引擎降级响应（best_params/best_metrics/fitness 显式 null）拦成 `returned invalid output` 硬错误，降级原因被消灭（FR-3）。

**当前状况**（2026-10-20 逐行核实）：

- `quantsys-v2/packages/qs_strategy/qs_strategy/application/services/strategy_backtest_service.py`：`run_backtest_from_signals`（:254）的 `trades.append` 只出现在 SELL 分支（:343 全清 / :443 减仓），主循环结束（:510 权益曲线收尾）后**无平仓计账段**，`total_trades=len(trades)`（:603）。
- `strategy_evolution_service.py`：`MIN_TRADES=1`（:44）在 :198/:223 读取 `total_trades`——判据代码正确，输入数据错误；`_degraded_run`（:487-505）返回 `best_params/best_metrics/fitness/fitness_improvement` 显式 None。
- `agent-dh/packages/tools/evolution/src/tools/EvolutionRunTool/EvolutionRunTool.ts`：`normalizeRunResult`（:7）只对 `degraded_reason` 做 null 剔除（:46），其余 4 个 null 键原样透传，撞上 output schema 的 `type: object/number`（prompt.ts:166-169）→ 硬错误。

**设计方案**：

1. **FR-1 计账不动账**：主循环后、metrics 计算前插入强制平仓段——`position_tiers` 非空则按末日收盘价补记一条 `trades` 条目（`forced_close: true`），**不回改 cash、不动 equity_curve**（权益本已按末日市值计入；本动作只修正交易计数与胜率/持仓天数统计）。pnl 不计卖出费用，与权益曲线口径一致。
2. **FR-2 口径字段**：metrics 新增 `open_position_at_end: bool` 与 `forced_closes: int`，调用方可区分「真无信号」与「有信号未平仓」。
3. **FR-3 工具侧白名单剔除**：`normalizeRunResult` 对 `degraded_reason`（既有）+ `best_params`/`best_metrics`/`fitness`/`fitness_improvement`（新增 4 键）做 null 值整体省略。引擎响应不动、schema 零改动（output schema 无 required 数组，省略键合法）。

**不这么做的后果**：不修 ①，163/178/179/193 的 OOS 补测与每周进化永远拿不到 fitness（连续 4 周复现）；不修 ②，降级原因在工具边界被消灭，排障只能去读后端日志；选引擎侧补占位字段则等于编造数字，违反诚实降级语义。

## 模块改动地图 `serves: FR-1, FR-2, FR-3`

```
strategy_execute(backtest) / evolution_run
  → qv2 StrategyBacktestService.run_backtest_from_signals   [改] 窗口末强制平仓计账 + 2 个 metrics 字段
  → qv2 StrategyEvolutionService                            [不动] MIN_TRADES 判据自愈
  → agent-dh EvolutionRunTool.normalizeRunResult            [改] null 键白名单剔除（4+1）
```

**改动清单**：

| 模块/文件 | 类型 | 改动内容 | 原因（serves哪条FR） | 影响范围 |
|---|---|---|---|---|
| `quantsys-v2/.../strategy_backtest_service.py` | 修改 | 主循环后增强制平仓计账段；metrics 加 2 键 | FR-1, FR-2 | 回测响应 additive 新增键；total_trades 口径变更（只增不减） |
| `quantsys-v2/tests/test_backtest_forced_close.py` | 新建 | C1 故障注入 + C2/C3 回归（pytest） | FR-4 | 无生产影响 |
| `agent-dh/.../EvolutionRunTool/EvolutionRunTool.ts` | 修改 | normalizeRunResult 扩展 null 剔除清单 | FR-3 | 降级返回合法化；qv2_real 路径不变 |
| `agent-dh/apps/web/tests/evolution-qv2-contract.test.ts` | 修改 | 新增 C4：线上真实「显式 null」降级形状用例 | FR-4 | 无生产影响 |

## 数据结构变更 `serves: FR-2`

详见 data-model.md。要点：无 DB 表/schema 变更；metrics dict 纯 additive 新增 `open_position_at_end`/`forced_closes`；`trades[]`/`trade_records[]` 强制平仓条目带 `forced_close: true`。

## 风险与对策 `serves: FR-1, FR-3, FR-4`

| 风险 | 对策 |
|---|---|
| `total_trades` 口径变更使新旧报告不可比 | data-model.md 口径声明；消费方仅 evolution 判据与展示层，无下游持久化聚合 |
| 强制平仓 pnl 与权益曲线口径漂移 | 不计卖出费、不动 cash/equity_curve；C1 断言 exit_price=末日收盘价锁口径 |
| evolution 包构建失败清空 dist（有前科） | 发版走 `agent-dh/scripts/restart-with-build.sh`，构建后 grep dist 产物关键符号；失败按「未生效」处理 |
| null 剔除误伤未来「合法 null」字段 | 剔除清单白名单化（仅 4+1 键），不全局剔 null；C4 与既有 REAL_RUN 用例双向锁死 |
