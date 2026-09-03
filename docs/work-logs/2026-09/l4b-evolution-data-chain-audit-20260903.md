# 进化数据链审计：A/B 双链并行与 leaderboard 占位冒充（L4-B §B5 梳理）

> 日期：2026-09-03（周四）
> 作者：investor（w-8366e526）
> 性质：架构混乱案例梳理——用户指出「第 3 层 进化数据链（发现架构混乱 ⚠️）」；本文全部结论基于 2026-09-03 实测（curl 双端点 + 代码行号），非转述
> 范围：只梳理不修码（B5 修复选项见 §6，待用户确认）

## 1. 三句话现状（实测）

1. **agent-dh 的 evolution_run / evolution_leaderboard 工具只连 A 链（Agent OS :8080）**——`evolution_leaderboard` 展示的"策略进化排名"**是占位分冒充**（0.05×i 启发式阶梯），不是真实策略表现。
2. **真实的双侧捕获 fitness 算法在 B 链（quantsys-v2）且算对过一次**——evolution_fitness 表仅 2 行、window_end 停在 **2026-08-14**，此后无生产者续采（采集闭环断）。
3. **两条链互不相通**：同一台 postgres（quant_investment 库）里两张表（evolution_runs / evolution_fitness），两套语义，agent-dh 工具看不到 B 链的真实分数。

## 2. 双链代码路径对照（带证据行号）

### A 链：agent-dh 工具 → Agent OS（占位冒充链）✅ 活着在跑

| 环节 | 证据 |
|---|---|
| evolution 插件默认指向 Agent OS :8080 | `agent-dh/packages/evolution/src/index.ts:23`（baseURL default `http://localhost:8080`）、`:32-33` |
| 工具调用 Agent OS | `EvolutionRunTool.ts:62` `aos.evolution.run(...)`；`EvolutionLeaderboardTool.ts:38` `aos.evolution.getLeaderboard(...)` |
| baseline 从 qv2 拉 avg_return | `agent-os/internal/api/evolution_handler.go:92` `fetchBaselineFitness` → `GET /api/performance/strategy/{id}` |
| **任何失败静默归零** | `evolution_handler.go:135-175`：build/fetch/read/parse 四类错误全部 `return 0`（无告警） |
| **baseline==0 → 0.05×i 占位** | `evolution_handler.go:182-186`：`riskMultiplier = 0.8+0.05*i`；`if baseline == 0 { estimated = 0.05*float64(i) }` |
| run 必标 completed（占位分也 completed） | `evolution_handler.go:87-108`：CreateRun → generateVariants → UpdateRunStatus("completed")，无真实回测环节 |
| leaderboard 读 evolution_runs 表 completed | `evolution_web_repository.go:57-60` `SELECT DISTINCT ON (strategy_id) ... WHERE status='completed'` |

**实测（2026-09-03）** `GET :8080/api/v1/evolution/leaderboard?limit=50` → **10 条 entries，全是占位分**：

```
strategy 178→0.15000000000000002(08-30)  203→0.1(08-19)  266→0.1(08-20)
268→0.15(08-31) 488→0.15(08-31) 635→0.15(09-01) 636→0.2(08-31)
637→0.15 638→0.15 639→0.15（08-31）
```

0.1 / 0.15 / 0.2 = 0.05×2/3/4（浮点 0.15000000000000002 即 0.05×3 的二进制痕迹）。Agent OS 是 legacy Go 服务但 **8080 仍活着**（本轮 curl 成功）。

### B 链：quantsys-v2 双侧捕获（真实算法、采集断链）✅ 算法真、数据停在 8/14

| 环节 | 证据 |
|---|---|
| 真实算法（纯函数） | `quantsys-v2/application/services/evolution/fitness_calculator.py:1-55`：`fitness = up_capture − down_capture`，大盘涨日/跌日账户收益分别归一（双侧捕获） |
| 服务层 | `evolution_fitness_service.py:18` `EvolutionFitnessService`、`:58` `compute_all_accounts` |
| **无生产者触发** | 全仓 grep：import evolution_fitness_service 的只有 `decision_score_service.py` + tests；**无任何定时任务/启动钩子调 compute_all_accounts** → 采集只可能在 8/14 前被一次性/人工跑过 |
| 路由只有读 | `evolution_async.py:19` `GET /api/evolution/leaderboard`（window_days/include_non_ok）；`evolution_async.py:41` `GET /api/evolution/decision-scores`；**无 POST 采集端点** |

**实测（2026-09-03）** `GET :5001/api/evolution/leaderboard` → **2 行真实双侧捕获值，window_end 全停 2026-08-14**：

```
agent_virtual        fitness 2.3337  up 2.1853  down -0.1485  ok
user_main_simulation fitness -0.0195 up -0.0289 down -0.0094  ok
```

## 3. 用户引述修正（诚实义务：实测与引述有出入）

用户转述的 B5 画像有 3 处与实测不符，如实纠正：

| 引述 | 实测 | 修正 |
|---|---|---|
| "从未有 completed run → leaderboard 空" | agent-os leaderboard **非空，10 条 completed runs**（08-19~09-01），fitness 全是 0.05×i 占位 | 空表不是问题——**假数据**才是：有 completed run 但 fitness 全是占位冒充 |
| "占位在 agent-dh 工具层" | 占位逻辑在 **agent-os generateVariants**（`evolution_handler.go:182-186`），agent-dh 工具只是透传（`EvolutionRunTool.ts:62`） | 修复点应在 agent-os 或让工具改走 B 链 |
| "两条链各读自己 DB" | 同库不同表：agent-os 与 qv2 都连 `quant_investment`（`agent-os/config.yaml` dbname），分表 evolution_runs / evolution_fitness | 不是异构库分叉，是同库内双写点分裂 |

**用户引述正确且更该警惕的部分**：agent-dh 工具声称"策略进化排名/进化运行"，实际给 agent 看到的是占位分——**进化排行榜成为既无真实语义又不标注降级的假指标**，agent 若据它决策=被占位误导。这正是"第 3 层（进化数据链）架构混乱"的实义。

## 4. 混乱根因（一句话）

**agent-dh 工具绑定的是 legacy Agent OS 的启发式占位实现，而真实双侧捕获算法在同一仓库另一条链里没有生产者续采（断在 8/14）、也没有工具接入——两条链从未被统一，占位链反而成了唯一对外展示的"进化"脸面。**

## 5. 危害链

```
agent 调 evolution_run / evolution_leaderboard
  → 看到 0.1-0.2 占位"适应度/排名"
  → 无任何降级标注（tools 不标 degraded）
  → agent 可能据此认为"策略 A fitness 0.2 > B 0.1 应启用 A"
  → 占位数字冒充了决策依据          ← 最危险：不是空，是"看起来有效"
```

## 6. B5 修复选项（待用户确认，未执行）

| 选项 | 动作 | 代价 | 效果 |
|---|---|---|---|
| **6a 工具改走 B 链（推荐）** | evolution_* 工具 baseURL 从 :8080 切到 :5001 的真实端点 + 给 B 链补生产者（盘后例程调 compute_all_accounts 落库）+ 端点支持 strategy_id 维度 | 中（动 agent-dh 工具 + qv2 生产者 + 可能加端点） | 工具展示真实双侧捕获；占位链退役；数据从 9/3 起每日续采 |
| **6b 占位链降级标注**（最小诚实化） | 不改链路，agent-os leaderboard 响应标 `baseline_unavailable/placeholder=true` 或工具侧对 0.05×i 特征值标注"占位分，非真实表现" | 小（agent-os handler 或 agent-dh 工具一处） | agent 不会被假数字误导，但真实进化仍未闭环 |
| **6c 统一到 A 链但替换占位** | 在 agent-os 里接 qv2 fitness 真实值替代启发式（evolution_handler.go 内改） | 中 | A 链继续当唯一入口，但数字变真 |
| **6d 维持现状**（记录在案） | 本文档归档为已知架构负债 | 0 | 混乱继续，占位继续冒充 |

> 建议：先 6b（当天可做，防误导），再排 6a（真实闭环）。是否执行、选哪档，请确认后我再动代码（本次只梳理）。

## 7. 相关文档

- 上游审计：`docs/work-logs/2026-09/profit-engine-autonomy-full-flow-audit-20260903.md`
- L4-B 实现：`docs/work-logs/2026-09/l4b-genome-benchmark-implementation-20260903.md`（§3 已诚实标注 Chain A 空转不在 L4-B 范围）
- 本审计不改变已交付的 L4-B B1-B4 结论（验证门/健康检查与 Chain A/B 分裂相互独立）
