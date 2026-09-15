# REQ-c90f01 实施计划 · 三条残留定时任务清理 + 看板展示加固

- 需求：REQ-c90f01（bug）· 窗口：w-f0d1f4f1（角色 investor）· 计划日期：2026-09-14
- 触发：用户 2026-09-14「会话探针，信号源健康检查，执行看板核验，这个3个定时任务有问题，查看原因」
  + 口径指示「**一次性的应该走 agent 的定时任务**」

## 1. 现象（线上取证 · 2026-09-14 01:5x）

这三条正是双线执行看板「临时/核验/其他」tab 的**全部**成员（`GET :13080/dashboard/api/board` → `byLine.other = 3`）：

| 任务（看板显示名） | 登记在 | 看板上的样子 | 真身 |
|---|---|---|---|
| 会话探针 `session-probe` | v2 任务 id=330 | 计划时刻列显示英文哨兵串 `managed_by_agent_os` + 状态「未启用」 | **无**（OS 作业 `w-f4aa1f6a-session-probe` 已删） |
| 信号源健康检查 `v2_health_check` | v2 任务 id=327（OS 任务镜像） | **计划时刻列显示哨兵串 `managed_by_agent_os`（不是时间）**、下次运行列显示 `None`、状态「未启用」；时间轴 16:45 一格空缺 | OS 任务 `992a47fd`，cron `0 45 16 * * 1-5`（= **工作日 16:45**），enabled，最近 2026-09-11 16:45 success（6 次 100%） |
| 执行看板核验 `board-3341a342-verify-daily-review` | OS 任务 `716f7b3e` | 「上次成功 09-08」，时间轴每天 15:45 挂「待执行」 | 自身，cron `0 45 15 8 9 *`（仅 9/8 触发），已跑过 1 次 success，下次 **2027-09-08** |

取证来源与时点：`GET :13080/dashboard/api/board`、`GET :5001/api/scheduler/tasks`、`GET :8080/api/v1/scheduler/tasks[/stats]`、`board_read`（帖子 `3341a342` 已 `done` @2026-09-08 13:08）、`quant.scheduler_runs`（psycopg2 直查）——均为 2026-09-14 01:5x–02:0x。

## 2. 根因（三类，互不相同）

- **R1 幽灵镜像行**：v2 webhook 写 run 时若任务名在 v2 表里查不到，会 `repo.add_task(cron_expression="managed_by_agent_os", command="agent_os_webhook", params={job_id, managed_by})` 再 `disable_task()`（`quantsys-v2/api/internal/scheduler_webhook.py:347-358`）。窗口 w-f4aa1f6a 2026-09-11 13:37:10 用一次性 OS 作业 `w-f4aa1f6a-session-probe` 打了一发后把作业删除 → v2 侧留下一行 `job_id` 悬空的占位行；全仓无任何 session-probe 实现。
- **R2 影子遮蔽真身 + 时间丢失**：看板把 webhook 指向 `:5001` 的 OS 任务判为 `v2_internal` 排除（`packages/pages/execution/src/services/data-aggregation.ts:222-232`，为避免与 v2 双计）→ 屏幕只剩那条 disabled 镜像行，状态显示「未启用」，与"它每周一到五 16:45 都在跑"的事实相反。
  **用户 2026-09-14 反馈"展示的时间不对"，实测同源**：镜像行的 `scheduleExpr` 是哨兵串 `managed_by_agent_os`（不是 cron）→
  ① 任务表「计划时刻」列 `cronPlan()` 对非 5 段原样返回 → 直接显示英文串 `managed_by_agent_os`（`client/view.ts:22-25`）；
  ② `buildTimeline` 的 `parseCronTime()` 需要分钟/小时两段 → 该行**根本进不了时间轴**（16:30 熔断检查与 17:00 事件入库之间，16:45 那一格空缺，`data-aggregation.ts:96-104`）；
  ③ `nextRunAt` 是 Python 的字符串 `"None"` → 「下次运行」列显示 `None`（`shortDT` 解析失败原样回显，`view.ts:13`）。
  真身的时间（工作日 16:45）因 R2 的排除规则从未进入看板数据 —— **看板不是"显示错了时间"，而是拿不到真身的时间**。
- **R3 一次性任务没有形态**：Agent OS `public.tasks` 只有 `schedule`/`cron` 字段（无 once/task_type；`agent-os/internal/kernel/scheduler/*` 无 once 实现），v2 `quant.scheduler_tasks.task_type` 现存 43 行全为 `cron` → 一次性任务只能用"指定年月日的 cron"硬凑，**跑完不自停**；看板时间轴的频率/执行日判定只看 cron 的 dow（`data-aggregation.ts:106-139 cronFreq / cronDowMatchToday`），dom/month 被忽略 → 该条永远挂「每日 15:45 待执行」。
  **"为何没有自动删除"（用户 2026-09-14 追问）查证结论**：①这两条都没走 v2 的一次性入口 —— `board-3341a342…` 建在 Agent OS（无 once 能力），`session-probe` 的 v2 行是 webhook 自动补建（`add_task` 默认 `task_type='cron'` + `disable_task`），其源 OS 作业是人工删除的；②**更根本：v2 的"执行后删除"是个死开关** —— `scheduler_async.py:266-268` 会写 `params._delete_after_run = True`，但**全仓无任何代码读取它**（repo-wide grep 仅此一处写入），即 `task_type='once'` 的任务跑完（apscheduler `DateTrigger`，`apscheduler_service.py:264-273`）也**不会**被删。

补充事实（同类风险已在线上）：OS 侧现存 2 条日期限定（一次性）任务 —— `board-3341a342-verify-daily-review`（已用毕）与 `agent-brain-live-order-test`（`0 45 9 14 9 *`，**2026-09-14 09:45** 触发，跑完会变成同款滞留任务）。

## 3. 口径（用户 2026-09-14 指示，本计划据此落地）

1. **一次性任务走 agent 的定时任务**（Agent OS / `scheduler_manage` 创建），不进 v2 引擎任务表；v2 引擎表的职责是周期性的数据/信号生产。
2. 一次性任务必须有**可辨识形态 + 用后即弃**。本需求定为：指定日期 cron + `metadata.once=true` + **任务收尾自停**（agent 在任务末尾 `scheduler_manage(update, enabled=false)`）；看板按「一次性」渲染，不再当每日 pending。
3. v2 侧由 webhook 自动生成的镜像行**不是任务**，不单独当任务展示，也不当数据源去猜时间 —— **直接从数据侧清掉**（软删是持久的，见 `cleanup-ledger.md §3 更正 / §4`）。真身的可见性由**看板侧**保证：真身带真实 cron（`0 45 16 * * 1-5` → 工作日 16:45）与真实状态，按 t2 的收窄规则并入看板并标注「由 Agent OS 托管」——**"宁显不藏"落在真身上，不是落在占位行上**。
4. **超时/过期即僵尸**：日期限定（一次性）任务过了执行日仍 enabled、或镜像行 `job_id` 悬空，都应被看板的「僵尸任务」判定捕获并可一键清理（t7）。

## 4. 任务拆分

| key | 标题 | phase | side | 依赖 | 验收 |
|---|---|---|---|---|---|
| t1 | 备份并清理存量残留任务 | implement | backend | — | ①`session-probe`(v2#330) 行 JSON 备份到 `docs/requirements/REQ-c90f01/cleanup-ledger.md` 后删除/停用；②`board-3341a342-verify-daily-review` OS 任务停用或删除；③`agent-brain-live-order-test` 在 2026-09-14 09:45 跑完后停用；④`decision_audit(record)` + `memory_write` 留痕 |
| t2 | 收窄 `v2_internal` 排除规则，让无孪生的 OS 真身回到看板 | implement | backend | — | **前提变更（2026-09-14 02:05）**：v2 侧 5 条镜像行已全部软删（`cleanup-ledger.md §4`），故不再做"镜像行对齐"。改为 `data-aggregation.ts` 的 `osTaskExclusionReason`：webhook 指向 `:5001` 的 OS 任务**仅当存在 v2 孪生任务**（同名去连字符/下划线归一后命中）才排除；无孪生的真身并入看板并标注「由 Agent OS 托管」，计划时刻取真身 cron（`v2_health_check` → 工作日 16:45）。单测覆盖"有孪生→排除 / 无孪生→并入 / 真身 disabled→排除"三分支 |
| t3 | 一次性任务的看板渲染 | implement | backend | — | `cronFreq`/`cronDowMatchToday` 支持 dom/month 限定：当日不匹配 → `off_day`，不再产生长期 pending；用例覆盖 `0 45 15 8 9 *`、`0 45 9 14 9 *` |
| t4 | 一次性任务形态约定（工具提示 + 纪律） | implement | backend | — | `SchedulerManageTool` prompt 写明一次性任务约定（`metadata.once=true` + 收尾自停）；`list` 输出能辨识一次性任务；`memory_write` 记录该纪律供后续窗口检索 |
| t5 | 回归测试 | test | backend | t2,t3 | `npx vitest run packages/pages/execution/tests/` 全绿；新增用例覆盖①镜像行对齐真身（时间/状态取真身）与悬空行计数②一次性 cron 的 off_day 判定 |
| t7 | 僵尸任务判定纳入"超时/过期"（用户口径） | implement | backend | — | 看板「僵尸任务」区目前只认 Agent OS 的"DB 有行但调度器未加载"（`/api/v1/scheduler/orphaned-tasks`，现恒 0），识别不到另外两类：①**日期限定（一次性）任务已过期仍 enabled**（如已删的 `board-3341a342…`：cron 只匹配 2026-09-08，过期后仍 enabled、下次触发 2027-09-08）；②v2 行 `payload.job_id` 悬空（真身已不存在）。在 agent-dh 侧聚合里补判定并进僵尸区（复用现有「清理」按钮），口径写进区标题的说明。单测覆盖"过期一次性→僵尸 / 悬空镜像→僵尸 / 正常周期任务→非僵尸" |
| t6 | 重建产物并线上核验 | merge | fullstack | t5 | `pnpm --filter @pi-investment/dashboard-execution build:client` 成功且 `lib/client.cjs` 可 grep 到改动；重启后线上核验：`v2_health_check` 行计划时刻 = 「工作日 16:45」且时间轴 16:45 出现该项（状态取真身"在跑"/上次成功）、`session-probe` 不再出现、「计划时刻」列无任何 `managed_by_agent_os`、悬空镜像计数在分类对账可见（留存 JSON 证据） |

## 5. 验证与留痕

- 单测：`packages/pages/execution/tests/`（新增镜像行↔真身对齐 + 悬空计数 + 一次性 cron 判定用例）。
- 线上证据：`GET :13080/dashboard/api/board` 改前/改后对比 ——
  ① **已达成（2026-09-14 02:05）**：任务表/时间轴里已无 `session-probe`、`board-3341a342…`，也无任何 `managed_by_agent_` 哨兵串（other 线 3 → 0、任务 65 → 60、v2 可见任务 40 → 34）；
  ② 待 t2 达成：`v2_health_check` 以真身身份回到看板，计划时刻 = 工作日 16:45、时间轴 16:45 入位（`market_perception_daily`/`signal_generate_sell` 同理）；
  ③ 待 t7 达成：僵尸区能列出"过期的一次性任务"与"悬空镜像行"（含清理入口）。
- `GET :8080/api/v1/scheduler/tasks` 改前/改后（32 → 31，`board-3341a342…` 已删）。
- 留痕：`decision_audit(record)`（每条清理一个）+ `memory_write`；工作记录落 `docs/work-logs/2026-09/`。
- 按 R-013，所有引用数据标注来源工具 + 数据时点。

## 6. 边界（本需求不做）

- **不改 agent-os（Go）代码**："executor 跑完自动停用"是最彻底的形态，但属跨仓改造（需构建 + 重启 :8080）→ 另立需求；本需求先用"agent 自停 + 看板可见"落地。
- ~~不删 5 条真身仍在的 v2 镜像行~~ **已改**：经复核（`get_task_by_name` 不筛软删 + `add_task` 复活分支）软删是持久安全的，2026-09-14 02:05 已按用户指示软删 5 条（`cleanup-ledger.md §4`）。**不再需要**看板侧过滤镜像行的逻辑；t2 改为让"无孪生"的真身可见。
- **不修 v2 的 `_delete_after_run` 死开关**（只写不读，"执行后删除"承诺未实现）：属 quantsys-v2 仓改动 → 另立需求（要么实现、要么删掉该字段以免误导）。
- **不给 Agent OS 加 `once` 任务类型**（跨仓 Go 改造）→ 另立需求。
- **不处理 `market_style_update` 的 ImportError**（其自检报 57% 失败率、DB 实证 09-07/08/09/10 连续 4 次 `No module named 'infrastructure.scheduler.market_style_jobs'`）：独立线索，另立需求。
- **不动 v2 其余 39 条任务**的调度与 v2 引擎侧代码（本需求只在 agent-dh 侧 + 两处数据清理）。

## 7. 风险

- 清理是破坏性动作 → 删前先把行 JSON 备份到台账，留 `decision_audit`；
- "自停"依赖 agent 跑到收尾，失败/超时会让一次性任务滞留 → 看板把「一次性 + 已过期 + 仍 enabled」显式标出（守住"宁显不藏"）；
- 对齐取真身数据依赖 OS 接口 `/api/v1/scheduler/tasks` 可用：该路失败时镜像行退化为「托管详情不可得」（显式标注、不静默显示错误时间），而不是回退显示哨兵串。
