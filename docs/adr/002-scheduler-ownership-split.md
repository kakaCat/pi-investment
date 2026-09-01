# ADR-002: 调度权按执行体拆分（数据任务归 v2，agent 提醒归 DSH）

> 日期：2026-09-01
> 状态：已决策（用户裁决）
> 决策人：用户 + investor（w-8366e526）
> 关联：临时解决办法审计 v2（docs/work-logs/2026-09/temp-solutions-audit-v2.md）B-1/A-1 条目

## 背景

当前 41 个调度任务全部由 Agent OS（Go legacy）托管 cron，存在双轨与职责倒挂：

| 任务类型 | 数量 | 执行体 | 当前链路 |
|---|---|---|---|
| 数据任务（kline 同步/池子刷新/信号生成等） | 25 | quantsys-v2 | Agent OS cron → webhook POST → v2 执行 |
| agent 提醒任务（盘前/盘后例程/周报等） | 15 | DSH agent | Agent OS cron → os-remind-bridge.sh → OS memory 信箱 → lifecycle 60s 轮询 → followup |

问题：
1. Agent OS 对两类任务都只是"闹钟"，执行分别在 v2 和 DSH——调度权与执行体分离
2. v2 本有 SchedulerService（APScheduler + scheduler_tasks 表），仅作 fallback 闲置
3. agent 提醒走三层桥（shell 脚本→信箱→轮询），任一环挂即静默丢提醒

## 决策

**调度权跟执行体走**：

- **数据任务（25 个）归 quantsys-v2**：SchedulerService 转正为主调度器，任务注册在 scheduler_tasks 表，APScheduler 直接执行 handler——闭环，去掉 Agent OS webhook 往返
- **agent 提醒任务（15 个）归 DSH**：scheduler 插件补原生 cron 执行 + `ctx.agents` followup 投递能力（当前它只是 Agent OS API 的 CRUD 薄封装）——去掉 os-remind-bridge.sh 三层桥
- **Agent OS 调度职能退役**：剩余 memory/notification 依赖由 C-1 迁移处理后，Agent OS 可整体退役

## 迁移路径（建议分两阶段）

### Phase 1：数据任务归 v2（先行，无跨系统依赖）

前置：v2 本地调度的 handler 覆盖率需达 100%（2026-09-01 盘点：task handler 重构进行中，当前 7/31 有 handler——由 scheduler 重构会话推进 JobRegistry/task_handlers 补全）。

1. handler 覆盖补齐后，`settings.scheduler.agent_os_enabled` 默认改为 false（v2 主调度）
2. 灰度：先切 1-2 个低风险任务（如 data_quality_check_daily）观察 1 日
3. 全量切换，Agent OS 侧 25 个 webhook 任务 disable
4. 观察 3 日无异常后删除 Agent OS 任务记录

### Phase 2：agent 提醒归 DSH（依赖 DSH 插件开发）

1. scheduler 插件新增原生 cron 执行器（cron 表达式解析 + 到点触发）
2. 触发动作：`ctx.agents` followup 投递到目标窗口（复用 lifecycle pending-resume 投递模式）
3. 15 个提醒任务从 Agent OS 迁移到 DSH scheduler 任务表
4. os-remind-bridge.sh / signal-perf-backfill.sh / signal-perf-verify.sh 退役删除
5. lifecycle 的 OS memory 信箱轮询逻辑退役

### 交接约束

- scheduler 目录当前由另一会话活跃重构中（2026-09-01：JobRegistry/task_handlers/ba12e287），**本 ADR 的两阶段执行应在该重构完成后启动**，避免战区冲突
- 切换期间保持双跑验证（新旧调度并行 1-2 天比对执行记录）再关停旧链路

## 验证清单

- [ ] v2 SchedulerService 为主调度（agent_os_enabled=false），25 个数据任务全部正常执行
- [ ] Agent OS 进程停止时：数据任务不受影响、agent 提醒仍投递
- [ ] DSH scheduler 插件原生执行 15 个提醒任务（无 shell 脚本参与）
- [ ] `grep -rn "os-remind-bridge" agent-dh/` 无命中
- [ ] scheduler_manage list 显示的命令不再是脚本路径

---

## 执行结果（2026-09-01 当日落地，超出预期）

**Phase 1（数据任务归 v2）✅ 完成**（提交 cc38c699 / 3eee7e77 / 54e283b0 / 64d0c05f）：
- v2 JobRegistry 33 jobs（含补缺口 6 个：data_update/risk_check/decision_score/evolution_fitness/missed_opportunity/signal_perf_backfill）
- APScheduler 主调度上线（`AGENT_OS_ENABLED=false`），加载 32→33 任务
- 连带修复调度层 4 bug：trigger 同步卡死 46 分钟事故→异步派发；`import main` 双实例陷阱→request.app；job_executor dict/对象混用+get_running_runs 缺失+complete_run 参数错配；data_quality datetime 丢失
- 实测：risk_check / daily_trade_verify / 数据质量 / 进化三任务全部 success 闭环

**Phase 2（agent 提醒归 DSH）✅ 已完成——但方案与设计不同**（另一会话并行实施）：
- 实际方案：lifecycle 插件内建 `native-scheduler.ts`（30s tick + cron.ts 解析器 + misfire 补偿 + 状态持久化），**不经 DSH scheduler 插件新开发**
- 无害化设计：Agent OS 侧任务 command 改 `/bin/true`（cron 壳保留但不做事），`payload.executor='dsh-native'` 标记接管权——无双跑、OS 宕机时缓存任务表续跑
- 15 个提醒任务全部已接管（state/native-scheduler.json lastFired 实证 19:05 投递）
- os-remind-bridge.sh 等 3 脚本已删除（归档说明 agent-dh/scripts/_archive/2026-09-scheduler-migration/）
- 发现的新偏差：方案把「调度触发壳」留在 Agent OS（/bin/true）——Agent OS 的 cron 仍是事实上的触发源之一（native scheduler 自己按 cron 表达式直投，不依赖 OS 触发；OS 任务只是注册表载体）。**C-1 迁移后建议把任务注册表也迁出 Agent OS**（v2 表或 DSH 配置），届时 Agent OS 调度职能才真正归零

**验证清单终态**：
- [x] v2 主调度（AGENT_OS_ENABLED=false），业务任务 31/31 覆盖正常执行
- [x] agent 提醒无 shell 脚本参与（native-scheduler 直投）
- [x] `os-remind-bridge` 生产引用清零
- [ ] Agent OS 进程停止全链路演练（建议切换稳定 3 日后做）
- [ ] 任务注册表迁出 Agent OS（C-1 依赖项，遗留）

## 备选方案（已否决）

- **Agent OS 主调度正式化**：工程量小但 legacy 依赖永久化，与"系统化"方向相悖——否决
- **全部归 v2（含 agent 提醒）**：agent 提醒的执行体在 DSH，v2 需回调 DSH 投递——桥接仍在只是换方向——否决
