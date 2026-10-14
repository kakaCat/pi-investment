# 测试证据（REQ-261004154902-a7cd）

> 全部命令均在 `quantsys-v2/` 下、用 `venv/bin/python` 执行；本文件记录**真实输出摘要**。
> 会话末统一打印 `notify-guard intercepted=0 egress=0 offenders=[]`（全程零真实外发）。

## 1. 分卡证据（开工基线 → 收尾实测）

| 卡 | 命令 | 结果 |
|---|---|---|
| t-c52a0a | `pytest tests/test_run_outcome.py -q` | **16 passed** |
| t-c52a0a | `pytest tests/test_failure_sink.py -q` | **6 passed** |
| t-b13aaf | `pytest tests/live_trading/test_daily_check_contract.py -q` | **9 passed** |
| t-da8070 | `pytest tests/test_trading_day_guard.py -q` | **47 passed** |
| t-0257b0 | `pytest tests/test_scheduler_misfire_semantics.py -q` | **22 passed** |
| t-141b38 | `pytest tests/services/test_pending_orders.py -q` | **28 passed** |
| t-322d78 | `pytest tests/test_job_failure_alerting.py -q` | **18 passed** |
| t-322d78 | `pytest tests/ -q -k "alerting or job_executor or scheduler or daily_jobs"` | **258 passed / 6 skipped** |
| t-0226ab | `pytest tests/test_notification_channel_fallback.py -q` | **13 passed** |
| t-979319 | `pytest tests/test_strategy_config_single_source.py -q` | **15 passed** |
| t-373c05 | `pytest tests/regression/test_strategy_config_refactor.py tests/test_v13_chain_wiring.py -q` | **25 passed** |
| t-ba8cc4 | `pytest tests/test_fake_green_gate.py tests/test_scheduled_jobs_account_value.py -q` | **9 passed** |
| t-900179 | `pytest tests/test_oversell_guard.py -q` | **25 passed** |
| t-5103ce | `pytest tests/test_should_have_run.py -q` | **26 passed** |

样例输出（末行）：

```
============================== 16 passed in 0.85s ==============================
============================== 25 passed in 0.98s ==============================
============================== 28 passed in 1.71s ==============================
```

## 2. 工具级验收（退出码 = 判据，不是「看输出顺眼」）

| 命令 | 退出码 | 含义 |
|---|---|---|
| `venv/bin/python tools/check_strategy_config_effective.py` | **0** | 声明 == 生效（持仓数 5 / 止损 -15% / 调仓 5 天） |
| `venv/bin/python tools/check_should_have_run.py` | **0** | 11 张启用任务五列对照表；无漏跑（含改动豁免 11） |
| `venv/bin/python tools/reconcile_sim_account.py --account v13_simulation` | **0** | 账本自洽（已排除 4 只已登记脏数据；现金重放差 ¥-0.01） |
| `venv/bin/python tools/check_v13_chain_health.py` | **0** | 三张表均有真实行、无待办 |
| `venv/bin/python tools/check_fake_green_tests.py --new-only` | **0** | 命中 37 / 基线 37 / 新增 0 |

**反向验证（判据真的会红）**：

- 对账器把脏清单指向不存在的位置 → 同样数据立刻退 **2**（`test_without_dirty_manifest_oversold_is_inconsistent`）。
- 假绿灯扫描工具对新增的 `def test_x(): return True` 会命中所属文件并退 **2**（`tests/test_fake_green_gate.py` 内含合成样本自检）。
- 检查器在声明源缺受检键时退 **3**（无法判定不许假装通过）。
- 自检器自身出错时退 **3**：实测踩过一次（SQL 分组表达式写错），它响亮报错而不是静默通过。

## 3. 全量回归

```
venv/bin/python -m pytest tests/ -q --ignore=tests/e2e
→ 6257 passed, 164 skipped, 2 xfailed, 10 xpassed, 1 failed, 3 errors in 225.74s
```

- **唯一 failed**：`tests/test_layer_purity.py::test_total_layer_violations_do_not_increase`
  （319 > 基线 318）。逐文件 AST 比对证明**本需求新增违规 0 处**，唯一变化的违规文件是
  未跟踪的 `application/services/trading_day_resolver.py`（另一需求当天新建）。基线未调。
- **3 errors**：`tests/daemon/test_daemon_integration.py`（缺可执行文件）——**开工前既有**，与本次无关。
- 开工基线为 6123 passed / 1 failed（同一分层条）/ 3 errors → 收尾 6257 passed，净增 134 条通过。

## 4. 真实数据侧核对（只读）

```sql
select id, name, is_enabled, cron_expression, misfire_grace_time_seconds
from quant.scheduler_tasks where id in (249,232,242);
-- 249 v13-simulation-trading  true  30 14 * * 1-5   NULL   ← 止血已恢复（本地 14:30，唤醒必补跑）
-- 232 每日数据质量检查          true  0 0 * * *       300
-- 242 每日信号执行             true  30 15 * * 1-5   300
select count(*) from public.apscheduler_jobs;   -- 11（与 11 张启用任务一致）
```

```sql
-- v13_simulation 账本矛盾（t11/t12 的取证与处置对象）
-- 300045 买 1000 / 卖 2000 ；300561 买 700 / 卖 1400
-- 300765 买 300  / 卖 600  ；300469 买 200 / 卖 400
-- 虚增卖出收入合计 ¥49,424.96（首次越界日 2026-08-21）
```

## 5. 备底

- `notes/code-changes-2026-10-04.patch`：37 文件 / 5773 行，`git apply --check --reverse` 通过（与工作树一致）。
- `notes/code-snapshot-2026-10-04.tar.gz`：222 项（改动文件 + 需求目录）。
- ⚠️ 仓库存在**卡住的未合并状态**（`.env` 与 3 个 agent-ts 文件），全程未执行任何 git 写操作。

## 6. 任务覆盖矩阵（covers）

> 门禁要求逐卡可查：父卡给出该卡的主证据，子卡沿用同一证据链（子卡是同一改动的阶段分工，
> 不各自另造证据）。全部命令均为本会话实测。

### t-c52a0a — pytest tests/test_run_outcome.py tests/test_failure_sink.py -q → 22 passed（结果契约 + 失败出口）

covers: t-c52a0a
covers: t-8133a0
covers: t-934549
covers: t-a6d274
covers: t-d6131f

### t-b13aaf — pytest tests/live_trading/test_daily_check_contract.py tests/test_v13_scheduler.py -q → 16 passed（日检三态 + 调度接线）

covers: t-b13aaf
covers: t-cb5d73
covers: t-a3ff51
covers: t-158ded
covers: t-8818ca

### t-da8070 — pytest tests/test_trading_day_guard.py tests/test_trading_day_resolver.py tests/live_trading/test_trading_day_judge.py -q → 72 passed（含四日期证伪点）

covers: t-da8070
covers: t-9630b6
covers: t-d64276
covers: t-82451b
covers: t-e8a6f4

### t-141b38 — pytest tests/services/test_pending_orders.py -q → 28 passed（单笔隔离 / 盘后跳过 / 超期作废）

covers: t-141b38
covers: t-672692
covers: t-6d84c3
covers: t-e99312
covers: t-de30a7

### t-0257b0 — pytest tests/test_scheduler_misfire_semantics.py -q → 22 passed（宽限语义 + 被跳过落库）

covers: t-0257b0
covers: t-20173e
covers: t-a9ba88
covers: t-318de0
covers: t-f6f85a

### t-322d78 — pytest tests/test_job_failure_alerting.py -q → 18 passed；另 pytest tests/ -k「alerting or job_executor or scheduler or daily_jobs」→ 258 passed

covers: t-322d78
covers: t-5a96d9
covers: t-54368b
covers: t-c34956
covers: t-67b43e

### t-5103ce — pytest tests/test_should_have_run.py -q → 26 passed；venv/bin/python tools/check_should_have_run.py → 退出码 0

covers: t-5103ce
covers: t-d935df
covers: t-2e7e2e
covers: t-7b82d0
covers: t-681cce

### t-0226ab — pytest tests/test_notification_channel_fallback.py -q → 13 passed（调仓/风控候选渠道含飞书）

covers: t-0226ab
covers: t-53a7f9
covers: t-1996fe
covers: t-645f92
covers: t-fa9784

### t-979319 — pytest tests/test_strategy_config_single_source.py -q → 15 passed；venv/bin/python tools/check_strategy_config_effective.py → 退出码 0

covers: t-979319
covers: t-2182ea
covers: t-d0e730
covers: t-0959dc
covers: t-6625c7

### t-373c05 — pytest tests/regression/test_strategy_config_refactor.py tests/test_v13_chain_wiring.py -q → 25 passed

covers: t-373c05
covers: t-f4a836
covers: t-7766ec
covers: t-ef72d4
covers: t-e03b96

### t-900179 — pytest tests/test_oversell_guard.py -q → 25 passed；venv/bin/python tools/reconcile_sim_account.py --account v13_simulation → 退出码 0

covers: t-900179
covers: t-61dd14
covers: t-0bd4f5
covers: t-96f359
covers: t-f2ca16

### t-174c1d — tests/test_oversell_guard.py::test_without_dirty_manifest_oversold_is_inconsistent（反证：清单不在即判不自洽）+ docs/requirements/REQ-261004154902-a7cd/notes/legacy-cash-disposition.md

covers: t-174c1d
covers: t-32c86e
covers: t-fe5f36
covers: t-94fe6d

### t-ba8cc4 — pytest tests/test_fake_green_gate.py tests/test_scheduled_jobs_account_value.py -q → 9 passed；venv/bin/python tools/check_fake_green_tests.py --new-only → 退出码 0

covers: t-ba8cc4
covers: t-02fc85
covers: t-5805e1
covers: t-8259cd

### t-ad58a1 — venv/bin/python tools/check_v13_chain_health.py → 退出码 0（三张表均有真实行）+ docs/requirements/REQ-261004154902-a7cd/tests/test-evidence.md

covers: t-ad58a1
covers: t-565bb2
covers: t-c4a54f
covers: t-ef5ca7
