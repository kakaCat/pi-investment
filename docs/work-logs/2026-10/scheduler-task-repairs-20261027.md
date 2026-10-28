# 定时任务故障逐项修复（2026-10-27）

- 执行：investor / w-0e4ae20d
- 触发：用户要求逐个查看并修复当前 V2 定时任务故障
- 原则：每项先确认根因，再做最小修复；不以“jobstore 有条目”当作业务可用。

## 1. plan_reflect_daily / plan_reflect_weekly

### 根因

`PlanReflectionJob.execute()` 调用 `result_from_dict(summary)`，但该函数签名为
`result_from_dict(action, ok_message, result)`。因此**成功路径和异常路径都会在包装
JobResult 时抛 TypeError**，真实业务结果无法回传。原测试只覆盖 `run()`，未覆盖
`execute()`。

### 修复

`packages/qs_plan/qs_plan/application/reflection_job.py`：

- 成功：`result_from_dict(self.name, "交易计划反思完成", summary)`
- 异常：返回标准 failed JobResult，保留任务名与错误。
- 新增 `execute()` 成功/异常两条回归测试。

验证：`tests/plan/test_reflection_job.py` **16 passed**。
提交：`3febc3fab`。

## 2. core_plan_generate 未知命令

### 根因

`core_plan_generate` 旧 Handler 已被交易计划重构移除，但 scheduler_tasks id=337 仍启用；
替代的 `trading_plan_generate_daily` / `trading_plan_readiness` 未注册，导致每天 09:05
报 `Unknown scheduler command`。

生产已具备新计划表（10 张 trading_plan_* 表）、Job 注册与测试，但任务注册迁移
`20261105e_trading_plan_daily_tasks.py` 未执行。

### 修复

执行现有替代迁移（非本次新写业务）：

- 新增 `trading_plan_generate_daily`：工作日 09:05，id 412。
- 新增 `trading_plan_readiness`：工作日 09:20，id 413。
- 禁用 `core_plan_generate`（id 337），并从 APScheduler jobstore 移除。

验证：jobstore 两条新任务 next_run 在 2026-10-28 09:05/09:20；337 不在 jobstore。
首次真实执行待 2026-10-28 复核。

## 3. watch_scan 30s delivery_failed / 孤儿 run

### 根因

`notify_agent.DEFAULT_AGENT` 是 `agent-ts`，而通知域
`WatchDeliveryPolicy.DEFAULT_AGENT` 是 `agent-dh`。生产未设置
`WATCH_ACCOUNT_AGENT_MAP`，于是未映射账户全部投给 `agent-ts:3002`。

实测 3002 **监听但不响应 /wake**，每次触发固定等待 10 秒超时；候选链按“超时不换人”
纪律停止，`delivered=False`，整个 30 秒扫描任务被判 failed。日志中 10:00、14:16–14:28
每秒级 `Agent notification timeout` 与结果中的 `delivery_failed=1~3` 完全对应。

一次 `watch_scan_30s_pm` run 从 14:28:30 起卡住，18:55 进程重启时被判孤儿，耗时
4小时26分。

### 修复

`notify_agent.DEFAULT_AGENT` 统一为 `agent-dh`，与通知域策略一致；未映射/空账户均
落在线 endpoint。新增默认值一致性测试。

验证：`test_watch_agent_default_alignment.py` + `test_account_routing.py` **13 passed**。
提交：`cf8fbad35`。

说明：单次 agent 调用超时从 10s 恢复为正常响应后，30 秒任务耗时应回到秒级；目前系统没有
独立的“单任务硬超时”执行器，仍保留一次卡死风险，需后续在调度执行层补 watchdog。

## 4. domain 标签缺失

### 根因

历史任务创建路径未写 domain；新 plan 迁移也只写 name/cron/command，导致健康检查
`domain_missing=15`，加入两条新 plan 后变 17。

### 修复

新增幂等迁移 `20261027_scheduler_domain_backfill.py`，按 command 映射六域并只填 NULL，
不覆盖已有标签；先 quant_test apply 验证，再生产执行。

生产结果：**68 启用任务，domain NULL = 0**。
提交：`0711e329e`。

## 当前健康状态

- APScheduler：68 启用任务，68 在 jobstore，0 缺失，0 孤儿；missed=0、zombie=0。
- `domain_missing`：0。
- 仍有 4 条 `high_failure_rate`，来自修复前的历史样本（30 秒档 3 条、plan_reflect_daily）；
  预期由 2026-10-28 起的新成功运行逐步覆盖，不删历史失败记录。
- `core_plan_generate` 已禁用；替代任务首次运行 2026-10-28 09:05/09:20。
- `plan_reflect_daily` 首次运行 15:35，`plan_reflect_weekly` 周六 10:00。
- 30 秒档首次验证 09:30–10:00，检查是否仍有 `delivery_failed`。

## 次日复核

已建提醒 `schedule-9688c682-6f72-456b-8dc0-21e4cdfbe978`（2026-10-28 16:05），
逐项核对 412/413、381/390/391/392、377、337、domain 与 high_failure 趋势。

## 2026-10-28 首日复核结果

- **plan_reflect_daily**：15:35 run 8587 **success**，packed=1、woken=1、overdue=1；通知已送达 agent-dh。
- **plan_reflect_weekly**：周六才到下一次，仍显示历史 failed 属正常。
- **watch_scan 30s**：
  - 381：58/58 success
  - 390：118/118 success
  - 391：60/60 success
  - 392：151/153 success
  - 392 两次失败：一次 `delivery_failed=1`，一次 SQLAlchemy `WatchRule is not bound to a Session`；均为单拍异常，不影响后续扫描。
- **core_plan_generate**：保持禁用，jobstore 已摘除；今日无新的 Unknown command 日志。
- **健康检查**（run 8598，16:05）：missed=0、zombie=0、domain_missing=0、total_enabled=68；
  仅剩 1 条 high_failure：plan_reflect_daily 历史 4/5（含昨天前样本），会随后续成功样本自然下降。
- **trading_plan 412/413 未执行根因**：它们插入时没有 `misfire_grace_time_seconds`，APScheduler 使用默认 5 分钟。
  10-28 宿主约 09:25:47 才恢复调度，412 已迟到 20m47s、413 迟到 5m47s，均超过 5 分钟被跳过，因此没有 run 记录。
  - 已用幂等迁移 `20261028_plan_job_misfire_grace.py` 将两者宽限设为 6 小时；提交 `28e8925c4`。
  - 已 reload APScheduler；next_run 同步为 2026-10-29 09:05/09:20，未在盘后补触发。
  - 次日 10:00 复核提醒：`schedule-895c92b2-a525-4ad1-bc94-03e8833c9e58`。

## 未纳入本次

- V13 06:30 单独日检与 14:30 全策略执行重叠，仍未处理，避免擅自改交易行为。
- cron 撞点治理仍待单独设计。
- 历史 high_failure 指标不清理、不改阈值；用真实成功样本自然收敛。
