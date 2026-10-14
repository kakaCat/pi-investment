# 测试证据 · REQ-261006190953-fc43

**采集时间**：2026-10-06 20:5x CST（本机 `date` → `Tue Oct  6 2026`）
**采集者**：本窗口（提交者）；每条命令都是**本期新鲜执行**的输出摘要，不是历史记录的转抄。
**环境**：`./venv/bin/python`（Python 3.13.14 / pytest 9.1.1）；DB 走 `quant_test`（pytest 自动切）；
agent-dh 侧 `npx vitest`（v1.6.1）。

---

## 1. 主验收命令（v2 侧：新增与改动文件）

```bash
./venv/bin/python -m pytest \
  tests/test_nav_series.py \
  tests/test_equity_snapshot_trading_day_gate.py \
  tests/test_equity_snapshot_daily_return.py \
  tests/test_daily_jobs_trading_day_gate.py \
  tests/test_risk_metrics_nav_window.py \
  tests/test_migration_purge_nontrading_snapshots.py \
  tests/test_check_nontrading_equity_snapshots.py -q
```
**输出摘要**：`117 passed, 1 skipped, 2 warnings in 13.79s`

## 2. 邻域回归（v2 侧）

```bash
./venv/bin/python -m pytest tests/api tests/migration/test_analysis_parity.py \
  tests/test_api_smoke.py tests/services/evolution tests/test_multi_account_domain.py \
  tests/application/test_account_trading_service_v2.py tests/services/test_risk_metrics_service.py \
  tests/test_trading_day_guard.py -q
```
**输出摘要**：`391 passed, 1 skipped, 35 warnings in 17.27s`（0 failed）

## 3. 巡检判据（**生产库实跑，只读**）

```bash
PYTHONPATH=. ./venv/bin/python tools/check_nontrading_equity_snapshots.py
```
**输出摘要**：
```
[coverage] 日历覆盖 1994-03-01 ~ 2026-12-31（白名单语义：范围内不在清单里 = 非交易日）
[result] 违规 35 行，涉及 7 个日期：2026-08-08×5, 2026-08-15×5, 2026-08-29×5,
         2026-09-05×5, 2026-09-06×5, 2026-09-12×5, 2026-10-02×5
[exit] 2
```
> 这是 **apply 前应有的红**。执行第 4 节的 apply 后，本条应转为 `[exit] 0`。

**测试库（日历空表）实跑** → `[unusable] … 无法判定 → [exit] 3`（判不了不报干净）。

## 4. 存量清理迁移（**生产只读 dry-run**，未 apply）

```bash
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py
```
**输出摘要**：
```
[plan] 待删 35 行；预期 35 行
[backup] 待删行已被备份覆盖 35/35 行
[replay] 合计重算派生字段 65 行
[verify] 判据 SQL（非交易日净值行数，本账户范围）=0
[dry-run] 已 ROLLBACK：库内零改动（表行数/校验和与执行前一致）。加 --apply 落库。
```
**生产库安全核对**（dry-run 后）：快照表 `187` 行未变、`bak_*` 表 `0` 个。

**apply（待人工放行，本窗口未执行）**：
```bash
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py --apply
```

## 5. 一致性校验器（生产只读，**apply 前基线**）

```bash
./venv/bin/python tools/verify_equity_snapshot_consistency.py \
  --accounts agent_virtual,user_main_simulation,v13_simulation,v14_simulation,v15_simulation
```
**输出摘要**：`结论：存在差异 119 处 → 退出码 2`（样本：`agent_virtual 2026-08-10 drawdown: 库内=0.020100 复算=-0.020124`
——库里还有**符号为正**的历史错值）。apply 之后本条应为 `diff=0` / 退出码 0。

## 6. 跨仓（agent-dh）

```bash
cd ../agent-dh && npx vitest run apps/web/tests/attribution-alignment.test.ts
```
**输出摘要**：`Test Files 1 passed (1)` / `Tests 15 passed (15)`

```bash
npx vitest run apps/web/tests/tool-silent-failure-guard.test.ts apps/web/tests/account-default.test.ts
```
**输出摘要**：`Test Files 2 passed (2)` / `Tests 37 passed (37)`

> 预存失败（与本需求无关，已用 `git stash` 对照取证）：`apps/web/tests/plugin-schema.smoke.test.ts`
> 插件构造 5000ms 超时 → 该文件 `1 failed | 20 passed`。

## 7. 验收映射（判据 → 用例名）

| 卡 | 验收点 | 用例 |
|---|---|---|
| B | ① | `test_upsert_refuses_weekend_and_writes_no_row` / `..._sunday_...` / `..._calendar_holiday` |
| B | ② | `test_upsert_writes_on_trading_day` |
| B | ③ | `test_upsert_writes_when_calendar_degraded` |
| B | ④ | `test_force_bypass_writes_non_trading_row` |
| B | ⑤ | `test_get_equity_snapshots_trading_days_only_limit_means_trading_days` |
| B | ⑥ | `test_get_equity_snapshots_unverified_does_not_filter` |
| B | ⑦ | `test_previous_valid_snapshot_skips_non_trading_baseline` |
| B | ⑧ | `test_previous_valid_snapshot_still_skips_incomplete_row` |
| B | ⑨ | `test_gate_is_consulted_with_target_day` |
| C | ① | `test_holiday_writes_zero_and_counts_every_account_as_refused` + `..._real_repo_refusal_is_counted_as_refused` |
| C | ② | `test_trading_day_writes_every_account_and_refuses_none` |
| C | ③ | `test_none_snapshot_becomes_skipped_structure` |
| C | ④ | `test_holiday_skips_with_non_trading_reason` + `test_two_skip_reasons_are_distinguishable` |
| C | ⑤ | `test_bar_exists_on_holiday_still_skips` |
| C | ⑥ | `test_service_and_engine_both_consume_the_shared_verdict` |
| D | ①~⑦ | `test_nav_points_equals_window_trading_days` / `test_window_has_five_typed_fields` / `test_nav_coverage_verified_and_reports_series_gap` / `test_nav_coverage_ignores_benchmark_gap` / `test_equity_curve_excludes_non_trading_rows` / `test_max_drawdown_comes_from_simulation_account` / `test_legacy_response_keys_survive` |
| F | ①~⑧ | `test_dry_run_reports_35_and_changes_nothing` / `test_apply_deletes_whitelist_missing_and_keeps_out_of_range` / `test_count_mismatch_exits_nonzero_and_prints_diff` / `test_backup_shortfall_aborts_before_delete` / `test_apply_clears_judgement_and_verifier_reports_zero_diff` / `test_apply_twice_is_idempotent` / `test_rollback_restores_rows_and_prints_loudly` / `test_apply_on_non_test_db_requires_explicit_flag` |
| G | ①~⑤ | `test_clean_window_exits_zero` / `test_in_range_non_trading_row_is_a_violation` / `test_out_of_range_row_is_only_a_warning` / `test_empty_calendar_is_unusable_not_clean` / `test_is_synthetic_claim_is_gone_from_guard_docstring` |
| E | ①~⑤ | `attribution-alignment.test.ts` 内 15 例（含 ① 透出 / ② 缺字段 / ② 非 2xx / ③ 国庆 0 缺口 / ④ 缺 09-25 仍报 / ⑤ 源码锁） |

## 8. 未覆盖 / 无法在代码侧覆盖的部分（如实列出）

1. **卡 E ①「透出」的端到端**：线上 v2 未重启，接口尚无新字段 → 当前为桩测（已对齐 v2 源码契约）。
2. **验收标准里唯一的"时间型"判据**（原需求判定标准第 8 条：10-07 休市无新增行 / 10-08 复市首日写入成功）：
   需等真实日期，属上线后回执。**其中「10-07 无新增行」在闸门上线后即可由巡检器间接证明**
   （apply 后巡检器 = 0 且 10-07 无新行）。
3. **生产 apply 与 v2 重启**：均为待人工放行动作，见 `reviews/code-review.md` §4。

---

## 9. 任务覆盖标注（covers）

> 说明：本需求 7 张父卡各展开 4 张子卡（研发 / 联调 / 复核 / 测试），**同一批用例同时是四段的判据**，
> 故下面每条 `covers` 指向的都是第 1~7 节里真实存在的命令与用例名，不是为过门而写的空标注。

### 卡 A · nav_series 口径模块（`tests/test_nav_series.py` 14 例）

- covers: t-7c5daa — 父卡：口径模块落盘 + shim 兼容，验收 ①~⑧
- covers: t-9425ac — 研发段：`trading_day_set` 不可得返回 None、`filter_trading_days` 未校验原样返回
- covers: t-c029f4 — 联调段：`tests/services/test_risk_metrics_service.py` + `test_api_smoke.py -k risk`
- covers: t-8c1870 — 复核段：`grep` 无 weekday 实现 + 分层归因（DEV-1/DEV-2）
- covers: t-19fd53 — 测试段：`./venv/bin/python -m pytest tests/test_nav_series.py -q` → 14 passed

### 卡 B · 净值仓储唯一写入闸门 + 交易日回退基准（`tests/test_equity_snapshot_trading_day_gate.py` 11 例 + `test_equity_snapshot_daily_return.py` 增量 2 例）

- covers: t-8c7962 — 父卡：拒写/降级照写/force/limit=交易日数/基准回退/残缺跳过/闸门被调
- covers: t-4dec44 — 研发段：`upsert_equity_snapshot` 门与 `get_equity_snapshots(trading_days_only)`
- covers: t-3b9912 — 联调段：四条写路径调用方面 160 passed + `test_multi_account_domain` 碰撞修复
- covers: t-d41793 — 复核段：DEV-4（懒加载方向）与分层违规从 +3 降到 +1
- covers: t-8d52f6 — 测试段：卡 B 验收命令 36 passed, 1 skipped

### 卡 C · 写入入口接线（`tests/test_daily_jobs_trading_day_gate.py` 增量 6 例 + 服务/引擎路径 8 例）

- covers: t-0ae23e — 父卡：`written/refused/skipped` + 两段跳过文案 + `snap=None` 路径
- covers: t-993380 — 研发段：`snapshot_all_accounts` 计数与 `_has_bar` 降级
- covers: t-4c6330 — 联调段：邻域 245 passed；唯一 Python 消费方逐个核对
- covers: t-649a6b — 复核段：六条验收逐条点名（用例名见第 7 节）
- covers: t-70118d — 测试段：卡 C 验收命令 52 passed

### 卡 D · 读取端 window / nav_coverage（`tests/test_risk_metrics_nav_window.py` 12 例）

- covers: t-39a044 — 父卡：`navPoints == window.trading_days`、五字段、`equity_curve` 无脏行
- covers: t-d20433 — 研发段：两个路由 + `shared.py` 组装 + `filtered_non_trading` 计数
- covers: t-04394d — 联调段：`tests/api` + `analysis_parity` + `api_smoke` 259 passed
- covers: t-87ba63 — 复核段：七条验收点名 + DEV-7/8/9/10 记账
- covers: t-a5759a — 测试段：卡 D 验收命令 12 passed

### 卡 F · 存量清理迁移与一致性校验（`tests/test_migration_purge_nontrading_snapshots.py` 8 例）

- covers: t-5c9a67 — 父卡：dry-run 零副作用 / 白名单删除 + 范围外不动 / 行数不符中止 / 备份不足中止 / 判据归零 / 幂等 / 回滚
- covers: t-6fd33d — 研发段：迁移三态 + `tools/verify_equity_snapshot_consistency.py` + D-6 谓词修正
- covers: t-7f18d9 — 联调段：测试库自清（日历 0 / 快照 366 / bak 0）+ 邻域 71 passed
- covers: t-584b02 — 复核段：八条验收点名（② 按 D-6 改写为覆盖范围防误删）
- covers: t-158541 — 测试段：卡 F 验收命令 8 passed；生产只读 baseline 119 处差异

### 卡 G · 常驻巡检判据 + 失真注释订正（`tests/test_check_nontrading_equity_snapshots.py` 6 例）

- covers: t-6f1c29 — 父卡：三态退出码（0/2/3）+ 造脏行活性 + `grep is_synthetic == 0`
- covers: t-3807ba — 研发段：巡检器 + 测试 + `trading_day_guard` 注释订正
- covers: t-a7b2d3 — 联调段：邻域 85 passed；判据工具不接任何既有链路
- covers: t-1e0690 — 复核段：五条验收点名 + DEV-12（③ 反转）/DEV-13（不放松判据）
- covers: t-6a230e — 测试段：卡 G 验收命令 6 passed；生产实跑 35 行 / 退出码 2

### 卡 E · 跨仓消费侧（`agent-dh/apps/web/tests/attribution-alignment.test.ts` 15 例）

- covers: t-1974b4 — 父卡：透出 / 缺字段如实声明 / 国庆 0 缺口 / 缺 09-25 仍报 / 无 getUTCDay
- covers: t-d1ea93 — 研发段：`probeNavCoverage` 改消费 v2 `nav_coverage`；`prompt.ts` 文案
- covers: t-bb7fce — 联调段：线上 v2 未重启的现场核对 + agent-dh 预存失败归属（DEV-15 / R-7）
- covers: t-e8d596 — 复核段：五条验收点名（① 当前为桩测，端到端待部署）
- covers: t-ee93ba — 测试段：`npx vitest run apps/web/tests/attribution-alignment.test.ts` → 15 passed

