# W1 调度器 webhook 任务通道根因与影响面诊断报告

- **任务**：t-1790d5（REQ-261019144524-ec50 · spike · W1）
- **诊断时间**：2026-10-19 17:00 CST · w-503df447（investor）
- **数据来源**：agent-os 源码（executor.go / scheduler.go）、quant_investment 库 tasks / task_runs / task_delivery_backlog 表、agent-os/logs/agent-os.log、macOS 文件系统实测

---

## 0. 结论先行（对设计阶段假设的修正）

**设计阶段 §10 的根因判断需要修正**：「webhook 任务被执行器按占位 command 执行、报 `fork/exec /bin/true: no such file or directory`」是 **2026-09-03 的历史故障**，且 **2026-09-15 已被修复**（17 个任务的 DB 行当日被批量更新，补 webhook_url、command 从 `/bin/true` 改为 `/usr/bin/true`）。agent-os 日志中 grep 到的 4 条 `/bin/true` 报错全部发生在 2026-09-03 23:00，此后再未出现。

**近一周（2026-10-14 ~ 10-19）进化/例程任务大面积 failed 的真实根因不是通道选择，而是 DSH（127.0.0.1:13080）长时间未运行**：task_runs 表中该时段 30+ 条失败记录的错误**全部**是 `dial tcp 127.0.0.1:13080: connect: connection refused`——执行器走的是**正确的 webhook 通道**，只是对端没起。

一句话版：

> **通道选择逻辑本身无 bug（webhook 优先）；09-03 的 command 误执行是任务数据缺 webhook_url 的历史数据问题（09-15 已修）；近一周的大面积失败是 DSH 停机导致的连接拒绝，触发链断在"对端存活"而非"通道选择"。**

---

## 1. 通道选择的代码路径（executor.go / scheduler.go）

### 1.1 执行期通道选择：webhook 优先

`agent-os/internal/kernel/scheduler/executor.go` **L105-115**（`Executor.Execute` 的重试循环内）：

```go
// Execute the task (webhook or command)
if task.WebhookURL != "" {                                   // L109 — webhook 优先
    output, err = e.executeWebhook(ctx, task, run)
} else if task.Command != "" {                               // L111 — 仅当 webhook_url 为空才走命令
    output, err = e.executeCommand(ctx, task.Command, e.config.DefaultTimeout)
} else {
    err = fmt.Errorf("task has neither webhook_url nor command")  // L114
}
```

- `executeWebhook`：executor.go **L307-376**（POST JSON，WP-15 契约，buildWebhookPayload L289-304）。
- `executeCommand`：executor.go **L209-235**，`exec.CommandContext(execCtx, args[0], args[1:]...)`（L221）——**绝对路径直接 exec，不查 PATH**。
- 该「webhook 优先」分支自 2026-08-18（commit `3bf154cef`）起就在源码中，不是新逻辑。

调用链（日志 stacktrace 实证）：`cron.FuncJob.Run` → `Scheduler.scheduleTask.func1`（scheduler.go L315）→ `Scheduler.executeTask`（scheduler.go L376，L418 委托）→ `Executor.Execute`（executor.go L56）。

### 1.2 残留代码陷阱（未引爆，但值得记录）

1. **cron 闭包捕获任务快照**：`scheduler.go` **L321-323**，`s.cron.AddFunc(cronExpr, func() { ... s.executeTask(ctx, task, ...) })`——闭包捕获的是**注册时刻的 `*types.Task` 指针**，任务只在 `Start()` 时从 DB 加载一次（L77 → `loadTasksAndDependencies` L422）。
2. **UpdateTask 不重排非调度字段**：`scheduler.go` **L166-180**，仅当 `existing.Schedule != task.Schedule || existing.Enabled != task.Enabled`（L167）才 remove + 重排。**只改 command / webhook_url 不触发重排**——运行中的调度器会继续用旧快照执行，直到 agent-os 重启。
3. 推论：任何「直接改 tasks 表 command/webhook_url 修复任务」的做法，**必须重启 agent-os 才生效**（2026-09-15 的批量修复能生效，正是因为当时 agent-os 也经历了重启/端口冲突排查，见 memory：w-b1cb22c6 2026-09-15 端口冲突排查）。

---

## 2. 根因结论（一句话）

> **当前线上不存在「webhook 任务被按 command 执行」的通道 bug**：executor.go L109 的 webhook 优先分支工作正常（今日 14:00 起 `agent-brain-realtime-check` 等任务经 webhook 成功）；需求 §2.4 观察到的「进化任务大面积 failed」是 2026-10-14~10-19 DSH（13080）停机造成的 `connection refused`，而设计阶段引用的 `fork/exec /bin/true` 证据是 2026-09-03 的旧日志——当时的真根因是 **tasks 表中 17 个任务的 webhook_url 为空 + command 为占位符**（数据缺陷，非代码缺陷），已于 2026-09-15 通过批量更新 DB 行修复（实证：tasks.updated_at 当日恰好 17 行、与现存 17 个 webhook+占位 command 任务一一对应；memory 中 2026-09-05 w-8366e526 的「19 个任务大规模失败根因与修复」为同一线索链）。

---

## 3. webhook + 占位 command 任务清单（17 条，全部启用中）

全量口径（2026-10-19 17:00 查 quant_investment.tasks）：启用任务 **58** 个，**全部 58 个都配了 webhook_url**，其中 **17 个 command 为占位符 `/usr/bin/true`**（已无任何任务使用 `/bin/true`）：

| # | 任务名 | command | webhook_url |
|---|--------|---------|-------------|
| 1 | afternoon-open-check-live | /usr/bin/true | http://127.0.0.1:13080/agent-os-trigger |
| 2 | agent-brain-daily-audit | /usr/bin/true | 同上 |
| 3 | agent-brain-daily-review | /usr/bin/true | 同上 |
| 4 | agent-brain-morning-analysis | /usr/bin/true | 同上 |
| 5 | agent-brain-realtime-check | /usr/bin/true | 同上 |
| 6 | agent-brain-weekly-distill | /usr/bin/true | 同上 |
| 7 | agent-brain-weekly-evolution | /usr/bin/true | 同上 |
| 8 | agent-brain-weekly-roi | /usr/bin/true | 同上 |
| 9 | attribution-daily | /usr/bin/true | 同上 |
| 10 | evolution-distill-daily | /usr/bin/true | 同上 |
| 11 | evolution-gate-adjudicate | /usr/bin/true | 同上 |
| 12 | evolution-weekly-variant | /usr/bin/true | 同上 |
| 13 | m4-circuit-breaker-live | /usr/bin/true | 同上 |
| 14 | meta-learning-weekly | /usr/bin/true | 同上 |
| 15 | post-market-routine-live | /usr/bin/true | 同上 |
| 16 | pre-market-routine | /usr/bin/true | 同上 |
| 17 | weekly-report-m6 | /usr/bin/true | 同上 |

说明：占位 command 在这些任务上是**冗余配置而非错误**——只要 webhook_url 非空，executor.go L109 的 webhook 分支会先行命中，command 永远不会被执行。它唯一的危险场景是：webhook_url 被清空而 command 残留（即 09-03 事故形态），或未来有人误改通道选择顺序。可考虑后续把这 17 条的 command 清空作为防御（处置建议，非本卡动作）。

---

## 4. `fork/exec /bin/true: no such file or directory` 的解释

两个事实叠加：

1. **这台 macOS 上 `/bin/true` 根本不存在**。实测（2026-10-19，Darwin 25.5.0 arm64）：`/bin/` 目录仅 39 个条目（bash/cat/chmod/cp/.../zsh），**没有 `true`**；`true` 只在 `/usr/bin/true`（-rwxr-xr-x）。新版 macOS 已把 `true` 移出 `/bin`。
2. **Go 的 `exec.CommandContext` 拿到绝对路径时不查 PATH**（executor.go L221），直接 `fork/exec` 该路径；文件不存在 → 内核返回 ENOENT → Go 包装为 `fork/exec /bin/true: no such file or directory`。

因此：任务数据里 command 写的是 `/bin/true`（Linux 习惯路径），在这台 macOS 上必然 100% 失败；换成 `/usr/bin/true`（09-15 修复值）则可执行——但因为 webhook 优先，该占位符实际上也不会被执行。

---

## 5. 影响面（近一周失败的真正构成）

- **2026-10-14 ~ 10-19 上午**：DSH（13080）未运行，30+ 条任务运行记录全部 `connection refused`（含 evolution-distill-daily、evolution-gate-adjudicate、evolution-weekly-variant、agent-brain-weekly-evolution/weekly-distill/weekly-roi/daily-review/daily-audit/morning-analysis/candidate-hunt/core-plan、meta-learning-weekly、strategy-loop-weekly、weekly-report-m6、pre-market-routine 等——与需求 §2.4 清单完全吻合）。
- **投递积压（2026-09-11 上线的 DeliveryBacklog）部分兜底**：`task_delivery_backlog` 共 90 条，**31 条 delivered**（今日 DSH 11:07 恢复后，今早的 pre-market-routine / core-plan / morning-analysis / candidate-hunt 等 9 次尝试内补投成功）；**59 条 failed**（2026-09-23 ~ 10-19 期间耗尽 10 次补投上限最终丢失，分布：agent-brain-realtime-check 12、daily-audit 5、order-sentinel-night 5、evolution-distill-daily 4、daily-review 4 等 27 个任务）。
- **结论**：多天级停机超出了补投机制的设计窗口（90s 内存重试 + 10 次持久补投），这部分运行**永久丢失且无任何告警**——这正是需求根因假设 4「失败无告警闭环」的实证。

## 6. 对后续 W 卡的输入

- **W 卡修触发链（SP-1）的正确对象不是 executor.go 通道选择**（它没坏），而是：①DSH 存活保障（launchd KeepAlive 已覆盖 13080，但 10-14~10-19 为何长时间停机需另查）；②多天级停机超补投窗口时的告警闭环；③（可选防御）17 条占位 command 清空 + UpdateTask 对 command/webhook_url 变化也触发重排（scheduler.go L167）。
- 需求 §10 待答问题 1「执行器为何不走 webhook 通道」答案：**它走；不走是 09-15 之前的数据缺陷，已修**。问题 4「payload 指向的 SOP 是否过期」不在本卡范围，留待后续。

## 7. 补遗：reqboard 自动链"静默空转"误判修正（2026-10-20，w-503df447）

**断点记录曾假设**：reqboard_task_run 三次派发"静默空转"（疑似 selectAdvanceEvent/autoRun 写入链路问题）。**经台账实证证伪**：

- 自动链本身健康：每次派发都真实执行了 driveChain，证据在 `.dsh-data/dsh-reqboard.json` 的 `advance.history`——四次派发（09:02/09:05/09:24/12:51）各产生一条 `FINALIZE_PARENT(t-f4e050) failed + PAUSE` 记录，advance-log.md 同步落文。
- **真实堵点**：`selectAdvanceEvent`（advance-select.ts L58-65）优先级 1 = 收尾——t-f4e050 处于 in_progress 且子卡全 done，每次派发都先选中它的 FINALIZE_PARENT；而它的 done 凭证门（assertDoneEvidence，REQBOARD_NO_EVIDENCE）因"开工以来无干活类工具动作"正确拒绝（诊断已证伪 executor 有 bug，无修复工作可做）→ 失败即 `pauseRequirement`（autoRun=false）。链永远到不了优先级 2 的 RUN_SUBTASK(t-aa8733)。
- **观测面缺口**（本需求的根因假设 4「失败无告警闭环」的新证据）：①reqboard_task_run 对"投递后立即失败熔断"也返回 `status=dispatched` 成功回执；②reqboard_run_status 的 snapshot 不含 stopped/pausedReason；③advance-log.md 的 FINALIZE_PARENT failed 记录无人消费。三重叠加使"链在空转"的表象持续了 3 次派发才人工介入。
- 处置：t-f4e050 前提被诊断证伪，经用户拍板取消（2026-10-20，看板人工操作）；取消后 t-aa8733 经孤儿回收（advance-select.ts L74-86）由自动链闭环。
