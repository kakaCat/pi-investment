# ADR-004: 调度归属 —— 业务的归 v2，agent-os 只管 agent

**状态**: 已采纳 ✅
**日期**: 2026-10-02
**决策者**: 用户
**取代**: [ADR-002](002-agent-os-scheduler.md)（该 ADR 的"迁移所有定时任务到 Agent OS"部分作废）

---

## 背景

ADR-002（2026-08-16）决定"把所有定时任务迁移到 Agent OS Scheduler，经 webhook 回调执行"。
但该方案在现网**从未真正生效**，且逐步演化成 **4 条调度路径并存**：

| # | 路径 | 读取源 | 实况（2026-10-01 实测） |
|---|---|---|---|
| ① | Agent OS webhook | Agent OS 8080 | 8080 不可达 → 启动时注册失败 |
| ② | `APSchedulerService` | `quant.scheduler_tasks` | 回退路径；**因 ORM/库表列漂移，一条都加载不了** |
| ③ | DailyJobs 宿主线程 | 代码内 9 个 JobDef | 在跑 |
| ④ | `UnifiedScheduler` | `config/scheduler_jobs.yml` | **空转**：`start()` 只翻标志位，无驱动循环 |

后果：同一时点有 2~3 条任务重复（如 15:30 三条、16:30 三条）；且 ② 静默取不到任务，
"服务在跑但没有任务在跑"——**最后一次成功调度执行停在 2026-09-13**。

## 决策

**业务的定时任务由 v2（quantsys-v2）自己调度；agent-os 只负责调度 agent 自身的任务。**

- 关闭"注册到 Agent OS 调度器"这条路：`AGENT_OS_ENABLED=false`；
- **通知不受影响**：`AGENT_OS_NOTIFY_ENABLED` 保持 true（通知仍"agent 优先、飞书降级"）——
  两个开关职责分离，是 2026-09-24 联调时明确过的（REQ-ad0a t7）；
- v2 侧**只保留两条互补路径**：
  - ② `APSchedulerService`：读 `quant.scheduler_tasks`，跑"非核心数据类"任务
    （实时信号监控、盘前扫描、缠论扫描、策略验证、周报、权益快照、v13 模拟等）；
  - ③ DailyJobs 宿主：代码内 9 个核心数据任务（数据管道、新鲜度巡检、筹码、财报、池刷新等），
    带幂等/补跑/失败告警与 `quant.inprocess_job_runs` 留痕。

## 落地（2026-10-02 · REQ-261001145152-3982 t-2d52a7）

1. **库表去重**：`quant.scheduler_tasks` 启用任务 26 → 16；撞点组 4 → 0。
   清掉：与 ③ 重叠的 6 条（因子计算×2 / K线 / 池刷新 / 进化适应度 / 财务数据）、
   同命令冗余 3 条（`data_update`）、中英同体 1 条；并把"数据流水线"错峰到 16:45。
2. **修模型漂移（这是 ② 一直不工作的真因）**：ORM 声明 19 列、库表只有 16 列，
   `domain` / `task_type` / `misfire_grace_time_seconds` 三列**从未被迁移**，
   导致 ② 的查询直接 `UndefinedColumn` 报错。
   迁移：`infrastructure/persistence/migrations/20261002_scheduler_tasks_missing_columns.py`。
3. **清 jobstore 僵尸**：`apscheduler_jobs` 27 → 16。删掉 11 条不在册的（4 条零代码引用、
   3 条与已排班任务重复、V13/V14 那几条在库里本已禁用却仍在排队）。
4. **删除 ④**：`unified_scheduler.py` + `config/scheduler_jobs.yml` + API 路由 + 专属 e2e 测试；
   `adapters/` 内引用收敛为 0。
5. **运维**：launchd plist 不再设任何 `DISABLE_*`（此前四路全关是为在滞后数据上避免补跑）。

## 后果

- ✅ 同一条业务只有一套调度，不会重复写数据/重复告警；
- ✅ v2 的调度能力回到"可被本仓代码评审"的状态（② 的取数不再被模型漂移挡住）；
- ⚠️ **监视点**：连续 3 个交易日 `quant.inprocess_job_runs` 中每个 job 每日应恰好 1 条 success
  （这是 t-2d52a7 的验收口径）；② 的任务执行记录看 `quant.scheduler_runs`；
- ⚠️ Agent OS 恢复后**也不要**再让它调度 v2 的业务任务（本 ADR 明确归属）。

## 复现命令（在 `quantsys-v2/` 下）

```bash
# 撞点重复应为 0
psql -h 127.0.0.1 -U mac -d quant_investment -At -c \
  "select count(*) from (select cron_expression from quant.scheduler_tasks where is_enabled group by 1 having count(*)>1) t"

# ② 是否真加载了任务（应 16 loaded）
grep "Task loading complete" logs/api.log | tail -1

# jobstore 应只剩在册任务
psql -d quant_investment -At -c "select count(*) from apscheduler_jobs where id not like 'task_%'"
```
