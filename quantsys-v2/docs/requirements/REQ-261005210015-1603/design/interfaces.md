---
req_id: REQ-261005210015-1603
title: 通知文本、handler 结果、service 返回体三份契约
doc: design/interfaces
serves: FR-2, FR-3, FR-4, FR-6
---

# 接口与数据契约（REQ-261005210015-1603）

本需求改三处**内部契约**（人读通知文本、handler 返回值、service 返回值），
**无对外 HTTP 契约变化**、无表结构变化。

## 契约 A：完成通知文本（人读，本次要改的对外语义）（serves: FR-1, FR-2, FR-3）

**结构**

```
[✅|⚠️] 每日任务完成[（无有效产出）]：<job_id>
<job.description>
耗时: <X.X 秒 | X.X 分钟>
<summary（handler 自述，若有）>
```

**耗时（FR-1）**

| elapsed | 输出 | 说明 |
|---|---|---|
| `1.21` | `1.2 秒` | 现状 `0.0 分钟`（错误观感） |
| `59.96` | `60.0 秒` | 阈值前仍用秒 |
| `60.0` | `1.0 分钟` | 边界归分钟 |
| `125.0` | `2.1 分钟` | |
| `< 0` | `0.0 秒` | 时钟回拨兜底 |

**语气（FR-3）**：`no_output is True` → 前缀 `⚠️ 每日任务完成（无有效产出）：`；否则与今天逐字相同。
**台账 `status` 不变**（仍 `success`）——这条是硬约束，见 `test-cases.md` T8。

**fitness 的 summary 文本（FR-2 / FR-5）**

```
有效 {computed_ok}（样本不足 {insufficient_sample} / 无成交 {no_trades} / 数据缺口 {data_gap}）
```
其后按条件追加（**两者互斥**）：

| 条件 | 追加 | 例 |
|---|---|---|
| `computed_ok == 0` 且 `idle_streak >= 2` | `｜已连续 {idle_streak} 次无有效产出（最近有效：{last_ok}）` | `｜已连续 2 次无有效产出（最近有效：2026-09-12）` |
| `computed_ok == 0` 且 `idle_streak == 1` | `｜本次无有效产出（最近有效：{last_ok}）` | `｜本次无有效产出（最近有效：2026-09-12）` |
| `computed_ok > 0` | 不追加 | — |
| 统计查询失败 | `｜空转统计不可用` | 见 `architecture.md` 失败隔离 |

`{last_ok}` 取 `quant.evolution_fitness` 中 `status='ok'` 的最大 `window_end`；从未有过 → `从未`。
`{idle_streak}` 取最近 `K=20` 个 `window_end`（去重、倒序）中**前导** `ok 计数 == 0` 的行数。

## 契约 B：handler 返回值（内部，新增顶层键）（serves: FR-2, FR-3, FR-6）

```python
# adapters/inbound/fastapi_app/daily_jobs/pipeline.py::_job_evolution_fitness
{
  'detail': {                       # 结构化计数（原样落 inprocess_job_runs.result）
      'window_end': '2026-10-05',
      'accounts_total': 5,          # 遍历到的 active 账户数
      'computed': 5,                # 兼容键，= accounts_total（语义见契约 C）
      'computed_ok': 0,
      'insufficient_sample': 2,
      'no_trades': 3,
      'data_gap': 0,
      'other': 0,
      'aligned_days': 14,           # 本次对齐窗口天数（诊断"样本不够"）
      'idle_streak': 2,
      'last_ok_window_end': '2026-09-12',
  },
  'summary': '有效 0（样本不足 2 / 无成交 3 / 数据缺口 0）｜已连续 2 次无有效产出（最近有效：2026-09-12）',
  'no_output': True,                # 语气标记（bool，不是 1/0）
  'note': '账户行为 fitness（非策略参数进化）',   # 既有键，保留
}
```

**消费方与不变式**

- `runtime._run_job`：读 `summary`（经 `_summarize_result`）、读 `no_output`。**不读 `detail`**。
- `find_result_failure`：**必须返回 `None`**（FR-6）。三条保障见 `architecture.md`「陷阱与防护」。
- `_summarize_result`：见契约 D。
- 兼容性：`quant.inprocess_job_runs.result` 是 JSONB，新键对既有消费方（巡检只读 `status`、
  白名单取键）无破坏；`note` / `detail` 键名沿用，旧日志解析脚本不受影响。

## 契约 C：`EvolutionFitnessService.compute_all_accounts()` 返回值（内部，改语义）（serves: FR-4）

```python
{
  'window_end': '2026-10-05',        # 既有
  'accounts_total': 5,               # 新增：遍历到的 active 账户数
  'computed': 5,                     # 保留（兼容键）：**= accounts_total**，不是"有效条数"
  'computed_ok': 0,                  # 新增：status == 'ok' 的条数（**唯一**可称"算出来了"的数）
  'insufficient_sample': 2,          # 新增
  'no_trades': 3,                    # 新增
  'data_gap': 0,                     # 新增（服务侧"无对齐日期"分支）
  'other': 0,                        # 新增：未预期 status 的兜底桶（防求和不变式被悄悄破坏）
  'aligned_days': 14,                # 新增：本次对齐窗口天数
  'skipped': 0,                      # **删除**（写死值，无消费方；已核 grep）
}
```

**不变式（测试锁）**：`computed_ok + insufficient_sample + no_trades + data_gap + other == accounts_total`。

**调用方影响**

| 调用方 | 现状用法 | 改动 |
|---|---|---|
| `daily_jobs/pipeline.py::_job_evolution_fitness` | `{'detail': summary, 'note': ...}` | 加 summary / no_output / streak（契约 B） |
| `daily_orchestrator.py:669` | `.get('computed', 0)` 打日志 | 保留 `computed` → **可不改**；建议顺带在同一行加 `computed_ok`（1 行，让日志也不再误导） |
| `tests/e2e/test_evolution_pipeline.py:160` | `assert result['computed'] >= 1` | 不动（`computed` 保留） |
| `tests/services/evolution/test_evolution_fitness_service.py` | 断言 upsert 调用 | 增补计数不变式断言 |

## 契约 D：`_summarize_result` 的行为矩阵（其他任务零变化）（serves: FR-2）

| 输入 | 输出 |
|---|---|
| 有非空 `summary` | `summary` + 顶层白名单键片段（**不再**输出子字典 dump 段） |
| 无 `summary` | **与今天逐字一致**：顶层白名单键片段 + 子字典 `key[...]` 段 |

白名单补 `computed_ok` / `insufficient_sample` / `no_trades` / `data_gap` / `no_output`
（作为"handler 忘记写 summary"时的兜底；`no_output` 以 `无有效产出=True` 形式可读）。
`max_len=300` 的截断保持。

**为什么用"有 summary 才替换"而不是"统一改写格式"**：后者会让 `evening_pipeline` 等任务的卡片
文本一起变（FR 明确要求它们正常路径语义不变），收益为零、回归面变大。

## 兼容与回滚（serves: FR-4, FR-6）

- 无表结构变更、无历史数据改写、无对外契约变更。
- 回滚 = `git revert` 对应提交；新键消失后 `_summarize_result` 自动回落到今天的行为（前向兼容）。
- **跨需求**：不改 `is_due` / `JobDef` / `registry.py` / `_mark_done` 语义，
  不与 REQ-261005203907-2b8c 的跳过分支发生接口耦合（见 `architecture.md` D-E）。
