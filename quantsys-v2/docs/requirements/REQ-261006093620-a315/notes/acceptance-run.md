# 验收运行记录（REQ-261006093620-a315）

> 本文件按卡追加**实际输出**（不是「应该没问题」）。t8 会在此文件上汇总端到端读数。

## 基线（2026-10-06 · t1 测试段建立）

```
$ ./venv/bin/python -m pytest tests/test_scheduler_duplicate_prevention.py \
      tests/test_scheduler_misfire_semantics.py tests/test_scheduler_inner_failure.py \
      tests/test_scheduler_run_result_json.py tests/infrastructure/test_apscheduler_service.py -q
67 passed in 1.64s
notify-guard intercepted=0 egress=0 offenders=[]
```

**调度侧回归基线 = 67 passed**。t4 / t5 / t6 / t8 改动后不得低于此数。

---

## t1 · 判据真源：trading_day_gate 模块与策略入口（t-63bc0a）

### 研发段（t-da2b87）

```
$ ./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q
21 passed, 1 warning in 0.86s
notify-guard intercepted=0 egress=0 offenders=[]

$ git status --short application/services/trading_day_gate.py tests/test_scheduler_trading_day_gate.py
?? application/services/trading_day_gate.py
?? tests/test_scheduler_trading_day_gate.py

$ wc -l application/services/trading_day_gate.py tests/test_scheduler_trading_day_gate.py
  163 application/services/trading_day_gate.py
  184 tests/test_scheduler_trading_day_gate.py
```

### 联调段（t-ae7033）

```
$ ./venv/bin/python -c "import infrastructure.scheduler.job_executor as je; \
    from application.services.trading_day_gate import should_skip, skip_non_trading_day; ..."
infra->app 导入 OK；today trading-days = True
③ 兼容入口仍可用 = True

# AST 依赖扫描（确认无反向依赖）
本模块依赖: ['__future__', 'datetime', 'typing', 'application.services.trading_day_guard']
是否引入 infrastructure: False

$ ./venv/bin/python -m pytest tests/test_trading_day_guard.py \
      tests/test_trading_day_resolver.py tests/test_daily_jobs_trading_day_gate.py -q
87 passed in 1.06s
```

### 复核段（t-eb87e5）

```
$ ./venv/bin/python docs/requirements/REQ-261006093620-a315/notes/gate-differential-check.py
[OK ] 休市日(法定节假日): skip=True  source=trading-calendar-holiday degraded=False
[OK ] 周末:               skip=True  source=weekend                  degraded=False
[OK ] 交易日:             skip=False source=trading-calendar         degraded=False
[OK ] 降级:工作日回退:    skip=False source=weekday_fallback         degraded=True
[OK ] 降级:日历不可用:    skip=False source=unavailable              degraded=True
[OK ] 未来日期:           skip=True  source=future                   degraded=False
[OK ] 判定器自身异常:     skip=False source=gate-error               degraded=True

✅ 全部一致：7 个场景 × 3 个入口（skip_non_trading_day / is_non_trading_day / verdict_info）逐字相同
退出码 0
```

**契约核对**（`inspect.signature`，对照 design/interfaces.md §1）：

```
verdict_info          (now: Optional[datetime] = None) -> Dict[str, Any]
skip_non_trading_day  (now: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]
is_non_trading_day    (now: Optional[datetime] = None) -> bool
should_skip           (policy: Optional[str], now: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]
常量: always / trading-days / holidays；SOURCE_GATE_ERROR = gate-error
节假日来源常量复用守卫的 SOURCE_CALENDAR_HOLIDAY（不留第二份字面量）
```

**未跑的检查（如实记录）**：`ruff` / `black` 不在 venv（本仓 dev 依赖未装），本次以
`compileall` + AST 依赖扫描 + 差分核对替代；lint 门待 CI 侧或装齐 dev 依赖后补跑。

### 测试段（t-54a3c8）

```
$ ./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q
21 passed, 1 warning in 1.77s

$ ./venv/bin/python -c "from application.services.trading_day_gate import should_skip as s; print(s('always')[0], s('holiday')[0])"
False False
```

**今日真实读数（验收对照，2026-10-06 国庆休市）**：

```
always        -> False   （缺省策略：照跑，行为与装门之前一致）
trading-days  -> True    （非交易日：跳过）
holidays      -> True    （日历答法定节假日：跳过）
2026-10-08 是交易日（正确判据 resolve_trading_day(d).date == d）: True
```

**与卡上验收的偏差（显式声明）**：卡上写「反例锁断言
`TradingDayGuard.check('2026-10-08').source=='future'`」。已实现为**远期日期**语义锁
（`check('2030-01-02').source == 'future'`），理由：`2026-10-08` 只在 10-08 **之前**返回
`future`，写死它会让用例在复市当天自己变红（假红）。10-08 的当日读数由上面的命令当场取证，
语义（未来日期保守判非交易日）已被测试永久锁住。

---

## t2 · 数据契约：三值列 + CHECK + 8 行回填 + ORM（t-e05ce2）

### 研发段（t-a7e4bb）

```
$ PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py
[dry-run] ALTER TABLE ... ADD COLUMN IF NOT EXISTS trading_day_policy varchar(16) NOT NULL DEFAULT 'always'
[dry-run] ALTER TABLE ... DROP CONSTRAINT IF EXISTS scheduler_tasks_trading_day_policy_check
[dry-run] ALTER TABLE ... ADD CONSTRAINT ... CHECK (trading_day_policy IN ('always','trading-days','holidays'))
[dry-run] COMMENT ON COLUMN ...
[dry-run] 回填计划: id=232 → holidays        ← 排班含周末，按 D-6 分档
[dry-run] 回填计划: id=237/242/247/249/250/259/261 → trading-days
[dry-run] 未做任何写入。加 --apply 执行。
退出码: 0

$ ... --apply --dsn postgresql://mac@127.0.0.1:5432/quant_test
[warn] 任务 232/237/242/247/249/250/259/261 不存在（可能已删除）→ 跳过，不算失败
[verify] 无「策略非 always」的行（表可能为空）；DDL 已应用     ← 空表路径无 TypeError（N7）
[完成] trading_day_policy 已就位

$ ... --apply          # 生产库
[apply] 任务 249/250/259/261 → trading-days
[verify] id=232 name='每日数据质量检查' policy=holidays
[verify] id=237/242/247/249/250/259/261 policy=trading-days
[count] always = 25 | holidays = 1 | trading-days = 7
```

**数据断言**（生产库）：

```
 挂门trading_days | 挂门holidays | 其余启用行非always | 启用总数
-----------------+--------------+--------------------+----------
               7 |            1 |                  0 |       11
```

### 联调段（t-faf05d）

```
$ ./venv/bin/python -c "... SchedulerRepository ..."
get_task(250) 含 trading_day_policy: True 值 = trading-days
list_tasks(enabled_only=True) 条数 = 11 | 缺该字段的 = []
装载链路读到的策略分布 = {'always': 3, 'trading-days': 7, 'holidays': 1}
```

### 复核段（t-37ba53）

```
# 复核① 非法值必须被 CHECK 拦住（测试库，事务内回滚）
ERROR:  new row for relation "scheduler_tasks" violates check constraint
        "scheduler_tasks_trading_day_policy_check"
DETAIL:  Failing row contains (..., bogus).

# 复核② 合法值可写、回滚后零残留
 回滚后残留 = 0

# 复核③ 幂等：重跑 --apply
[verify] ... （无任何 [apply] 写入行）| [count] always = 25 | holidays = 1 | trading-days = 7
```

### 测试段（t-3d3d60）

```
① dry-run 退出码 = 0
② 测试库列属性 = trading_day_policy | NO | 'always'::character varying
③ tests/test_orm_db_drift.py = 6 passed
④ 调度侧回归基线 = 67 passed   ← 与 t1 基线持平，未降
```

---

## t3 · ③ 退为薄转发 + 打桩点迁移（t-d91b87）

### 研发段 / 联调段 / 复核段 / 测试段

```
# 壳内零实现（两处 TradingDayGuard 命中均在 docstring 的陷阱说明，第 9-10 行）
$ grep -n "TradingDayGuard" adapters/inbound/fastapi_app/daily_jobs/gate.py
9:桩必须打在**被调函数所在模块**，即 `application.services.trading_day_gate.TradingDayGuard`。
10:打在本模块的 `TradingDayGuard` 名字上（哪怕手工造出来）**不会生效**——判定在那边取值。
$ grep -n "^\s*from" adapters/inbound/fastapi_app/daily_jobs/gate.py
16:from __future__ import annotations
18:from application.services.trading_day_gate import (  # noqa: F401

# 壳从 104 行 → 30 行；导出面 = SOURCE_GATE_ERROR / is_non_trading_day / skip_non_trading_day / verdict_info

# 调用方同源（不是拷贝）
runtime 拿到的就是新模块函数: True
pipeline 拿到的就是新模块函数: True
壳与新模块同源: True

# ③ 相关三套用例
$ ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py \
      tests/test_daily_jobs_bootstrap.py tests/test_daily_jobs_notify_truthfulness.py -q
57 passed in 1.64s

# 证伪用例单跑
$ ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q -k "forwarding_shell"
1 passed, 27 deselected

# 卡上验收命令
$ ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q
28 passed in 0.58s
$ ./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import gate; print(gate.skip_non_trading_day.__module__)"
application.services.trading_day_gate
$ 调度侧回归基线 = 67 passed
```

**与卡上验收的偏差（显式声明）**：卡上第三条「`git diff --stat` 显示 `runtime.py` 与 `pipeline.py`
零改动」**按字面无法成立** —— 工作树里这两个文件带着**上一个需求（REQ-261005203907-2b8c）的未提交接线**
（diff 内容即 `if job.trading_days_only: skip, gate_info = skip_non_trading_day()`），与本需求无关。
本次的等价证据有三条：① 本次会话未编辑这两个文件；② 其 diff 内容全部属于 2b8c 的门接线；
③ 调用方同源核验（`runtime.skip_non_trading_day is 新模块函数` = True）+ 57 条相关用例全过。

**另一处如实登记**：t1 复核用的差分脚本在本卡之后**失去对比意义**（旧实现已退为转发壳，
`old_gate is new_gate` 为 True = 自比），已在脚本头部标注为一次性产物；t1 当时的真实输出仍留在本文档上方。

---

## t5 · 执行期接门与跳过落账（t-42eb9a）

### 研发段（t-49f017）

```
$ ./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py -q
6 passed in 0.82s
notify-guard intercepted=0 egress=0 offenders=[]
```

覆盖：N1 休市日 `_execute_command` 零调用；N2 失败上报与 Agent OS 事件零调用；
N4 交易日 `complete_run_skipped` 零调用；FR-6 `manual=True` 休市日照跑；缺策略字段回落 `always`；
入口 `manual` 透传。

**夹具修正一处（如实记录）**：首版把假 session 写成 `object()`，照跑路径要
`session.rollback()` 止血 → `AttributeError`（2 条红）。这是**测试夹具**缺陷、不是产品缺陷：
改用具 `rollback/commit/close` 的假 session 后 6 条全过。

### 联调段（t-b88384）—— 真端到端探针（真仓储 + 真门 + 真库 + 今日恰为休市）

```
$ ./venv/bin/python -m pytest docs/requirements/REQ-261006093620-a315/notes/test_e2e_holiday_skip_probe.py -q -s
[e2e] run.status = skipped
[e2e] run.error  = None
[e2e] result     = {'policy': 'trading-days',
                    'reason': '交易日历判定为非交易日（来源 provider：该日不在交易日历中）',
                    'skipped': True, 'degraded': False,
                    'trading_day_source': 'trading-calendar-holiday'}
1 passed in 1.29s
```

**这条读数是本需求的交付点**：同一条执行路径在 2026-10-06 09:25 曾产出
`pre-market-scan run_id=3379 status=success`；现在同一路径在休市日产出 `skipped`。

### 复核段（t-cddd7a）

```
$ grep -n "交易日门|检查是否已有运行中的实例|manual" infrastructure/scheduler/job_executor.py
240:        # 2. 交易日门（... FR-2/FR-3/FR-4/FR-7）      ← 门
247:        if not manual:
253:                run_id = repo.create_run(task_id)
269:        # 3. 检查是否已有运行中的实例（防止并发）      ← 门在并发检查之前 ✓

$ grep -n "args=\[" infrastructure/scheduler/apscheduler_service.py
204:                    args=[task.get("id")],              ← 自动到点不传 manual → 必判门 ✓
```

### 测试段（t-0b6aaf）

```
$ ./venv/bin/python -m pytest tests/test_scheduler_duplicate_prevention.py \
      tests/test_scheduler_misfire_semantics.py tests/test_scheduler_inner_failure.py \
      tests/test_scheduler_run_result_json.py tests/infrastructure/test_apscheduler_service.py \
      tests/infrastructure/test_scheduler_run_skipped_ledger.py \
      tests/infrastructure/test_scheduler_skip_ledger.py -q
81 passed in 2.07s      ← 基线 67 + t4 新增 8 + t5 新增 6
```

---

## t6 · 人工触发改投一次性 manual=True job（t-3a7ebb）

### 研发段（t-2bf7e5）

```
$ ./venv/bin/python -m pytest tests/infrastructure/test_apscheduler_service.py -q
13 passed in 1.08s
```

`trigger_task_now` 由 `modify_job(next_run_time=now)` 改为投递一次性 job：

```
add_job(func=execute_scheduled_job, trigger=DateTrigger(run_date=datetime.now()),
        args=[task_id], kwargs={'manual': True},
        id=f'manual_{task_id}_{int(time.time())}', name=f'[manual] {job.name}',
        replace_existing=False, misfire_grace_time=None)
```

新断言四条：cron 的 `next_run_time` **未被扰动**；`manual_1_*` 唯一且 `kwargs['manual'] is True`；
`misfire_grace_time is None`；未注册 task_id 仍抛 `ValueError`（路由层靠它降级到 legacy 路径）。

### 联调段（t-02dd78）

```
$ git diff --stat adapters/inbound/fastapi_app/routes/scheduler_async.py
（无输出 = 路由层零改动）

$ ./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py -q -k "manual"
2 passed, 4 deselected      ← manual=True 时休市日照跑（门根本没被问）
```

### 复核段（t-badb26）—— 含一次**自我更正**

```
$ grep -rn "modify_job" --include='*.py' infrastructure/ adapters/ | wc -l
2                            ← 首轮口径：粗（把 docstring 提及算成了命中）
$ grep -rn "\.modify_job(" --include='*.py' infrastructure/ adapters/ | wc -l
0                            ← 精确口径（带点与左括号）：实际调用点归零 ✓
```

命中 2 处的真实身份是 `apscheduler_service.py:459/461` —— **本次新写的 docstring 里对旧实现的说明**
（"为什么必须改：`modify_job` 让同一个 job 立即触发…"）。结论（调用点归零）成立，
但首轮汇报把粗口径计数当成结论陈述，已在卡上追加更正。

### 测试段（t-2a9fe9）

```
$ ./venv/bin/python -m pytest tests/test_scheduler_duplicate_prevention.py \
      tests/test_scheduler_misfire_semantics.py tests/test_scheduler_inner_failure.py \
      tests/test_scheduler_run_result_json.py tests/infrastructure/test_apscheduler_service.py \
      tests/infrastructure/test_scheduler_run_skipped_ledger.py \
      tests/infrastructure/test_scheduler_skip_ledger.py -q
81 passed in 0.99s
```

---

## t7 · 巡检口径同步（t-54d79f）

### 研发段（t-79a341）

`should_have_run.py` 把「真执行」拆成两套**写出来的**常量（不再依赖 `!= 'missed'` 的副作用）：

```python
HANDLED_STATUSES = ('success', 'failed', 'skipped')   # 判「该槽位是否已处理」→ 判漏跑
REAL_RUN_STATUSES = ('success', 'failed')             # 呈现「最近一次真执行」→ 不含 skipped
```

取数由两次批量查询增至三次（真执行 / 已处理 / missed 记账）；SQL 的 IN 列表由常量拼接并加
`[a-z_]` 白名单校验（非用户输入，仍拒绝非法字面量）。

```
$ ./venv/bin/python -m pytest tests/test_should_have_run.py -q
31 passed in 0.68s
```

新增 5 条：门跳过不算漏跑（且 `last_run_at is None`——呈现不把 skipped 当执行）；
更早的跳过**不洗白**真漏跑；`missed` 仍告警；两套集合互斥；IN 拼接拒绝非法字面量。

### 联调段（t-7d47dd）—— 生产库只读实跑（与 health_probe 共用实现，不发通知）

```
$ ./venv/bin/python tools/check_should_have_run.py
每日信号执行        30 15 * * 1-5  2026-10-06 15:30  2026-10-05 15:30(success)  ok(改动豁免…)
pre-market-scan     25 9 * * 1-5   2026-10-07 09:25  2026-10-06 09:25(success)  ok(改动豁免,原应跑 2026-10-06 09:25)
daily-strategy-validation  0 21 * * 1-5  2026-10-05 21:00  2026-10-02 21:02(success)  missed
…
盘点时刻：2026-10-06T10:04:03+08:00｜启用任务：11；漏跑：1；无法判定：0；改动豁免：10
退出码: 2
```

读数里有本次要修的那条**假成功**（`pre-market-scan 2026-10-06 09:25(success)`），
以及下一个休市日槽位 `2026-10-07 09:25` —— 门接上后该槽位会产出 `skipped`，
而本模块现在把它认作「已处理」→ R3 记的假警由此消除。

**如实登记两处**：
1. 唯一那条 `missed` 是 `daily-strategy-validation`，属**不挂门的三条**之一（本就该照跑）；
2. 迁移回填写了 `updated_at=now()`，使 10 条任务暂时落进配置改动护栏（"自我改动以来未到期"），
   约一个排班周期后自然失效——这是回填的副作用，不是缺陷，但会短暂压低漏跑检出。

### 复核段（t-98ed3c）—— 计划的一处范围错误

计划写「watchdog 有两处 `status='success'` 需改」，实查**只有一处属本次范围**：

| 行 | 表 | 归属 | 本次动作 |
|---|---|---|---|
| 289 | `quant.scheduler_runs` | **v2 自调度** | 改为 `status IN ('success','skipped')` ✓ |
| 390 | `public.task_runs` | **Agent OS 调度**（agent 侧任务，无交易日门、无 skipped 语义） | **不改**，并就地写入"不要一并改"的警示注释 |

文件在 **monorepo 根 `scripts/`（v2 工作区之外）**：`compileall` 通过；
注入 croniter 桩后可 exec；v2 段新判据在位、Agent OS 段未被误改（全文件仅剩 1 处 success-only 判据）。

**两次门禁拦下（如实登记）**：
1. 用工作区相对路径 `scripts/scheduler_watchdog.py` 登记 `files_changed` → 被凭证门拒绝
   （该路径在工作区内不存在；真实文件在工作区外）；
2. `requirement.md` 的**作用域清单漏列根 `scripts/`**，而 FR-3/R3 明确点名该文件——
   属文档清单不全，不是范围蔓延（已在本次汇报中登记，供验收时核对）。

### 测试段（t-23d580）

```
$ ./venv/bin/python -m pytest tests/test_should_have_run.py tests/test_health_probe.py -q
36 passed in 0.58s
```

既有 24 条用例**零改动**通过（假源未喂 `handled` 时回落到 `runs`，行为不变）。

**该模块自带测试在本机从来跑不了**：`../scripts/tests/test_scheduler_watchdog_catchup.py`
10 个 error 全是 `ModuleNotFoundError: No module named 'croniter'`（venv 缺依赖），**非本次引入**。

---

## t8 · 端到端验收、真实台账观察与回滚演练（t-ea51f0）

### 六条验收命令（decomposition.md §6）

```
① tests/test_scheduler_trading_day_gate.py                         → 21 passed
② tests/infrastructure/test_scheduler_skip_ledger.py               →  6 passed
③ tests/test_daily_jobs_trading_day_gate.py                        → 28 passed
④ tests/test_should_have_run.py + tests/test_orm_db_drift.py       → 37 passed
⑤ tests/infrastructure/test_apscheduler_service.py                 → 13 passed
⑥ 台账查询（10-07 尚无数据，今天 10-06）                            → 见下
```

回归基线：**67 → 81 passed**（t4 +8、t5 +6），各卡复用全程未降。

### 生产重启（加载本次改动）

```
重启前 PID 74347（启动于 Mon Oct  5 21:28:34，跑的是改动前代码）
launchctl kickstart -k gui/501/com.pi-investment.v2-api
重启后 PID 86953（Tue Oct  6 10:05:58）
日志：Task loading complete: 11 loaded, 0 skipped (Agent OS) / ✅ APScheduler started
```

### ★ 生产端真实观测（决定性证据）

```
$ psql -d quant_investment -c "select r.id, t.name, r.status, r.started_at, r.error,
      r.result->>'trading_day_source' src, r.result->>'policy' policy from quant.scheduler_runs r
      join quant.scheduler_tasks t on t.id=r.task_id
      where r.started_at::date = DATE '2026-10-06' and r.started_at > TIMESTAMPTZ '2026-10-06 10:05:00+08'"

  id  |      name       | status  |          started_at           | error |           src            |    policy
------+-----------------+---------+-------------------------------+-------+--------------------------+--------------
 3381 | chan-scan-daily | skipped | 2026-10-06 10:10:00.072629+08 |       | trading-calendar-holiday | trading-days

服务日志：
Task 261 (chan-scan-daily) skipped by trading-day gate
  (policy=trading-days, source=trading-calendar-holiday, degraded=False, day=2026-10-06)
```

**对照原始问题**：同一条执行路径在 `2026-10-06 09:25` 曾产出
`pre-market-scan run_id=3379 / success / 129ms`；现在休市日的 `10:10` 槽位产出 `skipped`。

### 回滚 / 免 reload 演练（真库 + 真门 + 真执行体）

```
[① trading-days] status = skipped     ← 休市日：跳过、不执行
[② always]       status = success     ← 只改一行策略：立即照跑（无 reload、无重启）
[③ 改回]         status = skipped     ← 可逆
[结论] 策略改动即时生效、无需 reload；回滚 = 改回 always，可逆。
notify-guard intercepted=0 egress=0
```

### 待观察（今天做不到的两条）

| 时间点 | 期望 | 状态 |
|---|---|---|
| 2026-10-07（休市） | 8 条挂门任务 `skipped`、3 条不挂 `success` | ⏳ 该日未到 |
| 2026-10-08（复市首日） | 挂门任务恢复 `success`（不得跳过） | ⏳ 该日未到 |

### 探针首版的一次真实教训

`test_e2e_policy_toggle_probe.py` 首版故意执行一个不存在的命令 → 执行失败
→ 触发 `_report_failure_to_sink` → 起了真通知链并**尝试向 Agent OS 外发**
（被 `tests/notify_guard.py` 拦截：`intercepted=1 egress=0`，用户无感知），用例被判红。
补两处桩（`_execute_command` 换无害成功 + `_report_failure_to_sink` 空实现）后 `intercepted=0`。
**结论**：notify-guard 按设计拦住了我自己的失误，这条纪律有效。






