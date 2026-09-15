# REQ-c90f01 清理台账 · 残留定时任务

- 窗口：w-f0d1f4f1（investor）
- 执行时点：2026-09-14（Asia/Shanghai）
- 背景：用户报「会话探针 / 信号源健康检查 / 执行看板核验」三条任务有问题；口径「一次性的应该走 agent 的定时任务」。
  三条正处双线执行看板「临时/核验/其他」tab（`GET :13080/dashboard/api/board` → `byLine.other=3`，2026-09-14 01:5x）。

## 1. 会话探针 `session-probe`（v2 任务 id=330）—— 已删除（软删）

- **处置**：`DELETE http://127.0.0.1:5001/api/scheduler/tasks/330`
  （v2 语义：软删 `params._deleted_at` + `is_enabled=false` + 摘除 APScheduler job；行仍在库，历史 run 记录保留）
- **为什么可删**：它**不是任务**，是 v2 webhook 为"无主 run"自动生成的镜像行
  （`quantsys-v2/api/internal/scheduler_webhook.py:347-358`：`get_task_by_name` 未命中 → `add_task(cron_expression="managed_by_agent_os", command="agent_os_webhook", params={job_id, managed_by})` → `disable_task()`）。
  其 `payload.job_id = w-f4aa1f6a-session-probe` 对应的 Agent OS 作业**已不存在**
  （`GET :8080/api/v1/scheduler/tasks` 32 条，无此名）；且全仓（agent-dh / quantsys-v2 / agent-os）**无任何 session-probe 实现**。
- **删除前快照**（`GET :5001/api/scheduler/tasks`，2026-09-14）：

```json
{
 "id": "330",
 "name": "session-probe",
 "domain": null,
 "enabled": false,
 "scheduleKind": "cron",
 "scheduleExpr": "managed_by_agent_os",
 "payload": {
  "command": "agent_os_webhook",
  "description": "Agent OS managed job (job_id=w-f4aa1f6a-session-probe)",
  "job_id": "w-f4aa1f6a-session-probe",
  "managed_by": "agent_os"
 },
 "nextRunAt": "None",
 "lastRun": {
  "id": 3552,
  "taskId": 330,
  "taskName": "session-probe",
  "status": "success",
  "triggeredAt": "2026-09-11 13:37:10.098571+08:00",
  "startedAt": "2026-09-11 13:37:10.098571+08:00",
  "finishedAt": "2026-09-11 13:37:10.115574+08:00",
  "durationMs": 17,
  "payload": {
   "date": "2026-09-11",
   "matched": 0,
   "success": true,
   "anomalies": [],
   "mismatched": 0,
   "total_orders": 0
  },
  "error": null
 },
 "todayTriggered": 0,
 "todaySuccess": 0,
 "createdAt": "2026-09-11 13:37:10.106119+08:00",
 "updatedAt": "2026-09-11 13:37:10.156778+08:00"
}
```

## 2. 执行看板核验 `board-3341a342-verify-daily-review`（Agent OS 任务 `716f7b3e-ee79-4dd5-8c5e-790b34ea21c2`）—— 已删除

- **处置**：`scheduler_manage(action=delete, task_id=716f7b3e-ee79-4dd5-8c5e-790b34ea21c2)`
- **为什么可删**：这是一次性核验任务，**已用毕**——
  cron `0 45 15 8 9 *` 只在 2026-09-08 15:45 触发过一次（success，1 run / 100%）；
  其目标公告板帖 `3341a342-7376-4a38-afb1-fe21b1b4ecb3` 已于 **2026-09-08 13:08 置 done**（`board_read`，2026-09-14）。
  留着只会：① 下次触发 2027-09-08；② 看板时间轴把它当"每日 15:45 待执行"永久挂着
  （cron 频率/执行日判定只看 dow，见 `data-aggregation.ts:106-139`）。
- **删除前快照**（`GET :8080/api/v1/scheduler/tasks` + `scheduler_manage get`，2026-09-14）：

```json
{
 "id": "716f7b3e-ee79-4dd5-8c5e-790b34ea21c2",
 "name": "board-3341a342-verify-daily-review",
 "owner": "investor",
 "description": "[🧠 agent-webhook] board 3341a342 第2观测日核验：2026-09-08 15:35 qv2 daily_review cron run 后核验三项非 failed → complete board",
 "schedule": "0 45 15 8 9 *",
 "cron": "0 45 15 8 9 *",
 "webhook_url": "http://127.0.0.1:13080/agent-os-trigger",
 "payload": {
  "executor": "dsh-webhook",
  "prompt": "【2026-09-08 15:45 board 3341a342 关闭核验（investor 窗口）】背景：qv2 进化引擎 daily_review 三项 failed 修复（daily_orchestrator 三 Service ORM 注入 + exceptions.py 恢复，HEAD 0861c879），9/7 21:20 进程内断点续跑已全绿=第1观测日。本任务核验第2观测日后关闭。\n\n执行步骤：\n1. 核验 9/8 15:35 qv2 cron 调度 daily_review 是否真实执行且三项非 failed：查 /Users/yunpeng/pi-investment/quantsys-v2/logs/launchd-stdout.log 中 2026-09-08 的执行记录（grep 'review_phase' 与 '2026-09-08'），确认 decision_score_service completed（errors=0）且 missed_opportunity_service completed 且 evolution_fitness_service completed（computed≥1），且无 review_phase.*failed / ImportError / Service not registered。\n2. 若三项全绿=第2观测日达成（满足连续2交易日实测绿），用 board_update complete board 3341a342-7376-4a38-afb1-fe21b1b4ecb3（action=complete，note 附日志证据与时间戳，expected_revision 先用 board_read 查当前值）；随后 memory_write + decision_audit 留痕关闭结论，feishu_notify（channel=reports, urgency=normal）告知用户修复验收通过、board 已关闭。\n3. 若未执行或仍有 failed：不要关闭，board_update blocked/编辑附上 9/8 实测证据与诊断（查 launchd-stdout.log / launchd-stderr.log 是否服务崩溃、进程是否在 15:35 在线），feishu_notify（urgency=high, channel=alerts）告警需人工介入，并说明下一步。\n4. 无论结果，注明数据来源（日志文件+时间戳）与窗口署名（investor w-d5f37773）。"
 },
 "timeout": 60,
 "enabled": true,
 "created_at": "2026-09-07T21:52:22.478701+08:00",
 "updated_at": "2026-09-07T21:52:22.478701+08:00",
 "agent_line": "other"
}
```

## 3. 信号源健康检查 `v2_health_check` —— **未删除**（有意保留）

- **Agent OS 真身 `992a47fd-df04-49ec-a84e-9c970bbde00c` 正在跑**：cron `0 45 16 * * 1-5`、`enabled=true`、
  owner=quantsys-v2、webhook→`:5001`；累计 6 次运行、100% 成功，最近 2026-09-11 16:45 success。
  **删掉它 = 停掉信号源/调度健康自检**，不能删。
- **【2026-09-14 02:05 更正】** 上面这条"删了会长回来"的判断**是错的**，已复核推翻：
  webhook 写 run 走的是 `repo.get_task_by_name(job_name)`（`scheduler_repository.py:251-257`），
  该方法**只按名字查、不筛软删**；软删只是写 `params._deleted_at` + `is_enabled=False`，**行还在、名字仍被它占据**。
  于是下次投递会**命中这条软删行、复用它的 id**，只有"名字在表里完全没有行"时才会 `add_task` 新建
  （`add_task` 里对同名软删行是**复活**而不是新建，`scheduler_repository.py:124-157`）。
  ⇒ **软删是持久且安全的**：行从任务列表/看板消失且不会重建，run 仍挂靠同一 task_id（历史与健康检查都不丢）。
- **实际处置（2026-09-14 02:05）**：用户指示"直接删" → 已软删 v2 侧全部 5 条镜像行（见 §5）。

## 4. v2 侧 Agent OS 镜像行（5 条）—— 2026-09-14 02:05 全部软删除

用户指示「先直接给我删除了，这样的超时的应该算僵尸任务」→ 这 5 条都是 webhook 自动生成的
"占位/镜像行"（`cron_expression='managed_by_agent_os'`、`command='agent_os_webhook'`、`is_enabled=false`），
不是可调度任务；它们在看板上以「未启用 + 计划时刻列显示英文哨兵串 `managed_by_agent_os`」出现。

处置：`DELETE http://127.0.0.1:5001/api/scheduler/tasks/{323,324,325,326,327}`（均为 `{"success":true}`）

| id | 名字 | 真身（Agent OS 任务） | 删除前快照（关键字段） |
|---|---|---|---|
| 323 | market_perception_daily | `862847ec-…`（cron `0 30 15 * * 1-5`，enabled） | is_enabled=false, last=2026-09-11T15:30:02 success, next_run=null, domain=monitor |
| 324 | signal_generate_sell | `7f912ff2-…`（`0 30 15 * * 1-5`，enabled） | is_enabled=false, last=2026-09-11T15:30:01 success, next_run=null, domain=signal |
| 325 | market_style_update | `723ad3ad-…`（`0 30 15 * * 1-5`，enabled） | is_enabled=false, last=2026-09-11T15:30:00 success, next_run=null, domain=analysis |
| 326 | signal_perf_backfill_daily | `1deba5ac-…`（`0 45 15 * * 1-5`，enabled） | is_enabled=false, last=2026-09-11T15:45:02 success, next_run=null, domain=signal |
| 327 | v2_health_check | `992a47fd-…`（`0 45 16 * * 1-5`，enabled） | is_enabled=false, last=2026-09-11T16:45:00 success, next_run=null, domain=monitor |

**为什么这次删是持久的**（复核结论，见 §3 更正）：
1. `get_task_by_name` 不筛软删 → 下次 webhook 投递复用同一行 id，**不新建**；
2. `add_task` 对同名软删行走"复活"分支 → 也不会产生第二行；
3. run 记录照旧挂同一 `task_id`（`/api/scheduler/runs` 不做软删过滤，历史完整）；
4. 健康检查不受影响：`find_missed_tasks` 本就排除 `managed_by_agent_%`；`find_high_failure_tasks` 按 task join runs、不看 enabled/软删 → 真身的失败率信号仍在。

**核验（2026-09-14 02:0x）**：`GET :5001/api/scheduler/tasks` 可见任务 **40 → 34**、`scheduleExpr` 以 `managed_by_agent_` 开头的行 **0 条**；
`GET :13080/dashboard/api/board` → `byLine={engine:33, autonomy:13, account:14, other:0}`、任务数 **65 → 60**；
DB 直查 6 行（含 330）**行仍在**、仅带 `params._deleted_at`（可复活）。

**副作用（须知道）**：`market_perception_daily` / `signal_generate_sell` / `v2_health_check` 这 3 条**没有 v2 孪生**，
其真身又因"webhook 指向 :5001 → `v2_internal` 排除"的规则不进看板 ⇒ 它们暂时**从看板上消失**（真身照常运行）。
要恢复可见且显示正确时间，需收窄 `v2_internal` 排除规则（仅"存在 v2 孪生"时排除），见计划 t2。

## 5. 附带记录

- v2 **引擎**调度器本身是有"一次性"语义的：`task_type ∈ {delay, once}` 或 `delete_after_run=true` → `params._delete_after_run`（执行后删除，`scheduler_async.py:266-268`）。
  但 **Agent OS 的 `public.tasks` 没有**（只有 `schedule`/`cron`；`agent-os/internal/kernel/scheduler/*` 无 once 实现）→ 这就是"agent 侧一次性任务跑完不自停"的结构性根因，也是本需求 t4 要定的形态。
- 同类存量仍在：`agent-brain-live-order-test`（`0 45 9 14 9 *`，2026-09-14 09:45 触发）→ 跑完按 t1/自停纪律停用。
