# 拆分计划 · REQ-261006165125-23a9（每日任务空结果不发飞书）

**需求ID**: REQ-261006165125-23a9
**类型**: feature
**依据**: `requirement.md`（FR-1~FR-8）+ `design/`（architecture / interfaces / data-model / use-cases / test-cases）
**侧**: backend（无前端卡，无原型锚点）

## 1. 目标与做法（一段人能读懂的话）

让每日任务的通知从"跑了就说"改成"有事才说"：定义一个唯一的"无事"判据（`notify_policy.py`），
无事时**开始与完成两条飞书都不发**，台账照留痕；"开始消息"改成任务跑超过阈值才发的
「⏳ 仍在运行」提示；失败与异常一律照发；人工触发必须有回执；两个环境变量可一键回滚旧行为。

## 2. 代码层面变更盘点

### 新增

| 文件 | 内容 |
|---|---|
| `adapters/inbound/fastapi_app/daily_jobs/notify_policy.py` | 判据纯函数 `is_no_op` / `should_send_completion` / `should_send_start` + env 解析 `notify_noop_enabled` / `running_notice_seconds` + 常量 `NO_OP_STATUSES` |
| `tests/test_daily_jobs_quiet_noop.py` | 回归锁 T-1~T-16（见 design/test-cases.md §2） |
| `docs/requirements/REQ-261006165125-23a9/notes/rollback-and-observation.md` | 回滚态验证记录 + 真实观察留痕 |

### 修改（精确到函数）

| 文件 | 函数/位置 | 改什么 |
|---|---|---|
| `daily_jobs/runtime.py` | `_run_job` | 签名加 `manual: bool = False`；删除 line 126 的无条件开始消息；完成消息改为 `if should_send_completion(...)` 包裹并改调 `alerting.format_completion`；失败两处**不动** |
| `daily_jobs/runtime.py` | `_arm_running_notice` / `_send_running_notice` | **新增**两个函数（`threading.Timer`，回调住 runtime 以保住打桩点） |
| `daily_jobs/runtime.py` | `trigger_job` | 线程调用传 `manual=True`（签名与返回体不变） |
| `daily_jobs/alerting.py` | `format_completion` | **新增**：标题优先级 人工触发 > ⚠️无有效产出 > ✅；正文沿用 `_format_elapsed` / `_summarize_result` |
| `daily_jobs_bootstrap.py` | `__all__` + 转发 import | 补出 `_arm_running_notice` / `_send_running_notice`（保持转发壳诚实；既有 44 条导入路径不受影响） |
| `tests/test_daily_jobs_notify_truthfulness.py` | `TestHostTone` 两条用例 | 按 design/test-cases.md §3 改写（旧口径断言 → 新口径 + 开关态旧口径） |

### 删除

- **删旧行为**（不是删符号）：`runtime.py:126` 的"无条件立即发开始消息"。
  符号 `_send_feishu` / `_summarize_result` / `_format_elapsed` / `_mark_done` **一个都不删**。
- **不改** `daily_jobs/__init__.py`（新增符号不需要新的对外导入路径）、
  不改 `job_run_repository.py`、不改任何 handler、不改 APScheduler 与 interval 路径。

### 数据层变更

**零 DDL、零迁移、零回填**（design/data-model.md §1）；新增 2 个环境变量（只影响消息层）。

## 3. 批次与依赖（禁止前向引用）

```
批次 1（契约与判据）      policy ─┐
                          format ─┤
批次 2（宿主接线）                 └─▶ host
批次 3（回归锁，可并行）                ├─▶ tests-new
                                        └─▶ tests-legacy
批次 4（回滚与真实观察）                     tests-new, tests-legacy ─▶ rollback
```

## 4. 任务表

| key | 标题 | phase | depends_on | FR | D-x | footprint（files/anchors/chars → DU） |
|---|---|---|---|---|---|---|
| `policy` | 新建通知判据模块 notify_policy（无事判据 + 两个 env 解析） | implement | — | FR-1, FR-7 | D-2, D-3 | 1 / 6 / 1400 → **4.7** |
| `format` | alerting 抽出完成消息组装 format_completion | implement | — | FR-2, FR-6, FR-7 | D-2, D-3 | 1 / 3 / 800 → **2.9** |
| `host` | runtime 接线：通知收敛 + manual 参数 + 超阈值提示 + trigger_job | implement | policy, format | FR-2, FR-3, FR-4, FR-5, FR-6 | D-2, D-3 | 2 / 6 / 1800 → **5.9** |
| `tests-new` | 新增 tests/test_daily_jobs_quiet_noop.py（T-1~T-16） | test | host | FR-8（覆盖 FR-1~FR-7） | D-2, D-3 | 1 / 16 / 2200 → **10.1** |
| `tests-legacy` | 改写被新口径推翻的 2 条既有断言 + 相邻回归 | test | host | FR-8 | D-2 | 1 / 4 / 900 → **3.5** |
| `rollback` | 回滚态验证 + 部署重启 + 真实观察留痕 | test | tests-new, tests-legacy | FR-7, FR-8 | D-3 | 1 / 5 / 1200 → **4.1** |

容量核算（口径 `files×1 + anchors×0.5 + chars/2000`，容量 16 DU）：最大卡 `tests-new` = 10.1 DU < 16，
**无超容量卡**（不需 `⚠️超容量` 标注）。

### 4.1 `policy`（新增判据模块）

- **implementation**：新建 `adapters/inbound/fastapi_app/daily_jobs/notify_policy.py`，按 design/interfaces.md §1
  逐一实现 `NO_OP_STATUSES` / `RUNNING_NOTICE_DEFAULT_SECONDS` / `is_no_op` / `notify_noop_enabled` /
  `running_notice_seconds` / `should_send_start` / `should_send_completion`。
  `is_no_op` 严格 `is True`、status 走 `.strip().lower()` 白名单；env 解析复用同包
  `interval._env_flag`（不新增跨层依赖，符合 kb-conventions-c01）；任何输入不得抛异常。
- **acceptance**（可跑）：
  ```bash
  ./venv/bin/python -c "
  from adapters.inbound.fastapi_app.daily_jobs import notify_policy as p
  assert p.is_no_op({'status':'no_event'}) and p.is_no_op({'status':' NO_OP '}) and p.is_no_op({'no_output':True})
  assert not p.is_no_op({'no_output':1}) and not p.is_no_op({'status':'success'}) and not p.is_no_op(None) and not p.is_no_op('x')
  assert p.should_send_completion(result={'status':'no_event'}) is False
  assert p.should_send_completion(result={'status':'no_event'}, manual=True) is True
  print('policy ok')"
  # 坏值容错（不得抛异常）
  DAILY_JOBS_RUNNING_NOTICE_SECONDS=abc ./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import notify_policy as p; assert p.running_notice_seconds()==60.0"
  DAILY_JOBS_RUNNING_NOTICE_SECONDS=0 ./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import notify_policy as p; assert p.running_notice_seconds()==0.0"
  DAILY_JOBS_NOTIFY_NOOP=1 ./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import notify_policy as p; assert p.notify_noop_enabled() and p.should_send_start()"
  # 层边界（kb-conventions-c01）：不得出现 application./domain./infrastructure. 依赖
  ! grep -nE '^(from|import) (application|domain|infrastructure)' adapters/inbound/fastapi_app/daily_jobs/notify_policy.py
  ```
  → 四条命令全部退出码 0。

### 4.2 `format`（消息组装）

- **implementation**：在 `daily_jobs/alerting.py` 新增 `format_completion(job_id, description, elapsed, result, *,
  manual=False, warn_no_output=False) -> str`，标题优先级 `manual` > `warn_no_output` > `✅`；
  正文 `{description}\n耗时: {_format_elapsed(elapsed)}` + 非空摘要。
  **不改** `_send_feishu` / `_summarize_result` / `_format_elapsed`。
- **acceptance**（可跑）：
  ```bash
  ./venv/bin/python -c "
  from adapters.inbound.fastapi_app.daily_jobs import alerting as a
  t = a.format_completion('event_calendar_check','desc',1.2,{'updated':1})
  assert t.startswith('✅ 每日任务完成：event_calendar_check') and '耗时: 1.2 秒' in t, t
  assert a.format_completion('j','d',1.2,{'updated':1},manual=True).startswith('✅ 每日任务完成（人工触发）：j')
  assert a.format_completion('j','d',1.2,{'no_output':True},warn_no_output=True).startswith('⚠️ 每日任务完成（无有效产出）：j')
  print('format ok')"
  ```

### 4.3 `host`（宿主接线，本需求核心）

- **implementation**：`daily_jobs/runtime.py`：
  ① `_run_job(job, run_date, manual=False)`；② 删 line 126 无条件开始消息，改为
  `if notify_policy.should_send_start(): _send_feishu(开始文案)`（仅回滚态为真）；
  ③ `handler()` 前 `timer = _arm_running_notice(job)`，`finally` 里 `timer.cancel()`；
  ④ 完成分支改为 `if should_send_completion(result=result, manual=manual): _send_feishu(format_completion(...))`
  （`warn_no_output = notify_policy.notify_noop_enabled() and result.get('no_output') is True`）；
  ⑤ 无事外发被抑制时记 `logger.info("inprocess_job_notify_skipped", job=..., reason="no_op", manual=...)`；
  ⑥ 失败两处（内层失败 / 异常）**逐字不动**；⑦ `_arm_running_notice` / `_send_running_notice` 按
  interfaces.md §2.2 实现（回调内异常吞掉并记 `inprocess_job_running_notice_error`）；
  ⑧ `trigger_job` 传 `manual=True`。`daily_jobs_bootstrap.py` 的 `__all__`/转发 import 补两个新符号。
- **acceptance**（可跑）：
  ```bash
  ./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_daily_jobs_trading_day_gate.py \
      tests/test_false_success_guard.py tests/test_notify_guard.py -q   # 既有回归全过（跳过/失败路径未被误伤）

  ./venv/bin/python -c "
  from datetime import time as dtime
  from adapters.inbound.fastapi_app.daily_jobs import runtime
  from adapters.inbound.fastapi_app.daily_jobs.defs import JobDef
  sent=[]; runtime._send_feishu=lambda t:(sent.append(t),True)[1]
  runtime._mark_running=lambda *a,**k:None; runtime._mark_done=lambda *a,**k:None
  mk=lambda r: JobDef('event_calendar_check',dtime(16,45),(0,1,2,3,4,5,6),lambda:r,'事件日历检查')
  runtime._run_job(mk({'status':'no_event'}),'2026-10-07'); assert sent==[], sent
  runtime._run_job(mk({'updated':1}),'2026-10-07'); assert len(sent)==1 and sent[0].startswith('✅'), sent
  sent.clear()
  runtime._run_job(mk(lambda: (_ for _ in ()).throw(RuntimeError('boom'))),'2026-10-07') if False else None
  print('host ok')"

  # 定时路径 manual 默认 False：无事仍静默（用真实 JobDef + 桩）
  grep -n "manual: bool = False" adapters/inbound/fastapi_app/daily_jobs/runtime.py
  ```

### 4.4 `tests-new`（回归锁）

- **implementation**：新建 `tests/test_daily_jobs_quiet_noop.py`，实现 design/test-cases.md §2 的 T-1~T-16；
  打桩点**必须**是 `runtime._send_feishu` / `runtime._mark_running` / `runtime._mark_done`；
  阈值类用例用 `monkeypatch.setenv('DAILY_JOBS_RUNNING_NOTICE_SECONDS', ...)`（0.05 / 0）；
  T-13 用 `time.sleep(0.3)` 触发阈值提示，断言恰好 1 条 `⏳ 每日任务仍在运行：`。
  用例数上限：**16 条**，不做与 FR 无关的扩展。
- **acceptance**（可跑）：
  ```bash
  ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q
  #   → 全过（16 passed 或以上）；会话末 notify-guard 打印 egress=0
  ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q 2>&1 | tail -3 | grep -E "egress=0|passed"
  ```

### 4.5 `tests-legacy`（旧口径断言改写）

- **implementation**：`tests/test_daily_jobs_notify_truthfulness.py`：
  ① `test_zero_output_uses_warning_title` → 拆成"默认态零消息"+"开关态 ⚠️"两条；
  ② `test_elapsed_line_rendered_by_formatter` → 改用有产出结果构造（`computed_ok=3`）。
  其余用例（`test_nonzero_output_keeps_success_title` / `test_mark_done_status_stays_success` /
  `test_streak_query_failure_degrades_loudly`）**不改**，只重跑。
- **acceptance**（可跑）：
  ```bash
  ./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py tests/test_notify_guard.py -q   # 全过
  # 旧断言不得残留（⚠️ 断言只允许出现在开关态用例里）
  grep -n "startswith('⚠️ 每日任务完成" tests/test_daily_jobs_notify_truthfulness.py
  #   → 仅 1 处，且所在用例先 setenv('DAILY_JOBS_NOTIFY_NOOP','true')
  ```

### 4.6 `rollback`（回滚与真实观察）

- **implementation**：验证两条回滚路径并留痕到
  `docs/requirements/REQ-261006165125-23a9/notes/rollback-and-observation.md`：
  ① 开关态跑测试；② `DAILY_JOBS_RUNNING_NOTICE_SECONDS=0` 只关提示；
  ③ `launchctl kickstart -k gui/501/com.pi-investment.v2-api` 后确认服务健康；
  ④ 真实观察：等下一次自然排班（16:45）或用一个 `manual=False` 的真实调用，记录
  `quant.inprocess_job_runs` 行 + 飞书侧是否零条 + `inprocess_job_notify_skipped` 日志。
  **观察窗口未到就如实标注"待观察"**，不得用推断代替实测。
- **acceptance**（可跑）：
  ```bash
  DAILY_JOBS_NOTIFY_NOOP=true ./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py -q   # 开关态全过
  DAILY_JOBS_RUNNING_NOTICE_SECONDS=0 ./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import notify_policy as p; assert p.running_notice_seconds()==0.0"
  launchctl kickstart -k gui/501/com.pi-investment.v2-api && sleep 8 && \
      curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/jobs/inprocess/today   # → 200
  psql -d quant_investment -Atc "select job_id,status,result->>'status' from quant.inprocess_job_runs where run_date=current_date and job_id='event_calendar_check';"
  #   → success|no_event（且当日无该任务飞书）；窗口未到则 notes 里写「待观察（下一自然排班 16:45）」+ 原因
  ```

## 5. 验收总口径（合并后一次跑齐）

```bash
./venv/bin/python -m pytest tests/test_daily_jobs_quiet_noop.py tests/test_daily_jobs_notify_truthfulness.py \
    tests/test_daily_jobs_bootstrap.py tests/test_daily_jobs_trading_day_gate.py \
    tests/test_false_success_guard.py tests/test_notify_guard.py tests/test_freshness_guard.py \
    tests/test_job_failure_alerting.py -q
#   → 全过；notify-guard 会话末 egress=0 offenders=[]
```

## 6. 不做什么（防范围蔓延）

- 不修 `quant.event_calendar` 空表与未排班的 ingest 任务（另案，需求文档「不做什么」已登记）；
- 不动 APScheduler / interval 路径的通知口径；
- 不动交易日门跳过分支的位置与语义；
- 不动 `no_output` 的产生侧（各 handler）；
- 不新增表/列/迁移，不改任何对外 HTTP 契约。

## 7. 下一步

计划已落盘 → 交人工批准（`reqboard_ask_confirm(target=plan)`）；
批准后自动落库任务卡并进入 **implementing**（不再中途打断）。
