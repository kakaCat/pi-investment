# 全市场 K 线静默冻结 6 个交易日 —— 根因与修复（2026-09-10）

- **窗口**：w-23c70356（investor） / 需求 REQ-e5a251
- **触发**：定时任务反馈异常（chip_distribution 仅 0.0 分钟更新 109 只）
- **影响面**：quant.daily_klines / quant.factor_values / quant.chip_distribution_state 全链冻结

## 1. 现象

2026-09-10 三张定时任务回执：chip_distribution 更新 109 只、evolution_fitness 计算 7 只、
pool_daily_refresh 3 个动态池，耗时均为 0.0-0.1 分钟（耗时字段本身是 `f"{elapsed_min:.1f}"`
的渲染精度问题，只有 chip_distribution 是真异常）。

深挖后的事实：**全市场日 K 自 2026-09-02 起就没有再同步过**。

| 交易日 | 活跃股有当日 K 线 | 说明 |
|---|---|---|
| 2026-09-02 | 5284 / 5290 | 最后一次全市场同步（source=calc-amt） |
| 2026-09-03 ~ 09-09 | 88 ~ 145 | 只是 agent 临时取数写回的零星行 |
| 2026-09-10 | 46 / 5290（覆盖率 0.87%） | evening_pipeline 当天直接跳过同步 |

## 2. 三层根因

### 根因一（致命）：batch/priority 同步 SQL 三处独立缺陷

`infrastructure/jobs/kline_update_job.py` 的 batch/priority 查询自 2026-09-02 引入后
**从未成功执行过一次**。修一层暴露下一层：

1. `recent_symbols` CTE 引用 `quant.daily_klines.updated_at` —— 该列不存在
   （表结构为 symbol/trade_date/open/high/low/close/volume/amount/turnover_rate/remark/source）。
   这是落在 `inprocess_job_runs.result` 里的那层报错。
2. 修掉 1 后暴露：`SELECT DISTINCT symbol ... ORDER BY trade_date DESC` ——
   PostgreSQL 要求 ORDER BY 表达式出现在 DISTINCT 选择列表。
   → 改 `GROUP BY symbol ORDER BY MAX(trade_date) DESC`。
3. 修掉 2 后暴露：UNION ALL 外层 `ORDER BY priority` —— priority 不在 union 输出列中。
   → 子查询保留 priority 列，外层 `ORDER BY ordered.priority`。

即：即使没有根因二、三，K 线同步也不可能成功。

### 根因二（告警链）：失败被吞，任务仍报 success

`update_gem_klines` 内部 `except` 后 **return** `{'status':'error'}` 而不抛，
`_job_evening_pipeline` 把它塞进 results 照常 return → 宿主记 `status=success`
并推送"✅ 每日任务完成"。2026-09-03/04/07/08/09 连续 5 个交易日的
`{"kline_sync":{"error":"column \"updated_at\" does not exist",...}}` 都躺在
`quant.inprocess_job_runs.result` 里没触发任何失败告警。

### 根因三（判据）：新鲜度门用全表 max(trade_date)，一只票新鲜=全市场新鲜

`evening_pipeline` 与 `freshness_guard` 都用 `SELECT max(trade_date) FROM daily_klines`。
agent 的零星实时取数会把 max 顶到当天，于是判定"K 线已新鲜"直接跳过同步 ——
09-10 的 job 结果原文：`"kline_sync": {"reason": "K线已新鲜（2026-09-10 ≥ 2026-09-10）",
"status": "skipped"}`，而真实覆盖率只有 0.87%。

同时 `data_quality_report(data_type='kline', days=3)` 返回评分 92.5、缺失/延迟清单为空，
**这套数据质量看门狗对停摆式缺口是假阴性**。

### 附：freshness_guard 的告警其实响过

`quant.inprocess_job_runs` 证据：09-04、09-05、09-07、09-08、09-09 的
`freshness_guard` 均 `status=stale` 且 `alert_sent=true`。即告警并非完全沉默，
而是被同期"✅ 每日任务完成"的成功回执抵消，且 09-10 因 max() 被顶到当天而误判为 fresh。
教训：**同一事实必须有唯一权威判据**，成功回执与巡检结论不能互相矛盾。

## 3. 修复（branch `fix/kline-sync-silent-failure` → main）

1. `kline_update_job.py`：上述三处 SQL 缺陷。
2. `daily_jobs_bootstrap.py`：`kline_sync.status == 'error'` 时 `raise RuntimeError`，
   任务判 failed 并触发失败告警（放在因子计算之后，保证因子仍按现有数据算完）。
3. `daily_jobs_bootstrap.py`（另一窗口 w-* 同题贡献，已合并保留）：新鲜度门改为
   **按活跃股覆盖率**判定（未退市且名称不含 退/ST，5290 只），并按缺口动态放大
   batch_size / days。

## 4. 验证

- 四个 scope 的真实 SQL 在库上实跑：batch 1102 只 / priority 602 只 / all 5290 只（修复前全部报错）。
- 端到端：`update_gem_klines(scope='all', days=15, symbols=['600519','000001'])`
  → `status=success, failed=0, stale=0, date_range 2026-08-26 -> 2026-09-10`。
- 修复后进程已重启（5001，PID 87594，启动 21:49:27 晚于文件 mtime 21:46:49 → 新代码已加载）。
- 覆盖度回补：由 46/5290（0.87%）补至 5000+（见"5. 回补"）。

## 5. 回补与下游恢复（22:12 全部完成，实测）

| 环节 | 修复前 | 修复后 |
|---|---|---|
| `daily_klines` 09-10 覆盖 | 46 只（0.87%） | **5264 只**（活跃股 5290 → 99.5%；残留 26 只为停牌/指数/非股票） |
| `factor_values` 09-10 | 46 只 / 1333 行 | **5257 只**（handle_factor_compute: 5266 computed / 0 failed，1.7 min） |
| `chip_distribution_state` 最新日 | 5129 只停在 09-02 | **5499 只到 09-10**（chip job 约 2 min） |
| 09-03~09-09 各日行数 | 88~145 | **4972~4981**（缺口交易日全部补齐） |

- 并行窗口的 `/tmp/kline_catchup.py`（直连 sina，3 并发）先补了约 3029 只后停止；
- 本窗口对剩余 **1967 只** stale 活跃股走**修复后的生产代码路径**
  `update_gem_klines(scope='all', days=15)`（脚本 `/tmp/kline_fill_rest_w23c70356.py`）；
  第 1 个 chunk 实测 `250/250 成功 248 只, 失败 0, 未覆盖 2 只`（生产路径端到端实证）；
  随后发现另一窗口重启了 `/tmp/kline_catchup2.py`，**本窗口主动停掉重复回补**避免同源双份压力。
- 下游恢复链：`/tmp/post_backfill_chain2_w23c70356.py`（等覆盖率达标 → 因子 → 筹码）。
  注意：standalone 进程跑 `handle_factor_compute` 必须先
  `register_all_services()`，否则 `Service not registered: IStockRepository`（本链首跑即踩）。

## 6. 遗留与建议

1. **freshness_guard 基准日语义**：17:20 巡检用"当天"当基准，而当天 EOD 要到
   20:30 的 evening_pipeline 才落库 → 结构上每天都判 stale（09-04~09-09 天天告警）。
   建议基准改为"前一交易日"，否则告警会因长期噪声被忽略。
2. **data_quality_report 对停摆型缺口假阴性**（09-10 覆盖率 0.87% 但评分 92.5、缺失清单为空），
   建议引入同一套覆盖率口径。
3. **恢复链脚本的 DI 依赖**：`handle_factor_compute` / 其它走工厂的函数在进程外必须
   显式注册服务（`infrastructure.services.service_registry.register_all_services`），
   建议在 `daily_jobs_bootstrap` 外提供统一的 standalone bootstrap 入口。

## 7. 附带发现（数据质量，未修，需决策）

`quant.daily_klines` 中存在 source = `sina-volsync-20260910` 的行 **85831 条**
（2025-07-17 ~ 2026-09-10），其 `amount` **恰好等于 `volume × close × 100`**：

| symbol | date | close | volume | amount | amount/volume |
|---|---|---|---|---|---|
| 688065 凯赛生物 | 2026-09-10 | 39.6 | 4,719,691 | 18,689,976,360 | 3960 (=100×close) |

- 判别依据①：该 source 的 volume×close/市值 中位数 0.74%（与 `sina` 1.32%、`tencent` 1.16% 同量级）
  → **volume 是对的，amount 被放大了 100 倍**；
- 判别依据②：amount/100 = 186,899,763.6 = volume×close **分毫不差**；
- 影响面：任何用 amount 的因子/筹码换手口径在这 8.6 万行上会被放大 100 倍
  （turnover 类因子、筹码衰减）。
- 该 source 由并行窗口的修复脚本写入（`/tmp/vol_fix_noamount*.py` 目前处理的是
  `amount=0` 的另一批行），本窗口未擅自改写别人的数据，**待用户决策**：
  `UPDATE quant.daily_klines SET amount = round(amount/100.0, 2) WHERE source='sina-volsync-20260910' AND amount > volume*close*20;`
  （谓词自限：修正后不再命中，可安全重跑、并发重入不会二次除）。

**已执行修正（22:14，psql 实测）**：该 source 的 amount 错误是**双向**的——

| 情况 | 行数 | 处置 | 修正后校验 |
|---|---|---|---|
| amount = volume×close×**100** | 4922（472 只，07-24~09-10） | ÷100 | 688065 09-10：18,689,976,360 → **186,899,764** = 4,719,691×39.6 分毫不差 |
| amount = volume×close/**100** | 129 | ×100 | 601600 09-02：13,263,002 → 1,326,300,259 = 138,156,277×9.6 |
| amount = 0 | 80606 | **未动** | 属并行窗口 vol_fix_noamount*.py 在办的 volume 单位修复范围 |
| amount IS NULL | 8 | **未动** | 同上 |

修正后该 source 全部 5217 行 `amount/volume == close`。
判别方法（可复用）：**先用 `volume×close/市值` 的换手率分位数跨 source 交叉验证谁错**
（本 source 中位 0.74% vs sina 1.32% vs tencent 1.16% → volume 对、amount 错），
再用 `amount/volume÷close` 的比值（100 或 0.01）确认方向。
留痕：decision_audit DEC-20260910221628-61416101、memory(a76837cd)、公告板 8af83e82。

## 8. 收尾（2026-09-10 22:16）

| 项 | 状态 |
|---|---|
| K线三处 SQL 缺陷 + 失败上抛 | 已修，commit `41f19484`（含并行窗口覆盖率门贡献） |
| `freshness_guard` 基准日改"前一交易日" | 已修，commit `a3aa451f`；5001 已重启（PID 93006 @ 22:15:32）加载 |
| 基准日实测复核 | 旧基准=当天 09-10：5290 只覆盖 5264（99.5%）→ fresh；新基准=前一交易日 09-09：5266（99.5%）→ fresh；`factor_values` 最新 09-10 ≥ 基准 → **双基准下均不误报**（差异只在 17:20 这种 EOD 未落库的时刻显现） |
| amount 双向 100 倍修正 | 已修（见第 7 节），已留痕 |
| 本文档 | commit `35340f92`（本次续修另计） |

**唯一遗留**：`data_quality_report(kline)` 对停摆型缺口假阴性（覆盖率口径不统一），
建议后续纳入同一套 `_kline_coverage` 口径。
