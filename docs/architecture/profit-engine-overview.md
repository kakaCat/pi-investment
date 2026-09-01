# 盈利引擎系统架构：M0-M8 × quantsys-v2 × Agent OS 关系与业务流程

> 日期：2026-09-01（调度拆分 ADR-002 落地后定稿）
> 作者：investor（w-8366e526）
> 读者：新会话/新成员快速建立全局认知；架构变更时对照检查

---

## 1. 一句话定位

**盈利引擎**是目标层（M0-M8 九个能力模块），**quantsys-v2** 是业务后端（数据+计算+调度+存储），**agent-dh** 是 AI 决策层（DSH 插件/工具/提示词基因组），**Agent OS** 是 legacy 残余（仅剩注册表载体 + memory/notification，等待 C-1 迁移后退役）。

```
盈利引擎（要什么能力）          系统承载（在哪实现）
M0-M8 模块定义          →      代码分布在 agent-dh / v2 / OS 三端
```

## 2. 三端职责边界（ADR-002 落地后）

```
┌──────────────────────────────────────────────────────────────────┐
│  用户（你）                                                       │
│  Web GUI :13080 / 飞书通知                                       │
└──────────────┬───────────────────────────────────────────────────┘
               │ 对话 / 通知
┌──────────────▼───────────────────────────────────────────────────┐
│  agent-dh（DSH profile :13080）— AI 决策层                        │
│  15 个插件包、60+ 工具                                             │
│  · 决策大脑：investor 角色 + 基因组提示词（constitution/principles/ │
│    rules/lessons，可进化）                                        │
│  · 原生调度：lifecycle native-scheduler（15 个 agent 提醒任务     │
│    直投 followup：盘前/盘后例程、周报、进化裁决等）                 │
│  · 自修复：self_restart/finalize（wip 检查点+自动回滚+续跑）        │
│  调用 ↓ HTTP                                                       │
├──────────────────────────────────────────────────────────────────┤
│  quantsys-v2（FastAPI :5001）— 业务后端                           │
│  · 数据：K线/财务/因子/资金流/龙虎榜（akshare/sina/baostock 多源）  │
│  · 计算：回测引擎（真实 StrategyCodeService）、组合回测 combo、     │
│    回测矩阵 /api/backtest/matrix、ML 预测（含上线门禁）             │
│  · 交易：虚拟账户撮合（T+1/整手/费用）、滑点追踪                    │
│  · 调度：APScheduler 主调度（33 个业务任务：数据/信号/分析/监控）   │
│  · 存储：PostgreSQL quant_investment（quant schema 73+ 表）         │
├──────────────────────────────────────────────────────────────────┤
│  Agent OS（Go :8080）— legacy 残余 ⚠️ 退役中                      │
│  · 仍承担：任务注册表载体（cron 壳 /bin/true）、memory 存储、       │
│    飞书通知通道                                                   │
│  · 调度职能：已退役（2026-09-01 ADR-002）                          │
│  · 退役前置：C-1 迁移（memory→v2 memory_async、notify→feishu_service）│
└──────────────────────────────────────────────────────────────────┘
```

## 3. 盈利引擎 M0-M8 模块 × 三端映射

| 模块 | 能力 | 主承载端 | 关键组件 |
|------|------|---------|---------|
| **M0 数据地基** | 数据管道+质量门禁 | v2 | data_pipeline_daily/kline_update Job、factor_freshness 门禁、stale 标记 |
| **M1 市场感知** | regime/主线/情绪 | v2+agent-dh | regime_daily/mainline_scan 落库、market_sentiment/retail_panic 工具 |
| **M2 标的工厂** | 股票池+战场评估 | v2+agent-dh | pool_refresh Job、pool_battlefield 工具、pool_battlefield 评估端点 |
| **M3 信号择时** | 信号生成+分级+追踪 | v2+agent-dh | signal_generate Job、signal_track 三级（A/B/C）、signal_perf_backfill（胜率回填） |
| **M4 仓位风控** | regime 仓位映射+熔断 | agent-dh | regime_position_limit 工具、circuit_breaker 检查（60日回撤>8% 熔断） |
| **M5 交易执行** | 下单+滑点+对账 | v2+agent-dh | portfolio_trade/algo_execute 工具、trade:slippage 落库、/api/risk/trade-verify |
| **M6 学习飞轮** | 经验→蒸馏→进化 | agent-dh+v2 | learning_track/analyze/distill、daily_distill、prompt_evolver、genome 版本化 |
| **M7 对手博弈** | 三方对手行为分析 | v2+agent-dh | opponent_behavior/manipulation_detect 工具、fund_flow/lhb 数据 |
| **M8 预测引擎** | ML 预测+质量门禁 | v2 | ml/train+predict（特征同源+scaler）、上线门禁（test_accuracy 分级） |

**读法**：策略与决策逻辑在 agent-dh（工具+基因组），数据与重计算在 v2（API+Job+存储），Agent OS 只剩通道类残留。

## 4. 调度新格局（2026-09-01 拆分后）

```
                    cron 到点
        ┌───────────────┴────────────────┐
        ▼                                ▼
┌───────────────────┐          ┌─────────────────────┐
│ v2 APScheduler     │          │ DSH native-scheduler │
│ （业务任务 33 个） │          │ （agent 提醒 15 个） │
│ scheduler_tasks 表 │          │ lifecycle 插件内建   │
│ → JobRegistry      │          │ 30s tick+cron 解析   │
│ → Job.execute      │          │ → followup 直投窗口  │
└───────────────────┘          └─────────────────────┘
        │                                │
        ▼                                ▼
  数据落库/计算/执行                agent 会话被唤醒执行例程

Agent OS：仅注册表载体（任务 command=/bin/true 空壳 +
          payload.executor='dsh-native' 标记接管权）
```

**原则**：调度权跟执行体走——执行在 v2 的任务由 v2 调度，执行在 DSH 会话的任务由 DSH 调度。

## 5. 业务流程图（每日闭环）

### 5.1 主流程（交易日）

```
                        ┌─ 周末 ─────────────────────────┐
                        │ 策略进化 evolution-weekly       │
                        │ 基因组裁决 validation-gate      │
                        │ 周报 weekly-report              │
                        └────────────▲───────────────────┘
                                     │ 经验沉淀反哺
                                     │
 盘前（09:00-09:30）      盘中（09:30-15:00）      盘后（15:00-16:30）
 ┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
 │ pre-market 例程  │    │ watch 盯盘触发    │    │ post-market 例程  │
 │ ·事件日历检查     │    │ ·价格/涨跌幅预警  │    │ ·trade_verify 对账│
 │ ·事件影响评估     │    │ ·操纵检测告警     │    │ ·risk_metrics 评估│
 │ ·主线扫描         │    │ ·信号执行监控     │    │ ·滑点复盘         │
 │ ·股票池刷新结果   │    │                  │    │ ·信号胜率回填     │
 └────────┬────────┘    └────────┬─────────┘    │ ·经验蒸馏 distill │
          ▼                      ▼              │ ·regime 落库      │
 ┌─────────────────┐    ┌──────────────────┐    └────────┬─────────┘
 │ 信号生成+机会扫描 │    │ 决策执行（有信号时）│             ▼
 │ signal_generate  │    │ R-001 买入确认链： │    ┌──────────────────┐
 │ opportunity_scan │    │ quote→资金→regime │    │ 通知与留痕        │
 └────────┬────────┘    │ 仓位→仓位计算      │    │ ·feishu 日报/告警 │
          ▼             │ R-008 检索历史教训 │    │ ·经验写 memory    │
 ┌─────────────────┐    │ R-009 信号分级A/B/C│    │ ·signal_track 记录│
 │ 信号分级落库     │    │ R-005 下单注明依据 │    └──────────────────┘
 │ A级标准仓/B半仓  │    └────────┬─────────┘
 │ C级只观察       │             ▼
 └─────────────────┘    ┌──────────────────┐
                        │ portfolio_trade   │
                        │ （T+1/整手/仓位上限│
                        │  宪法约束校验）    │
                        └──────────────────┘
```

### 5.2 数据流（感知→决策→执行→学习）

```
数据源层    akshare / sina / 腾讯 / baostock / 东财
   │  多源 fallback + 限速防封
   ▼
采集层      v2 数据任务（APScheduler）
   │  kline_update → data_pipeline → factor_compute → chip_distribution
   ▼
存储层      PostgreSQL quant.*（klines/factors/pools/signals/trades/runs…）
   │  质量门禁：factor_freshness（陈旧>5交易日降级/拒服）、stale 标记
   ▼
感知层      M1：regime_daily（恐慌贪婪+涨跌比+量能）→ market:regime 落库
   │        M7：对手行为/资金流/龙虎榜/操纵检测
   ▼
决策层      agent-dh investor 会话
   │        M2 选战场（pool_battlefield）→ M3 信号分级（A/B/C）
   │        → R-008 检索经验 → M4 仓位映射（regime→上限）→ 止损检查
   ▼
执行层      M5：portfolio_trade（宪法校验）→ algo_execute（大单拆分）
   │        → 成交落库 → trade:slippage 滑点 → trade_verify 对账
   ▼
学习层      M6：learning_track 自动追踪 → experience 经验库
            → daily_distill 蒸馏 → prompt_evolver → genome candidate
            → validation_gate 裁决（观察期不劣于基准→转正/回滚）
            → 基因组新版本生效（自我进化的提示词）
```

### 5.3 账户与风控闭环

```
┌────────────────────────────────────────────────────────┐
│ 虚拟账户 agent_virtual（模拟盘）                         │
│                                                        │
│  每笔交易前：                                           │
│   regime_position_limit ──→ regime 仓位上限校验          │
│   （恐慌≤100%/偏多80%/震荡60%/偏空40%/狂热30%）          │
│   risk_controller ──────→ 单股仓位计算/止损价            │
│   宪法硬约束 ──────────→ 单股≤20%、单行业≤40%、现金≥10%   │
│                                                        │
│  每日盘后：                                             │
│   trade_verify 对账 ────→ 漏单/错单/重复/持仓勾稽        │
│   risk_metrics ────────→ 60日回撤/夏普/VaR              │
│   circuit_breaker ─────→ 回撤>8% 触发熔断（减仓一半+禁开仓）│
│                                                        │
│  纪律线：止损铁律（蓝筹-8%/成长-10%/题材-12%）           │
└────────────────────────────────────────────────────────┘
```

## 6. 关键设计原则（为何这样拆）

1. **数据驱动**：agent 100% 基于工具返回的真实数据决策，禁止编造——所有行情/财务/持仓都来自 v2 API
2. **调度权跟执行体走**：v2 管业务任务、DSH 管 agent 提醒（ADR-002），消灭三层桥接
3. **假数据零容忍**：随机数假回测引擎已拆（E-1），模型上线有 accuracy 门禁（M8-2），陈旧因子有 freshness 门禁（M0-4）
4. **可进化**：提示词基因组（constitution 宪法不可改 + principles/rules/lessons 可进化），验证门裁决防退化
5. **零交易合法**：没有信号时空仓等待是正确决策，系统不为交易而交易

## 7. 已知遗留（按优先级）

| 项 | 内容 | 依赖 |
|---|---|---|
| C-1 | memory/notification 从 Agent OS 迁到 v2（10 插件） | 大工程排期 |
| — | Agent OS 停机全链路演练 | 切换稳定 3 日后 |
| — | 任务注册表迁出 Agent OS | 随 C-1 |
| M1 | catalyst 空、sentiment 覆盖率低（数据问题非工单） | 数据源扩展 |
| D 类 | webhook 密钥清理、一次性脚本归档 | P2 收尾 |

## 8. 端口与入口速查

| 组件 | 端口 | 入口 |
|---|---|---|
| DSH Web GUI（用户对话） | 13080 | `~/.dsh/profiles/investment/start.sh` |
| quantsys-v2 API | 5001 | launchd `com.pi-investment.v2-api`（start-launchd.sh） |
| Agent OS（legacy） | 8080 | launchd `com.pi-investment.agent-os` |
| PostgreSQL | 5432 | `quant_investment` 库，quant schema |

## 相关文档

- [ADR-002 调度权拆分](../adr/002-scheduler-ownership-split.md)（2026-09-01 落地）
- [临时办法审计 v2](../work-logs/2026-09/temp-solutions-audit-v2.md)
- [M0-M8 进度基线](../../agent-dh/docs/work-logs/2026-09/m0-m8-progress-rebaseline.md)
- [M3-2 回测矩阵结果](../../agent-dh/docs/work-logs/2026-08/m3-2-backtest-matrix-results.md)
- [signal-grading 信号分级](./signal-grading.md)
