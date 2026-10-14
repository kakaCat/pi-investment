# REQ-261006163444-8e4f · 设计：数据模型与数据契约

## 1. 是否改表 / 改 schema（serves: FR-1, FR-2）

**不改。零 DDL、零迁移、零新表。**

- 分域快照由 `quant.daily_klines` 的 `trade_date` **现算**（architecture.md §2），
  不持久化"上期域"、不存"观察中天数" ⇒ 无需新表/新列。
- 本需求只有一个**数据行变更**（非 schema）：`quant.scheduler_tasks` id=232 的 params 里
  `quality_threshold` 95.0 → 88.0（§5），以及一个**语义修正**（`original_count` 的写入键，§3）。

> 升级信号（D-3 已排除）：若日后要把"域"落成持久化状态（例如按日归档域快照以便回溯），
> 才需要一次迁移；本设计选择"现算"以避免它。

## 2. 读契约：`quant.daily_klines` 的两个新查询（serves: FR-1）

| 查询 | 语义 | 返回 | 预计行数 |
|---|---|---|---|
| `list_recent_trade_dates(limit=2)` | 全市场交易日倒序前 N 个 | `list[str]`（`'YYYY-MM-DD'`） | 2 |
| `list_symbol_last_trade_date()` | 每个标的最新的有 K 线交易日 | `list[tuple[str, str]]`（symbol, date） | 5686 |

```sql
-- list_recent_trade_dates(2)
SELECT DISTINCT trade_date FROM quant.daily_klines ORDER BY trade_date DESC LIMIT 2;

-- list_symbol_last_trade_date()
SELECT symbol, MAX(trade_date) FROM quant.daily_klines GROUP BY symbol;
```

- **过滤条件**：不加 `WHERE`。分域要覆盖**全库标的**（含已退市），正是为了把它们识别出来——
  加任何"最近 N 天"过滤都会让死标的消失（那正是我们要看的东西）。
- **`gap` 的算法**：`gap = rank(mx) - 1`，`rank` 为交易日倒序名次（`D_last` 名次为 1）。
  （订正：本节初稿误写为 `rank(D_last) - rank(mx)`；2026-10-06 实施 t1 时订正。）
  由 `classify_domain()` 在内存里算（纯函数，interfaces.md §1）。
  某标的的 `mx` 不在交易日集合内（异常数据）⇒ `gap` 取哨兵 **9999**，落"存量"并在日志 warning。
- **序号不落库**：`rank` 只在内存里当中间量，不写表。

## 3. 写契约 1：审计表 `public.kline_data_quality`（serves: FR-5）

| 列 | 现写入 | 修后写入 | 说明 |
|---|---|---|---|
| `original_count`（int, not null） | `gap_info.get('expected_days', 0)` ⇒ **恒 0** | `gap_info.get('total_trading_days', 0)` ⇒ 窗口交易日数 | 真实键见 `data_gap_detector.py:90`；这是本需求唯一改动的**既有列语义** |
| `cleaned_count` | `gap_info.get('actual_days', 0)` | 不变 | 实际有数据的天数 |
| `completeness_score` | `gap_info['coverage_rate']` | 不变 | |
| `accuracy_score` | `validator.get_data_quality_score(...)` | 不变（但改为**只算一次**并复用，见 §6） | |
| `overall_score` / `grade` | `(cov+cons+acc)/3` → `_calculate_grade` | 不变 | 等级分数线不动 |

- **历史行不追改**：2026-10-06 之前写入的 `original_count` 全为 0，保持原样；
  阅读旧数据时按"该列当时不可用"解读（登记在 requirement.md 后续线 2）。
- **无新列、无索引变更。**

## 4. 写契约 2：任务结果 `quant.scheduler_runs.result`（jsonb）（serves: FR-2, FR-3）

`daily_data_quality_check` 返回的 `result` 新增三个键（**只增不改**，既有键全部保留）：

```jsonc
{
  "alert_scope": "tradable",                    // 新增：本次告警的分域口径标识
  "domain": {                                    // 新增：检查域快照
    "last_trade_date": "2026-09-30",
    "prev_trade_date": "2026-09-29",
    "tradable_count": 5280,
    "observing_count": 3,
    "stock_count": 403,
    "stats_symbols": 5280,                       // 参与均值统计的只数（截断时 < tradable_count）
    "degraded": false,
    "degrade_reason": null
  },
  "domain_dropped": {                            // 新增：本期掉出可交易域
    "count": 2,
    "symbols": ["002813", "603183"],             // 正文展示上限 20 只；count 为全量
    "truncated": false,
    "reason": null                               // 无上期交易日时为 "no_prev_trade_date"
  },
  "alert_thresholds": {                          // 新增：本次生效阈值（可核验，避免"配置了没生效"）
    "d_grade": 20, "score": 88.0, "coverage_info": 97.0,
    "backfill_fail_rate": 50.0, "backfill_min_sample": 10
  }
}
```

**负向契约（必须遵守）**：

1. **`per_symbol` 禁止写入 `result`**：它是 5686 条的内存明细（约 1MB），只在本 run 内用于聚合。
   `result` 由作业显式构造（`data_quality_check_job.py:295-319`），**不得**整包透传
   `quality_result`——否则 jsonb 会被撑爆。
2. **`domain_dropped.symbols` 上限 20 只**（正文可读性）；`count` 永远是全量真值，两者不一致时
   `truncated=true`，不允许用截断后的长度冒充 `count`（这是 REQ-261006133733-1fdf 同族的"静默失真"）。
3. 既有 `check_summary` / `backfill_summary` / `backfill_degraded` / `alert_dispatch` 保持原义。

## 5. 配置行变更：`quant.scheduler_tasks` id=232（serves: FR-4）

| 键 | 旧值 | 新值 | 理由 |
|---|---|---|---|
| `quality_threshold` | `95.0` | **`88.0`** | 95.0 与旧口径上限 95.02 只差 0.02 分 ⇒ 永久红（E8）；域内现值 90.84，88.0 留 ≈2.8 分余量 |
| `days` | `365` | 不变（仍被 `MAX_CHECK_DAYS=90` 钳制） | 窗口不属本需求 |
| `stock_limit` / `check_all_stocks` | 不变 | 不变 | 扫描范围不属本需求——**扫描仍覆盖全库**（死标的要能被识别出来） |

- **执行方式**：一条 `UPDATE quant.scheduler_tasks SET params = params || '{"quality_threshold": 88.0}' WHERE id = 232;`
  （jsonb 合并，幂等）；回滚 = 改回 `95.0`（旧值已记录在此表与本文档）。
- **缺省值同步**：`_normalize_params` 里 `quality_threshold` 的代码缺省从 `90.0` 改为 **`88.0`**，
  新增 `d_grade_threshold`（缺省 **20**）、`coverage_info_threshold`（缺省 **97.0**）、
  `backfill_min_sample`（缺省 **10**）；四个键都进 `effective_params` 与 `param_notes`（可核验）。
- **不需要**改 `apscheduler_jobs`：本键只在任务执行时读取，不进 APScheduler jobstore。

## 6. 内存事实的形状：`per_symbol`（serves: FR-2）

`DataQualityService.check_data_quality` 新增返回 `per_symbol`，形状固定（**不外传、不入库**）：

```python
per_symbol: dict[str, dict] = {
    "600519": {
        "coverage_rate": 100.0,        # float 0..100，来自 gap_info
        "missing_days_count": 0,       # int，来自 gap_info
        "quality_score": 93.33,        # float 0..100（= 现 accuracy_score）
        "overall_score": 97.78,        # float 0..100
        "grade": "A",                  # 'A+'|'A'|'B'|'C'|'D'
        "has_duplicates": False,
        "has_anomalies": True,
        "anomaly_unknown": False,
    },
    # ... 全量 N 条（今日 5686）
}
```

- **`grade` 只算一次**：`overall_score` → `_calculate_grade` 的调用从 `_persist_quality_audit` 内部
  上提到循环内一次计算，审计写入与告警统计**消费同一个值**（避免"同一件事两处实现"，本仓反复踩）。
- **键集**：上述 8 个键只增不改；`per_symbol` 的存在本身就是新契约，调用方若不用可忽略。

## 7. 不写什么（负向契约）（serves: FR-3, FR-5）

1. **不写"域快照"表/列**：域是现算视图，不是持久状态（§1）。
2. **不写"已通知过掉出"标记**：靠 `gap ∈ [1,4]` 天然只亮相 4 天（architecture.md §2.1）。
3. **不写 `per_symbol` 进任何持久层**（§4 负向契约 1）。
4. **不在 `kline_data_quality` 加 `run_id`**：本次告警统计已改为读内存事实，
   不需要靠"按 run 切分审计行"来避免重复计数——加列属范围外。
5. **不改 `data_gap_detector` 的返回键**（`total_trading_days` / `avg_coverage_rate` 等）——
   它是既有契约，本需求只让消费者改用它真实的键名。
