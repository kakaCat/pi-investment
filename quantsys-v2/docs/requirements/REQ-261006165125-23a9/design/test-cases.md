# 设计 · 测试策略与用例（每日任务空结果不发飞书）

**需求ID**: REQ-261006165125-23a9
**类型**: feature
serves: FR-1, FR-2, FR-3, FR-4, FR-6, FR-7, FR-8

## 1. 三层策略（serves: FR-8）

| 层 | 对象 | 手段 | 为什么够 |
|---|---|---|---|
| L1 纯函数 | `notify_policy` 全部函数 | 直接调用 + `monkeypatch.setenv` | 判据无 IO，边界可穷举 |
| L2 宿主行为 | `runtime._run_job` | 桩掉 `runtime._send_feishu` / `_mark_*`（**不碰库、不真发**） | 断言"发了几条、文案是什么、台账 status" |
| L3 真实观察 | 生产台账 + 飞书侧 | 次日实跑后查表/查日志 | 端到端唯一可信证据 |

## 2. 新增文件：`tests/test_daily_jobs_quiet_noop.py`（serves: FR-1, FR-2, FR-3, FR-4, FR-6, FR-7）

| # | 用例 | 断言（可证伪） |
|---|---|---|
| T-1 | `is_no_op` 白名单 | `{'status':'no_event'}`→True；`{'status':'no_op'}`→True；`{'no_output':True}`→True；`{'no_output':1}`→False；`{'status':'success'}`→False；`{}`→False；`None`/`'x'`/`[]`→False |
| T-2 | `is_no_op` 大小写/空格 | `{'status':' NO_EVENT '}`→True |
| T-3 | `should_send_completion` 四分支 | 无事→False；有产出→True；无事+`manual=True`→True；有产出+`manual=True`→True |
| T-4 | 开关解析 | `DAILY_JOBS_NOTIFY_NOOP` ∈ {未设, `''`, `'0'`, `'false'`, `'nope'`}→False；∈ {`'1'`,`'true'`,`'TRUE'`,`'yes'`,`'on'`}→True；开关为真时 `should_send_completion(无事)`→True |
| T-5 | 阈值解析 | 未设→60.0；`'abc'`→60.0；`'0'`→0.0；`'-1'`→0.0；`'30'`→30.0 |
| T-6 | **宿主：无事 → 零消息** | handler 返回 `{'status':'no_event','pending_in_window':0}` → `sent.texts == []` **且** `sent.marks[-1][0][2] == 'success'` 且 result 原样落库 |
| T-7 | 宿主：有产出 → 一条完成消息 | handler 返回 `{'updated': 12}` → `len(sent.texts) == 1`、以 `✅ 每日任务完成：` 开头、含 `耗时: ` 且以「秒」结尾 |
| T-8 | 宿主：异常 → 🚨 且不静默 | handler 抛 `RuntimeError('boom')` → `len(sent.texts) == 1` 且以 `🚨 每日任务失败：` 开头、`marks[-1][0][2] == 'failed'` |
| T-9 | 宿主：内层失败优先于"无事" | handler 返回 `{'status':'no_event','success':False}` → `len(sent.texts) == 1` 且 🚨、`failed` |
| T-10 | 宿主：人工触发必有回执 | `_run_job(job, date, manual=True)` + 无事 result → 1 条且含「（人工触发）」 |
| T-11 | 宿主：开关打开 = 旧行为 | `setenv('DAILY_JOBS_NOTIFY_NOOP','true')` + 无事 result → 2 条（开始 + 完成）；零产出 → 完成消息以 `⚠️ 每日任务完成（无有效产出）：` 开头 |
| T-12 | 宿主：阈值内不发"仍在运行" | 阈值设为 5s、handler 立即返回 → `sent.texts` 中**无**「⏳ 仍在运行」 |
| T-13 | 宿主：超阈值发"仍在运行" | 阈值设为 `0.05`、handler `sleep(0.3)` → 收到恰好 1 条以 `⏳ 每日任务仍在运行：` 开头的消息（与完成消息并存，最多 2 条） |
| T-14 | 阈值 `0` 关闭提示 | `setenv('DAILY_JOBS_RUNNING_NOTICE_SECONDS','0')` + 慢 handler → **无**「⏳」消息 |
| T-15 | 提示回调异常不得影响任务 | patch `runtime._send_feishu` 抛异常 → `_run_job` 正常收尾、台账仍 `success` |
| T-16 | `trigger_job` 传 `manual=True` | patch `runtime._run_job` 捕获 kwargs → `kwargs.get('manual') is True` |

约定的桩点（本仓铁律，见 `CLAUDE.md`「打桩点规则」与 `tests/test_daily_jobs_notify_truthfulness.py` 文件头注释）：

```python
from adapters.inbound.fastapi_app.daily_jobs import runtime
monkeypatch.setattr(runtime, '_send_feishu', lambda text: (sent.append(text), True)[1])
monkeypatch.setattr(runtime, '_mark_running', lambda *a, **k: None)
monkeypatch.setattr(runtime, '_mark_done', lambda *a, **k: marks.append((a, k)))
```
**不得**把桩打在 `alerting._send_feishu` 或 `daily_jobs_bootstrap._send_feishu` 上（名字在、不生效）。

## 3. 既有用例改写点（serves: FR-2, FR-7）

`tests/test_daily_jobs_notify_truthfulness.py` 里有 **2 条**用例把"零产出仍要发 ⚠️"写成了断言，
它们编码的正是本需求要推翻的旧口径（R3），**必须**随本需求改写：

| 用例（类::方法） | 现状断言 | 改写为 |
|---|---|---|
| `TestHostTone::test_zero_output_uses_warning_title` | `sent.texts[-1].startswith('⚠️ 每日任务完成（无有效产出）：…')` | 拆两条：① 默认（开关关）→ `sent.texts == []`；② 开关打开 → ⚠️ 文案（旧口径作为回滚态保留） |
| `TestHostTone::test_elapsed_line_rendered_by_formatter` | 用 `_result()`（零产出）取 `sent.texts[-1]` 找「耗时: 」 | 改用有产出结果（`_result(computed_ok=3, no_trades=2, insufficient_sample=0)`），断言不变（仍是「秒」结尾） |

**确认无需改动**（但实施后必须重跑）：`TestHostTone::test_nonzero_output_keeps_success_title`（有产出 → ✅）、
`test_mark_done_status_stays_success`（只查台账）、`TestIdleStreak::test_streak_query_failure_degrades_loudly`
（只查台账 success），以及 `tests/test_false_success_guard.py`（失败路径）、
`tests/test_daily_jobs_trading_day_gate.py`（跳过路径，本就静默）、`tests/test_notify_guard.py`（打桩点纪律）、
`tests/test_freshness_guard.py`、`tests/test_job_failure_alerting.py`（失败告警，不受影响）。

## 4. 命令与期望输出（serves: FR-8）

```bash
# ① 本需求回归锁
./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q
#    → 全过（T-1 ~ T-16）

# ② 被改口径的既有文件 + 相邻路径回归
./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py \
    tests/test_daily_jobs_bootstrap.py tests/test_daily_jobs_trading_day_gate.py \
    tests/test_false_success_guard.py tests/test_notify_guard.py -q
#    → 全过；会话末打印 notify-guard intercepted=N egress=0 offenders=[]

# ③ 回滚态自证（开关打开 = 旧行为）
DAILY_JOBS_NOTIFY_NOOP=true ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q
#    → 全过（T-11 在开关态下断言两条）

# ④ 规范条目核对（kb-conventions-c01「层边界只许向内」）
grep -n "^from\|^import" adapters/inbound/fastapi_app/daily_jobs/notify_policy.py
#    → 只允许：标准库 + 同包 `...daily_jobs.interval._env_flag`；
#      不得出现 application. / domain. / infrastructure. 的新依赖（adapters 层不自造向内依赖）
```

验收口径引用规范条目：`reqboard_kb(kind='standard')` → `kb-conventions-c01`（层边界只许向内）。
本需求新增的 `notify_policy.py` 位于 adapters 层、只依赖标准库与同包私有 helper，
**不新增任何跨层依赖**，故 ④ 的 grep 是这条规范在本需求上的可执行落点。

## 5. 真实观察（serves: FR-2, FR-5, FR-8）

部署后次日（或当日手动 `trigger_job` 之外的自然排班）取两条证据：

```bash
# 台账：仍留痕（无事也 success）
psql -d quant_investment -Atc "select job_id,status,result->>'status'
  from quant.inprocess_job_runs where run_date = current_date and job_id='event_calendar_check';"
#   → success | no_event

# 日志：静默原因可查（新增可观测点）
grep inprocess_job_notify_skipped logs/api.log | tail -5
#   → {"job":"event_calendar_check","reason":"no_op",...}
```
飞书侧（人看）：当日**无**「▶️ 每日任务开始」/「✅ 每日任务完成：event_calendar_check」两条
（对照 2026-10-06 实发 2 条，见需求文档 E9）。

## 6. 反例与边界（防"测过了但没测对"）（serves: FR-1, FR-4）

- **反例必须留下**：T-1 的 `{'no_output': 1}`（真值但非 `True`）与 T-9 的"无事+失败"两条是**反向锁**——
  去掉它们，判据可以悄悄放宽到 `truthy` 或让失败被静默，而测试仍全绿。
- **不许用真实外发验证**：所有 L2 用例都在 notify-guard 下跑（未声明的真实外发 = 该用例失败）。
- **不许以"消息文本变了"当失败**：本需求只允许两类文本变化——完成消息新增「（人工触发）」分支、
  新增「⏳ 每日任务仍在运行」；其余文案逐字不变。
