# 独立审阅发现的处置记录（2026-09-13，w-c8cae280）

独立只读审阅（subagent 7fd7dd55，基准 HEAD=4f0adf5a）给出 3 HIGH / 8 MEDIUM / 3 LOW。
本文逐条记录处置与"为什么这样处置"，含**明确不改**的项与理由。

## 一、已修（本轮）

### H1 risk_controller(position_size) 超时回归
- 现场：新增的 getPortfolioSummary（实测单次 ~9.4s，实时刷行情）塞进 timeoutMs=10000 的工具；
  同参连调第 1 次 timeout 10000ms、第 2 次 9630ms 贴边。
- 处置：timeoutMs 提到 30000；账户总值只取一次并复用（原实现在 Promise.all 里重复调用）。

### M1 totalValue=0 被当成"没有余量"
- 现场：headroomAmount = floor(0 × 60%) = 0 → min(20000, 0) = 0，且 cappedBy 误标 regime_headroom。
- 处置：valueAvailable=false 时降级为静态建议 + headroomNote，cappedBy=account_value_unavailable。

### M2 返回里并存两个账户价值，其中一个是后端硬编码 100000
- 根因：routes/risk_async.py 的 account_value 缺省 100000，client 未传 → 静态建议恒 20000。
- 处置：把真实总值传给后端；顶层 accountValue 用真实值覆盖，原值移到 backendAccountValueIgnored。

### M3 连笔下单无预留
- 处置：返回加 disclaimer，说明是单笔上限、未对同时挂出的多笔做预留。
  （已核实：真实下单路径 portfolio_trade 会再用 regime_position_limit 复核总敞口，不会被骗过。）

### M5 打分指标硬编码 labels(account="agent_virtual")
- 处置：按决策 context.account 逐账户记账。

### M6 持仓看板文案过期 + 新任务不可见
- 处置：note 口径更新（8 条 + 系统巡检已显式传参）；白名单补 agent-brain-candidate-hunt。

### M7 护栏测试取证面偏窄
- 处置：新增走 toDSHToolDefinition().execute 的**真实调用链**断言（10 条，只断言拒绝路径，不触发下单）；
  源码扫描扩到 agent-dh 全部包 + 顶层客户端；新增 dist 产物扫描；正则加宽并排除比较运算
  （首版正则把自家护栏里的 a === 'agent_virtual' 判成违规，属自我误报，已修）。
  测试：account-guard 33/33。

### M8 护栏拒绝集不含 default（已冻结 legacy 账户）
- 处置：5 个写工具的拒绝集改为 [agent_virtual, default]，并抽成单点判据。

### H3 写工具示例与护栏自相矛盾
- 处置：portfolio_trade 两个示例补 account_name；strategy/rotation 三件套的 example 与示例串
  从 default 改 agent_brain。照抄文档示例不会再被拒或写向冻结账户。

### M4 watch_engine 金额门借用别人账户（安全子集）
- 处置：position_value_provider 无归属账户时返回 None（不再取 agent_virtual 的持仓）；
  account_total_provider 改为按规则归属账户取值、无归属时用 agent-dh 自有账户
  （WATCH_ENGINE_DEFAULT_ACCOUNT 可覆盖），engine._account_total 透传 rule。

### L1/L2 脚本口径与装饰性 default
- 处置：quick-test / simple-test / integration-smoke / slippage-tool 统一 agent_brain；
  删除 4 个写工具参数里的 default 键（dsh-tools 不注入 default，留着会误导为"可省"）。

### 陈旧测试：日收益率契约变更后未同步（3 个用例）
- 现场：test_daily_snapshot_service 仍断言 kw['daily_return']，而 e020a76b 已把口径收敛到 repo。
- 处置：按新契约改为断言"不传 daily_return"。tests/services/evolution **47 passed / 0 failed**。

## 二、审阅新发现并已解决：投资脑净值序列饥饿

- 现场：近 30 天 simulation_equity_snapshot 覆盖 —— agent_virtual 20 天、v13 8 天、user_main 6 天，
  而**投资脑自有账户 agent_brain 只有 3 天**（08-26/09-10/09-11，恰为交易日）。
  后果：risk_metrics 的波动率/alpha/IR 与 M4 熔断净值复算建立在 3 个点上，"最大回撤 -0.13%"无统计意义。
- 根因（两条）：①写入方 equity-snapshot-daily 任务 2026-09-11 才建号（此前无任何调度在写）；
  ②历史交易日从未回填。
- 处置：新增 quantsys-v2/scripts/backfill_snapshots.py（交易回放 + 最近可得收盘价 mark-to-market，
  **默认不覆盖已有真实快照**），回填 agent_brain 2026-07-21→09-11 共 **36 个交易日**：
  覆盖 3 → **39 条**（近 30 天 20 天，与 agent_virtual 持平）。
- 回填后 risk_metrics(agent_brain)：vol 2.77%、**max_drawdown -1.18%**、beta 0.023、VaR -0.15%、
  nav_coverage.points=39 / missing_count=0 / impact="序列连续，日收益口径可用"；
  基准归因：沪深300 -4.83% vs 组合 -1.11% → 超额 +3.72%（这是投资脑第一份真实归因）。

## 三、明确不改（附理由）

1. **v2 API 路由的 account_name 默认值**（risk_async / circuit_breaker_async / orders_async /
   portfolio_breaker_service / daily_orchestrator 的 TRADING_ACCOUNT 等）。
   理由：这些接口 **agent-ts（fin-agent）也在调用**。把默认值从 agent_virtual 翻转成 agent_brain，
   会让 fin-agent 未传参的调用落到投资脑账上 —— 比现状更危险。正确修法是"要求显式传参（缺参 400）"，
   需要与 agent-ts 协调后统一做。
2. **daily_orchestrator 的交易账本常量**：它给 agent 的指令文案（portfolio_trade(account=agent_virtual)）
   决定了某个自动闭环往哪个账下单，属跨线行为变更，不由本窗口单方面改。

## 四、验证汇总

| 项 | 结果 |
|---|---|
| agent-dh 护栏测试 | account-guard **33/33**（含 10 条真实链路断言） |
| 风险工具测试 | risk-position-size-headroom **9/9** |
| 插件 schema 冒烟 | **19/19** |
| dist 构建 | **19/19** 包重建校验通过 |
| v2 定向测试 | watch_engine/snapshot/decision_score/circuit_breaker **117 passed / 2 failed**（2 个失败在 tests/integration/test_provider_failover.py，属数据源故障转移，与本轮改动无关） |
| v2 服务重启 | pid 74259，6 秒健康就绪 |
| 净值回填 | agent_brain 39 条连续快照；risk_metrics 口径从"3 点"变为"39 点可用" |

## 五、仓库卫生发现

- `quantsys-v2/.gitignore:22` 忽略 `scripts/`，但该目录下已有 116 个文件被跟踪 —— 我 09-11 写的
  `scripts/snapshot_daily.py`（equity-snapshot-daily 任务直接调用的脚本）当时**未入库**，只存在于本机。
  本轮已 `git add -f` 把 snapshot_daily.py 与 backfill_snapshots.py 一并入库，消除"定时任务依赖一个
  不受版本控制的脚本"这一隐患。
- 提交纪律：另一工作线在 `packages/pages/holdings` 有 5 个 staged 文件（lib/client.js 等），本窗口所有
  提交均显式列路径，未夹带。
