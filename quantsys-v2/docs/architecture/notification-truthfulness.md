---
id: notification-truthfulness
title: 每日任务完成通知的如实性契约（有事才说：跑了 ≠ 有产出 ≠ 该发）
summary: 通知分两层——「该不该发」由 notify_policy 判据决定（无事不发），「怎么说得清」由耗时量级、状态分布、计数语义与失败判定守住；含两条失败判定陷阱与一处证据口径陷阱。
type: architecture
status: living
updated: 2026-10-06
owners: [session-2bee6968, session-981b7858]
tags: [notification, daily-jobs, observability, reqboard]
---

# 每日任务完成通知的如实性契约（REQ-261005210015-1603；REQ-261006165125-23a9 扩为两层）

> **2026-10-06 变更（REQ-261006165125-23a9）**：本契约从"**每跑必说、说得清**"扩为
> "**有事才说**"——没有事情发生（`no_output=True` / `status ∈ {no_event, no_op}`）时，
> **开始与完成两条都不发**；旧口径里"零产出改 ⚠️ 但**仍要发**"只保留在**回滚态**与**人工触发**。
> 两层的分工：**发不发**看 `daily_jobs/notify_policy.py`（唯一判据入口）；
> **发出去怎么说得清**看本文余下规则。


## 问题（为什么要有一条契约）

2026-10-05 用户收到这样一张卡片：

```
✅ 每日任务完成：evolution_fitness
耗时: 0.0 分钟
detail[computed=5]
```

而那次运行的 5 行 fitness **全部为 NULL**（样本不足 2 + 无成交 3），
且这种状态**已连续 20+ 天**（全表 280 行只有 60 行有值，最后一天 2026-09-12）。
卡片没说谎（任务确实跑完了），但它让读者把「跑了」读成了「有产出」——
这正是本仓反复治过的「假成功」族缺陷在**消息层**的现形。

**契约**：完成通知**必须**让只读卡片的人分辨出这两件事；分辨不出就算缺陷。

## 五条规则

1. **耗时按量级显示**（`alerting._format_elapsed`）：< 60 秒用秒（1 位小数），否则用分钟。
   1.21 秒的活不许印成 `0.0 分钟`（3 秒以内的任务都会是 0.0）。
2. **摘要必须是人话，且必须含"没做成的动作"**：handler 可在返回值里写顶层 `summary`
   自述文本；`alerting._summarize_result` 见到非空 `summary` 时以它为首段、
   **不再 dump 子字典**。没有 `summary` 的任务输出逐字不变（其他任务零变化）。
   `computed_ok` / `insufficient_sample` / `no_trades` / `data_gap` 在白名单里兜底可见。
3. **无事不发（2026-10-06 起，REQ-261006165125-23a9）**：本次"没有事情发生"时，
   **开始与完成两条飞书都不发**。判据只有一个入口 `daily_jobs/notify_policy.py::is_no_op`：
   顶层 `no_output is True`（**严格** `is True`，`1` / `'true'` 不算）**或**
   `status` 去空白小写后命中白名单 `{no_event, no_op}`。
   **不在白名单内的一律照发**（未知 status、缺失键、非 dict 都算"有事"）——判宽了会静默掉真产出。
   **台账 `status` 仍写 `success`**（`result` 原样）——静默只发生在**外发**层，
   判 failed 会牵动 2h 失败重试与跨日补跑链（代价与收益不成比例）。
   静默时记一条 `logger.info("inprocess_job_notify_skipped", job=…, reason="no_op", manual=…)`——
   日后有人问"今天怎么没消息"，日志能直接回答。
4. **计数语义要诚实**：`computed` 只表示"遍历到的账户数"，**唯一**可称"算出来了"的是
   `computed_ok`；四类状态计数 + `other` 恒等于 `accounts_total`；不许保留写死的计数键
   （历史上的 `skipped: 0` 从没被赋值过）。
   指标口径与返回值口径一致（`evolution_fitness_computed_total` 按 `computed_ok` 累加）。
5. **开始消息改为「超阈值仍在运行」提示（2026-10-06 起）**：`▶️ 每日任务开始` **不再**在 handler
   之前无条件发出（否则"无事"的任务照样先响一声）。默认路径改为：任务超过
   `DAILY_JOBS_RUNNING_NOTICE_SECONDS`（默认 60 秒）仍未结束时，发一条
   `⏳ 每日任务仍在运行：{job_id} … 已跑 N 分钟`；跑完仍按规则 3/6 决定是否发完成消息。
   `<= 0` = 关闭该提示。**旧口径（立即发开始消息）只在回滚态可达**（见下）。

## 失败路径与两条例外（都不受规则 3 约束）

- **失败一律照发**：handler 抛异常、handler 未抛异常但 `find_result_failure` 命中内层失败——
  两类都发 `🚨 每日任务失败`，**不经过** `is_no_op` 判据。`result` 同时含"无事"与失败时
  **以失败为准**（漏报失败的代价远高于多一条噪音）。
- **人工触发必有回执**：`POST /api/jobs/inprocess/{job_id}/run`（`trigger_job`）是人亲手点的，
  即使本次无事也回一条 `✅ 每日任务完成（人工触发）：…`，否则"点了没反应"。

## 回滚（两个环境变量，均只影响消息层）

| 变量 | 默认 | 语义 |
|---|---|---|
| `DAILY_JOBS_NOTIFY_NOOP` | 空/false | `true` = 恢复旧行为：立即发开始 + 完成必发（零产出用 `⚠️ 每日任务完成（无有效产出）：` 语气） |
| `DAILY_JOBS_RUNNING_NOTICE_SECONDS` | `60` | `>0` 超阈值提示；`<=0` 关闭提示；非数回落 60 |

改 plist `EnvironmentVariables` 后 `launchctl kickstart -k gui/501/com.pi-investment.v2-api`。


## 两条失败判定陷阱（踩过一次，写下来）

`infrastructure/scheduler/job_executor.py` 的 `find_result_failure` 会判"内层失败"：

- **下钻只在含 `success`/`status` 标记键的子字典上发生**。所以 `detail` 里
  **不要**放这两个键（放了才会被看）。
- `_NOOP_COUNT_KEYS` 含 **`computed`**，`_GAP_KEYS` 含 `no_data` 等。真正会踩的组合是
  「有标记键 + 某个计数键为 0 + 一个缺口键 > 0」三者同时成立（实测 C 组）；
  单独改名或单独加 `no_data` 都不会误判（实测 A/B 组）。
- 因此两道保险：① `detail` 不带标记键；② **保留 `computed = accounts_total`（恒 > 0）**，
  即使将来有人加了标记键也落不到"计数全 0"。

（另：`_as_int` 把 bool 判为 None —— 这正是 `no_output` 适合当语气标记的原因，不能用 `1`。）

## 测试纪律

- **桩打在被调函数所在模块**：`runtime._run_job` 读的是 `runtime` 自己的全局名，
  所以 `monkeypatch.setattr(runtime, '_send_feishu', ...)` 才有效；打在 `alerting`
  或转发壳 `daily_jobs_bootstrap` 上会**静默失效、真函数照发**（4 张假卡片的来源）。
  同理 `⏳ 仍在运行` 的回调 `_send_running_notice` **必须住 `runtime.py`**，搬走即失配。
- `tests/notify_guard.py` 默认 `fail`：测试期任何未声明的真实外发都让用例变红。
- 回归锁：`tests/test_daily_jobs_notify_truthfulness.py`（格式 / 摘要 / 空转三态 / 降级 /
  失败判定不变式 / 其他任务逐字不变）＋ `tests/test_daily_jobs_quiet_noop.py`（T-1~T-16：
  判据白名单与**反向锁**、宿主四态、回滚态、阈值三态、人工触发）。
- ⚠️ **证据口径陷阱（2026-10-06 实测踩到）**：`tests/test_daily_jobs_quiet_noop.py` 的 `sent`
  夹具里有 `monkeypatch.delenv('DAILY_JOBS_NOTIFY_NOOP')`（刻意的环境隔离）。
  因此 `DAILY_JOBS_NOTIFY_NOOP=true pytest …` **恒过、但不构成回滚证据**——
  它证明的是"用例与环境隔离"。回滚证据只能来自①用例内显式 `setenv`，或②进程级
  `DAILY_JOBS_NOTIFY_NOOP=true python -c "…"`。


## 落点（改动即查）

| 关注点 | 落点 |
|---|---|
| **发不发（唯一判据入口）** | `adapters/inbound/fastapi_app/daily_jobs/notify_policy.py`（纯函数：`is_no_op` / `should_send_start` / `should_send_completion` / 两个 env 解析） |
| 耗时格式化、摘要渲染、完成文案组装 | `adapters/inbound/fastapi_app/daily_jobs/alerting.py`（`format_completion` / `_format_elapsed` / `_summarize_result`） |
| 通知时机、超阈值提示、`manual` 参数 | `.../daily_jobs/runtime.py::_run_job` / `_arm_running_notice` / `_send_running_notice` / `trigger_job` |
| fitness handler 的 summary / no_output / 空转 | `.../daily_jobs/pipeline.py::_job_evolution_fitness` |
| 诚实计数 | `application/services/evolution/evolution_fitness_service.py` |
| 空转读数（只读） | `adapters/outbound/repositories/evolution_fitness_repository.py` |
| 失败判定口径 | `infrastructure/scheduler/job_executor.py` |

## 相邻边界（别改错门）

`runtime.py::_run_job` 还有另一条改动线：**休市日交易日门**（REQ-261005203907-2b8c，
其 `skipped` 分支在自己的 `return` 处结束、且跳过时不发通知）。改这个函数时：
**跳过路径不得经过完成分支**；两条线互不改对方分支。
第三条线是**通知判据**（REQ-261006165125-23a9，规则 3/5）：它只决定"发不发"，
不得改动门的分支位置、也不得改台账写入语义。

## 档案

- `docs/requirements/REQ-261005210015-1603/`（requirement / decomposition / verification /
  notes/observation / reviews / tests）
- `docs/requirements/REQ-261006165125-23a9/`（"有事才说"：requirement / decomposition /
  design×5 / reviews/review-report / tests/test-evidence /
  notes/rollback-and-observation）

