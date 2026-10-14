---
req_id: REQ-261005210015-1603
title: 通知链路的落点、三个结果约定与两处陷阱
doc: design/architecture
serves: FR-1, FR-2, FR-3, FR-6
---

# 架构设计（REQ-261005210015-1603）

**前提**：本需求**不改运行时架构**——不新增服务、不新增表、不新增依赖、不改任务分支结构。
只改两件事：**消息怎么拼**（耗时格式 + 人读摘要 + 语气）与**返回体怎么数**（诚实计数）。

## 目标与判定（serves: FR-1, FR-2, FR-3）

**目标**：同一条完成通知里，"跑了"与"有产出"必须能被读者分开；
`computed` 这个数不再被读成"算出了几条 fitness"。

可证伪判定：

1. `./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py -q` → 全过；
2. 以 2026-10-05 的真实 result 渲染 → 标题 `⚠️`，正文含 `有效 0`、`样本不足 2`、`无成交 3`、
   `已连续 2 次无有效产出（最近有效：2026-09-12）`；
3. `./venv/bin/python -m pytest tests/services/evolution/test_evolution_fitness_service.py tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py -q` → 全过。

## 改动落点与数据流（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）

```
application/services/evolution/evolution_fitness_service.py
  compute_all_accounts()                                        [FR-4] 诚实计数
     |  返回 {'computed'(=accounts_total,兼容键), 'computed_ok',
     |        'insufficient_sample', 'no_trades', 'data_gap', 'other',
     |        'window_end', 'aligned_days', 'accounts_total'}
     v
adapters/inbound/fastapi_app/daily_jobs/pipeline.py::_job_evolution_fitness
  |  [FR-5] 只读两次 -> EvolutionFitnessORMRepository
  |         .list_recent_window_ok_counts(limit=20)     # 连续 ok==0 次数
  |         .get_last_ok_window_end()                   # 最近一次有有效产出
  |  [FR-2] summary = "有效 3（样本不足 1 / 无成交 1 / 数据缺口 0）｜…"
  |  [FR-3] no_output = (computed_ok == 0)
  v  返回 {'detail': {...}, 'summary': str, 'no_output': bool, 'note': ...}
adapters/inbound/fastapi_app/daily_jobs/runtime.py::_run_job
  |  [FR-1] elapsed -> _format_elapsed(elapsed)          # 秒/分钟
  |  [FR-3] prefix = "⚠️ 每日任务完成（无有效产出）：" if no_output else "✅ 每日任务完成："
  |  [FR-2] _summarize_result(result)                     # summary 优先
  v
adapters/inbound/fastapi_app/daily_jobs/alerting.py
   _format_elapsed()（新增，FR-1）
   _summarize_result()（改造：有 summary 用它，无 summary 逐字保持今天的行为，FR-2）
   _send_feishu()（不动）
```

| 落点 | 现状 | 改动 | FR |
|---|---|---|---|
| `alerting.py` 新增 `_format_elapsed(seconds) -> str` | 无此函数 | `<60s → "1.2 秒"`，`≥60s → "2.1 分钟"`（均 1 位小数） | FR-1 |
| `runtime.py:133-137` | `f"{elapsed_min:.1f} 分钟"` | 改调 `_format_elapsed(elapsed)` | FR-1 |
| `runtime.py:135-138` 标题 | 恒 `✅ 每日任务完成：` | `no_output is True` → `⚠️ 每日任务完成（无有效产出）：` | FR-3 |
| `alerting.py:180-207` `_summarize_result` | 只按白名单取键 + 子字典 dump | ① 顶层 `summary` 非空 → 用它替代子字典段；② 白名单补 `computed_ok/insufficient_sample/no_trades/data_gap/no_output`（兜底可见） | FR-2 |
| `pipeline.py:143-166` `_job_evolution_fitness` | 直接 `return {'detail': summary, ...}` | 组装 `summary` / `no_output`；两次只读查询（失败降级不致命） | FR-2、FR-3、FR-5 |
| `evolution_fitness_service.py:58-107` | `{'computed': n, 'skipped': 0, ...}` | 四类状态计数 + `accounts_total`；删 `skipped`；保留 `computed`（语义写进 docstring） | FR-4 |
| `adapters/outbound/repositories/evolution_fitness_repository.py` | 只有 `upsert_fitness` / `get_leaderboard` | 新增两个**只读**方法（见 `data-model.md`） | FR-5 |

**不做**：`is_due` / `JobDef` / `registry.py`（归 REQ-261005203907-2b8c）、`_mark_done` 的 status 语义、
`find_result_failure` 本体、`_send_feishu`、表结构、APScheduler 路径。

## 设计决策（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）

### D-A `_format_elapsed` 放 `alerting.py`（不是 runtime）（serves: FR-1）

消息文本的格式化全部集中在通知模块；`runtime.py` 已经 `from ...alerting import _send_feishu, _summarize_result`
（[runtime.py:19](adapters/inbound/fastapi_app/daily_jobs/runtime.py#L19)），加一个导入即可。

规则：`s < 0`（时钟回拨）按 `0.0 秒`；`60s ≤ s < 3600s` 用分钟；**不新增"小时"分支**——
超出 FR-1 的声明（60 分钟以上仍显示分钟，如 `150.0 分钟`）；将来若要小时分支，属新的裁定。

### D-B handler 结果新增两个**顶层**键：`summary` 与 `no_output`（serves: FR-2, FR-3, FR-6）

- `summary: str`：handler 自述的人读摘要。`_summarize_result` **只在它非空时**用它替代"子字典 dump"段；
  顶层白名单键的提取照旧。**没有 summary 的任务（其余全部任务）输出逐字不变**——这是"其他任务零变化"的实现保证。
- `no_output: bool`：本次无有效产出。只被 `_run_job` 读来决定标题语气，**不参与任何失败判定**。
- 为什么放顶层而不是塞进 `detail`：`find_result_failure` 只对**含 `success`/`status` 标记键**的子字典下钻
  （`_RESULT_MARKER_KEYS`）；把语气标记放在 `detail` 里会让 `detail` 更容易被未来某次改动带上标记键而触发下钻，
  顶层键与下钻逻辑正交，风险最小。

### D-C 空转统计放**handler**，不放进 service（serves: FR-5）

service 的职责是"算 fitness + 如实计数"；"这条消息该怎么描述这批数"是展示层的事。
且 16:30 的 `daily_orchestrator` 复核路径也调 `compute_all_accounts()`
（[daily_orchestrator.py:661-672](application/services/daily_orchestrator.py#L661-L672)），它不发卡片，不需要 streak。

### D-D `computed` 保留（语义收窄为"遍历到的账户数"）（serves: FR-4）

两个硬理由：① `tests/e2e/test_evolution_pipeline.py:160` 断言 `result['computed'] >= 1`；
② `daily_orchestrator.py:669` 用 `.get('computed', 0)` 打日志。
保留它、并把"有效条数"交给 `computed_ok`，是**改语义而不是改键名**的最小改法；
service 的 docstring 必须写明两者差别（防下一个人再读错）。

### D-E 与 REQ-261005203907-2b8c 的次序与边界（serves: FR-6）

两条需求都改 `runtime.py::_run_job`，但落在**互不相交的语句块**：

- 2b8c：在**进入 handler 之前**加"休市日跳过"分支（写 `status='skipped'`、不发通知、直接 return）；
- 本需求：在**成功分支内**改标题/耗时/摘要的构造。

**不变式（写进测试）**：跳过路径**不得**经过本需求的任何一行（否则会出现"跳过了却收到 ⚠️ 卡片"）。
两者无 merge 冲突风险；若 2b8c 先落，本需求基于其新分支 rebase，**不得**改动其跳过分支。

## 依赖方向与失败隔离（serves: FR-5）

- 依赖方向不变：`adapters/inbound`（pipeline/alerting/runtime）→ `adapters/outbound`（ORM 仓储）
  是既有用法（`pipeline.py` 现在就显式 `import EvolutionFitnessORMRepository`），无反向依赖、无环。
- **空转统计是"锦上添花"，不得把好任务拖成 failed**：两次只读查询任一抛错 →
  ① `logger.error`（响亮）；② 该句省略并改写成 `空转统计不可用`；③ **任务仍记 success**。
  绝不允许因为"报告写不出来"而让一次成功的采集判失败。

## 陷阱与防护（FR-2 / FR-6 的实现约束）（serves: FR-2, FR-6）

**陷阱 1：`_noop_gap_failure` 的"计数全 0 + 有缺口"规则会误伤新键。**
`_NOOP_COUNT_KEYS` 含 **`computed`**，`_GAP_KEYS = ("stale","uncovered","missing","not_covered","no_data","未覆盖")`
（[job_executor.py:105-108](infrastructure/scheduler/job_executor.py#L105-L108)）。

- 约束 ①：`detail` 子字典**不得**引入 `success` / `status` 标记键——**下钻只发生在含标记键的子字典上**，
  没有标记键时 `_noop_gap_failure` 根本看不到它里面的键。
  **2026-10-05 实测修正（t-bf4521 复核段）**：初稿把这条写成"把 `data_gap` 改名成 `no_data` 就会误判"，
  实测**偏强**——无标记键时 `no_data=3` 仍返回 `None`；只有"带标记键 + 某计数键为 0 + `_GAP_KEYS` 名字"
  三者同时成立才判失败（实测 C 组：`status` 标记 + `computed=0` + `no_data=3` → 判失败）。
- 约束 ②：新增状态键**仍应避免**与 `_GAP_KEYS` 撞名——把 `data_gap` 写成 `no_data` 会平白给自己埋一颗雷。
- 防护 ③：保留 `computed = accounts_total`（active 账户数，恒 > 0）——即便将来有人给 `detail` 加上标记键，
  "计数全 0"的前提也不成立。测试把这条不变式锁死（四组对照：无标记键 / 带标记键且 `computed>0` /
  带标记键且 `computed=0` 且 `no_data` / `data_gap` 命名安全）。

**陷阱 2：`_as_int` 把 bool 判为 None**（[job_executor.py:111-115](infrastructure/scheduler/job_executor.py#L111-L115)）
→ `no_output: True` 天然不参与任何计数/缺口判定；这也正是它适合当语气标记的原因（不能是 `1`）。

## 测试落点（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）

见 `test-cases.md`：新增 `tests/test_daily_jobs_notify_truthfulness.py`，
增补 `tests/services/evolution/test_evolution_fitness_service.py`，回归既有 3 个测试文件。
