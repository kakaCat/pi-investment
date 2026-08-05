# Agent 行为进化系统设计（目标驱动 · 单账户）

- 日期：2026-08-05
- 状态：Phase 1 已上线（2026-08-05），进入 20 个交易日观察期
- Phase 1 验收备注：公式方向性验证通过（agent_virtual fitness 1.91 显著领跑：涨日 1.86x / 跌日 -0.05）；「v14 垫底」判据未能检验——v13/v14 真实亏损路径不在 simulation_trades 中（校准重置），快照回填仅对交易史完整的账户（agent_virtual/user_main）可信，v13/v14 待每日快照任务积累后重新评估
- 前置调查：2026-08-05 自我进化机制审计（agent-ts / quantsys-v2 代码层 + 生产 PG 数据层三路核查）

## 1. 背景与问题

系统愿景是「agent 从结果中学习、随时间改进决策质量」。审计结论：骨架齐全但闭环多处断头——

- weekly_evolution 引擎代码完整但 2026-07-19 后停运，其依赖的 `.pi-invest/reviews/` 信号源 5-26 起失效
- 经验库 verifyExperience 零调用点（经验只衰减不验证）
- 缠论蒸馏闭环是唯一端到端自动学习闭环（08-04 上线），但 cron 未真正注册到调度器
- signals 89% 停 pending，signal_executions / pool_change_log / strategy_validation_reports 均空表

用户的进化观：股票市场有天然适应度——**单位时间挣得多就是好；大盘涨时挣最多、大盘跌时赔最少；长周期必然收敛到盈利**。进化对象是 **agent 行为本身**（prompt、决策规则、经验、工具习惯），不是策略参数（策略层已被策略体检/动态权重覆盖）。

### 旧引擎失败教训（本设计必须规避）

| weekly_evolution 失败点 | 本设计对策 |
|---|---|
| 决策质量信号源（reviews/）失效两个月无人察觉 | 数据源用 simulation_equity_snapshot（交易链路天然产出，断了即有告警） |
| 一次改多个东西，归因模糊 | 硬约束每代一个行为改动 + 可证伪假设 |
| 没有显式目标，「改进」无标尺 | 每代显式目标落库 + 达成/未达成判定 |
| 一次建太大直接上闭环 | 分两阶段，Phase 1 先证明度量有效 |

## 2. 核心设计决策（用户逐项确认）

1. **进化对象**：agent 行为本身（prompt / 决策规则 / 经验 / 工具习惯）
2. **进化机制**：单账户目标驱动（agent_virtual）。多账户种群竞争归档为未来选项——现状是 agent 被 prompt 写死操作唯一账本（agent-decision-tasks.ts / wake-adapter.ts），多账户地基工程量大，先证明单账户循环有效
3. **适应度函数**：双侧捕获差 = up_capture − down_capture（大盘涨日收益弹性 − 大盘跌日亏损弹性）
4. **世代长度**：20 个交易日（与缠论蒸馏验证窗一致，基建复用）
5. **变异方式**：LLM 自由反思，加硬约束——每代一个改动 + 可证伪假设结构化落库，保证归因干净
6. **落地路线**：两阶段，先度量后闭环

## 3. Phase 1：适应度计算与排行榜（纯观察，零风险）

### 3.1 适应度公式

数据源：`simulation_equity_snapshot`（已有，每日净值）+ 沪深300 指数日线（kline 链路已有）。

滚动 20 交易日窗：

- 大盘日分类（沪深300 日涨跌幅）：涨日 ≥ +0.3%，跌日 ≤ −0.3%，|涨跌幅| < 0.3% 为横盘日，剔除出两类样本，避免噪声稀释
- 涨日样本：`up_capture = mean(账户日收益) / mean(大盘涨日收益)`
- 跌日样本：`down_capture = mean(账户日收益) / mean(大盘跌日收益)`（亏得少 → 值小；分母为负值，账户亏更少时比值趋 0 或转负）

边界规则：

- 窗口内上涨日或下跌日 < 5 天 → `insufficient_sample`，不参与排名
- 账户窗口内零交易 → fitness 置 NULL 并标注「空仓观察期」（空仓在跌市 down_capture≈0 会虚高分，不能让它赢）
- equity snapshot 缺日：跳过并扣减样本计数；连续缺 3 天标 `data_gap` 不排名
- 基准数据缺失：走 kline 降级链（database→baostock→tencent），全缺则当日不计算

### 3.2 存储

新表 `quant.evolution_fitness`：

| 列 | 说明 |
|---|---|
| account_id | 账户 |
| window_end | 窗口末日（交易日） |
| up_capture / down_capture / fitness | 三项指标 |
| up_days / down_days | 样本计数 |
| status | ok / insufficient_sample / no_trades / data_gap |

每日收盘后由 scheduler 增量计算，历史保留——排行趋势本身也是进化证据。

### 3.3 消费端

- API：`GET /api/evolution/leaderboard?window=20` → 全账户排名 + 明细 + status 标注，走 `{ok,command,data}` 信封
- agent 工具：`evolution_leaderboard`（agent-ts 薄封装）
- **接入 daily_ai_review 复盘 prompt**：agent 每天看到自己排第几、为什么（涨日没跟上 vs 跌日亏多了）——最便宜的进化压力，不用等 Phase 2
- 首批观察账户：agent_virtual、v13_simulation、v14_simulation、user_main_simulation（不同操盘者的自然对照）

### 3.4 Phase 1 验收标准

跑满 20 个交易日后：已知差的（v14，-52.86%）应稳定垫底，已知好的（agent_virtual，+2.48%）应靠前。**若度量分不出好坏，改公式，不硬上 Phase 2。**

## 4. Phase 2：目标驱动进化循环

### 4.1 核心循环（每代 20 个交易日）

```
定目标 → 执行 → 测量 → 对照目标反思 → 提出一个行为改动 → 下一代验证
```

**定目标**：
- 北极星：年化跑赢沪深300
- 每代战术目标默认：`up_capture ≥ 1.0` 且 `down_capture ≤ 0.7`
- 之后每代由 LLM 基于大盘环境提议调整（震荡市可放宽 up、收紧 down），人可在 dashboard 改
- 新表 `quant.evolution_goals`（代次、目标值、设定理由）——目标本身也是进化对象，防止 agent 给自己定容易目标

**对照目标反思（每代结束，agent-ts 世代任务，LLM 结构化输出三段）**：
1. **差距归因**：未达成项拆为 大盘环境 / 选股 / 择时 / 执行 四类（复用 comparator.ts attributeGap 思路，数据源换 equity snapshot + trades）
2. **验证上代假设**：上代改动的可证伪假设兑现与否 → 兑现保留、未兑现回滚到父代行为
3. **本代唯一改动**：一个行为改动 + 可证伪假设（"因为X，改Y，预期 down_capture 从 a 降到 b"），结构化落库

**行为改动生效**：
- 新表 `quant.behavior_variants`（account_id、generation、parent_id、mutation_hypothesis、behavior_patch(JSONB)、status）
- system-prompt-builder 现有 8 层结构加第 9 层「行为基因」：按 session 账户取当前生效 patch 注入 prompt
- 只作用于 agent_virtual

**传承**：所有假设与结果写入 `quant.agent_knowledge`；同类失败假设永久阻止重提（与缠论蒸馏共用知识表）。

**安全闸**：账户回撤 >15% 立即熔断回滚到父代基因，不等世代结束（复用 strategy_circuit_breaker 模式）。

### 4.2 Phase 2 前置条件

- Phase 1 验收通过（度量被证明有效）
- agent_virtual 有持续交易活动（当前 7 月以来 36 笔，满足）

## 5. 测试策略

TDD。fitness 计算用合成行情单测，覆盖：纯涨市 / 纯跌市 / 混合 / 横盘剔除 / 样本不足 / 空仓账户 / snapshot 缺日 / 基准缺失降级。API 契约测试对齐 `{ok,command,data}` 信封（FastAPI 侧）。Phase 2 反思任务用 golden 数据测试结构化输出解析与假设回滚逻辑。

## 6. 明确不做（YAGNI）

- 不做策略参数级/策略组合级进化（策略体检 + 动态权重已覆盖）
- 不做回测重放筛选（LLM 行为不可复现，伪精确）
- Phase 1 不动 weekly_evolution 旧引擎；Phase 2 上线并验证后将其退役
- 不做多账户种群竞争（未来选项；届时需先做多账户操作地基 + 账户白名单保护——现有「唯一账本 agent_virtual」prompt 约束是防止乱动用户账户的保护栏，改造时 user_main 等永不进白名单）
- 不做 web 前端排行榜页面（Phase 1 只要 API + agent 工具；页面可随时后补）

## 7. 与既有系统的关系

| 既有件 | 关系 |
|---|---|
| simulation_equity_snapshot | 适应度数据源 |
| 缠论蒸馏（agent_knowledge 表） | Phase 2 假设传承共用知识表；20 日验证窗一致 |
| comparator.ts / attributeGap | 归因思路复用，数据源替换 |
| strategy_circuit_breaker | 熔断模式复用 |
| daily_ai_review | Phase 1 排行榜注入其 prompt |
| weekly_evolution 旧引擎 | Phase 2 验证后退役 |
| evolution_leaderboard 工具 | 新增，注册进 tools/index.ts |
