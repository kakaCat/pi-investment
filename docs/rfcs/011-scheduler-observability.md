# RFC 011：双调度系统三层监控体系（Scheduler Observability）

- 状态：提案（Proposed）
- 日期：2026-09-02
- 作者：investor（窗口 w-8366e526）
- 关联：ADR-002（v2 APScheduler 转正主调度）、工具连通性审计 §7.2b（v2_health_check 误报三修）

## 1. 背景与问题

2026-09-01 的事故暴露了调度体系的脆弱性：v2_health_check 首跑发现 **24 missed + 1 zombie + 3 failed**，且发现延迟近 10 小时（早间任务丢失，16:45 才暴露）。根因是现有监控存在 3 个结构性缺口：

| 缺口 | 现状 | 后果 |
|---|---|---|
| ① 监控依赖被监控对象 | v2_health_check 是 v2 内部 handler，由 Agent OS 触发 | v2/Agent OS 任一失联，监控随之失联（盲区） |
| ② 每日一次、纯事后 | v2_health_check 每日 16:45 才跑 | 早间任务丢失要等约 10 小时才发现，当日无法补救 |
| ③ 只告警、不恢复 | 发现 missed 后无补跑机制 | 24 任务丢失只能等次日 cron 自然恢复 |

并且问题不限于 v2——**Agent OS 调度同样需要监控**（当前无任何失联/missed 自检能力，grep 全空）。

## 2. 被监控对象结构（调研结论）

### 2.1 v2（Python APScheduler，:5001）
- 任务表 `quant.scheduler_tasks`（34 启用），执行记录 `quant.scheduler_runs`（status/started_at/completed_at/error/result）
- JobStore `public.apscheduler_jobs`（id=`task_{id}`，**有 `next_run_time` epoch**，可直接判"已排期"）
- misfire 配置：`coalesce=False, max_instances=1, misfire_grace_time=300`
- 已有自检：`v2_health_check` handler（zombie/missed/high_failure 三查）

### 2.2 Agent OS（Go robfig/cron v3，:8080）
- 任务表 `public.tasks`（43 任务/17 启用；15 个 `command=/bin/true` 占位、2 个真 webhook：signal_perf_backfill_daily / v2_health_check）
- 执行记录 `public.task_runs`（status/started_at/finished_at/error/triggered_by）
- **无 next_run_at 字段**——期望执行时间只能从 cron 表达式推算
- 内存 cron + DB 持久化，重启经 `loadTasksAndDependencies()` 恢复
- 存活探针 `GET /health` → `{"status":"ok"}`
- **无任何 missed/heartbeat 自检**

### 2.3 通知通道（关键独立性前提）
- `FEISHU_WEBHOOK_URL`（v2 `.env:45`）为**直连飞书 bot webhook**，不依赖 v2/Agent OS 进程 → 独立看门狗可用它直发告警，满足"监控者不依赖被监控系统"。

## 3. 设计目标与原则

1. **监控者独立性**：第3层看门狗不依赖 v2 或 Agent OS 任一进程存活（否则互挂即盲区）。承载形态：**macOS launchd 独立 cron**。
2. **统一抽象**：两系统 runs 表高度同构（task 外键 + status + started/finished + error），抽象为统一的「期望执行 vs 实际执行」比对模型。
3. **分级告警**：high（失联/zombie/关键任务 missed）→ 飞书强提醒；normal（汇总）→ 报告群。
4. **幂等补跑**：默认「告警 + 人工确认」；白名单幂等任务（数据更新/因子/信号回填）可配置自动补跑。**初期默认不开自动补跑**（防重复执行污染）。
5. **不误报**：复用本轮修复成果——已排期（job store 有未来 next_run）不算 missed；孤儿 run（进程重启遗留）不算逻辑失败。

## 4. 三层架构

```
┌──────────────────────────────────────────────────────────┐
│ 第3层 独立看门狗 scheduler-watchdog（launchd cron, 独立进程）│
│   数据源：直查 PG（public.tasks/task_runs +                 │
│           quant.scheduler_tasks/scheduler_runs/apscheduler_jobs）│
│   探活：curl v2:5001/health + Agent OS:8080/health          │
│   检测：进程失联 / 任务漏执行(期望 vs 实际) / zombie run      │
│   动作：飞书直发告警（独立 webhook）+ 可选白名单自动补跑        │
│   兜底语义：v2/Agent OS 全挂时它仍能发现并告警                │
├──────────────────────────────────────────────────────────┤
│ 第2层 系统内高频自检（各自进程内）                            │
│   v2：v2_health_check 16:45 → 每小时整点哨兵                 │
│   Agent OS：新增 scheduler 自检任务（missed/zombie 检测）     │
│   价值：早发现（小时级），但依赖各自进程存活                   │
├──────────────────────────────────────────────────────────┤
│ 第1层 执行保障（调度器自身，治本减少丢失）                     │
│   v2：misfire_grace_time 调大 + 进程重启后补跑错过的任务       │
│   Agent OS：重启恢复（已有 loadTasksAndDependencies）+        │
│            补跑重启窗口内错过的任务（新增）                    │
└──────────────────────────────────────────────────────────┘
```

## 5. 各层详细设计

### 5.1 第1层：执行保障（治本）

**v2（APScheduler）**
- `misfire_grace_time` 300s → 3600s（1 小时），容忍更长的进程重启窗口
- 新增启动补跑：v2 启动装入任务后，对每个启用任务计算「上次期望执行时刻」，若 `last_run_at < 上次期望时刻` 且距现在 < grace → 立即补跑一次（标记 `triggered_by=startup_catchup`）
- 风险：补跑可能撞上 cron 正常触发 → 依赖 `max_instances=1` + 任务自身幂等性。**仅限白名单幂等任务启用 catchup**（配置 `catchup_enabled` 标志）

**Agent OS（robfig/cron）**
- 重启恢复已有（loadTasksAndDependencies）。新增：启动时对每个启用任务，若 cron 上次应触发时刻在「停机窗口」内且无对应 task_runs 记录 → 白名单任务补跑
- robfig/cron 无 misfire 概念，错过即丢 → 启动补跑是主要补漏手段

### 5.2 第2层：系统内高频自检（早发现）

**v2**：`v2_health_check` 从每日 16:45 改为**每小时整点**（cron `0 0 * * * *`），沿用已修复的三查口径（zombie/missed/high_failure，已排除已排期任务与孤儿 run）。发现 high 级问题即时飞书告警（不复用每日一次的节奏）。

**Agent OS**：新增自检任务 `agent_os_health_check`（每小时），调用 scheduler 内部状态：
- 扫 `public.task_runs`：status='running' 且 started_at < now-1h → zombie
- 对每个启用任务按 cron 推算上次应触发时刻，无对应 task_runs → missed
- 结果写日志 + 复用飞书 webhook 告警

### 5.3 第3层：独立看门狗（兜底，核心新增）

**形态**：`scripts/scheduler_watchdog.py`（纯 Python，仅依赖 psycopg2 + urllib，不 import v2/Agent OS 任何代码），launchd `com.pi-investment.scheduler-watchdog.plist` 每 15 分钟触发一次。

**检测逻辑**（每次运行）：
1. **进程探活**：curl v2:5001/health、Agent OS:8080/health，超时/非 2xx → 记录失联
2. **期望 vs 实际比对**：
   - v2 任务：从 `quant.scheduler_tasks` 取启用任务，按 cron 推算「过去 N 小时内应触发的时刻集合」，逐个检查 `quant.scheduler_runs` 是否有对应记录；但**排除** `apscheduler_jobs` 中 `next_run_time` 在未来的（已排期，切换期不补跑属正常）
   - Agent OS 任务：同上，从 `public.tasks` + cron 推算期望时刻，比对 `public.task_runs`
   - **跳过** `command=/bin/true` 占位任务（不产生实际影响，避免噪音）与 `managed_by_agent_*` 伪任务
3. **zombie 检测**：两系统 runs 表 status='running' 且超过阈值（1h）未完成
4. **失联检测**：进程探活失败 且 该时段有任务应执行却无记录 → 判定系统失联（区别于"系统正常但任务失败"）

**告警与恢复**：
- 所有问题分级，飞书 webhook 直发（high→强提醒）
- 补跑：初期仅告警并附「建议补跑命令」；白名单幂等任务可配置 `--auto-rerun` 直调对应系统的 trigger API（v2 `POST /api/scheduler/tasks/{id}/trigger`、Agent OS `POST /api/v1/scheduler/tasks/{id}/trigger`）

**状态持久化**：看门狗自身写 `quant.scheduler_watchdog_log`（检测时间/发现的问题/动作），避免重复告警（同一问题在恢复前只报一次，恢复后报一次"已恢复"）。

## 6. 统一抽象：期望执行比对模型

核心是把两系统统一为一个函数：`expected_runs(task, since) -> [datetime]` 与 `actual_runs(task, since) -> [datetime]`，差集即 missed。

- v2 的「已排期豁免」用 `apscheduler_jobs.next_run_time`；Agent OS 无此表，用「当前时间在 next 期望时刻之前」等价判断
- cron 解析统一用 `croniter`（看门狗独立引入，6 字段含秒兼容 robfig/cron；5 字段兼容 APScheduler）
- 时区统一 Asia/Shanghai

## 7. 实施步骤（分阶段，可独立交付）

1. **P1 第3层看门狗骨架**：`scheduler_watchdog.py`（探活 + 期望/实际比对 + 飞书告警，只读不补跑）+ launchd plist。最高性价比，最先交付。
2. **P2 第2层 v2 自检高频化**：v2_health_check cron 16:45 → 每小时。
3. **P3 第2层 Agent OS 自检**：新增 agent_os_health_check 任务。
4. **P4 第1层 v2 补跑**：misfire 调大 + 白名单启动补跑。
5. **P5 第1层 Agent OS 补跑**：启动补跑白名单任务。
6. **P6 自动补跑白名单**：看门狗接通 trigger API，白名单幂等任务自动补跑。

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 自动补跑重复执行污染数据 | 初期默认只告警；补跑限白名单幂等任务；任务侧加幂等键 |
| 看门狗误报 | 复用已修复口径；同一问题去重（恢复前只报一次） |
| 看门狗自身挂掉无人知 | launchd KeepAlive + 看门狗每次运行写心跳到 `scheduler_watchdog_log`，可被更高层（如每日人工巡检/未来 meta-watchdog）检查 |
| cron 推算期望时刻有误差 | 容差窗口（期望时刻 ±5min 内的实际 run 视为命中） |

## 9. 验收标准

- 模拟 v2 进程 kill → 看门狗 15min 内检测失联并飞书告警
- 模拟某任务漏执行 → 看门狗报 missed（且不误报已排期/占位/伪任务）
- 模拟 zombie run → 看门狗报 zombie
- v2_health_check 每小时运行且结果落库
- 全程不触发误报风暴（同一问题去重生效）
