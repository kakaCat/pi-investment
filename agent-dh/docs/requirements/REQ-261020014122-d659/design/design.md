# REQ-261020014122-d659 设计：回测判据与 evolution_run schema 修复

- **需求**：docs/requirements/REQ-261020014122-d659/requirement.md（已确认）
- **类型**：feature（expert）· 设计合一档（改动面小：2 个仓库各 1 处生产代码 + 2 个测试文件，单一文档覆盖四视角）
- **作者**：w-503df447（investor）· 2026-10-20

## 1. 架构与改动面 `serves: FR-1, FR-2, FR-3`


链路现状（已逐行核实，2026-10-20）：

```
strategy_execute(backtest) / evolution_run
  → qv2: StrategyBacktestService.run_backtest_from_signals   ← 缺陷1：trades 只在 SELL 分支 append
       （packages/qs_strategy/qs_strategy/application/services/strategy_backtest_service.py:254，
         append 于 :343/:443，窗口末无平仓段，total_trades=len(trades) 于 :603）
  → qv2: StrategyEvolutionService MIN_TRADES=1 判据
       （strategy_evolution_service.py:44/:198/:223，语义本身正确，输入数据错误）
  → agent-dh: EvolutionRunTool.normalizeRunResult             ← 缺陷2：引擎 degraded 返回
       （packages/tools/evolution/src/tools/EvolutionRunTool/EvolutionRunTool.ts:7）
       best_params/best_metrics/fitness/fitness_improvement 显式 null
       （引擎 _degraded_run，strategy_evolution_service.py:487-505），
       撞上 output schema 的 type:object/number → "returned invalid output" 硬错误，
       degraded_reason 被消灭。
```

改动面（4 个文件，无新增子系统、无 schema/表结构变更）：

| 文件 | 动作 | 职责 |
|---|---|---|
| `quantsys-v2/packages/qs_strategy/qs_strategy/application/services/strategy_backtest_service.py` | 修改 | 窗口末强制平仓计账 + metrics 新增 2 字段 |
| `quantsys-v2/tests/test_backtest_forced_close.py` | 新建 | FR-4 故障注入 + 回归用例（pytest） |
| `agent-dh/packages/tools/evolution/src/tools/EvolutionRunTool/EvolutionRunTool.ts` | 修改 | normalizeRunResult 扩展 null 键剔除 |
| `agent-dh/apps/web/tests/evolution-qv2-contract.test.ts` | 修改 | 新增线上真实形状（显式 null）降级用例 |

**边界（与需求 §5 一致）**：不改 fitness 归一公式、参数网格、MIN_TRADES 阈值（数值与判据位置均不动）、分钟线 T+1 逻辑、回测其它分支（分批买卖/自定义价格校验）。strategy_evolution_service.py **零改动**——判据代码正确，只是输入被缺陷 1 污染，修完缺陷 1 即自愈。

## 2. 接口与数据契约 `serves: FR-1, FR-2, FR-3`


### 2.1 回测 metrics 新增字段（FR-2） `serves: FR-2`

`run_backtest_from_signals` 返回 dict（经 `/api/backtest/strategy` 与 `strategy_execute(mode=backtest)` 原样透传）新增两个键，**纯新增、不改既有键语义以外的任何内容**：

| 字段 | 类型 | 约束 | 含义 |
|---|---|---|---|
| `open_position_at_end` | bool | 恒存在 | 窗口结束时是否有未平仓持仓 |
| `forced_closes` | int | 恒存在，取值 0 或 1 | 窗口末强制平仓计账笔数（当前持仓模型为单一篮子，最多 1；int 预留扩展） |

`trades[]` 元素新增键 `forced_close: true`（仅强制平仓条目携带；普通条目不出现该键，保持旧报告字段形状兼容）。`trade_records[]` 强制平仓条目同样带 `forced_close: true`、`action: 'sell'`、`type: 'SELL'`。

**口径变更声明**：`total_trades` 自本需求上线起 =「发生过的往返交易数（含窗口末强制平仓）」，只增不减；上线前旧报告与新口径不可直接比较。变更时点以本需求验收日为准，写进 quantsys-v2 changelog 与本文件即完成告知义务（消费方只有 evolution 判据与报表展示，无下游持久化聚合）。

### 2.2 强制平仓计账口径（FR-1） `serves: FR-1`

- **触发点**：主循环结束后、`calculate_metrics_from_trades` 调用前（strategy_backtest_service.py 现 L510 与 L512 之间）；仅当 `position_tiers` 非空。
- **价格**：末日 `close_price`（窗口最后一条 K 线收盘价），`exit_date` = 末日 `date_str`。
- **盈亏口径**：`pnl = total_shares × (exit_price − avg_entry)`，**不计卖出费用**——与权益曲线口径一致（权益曲线持仓市值本未扣卖出费），保证 `sum(trades.pnl)` 与权益变动可对账。
- **不动账**：不回改 `cash`、不向 `equity_curve` 追加点——强制平仓是**计账动作**（修正 trades 计数与胜率/持仓天数统计），不是权益事件；权益本已按末日市值计入。
- **T+1 豁免**：不受 `enable_t1_constraint` 限制（记账非真实交易，分钟线窗口末同样计账）。
- **tiers 明细**：与全清分支（L343-363）同构，逐 tier 记录 entry/exit/shares/pnl，外加 `forced_close: true`。

### 2.3 evolution_run 工具降级形状（FR-3） `serves: FR-3`

**选型：工具侧剔除 null 键（方案 A），不选引擎侧补占位字段（方案 B）。**
理由：①方案 B 在降级响应里补 `best_params={}`/`fitness=0` 等于编造占位数字，直接违反诚实降级语义；②工具侧已有同款先例（EvolutionRunTool.ts:44-46 对 `degraded_reason==null` 的剔除）；③output schema 无 required 数组，省略键合法；④引擎响应对其他消费方（evolution_leaderboard 已能正确处理 null）保持不变，改动面最小。

契约（normalizeRunResult 输出）：

- 以下键值为 `null`/`undefined` 时**整体省略**（不出现在输出对象）：`degraded_reason`（既有行为）、`best_params`、`best_metrics`、`fitness`、`fitness_improvement`（本次新增 4 键）。
- `data_source='degraded'` 时输出必含 `degraded_reason: string`（引擎保证非空；空响应兜底分支 EvolutionRunTool.ts:8 已保证）。
- qv2_real 路径不受影响：这 4 键在真实 run 中非 null（引擎 :487 之外的成功路径），照常透传。
- schema 文件 prompt.ts **零改动**（键本就可缺省；null 不允许，剔除后天然合法）。

错误语义：修复后降级调用返回 `success: true` + `data_source: 'degraded'` + 可读 `degraded_reason`，不再出现 `returned invalid output` 硬错误——与 evolution_leaderboard 对同一降级事实的表述一致（验收锚点 4）。

## 3. 数据层与迁移/回滚 `serves: FR-1, FR-2, FR-3`


- **不改表、不改 DB schema**：metrics 是 dict/JSON 透传，新字段纯 additive；evolution 落库行（record_batch）结构不变。
- **旧调用方兼容**：`/api/backtest/strategy` 与 `strategy_execute(backtest)` 响应只是多两个键，旧消费方忽略未知键即可；`trades[]` 普通条目不新增键。
- **回滚路径**：两侧均为纯代码变更，`git revert` 即可；无数据迁移、无回填。agent-dh 侧 evolution 包是 **dist 加载**（package.json main=./dist/index.mjs）——上线与回滚都必须走 `agent-dh/scripts/restart-with-build.sh`（构建→校验 dist→重启），构建后 grep dist 产物确认新逻辑符号存在（lessons：「改了源码≠已生效」「构建失败会清空 dist，必须校验产物」）。

## 4. 测试策略（故障注入实测） `serves: FR-4, FR-5`


> 纠正需求 §6 的一处表述：后端用例走 **pytest**（quantsys-v2/tests/），vitest 只覆盖 agent-dh 工具侧；两侧各自可独立跑绿。

### 4.1 后端 pytest：`quantsys-v2/tests/test_backtest_forced_close.py`（新建） `serves: FR-4`

直接构造 `signals_df` 调 `StrategyBacktestService.run_backtest_from_signals`，不依赖数据库与行情源：

| 用例 | 构造 | 断言（可证伪） |
|---|---|---|
| C1 故障注入·开窗未平仓 | 首日 `buy_tier1=1, buy_tier1_pct=0.5`，全程无 sell 信号，≥5 根日 K | `total_trades == 1`；`forced_closes == 1`；`open_position_at_end is True`；`trades[0]['forced_close'] is True`；`trades[0]['exit_price'] == 末日收盘价`；`trades[0]['exit_date'] == 末日日期` |
| C2 回归·真无信号 | 无任何 buy/sell 信号 | `total_trades == 0`；`forced_closes == 0`；`open_position_at_end is False`（MIN_TRADES 判据对真空窗仍降级，语义不失） |
| C3 回归·正常往返 | 首日买入、第三日 `sell_tier1=1, sell_tier1_pct=1.0` 全清 | `total_trades == 1`；`forced_closes == 0`；`open_position_at_end is False`；trades[0] 无 `forced_close` 键（旧形状不变） |

### 4.2 工具侧 vitest：`agent-dh/apps/web/tests/evolution-qv2-contract.test.ts`（改） `serves: FR-3, FR-4`

新增用例 C4，**mock 用线上真实形状**（`_degraded_run` 实测：显式 null，而非现有 DEGRADED_RUN mock 的键缺失——形状不符正是本缺陷漏测的根因）：

- C4 故障注入·降级显式 null：`{ success: true, dataSource: 'degraded', degradedReason: '基线回测零交易…', bestParams: null, bestMetrics: null, fitness: null, fitnessImprovement: null, proposals: [], ... }` → 断言工具结果 `data` 中 `best_params/best_metrics/fitness/fitness_improvement` **键不存在**（`expect('fitness' in data).toBe(false)`），`data_source === 'degraded'`，`degraded_reason` 原文保留。若测试基建允许，再过一遍工具 output schema 校验（与 plugin-schema.smoke 同款绑定层校验）断言不抛 invalid output。
- 既有 REAL_RUN / DEGRADED_RUN 用例必须继续全绿（回归）。

### 4.3 实证回归（FR-5，验收时人工/agent 实调） `serves: FR-5`

1. `strategy_execute(mode=backtest, strategy_id=202, symbol=002007, 2025-09-20~2026-09-20)`：返回 `total_trades ≥ 1` 且含 `forced_closes`/`open_position_at_end` 字段（该用例修复前实测 equity 走向 768,184 仍持仓、`totalTrades=0`）。
2. `evolution_run(202, 002007, propose)`：返回 success（qv2_real 或 degraded 均可），degraded 时 `degraded_reason` 非空、无 schema 硬错误。
3. `evolution_leaderboard(202)` 与 evolution_run 对同一降级事实表述一致。

### 4.4 验收命令汇总 `serves: FR-4, FR-5`

```bash
# 后端（FR-4 C1-C3）
cd quantsys-v2 && python -m pytest tests/test_backtest_forced_close.py -v
# 工具侧（FR-4 C4 + 回归）
cd agent-dh && npx vitest run apps/web/tests/evolution-qv2-contract.test.ts
# schema 门禁回归（防 schema 铁律破坏）
cd agent-dh && npx vitest run apps/web/tests/plugin-schema.smoke.test.ts
# 发版与 dist 产物校验（lessons 纪律）
agent-dh/scripts/restart-with-build.sh   # 构建后确认 dist 含新符号再重启
```

## 5. 风险与对策 `serves: FR-1, FR-3, FR-4`


| 风险 | 对策 |
|---|---|
| `total_trades` 口径变更使新旧报告不可比 | §2.1 口径声明 + 新字段让调用方可区分；消费方仅 evolution 判据与展示层，无聚合报表污染 |
| 强制平仓 pnl 与权益曲线口径漂移 | §2.2 明确不计卖出费、不动 cash/equity_curve；C1 断言 exit_price=末日收盘价锁住口径 |
| evolution 包构建失败清空 dist（有前科） | 发版走 restart-with-build.sh，构建后 grep dist 产物关键符号（如 `best_params` 剔除逻辑），失败按「未生效」处理 |
| 剔除 null 键误伤未来「合法 null」字段 | 剔除清单白名单化（仅 4+1 个键），不全局剔 null；C4 与既有 REAL_RUN 用例双向锁死 |

## 6. 不做什么（与需求 §5 对齐） `serves: FR-1, FR-3`


- 不改 strategy_evolution_service.py 任何一行（MIN_TRADES 数值、判据位置、归一公式、网格生成均不动）；
- 不做 163/178/179/193 的 OOS 补测执行（链路修通后另起卡或收尾时顺带，本需求只保证链路通）；
- 不动分钟线 T+1、分批买卖、自定义价格校验分支；
- 不改 evolution_leaderboard（其行为已是正确参照系）。
