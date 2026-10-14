# 休市日观察记录（REQ-261005203907-2b8c · t-6384c0）

> 设计依据：[`../design/test-cases.md`](../design/test-cases.md) §TC-6（真实观察）、§7（命令）。
> 本文件是**实测记录**：命令与输出逐字粘贴。**窗口未到的部分如实标注为待观察**，
> 不用推断代替实测。

## 1. 单元/回归验收（窗口无关，已全过）

```console
$ ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q
27 passed in 0.55s
notify-guard intercepted=0 egress=0 offenders=[]

$ ./venv/bin/python -m pytest tests/test_evening_pipeline_holiday_gate.py -q
6 passed in 0.66s
notify-guard intercepted=0 egress=0 offenders=[]

$ ./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q
37 passed, 1 warning in 1.26s
notify-guard intercepted=0 egress=0 offenders=[]
```

## 2. 改造前基线（2026-10-05，国庆休市）——门尚未生效的证据

```console
$ psql -d quant_investment -c "select job_id, status, started_at::time(0), finished_at::time(0),
  round(extract(epoch from (coalesce(finished_at, now())-started_at))/60, 1) as minutes
  from quant.inprocess_job_runs where run_date='2026-10-05' order by started_at;"
        job_id        | status  | started_at | finished_at | minutes
----------------------+---------+------------+-------------+---------
 watch_rule_health    | success | 16:30:48   | 16:30:49    |     0.0
 event_calendar_check | success | 16:45:51   | 16:45:51    |     0.0
 freshness_guard      | success | 17:20:56   | 17:20:56    |     0.0
 pool_daily_refresh   | success | 19:05:40   | 19:06:02    |     0.4   ← 空跑 22.1 秒
 evening_pipeline     | running | 20:31:00   |             |    53.4   ← 全市场因子重算中
 evolution_fitness    | success | 20:35:01   | 20:35:02    |     0.0
 chip_distribution    | running | 21:10:54   |             |    13.5   ← 休市日仍在跑
(7 rows)
```

**为什么这还是改造前的行为**（关键前提，不许省略）：

```console
$ ps -o pid,lstart,command -p $(pgrep -f "fastapi_app/main.py" | head -1)
  PID STARTED                      COMMAND
86976 Mon Oct  5 09:09:10 2026     .../adapters/inbound/fastapi_app/main.py
```

服务进程 **09:09:10 启动**，早于本次代码改动落盘时间（21:0x）→ 宿主线程里跑的是**旧代码**。
因此 2026-10-05 当晚（含 21:10 的 `chip_distribution`）**不体现**交易日门，属预期。

**改造前基线可读出的两件事**：
1. `pool_daily_refresh` 在休市日真的跑了（22.1 秒、`result.status=success`、`pool_change_log` 当天 0 行）；
2. `evening_pipeline` 的因子段在休市日真的在烧 CPU（20:31 起，至 21:24 已 53.4 分钟）；
   同一时刻日志有 `K线已新鲜（覆盖 5265/5277=99.8% ≥ 98%，基准日 2026-09-30），跳过同步`
   ——即 K 线段已自守、因子段没有门。

## 3. 待观察项（**窗口未到**，不得用推断代替实测）

### 3.1 前置条件（必须先做，否则门不生效）

```bash
# 让宿主线程加载新代码（改的是进程内线程里的代码，必须在进程内重新加载）
launchctl kickstart -k gui/501/com.pi-investment.v2-api
# 确认新进程已起
ps -o pid,lstart,command -p $(pgrep -f "fastapi_app/main.py" | head -1)
```

> **本次未执行重启**：重启生产服务会连带加载工作区里其它未提交改动，属需要人拍板的动作，
> 故本卡只把前提写成可执行命令并显式标注为**阻塞项**。

### 3.2 休市日（2026-10-06 或 10-07，19:05 之后）

```sql
SELECT job_id, status, result->>'reason' AS reason, result->'trading_day'->>'source' AS source
FROM quant.inprocess_job_runs WHERE run_date = DATE '2026-10-06' ORDER BY job_id;
```

| 期望 | 判据 |
|---|---|
| `pool_daily_refresh` = `skipped` | 改造前是 `success` + 22 秒空跑（见 §2） |
| `chip_distribution` = `skipped` | 改造前是 `running`（21:10 起，见 §2） |
| `evolution_fitness` = `skipped` | — |
| `watch_rule_health` / `event_calendar_check` / `freshness_guard` = `success` | 未置位任务行为不变 |
| `evening_pipeline` 的 `result->'factor_compute'->>'status'` = `skipped` | K 线段仍照跑（`kline_sync` 有值） |

```sql
SELECT job_id, status, result->'factor_compute'->>'status' AS factor_status
FROM quant.inprocess_job_runs WHERE run_date = DATE '2026-10-06' AND job_id='evening_pipeline';
```

**飞书侧**：当天不应收到这 3 个任务的「▶️ 每日任务开始 / ✅ 每日任务完成」
（对照 2026-10-05：`pool_daily_refresh` 各发 1 条开始与完成）。

### 3.3 复市首日（2026-10-08）

```sql
SELECT job_id, status FROM quant.inprocess_job_runs
WHERE run_date = DATE '2026-10-08' AND job_id IN ('pool_daily_refresh','evening_pipeline');
-- 期望：两行都是 success（复市首日不跳过）
```

## 4. 未覆盖 / 残留

- **降级路径（fail-open）只做了单元验证**（`test_degraded_runs_fail_open`），
  没有在真实日历源故障下实测——制造真实故障会污染生产日历读取，成本高于收益，故留作已知缺口。
- **选择集里的 1 条既有 order-dependent 失败**（`test_daily_jobs_notify_truthfulness.py::TestIdleStreak::test_streak_query_failure_degrades_loudly`，
  capsys 断言）与本需求无关：单跑通过、失败点在本需求代码之前（详见 t-4dec18 汇报）。
- 观察窗口（10-06/10-07/10-08）到点后请照 §3.2/§3.3 复跑并回填本节上方的实测输出。

---

## 5. 补记：2026-10-05 21:28 重启宿主（用户裁定后执行）

**为什么重启**：门改的是宿主线程里的代码，仅在进程内重新加载后生效——不重启则 10-06 19:05
仍是旧行为。用户于 2026-10-05 21:2x 明确裁定「重启，让门在 10-06 19:05 生效」。

```console
$ launchctl kickstart -k gui/501/com.pi-investment.v2-api
$ ps -o pid,lstart,command -p $(pgrep -f "fastapi_app/main.py" | head -1) | tail -1
74347 Mon Oct  5 21:28:34 2026     .../adapters/inbound/fastapi_app/main.py     ← 旧进程 86976@09:09 已被替换
$ curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5001/api/pools
200
```

启动日志（`logs/launchd-api.log`，21:28 之后）：

- `✅ APScheduler started (fallback mode)`
- `✅ daily-jobs host thread started`，jobs = 9 个（含 3 个带门任务）→ **`gate.py` 导入无误，新代码已在跑**
- `inprocess_job_orphans_reaped` count=2：上一进程被 kill 时正在跑的 `evening_pipeline`（20:31 起）
  与 `chip_distribution`（21:10 起）被判为孤儿 `failed`（既有 reaper 行为，非本需求引入）：

```console
$ psql -d quant_investment -c "select job_id, status, started_at::time(0), finished_at::time(0),
  left(coalesce(error,''),40) from quant.inprocess_job_runs where run_date='2026-10-05' order by started_at;"
 pool_daily_refresh | success | 19:05:40 | 19:06:02 |
 evening_pipeline   | failed  | 20:31:00 | 21:28:38 | 宿主重启导致中断（孤儿 running 行，进程已不在）
 chip_distribution  | failed  | 21:10:54 | 21:28:38 | 宿主重启导致中断（孤儿 running 行，进程已不在）
```

### 5.1 意外收获：**今晚就有第一个可观察点**（不用等到 10-06）

被 reaper 判 failed 的两行会按既有规则「失败冷却 2h 后重试」，即：

| 任务 | started_at | 冷却到期 | 预期（新代码 + 休市日） |
|---|---|---|---|
| `evening_pipeline` | 20:31:00 | **22:31 之后** | K 线段（覆盖度新鲜→skipped）+ **因子段 skipped**；任务记 success |
| `chip_distribution` | 21:10:54 | **23:10 之后** | **整段 skipped**（写 `status='skipped'`，不发飞书） |

复跑命令（今晚 22:40 / 23:20 之后各跑一次）：

```sql
SELECT job_id, status, result->>'reason' AS reason, result->'trading_day'->>'source' AS source
FROM quant.inprocess_job_runs WHERE run_date = DATE '2026-10-05'
  AND job_id IN ('evening_pipeline','chip_distribution');
```

**期望**：两行都变成 `success`（前者 `result->'factor_compute'->>'status' = 'skipped'`），
或后者为 `skipped`——**不再是"全市场重算 54 分钟"**。

---

## 6. 实测回填（2026-10-05 22:31，门生效后的第一次真实运行）

**来龙去脉**：21:28 重启时，20:31 起正在跑的 `evening_pipeline` 被 reaper 判孤儿 `failed`；
按既有「失败冷却 2h」规则，它于 **22:31:47** 被自动重试——**这次跑的是新代码**。

```console
$ psql -d quant_investment -x -c "select job_id, status, started_at::time(0), finished_at::time(0),
  round(extract(epoch from (finished_at-started_at))/60,2) as min,
  result->'kline_sync'->>'status' as kline, result->'factor_compute'->>'status' as factor,
  result->'factor_compute'->>'skipped' as factor_skipped,
  result->'factor_compute'->>'reason' as reason
  from quant.inprocess_job_runs where run_date='2026-10-05' and job_id='evening_pipeline';"
job_id         | evening_pipeline
status         | success
started_at     | 22:31:47
finished_at    | 22:31:47
min            | 0.01                      ← 改造前同一任务是 57.6 分钟
kline          | skipped
factor         | skipped
factor_skipped | true
reason         | 非交易日（2026-09-30 基准）且 K 线本次无更新
```

对应日志（`logs/api.log`）：

```console
2026-10-05T22:31:46.978782+08:00 | info | inprocess_job_start
2026-10-05T22:31:49.083390+08:00 | info | evening_pipeline: 非交易日（基准日 2026-09-30）且 K 线本次无更新 → 跳过因子全市场计算
2026-10-05T22:31:49.097426+08:00 | info | inprocess_job_done
```

**结论（实测，不再是推断）**：休市日的全市场因子重算**确实不再发生**——
`57.6 分钟 → 0.01 分钟（约 0.6 秒）`，且 **K 线段保留**（`kline_sync` 有值、`status=skipped` 是它自己的
新鲜度门判的），`factor_compute.skipped=true` + 原因带基准日。任务终态 `success`
（跳过不是失败），完成通知按既有规则照发（这条任务真的跑了 K 线段检查）。

**仍待观察**：
- `chip_distribution` 的重试窗口（21:10 + 2h ≈ **23:11**）——预期整段 `status='skipped'`；
- 10-06 / 10-07（休市日 19:05 起）与 10-08（复市首日）。

---

## 7. 实测回填（2026-10-05 23:11，整段跳过的第一次真实运行）

**来龙去脉**：21:10 起在跑的 `chip_distribution` 同样在 21:28 重启时被判孤儿 `failed`，
按 2h 冷却于 **23:11:54** 自动重试——这次跑的是新代码。

```console
$ psql -d quant_investment -x -c "select job_id, status, started_at::time(0), finished_at::time(0),
  result->>'skipped' as skipped, result->>'reason' as reason,
  result->'trading_day'->>'source' as td_source, result->'trading_day'->>'degraded' as degraded
  from quant.inprocess_job_runs where run_date='2026-10-05' and job_id='chip_distribution';"
job_id      | chip_distribution
status      | skipped
started_at  | 23:11:54
finished_at | 23:11:54
skipped     | true
reason      | 非交易日（2026-10-05）：交易日历判定为非交易日（来源 calendar_table：该日不在交易日历中）
td_source   | trading-calendar-holiday
degraded    | false
```

**该时间窗内 `logs/api.log` 的全部相关行（只有两行）**：

```console
2026-10-05T23:11:53.599486+08:00 | info | ...daily_jobs.defs | inprocess_job_start
2026-10-05T23:11:53.608835+08:00 | info | ...daily_jobs.defs | inprocess_job_skipped
```

**没有任何通知日志**——正常路径在这个窗口会出现
`domain.notification.services.notification_service: 发送通知` 与
`feishu_channel: 飞书发送成功`（对照 19:05 那次 `pool_daily_refresh`）。
⇒ **FR-3「留痕 + 不打扰」实测成立**：台账留一行 `skipped`，飞书一条不发。

**累计实测对照（2026-10-05，同一休市日）**：

| 任务 | 改造前 | 门生效后 | 差异 |
|---|---|---|---|
| `evening_pipeline` | 20:31 起跑 **57.6 分钟**（因子全市场重算） | 22:31:47 **0.01 分钟**，`factor=skipped`、K 线段保留 | 省掉整段重算 |
| `chip_distribution` | 21:10 起跑到被重启打断（**17.7 分钟**仍在跑） | 23:11:54 **`skipped`**，0 秒 | 整段不跑、且不发通知 |
| `pool_daily_refresh` | 19:05 空跑 22.1 秒 + 2 条飞书、0 换血 | （当日已过点，未重跑） | 见 10-06 观察项 |

**至此，本次交付的三条核心语义（整段跳过 / 局部跳过保留 K 线段 / 跳过不打扰）都已有生产实测**。
剩余观察窗口：10-06 / 10-07（19:05 起的 `pool_daily_refresh` 等）与 10-08 复市首日。
