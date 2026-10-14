# 测试证据（REQ-261005210015-1603）

**取证日期**：2026-10-05
**工作区**：`quantsys-v2/`（venv: `./venv/bin/python`）

## 1. 命令与输出摘要（四条，全部新鲜执行）

```bash
# ① 通知层用例（FR-1/2/3/5/6）
$ ./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py -q
14 passed in 0.64s
notify-guard intercepted=0 egress=0 offenders=[]

# ② 数据层用例（FR-4/5）
$ ./venv/bin/python -m pytest tests/services/evolution/test_evolution_fitness_service.py \
      tests/repositories/test_evolution_fitness_repository.py -q
15 passed, 1 skipped in 0.65s

# ③ 全量回归（FR-7，含 e2e）
$ ./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py \
      tests/e2e/test_evolution_pipeline.py tests/services/evolution/test_evolution_fitness_service.py \
      tests/repositories/test_evolution_fitness_repository.py tests/test_daily_jobs_notify_truthfulness.py -q
68 passed, 1 skipped, 1 warning in 1.39s
notify-guard intercepted=0 egress=0 offenders=[]
```

**为何 68 而不是更多**：本需求只新增 21 条用例（14 + 7），其余为既有回归；
`1 skipped` 是既有用例（默认构造依赖已迁移的仓储类，历史占位跳过，与本需求无关）。

## 2. 新增用例清单与覆盖映射

**`tests/test_daily_jobs_notify_truthfulness.py`（14 条）**

| 用例 | 覆盖 |
|---|---|
| `test_format_elapsed_seconds_below_minute` | FR-1（1.21→1.2 秒、59.96→60.0 秒、-1→0.0 秒） |
| `test_format_elapsed_minutes_above_minute` | FR-1（60.0→1.0 分钟、125.0→2.1 分钟） |
| `test_summary_shows_state_distribution` | FR-2（含四类计数、无 `detail[computed=`） |
| `test_other_job_summary_unchanged` | FR-2/FR-7（旧形状逐字不变 + 兜底可见） |
| `test_zero_output_uses_warning_title` | FR-3（⚠️ 前缀） |
| `test_nonzero_output_keeps_success_title` | FR-3（有产出仍 ✅） |
| `test_elapsed_line_rendered_by_formatter` | FR-1（耗时行以秒结尾） |
| `test_mark_done_status_stays_success` | FR-6（台账仍 success） |
| `test_new_result_shape_not_judged_failed` | FR-6（失败判定不变式） |
| `test_idle_streak_phrase_when_two_zero_windows` | FR-5（已连续 2 次 + 最近有效日） |
| `test_no_streak_phrase_when_output_exists` | FR-5（反例：有产出不出现该句） |
| `test_streak_capped_renders_ge_k` | FR-5（截断渲染 ≥20 次） |
| `test_first_idle_window_wording` | FR-5（首次措辞 + 最近有效：从未） |
| `test_streak_query_failure_degrades_loudly` | FR-5/FR-6（降级文案 + error 日志 + 仍 success） |

**`tests/services/evolution/test_evolution_fitness_service.py`（新增 5 条）**

| 用例 | 覆盖 |
|---|---|
| `test_state_counts_sum_to_accounts_total` | FR-4（不变式） |
| `test_null_rows_not_counted_as_ok` | FR-4（NULL 不计入 ok） |
| `test_skipped_key_removed` | FR-4（删写死键） |
| `test_computed_key_kept_for_compat` | FR-4（兼容锁） |
| `test_aligned_days_reported` | FR-4（对齐窗口天数） |

**`tests/repositories/test_evolution_fitness_repository.py`（新增 2 条）**

| 用例 | 覆盖 |
|---|---|
| `test_recent_window_ok_counts_groups_desc` | FR-5（分组 + 倒序） |
| `test_last_ok_window_end_ignores_newer_non_ok` | FR-5（忽略更新的非 ok 行） |

## 3. 打桩点合规（历史事故的防线）

`_run_job` 读的是 `runtime` 模块自己的全局名，故所有用例的桩都打在
`adapters.inbound.fastapi_app.daily_jobs.runtime`（`_send_feishu` / `_mark_running` / `_mark_done`）。
未打在 `alerting` 或转发壳上（那是 2026-10-03 四张假卡片的成因）。

## 4. 零真实外发

每轮测试末尾的 `notify-guard intercepted=0 egress=0 offenders=[]` 即证据：
测试期间没有任何未声明的真实通知外发。

## 5. 真实观察（非桩）

见 `docs/requirements/REQ-261005210015-1603/notes/observation.md`：
跑**真实 handler**（生产库、幂等 upsert、不发通知）得到

```
summary   : 有效 0（样本不足 2 / 无成交 3 / 数据缺口 0）｜已连续 2 次无有效产出（最近有效：2026-09-12）
no_output : True
失败判定   : find_result_failure(result) → None
```

## 6. 未覆盖 / 受限项（如实登记）

1. **「表内一条 ok 都没有 → `None`」**：该分支依赖空表，共享测试库下不可构造，
   改以「更新的非 ok 行不得顶掉最近 ok 日」锁同一语义（用例内已写明）。
2. **真实飞书投递**：本需求只改消息**文本**，未改投递通道；卡片实际投递由日常运行验证
   （观察窗口见 `notes/observation.md` §5，可能被邻居交易日门判 `skipped`）。
3. **耗时格式化的小时分支**：FR-1 只要求秒/分钟两级，未实现小时级（属超范围）。

## 7. 用例与任务卡对应（covers）

每张任务卡（含子卡）都能指向本次新增/执行的用例或命令；父卡与其子卡链共用同一批证据。

- covers: t-cda13d — 通知层契约落地（父卡）：`tests/test_daily_jobs_notify_truthfulness.py::TestElapsedFormat` + `TestSummaryTruthfulness`
- covers: t-39a1a8 — 该卡研发子卡：同上（研发段即该文件的落地）
- covers: t-bf7712 — 该卡联调子卡：`test_summary_shows_state_distribution`（真实 result 渲染）
- covers: t-bf4521 — 该卡复核子卡：`test_new_result_shape_not_judged_failed`（陷阱不变式）
- covers: t-b8daeb — 该卡测试子卡：`pytest tests/test_daily_jobs_notify_truthfulness.py -q` → 14 passed
- covers: t-c0941a — 服务诚实计数（父卡）：`tests/services/evolution/test_evolution_fitness_service.py::TestHonestStateCounts`
- covers: t-c4b336 — 该卡研发子卡：`test_state_counts_sum_to_accounts_total`
- covers: t-90d649 — 该卡联调子卡：`test_computed_key_kept_for_compat`
- covers: t-d9106a — 该卡复核子卡：`test_skipped_key_removed`
- covers: t-ef688c — 该卡测试子卡：`pytest tests/services/evolution/... -q` → 15 passed, 1 skipped
- covers: t-17fce0 — 空转读数（父卡）：`tests/repositories/test_evolution_fitness_repository.py::TestReadOnlyAggregates`
- covers: t-228f42 — 该卡研发子卡：`test_recent_window_ok_counts_groups_desc`
- covers: t-735131 — 该卡联调子卡：真库只读读数（10-05=0、10-02=0、09-12=3）
- covers: t-1dada1 — 该卡复核子卡：只读性核对（无 add/commit/update）
- covers: t-a00ef1 — 该卡测试子卡：`pytest tests/repositories/test_evolution_fitness_repository.py -q` → 5 passed
- covers: t-2d12c5 — handler 组装（父卡）：`TestIdleStreak` 全组
- covers: t-a494c4 — 该卡研发子卡：`pipeline._job_evolution_fitness` 的 summary/no_output 组装
- covers: t-d796cd — 该卡联调子卡：`test_idle_streak_phrase_when_two_zero_windows`
- covers: t-e4693b — 该卡复核子卡：契约逐条对照（见 reviews/review-report.md §1）
- covers: t-23611a — 该卡测试子卡：`test_streak_query_failure_degrades_loudly`
- covers: t-4b35ba — runtime 接线（父卡）：`TestHostTone` 全组
- covers: t-af5158 — 该卡研发子卡：`test_zero_output_uses_warning_title`
- covers: t-de98f5 — 该卡联调子卡：`test_nonzero_output_keeps_success_title`
- covers: t-88c26a — 该卡复核子卡：`test_mark_done_status_stays_success`（FR-6 硬约束）
- covers: t-507717 — 该卡测试子卡：`test_elapsed_line_rendered_by_formatter`
- covers: t-cef289 — 通知层用例（父卡）：上表第 2 节 14 条清单
- covers: t-003afe — 该卡研发子卡：该文件整体落地（14 passed）
- covers: t-8bec5b — 该卡复核子卡：打桩点合规核对（桩打在 runtime 模块）
- covers: t-cca3af — 该卡测试子卡：`pytest tests/test_daily_jobs_notify_truthfulness.py -q` → 14 passed
- covers: t-89b1f4 — 数据层用例（父卡）：上表第 2 节新增 7 条清单
- covers: t-985e3a — 该卡研发子卡：服务层 5 条落地
- covers: t-66db6e — 该卡联调子卡：真库读数与注入点核对
- covers: t-16f3fb — 该卡复核子卡：共享库稳健性口径（子集断言 + 未来日期）
- covers: t-ad4340 — 回归与真实观察（父卡）：第 3 节四条命令 + `notes/observation.md`
- covers: t-243932 — 该卡研发子卡：`pytest` 六文件 → 68 passed, 1 skipped
- covers: t-df7921 — 该卡复核子卡：观察证据可复核性核对（含偏离登记）
- covers: t-2acb88 — 该卡测试子卡：零外发与文档齐备核对

