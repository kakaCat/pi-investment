# REQ-261005210015-1603 · 修复每日任务完成通知误导（耗时 0.0 分钟 / computed 语义 / 全 NULL 仍报 ✅）

**需求ID**: REQ-261005210015-1603
**类型**: feature
**作用域**: `quantsys-v2/`（`adapters/inbound/fastapi_app/daily_jobs/`（runtime / alerting、pipeline 的 fitness handler）、`application/services/evolution/`、`tests/`）
**侧**: backend（无前端产出，不涉及原型）
**档位**: 轻档（L3 依据见文末；出现"第二个未定决策 / 动架构 / 新增子系统 / 改数据模型"即单向升级重档）

## TL;DR

用户收到 2026-10-05 20:35 的飞书卡片：

```
✅ 每日任务完成：evolution_fitness
B链账户行为双侧捕获 fitness 续采（RFC 012 P3，8/14 断点恢复；账户行为域，非策略参数进化）
耗时: 0.0 分钟
detail[computed=5]
```

**卡片没坏，任务也没失败——坏的是它把「零有效产出」报成了「完成」。** 同一次运行的 5 行 fitness
`up_capture / down_capture / fitness` **全部为 NULL**（2 条 `insufficient_sample` + 3 条 `no_trades`），
而正文里没有任何一个词能让人看出这件事：

```
runtime.py:133   f"耗时: {elapsed_min:.1f} 分钟"        ← 1.21 秒 → "0.0"（复现见 E3）
alerting.py:190  摘要键表无 no_trades/insufficient_sample/data_gap  ← 全 NULL 不进正文（E4）
service:73-102   computed += 1（NULL 行也 +1）；skipped 写死 0      ← 计数不是"算出了几条"（E7）
```

**可证伪的现状**：全表 280 行只有 60 行有 fitness 值，且最后一天是 **2026-09-12**；10-02 与 10-05
两次运行的 `ok` 数**都是 0**（E6）——即 B 链 fitness 已空转 20+ 天，卡片每天照发 ✅。

```
  _job_evolution_fitness()          _run_job(job, run_date)               飞书卡片
  -------------------------         ---------------------------------     ---------------------------
  EvolutionFitnessService           t0 = time.time()                      ✅ 每日任务完成：...
    .compute_all_accounts()         result = job.handler()                B链账户行为双侧捕获 ...
        |                              |                                    耗时: 0.0 分钟   <-- (1)
        |  5 行 upsert                 |  find_result_failure(result)          detail[computed=5] <-- (2)
        |  ok=0 (全 NULL) --------+    |    -> 空（NULL 不算失败）              ^
        v                         |    v                                       |
  {'detail': {...},           (3) |  elapsed = 1.21s  ------------------------+
   'note': ...}                   |  _summarize_result(result)  -------------+  (2) 键表无
                                  |  _mark_done('success')                   |      no_trades / insuff...
                                  v                                          |  (3) 计数含 NULL 行
                              status=success  <-- 不变（FR-6）               |      skipped 写死 0
                                                                             |  (1) /60 + .1f -> 0.0
```

三处缺陷的落点：**(1)** `runtime.py:133-137` ｜ **(2)** `alerting.py:188-207` ｜ **(3)** `evolution_fitness_service.py:73-107`。

**本需求要做的**：让这条消息**说真话**——耗时能读懂、摘要带上"有效/样本不足/无成交"的分布、
零有效产出时不再用 ✅ 语气（并给出"连续几次空转 + 最近一次有有效产出是哪天"），
同时把 `computed` 这个空转指标拆成诚实的计数。

## L1 一句话目标 + 可证伪判定标准

**目标**：DailyJobs 的完成通知**只允许说真的**——"完成"不得被读成"有产出"，
"computed=N" 不得被读成"算出了 N 条 fitness"，耗时要能反映真实量级。

**可证伪判定标准**（跑什么、看到什么算过，逐条对应下方 FR）：

1. 耗时格式化（FR-1）：`elapsed=1.21` → 文本含 `1.2 秒`；`elapsed=125` → 文本含 `2.1 分钟`。
2. 摘要有状态分布（FR-2）：以 E2 的真实 result 渲染 → 文本含「有效 0」「样本不足 2」「无成交 3」，
   且**不再**只出现裸 `detail[computed=…]`。
3. 零产出不报 ✅（FR-3）：`computed_ok == 0` → 标题为 `⚠️ …（无有效产出）`；
   `computed_ok > 0` → 标题仍为 `✅ …`。
4. 计数语义（FR-4）：`compute_all_accounts()` 返回体含 `computed_ok / insufficient_sample / no_trades / data_gap`，
   四者相加 = 遍历账户数；**不再存在**写死的 `skipped`；`computed` 若保留，其语义必须是"遍历到的账户数"且不与"有效条数"混用。
5. 连续空转可见（FR-5）：以"最近 2 次 window_end 的 ok 均为 0"构造 → 文本含
   「连续 2 次无有效产出（最近有效：2026-09-12）」；构造 ok>0 → 不含该句。
6. 台账语义不变（FR-6）：任务本身仍记 `status='success'`，不触发 2h 失败重试与跨日补跑。
7. 回归：`tests/test_daily_jobs_bootstrap.py`、`tests/test_false_success_guard.py`、
   `tests/services/evolution/test_evolution_fitness_service.py` 全绿；其他任务（evening_pipeline 等）
   的通知在正常路径上语义不变。

## 边界

### 做什么

1. **耗时按量级显示**：< 60 秒用秒（1 位小数），≥ 60 秒用分钟（1 位小数）。
2. **摘要必须含"没做成的动作"**：把 fitness 的状态分布（有效 / 样本不足 / 无成交 / 数据缺口）
   写进正文，且不再是内部字段名的原样 dump。
3. **零有效产出不得报 ✅**：结果契约新增一个通用标记（候选顶层键 `no_output`，见「接口与数据契约」），
   由 `_run_job` 消费决定语气；**只改消息，不改台账 status**。
4. **计数语义诚实**：拆分 `computed`，去掉写死的 `skipped`，计数器与返回值口径一致。
5. **空转跨天可见**：消息里带"连续 N 次无有效产出 + 最近一次有有效产出的日期"。
6. **可测**：新增日期/结果驱动的单测 + 一次真实运行后的文本核对。

### 不做什么

- **B1 不做交易日门 / 休市日跳过**：`JobDef` 标志、`is_due` 接入日历、registry 排班
  —— 由邻居需求 **REQ-261005203907-2b8c**（"DailyJobs 宿主接入交易日门"）承担，
  其 FR-4 已明确 `evolution_fitness` 休市日整段跳过。本需求**不碰** `is_due` / `JobDef` / `registry.py`。
  协调点：两条需求都会改 `runtime.py::_run_job`——本需求的改动**限于消息构造与结果消费**，
  不得改动其分支结构（避免与其"跳过即不发通知"的分支相互冲突）。
- **B2 不修数据链**：不补/不回填账户净值快照（`quant.simulation_equity_snapshot` 的洞），
  不改 `MIN_SAMPLE_DAYS` / `SIDEWAYS_THRESHOLD` 等算法阈值——"为什么算不出数"是**另一个问题**。
- **B3 不排查「卡片上的 7」的来源**：台账 / 日志 / 复现三处一致为 5（E8），用户所见为 7，
  差异原因未知（是否存在第二个发送方）——登记为待查项，不在本次动调度与通知发送点。
- **B4 不引入指标面**：**不**暴露 `/metrics`、**不**接 Prometheus、**不**改 `alerts.yml`
  （本部署无 scrape 端，`alerts.yml` 当前是死规则，见 E9）；不改 `quant.evolution_fitness` 表结构；
  不动 APScheduler 路径的任务。

### 边界理由

- 用户可感知的成本是一条**每天都在误导人的消息**：它把"空转 20+ 天"读成"每天都在正常采集"。
- 修法局部：1 处格式化 + 1 处摘要 + 1 个返回体 + 1 处消费分支 + 测试，不新增子系统、不动数据模型。
- 为什么**不**把零产出判成 failed：任务是**真的跑完了**（5 行 upsert 成功、无异常，
  `find_result_failure` 判不出问题，见 R1）。判 failed 会牵动 2h 失败重试与跨日补跑链，
  代价与收益不成比例——"完成但无产出"是消息层的事实，先在这里如实说清（升级信号①）。
- 为什么观测不押在 Prometheus 上：`evolution_fitness_score` 这类 Gauge 在非 ok 时从不被 set，
  且本部署既无 `/metrics` 端点也无 Prometheus 进程（E9）——押在它上面等于把"空转可见"交给一个不存在的通道。
- 为什么不顺手修数据链：快照洞的成因（9-13~10-01 停摆 18 天 + 长假）与"消息说不说真话"是两件事，
  混在一起会让本条需求无法用"消息文本"证伪（升级信号③）。

## 产品定义

### 一句话

让"✅ 每日任务完成"这句话**重新可信**：读者从卡片上就能判断"今天到底有没有产出"，
而不是只能看到"跑过了"。

### 为什么现在做

1. **假成功是本仓已付出的代价**：`REQ-261003150739-b98d` 治的是"测试真发通知"，
   `REQ-261004154902-a7cd` / `t-322d78` 治的是"没做成的动作不进正文"——本条是同一族缺陷
   在 fitness 上的现形：**动作做了，产出是 0，消息说成功**。
2. **误导是持续性的**：不是某一天偶发——`ok` 数自 2026-09-12 起连续为 0（E6），
   20+ 天的 ✅ 叠起来形成"B 链采集一直正常"的错误印象。
3. **修完立刻可验**：下一次 evolution_fitness 运行（视 2b8c 的门，10-06/07 休市跳过或 10-08 复市）
   就能拿到真实卡片文本做核对。

### 成功长什么样

- 零产出那天：标题是 `⚠️ 每日任务完成（无有效产出）：evolution_fitness`，
  正文有 `耗时: 1.2 秒` + `有效 0 / 样本不足 2 / 无成交 3` + `连续 2 次无有效产出（最近有效：2026-09-12）`。
- 有产出那天：标题仍是 `✅ …`，正文给出真实的有效条数与分数区间（本期不要求分数区间，仅要求能看出"有产出"）。
- 台账：`quant.inprocess_job_runs.status` 仍为 `success`，`result` 里多出结构化的状态计数。

## 用户与角色

| 角色 | 关心什么 | 现状痛点 |
|---|---|---|
| 用户（项目所有者） | "B 链 fitness 到底在不在采" | 每天收到 ✅，实际 20+ 天零产出（E6）；连 `computed` 都被读成"算出了 N 条" |
| agent（投资脑） | 行为进化的输入是否可用 | 读到 ✅ 便认为输入可用，实际 `up_capture/down_capture` 全 NULL |
| 看板 / 调度 | 任务健康度 | `success` 不分"有产出"与"空转"，`computed` 是空转指标（E7） |
| 后续维护者 / 新会话 | 加新任务时怎么发通知 | 没有"零产出怎么说"的约定，也没有可复用的标记位（本需求补上） |

## 功能点（G2 条款）

**FR-1: 完成/失败通知的耗时必须反映真实量级**
`elapsed < 60s` 显示秒（1 位小数），`≥ 60s` 显示分钟（1 位小数）；
禁止再出现"1.2 秒的活印成 0.0 分钟"。（仅改展示，不改计时口径。）

**FR-2: 摘要必须含"没做成的动作"，且不得是内部字段名的原样 dump**
`fitness` 结果渲染进正文时，必须给出**有效 / 样本不足 / 无成交 / 数据缺口**四类计数；
`alerting._summarize_result` 的键覆盖必须包含这些状态键（现状缺，E4）。
其余任务（`evening_pipeline` 等）在正常路径上的摘要语义不变。

**FR-3: 零有效产出不得报 ✅**
结果契约新增通用标记（候选顶层键 `no_output: bool`，缺省不存在 = 有产出）；
`_run_job` 在其为真时把标题从 `✅ 每日任务完成：` 改为 `⚠️ 每日任务完成（无有效产出）：`，
正文保留全部计数。**台账 `status` 仍写 `success`**（见 R1 与 FR-6）。

**FR-4: 计数语义必须诚实**
`EvolutionFitnessService.compute_all_accounts()` 返回体必须能区分
`computed_ok` / `insufficient_sample` / `no_trades` / `data_gap`（四者相加 = 遍历账户数），
并带 `window_end` 与对齐窗口天数；**删除写死的 `skipped: 0`**（E7）。
Prometheus 计数器（`evolution_fitness_computed_total`）的口径与 `computed_ok` 一致，或按状态打标签——
不得再让"遍历到几条"冒充"算出了几条"。

**FR-5: 空转必须跨天可见**
消息正文必须给出**连续 N 次无有效产出**（自最近一个 `window_end` 往前数，全部 `ok` 为 0）
与**最近一次有有效产出的 `window_end`**；无空转时不得出现该句。
计数来源为 `quant.evolution_fitness` 的只读查询（不改表结构）。

**FR-6: 台账与重试语义不动**
本次改动**不得**让该任务被判 `failed`：不触发 2h 失败重试、不进入跨日补跑
（`catchup_due` 只看 `failed`，须保持）；`trigger_job` 对 `success` 行的既有拒绝行为不变。
另：`find_result_failure` 对新增的 `no_output` 键**不得**判为失败（否则 FR-3 的反语气会反向变成假失败）。

**FR-7: 回归锁与真实观察**
新增单测覆盖 FR-1~FR-5 的每一条（含 `ok>0` 的反例）；既有
`tests/test_daily_jobs_bootstrap.py` / `tests/test_false_success_guard.py` /
`tests/services/evolution/test_evolution_fitness_service.py` 全绿；
产出一次真实运行后的卡片文本（或等价的 `_send_feishu` 记录器输出）作为观察结论。

## 接口与数据契约

- **通知文本契约（人读，本次要改的对外语义）**：
  `[✅|⚠️] 每日任务完成[（无有效产出）]：<job_id>` + `<description>` + `耗时: <X 秒|X.X 分钟>` + 摘要。
  摘要格式为**增量**：既有 `k=v; …` 片段保留，新增 fitness 状态与空转短语。
- **handler 结果契约（内部，新增键）**：顶层可选布尔 `no_output`（缺省不存在 = 有产出）。
  消费方：`runtime._run_job`（决定语气）。`find_result_failure` 必须显式忽略它（FR-6）。
  兼容性：`quant.inprocess_job_runs.result` 是 JSONB，新增键对既有消费方（巡检只读 `status`、
  `_summarize_result` 按白名单取键）无破坏。
- **服务返回体契约（内部，改语义）**：`compute_all_accounts() -> Dict`
  新增 `computed_ok` / `insufficient_sample` / `no_trades` / `data_gap` / `aligned_days`；
  旧键 `skipped` 删除；`computed` 若保留必须只表示"遍历到的账户数"。
  调用方：`daily_jobs/pipeline.py::_job_evolution_fitness`（唯一生产调用方，已核对）、
  `application/services/daily_orchestrator.py:661-672`（取 `.get('computed', 0)` 打日志——改键后需同步或保留兼容键）。
- **迁移与回滚**：无表结构变更、无历史数据改写；回滚 = `git revert` 对应提交。

## 现状取证（2026-10-05 实测）

| 编号 | 证据 |
|---|---|
| E1 | 用户提供的现场（原话见 D-2）：卡片正文含 `✅ 每日任务完成：evolution_fitness` + `耗时: 0.0 分钟` + `detail[computed=7]` |
| E2 | 同一次运行台账（`quant.inprocess_job_runs`）：`2026-10-05 20:35:00.502529+08 → 20:35:01.711804+08`（**1.21 秒**），`status=success`，`result={"note": "...", "detail": {"skipped": 0, "computed": 5, "window_end": "2026-10-05"}}` |
| E3 | `runtime.py:133-137`：`elapsed_min = elapsed/60` + `f"{elapsed_min:.1f} 分钟"`；复现 `f"{1.21/60:.1f}" == '0.0'` |
| E4 | `_summarize_result`（`alerting.py:188-207`）以 E2 真实 result 复现 → 输出 **`'detail[computed=5]'`**；键表（:190-195）无 `no_trades` / `insufficient_sample` / `data_gap` |
| E5 | `quant.evolution_fitness` 10-05 五行：`insufficient_sample` 2（agent_virtual / v13_simulation，up_days=2/down_days=4 与 2/3）+ `no_trades` 3（user_main_simulation / v14 / v15）→ `up_capture / down_capture / fitness` **全 NULL** |
| E6 | 全表 280 行中仅 **60 行**有 fitness 值，其 `window_end ∈ [2026-07-27, 2026-09-12]`；按 window_end 统计 `ok` 数：09-12 = 3、**10-02 = 0、10-05 = 0** → 有效产出已断 20+ 天而卡片每天 ✅ |
| E7 | 计数语义（代码）：`evolution_fitness_service.py:102` 每账户 `computed += 1`（含 NULL 行）；`:107` `'skipped': 0` **写死**；`:104` 计数器按同口径累加 |
| E8 | 数字不符：56 个 `window_end` **每个恰好 5 行**（psql）；`logs/launchd-api.log:262676` `"computed": 5`；账户表 active 5 / 总 7（`default`、`rotation_main` 为 `frozen`）→ `7` 在本仓任何日志/库/复现中**均无出现**（仅出现在用户消息里） |
| E9 | 指标面是死的：`infrastructure/monitoring/alerts.yml:14` 的 `evolution_fitness_score{type="up_capture"} < 0.5` 永不触发——Gauge 在非 ok 时从不 set，且全仓无 `/metrics` 暴露、无 Prometheus 进程（实测） |
| E10 | 邻居需求：`docs/requirements/REQ-261005203907-2b8c/requirement.md` 已覆盖"休市日门"（其 FR-4 含 `evolution_fitness` 休市日整段跳过、FR-3 含"跳过不发通知"），且同改 `runtime.py::_run_job` |

### 反向证据（必须一并记录，避免为迎合而罗列）

- **R1（任务没失败）**：E2 的 5 行确实 upsert 成功、handler 未抛异常、`find_result_failure` 判不出问题。
  把它报成 ✅ 在"任务健康"语义上**成立**——错的是读者把"完成"读成"有产出"。
  故本次**不改台账 status**（FR-6），只改消息与计数。
- **R2（`computed` 字面不算错）**：`computed=5` 对"遍历到 5 个 active 账户"是**准确**的（E8 与账户表一致）。
  错在它被当成"算出了 5 条 fitness"读 → 结论是**拆键**（FR-4），而不是简单改数字。
- **R3（快不是异常）**：1.21 秒是真实耗时（28 条指数 + 5 账户 + 一次 upsert）。
  **不做**"耗时过短即告警"的规则——只修显示精度，避免把正常快任务误伤成告警。

## 判定标准（可跑，逐条对应条款）

1. 对应 FR-1：`./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py -q`
   → 断言 `_format_elapsed(1.21) == '1.2 秒'`、`_format_elapsed(125) == '2.1 分钟'`（函数名由设计定）。
2. 对应 FR-2 / FR-3：同文件以 E2 的真实 result 作为输入 → 断言渲染文本含
   `有效 0`、`样本不足 2`、`无成交 3`，且标题为 `⚠️`；再以 `computed_ok=3` 的 result → 标题为 `✅` 且不含"无有效产出"。
3. 对应 FR-4：`./venv/bin/python -m pytest tests/services/evolution/test_evolution_fitness_service.py -q`
   → 断言四类计数相加 = 账户数、返回体无 `skipped` 键、NULL 行不计入 `computed_ok`。
4. 对应 FR-5：以 `quant.evolution_fitness` 最近两个 `window_end`（10-02、10-05，均为 0）为目标 →
   断言文本含「连续 2 次无有效产出（最近有效：2026-09-12）」；把最近一行改成 `ok` 后该句消失。
   （只读查询：`select window_end, count(*) filter (where status='ok') ok from quant.evolution_fitness group by 1 order by 1 desc limit N;`）
5. 对应 FR-6：`./venv/bin/python -m pytest tests/test_false_success_guard.py tests/test_daily_jobs_bootstrap.py -q`
   → 全绿；新增用例断言 `no_output=True` 时 `find_result_failure` 返回空、`_mark_done` 收到 `status='success'`。
6. 对应 FR-7 的真实观察：下一次 evolution_fitness 运行后，飞书卡片（或 `logs/api.log` 中
   `feishu_channel` 记录）文本与第 2/4 条的期望一致；若当天被 2b8c 的交易日门判为 `skipped`，
   则改为核对其 `skipped` 行 + "无该任务通知"（并在结论里写明观察窗口被门改变，不算未完成）。

## 轻档依据（L3）与升级信号

- **L1 一句话目标 + 可证伪判定**：见「产品定义」与「判定标准」第 1~5 条（命令 + 期望文本写死）。
- **L2 范围边界**：见「做什么」6 条 /「不做什么」B1~B4 四条，显式排除交易日门、数据链、指标面。
- **L3 轻路径依据**：改动面 = `runtime.py` 1 处格式化 + 1 处语气分支、`alerting.py` 1 处键表、
  `evolution_fitness_service.py` 1 处返回体 + 1 个只读查询、新增 1 个测试文件；
  通道（`_send_feishu`）、仓储（`JobRunRepository`）、判定器（`find_result_failure`）**都已存在**。
- **单向升级信号**（出现任一即停手升重档、改走完整设计）：
  ① 设计要求把"零有效产出"判成任务 `failed`（牵动 2h 重试 / 跨日补跑链）；
  ② 要求暴露 `/metrics` 或接入 Prometheus / 改 `alerts.yml`（新增子系统）；
  ③ 把"为什么算不出数"（净值快照链、阈值口径）纳入本次范围；
  ④ 需要改 `quant.evolution_fitness` / `quant.inprocess_job_runs` 表结构。
- **提示词难度**：`expert`（立项弹框作答，见 D-1）。

## 讨论与裁定记录（D-x）

| 编号 | 原话来源 | 裁定 | 影响 FR | 判据 |
|---|---|---|---|---|
| D-1 | 立项弹框作答（本窗口，2026-10-05 21:00）：名称「修复每日任务完成通知误导（耗时 0.0 分钟 / computed 语义 / 全 NULL 仍报 ✅）」/ 类型 feature / 难度 expert / 文档位置 `docs/requirements/<REQ>/` | 本工作立项为 **feature**，难度 expert，文档落 `docs/requirements/REQ-261005210015-1603/` | FR-1、FR-2、FR-3、FR-4、FR-5、FR-6、FR-7 | `reqboard_status` 显示本窗口绑定 REQ-261005210015-1603 且状态为 brainstorming |
| D-2 | 本窗口用户消息 seq=5（2026-10-05 20:36）：「你看看这个发送什么问题」（附卡片原文：`✅ 每日任务完成：evolution_fitness` / `耗时: 0.0 分钟` / `detail[computed=7]`） | 先取证再定缺陷：核查结论为"消息把零有效产出报成成功"，**不**按"任务失败"处理；卡片上的 `7` 与台账不符，登记为待查项（B3） | FR-2、FR-3、FR-6 | E1~E9；`computed` 三处一致为 5，`7` 无来源 |
| D-3 | 本窗口选择框作答（2026-10-05 21:01）：「B：通知如实 + 计数语义 + 空转可观测（推荐）」 | 范围取 **B**：改消息如实性 + 计数语义 + 空转可观测；「7 的来源」与「净值快照链核对」**不做**，登记为待查项 | FR-1、FR-2、FR-3、FR-4、FR-5、FR-6 | 边界 B2/B3；升级信号③ 据此写明 |
| D-4 | 本窗口用户消息 seq=330（2026-10-05 21:03）：「继续」 | requirement 产物已确认（ticket pc-679a3f）→ 推进 design 节点；不重复弹确认框、不回退重议边界。**注意**：`brainstorming>design` 属五道人工门（`RequirementStatus.ts:83`），agent 调 `reqboard_move` 被 `REQBOARD_HUMAN_GATE` 拒绝 → 该转移须由人在看板点 | FR-1、FR-2、FR-3、FR-4、FR-5、FR-6、FR-7 | 产物回执 `confirmed=true`（`pc-679a3f`）；阶段转移待人在看板执行（agent 侧拒绝码已实测） |

| D-5 | 本窗口用户消息 seq=412（2026-10-05 21:07）第二次：「继续」 | 在**阶段标签仍为 `brainstorming`（人门未被人在看板点）** 的情况下，按人连续两次明确指令先产出并登记设计文档；**阶段标签的机械推进仍须人在看板执行**（拆分之前必须，agent 已被 `REQBOARD_HUMAN_GATE` 拒绝、不得代跨） | FR-1、FR-2、FR-3、FR-4、FR-5、FR-6、FR-7 | `reqboard_submit(kind=design)` 登记 5 份设计文档；`reqboard_status` 如实显示仍为 brainstorming |

> 交易日门归 `REQ-261005203907-2b8c` 一事系 **agent 自查发现**（非用户原话），已写入「边界 B1」与证据 E10，不占 D-x 条目。

## 待查项（本次不做，另案登记）

1. **卡片上的 `7` 从哪来**：台账 / 日志 / 复现三处一致为 5，56 个 window_end 每行恰好 5 条，账户 active=5、总=7
   —— 是否存在**第二个发送方**（另一进程 / 另一 checkout / 另一台机器）未证实。需要用户提供现场来源
   （截图 / 哪台机器 / 哪条消息）才能继续。
2. **净值快照链的洞**：`quant.simulation_equity_snapshot` 最新仅到 2026-10-02，v13 在 8-21~9-12 仅 14 条稀疏快照
   → 对齐窗口凑不满 `MIN_SAMPLE_DAYS=5` 是 `insufficient_sample` 的直接成因；服务已恢复（10-02 起 launchd），
   复市后能否自然补齐需观察。
3. **指标面整体是死的**：`business_metrics.py` 定义了 Gauge/Counter，但无 `/metrics` 暴露、无 Prometheus 进程
   → `infrastructure/monitoring/alerts.yml` 与 Grafana 面板全部不可能生效（E9）。

## 下一步

- **下一步**：design —— 产物经 `reqboard_submit(kind=requirement)` 登记后，
  用 `reqboard_ask_confirm(target=artifact, kind=requirement)` 交棒；未获批准不得进入。
- 批准后产出设计文档至 `docs/requirements/REQ-261005210015-1603/design/`，
  再经 `reqboard_submit(kind=design)` + 确认后进入拆分。

## L5 轻档 ≠ 无产物

本文件即 requirement 产物（头部带 REQ id）；`docs/requirements/REQ-261005210015-1603/` 为需求目录。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-cda13d、t-4b35ba、t-cef289 |
| FR-2 | ✅ 已接收 | t-cda13d、t-2d12c5、t-cef289 |
| FR-3 | ✅ 已接收 | t-2d12c5、t-4b35ba、t-cef289 |
| FR-4 | ✅ 已接收 | t-c0941a、t-89b1f4 |
| FR-5 | ✅ 已接收 | t-17fce0、t-2d12c5、t-cef289、t-89b1f4 |
| FR-6 | ✅ 已接收 | t-4b35ba、t-cef289 |
| FR-7 | ✅ 已接收 | t-ad4340 |

> 无未接收条款（7 条全部有落点）。

<!-- reqboard:marks:end -->
