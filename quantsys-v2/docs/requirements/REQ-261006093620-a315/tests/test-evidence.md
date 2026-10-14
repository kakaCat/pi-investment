# 测试证据（REQ-261006093620-a315）

> 全部输出为**提交验收前的当次运行**逐字粘贴（本仓纪律：不以自述代替证据）。
> 覆盖对照：[`../design/test-cases.md`](../design/test-cases.md) 的真值表与负向断言清单。

## 1. 汇总（一条命令跑齐新增用例 + 调度侧回归）

```console
$ ./venv/bin/python -m pytest tests/test_scheduler_duplicate_prevention.py \
    tests/test_scheduler_misfire_semantics.py tests/test_scheduler_inner_failure.py \
    tests/test_scheduler_run_result_json.py tests/infrastructure/test_apscheduler_service.py \
    tests/infrastructure/test_scheduler_run_skipped_ledger.py \
    tests/infrastructure/test_scheduler_skip_ledger.py -q
83 passed in 2.24s
notify-guard intercepted=0 egress=0 offenders=[]
```

**回归基线演进**（t1 建立，各卡复用）：`67 → 81 → 83 passed`
（t4 新增 8、t5 新增 8；其中 t5 后 2 条是**独立复核发现 F5/F6 后补的回归锁**），全程未降。

## 2. 分文件（含卡归属）

| 文件 | 用例数 | 命令 | 结果 | 覆盖 |
|---|---|---|---|---|
| `tests/test_scheduler_trading_day_gate.py` | 21 | `pytest … -q` | **21 passed** | t1：14 行策略真值表 + `future` 反例锁 + 兜底与兼容（FR-1/2/5） |
| `tests/infrastructure/test_scheduler_run_skipped_ledger.py` | 8 | `pytest … -q` | **8 passed** | t4：三态收尾语义（假会话零 DB）+ 一次真库往返（FR-3） |
| `tests/infrastructure/test_scheduler_skip_ledger.py` | 8 | `pytest … -q` | **8 passed** | t5：N1/N2/N4 负向断言 + `manual` 旁路 + 入口透传 + **F5 降级留痕** + **F6 记账失败不外抛**（FR-2/3/4/6） |
| `tests/test_daily_jobs_trading_day_gate.py` | 28 | `pytest … -q` | **28 passed** | t3：③ 语义不回归 + 打桩点迁移后的证伪断言（FR-8） |
| `tests/test_should_have_run.py` | 31 | `pytest … -q` | **31 passed** | t7：门跳过不算漏跑、更早跳过不洗白真漏跑、missed 仍告警、两套集合互斥、IN 拼接拒非法（FR-3） |
| `tests/infrastructure/test_apscheduler_service.py` | 13 | `pytest … -q` | **13 passed** | t6：一次性 manual job + 排期不被扰动 + 未知 task 抛 ValueError（FR-6） |
| `tests/test_orm_db_drift.py` | 6 | `pytest … -q` | **6 passed** | t2：ORM 与库表一致（FR-1/7） |
| `tests/test_trading_day_guard.py` + `tests/test_trading_day_resolver.py` + ③ 门用例 | 87 | `pytest … -q` | **87 passed** | 相邻链条零干扰（t1 联调段） |

五条卡上验收命令（`decomposition.md` §6）：

```console
$ ./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q                    → 21 passed
$ ./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py -q          →  6 passed
$ ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q                   → 28 passed
$ ./venv/bin/python -m pytest tests/test_should_have_run.py tests/test_orm_db_drift.py -q    → 37 passed
$ ./venv/bin/python -m pytest tests/infrastructure/test_apscheduler_service.py -q            → 13 passed
```

## 3. 负向断言清单（"过"的意义所在）

| 编号 | 断言 | 位置 | 结果 |
|---|---|---|---|
| N1 | 休市日跳过时 `_execute_command` **零调用** | `test_holiday_skips_without_executing` | pass |
| N2 | 跳过时 `_report_failure_to_sink` 与 Agent OS 事件**零调用** | `test_holiday_skip_does_not_notify` | pass |
| N3 | 跳过行 `last_error` 为空、`result` 无 `last_error` 键 | `test_holiday_skips_without_executing` | pass |
| N4 | 交易日 `complete_run_skipped` **零调用** | `test_trading_day_runs_and_never_calls_skip_ledger` | pass |
| N5 | `missed`（真漏跑）**仍然**进 missed 列表 | `test_missed_run_row_still_alarms` | pass |
| N6 | `manual=True` 时**不判门**、照跑 | `test_manual_trigger_runs_on_holiday` | pass |
| N7 | 迁移在**空表**上 verify 段不抛 | 测试库 apply 实跑（无 `row[0]` TypeError） | pass |
| — | 两套状态集互斥、`skipped` 只进"已处理" | `test_handled_and_real_status_sets_are_distinct` | pass |
| — | 打桩点迁移后**桩失效会被发现**（证伪用例非空） | `test_forwarding_shell_reads_patched_new_module` | pass |
| F5 | 降级**照跑**时 result 必带 `trading_day_gate{source,degraded,policy}`（独立复核发现后补） | `test_degraded_run_annotates_result` | pass |
| F6 | 跳过记账失败**不外抛**、且仍不执行命令（独立复核发现后补） | `test_skip_ledger_failure_does_not_raise` | pass |
| F2 | 摘掉 `skipped` 后 `/runs/failed` 的 parity 未破 | `tests/migration/test_scheduler_parity.py`（7 passed） | pass |

## 4. 端到端探针（不进正式测试集，手工调用）

```console
$ ./venv/bin/python -m pytest docs/requirements/REQ-261006093620-a315/notes/test_e2e_holiday_skip_probe.py -q -s
[e2e] run.status = skipped
[e2e] run.error  = None
[e2e] result     = {'policy': 'trading-days', 'skipped': True, 'degraded': False,
                    'trading_day_source': 'trading-calendar-holiday', 'reason': '…该日不在交易日历中'}
1 passed

$ ./venv/bin/python -m pytest docs/requirements/REQ-261006093620-a315/notes/test_e2e_policy_toggle_probe.py -q -s
[① trading-days] status = skipped
[② always]       status = success
[③ 改回]         status = skipped
1 passed
notify-guard intercepted=0 egress=0 offenders=[]
```

## 5. 生产端真实观测（决定性）

```console
$ psql -h 127.0.0.1 -U mac -d quant_investment -c "select r.id, t.name, r.status, r.started_at, r.error, \
    r.result->>'trading_day_source' src, r.result->>'policy' policy from quant.scheduler_runs r \
    join quant.scheduler_tasks t on t.id=r.task_id \
    where r.started_at::date = DATE '2026-10-06' and r.started_at > TIMESTAMPTZ '2026-10-06 10:05:00+08'"
  id  |      name       | status  |          started_at           | error |           src            |    policy
------+-----------------+---------+-------------------------------+-------+--------------------------+--------------
 3381 | chan-scan-daily | skipped | 2026-10-06 10:10:00.072629+08 |       | trading-calendar-holiday | trading-days
```

服务日志（PID 86953，10:05:58 重启后加载新代码）：

```
Task loading complete: 11 loaded, 0 skipped (Agent OS)
✅ APScheduler started
Task 261 (chan-scan-daily) skipped by trading-day gate
  (policy=trading-days, source=trading-calendar-holiday, degraded=False, day=2026-10-06)
```

**对照原始问题**：同一条路径在 `2026-10-06 09:25` 产出 `pre-market-scan run_id=3379 / success / 129ms`。

## 6. 未运行的项（如实登记，不在报告里冒充"通过"）

| 项 | 原因 | 替代证据 |
|---|---|---|
| `ruff` / `black` | venv 未装 dev 依赖（`No module named ruff/black`） | `compileall` + AST 依赖扫描 |
| `../scripts/tests/test_scheduler_watchdog_catchup.py` | venv 缺 `croniter` → 10 个 `ModuleNotFoundError`（**非本次引入**，该模块在本机从来跑不了） | 注入 croniter 桩后 exec + 文本断言（v2 段新判据在位、Agent OS 段未被误改） |
| `2026-10-07` / `2026-10-08` 台账观察 | 该两日尚未到 | 10-06 10:10 生产实跑已证明同一机制在休市日生效（见 §5） |

## 7. 卡覆盖对照（`covers:` 标注）

> 39 张任务卡（8 父卡 + 31 子卡）逐张对应到实际跑过的测试/核验。子卡的"联调/复核"段没有新增用例，
> 其证据是**当卡时点**实际执行的命令（读码核对、边界探测、真库往返、生产只读 SQL）。

### t1 · 判据真源：trading_day_gate 模块与策略入口

| 卡 | 类型 | 测试/核验 | 结果 |
|---|---|---|---|
| covers: t-63bc0a | 父卡 | `tests/test_scheduler_trading_day_gate.py`（21 条） | 通过 |
| covers: t-da2b87 | 子卡·研发 | 同上 21 条（14 行真值表 + 反例锁） | 通过 |
| covers: t-ae7033 | 子卡·联调 | 真实调度侧上下文导入 + 相邻三套 87 passed | 通过 |
| covers: t-eb87e5 | 子卡·复核 | `notes/gate-differential-check.py`（当卡时点：7 场景 × 3 入口一致）+ 签名核对 | 通过 |
| covers: t-54a3c8 | 子卡·测试 | 21 passed + `should_skip('always'/'holiday')` 一行命令 → `False False` | 通过 |

### t2 · 数据契约：三值列 + CHECK + 8 行回填 + ORM

| 卡 | 类型 | 测试/核验 | 结果 |
|---|---|---|---|
| covers: t-e05ce2 | 父卡 | 迁移 dry-run/apply + `tests/test_orm_db_drift.py`（6 条）+ 数据断言 7/1/0 | 通过 |
| covers: t-a7e4bb | 子卡·研发 | 两库 apply（测试库空表路径无 TypeError） | 通过 |
| covers: t-faf05d | 子卡·联调 | `SchedulerRepository.get_task/list_tasks` 读到策略分布（3/7/1） | 通过 |
| covers: t-37ba53 | 子卡·复核 | CHECK 拦非法值（真库事务回滚）+ 重跑幂等零写入 | 通过 |
| covers: t-3d3d60 | 子卡·测试 | dry-run 退出码 0 / 列在位 / drift 6 passed / 基线 67 passed | 通过 |

### t3 · ③ 退为薄转发 + 打桩点迁移

| 卡 | 类型 | 测试/核验 | 结果 |
|---|---|---|---|
| covers: t-d91b87 | 父卡 | `tests/test_daily_jobs_trading_day_gate.py`（28 条） | 通过 |
| covers: t-989aba | 子卡·研发 | 同上 28 条（含新增证伪断言） | 通过 |
| covers: t-b8b7c6 | 子卡·联调 | 调用方同源（`is` 判定为真）+ ③ 相关三套 57 passed | 通过 |
| covers: t-2d64a2 | 子卡·复核 | 壳内零实现（`TradingDayGuard` 仅 docstring）+ 证伪用例单跑 1 passed | 通过 |
| covers: t-6373a5 | 子卡·测试 | 28 passed + `__module__` = `application.services.trading_day_gate` + 基线 67 passed | 通过 |

### t4 · 仓储层：`complete_run_skipped` + 抽 `_finish_run`

| 卡 | 类型 | 测试/核验 | 结果 |
|---|---|---|---|
| covers: t-da502d | 父卡 | `tests/infrastructure/test_scheduler_run_skipped_ledger.py`（8 条） | 通过 |
| covers: t-13669a | 子卡·研发 | 同上 8 条（假会话语义 + 一次真库往返） | 通过 |
| covers: t-4b81fd | 子卡·联调 | `complete_run` 调用方清点 18 处零改造 + 75 passed | 通过 |
| covers: t-b8df8c | 子卡·复核 | `_finish_run` 唯一性（2 个调用点）+ 两态异常策略差异用例 | 通过 |
| covers: t-4006a7 | 子卡·测试 | 8 passed + 合并 75 passed 未降 | 通过 |

### t5 · 执行期接门与跳过落账（含 `manual` 旁路）

| 卡 | 类型 | 测试/核验 | 结果 |
|---|---|---|---|
| covers: t-42eb9a | 父卡 | `tests/infrastructure/test_scheduler_skip_ledger.py`（8 条） | 通过 |
| covers: t-49f017 | 子卡·研发 | 同上 8 条（N1 `_execute_command` 零调用、N2 零通知、N4 交易日不跳） | 通过 |
| covers: t-b88384 | 子卡·联调 | `notes/test_e2e_holiday_skip_probe.py`（真仓储+真门+真库）→ 1 passed | 通过 |
| covers: t-cddd7a | 子卡·复核 | 门在并发检查之前（grep 行号）+ 跳过路径零副作用核对 | 通过 |
| covers: t-0b6aaf | 子卡·测试 | 8 passed（含复核后补的 F5/F6 两条）+ 合并 83 passed | 通过 |

### t6 · 人工触发改投一次性 `manual=True` job

| 卡 | 类型 | 测试/核验 | 结果 |
|---|---|---|---|
| covers: t-3a7ebb | 父卡 | `tests/infrastructure/test_apscheduler_service.py`（13 条） | 通过 |
| covers: t-2bf7e5 | 子卡·研发 | 同上 13 条（排期不被扰动 + `manual` 参数为 True + 未知 task 抛 ValueError） | 通过 |
| covers: t-02dd78 | 子卡·联调 | 路由层 `git diff` 空 + `-k manual` 2 passed | 通过 |
| covers: t-badb26 | 子卡·复核 | 精确口径 `\.modify_job(` 生产调用点 0（首轮粗口径已自我更正） | 通过 |
| covers: t-2a9fe9 | 子卡·测试 | 13 passed + 合并 83 passed | 通过 |

### t7 · 巡检口径同步：`should_have_run` 与 watchdog

| 卡 | 类型 | 测试/核验 | 结果 |
|---|---|---|---|
| covers: t-54d79f | 父卡 | `tests/test_should_have_run.py`（31 条） | 通过 |
| covers: t-79a341 | 子卡·研发 | 同上 31 条（门跳过不算漏跑、更早跳过不洗白真漏跑、missed 仍告警、两套集合互斥） | 通过 |
| covers: t-7d47dd | 子卡·联调 | `tools/check_should_have_run.py` 生产只读实跑（11 启用 / 1 漏跑 / 10 豁免）+ 36 passed | 通过 |
| covers: t-98ed3c | 子卡·复核 | watchdog 只改 v2 那处（Agent OS 段原样）+ croniter 桩核验 | 通过 |
| covers: t-23d580 | 子卡·测试 | 36 passed（含 `test_health_probe.py`） | 通过 |

### t8 · 端到端验收、真实台账观察与回滚演练

| 卡 | 类型 | 测试/核验 | 结果 |
|---|---|---|---|
| covers: t-ea51f0 | 父卡 | 六条验收命令（21/8/28/37/13 + 台账查询）+ 生产 run 3381 `skipped` | 通过 |
| covers: t-173a83 | 子卡·研发 | 同上；生产重启后 11 条任务加载成功 | 通过 |
| covers: t-fde9be | 子卡·复核 | `notes/test_e2e_policy_toggle_probe.py`（回滚/免 reload 三步）→ 1 passed | 通过 |
| covers: t-cabaf9 | 子卡·测试 | 读数留档 `notes/acceptance-run.md` + `verification.md` | 通过 |

