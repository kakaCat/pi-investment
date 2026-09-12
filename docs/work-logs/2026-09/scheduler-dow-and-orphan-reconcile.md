# 调度体系三个静默缺陷：DOW 口径错位 / 启动对账时序 / 看门狗豁免（2026-09-12）

> 执行：w-c8cae280（investor）｜触发：用户「还有缺少的内容吗」→ 核查中**推翻了自己的初判**（详见 §一）

## 一、起点是一次误判（记录过程，避免后人重走）

盘后发现检查点 `m0_fin_weekly` 状态 `late`，DB 里 `每周财务数据更新`(238) 的
`last_run_at` 停在 09-06、`next_run_at` 停在 09-12 18:30 → 初判「周六任务漏跑，
服务健康时被静默跳过」。**该结论是错的**，两处反证：

1. `public.apscheduler_jobs` 里 `task_238` 的 next_run_time = 1789295400 → **2026-09-13 18:30 周日**；
2. `last_run_at` = 2026-09-06 → **也是周日**。

即执行器按**周日**跑，而 DB 元数据/croniter/检查点按**周六**。真因是 §二。

## 二、缺陷 1：cron 星期（DOW）口径分歧 —— 23 个任务整体错位一天

- `CronTrigger.from_crontab`（APScheduler）按 **0=周一 … 6=周日**；
- 本仓其余全部消费方按**标准 cron（0=周日 … 6=周六）**：`parse_cron`（校验+next_run_at）、
  `scheduler_watchdog.py`（croniter）、Agent OS 侧 robfig/cron、检查点期望、人工书写习惯。

**实证（近三周 scheduler_runs）**：`30 22 * * 1-5` 的「每日数据更新」实际跑 **周二~周六**，
**周一一整天没有 v2 日线流水**；`0 1 * * 0` 的「v13-weekly-report」实跑**周一**。
全部 **23/23** 个带 DOW 的 enabled 任务分歧。

**修复**：库中表达式保持标准 cron 不变，只在交给 APScheduler 的边界翻译 DOW
（新模块 `infrastructure/scheduler/cron_compat.py`，唯一翻译点）。
重启后实测 `apscheduler_jobs` 与 croniter **23/23 一致**：每日数据更新 → Mon 22:30、
每周财务数据更新 → Sat 18:30、v13 周报 → Sun 01:00。

> ⚠️ 行为变更：修复后 **周一恢复完整 v2 日线流水**、周六不再跑 Mon-Fri 任务、
> 周日任务从周一回到周日。首个完整验证窗口是 2026-09-14（周一）。

> 遗留：任务 253 `weekly-strategy-discovery` 的 handler docstring 写「每周日」，
> 而 cron `0 2 * * 6` 依标准 cron 是周六。已按"字符串为准"处理（周六），
> **待用户裁决**：若确为周日，应把 cron 改成 `0 2 * * 0`。

## 三、缺陷 2：启动对账跑在 scheduler.start() 之前 → 禁用任务照跑

`start()` 原顺序是 `load_tasks_from_db()`（内含 `reconcile_jobs`）→ `scheduler.start()`。
未启动的 BackgroundScheduler 上 `get_jobs()` **只返回本次会话 pending 的 job**，
看不到持久化 jobstore 里的历史 job → 对账恒报「无孤儿」。

**实证**：任务 250 `pre-market-scan` 早已 `is_enabled=false`，仍每天 01:25 触发
（近 30 天 15 次），三次进程重启都没摘掉；只有显式 `POST /api/scheduler/reload`
（此时 scheduler 已 running）才摘得掉。

**修复**：`load_tasks_from_db()` 返回 `desired_ids`，`start()` 在 `scheduler.start()`
之后**再对账一次**；并让 enable/disable 路由立即 `reload_tasks()`（此前只改 DB 标志位）。

**故障注入验证**：直连 DB 启用 250 → reload（job 出现）→ 直连 DB 禁用（job 残留）
→ 重启 → 日志 `🧹 孤儿调度任务已摘除: id=task_250 name=pre-market-scan`，
job 28→27 ✅。API 即时性：enable→job 出现、disable→job 消失 ✅。

## 四、缺陷 3：看门狗的"已排期豁免"掩盖真漏跑

`scan_v2` 原逻辑：只要 `apscheduler_jobs` 里 next_run 在未来就整体豁免 missed。
而任务漏掉本次槽位后 APScheduler **本来就会**把 next_run 推到下个周期 → 该豁免恰好把
"漏跑"与"活着"混为一谈（这也是缺陷 1 能潜伏数周无人发现的原因，issues 恒为 0）。

**修复**：改为按 misfire 宽限期判定——宽限期内仍可能补投则豁免；超过宽限期，
未来排期只能说明"下次会跑" → 报 missed。并新增 **未打标检测**
（`public.tasks.agent_line IS NULL` → `os:untagged:*`）。

**验证**（webhook 指向无效地址干跑）：立刻报出 2 项此前不可见的真漏跑
——`应于 09-12 02:00 执行（0 2 * * 6）`、`应于 09-12 18:30 执行（30 18 * * 6）`。

## 五、打标写入路径闭合（承接同日 §六"接口暴露"）

- **Go 写入**：`CreateTaskRequest` + register/update handler + `Create()`/`Update()` SQL
  支持 `agent_line`；
- **未打标可表达**：`ALTER TABLE public.tasks ALTER COLUMN agent_line DROP NOT NULL / DROP DEFAULT`
  （备份 `/tmp/tasks_agentline_20260913-003247/public_tasks_agent_line.json`，27 行；
  分布不变 account 7 / autonomy 5 / other 2 / profit_engine 13）。此前 `NOT NULL DEFAULT
  'profit_engine'` + `Create()` 不写该列 = 新建任务静默继承默认值（9 条 mis-tag 的根因）；
- **工具侧**：`scheduler_manage` 新增 `agent_line` 入参（create/update）；
- **E2E 实测**：带 `agent_line=other` 新建 → 201/other；不带 → 201/**NULL**（未打标）；
  PUT 改 other→account → 200/account；探针清理后生产分布不变。

## 六、补跑

对齐声明口径后，本周六的槽位确实未被服务（07:00 CST 之前的执行按旧口径落在周日）：
- 253 `weekly-strategy-discovery` → 手工 trigger → **success**；
- 238 `每周财务数据更新` → 手工 trigger → **success**（启动对账同时把 running 回填为 success）。

## 七、遗留

1. 253 的"周六 vs 周日"意图待裁决（见 §二 注）；
2. `WATCHDOG_AUTO_RERUN` 仍为 false（只告警不自动补跑）——是否开启需用户决定；
3. v2 侧 `domain` 未打标不做告警（六域正交 + 存在有意保留的 `session-probe` NULL）。
