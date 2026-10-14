---
req_id: REQ-261005210015-1603
title: FR-1~FR-7 逐条可跑用例、打桩点与真实观察
doc: design/test-cases
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7
---

# 测试用例（REQ-261005210015-1603）

## 打桩点铁律（先写这里，因为它最容易再次踩）（serves: FR-1, FR-2, FR-3, FR-6）

`runtime.py` 用 `from ...alerting import _send_feishu, _summarize_result` 取值导入
（[runtime.py:19](adapters/inbound/fastapi_app/daily_jobs/runtime.py#L19)）——**它读的是自己模块的全局名**。
所以：

- ✅ 打桩必须打在 **`adapters.inbound.fastapi_app.daily_jobs.runtime`**（`monkeypatch.setattr(runtime, '_send_feishu', recorder)`）；
- ❌ 打在 `alerting._send_feishu` 或转发壳 `daily_jobs_bootstrap._send_feishu` 上——**名字存在但不生效**，
  真函数照发（这正是 REQ-261003150739-b98d 用 4 张假卡换来的教训）。
- 跑测试时 `tests/notify_guard.py` 默认 `fail`：任何未声明的真实外发会让用例变红——用它当兜底。

## 新增文件 `tests/test_daily_jobs_notify_truthfulness.py`（serves: FR-1, FR-2, FR-3, FR-5, FR-6）

| 用例 | 断言 | FR |
|---|---|---|
| `test_format_elapsed_seconds_below_minute` | `_format_elapsed(1.21) == '1.2 秒'`；`59.96 → '60.0 秒'`；`-1 → '0.0 秒'` | FR-1 |
| `test_format_elapsed_minutes_above_minute` | `60.0 → '1.0 分钟'`；`125.0 → '2.1 分钟'` | FR-1 |
| `test_summary_shows_state_distribution` | 以 **2026-10-05 的真实 result**（`computed_ok=0/insufficient_sample=2/no_trades=3/data_gap=0`）渲染 → 含 `有效 0`、`样本不足 2`、`无成交 3`、`数据缺口 0`；**不含** `detail[computed=` | FR-2 |
| `test_zero_output_uses_warning_title` | `no_output=True` → `_run_job` 发出的文本首行 == `⚠️ 每日任务完成（无有效产出）：evolution_fitness` | FR-3 |
| `test_nonzero_output_keeps_success_title` | `no_output=False`（或键缺失）→ 首行 == `✅ 每日任务完成：evolution_fitness` | FR-3 |
| `test_idle_streak_phrase_when_two_zero_windows` | `idle_streak=2` + `computed_ok=0` + `last_ok='2026-09-12'` → 含 `已连续 2 次无有效产出（最近有效：2026-09-12）` | FR-5 |
| `test_no_streak_phrase_when_output_exists` | `computed_ok=3` → **不含** `无有效产出`、**不含** `连续` | FR-5 |
| `test_streak_capped_renders_ge_k` | 最近 20 条全 0 → 含 `已连续 ≥20 次无有效产出` | FR-5 |
| `test_streak_query_failure_degrades_loudly` | 仓储方法抛错 → 文案含 `空转统计不可用`，`caplog` 有 error，**且 `_mark_done` 收到 `status='success'`** | FR-5、FR-6 |
| `test_new_result_shape_not_judged_failed` | `find_result_failure(契约 B 的 result) is None`（锁 `_noop_gap_failure` / `classify_job_result` 不变式） | FR-6 |
| `test_mark_done_status_stays_success` | 零产出运行后 `_mark_done(job, date, 'success', result=…)` 被调用且参数 `status='success'` | FR-6 |
| `test_other_job_summary_unchanged` | 以 `evening_pipeline` 形态的 result（无 `summary`）渲染 → 与**改造前实现**的输出逐字一致（同测试内保留旧逻辑快照做对照） | FR-2、FR-7 |

`_run_job` 类用例的写法：`monkeypatch.setattr(runtime, '_send_feishu', recorder)` +
`monkeypatch.setattr(runtime, '_mark_running', ...)` / `runtime._mark_done` 桩，
`job = JobDef('evolution_fitness', dtime(20,35), (0,1,2,3,4), lambda: <契约 B 的 result>, desc)`
（参照 `tests/test_false_success_guard.py` 的既有写法，勿新造范式）。

## 增补 `tests/services/evolution/test_evolution_fitness_service.py`（serves: FR-4）

| 用例 | 断言 | FR |
|---|---|---|
| `test_state_counts_sum_to_accounts_total` | `computed_ok + insufficient_sample + no_trades + data_gap + other == accounts_total`（4 个账户造 1 ok / 1 no_trades / 1 insufficient / 1 data_gap） | FR-4 |
| `test_no_null_row_counted_as_ok` | 返回 `status='data_gap'` / `no_trades` 的账户**不计入** `computed_ok` | FR-4 |
| `test_skipped_key_removed` | 返回体**不含** `skipped` 键 | FR-4 |
| `test_computed_key_kept_for_compat` | `result['computed'] == result['accounts_total']`（e2e `assert result['computed'] >= 1` 依赖它） | FR-4 |
| `test_aligned_days_reported` | 构造 10 个对齐日 → `aligned_days == 10` | FR-4 |

（既有 `_make_service` 的 Mock 注入范式直接复用；新增的只读仓储方法在 Mock 上返回可迭代空值 → 不影响既有断言。）

## 增补 `tests/repositories/test_evolution_fitness_repository.py`（serves: FR-5）

| 用例 | 断言 | FR |
|---|---|---|
| `test_list_recent_window_ok_counts_orders_desc_and_counts_ok` | 插 3 个 `window_end`（ok 数 2/0/1）→ 返回倒序 `[(最新,2),(中,0),(最旧,1)]` | FR-5 |
| `test_get_last_ok_window_end_ignores_non_ok` | 最新一条是 `insufficient_sample`、次新是 `ok` → 返回次新的 `window_end`；全非 ok → `None` | FR-5 |

## 判定标准（逐条命令）（serves: FR-7）

```bash
# FR-1 / FR-2 / FR-3 / FR-6（含打桩点与不变式）
./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py -q

# FR-4
./venv/bin/python -m pytest tests/services/evolution/test_evolution_fitness_service.py -q

# FR-5（只读口径）
./venv/bin/python -m pytest tests/repositories/test_evolution_fitness_repository.py -q

# FR-7 回归（既有行为不得破）
./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py -q
./venv/bin/python -m pytest tests/e2e/test_evolution_pipeline.py -q     # result['computed'] >= 1 仍成立
```

**真实观察（FR-7 第 3 条）**：下一次 `evolution_fitness` 运行后核对

```bash
psql -d quant_investment -c "select result->>'summary', result->>'no_output' \
  from quant.inprocess_job_runs where job_id='evolution_fitness' order by started_at desc limit 1;"
grep -n "飞书发送成功\|evolution_fitness" logs/api.log | tail -5   # 确认卡片发的是新文案
```

- 期望 `no_output = true`、`summary` 含 `有效 0` 与 `已连续 N 次无有效产出（最近有效：2026-09-12）`；
- 若当天被 REQ-261005203907-2b8c 的交易日门判 `skipped`（休市日 10-06/10-07 可能如此）：
  **改核对其 `skipped` 行 + 当天无该任务通知**，并在验收材料里写明"观察窗口被门改变"，
  **不得**把该情形记作未完成。

## 覆盖矩阵（FR → 用例）（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）

| FR | 主用例 | 兜底 |
|---|---|---|
| FR-1 | `test_format_elapsed_*`（2 条） | UC-1/UC-3 文本断言 |
| FR-2 | `test_summary_shows_state_distribution` | `test_other_job_summary_unchanged` |
| FR-3 | `test_zero_output_uses_warning_title` / `test_nonzero_output_keeps_success_title` | UC-1/UC-2/UC-3 |
| FR-4 | 服务层 5 条 | 契约 C 不变式 |
| FR-5 | `test_idle_streak_*` / `test_streak_capped_*` / 仓储 2 条 | UC-4 降级 |
| FR-6 | `test_new_result_shape_not_judged_failed` / `test_mark_done_status_stays_success` | 真实台账核对（仍 success） |
| FR-7 | 上述 4 条 pytest 命令 + 真实观察脚本 | 覆盖矩阵本身 |
