# 拆分计划（REQ-261005210015-1603）

**上游**：design/[architecture.md](design/architecture.md)（落点、结果约定、两处陷阱）·
[interfaces.md](design/interfaces.md)（三份契约 + `_summarize_result` 行为矩阵）·
[data-model.md](design/data-model.md)（只读查询口径，不改 DDL）·
[use-cases.md](design/use-cases.md)（五场景卡片样例）·
[test-cases.md](design/test-cases.md)（用例清单 + 打桩点铁律）

**目标**：让 `evolution_fitness` 的完成通知**说真话**——耗时量级可读、摘要带状态分布、
零有效产出改 `⚠️`（台账仍 `success`）、`computed` 拆成诚实计数、空转连续次数可见。

## TL;DR

```
  3 张无依赖卡 → 汇成 handler → runtime 接线 → 测试/回归

  t1 alerting 契约落地 ┐
  t2 service 诚实计数  ├─▶ t4 handler 组装 ─┐
  t3 repo 只读查询     ┘                     ├─▶ t6 通知层用例 ┐
                         t5 runtime 接线 ────┘                 ├─▶ t8 回归+真实观察
                         t7 数据层用例 ◀── t2,t3 ──────────────┘

  ★ 汇合点 t6 必须在 t4/t5 之后：它断言的是"整条消息长什么样"
  ★ 打桩点铁律：桩打在 runtime 模块（打在 alerting 会静默失效，见 test-cases.md）
```

## 改动盘点（对照设计文档）

| 类别 | 内容 | 规模 | 归属卡 |
|---|---|---|---|
| **新增** | `alerting._format_elapsed()` | ~8 行 | t1 |
| **修改** | `alerting._summarize_result()`：顶层 `summary` 优先 + 白名单补 5 键 | ~12 行 | t1 |
| **修改** | `evolution_fitness_service.compute_all_accounts()`：四类计数 + `accounts_total` + `aligned_days`；删 `skipped`；`computed` 语义收窄 | ~25 行 | t2 |
| **修改** | `daily_orchestrator.py` 复核阶段日志行补 `computed_ok` | 1 行 | t2 |
| **新增** | `EvolutionFitnessORMRepository.list_recent_window_ok_counts()` / `get_last_ok_window_end()`（只读） | ~25 行 | t3 |
| **修改** | `pipeline._job_evolution_fitness()`：组装 `summary` / `no_output` / 空转统计（含纯函数 `_derive_idle_streak`、查询失败降级） | ~45 行 | t4 |
| **修改** | `runtime._run_job()`：耗时改调 `_format_elapsed`；标题语气三元式 | 3 行 | t5 |
| **新增** | `tests/test_daily_jobs_notify_truthfulness.py` | 1 文件 / 12 用例 | t6 |
| **修改** | `tests/services/evolution/test_evolution_fitness_service.py`、`tests/repositories/test_evolution_fitness_repository.py` | 2 文件 / 7 用例 | t7 |
| **删除** | `compute_all_accounts()` 返回值里的 `skipped` 键（写死 0、零消费方） | 1 键 | t2 |
| **无改动** | `is_due` / `JobDef` / `registry.py`（归 REQ-261005203907-2b8c）、`find_result_failure` 本体、`_send_feishu`、`_mark_done` 语义、表结构 | 0 | — |

## 需求条款覆盖对照表

| 条款 | 内容 | 接收任务 |
|---|---|---|
| FR-1 | 耗时反映真实量级 | t1（格式化器）· t5（接线）· t6（用例） |
| FR-2 | 摘要含状态分布、不是内部字段 dump | t1（summary 优先）· t4（组装）· t6 |
| FR-3 | 零有效产出不报 ✅ | t4（`no_output`）· t5（语气）· t6 |
| FR-4 | 计数语义诚实 | t2 · t7 |
| FR-5 | 空转跨天可见 | t3（读数）· t4（组装 + 降级）· t6 · t7 |
| FR-6 | 台账与重试语义不动 | t5（不碰 status）· t6（`find_result_failure` 不变式 + `_mark_done` 断言） |
| FR-7 | 回归锁与真实观察 | t6 · t7 · t8 |

**无"本轮不做"条款**：FR-1…FR-7 全部有接收任务。

## 迁移与兼容（为什么没有单独的迁移卡）

本需求**无 DDL、无数据回填、无对外 HTTP 契约变化**——这是设计阶段定死的（`data-model.md`「结论先行」）。
兼容面只有三处，且都落在已有卡的验收里，因此**有意不设独立迁移卡**（不是遗漏）：

1. **旧调用方**：`daily_orchestrator.py:669` 读 `.get('computed', 0)`、`tests/e2e/test_evolution_pipeline.py:160`
   断言 `result['computed'] >= 1` → 由 **t2 保留 `computed`（= `accounts_total`）** 承接，t2 的验收含
   `result['computed'] == result['accounts_total']` 与 e2e 用例继续通过。
2. **旧 result 形态**（历史行没有 `summary`）：`_summarize_result` 只在 `summary` 非空时才替换子字典段
   → 由 **t1** 承接，验收含"以 `evening_pipeline` 形态渲染与改造前逐字一致"。
3. **回滚**：无 schema 变更 → `git revert` 即回到现状；新键消失后消费方自动回落（t8 做一次回滚演练）。

## 任务表

| key | title | phase | side | depends_on | footprint(f/a/c) | DU |
|---|---|---|---|---|---|---|
| t1 | 通知层契约落地：`_format_elapsed` + `_summarize_result` 支持顶层 `summary` | implement | backend | — | 1 / 4 / 700 | 3.35 |
| t2 | fitness 服务诚实计数：四类状态 + `accounts_total`，删 `skipped`、收窄 `computed` 语义 | implement | backend | — | 2 / 4 / 700 | 4.35 |
| t3 | 空转读数：`EvolutionFitnessORMRepository` 两个只读聚合方法 | implement | backend | — | 1 / 2 / 500 | 2.25 |
| t4 | handler 组装：`summary` / `no_output` / 空转统计（含纯函数与查询失败降级） | implement | backend | t1, t2, t3 | 1 / 5 / 900 | 3.95 |
| t5 | runtime 接线：耗时按量级显示 + 零产出改 ⚠️（不动 status、不碰跳过分支） | implement | backend | t1 | 1 / 4 / 500 | 3.25 |
| t6 | 新增通知层用例（12 条：格式/摘要/语气/空转/降级/失败判定不变式/其他任务逐字不变） | test | backend | t4, t5 | 1 / 12 / 1500 | 7.75 |
| t7 | 数据层用例：计数不变式、无 `skipped`、`computed` 兼容、只读聚合口径 | test | backend | t2, t3 | 2 / 7 / 900 | 5.95 |
| t8 | 回归四连 + 兼容核对 + 真实观察取证（含回滚演练） | test | backend | t6, t7 | 7 / 5 / 600 | 9.80 |

**容量**：单卡上限 16 DU，最大一张 t8 = 9.80 DU（回归命令点到 6 个路径，故 `files=7` 留余量），**无超容量卡**（无需 ⚠️ 标记）。

### 逐卡 implementation / acceptance

**t1 · 通知层契约落地**（FR-1、FR-2）
- implementation：`alerting.py` 新增 `_format_elapsed(seconds) -> str`（`<60s → f"{s:.1f} 秒"`，否则
  `f"{s/60:.1f} 分钟"`，负数按 0）；改 `_summarize_result`：`result.get('summary')` 为非空 str 时以其为首段
  且**不再**输出子字典 `key[...]` 段，否则逐字保持现有行为；白名单补
  `computed_ok / insufficient_sample / no_trades / data_gap / no_output`。
- acceptance：`./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs.alerting import _format_elapsed as f; assert f(1.21)=='1.2 秒' and f(59.96)=='60.0 秒' and f(60.0)=='1.0 分钟' and f(125.0)=='2.1 分钟' and f(-1)=='0.0 秒'"` 退出码 0；
  且 `_summarize_result({'kline_sync': {'status':'success','updated':3}})` 的输出与改造前快照逐字相同。

**t2 · fitness 服务诚实计数**（FR-4）
- implementation：`evolution_fitness_service.compute_all_accounts()` 按 `result['status']` 累加
  `computed_ok / insufficient_sample / no_trades / data_gap / other`（`data_gap` 走服务侧无对齐日期分支），
  返回体加 `accounts_total`、`aligned_days`；**删除 `skipped`**；`computed` 保留 = `accounts_total`
  并在 docstring 写明"遍历到的账户数，不是有效条数"；`daily_orchestrator.py` 复核阶段日志行补 `computed_ok`。
- acceptance：`./venv/bin/python -m pytest tests/services/evolution/test_evolution_fitness_service.py -q` 全过，
  且新增断言 `computed_ok+insufficient_sample+no_trades+data_gap+other == accounts_total`、
  `'skipped' not in result`、`result['computed'] == result['accounts_total']`。

**t3 · 空转读数（只读）**（FR-5）
- implementation：`EvolutionFitnessORMRepository` 新增
  `list_recent_window_ok_counts(limit=20, window_days=20) -> List[Tuple[date,int]]`（`group_by(window_end)` +
  `count(case((status=='ok',1)))`，倒序）与 `get_last_ok_window_end(window_days=20) -> Optional[date]`
  （`max(window_end) where status='ok'`）；均**只读**、不写库、不加列。
- acceptance：`./venv/bin/python -m pytest tests/repositories/test_evolution_fitness_repository.py -q` 全过；
  新增断言：插 3 个 `window_end`（ok 数 2/0/1）→ 返回顺序与计数正确；最新为 `insufficient_sample`、
  次新为 `ok` → `get_last_ok_window_end()` 返回次新；全非 ok → `None`。

**t4 · handler 组装**（FR-2、FR-3、FR-5）
- implementation：`pipeline._job_evolution_fitness()` 用 t3 的两次查询算出 `idle_streak`（纯函数
  `_derive_idle_streak(counts_desc) -> (int, bool)`，截断标志）与 `last_ok_window_end`；
  按 `interfaces.md` 契约 A 拼 `summary`；`no_output = (computed_ok == 0)`；
  **两次查询任一抛错 → `logger.error` + `summary` 追加"空转统计不可用" + 任务仍成功**（不得外抛）。
- acceptance：`./venv/bin/python -c` 直接调 `_job_evolution_fitness` 的降级路径（monkeypatch 仓储抛错）→
  返回体含 `'空转统计不可用'` 且无异常；正常路径返回体 `summary` 含
  `有效 0（样本不足 2 / 无成交 3 / 数据缺口 0）` 与 `已连续 2 次无有效产出（最近有效：2026-09-12）`
  （用生产真实计数构造）。

**t5 · runtime 接线**（FR-1、FR-3、FR-6）
- implementation：`runtime._run_job()` 成功分支：`elapsed` 改经 `_format_elapsed` 渲染；
  标题前缀改 `"⚠️ 每日任务完成（无有效产出）：" if result.get('no_output') is True else "✅ 每日任务完成："`；
  **不改** `_mark_done` 的 `status`、**不改** `find_result_failure` 调用、**不碰**任何跳过分支
  （REQ-261005203907-2b8c 的地盘）。
- acceptance：`./venv/bin/python -m pytest tests/test_false_success_guard.py -q` 全过（既有断言不破）；
  且新增用例断言 `no_output=True` 时首行为 ⚠️ 文案、`no_output` 缺失时为 ✅。

**t6 · 通知层用例**（FR-1、FR-2、FR-3、FR-5、FR-6）
- implementation：新增 `tests/test_daily_jobs_notify_truthfulness.py`，按 `test-cases.md` 的 12 条写；
  **桩打在 `runtime` 模块**（`monkeypatch.setattr(runtime, '_send_feishu', recorder)`），
  `_mark_running` / `_mark_done` 同样打在 runtime；用例数据用生产真实计数形态。
- acceptance：`./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py -q` → 12 passed；
  其中 `find_result_failure(<契约 B 的 result>) is None` 与 `_mark_done(...status='success')` 两条必须存在。

**t7 · 数据层用例**（FR-4、FR-5）
- implementation：增补 `tests/services/evolution/test_evolution_fitness_service.py`（5 条）与
  `tests/repositories/test_evolution_fitness_repository.py`（2 条），复用既有 Mock 注入范式。
- acceptance：`./venv/bin/python -m pytest tests/services/evolution/test_evolution_fitness_service.py tests/repositories/test_evolution_fitness_repository.py -q` 全过（新增 ≥7 条，既有断言不破）。

**t8 · 回归 + 真实观察**（FR-7）
- implementation：跑 4 条回归命令；在下一次 `evolution_fitness` 运行后核对
  `quant.inprocess_job_runs.result` 的 `summary` / `no_output` 与 `logs/api.log` 的飞书发送行；
  做一次回滚演练（`git stash` 或 revert 后确认文本回落）；把结论写进
  `docs/requirements/REQ-261005210015-1603/notes/observation.md`。
  若当天被 2b8c 的交易日门判 `skipped` → 改核对其 `skipped` 行 + 当天无该任务通知，并写明"观察窗口被门改变"。
- acceptance：上述 4 条 pytest 命令全过（含 `tests/e2e/test_evolution_pipeline.py`）；
  `notes/observation.md` 内含至少 1 条**真实**台账证据（`result->>'summary'` 原文）与回滚演练结论。

## 依赖与批次

| 批次 | 卡 | 说明 |
|---|---|---|
| 1 | t1、t2、t3 | 互不依赖（不同文件），可并行 |
| 2 | t4（→t1,t2,t3）、t5（→t1）、t7（→t2,t3） | t4 要三张卡的产物齐了才组装 |
| 3 | t6（→t4,t5） | 断言"整条消息"，必须等接线完成 |
| 4 | t8（→t6,t7） | 回归与真实观察是收口 |

**无前向引用**：`depends_on` 一律指向本表更靠前的 key。

## 边界（本阶段不做什么）

- 不做交易日门 / 休市日跳过（`is_due` / `JobDef` / `registry.py`）：归 **REQ-261005203907-2b8c**。
- 不修净值快照链、不改 `MIN_SAMPLE_DAYS` / `SIDEWAYS_THRESHOLD`（需求边界 B2）。
- 不排查"卡片上的 7"的来源（需求边界 B3，待用户提供现场）。
- 不碰 Prometheus / `/metrics` / `alerts.yml`（需求边界 B4）。
- 与设计矛盾时**退回设计改计划**（重新提交本计划并重新批准），不在本阶段私改设计。

## 下一步

`reqboard_submit(kind=plan)`（本文件 + 任务表）→ `reqboard_ask_confirm(target=plan)` 请人批准；
批准后自动落库任务卡并进入实施。
