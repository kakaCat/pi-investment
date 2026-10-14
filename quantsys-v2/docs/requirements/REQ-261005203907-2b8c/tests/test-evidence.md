# 测试证据（REQ-261005203907-2b8c）

> 全部输出为**提交验收前的当次运行**逐字粘贴（本仓纪律：不以自述代替证据）。
> 覆盖对照：[`../design/test-cases.md`](../design/test-cases.md) 的 TC-1~TC-6。

## 1. 汇总（一条命令跑齐五文件）

```console
$ ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py \
    tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py \
    tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q
======================== 70 passed, 1 warning in 2.08s =========================
notify-guard intercepted=0 egress=0 offenders=[]
```

## 2. 分文件（含卡归属）

| 文件 | 用例数 | 命令 | 结果 | 覆盖 |
|---|---|---|---|---|
| `tests/test_daily_jobs_trading_day_gate.py` | 27 | `pytest … -q` | **27 passed** | TC-1 真值表 13（t-dd0d4d）+ TC-2/TC-3 宿主接线 8（t-075116）+ TC-5 兼容判据 6（t-dbb9d0） |
| `tests/test_evening_pipeline_holiday_gate.py` | 6 | `pytest … -q` | **6 passed** | TC-4 六行真值表（t-588729） |
| `tests/test_daily_jobs_bootstrap.py` | — | `pytest … -q` | 全过 | `is_due` / `catchup_due` 既有语义不回归 |
| `tests/test_false_success_guard.py` | — | `pytest … -q` | 全过 | 假成功判定与通知打桩纪律不回归 |
| `tests/test_pool_refresh_daily.py` | — | `pytest … -q` | 全过 | 池刷新任务本体不回归 |

## 3. TC 逐条对照（验收标准 → 证据）

| TC | 判据 | 证据（用例名 / 命令） | 结果 |
|---|---|---|---|
| TC-1 | 休市日 10-05/06/07 跳过；交易日 09-30/10-08 照跑；周末跳过；`degraded=True` 照跑；判定器异常照跑；注解五键 | `test_holiday_truth_skips` / `test_trading_day_truth_runs` / `test_weekend_truth_skips` / `test_degraded_runs_fail_open` / `test_gate_error_runs` / `test_returns_annotation_shape` | ✅ |
| TC-2 | 跳过写 `skipped` 且 `_send_feishu` 零调用；handler 未执行；duration 未观测；降级路径补注解 + warning | `test_skip_writes_skipped_row_and_no_notify` / `test_skip_does_not_observe_duration` / `test_unflagged_job_ignores_gate` / `test_degraded_run_annotates_result_and_warns` | ✅ |
| TC-3 | 注册表里带门任务**恰好** 3 个；其余 6 个默认 False | `test_registry_flags_exactly_three` / `test_evening_pipeline_not_flagged` / `test_other_jobs_unflagged` | ✅ |
| TC-4 | 六行真值表（含交易日绝不跳因子、error 先算后抛） | `test_holiday_fresh_kline_skips_factor` / `test_holiday_repaired_kline_runs_factor` / `test_holiday_zero_success_skips_factor` / `test_holiday_kline_error_still_computes_then_raises` / `test_trading_day_never_skips_factor` / `test_result_passes_failure_classifier` | ✅ |
| TC-5 | `skipped` 对既有消费者行为不变（`is_due` / `catchup_due` / `trigger_job` / 失败判定） | `TestSkippedRowCompatibility` 6 条 | ✅ |
| TC-6 | 真实休市日 / 复市首日台账观察 | **窗口未到**：见 [`../notes/holiday-observation.md`](../notes/holiday-observation.md) §3（含复跑命令与重启前提） | ⏳ 待观察 |

## 4. 静态检查

```console
$ ./venv/bin/python tools/check_undefined_names.py | grep -E "daily_jobs/(gate|runtime|registry|pipeline)\.py|test_daily_jobs_trading_day_gate|test_evening_pipeline"
（无输出 → 0 命中）

$ ./venv/bin/python tools/analyze_layer_violations.py | grep -E "daily_jobs/(gate|runtime|registry|pipeline)\.py"
（无输出 → 0 违规；inbound → application 方向只许向内）

$ ./venv/bin/python -m py_compile adapters/inbound/fastapi_app/daily_jobs/gate.py \
    adapters/inbound/fastapi_app/daily_jobs/defs.py
py_compile OK
```

> 注：`ruff` 未安装于本仓 venv（`No module named ruff`），故 linter 未跑，如实标注。

## 5. 通知零外发

各次运行末尾均打印 `notify-guard intercepted=0 egress=0 offenders=[]`
（根 `conftest.py` 的通知守卫处于 `fail` 模式；跳过路径的断言之一就是「一条通知都不许发」）。

## 6. 未覆盖（如实登记，不当作已验）

1. **真实休市日观察（TC-6）**：10-06 / 10-07 / 10-08 窗口未到；且需先重启宿主（见 §3 前置）。
2. **fail-open 的真实故障场景**：仅单元验证（假判定器），未在真实日历源故障下实测。
3. **既有 order-dependent 失败**：`tests/test_daily_jobs_notify_truthfulness.py::TestIdleStreak::test_streak_query_failure_degrades_loudly`
   在宽选择集下失败、单跑通过；与本需求无关（失败点在本需求代码之前），未修（属他人范围）。

## 7. 任务覆盖（covers）

> 每个任务卡（含子卡）对应的测试证据；父卡与子卡共用同一批用例，按阶段侧重标注。

| 任务 | 角色 | 测试证据 | 结果 |
|---|---|---|---|
| covers: t-dd0d4d | 父卡·门模块与 JobDef 字段 | `tests/test_daily_jobs_trading_day_gate.py::TestTruthTable` / `TestFailOpen` / `TestJobDefField`（13 条） | 通过 |
| covers: t-c8a4bc | 子卡·研发 | 同上 13 条 | 通过 |
| covers: t-5d3b29 | 子卡·复核 | 读码对照 + 静态检查（`check_undefined_names` / `analyze_layer_violations` 0 命中） | 通过 |
| covers: t-36bf41 | 子卡·测试 | `pytest tests/test_daily_jobs_trading_day_gate.py -q` → 13 passed（当卡时点） | 通过 |
| covers: t-075116 | 父卡·宿主接线 | `TestRunJobSkip` / `TestRunJobDegraded` / `TestRegistryScope`（8 条） | 通过 |
| covers: t-074a02 | 子卡·研发 | 同上 8 条（含 `_send_feishu` 零调用断言） | 通过 |
| covers: t-935496 | 子卡·复核 | 读码核对早退点位置与指标契约 | 通过 |
| covers: t-bdfaae | 子卡·测试 | `pytest tests/test_daily_jobs_trading_day_gate.py -q` → 21 passed（当卡时点） | 通过 |
| covers: t-588729 | 父卡·晚间管线因子段 | `tests/test_evening_pipeline_holiday_gate.py`（6 条） | 通过 |
| covers: t-e11789 | 子卡·研发 | 同上 6 条（含交易日绝不跳因子的回归锁） | 通过 |
| covers: t-c7f120 | 子卡·复核 | `git diff` 核对 K 线段 0 条增删 + 静态检查 | 通过 |
| covers: t-4dec18 | 子卡·测试 | `pytest tests/test_evening_pipeline_holiday_gate.py -q` → 6 passed；回归三文件 36 passed | 通过 |
| covers: t-dbb9d0 | 父卡·兼容与回滚核验 | `TestSkippedRowCompatibility`（6 条）+ `notes/compat-rollback.md` | 通过 |
| covers: t-434c63 | 子卡·研发 | 同上 6 条 + 零 DDL 三处交叉核验 | 通过 |
| covers: t-e199f4 | 子卡·复核 | 兼容矩阵 7 行逐行核对（4 行断言 / 3 行读码说明） | 通过 |
| covers: t-0c1cf7 | 子卡·测试 | `pytest tests/test_daily_jobs_bootstrap.py tests/test_pool_refresh_daily.py -q` → 20 passed | 通过 |
| covers: t-6384c0 | 父卡·回归与真实观察 | §1 汇总 70 passed + `notes/holiday-observation.md`（基线实测；观察窗口待） | 部分（窗口未到） |
| covers: t-d78651 | 子卡·研发 | §1 三条命令全过 | 通过 |
| covers: t-d9d825 | 子卡·复核 | 观察记录证据分级逐节核对 | 通过 |
| covers: t-bc7a9b | 子卡·测试 | 四条验收复跑与记录一致（27 / 6 / 37 passed + 台账） | 通过 |

**覆盖度口径说明**：`t-6384c0` 的 TC-6 真实观察部分为**待观察**（10-06/10-07/10-08 窗口未到，
且需先重启宿主），其余 19 张卡均有当次可复跑的通过证据。
