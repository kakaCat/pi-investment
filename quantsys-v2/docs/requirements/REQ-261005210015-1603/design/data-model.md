---
req_id: REQ-261005210015-1603
title: 不改表结构——空转 streak 的只读口径与 result 新形状
doc: design/data-model
serves: FR-4, FR-5
---

# 数据模型（REQ-261005210015-1603）

**结论先行：本需求不动任何 DDL。** `quant.evolution_fitness` 现有列足以支撑诚实计数与空转统计；
新信息只落在 `quant.inprocess_job_runs.result`（JSONB 增量键）。

## 现有表（不改）（serves: FR-4）

`quant.evolution_fitness`（DDL 见 `infrastructure/persistence/migrations/add_evolution_fitness_table.sql`）

| 列 | 类型 | 本次用途 |
|---|---|---|
| `account_name` | String(50) | 计数分组 |
| `window_end` | Date | **streak 分组键**、`last_ok` 取值 |
| `window_days` | Integer（默认 20） | 只读查询的过滤条件（避免混入其它窗口口径） |
| `status` | String(20) | **有效与否的唯一依据**（`ok` / `insufficient_sample` / `no_trades` / `data_gap`） |
| `up_capture` / `down_capture` / `fitness` | Numeric(10,4) | 非 `ok` 时为 NULL（E5 实测 10-05 五行全 NULL） |
| `up_days` / `down_days` | Integer | 诊断样本天数（本期只读，不进消息） |
| `computed_at` | DateTime | 不动 |

唯一键 `(account_name, window_end, window_days)` 保证 upsert 幂等——**同一 `window_end` 重跑只覆盖，不新增**，
这也是"56 个 window_end 每个恰好 5 行"（E8）的结构性原因。

**为什么不加"有效产出数"列**：它可由 `status` 聚合导出，加列会产生"两份真相"；
且加列 = 改数据模型 → 触发本需求的升级信号④。

## 新增两个**只读**仓储方法（serves: FR-5）

落点：`adapters/outbound/repositories/evolution_fitness_repository.py::EvolutionFitnessORMRepository`
（handler 已经显式导入该类，见 `pipeline.py:156-158`）。

```python
from sqlalchemy import case, func

def list_recent_window_ok_counts(
    self, limit: int = 20, window_days: int = 20
) -> List[Tuple[date, int]]:
    """最近 limit 个 window_end 的 ok 条数（倒序）。只读，供空转统计。"""
    rows = (
        self.session.query(
            EvolutionFitness.window_end,
            func.count(case((EvolutionFitness.status == 'ok', 1))).label('ok_count'),
        )
        .filter(EvolutionFitness.window_days == window_days)
        .group_by(EvolutionFitness.window_end)
        .order_by(EvolutionFitness.window_end.desc())
        .limit(limit)
        .all()
    )
    return [(r[0], int(r[1] or 0)) for r in rows]

def get_last_ok_window_end(self, window_days: int = 20) -> Optional[date]:
    """最近一次有有效产出的 window_end；从未有过 → None。只读。"""
    return (
        self.session.query(func.max(EvolutionFitness.window_end))
        .filter(EvolutionFitness.window_days == window_days,
                EvolutionFitness.status == 'ok')
        .scalar()
    )
```

**口径（纯函数，便于单测）**

```python
def derive_idle_streak(counts_desc: Sequence[Tuple[date, int]]) -> Tuple[int, bool]:
    """返回 (连续无有效产出的次数, 是否被 K 截断)。

    自最近一个 window_end 往前数，直到遇到 ok_count > 0 为止；
    若 limit 条全为 0 → 真实 streak 可能更大，第二项为 True（消息渲染成「≥K 次」）。
    """
```

**性能与索引**：`idx_evolution_fitness_window_end` 已存在；当前表规模 280 行 / 56 个 `window_end`，
两条聚合查询为毫秒级。**每次运行只增两次 SELECT**，无写放大。

**失败隔离（与 `architecture.md` 一致）**：任一查询抛错 → `logger.error` + 文案降级为 `空转统计不可用`，
**任务仍记 success**；不得让"报告写不出来"把一次成功采集判成失败。

## `quant.inprocess_job_runs.result` 的新形状（JSONB，增量键）（serves: FR-3, FR-4）

```json
{
  "note": "账户行为 fitness（非策略参数进化）",
  "summary": "有效 0（样本不足 2 / 无成交 3 / 数据缺口 0）｜已连续 2 次无有效产出（最近有效：2026-09-12）",
  "no_output": true,
  "detail": {
    "window_end": "2026-10-05",
    "accounts_total": 5,
    "computed": 5,
    "computed_ok": 0,
    "insufficient_sample": 2,
    "no_trades": 3,
    "data_gap": 0,
    "other": 0,
    "aligned_days": 14,
    "idle_streak": 2,
    "last_ok_window_end": "2026-09-12"
  }
}
```

（现状同一行的 result 为 `{"note": ..., "detail": {"skipped": 0, "computed": 5, "window_end": "2026-10-05"}}`
——本次**删除** `skipped`、**新增**上述键。）

**兼容性检查（已核）**

- `find_result_failure`：`detail` 不含 `success`/`status` 标记键 → **不下钻**；
  顶层 `no_output` 是 bool → `_as_int` 返回 None，不参与"计数全 0 + 有缺口"判定 → **判 `None`（非失败）**。
- `_job_failure_watch` / `_reap_orphan_runs` / `list_today_runs`：只读 `status` / `error`，不读 result 形状。
- 旧日志解析脚本：`note` / `detail` 键名沿用，只是新增键，无需改。

## 边界与回滚（serves: FR-4, FR-5）

| 边界 | 处理 |
|---|---|
| 从未有过 `ok` 行 | `get_last_ok_window_end()` → `None` → 文案 `（最近有效：从未）` |
| 最近 K 条全为 0 | `derive_idle_streak` 返回 `(K, True)` → 文案 `已连续 ≥20 次无有效产出` |
| 表中只有 1 个 `window_end` 且为 0 | streak = 1 → 走"本次无有效产出"分支（不写"连续 2 次"） |
| `window_days` 混用（历史有 20 以外） | 查询按 `window_days=20` 过滤，避免口径串味 |
| 回滚 | 无 DDL / 无数据改写 → `git revert` 即回到现状；新键消失后消费方自动回落 |
