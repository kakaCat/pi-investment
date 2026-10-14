# 设计 · 架构（每日任务空结果不发飞书）

**需求ID**: REQ-261006165125-23a9
**类型**: feature
**侧**: backend（无前端，无原型）
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

## 1. 落点：把"该不该发"从三处散点收敛到一个判据入口（serves: FR-1, FR-2, FR-4）

现状（`daily_jobs/runtime.py`）通知决策散在三条路径上，各自独立判断：

| 位置 | 现状 | 新设计 |
|---|---|---|
| `runtime.py:126` | 无条件发「▶️ 每日任务开始」 | **删除**；改为 `_arm_running_notice()`（超阈值仍在跑才发） |
| `runtime.py:154` | 内层失败 → 🚨 | **不变**（失败路径不参与静默） |
| `runtime.py:174-180` | 无条件发「✅/⚠️ 每日任务完成」 | **改为** `if should_send_completion(...)` |
| `runtime.py:191` | 异常 → 🚨 | **不变** |

新增模块 `adapters/inbound/fastapi_app/daily_jobs/notify_policy.py`：**纯函数、零 IO、零 DB、零线程**。
`runtime._run_job` 只调它，不再自己判断"这条要不要发"。这条收敛是 FR-1 的落地形态——
以后新增"无事"取值改一处白名单，不必在三个分支里各改一遍。

```
_run_job(job, run_date, manual=False)
  ├─ 交易日门跳过 → 早退（既有分支，已静默；本设计不动它的位置）
  ├─ timer = _arm_running_notice(job)          # 超阈值才发「⏳ 仍在运行」
  ├─ result = job.handler()
  ├─ 内层失败？ → 🚨 照发 → return              # FR-4
  ├─ _mark_done('success', result)
  └─ if should_send_completion(result=result, manual=manual):   # FR-1/FR-2/FR-6/FR-7
         _send_feishu(完成消息)
  finally: timer.cancel()                      # 阈值内完成 → 零消息
```

## 2. 为什么"开始消息"必须换形态（serves: FR-2, FR-3）

"无事则两条都不发"与"开始消息发在 handler 之前"在逻辑上不可同时成立：消息发出时结果尚不存在，
没有任何依据判断这次会不会有产出。三条可选路径：

1. **预检（peek）**：跑前先问 handler"这次有活干吗"——需要每个 handler 提供第二个入口，
   等于改 9 个任务的语义面（且 `evening_pipeline` 这类任务根本无法先验）。**否决**：越界（升级信号①）。
2. **事后抑制**：只压完成消息，开始消息照发——**不满足用户裁定 A**（噪音减半，不是消失）。
3. **超阈值提示（采用）**：开始消息不再宣告"我开始了"，改为"我跑了这么久还没完"——
   这是一条**有信息量**的消息（无事且快速的任务天然不产生它）。

采用 3。代价与兜底：长任务（`evening_pipeline` 常跑 1 小时以上）前 60 秒无声，
由阈值提示 + 失败告警覆盖；阈值可配（`DAILY_JOBS_RUNNING_NOTICE_SECONDS`）。

## 3. 阈值计时不得阻塞任务线程（serves: FR-3）

`_run_job` 已经运行在自己的线程里（`_jobs_loop` / `trigger_job` 各自 `threading.Thread`），
但 handler 是**同步**调用，不能在它前后 sleep 或 join。实现用 `threading.Timer`：

- `_arm_running_notice(job)`：`threading.Timer(secs, _send_running_notice, args=(...))`，
  `daemon=True`，立即 `start()`，返回 timer 句柄；`secs <= 0` 时返回 `None`（关闭该提示，测试用）。
- `finally: timer.cancel()` —— 任务在阈值内结束则回调被取消，**零消息**。
- 回调 `_send_running_notice(job_id, description, secs)` **定义在 `runtime.py`**（不是 `notify_policy.py`）：
  它要用 `runtime._send_feishu` 这个全局名。这是打桩点纪律（E8）的直接后果——
  回调若搬进 `notify_policy.py`，测试就必须改 patch 点，且 guard 用例（`tests/test_notify_guard.py`）会失配。

竞态与语义边界：任务恰在阈值时刻结束时，可能收到一条"仍在运行"+一条完成消息（最多一条冗余），
**不可接受的是漏报失败**——失败路径与 timer 无关，不受影响。

## 4. 与相邻口径的关系（serves: FR-2, FR-5）

- **交易日门跳过（REQ-261005203907-2b8c FR-3）**：已实现"留痕 + 不打扰"，早退点在 `_send_feishu` 之前。
  本设计**不动它的位置**，只把 `skipped` 列入"无事"家族的登记说明（`NO_OP_STATUSES` 不含 `skipped`，
  因为该路径在消息层之前就 return，永远到不了判据）。
- **`no_output` 语气（REQ-261005210015-1603 FR-3）**：那次裁定"零产出改 ⚠️ 语气、仍要发"。
  本设计**取代**它对**定时路径**的效力（D-2）。为避免"旧需求被静默推翻"，处理方式：
  ⚠️ 文案**保留**在代码里，只在 `DAILY_JOBS_NOTIFY_NOOP=true`（开关打开）或 `manual=True` 时可达；
  归档时在项目说明书里更新通知口径（见 `docs/architecture/project-manual.md` 的通知一节）。
- **APScheduler 路径（`infrastructure/scheduler/job_executor.py`）**：只有失败才外发（`severity=high`），
  没有例行开始/完成消息 → 本设计不改它（登记为潜在升级信号②）。
- **`interval` 路径（`daily_jobs/interval.py`）**：只有日志，无 `_send_feishu` → 不改。

## 5. 文件结构（新建 / 修改，各自职责一句话）（serves: FR-1, FR-2, FR-3, FR-6, FR-7）

| 文件 | 动作 | 职责 |
|---|---|---|
| `adapters/inbound/fastapi_app/daily_jobs/notify_policy.py` | **新建** | 通知判据纯函数 + 两个 env 解析（`DAILY_JOBS_NOTIFY_NOOP` / `DAILY_JOBS_RUNNING_NOTICE_SECONDS`） |
| `adapters/inbound/fastapi_app/daily_jobs/runtime.py` | 修改 | `_run_job` 三处通知收敛到判据；新增 `_arm_running_notice` / `_send_running_notice`；`_run_job` 增 `manual` 参数；`trigger_job` 传 `manual=True` |
| `adapters/inbound/fastapi_app/daily_jobs/alerting.py` | 修改 | 完成消息文案组装抽成 `format_completion(job_id, description, elapsed, result, manual)`（含 ⚠️/✅ 选择），供 runtime 调用；`_send_feishu` / `_summarize_result` 不动 |
| `adapters/inbound/fastapi_app/daily_jobs_bootstrap.py` | 修改 | 转发壳 `__all__` 补出新符号（`_arm_running_notice` / `_send_running_notice`）；既有 44 个导入路径不受影响 |
| `tests/test_daily_jobs_quiet_noop.py` | **新建** | 判据与宿主行为的回归锁（见 test-cases.md） |
| `tests/test_daily_jobs_notify_truthfulness.py` | 修改 | 旧口径断言改写（test-cases.md §3 逐条列明） |

**不做**：不改 `alerting._send_feishu` 的通道语义（agent → 飞书降级链）、不改 `_mark_done` / 台账、
不改 `job_run_repository`、不改任何 handler（`no_output` 的产生侧一律不动）。

## 6. 裁定引用（serves: FR-2, FR-3, FR-4, FR-6）

| 裁定 | 设计落点 |
|---|---|
| **D-2**（"没有事情不应该发送飞书信息"） | §1 收敛点、§4 对旧口径的取代关系、`should_send_completion` 的默认静默 |
| **D-3**（A：通用规则 + 两条都不发） | §2 否掉"只压完成消息"与"只修 event_calendar_check"两条路径；FR-3 的阈值提示是其代价兜底 |
| D-1（feature / expert） | 本文档集五份（architecture / interfaces / data-model / use-cases / test-cases） |

## 7. 回滚路径（serves: FR-7）

1. **配置回滚（不改代码）**：`DAILY_JOBS_NOTIFY_NOOP=true` → 恢复"开始必发 + 完成必发（⚠️ 语义）"
   的旧行为。改 plist `EnvironmentVariables` 后 `launchctl kickstart -k gui/501/com.pi-investment.v2-api`。
   注意：旧行为里的"开始消息"在代码层已删除，开关打开时以**立即**发出一条开始消息来复原（见 interfaces.md §4）。
2. **代码回滚**：`git revert` 本需求提交（新增 1 文件 + 改 3 文件 + 测试），无数据迁移、无 schema 变更，
   回滚后无残留状态。
3. **局部回滚**：只需去掉阈值提示而保留静默 → `DAILY_JOBS_RUNNING_NOTICE_SECONDS=0`。
