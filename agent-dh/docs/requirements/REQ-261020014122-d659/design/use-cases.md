---
requirement_refs: [FR-1, FR-2, FR-3, FR-5]
---

# 用户场景（REQ-261020014122-d659）

> 本需求用户是 agent 本身与复核的人类，无 UI 交互；场景聚焦链路修复后的两条主用路径。

## 场景总览 <!-- serves: FR-1, FR-3 -->

| 场景 | 角色 | 触发 | 完成标志 | serves |
|---|---|---|---|---|
| UC-1 | 投资脑（agent） | 每周进化/补测调用 evolution_run | 降级时拿到可读原因而非硬错误 | FR-3, FR-5 |
| UC-2 | 投资脑（agent） | 策略回测/补测（strategy_execute backtest） | 有持仓未平仓的回测 total_trades ≥ 1，进化判据不再误判 | FR-1, FR-2, FR-5 |
| UC-3 | 人类用户（复核者） | 验收 | 按 test-cases.md 命令复跑全绿 | FR-4, FR-5 |

## UC-1 进化降级可读 <!-- serves: FR-3, FR-5 -->

- **用例角色**：投资脑（本实例，evolution_run 调用方）
- **前置条件**：qv2 进化引擎因基线零交易/样本不足等原因诚实降级（`_degraded_run` 返回显式 null 四键）
- **交互流程**：
  1. agent 调 `evolution_run(strategy_id, symbol, mode=propose)`；
  2. 引擎返回 `data_source=degraded` + `degraded_reason`；
  3. 工具 normalizeRunResult 剔除 null 键后通过 output schema 校验；
  4. agent 收到 `success: true`、`data_source: 'degraded'`、完整 `degraded_reason`。
- **异常流**：引擎空响应 → 兜底降级（既有行为不变）；引擎 qv2_real → 四键非 null 正常透传（C4 与 REAL_RUN 回归双向锁死）。
- **后置条件**：agent 能基于 degraded_reason 决策（如调整窗口/标的/策略参数），且不产出任何占位 fitness。
- **完成标志**：不再出现 `returned invalid output`；与 evolution_leaderboard 对同一降级事实表述一致。

## UC-2 回测判据正确 <!-- serves: FR-1, FR-2, FR-5 -->

- **用例角色**：投资脑（补测执行方）；间接受益：策略线账户（共用同一判据）
- **前置条件**：策略在回测窗口内有买入信号但窗口结束仍持仓（实证：策略 202/002007 一年窗，184 天持仓、收益 -23.18%）
- **交互流程**：
  1. agent 调 `strategy_execute(mode=backtest, …)` 或进化引擎内部跑基线回测；
  2. 窗口末强制平仓计账段补记 `forced_close: true` 条目；
  3. metrics 返回 `total_trades ≥ 1`、`open_position_at_end: true`、`forced_closes: 1`；
  4. 进化判据 `total_trades >= MIN_TRADES` 通过，进入正常变体评估/归一。
- **异常流**：真无信号窗口 → `total_trades=0`、`forced_closes=0`，判据照常降级且 degraded_reason 语义从此准确（C2 锁定）。
- **后置条件**：补测链路通畅，163/178/179/193 的 OOS 补测可执行（执行本身为可选项/后续卡）。
- **完成标志**：C5 实证三步骤全部满足。

## UC-3 人工验收复跑 <!-- serves: FR-4, FR-5 -->

- **用例角色**：人类用户（复核者）
- **前置条件**：修复已部署（quantsys-v2 重启、agent-dh 经 restart-with-build.sh 发版且 dist 校验通过）
- **交互流程**：按 test-cases.md「验收命令」逐条执行；再执行 C5 三个实调。
- **异常流**：任一命令非全绿 → 按 test-cases.md 定位到具体用例，退回实施返工。
- **后置条件**：pytest 3 用例 + vitest 契约用例 + schema 门禁全绿；实证三步骤满足。
- **完成标志**：验收单逐项通过。
