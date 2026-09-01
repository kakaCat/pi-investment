# 自主能力体系 × Agent OS × quantsys-v2 架构关系（2026-09-01）

> 状态：反映 ADR-002 落地后的真实架构（watch notify_mode 分流 + DSH 原生提醒调度已上线）
> 数据来源：42 个调度任务（15 dsh-native + 26 webhook + 1 其他）、v2 scheduler_tasks 32 启用、watch_rules 31 条（direct 21 / agent 10）

## 一、三者角色

| 层 | 项目 | 角色 | 核心职责 |
|---|---|---|---|
| 大脑 | DSH / agent-dh（:13080） | 投资脑 investor | 决策·交易·学习·进化·自修复；14+ 插件 48+ 工具 |
| 手脚 | quantsys-v2（:5001） | 业务后端 | 行情/K线/财务/策略/回测/交易/盯盘引擎；APScheduler 主调度（Phase 1 转正） |
| 记事本 | Agent OS（:8080） | legacy 基础设施 | memory/notification/scheduler 注册表/窗口花名册；**调度职能已退役，记忆与通知待 C-1 迁移** |

**Autonomy 线（自主能力体系）** 是大脑的自我升级机制，横跨三者：用 v2 数据做决策，用 Agent OS 记忆做积累，用 DSH 插件做自我改造。

- RFC 003：learning 插件（track→analyze→distill→apply）
- RFC 005：自进化闭环（蒸馏→变异→裁决→启用→元学习）
- RFC 006/007/008：genome 基因组（constitution/principles/rules/lessons 4 段）+ 版本化 + 验证门
- lifecycle：self_restart/self_finalize 自修复 + NativeReminderScheduler 原生提醒调度

## 二、演进方向（ADR-002 用户裁决 2026-09-01）

调度权按执行体拆分：

- **数据任务（26 个 webhook）归 v2**：APScheduler 转正主调度，JobRegistry 31 个业务 Job（Phase 1 进行中）
- **agent 提醒任务（15 个 dsh-native）归 DSH**：NativeReminderScheduler cron 直投 followup（Phase 2 ✅ 已完成 2026-09-01）
- **Agent OS 调度职能退役**：剩余 memory/notification 依赖由 C-1 迁移后可整体退役

## 三、调度链路（修复后）

```
数据任务：  v2 APScheduler → JobRegistry → 业务执行（闭环，无跨系统往返）
agent 提醒：OS 注册表(executor=dsh-native) → DSH NativeReminderScheduler 30s tick → followup 投递
盯盘提醒：  v2 WatchEngine → notify_mode 分流
            ├─ direct（21 条·观察提醒）→ feishu_service 直发飞书（不经 LLM）
            └─ agent（10 条·止损止盈）→ /wake 唤醒 LLM 决策
```

## 四、每日自主运行时间线（交易日）

| 时间 | 任务 | 内容 |
|---|---|---|
| 09:25 | pre-market-routine | 持仓核对·集合竞价·regime 仓位上限·告警·情绪 |
| 09:30-15:00 | 交易时段 | **冻结一切进化活动（宪法铁律）**，只交易+打标 |
| 13:00 | afternoon-open-check | regime 复核·账户状态·市场告警 |
| 15:30 | post-market-routine | 对账·风险指标·regime 更新·信号回填·操纵检测 |
| 16:00 | daily-trade-verify + evolution-distill-daily | 对账 + 每日蒸馏（决策→规则候选，预览模式） |
| 16:05 | data-quality-monitor | 数据质量监控 |
| 16:30 | m4-circuit-breaker | 熔断检查（60 日回撤>8% 减半仓） |
| 16:45 | event-calendar-check | 未来 2 日事件预警 |
| 21:00 | daily-kline-sync | K 线同步 |
| 周六 10:00 | evolution-weekly-variant | prompt_evolver 生成 candidate 观察版 |
| 周日 11:00 | evolution-gate-adjudicate | validation_gate 裁决：转正/回滚 |
| 周日 11:30 | meta-learning-weekly | 元学习：哪类变异有效·跨代比较 |
| 周日 12:00 | weekly-report-m6 | 周报飞书推送 |
| 周一 09:30 | — | 通过验证的新基因组随开盘启用 |

## 五、关键不变式

1. 进化永不在交易时段改动正在使用的基因组
2. 交易宪法最高优先级：时段/T+1/仓位上限/止损铁律
3. 提醒任务必须被执行：目标窗口不在线 → 创建新窗口代执行
4. 执行留痕：每次提醒投递写 OS memory（office:reminder:exec，含完整 prompt）
5. C 级信号只观察不交易；无信号空仓合法

## 关联文档

- ADR-002 调度权拆分：`docs/adr/002-scheduler-ownership-split.md`
- 临时方案审计：`docs/work-logs/2026-09/temp-solutions-audit.md`（第 8/9 节为本次修复记录）
- RFC 005 自进化：`agent-dh/docs/rfcs/005-self-evolving-agent.md`
- 自主能力总览：`agent-dh/docs/AUTONOMY-SYSTEM.md`
