# 测试证据 · REQ-261006165125-23a9

**采集时点**: 2026-10-06 17:05–17:12（全部命令为**当次实跑**输出，非转述）
**环境**: `/Users/mac/Documents/ai/pi-investment/quantsys-v2`，`./venv/bin/python`（Python 3.13.14 / pytest 9.1.1）
**总判定**: 合并口径 **152 passed / 0 failed**；notify-guard **egress=0 offenders=[]**

## 1. 合并口径（需求级判定命令）

```bash
./venv/bin/python -m pytest \
  tests/test_daily_jobs_quiet_noop.py tests/test_daily_jobs_notify_truthfulness.py \
  tests/test_daily_jobs_bootstrap.py tests/test_daily_jobs_trading_day_gate.py \
  tests/test_false_success_guard.py tests/test_notify_guard.py \
  tests/test_freshness_guard.py tests/test_job_failure_alerting.py -q
```
实测输出（末尾）：
```
notify-guard intercepted=0 egress=0 offenders=[]
======================== 152 passed, 1 warning in 7.39s ========================
```

## 2. 分文件证据

| 文件 | 实测 | 说明 |
|---|---|---|
| `tests/test_daily_jobs_quiet_noop.py`（新增） | **40 passed** | T-1~T-16 参数化展开；本需求的回归锁 |
| `tests/test_daily_jobs_notify_truthfulness.py`（改写 2 条） | **30 passed**（含 notify_guard） | 默认态零消息 + 开关态 ⚠️ |
| `tests/test_daily_jobs_bootstrap.py` | 通过 | 宿主内核与既有导入路径未破 |
| `tests/test_daily_jobs_trading_day_gate.py`（改写 2 条断言） | **28 passed** | 门语义不变，仅消息条数 2 → 1 |
| `tests/test_false_success_guard.py` | 通过 | 假成功防线未被牵连 |
| `tests/test_notify_guard.py` | 通过 | 打桩点纪律 |
| `tests/test_freshness_guard.py` / `tests/test_job_failure_alerting.py` | 通过 | 失败告警链路未受影响 |

## 3. 行为面证据（非"测试通过"式结论，逐态实跑）

```bash
./venv/bin/python -c "<桩 runtime._send_feishu/_mark_running/_mark_done>"
```
| 输入 | 实测飞书条数 | 文案 | 台账 |
|---|---|---|---|
| `{'status':'no_event'}`（无事） | **0** | —（日志 `inprocess_job_notify_skipped reason=no_op`） | `success`（result 原样） |
| `{'updated':1}`（有产出） | **1** | `✅ 每日任务完成：event_calendar_check` | `success` |
| `manual=True` + 无事 | **1** | `✅ 每日任务完成（人工触发）：…` | `success` |
| handler 抛 `RuntimeError` | **1** | `🚨 每日任务失败：…` | `failed` |
| `{'status':'no_event','success':False}` | **1** | `🚨 …`（**失败优先**） | `failed` |
| 阈值 0.05s + handler 睡 0.3s | **2** | `⏳ 每日任务仍在运行：…` + `✅ …` | `success` |
| 阈值 0（关闭） + 慢 handler | **1** | 仅 `✅ …`（无 ⏳） | `success` |

## 4. 回滚与部署证据

```bash
DAILY_JOBS_NOTIFY_NOOP=true ./venv/bin/python -c "…"        # → switch-mode OK（无事也发）
DAILY_JOBS_RUNNING_NOTICE_SECONDS=0 ./venv/bin/python -c "…" # → notice-off OK
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5001/api/jobs/inprocess/status  # → 200
psql -d quant_investment -Atc "select job_id,status,result->>'status' from quant.inprocess_job_runs
  where run_date=current_date and job_id='event_calendar_check';"   # → event_calendar_check|success|no_event
```
部署：`launchctl kickstart -k gui/501/com.pi-investment.v2-api` → 新 PID 57853；
`logs/api.log` 2026-10-06T17:09:55 `✅ daily-jobs host thread started`（含 `event_calendar_check`）。

## 5. 未取证项（不得算作通过）

| 项 | 为什么没做 | 何时/如何判定 |
|---|---|---|
| 真实排班下"无事飞书静默" | 部署时点 17:09 已过当日 16:45 排班；当日那次是**旧代码** | 2026-10-07 16:45 后按 `notes/rollback-and-observation.md §3.2` 三条判据核对 |

## 6. 证据口径提醒（防复现时得到假绿）

`DAILY_JOBS_NOTIFY_NOOP=true ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q`
**恒过且不构成回滚证据**——夹具 `sent` 会 `delenv` 隔离环境变量。回滚证据请看 §4 的两条进程级命令
与用例内显式 `setenv` 的 T-4 / T-11。

## 7. 卡片覆盖度（每张卡的证据落在哪个测试/命令）

六张父卡与其子卡链（研发 / 复核 / 测试）的证据来源如下；父卡证据 = 其子卡链证据的并集。

covers: t-9c727a
covers: t-bf39b1
covers: t-f78a6f
covers: t-eacc2e
covers: t-9a1066
covers: t-60e3a6
covers: t-2f0bc5
covers: t-11b46b
covers: t-15bb12
covers: t-dd129f
covers: t-e34e81
covers: t-319ae0
covers: t-1ec5fa
covers: t-9138db
covers: t-e704f1
covers: t-4a30f8
covers: t-fd8513
covers: t-0b1d7e
covers: t-6465f8
covers: t-4eefcc
covers: t-f9a549
covers: t-759ba0
covers: t-8e8912
covers: t-ddc9c6

### 7.1 逐卡证据索引

| 卡片 | 证据（测试用例 / 命令） |
|---|---|
| `t-9c727a` / `t-bf39b1`（notify_policy 研发） | T-1~T-5 用例 + §4 两条进程级回滚命令 + 层边界 grep |
| `t-f78a6f`（notify_policy 复核） | 评审报告 §2 前两行（契约逐条比对，10 项） |
| `t-eacc2e`（notify_policy 测试） | T-1~T-5 + 既有 4 文件回归（75 passed） |
| `t-9a1066` / `t-60e3a6`（format 研发） | `python -c` 打印 `format ok`（三级标题 + 正文形状） |
| `t-2f0bc5`（format 复核） | 评审报告 §2（签名与标题优先级逐条） |
| `t-11b46b`（format 测试） | 上述命令复跑 + 相邻文件 152 passed |
| `t-15bb12` / `t-dd129f`（host 研发） | T-6~T-16 用例 + §3 行为面逐态表 + 两处 grep |
| `t-e34e81`（host 复核） | 13 项结构/行为复核（含"失败优先"与打桩点） |
| `t-319ae0`（host 测试） | 既有 4 文件 75 passed；扩大跑 152 passed |
| `t-1ec5fa` / `t-9138db`（回归锁研发） | `pytest tests/test_daily_jobs_quiet_noop.py -q` → 40 passed |
| `t-e704f1`（回归锁复核） | 16 编号齐备 + 三条反向锁 + 打桩点检查（13 项） |
| `t-4a30f8`（回归锁测试） | 40 passed + 合并口径 152 passed（§1） |
| `t-fd8513` / `t-0b1d7e`（旧断言研发） | `pytest tests/test_daily_jobs_notify_truthfulness.py tests/test_notify_guard.py -q` → 30 passed |
| `t-6465f8`（旧断言复核） | 旧断言仅剩开关态 1 处 + 三条未改用例仍在（13 项） |
| `t-4eefcc`（旧断言测试） | 该文件 30 passed + 合并口径 152 passed |
| `t-f9a549` / `t-759ba0`（回滚留痕研发） | §4 回滚双路径 + 部署三项证据 + 留痕文件 |
| `t-8e8912`（回滚复核） | 留痕 8 项核对（含两处偏差登记） |
| `t-ddc9c6`（回滚测试） | 留痕 §5 测试段复跑记录（五项实测输出） |

