# 架构设计（REQ-261006093620-a315）

**目标一句话**：把"今天该不该自动开火"从"工作日近似"改成"交易日历判定"，并让 v2 的**两条**调度路径
（② 库表 APScheduler / ③ DailyJobs）**共用同一份判据**；跳过在台账里可见，且**不产生误报**。

```
                  +-------------------------------------------+
                  |  application/services/                    |
                  |    trading_day_guard.py  (fail-closed)    |  ← 既有，不动语义
                  |    trading_day_gate.py   (fail-open 策略)  |  ← 本需求新增（唯一判据）
                  +-------------------------------------------+
                        ^                            ^
        import          |                            |          import
        (薄转发)         |                            |          (直接用)
   +--------------------+----+              +--------+---------------------+
   | adapters/inbound/       |              | infrastructure/scheduler/    |
   |   fastapi_app/daily_jobs|              |   job_executor.py            |
   |   /gate.py  ③ 保持行为   |              |   _execute_scheduled_job_impl|
   +-------------------------+              +------------------------------+
                                                        |
                                                        v
                                          quant.scheduler_runs.status='skipped'
```

## 落点与依赖方向（serves: FR-1, FR-2, FR-3）

**判据放 `application/services/trading_day_gate.py`（新建），不放任何一侧的 adapter 里。**

- 现状：判据住在 `adapters/inbound/fastapi_app/daily_jobs/gate.py`（② 的入站适配器目录）。
  ② 的 `infrastructure/scheduler/` 若 import 它，就是**基础设施依赖入站适配器**——方向反了。
- 本仓真实分层：`infrastructure/scheduler/scheduler.py:1345` 已经在 import
  `application.services.stock_screening_service` → **infrastructure → application 是既有合法方向**。
- 因此抽到 `application/services/` 后：③ 的 `daily_jobs/gate.py` 退化为**薄转发**
  （保住既有导入路径与 44 个模块的兼容面），② 直接 import 新模块。**判据只有一份**。

**为什么不是"两边各写一份"**：`gate.py:14` 自己的 docstring 就写着
「判据只有一条，调用方不许各写一份（那正是本仓反复踩的形态）」；同一份"今天是不是交易日"
在两处漂移，正是本需求要消灭的东西。

## 执行期落点，而不是排班期落点（serves: FR-7）

门放在 `job_executor._execute_scheduled_job_impl` 内（读任务之后、建 run 之前），**不**放在
`load_tasks_from_db` / `_create_trigger`。

| | 排班期（注册 job 时判） | **执行期（本设计）** |
|---|---|---|
| 存量 jobstore 旧 job | **需 reload 才生效**（坑：`apscheduler_service.py:369` 实证任务 250 禁用后仍触发 15 天） | **立即生效**，无需 reload |
| 策略值改动 | 需 reload | 每次执行从 DB 读，改一行即生效 |
| 与 cron 的语义冲突 | 要把"跳过某天"表达成 trigger（做不到） | 天然是"到点了，判定后决定跑不跑" |

结论：执行期判定的**主要收益不是省事，而是绕开了"DB 改了但 jobstore 持旧 job"这一族坑**
（该坑在本仓有两次实证：任务 250 残留 15 天、2026-09-13 reload 读库失败导致 27 个 job 全没）。

## 为什么策略是三值而不是布尔（serves: FR-4, FR-5）

布尔 `trading_days_only` 无法表达用户裁定的 D-6（`#232` **只跳法定节假日、周末照跑**）：

- 若 `true` 且判据是"非交易日就跳" → `#232` 周末也被跳（**行为扩大**，超出裁定）；
- 若为了 `#232` 把判据改成"只跳节假日" → 那么"周六排班且吃当日行情"的未来任务就没有档位可用。

故取三值 `trading_day_policy ∈ {always, trading-days, holidays}`：

- `always`（**缺省**）→ 行为与现在完全一致；
- `trading-days` → 非交易日一律跳（周末/节假日/未来都算非交易日，但周末对 `1-5` 任务不可达）；
- `holidays` → 只跳 `source='trading-calendar-holiday'`，周末照跑。

## 人工触发的旁路（serves: FR-6）

**问题**：`trigger_task_now` 现在是 `modify_job(next_run_time=now)`——它让**同一个 job** 立即触发，
执行路径与自动到点**逐字相同**，执行期拿不到任何"这是人按的"信息。也就是说，门一旦落在执行期，
**休市日的人工触发会被一起挡掉**（违反 FR-6）。

**设计**：`trigger_task_now` 改为投递一个**一次性 job**，并在参数里显式带上 `manual=True`：

| | 现状 | 本设计 |
|---|---|---|
| 机制 | `modify_job(f'task_{id}', next_run_time=now)` | `add_job(func=execute_scheduled_job, trigger=DateTrigger(run_date=now), args=[id], kwargs={'manual': True}, id=f'manual_{id}_{epoch}')` |
| 执行路径 | 与自动到点同路径（不可区分） | 同 executor，但 `manual=True` → 不判门 |
| 对 cron 的影响 | **扰动** `next_run_time`（当天的正常排班可能被提前吞掉） | 不动 cron job 的排班（更安全） |
| 收尾 | 一次性触发后回到 cron | 一次性 job 执行后由 APScheduler 摘除（DateTrigger 耗尽） |

对外语义（"立即跑一次"）不变；路由层（`scheduler_async.py:441`）不需要改。

**另一条人工路径天然不受影响**：路由的 legacy fallback `_scheduler.run_task(task_id)`
（`:447`）不经 `execute_scheduled_job`，门碰不到它。

## 文件结构（新建 / 修改，各自职责一句话）（serves: FR-1, FR-2, FR-3, FR-4, FR-6）

| 文件 | 动作 | 职责一句话 |
|---|---|---|
| `application/services/trading_day_gate.py` | **新建** | 唯一判据：`should_skip(policy, now)` + 既有三个兼容函数，永不抛、fail-open |
| `infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py` | **新建** | 加 `trading_day_policy` 列并回填 8 条任务的策略（幂等、可 dry-run） |
| `infrastructure/persistence/orm/models/scheduler.py` | 改 | `SchedulerTaskConfig` 加同名列（否则 ORM 与库表漂移，`test_orm_db_drift.py` 红） |
| `infrastructure/scheduler/job_executor.py` | 改 | `execute_scheduled_job(manual=False)`；读任务后判定策略，跳过则落 `skipped` 并 return |
| `infrastructure/scheduler/apscheduler_service.py` | 改 | `trigger_task_now` 改投一次性 `manual=True` job |
| `adapters/outbound/repositories/scheduler_repository.py` | 改 | 新增 `complete_run_skipped(...)`；抽出私有 `_finish_run(...)` 供 success/failed/skipped 共用 |
| `adapters/inbound/fastapi_app/daily_jobs/gate.py` | 改 | 退化为**薄转发**（re-export），③ 的行为逐字不变 |
| `application/services/should_have_run.py` | 改 | "最近一次真执行"判据**显式**认 `skipped`（不算漏跑、也不算真执行） |
| `scripts/scheduler_watchdog.py` | 改 | 口径同步：`success` → `success` 或 `skipped`（该脚本未见排班，属低成本一致性） |
| `tests/test_daily_jobs_trading_day_gate.py` | 改 | **打桩点迁移**到新模块（见下） |
| `tests/infrastructure/test_apscheduler_service.py` | 改 | `test_trigger_task_now` 断言改成"投递了 manual job" |
| `tests/test_scheduler_trading_day_gate.py` | **新建** | 门 × 策略 × 日期条件的表驱动单测 |
| `tests/infrastructure/test_scheduler_skip_ledger.py` | **新建** | executor 层：休市日落 `skipped`、`manual=True` 照跑、交易日行为不变 |

**不删除任何文件**。

## 打桩点迁移（本设计唯一碰 ③ 文件的动作）（serves: FR-3, FR-8）

`gate.py` 变薄转发后，`TradingDayGuard` 这个名字的**被调函数所在模块**变成
`application.services.trading_day_gate`。既有测试里三处
`monkeypatch.setattr(gate_mod, 'TradingDayGuard', ...)`（`tests/test_daily_jobs_trading_day_gate.py:80/131/139`）
会**静默失效**——桩还在，名字还在，但真日历照跑。

这正是本仓 CLAUDE.md 明载的「打桩点规则（唯一判据）：桩必须打在**被调函数所在的模块**」，
所以迁移必须**同批完成并跑测试**，不允许留到最后。这也是本设计把 `FR-8 回归锁` 与本次改动
绑在一张卡上的原因。

## 回滚路径（serves: FR-1, FR-3, FR-7）

**三层，全部不需要 DDL 回滚**：

1. **业务回滚（首选）**：把 8 行的 `trading_day_policy` 改回 `'always'` → 行为**立刻**回到今天的样子
   （执行期判定 ⇒ 无需 reload、无需重启）。留痕字段仍在，不影响。
2. **代码回滚**：`execute_scheduled_job` 的 `manual` 形参有缺省值 → 旧调用方兼容；
   `daily_jobs/gate.py` 的公开名字全部保留 → ③ 的调用方兼容。
3. **列保留**：`trading_day_policy` 列**不删**（`DEFAULT 'always'` 即旧行为），
   删列属破坏性 DDL、收益为零。

## 不做什么（serves: FR-4）

- **不收敛 ③ 的判定行为**：只做模块搬迁 + 薄转发；③ 的 `skip_non_trading_day` 语义、
  `runtime._run_job` 与 `pipeline` 的用法**逐字不变**。
- **不改 `TradingDayGuard`**：它保持 fail-closed（含"未来 → 非交易日"）。
  `2026-10-08` 在 10-06 当天返回 `source='future'` 是**故意**的写入型口径，
  门不会用它做"复市首日"判定（见 interfaces「判据口径」）。
- **不改 cron 表达式**：门是执行期判定，排班保持 `* * 1-5` 原样。
- **不动 Agent OS 托管任务**（`cron_expression='managed_by_agent_os'`）：它们本就不注册进 APScheduler。
- **不追「早盘要点」卡片产出方**：来源未钉死，属另一条线（见需求 D-3）。
- **不新增第三份调度实现**、不改数据模型主键、不改对外 HTTP 契约语义。
