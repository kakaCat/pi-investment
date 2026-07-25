# 盈利闭环统一设计（Profit Loop Closure）

**日期**：2026-07-24
**状态**：已获用户确认（6 节设计逐节通过）
**范围**：完整闭环——找股票 → 信号 → agent 模拟买卖 → 日复盘 → 每周进化，加进程常驻

## 背景与问题

系统现状：每一环的代码都存在，但"找股票→模拟买卖→复盘→改进"没有一条链路能自动跑通。断点在编排层而非功能层：

1. 动态池 `refresh_interval` 是死字段，无人自动刷新
2. 双轨账户分裂：v2 DailyOrchestrator 自动执行信号写死 `rotation_main`；agent 自主交易操作代管账户，两本账互相看不见
3. 进程依赖碎片化：闭环需要 4 个进程同时活着（5001 主服务、scheduler_daemon、agent dev、agent wake），缺一个环节静默消失
4. `signal_execution_daily` 处理器存在但未入调度种子
5. 每周进化（`runWeeklyEvolution`）只能 CLI 手动触发，学习反馈不自动
6. 次要：前端模拟交易页无手工下单按钮；PoolScanScheduler 通知逻辑 TODO

## 已确认的关键决策

| 决策点 | 结论 |
|---|---|
| 谁是唯一买卖决策者 | **agent（LLM）**。v2 orchestrator 降级为信号/数据准备，永不下单 |
| 方案范围 | 完整闭环（6 个断点全包） |
| 唯一交易账本 | **agent_virtual**（100k、空仓、干净）。rotation_main 冻结，v13/v14/v15 保留为策略校准对照组，default 冻结处置 |
| 驱动架构 | 方案 A：日程骨架 + 事件驱动 |
| 进程常驻 | 统一 supervisor（脚本化，健康检查 + 崩溃重启 + 飞书告警） |

## 1. 架构与职责边界

```
┌─ quantsys-v2（确定性骨架）────────────────────────────┐
│ scheduler_daemon (APScheduler)                        │
│  ├─ 02:00 动态池刷新（按 refresh_interval，新增）      │
│  ├─ DailyOrchestrator（改造）                          │
│  │   PRE_MARKET: 数据更新→因子→信号生成（不变）        │
│  │   MARKET_OPEN: 不再下单 → 推送 signals_ready        │
│  │   REVIEW: 推送 daily_review（不变）                 │
│  └─ signal_execution_daily → 改造为信号汇总推送        │
│ WatchEngine → watch_triggered（不变，已通）            │
└──────────────┬────────────────────────────────────────┘
               │ wake channel (HTTP /wake)
┌──────────────▼────────────────────────────────────────┐
│ agent-ts（唯一交易者）                                 │
│  事件驱动: signals_ready / watch_triggered / daily_   │
│           review → 决策 → portfolio_trade             │
│  日程骨架: 09:00 早盘分析(处理隔夜信号+持仓检查)        │
│           盘中 30min 巡检(止盈止损)                    │
│           18:00 日复盘(经验+知识沉淀)                  │
│           周日 20:00 每周进化(新增)                    │
│  唯一账本: agent_virtual                               │
└───────────────────────────────────────────────────────┘
        ↑ 4 进程由统一 supervisor 拉起+健康检查+崩溃重启
```

**职责边界原则**：v2 永远不下单（唯一例外：人工调 API 手动下单）；agent 永远通过 `portfolio_trade` + `agent_virtual` 账户交易；所有判断（买/卖/不买）都是 LLM 的，所有确定性工作（刷池、算因子、生成信号、推事件）都是 v2 的。

## 2. v2 侧改动

### 2.1 DailyOrchestrator 改造
文件：`quantsys-v2/application/services/daily_orchestrator.py`
- MARKET_OPEN 阶段：删除对 `SignalExecutionScheduler.execute_daily_signals()` 的调用，改为 `_notify_agent('signals_ready', payload)`
- payload 含当日 pending 信号列表：代码、方向、策略、强度、建议仓位区间
- 走现有 `agent_notification_service.notify_agent_detailed` 通道（与 watch_triggered 同链路）

### 2.2 动态池自动刷新（新增任务）
- 新增 `pool_refresh_daily` 处理器：查询所有 `refresh_interval` 到期的动态池 → 调用现有 `StockPoolService.refresh_pool` → 记录成员变更（进/出及原因）→ 重大变更时 notify agent（`pool_changed` 事件）
- 注册到 `application/services/scheduler_tasks.py` + `scripts/init_scheduler_tasks.py` 种子，cron 每天 02:00

### 2.3 调度种子补全
- `signal_execution_daily` 改造为"信号汇总确认"：不再下单，只确保信号已生成并推送，作为 signals_ready 的兜底重推
- 补进 `scripts/init_scheduler_tasks.py` 种子清单

### 2.4 PaperTradingEngine 解耦
- orchestrator 不再引用 PaperTradingEngine
- `rotation_main` 账户 status 置为 `frozen`（不删数据，保留历史）

## 3. agent 侧改动

### 3.1 新增 signals_ready 事件处理
文件：`agent-ts/src/wake-channel.ts`（参照现有 watch_triggered prompt 模式）

决策链 prompt：
1. `portfolio_status(agent_virtual)` 查持仓与可用资金
2. 逐信号评估：是否已持仓？与现有持仓相关性？是否符合当前策略？
3. 决定买入：`portfolio_trade(account=agent_virtual, reason≥10字)`
4. 放弃：`decision_record` 记录理由（学习数据）
5. 全部处理完：`knowledge_record` 摘要 + 飞书简报

**防重复**：v2 侧可能兜底重推，agent 处理前先查当日 `decision_history`，按"信号 ID + 日期"判重，已决策过的跳过——不靠记忆。

### 3.2 早盘任务职责调整
文件：`agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts`
- `morning_ai_analysis` 增加第一步：检查"昨日生成但未处理"的信号（兜底——signals_ready 推送时 agent 可能不在线）。事件丢了，日程兜底
- `daily_ai_review` 增加：当日信号处理覆盖率统计（收到 N 条、处理 N 条、成交 N 笔），写入 knowledge_record

### 3.3 新增每周进化定时任务
- 注册 `weekly_evolution` 任务（周日 20:00；scheduler-executor 已支持该类型），调用现有 `runWeeklyEvolution`（`services/intelligence/evolution-service.ts:220`）
- 产出：上周绩效归因、经验条目评审、策略参数调整建议（写 knowledge_record，重大调整飞书通知人工确认）

### 3.4 账户硬编码收敛
- agent 侧所有交易相关 prompt 和工具默认账户统一为 `agent_virtual`
- `portfolio_trade` 的 account 参数在系统 prompt 层固定，防止 LLM 选错账户

## 4. 账户与风控护栏

### 4.1 账户处置
| 账户 | 处置 |
|---|---|
| agent_virtual | 唯一交易账本，保持 100k 起点（当前空仓干净，直接启用） |
| rotation_main | frozen，orchestrator 不再引用 |
| v13/v14/v15 | 保留为策略校准对照组，`/api/simulation/run` 策略模拟继续用 |
| default | frozen（原"被重建待处置"，本次顺手处理） |

### 4.2 风控护栏（v2 服务端强制执行，不信 LLM 自觉）
- 沿用现有：单股 ≤30%、持仓 ≤3 只、总仓 ≤80%
- 新增 `agent_virtual` 账户级限制：单日买入 ≤5 笔、单日买入金额 ≤总资产 50%。写在 v2 模拟交易路由风控层，超限拒绝并返回明确原因（agent 会把拒绝原因写进 decision_record，形成学习数据）
- 止盈止损（+10%/-5%）保持 agent 侧 prompt 引导，不硬编码——属策略判断范畴

## 5. 统一 Supervisor

新增 `scripts/loop_supervisor.py`（仓库根目录，Python，复用 v2 venv）

### 5.1 进程清单
| 进程 | 启动命令 | 健康检查 |
|---|---|---|
| v2 主服务 | `quantsys-v2/start_all.py`（venv/bin/python） | `GET :5001/api/health` |
| scheduler_daemon | `scheduler_daemon.py`（**必须 venv/bin/python**） | 进程存活 + 调度表心跳字段 |
| agent 主进程 | `npm run dev`（agent-ts/） | 进程存活 |
| agent wake | `npm run wake`（agent-ts/） | wake channel 端口监听（:3001） |

### 5.2 职责
- 启动：按依赖序拉起（v2 主服务 → daemon → agent），等待健康检查通过再拉下一个
- 监控：每 30s 轮询；进程非零退出或健康检查连续 3 次失败 → 自动重启（指数退避 1min/5min/15min 封顶）
- 告警：重启发生、或连续重启 3 次失败 → 飞书通知（复用 v2 飞书通道），不做静默失败
- 状态：写 `logs/supervisor/status.json`（每进程：pid、启动时间、重启次数、最近健康检查结果）
- 停止：`loop_supervisor.py stop` 优雅终止全部子进程

### 5.3 日志
- 每进程 stdout/stderr → `logs/supervisor/<name>.log`，按天滚动
- supervisor 自身日志记录所有重启和告警事件

### 5.4 边界说明
supervisor 解决"进程活着"，不解决"笔记本合盖"——合盖休眠全体停摆是物理约束。唤醒后靠 APScheduler misfire 修复（已有）+ agent 早盘兜底检查恢复。

## 6. 错误处理与测试

### 6.1 错误处理
- **信号丢失**：signals_ready 推送失败 → v2 重推（交易类事件可重推，agent 有判重）→ 最终兜底：早盘任务查未处理信号
- **LLM 不可用**：agent 收到事件但 LLM 失败 → decision_record 标 `deferred`，早盘任务重试；当日无法处理 → 飞书告知"今日信号未处理"
- **下单被拒**：风控拒绝 → agent 记录原因并可降仓位重试一次，不无限重试
- **账户不一致**：每日复盘 agent 调 portfolio_status 核对；agent_virtual 有持仓变动但无当日决策记录 → 报警（说明有别的路径写了这本账）

### 6.2 测试策略
- v2：`pool_refresh_daily` 单测（mock 池服务）；orchestrator MARKET_OPEN 断言"不调 execute_daily_signals、调 notify_agent(signals_ready)"；新风控限制单测
- agent：signals_ready 链路集成测试（mock v2 API，验证判重与 portfolio_trade 参数）；weekly_evolution 任务注册测试
- 端到端冒烟：`scripts/smoke_loop.sh`（半自动，需 LLM key）——supervisor 拉起 4 进程 → 手动触发 signals_ready → 验证 agent 决策下单到 agent_virtual → 复盘任务产出记录。作为验收标准
- 回归：现有 scheduler/daemon 测试保持绿（尤其 misfire 修复相关）

## 验收标准

1. 一条命令（supervisor）拉起全部 4 进程，健康检查全绿
2. 交易日 09:30 前 v2 生成信号并推送 signals_ready，agent 自主决策，成交落在 agent_virtual（可在前端模拟交易页看到持仓）
3. 18:00 日复盘产出：绩效、信号覆盖率、经验记录
4. 周日 20:00 每周进化自动运行并产出调整建议
5. 杀掉任一进程，supervisor 自动重启并飞书告警
6. rotation_main / default 冻结，任何自动路径不再写这两本账
