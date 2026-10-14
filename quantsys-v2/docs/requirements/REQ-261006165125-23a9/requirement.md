# REQ-261006165125-23a9 · 每日任务空结果不发飞书（no_event/skipped 静默）

**需求ID**: REQ-261006165125-23a9
**类型**: feature
**作用域**: `quantsys-v2/`（`adapters/inbound/fastapi_app/daily_jobs/`（runtime / alerting / defs）、`tests/`）
**侧**: backend（无界面/交互产出，**不涉及原型**）
**档位**: 轻档（L3 依据见文末；出现"第二个未定决策 / 动架构 / 新增子系统 / 改数据模型"即单向升级重档）

## TL;DR

**2026-10-06 16:45 的 `event_calendar_check` 什么也没发生**（台账 `result = {"status": "no_event",
"pending_in_window": 0, "notified": 0}`、`status = success`、耗时 0.8 秒），
但飞书照旧收到**两条**消息：「▶️ 每日任务开始」+「✅ 每日任务完成」——完成消息里没有事件名，
因为压根没有事件。

```
runtime.py:126   _send_feishu("▶️ 每日任务开始：{job_id}…")        ← 无条件、发在 handler 之前
runtime.py:174   no_output = result.get('no_output') is True       ← 只用来换 ⚠️ 语气
runtime.py:177   _send_feishu("✅/⚠️ 每日任务完成：{job_id}…")      ← 无条件（无事也发）
health.py:230    if not target: return {'status': 'no_event', …}   ← 无事的声明方式（不是 no_output）
```

**本需求要做的**：给 DailyJobs 宿主立一条**通用**通知规则——**本次没有事情发生 → 开始与完成两条
都不发**（台账照留痕、失败照告警）。与既有的"交易日跳过 = 留痕 + 不打扰"先例（E3）取向一致，
只是把该语义从"交易日门"推广到"无产出/无事件"。

## L1 一句话目标 + 可证伪判定标准

**目标**：飞书上只出现"真的发生了事"和"真的出了错"；空跑的完成通知与空跑的开始通知一起消失，
但"跑过、结果是什么"必须能从台账里查出来。

**可证伪判定标准**（跑什么、看到什么算过，逐条对应下方 FR）：

1. 单测：handler 返回 `{'status': 'no_event'}` 或 `{'no_output': True}` → `_send_feishu` **调用次数 = 0**。
2. 单测：handler 抛异常 / 返回内层失败（`find_result_failure` 命中）→ `_send_feishu` **≥1 次**且文案含 🚨。
3. 单测：正常有产出（如 `{'updated': 12}`）→ 完成消息**照发**（1 次）。
4. 台账：无事的那次仍写 `status='success'`（`quant.inprocess_job_runs` 有行、result 原样保留）。
5. 开关：`DAILY_JOBS_NOTIFY_NOOP=true` 时恢复旧行为（两条都发）——可一键回滚。
6. 真实观察：次日起 `event_calendar_check` 台账仍 `success`，飞书侧**无该任务消息**
   （对照 2026-10-06 的 2 条）。

## 边界

### 做什么

1. **立"无事"判据（白名单枚举）**：`result` 里 `no_output is True`，或 `status ∈ {'no_event', 'no_op'}`
   （外加既有交易日门路径的 `skipped`，它已经静默、本次只做统一登记）。
   **未知取值一律视为"有事"**（宁多一条、不漏一条）。
2. **无事 → 开始与完成两条都不发**（用户裁定 A，见 D-3）。这要求"开始消息不得在结果未知前发出"：
   把 `▶️ 开始` 从"无条件立即发"改为**超过阈值仍在跑才发**（默认 60 秒，见 FR-3）。
3. **失败一律照发**：handler 异常、handler 未抛异常但内层失败（`find_result_failure`）、
   `status='failed'` —— 这三类**不受静默规则影响**（FR-4）。
4. **只静默外发，不静默留痕**：`quant.inprocess_job_runs` 的 status/result 语义**逐字不变**
   （沿用既有裁定：判 `failed` 会牵动 2h 失败重试与跨日补跑链，见 E4）。
5. **人工触发例外**：`POST /api/jobs/inprocess/{job_id}/run`（`trigger_job`）是人主动点的，
   必须回一条结果，**即使无事也回**（否则"点了没反应"）。因此 `_run_job` 需要知道触发来源。
6. **可回滚**：新增环境变量开关（默认新行为），出问题一键恢复旧行为（见「接口与数据契约」）。
7. **回归锁 + 一次真实观察**（判定标准 1~6）。

### 不做什么

- **不修 `quant.event_calendar` 的数据来源**：本窗口实测该表 **0 行**、`quant.scheduler_tasks` 里
  `ingest_events_*` **一条都没有**（E6）→ `event_calendar_check` 每天必然 `no_event`。
  这是"事件日历是空壳"的**另一个决定**，本次只登记，不在本需求内修。
- **不动 APScheduler 路径**：`infrastructure/scheduler/job_executor.py` 只在外发 `severity=high`
  的失败通知（E7），没有"开始/完成"这对例行消息，本次不改。
- **不动 `interval` 路径**：`daily_jobs/interval.py` 只有日志（`interval_job_done`），无 `_send_feishu`。
- **不改交易日门（`trading_days_only`）的既有跳过语义**：那条路径的"留痕 + 不打扰"已经落地（E3），
  本需求只把 `skipped` 纳入统一判据，不改它的分支位置。
- **不新增数据表 / 不改任何对外 HTTP 契约 / 不新增第三方依赖**。
- **不动 `no_output` 的产生方**（`pipeline.py:236` 的 `computed_ok == 0` 等）：本需求只改消费侧。

### 边界理由

- 用户可感知的成本是**纯噪声**：9 个在册任务 × 2 条 = 每天最多 18 条飞书，其中空跑占相当比例
  （10-03~10-06 的 `event_calendar_check` 连续 4 天 `no_event`，每天照发 2 条）。
- 修法局部：`_run_job` 里三处 `_send_feishu` 收敛成一个决策函数 + 一个阈值参数 + `trigger_job` 传一个来源标志，
  不动宿主线程模型、不动台账 schema。
- **为什么不能只删完成消息**：用户看到的是"▶️开始 + ✅完成"成对出现的空跑，只删后者等于把噪音减半；
  而"开始消息"的信息量在无事场景下本身就是 0（它宣告了一件不会发生的事）。要真正做到"没有事情不发"，
  就必须让开始消息也具备"结果已知"的前提——这是 FR-2/FR-3 的设计动机。

## 产品定义

### 一句话

每日任务的通知从"**跑了就说**"改成"**有事才说**"：有产出 → 一条完成消息（含耗时与摘要）；
无事 → 一条都不发；出错 → 照旧 🚨 告警；跑过没跑过，去台账看。

### 为什么现在做

1. **用户已明确表态**（D-2）："没有事情不应该发送飞书信息"——这是对现有通知口径的直接纠正，
   不是"再加一个可选配置"。
2. **同类先例已经在本仓落地**：交易日门那次已经裁定"跳过 = 留痕 + 不打扰"（E3），
   并明确写了"通知一旦发出去就白做"；本次是把同一口径补到"无产出/无事件"这一类，属于**收敛口径**而非新发明。
3. **现成的判据已经在 result 里**：`no_output`（E4）与 `status='no_event'`（E5）都已存在，
   缺的只是消费侧的一致性——现在 `no_output` 只换个 ⚠️ 前缀，`no_event` 连前缀都没有。

### 成功长什么样

- 次日 16:45：飞书**安静**；`quant.inprocess_job_runs` 里 `event_calendar_check` 仍是 `success`，
  `result` 仍是 `{"status":"no_event","pending_in_window":0,"notified":0}`。
- 有事件的那天：只收到一条「🚨 未来2日高优事件预警」或「📌 未来2日事件提醒」（事件自己的卡片，不是任务的例行消息）。
- 失败的那天：照旧收到「🚨 每日任务失败：…」。
- `evening_pipeline` 这类长任务：20:30 起跑后**不再有"开始"消息**，但超过阈值仍在跑时有一条
  「⏳ 仍在运行：evening_pipeline …」；跑完有产出则再来一条完成消息。

## 用户与角色

- **项目所有者（人类）**：判断标准是"飞书只在我需要知道的时候响；我按台账能查全"。
- **窗口 AI Agent（本需求实施者）**：按 FR 逐条改，改动集中在 `daily_jobs/runtime.py` 一处决策函数
  + `alerting.py` 一个文案 + `trigger_job` 传参 + 测试。
- **后续维护者 / 新会话**：需要一条明确规则——**"这条消息该不该发"只允许有一个判据入口**
  （`should_notify(...)` 纯函数），禁止在 handler 里各自决定"要不要通知"。

## 功能点（G2 条款）

**FR-1: 立唯一的"无事"判据（白名单 + 默认外发）**
判据实现为纯函数（候选名 `should_notify(result, status, manual)`，落 `daily_jobs/runtime.py` 或 `alerting.py`）：
`result.get('no_output') is True` 或 `result.get('status') in {'no_event', 'no_op'}`（`'skipped'` 沿用既有分支）。
**不在白名单内的一律返回"该发"**——包括 `None`、未知 status、字符串形态的 result。
判据必须可被单测直接调用，不依赖线程/DB。

**FR-2: 无事 → 开始与完成两条都不发**
判据命中时，本次运行**不得**调用 `_send_feishu`（开始、完成都不得）。
台账仍写 `status='success'`，`result` 原样落库；日志仍记 `inprocess_job_start` / `inprocess_job_done`。

**FR-3: 开始消息改为"超阈值仍在跑"提示**
`▶️ 每日任务开始` 不再在 handler 之前无条件发出：改为任务启动后若**超过阈值仍未结束**才发一条
「⏳ 仍在运行：{job_id}（已跑 N 分钟）」；阈值可配（候选 `DAILY_JOBS_RUNNING_NOTICE_SECONDS`，默认 60）。
有产出的任务完成时，完成消息内仍带开始时间与耗时（信息不丢）。
阈值计时不得阻塞任务线程（用已有的宿主线程模型，不新起进程/线程池）。

**FR-4: 失败一律照发（静默规则不覆盖失败）**
以下三类**必须**外发 🚨 告警，且**不受** FR-1/FR-2 影响：
① handler 抛异常；② handler 未抛异常但 `find_result_failure(result)` 命中（内层失败）；
③ 台账 status 为 `failed`。
判据命中"无事"而实际是失败（例如 `{'status':'no_event','success':False}`）时，**以失败为准**（失败优先）。

**FR-5: 只静默外发，不静默留痕**
`quant.inprocess_job_runs` 的写入语义与形状**不变**（status 取值集合不新增；`result`/`error` 原样）。
即：本需求**不**把"无事"记成 `skipped`、**不**改任何 status 语义——静默是消息层决策。

**FR-6: 人工触发必须有回执**
`trigger_job(job_id, force=...)` 触发的运行（含 `force=True`）**始终**发一条完成/失败消息
（无事也发，文案标注"（人工触发）"）。实现上 `_run_job` 需接受触发来源（候选参数 `manual: bool = False`），
定时路径传 `False`、`trigger_job` 线程传 `True`。

**FR-7: 开关与回滚**
新增环境变量 `DAILY_JOBS_NOTIFY_NOOP`（默认空/false = 新行为"无事不发"）；
置 `true` 时恢复**逐字旧行为**（开始时发 + 完成必发 + `no_output` 用 ⚠️ 前缀）。
开关解析必须容错（拼写错误/空值按默认走，不得抛错）。

**FR-8: 回归锁与真实观察**
新增 `tests/test_daily_jobs_quiet_noop.py`：覆盖 无事(no_event) / 无事(no_output) / 有产出 / 异常 /
内层失败 / 人工触发 / 开关打开 七条断言（打桩点按本仓规则打在 `daily_jobs.runtime` 自己的全局名上，
见 E8）；既有 daily_jobs 相关测试全过；产出一次真实观察结论（次日实跑台账 + 飞书侧零消息）。

## 现状取证（2026-10-06 实测）

| 编号 | 证据 |
|---|---|
| E1 | `adapters/inbound/fastapi_app/daily_jobs/runtime.py:126`：`_send_feishu("▶️ 每日任务开始：…")` 在 `job.handler()` **之前**无条件执行 |
| E2 | `adapters/inbound/fastapi_app/daily_jobs/runtime.py:174-180`：完成消息无条件发出；`no_output` 仅决定 `⚠️` 还是 `✅` 前缀 |
| E3 | 既有"不打扰"先例：`runtime.py:104-124` 交易日门早退（注释原文"早退点**必须**在下面那条 `_send_feishu` 之前……通知一旦发出去就白做"），对应 REQ-261005203907-2b8c FR-3 |
| E4 | `no_output` 的既有语义（REQ-261005210015-1603 t-4b35ba）：**只改消息语气、不改台账**；本需求把它升级为"静默"，属与该需求的**行为变更点**（见 R3） |
| E5 | `adapters/inbound/fastapi_app/daily_jobs/health.py:228-231`：`event_calendar_check` 无事时返回 `{'status': 'no_event', 'pending_in_window': 0, 'notified': 0}`——**不含** `no_output` 键 |
| E6 | 本窗口实测（2026-10-06）：`quant.event_calendar` **0 行**；`quant.scheduler_tasks` 里 `command like 'ingest%'` **0 行**（四个 ingest job 虽在 `main.py:107-115` 注册进 JobRegistry，但从未排班）→ 该任务每天必然 `no_event` |
| E7 | `infrastructure/scheduler/job_executor.py:37`：APScheduler 路径只在失败时经 NotificationFacade 外发（`severity=high`），**没有**例行开始/完成消息 → 不在本次范围 |
| E8 | 打桩点规则（`CLAUDE.md`「测试期不得真实外发通知」）：桩必须打在**被调函数所在模块**——`runtime.py` 用 `from …alerting import _send_feishu` 取值导入，故测试须 patch `daily_jobs.runtime._send_feishu` |
| E9 | 台账佐证：`quant.inprocess_job_runs` 2026-10-03~10-06 `event_calendar_check` 连续 4 天 `success` + `no_event`；10-02 为 `failed`（`InFailedSqlTransaction`，缺表毒化会话的旧账） |

### 反向证据（必须一并记录，避免为迎合而罗列）

- **R1（静默可能掩盖"跑了但没干活"）**：`no_output=True` 的任务（如 `evening_pipeline` 因子段零产出）
  静默后，人不再被动知道它"跑了个空的"。**为什么仍接受**：台账仍留 `success` + `result`，
  巡检（`_job_failure_watch` / `freshness_guard`）仍可查；用户要的正是"没事别响"。
- **R2（长任务可见性下降）**：取消立即的"开始"消息后，长任务（`evening_pipeline` 常跑 1 小时以上）
  在前 60 秒内完全无声。**兜底**：FR-3 的超阈值提示 + 失败告警；阈值可配。
- **R3（与既有需求的冲突面）**：REQ-261005210015-1603 FR-3 明确要求"`no_output` 时改 ⚠️ 语气"
  （仍要发）。本需求把它改为静默——**同一行为的相反裁定**，需在设计阶段显式处理（保留 ⚠️ 分支供
  手触发/开关打开时使用，还是删除），并在归档时更新说明书里的通知口径。
- **R4（判宽了会漏报真产出）**：把 `status` 里的正常值误当"无事"会静默掉真实产出。
  **对策**：FR-1 用白名单枚举 + 默认外发；新增"无事"取值必须走设计阶段登记，不许就地加字符串。

## 接口与数据契约

- **内部接口（签名变更）**：
  - `_run_job(job: JobDef, run_date: str, manual: bool = False)`（新增可选参数，默认 `False` = 定时路径）；
  - 新增纯函数 `should_notify(result, *, manual: bool = False) -> bool`（FR-1/FR-4/FR-6 的唯一判据入口）。
- **数据契约**：`quant.inprocess_job_runs` **零变更**（不新增 status 取值、不改 result 形状）。
  被消费的结果键 = 既有 `no_output: bool` / `status: str`（**不新增键**）。
- **配置契约（新增 2 个环境变量，均有默认值、均可回滚）**：
  | 变量 | 默认 | 语义 |
  |---|---|---|
  | `DAILY_JOBS_NOTIFY_NOOP` | 空/`false` | `true` = 恢复旧行为（无事也发两条） |
  | `DAILY_JOBS_RUNNING_NOTICE_SECONDS` | `60` | 超过该秒数仍未结束 → 发一条"仍在运行" |
- **对外 HTTP 契约**：无变化（`/api/jobs/inprocess/*` 的响应字段不变）。
- **迁移与兼容路径**：无数据迁移；旧行为可经 `DAILY_JOBS_NOTIFY_NOOP=true` 环境变量一步恢复
  （改 plist 的 `EnvironmentVariables` 后 `launchctl kickstart -k`）。

## 判定标准（可跑）

1. `./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q` → 全过（7 条断言，见 FR-8）。
2. 回归：`./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_daily_jobs_trading_day_gate.py tests/test_daily_jobs_notify_truthfulness.py tests/test_false_success_guard.py -q` → 全过。
3. 零外发：上述用例须在 notify-guard 下跑（未声明的真实外发会让用例失败），会话末 `egress=0`。
4. 台账不变：`psql -d quant_investment -Atc "select status, result->>'status' from quant.inprocess_job_runs where job_id='event_calendar_check' order by run_date desc limit 1;"` → `success` / `no_event`。
5. 开关回滚：`DAILY_JOBS_NOTIFY_NOOP=true ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q`
   → "旧行为"两条用例转绿（证明可回滚）。
6. 真实观察：次日 16:45 之后，`quant.inprocess_job_runs` 仍有该任务的 `success` 行，且飞书侧
   **无**「▶️ 每日任务开始」/「✅ 每日任务完成：event_calendar_check」两条（对照 2026-10-06 实发 2 条）。

## 轻档依据（L3）与升级信号

- **L1 一句话目标 + 可证伪判定**：见「产品定义」与「判定标准」1~6（命令 + 期望输出写死）。
- **L2 范围边界 ≤3 条**：见「做什么 / 不做什么」，显式排除 APScheduler 路径、interval 路径与事件数据源。
- **L3 轻路径依据**：改动面小（1 个纯函数 + `_run_job` 三处通知收敛 + `trigger_job` 传参 + 1 个测试文件），
  判据键**已存在**（`no_output` / `status`），不动数据模型、不新增子系统。
- **单向升级信号**（出现即升重档、改走完整设计）：
  ① 设计阶段若要动 `no_output` 的**产生侧**（各 handler 自报"无事"的口径统一）——那是多个任务的语义改造，
  属**第二个未定决策**；
  ② 若要把规则推广到 APScheduler 路径（`job_executor` 的通知口径）——**动架构**（两条调度路径共用通知策略）；
  ③ 若要引入"通知分级/聚合"（如每日汇总一条）——新增子系统。
- **提示词难度**：`expert`（立项弹框作答，见 D-1）。

## 讨论与裁定记录（D-x）

| 编号 | 原话来源 | 裁定 | 影响 FR | 判据 |
|---|---|---|---|---|
| D-1 | 立项弹框作答（本窗口，2026-10-06 16:51）：名称「每日任务空结果不发飞书（no_event/skipped 静默）」/ 类型 feature / 难度 expert / 文档位置 `docs/requirements/<REQ>/` | 本工作立项为 **feature**，难度 expert，文档落 `docs/requirements/REQ-261006165125-23a9/` | FR-1~FR-8 | `reqboard_status` 显示本窗口绑定 REQ-261006165125-23a9 |
| D-2 | 本窗口用户消息（2026-10-06）：「没有事情不应该发送飞书信息」（前置消息：「没说是什么事件」） | **无事实发生 → 不得外发通知**：空跑的"开始/完成"两条都属于应当消失的噪音；本裁定优先于 REQ-261005210015-1603 FR-3 的"no_output 改 ⚠️ 语气" | FR-1、FR-2、FR-5 | 单测断言 `no_event` / `no_output` 时 `_send_feishu` 调用次数 = 0；台账 status 仍 `success` |
| D-3 | 本窗口 `ask_user_question` 作答（2026-10-06）：「A. 通用规则 + 两条都不发（含开始）」 | 做**通用规则**（不是只修 `event_calendar_check`），且**开始消息一并静默**；失败/异常照常告警；台账照留痕 | FR-2、FR-3、FR-4、FR-6 | FR-3 的"超阈值仍在跑"提示 + FR-4 的失败必发，共同保证"静默的是无事、不是消息能力" |

## 下一步

产物已落盘 → 交人工确认（`reqboard_ask_confirm(target=artifact, kind=requirement)`）；
确认后进入 **design** 节点（只写设计文档，`docs/requirements/REQ-261006165125-23a9/design/`）。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-9c727a、t-1ec5fa |
| FR-2 | ✅ 已接收 | t-9a1066、t-15bb12、t-1ec5fa |
| FR-3 | ✅ 已接收 | t-15bb12、t-1ec5fa |
| FR-4 | ✅ 已接收 | t-15bb12、t-1ec5fa |
| FR-5 | ✅ 已接收 | t-15bb12 |
| FR-6 | ✅ 已接收 | t-9a1066、t-15bb12、t-1ec5fa |
| FR-7 | ✅ 已接收 | t-9c727a、t-9a1066、t-1ec5fa、t-f9a549 |
| FR-8 | ✅ 已接收 | t-1ec5fa、t-fd8513、t-f9a549 |

> 无未接收条款（8 条全部有落点）。

<!-- reqboard:marks:end -->
