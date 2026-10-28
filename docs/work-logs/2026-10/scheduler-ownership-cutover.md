# V2 业务调度归属切换台账（2026-10-27）

- 执行：investor / w-0e4ae20d
- 依据：`quantsys-v2/docs/adr/004-scheduling-ownership.md`
- 用户确认：两阶段切换；先停用已有 V2 覆盖的 17 个 OS 重复入口，再为其余 10 个建立 V2 本地排班并停用 OS 入口。
- 原则：V2 业务由 V2 调度；Agent OS 只保留 Agent 自身任务；通知路由不随调度归属变体。

## 切换结果

- Agent OS → V2 任务：30 条，**启用 0 / 禁用 30**。
- Agent OS 的 Agent 任务：切换前 28 条；切换期间其他会话新增 `agent-brain-stop-loss-preopen`，终验时 29 条（启用 28），均指向 `:13080`。
- V2 APScheduler：原有 47 条启用任务，第二阶段新增/接管 10 条，终验启用 57 条。
- V2 本地 23 条替代/接管排班均存在 `public.apscheduler_jobs` 记录，且下一触发时间在未来。
- DailyJobs 的 K线→因子、筹码、财报、股票池覆盖保持启用。
- `AGENT_OS_ENABLED=false` 未变；`AGENT_OS_NOTIFY_ENABLED` 未改，代码默认仍为 true。

## 两阶段操作

### 第一阶段：17 条已有 V2 覆盖的 OS 入口

已停用：缠论扫描/蒸馏、筹码、数据质量、因子、K线、两类财务更新、市场感知、市场风格、股票池、周报、策略发现、策略验证、V13 风险/验证/周报。

V2 覆盖来自 13 条 APScheduler 任务及 DailyJobs；未删除历史任务或执行记录。

### 第二阶段：10 条需先补 V2 本地能力的任务

- 指数成分更新：V2 task 362。
- 盘中风控：V2 task 351/354/355/356/358/359/360，保留原 10:00、10:30、11:00、13:00、13:30、14:00、14:30 时刻。
- 全策略执行：V2 task 361。
- V2 调度健康检查：复用并恢复 V2 task 327。
- 上述 10 条先以 disabled 配置，代码部署后启用并核验下一触发时间，再停用对应 OS 入口。
- 盘后未手动触发策略交易或止损任务；交易类验证采用 mock 单元测试 + 真实 APScheduler 排班核验，首个业务运行日为 2026-10-28。

## 代码变更

提交 `a06ed029f`（merge commit `def7f0688`）：

- `StrategyExecuteAllJob` / `IntradayRiskCheckJob`：复用既有业务函数接入 JobRegistry，不改交易逻辑。
- `V2HealthCheckJob`：复用 `check_job_health` 接入 V2 本地调度。
- `tools/register_jobs_to_agent_os.py`：公开注册入口按 ADR-004 fail-fast，防止旧任务被重新注册到 Agent OS。
- 更新 V2 调度文档及健康检查旧注释。
- 新增 `tests/infrastructure/test_local_scheduler_job_adapters.py`。

## 验证证据

- 主工作区与 worktree 均执行目标测试：**9 passed**；`py_compile` 与 `git diff --check` 通过。
- 等 `evening_pipeline` 自然完成后才重启 V2：2026-10-27 22:38:12 成功；`chip_distribution` 21:10:40 成功。
- V2 重启后 7 秒健康检查通过，pid 66774。
- `v2_health_check` 经真实 V2 APScheduler 手动触发验证成功：run **8083**，2026-10-27 22:39:33，耗时 118ms。
- 终验：OS→V2 enabled=0；23 条所需 APScheduler jobstore 记录齐全且下次触发在未来；`managed_by_agent_os` 启用行=0。
- before/after 快照与终验摘要：`agent-dh/.dsh-data/state/scheduler-cutover-20261027/`。

## 操作异常与处置

新建健康检查任务时，线上创建接口返回了非预期的 `Unnamed Task / enabled=True`（task 400）。该任务未运行、未手动触发；随即禁用并软删除。改为复用原有软删除的 task 327，清理 `_deleted_at` 后以 disabled 配置，最终正常启用。终验无启用中的意外任务。

## 尚未治理的既有问题（不属于归属切换失败）

1. `check_scheduler_dedup.py` 仍报 5 组 cron 撞点；它们是不同的业务共用时刻，不是同一业务双跑。为不在本次擅自改变交易时序，保留原时刻，后续单独评估错峰：
   - 13:00 盘中风控 / 策略验证；
   - 14:30 盘中风控 / 全策略执行；
   - 15:40 指数成分 / 每日信号执行；
   - 22:30 缠论扫描 / 每日数据更新；
   - 15:35 权益快照 / 计划反思 / 交易对账。
2. 健康检查 run 8083 返回业务 `healthy=false`：高失败率任务 4 个、启用任务缺 domain 15 个；这是本次切换前已有问题。新增/接管的 10 条均已打 domain。
3. `nextRunAt` 摘要中 task 268/269 仍显示 2026-10-26，但实际 jobstore 分别为 2026-10-28 08:00/07:30，属于摘要展示陈旧，不是漏排。
4. 连续干净日目前为 1；10/19、10/20、10/26 的 evening_pipeline 失败均记录为宿主重启造成的孤儿 running，不是本次业务逻辑失败。
5. Agent 侧仍有历史一次性任务治理空间，例如 `post-lift-core-plan-execute-2026-10-20`；未混入本次 V2 迁移。

## 2026-10-28 首日真实运行复核

- V2 十条任务均按排班**触发**；`v2_health_check` run 8601 success（missed=0、zombie=0、domain_missing=0）。
- **7 条盘中风控 + 全策略 + 指数任务全部在业务入口失败**，错误一致：
  `argument after ** must be a mapping, not str`。
- 根因：线上 JSONB `params` 被驱动/会话读成字符串 `'{}'`，`SchedulerRepository._row_to_dict`
  未归一化，Job 类执行 `**params` 立即抛错。调度触发了，但风控/策略实际未执行。
- 修复：仓储边界统一 `_normalize_params`，所有 Job/API 消费方拿到 dict；
  提交 `77a309e07`，目标测试 9 passed。
- 修复后在线验证：`index_constituents_update`（362）手动触发 run 8603 **success**，
  返回指数成分 000300.SH=300、000688.SH=50、399006.SZ=100。
- 7 条风控与 361 全策略未在盘后补触发；下一合法交易日 2026-10-29 10:00–14:30 验证。
- Agent OS 对应 10 项 last_run_at 为 null/旧值，日志中的执行均为 2026-10-27 历史；
  2026-10-28 无新的 `:5001/internal/scheduler/webhook` 执行。
- 次日 16:10 复核提醒：`schedule-07c705f8-e7a8-4626-bff7-cabdaa1da315`。

## 后续复核

2026-10-28 盘后核对 7 条盘中风控、全策略执行、指数成分与健康检查的真实首轮运行，并确认 Agent OS 无对应 V2 执行记录。首日已发现参数字符串缺陷并修复；2026-10-29 盘中重新验证交易类任务。若需回滚，使用上述状态目录的 before 快照；先恢复 OS 入口，再停用对应 V2 新排班，避免保护性任务空档。
