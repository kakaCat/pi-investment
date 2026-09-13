# 错误事件处置：数据契约违约 quant.index_daily:000300.SH（freshness）

- **事件 ID**：`81d8f56c-47cb-494d-a240-625a5a522d80`（source=v2，severity=high，error）
- **处置窗口**：w-32314d00（投资脑 investor）
- **处置时间**：2026-09-13
- **关联事件**：`397def4e244c4d71`（同因，表级契约 `quant.index_daily` 整表 max(trade_date)）——同一根因两个口径，一并消除

## 1. 现象与复现（证据）

契约判定器（launchd `com.pi-investment.data-contracts-check`，每日 23:40）实测输出：

```
./venv/bin/python tools/check_data_contracts.py --dataset "quant.index_daily:000300.SH"
  status=fail severity=high
  detail: trade_date 最新=2026-09-10，market_latest=2026-09-11，滞后 1 自然日（容忍 ≤ 0）
  → exit 1；error_events UPSERT(+1) data-contract:4b9cdeef616626d9 occurrence_count=2→3
```

库内事实（psycopg2 直查 quant_investment）：

```
index_daily by source: [('sina:stock_zh_index_daily', min 2025-08-07, max 2026-09-10, 2136 行,
                         last updated_at 2026-09-11 16:30:04), ...]
每天行数：09-08 5502 / 09-09 5501 / 09-10 5499 / 09-11 5248   ← market_latest=2026-09-11
```

即：**个股日线已到 09-11，指数日线全表停在 09-10**。

## 2. 根因（代码/配置定位）

1. `infrastructure/jobs/kline_update_job.py` 的个股 K 线同步（`update_gem_klines`，由
   20:30 的 in-process `evening_pipeline` 驱动）通过 `utils.symbol_classifier.index_symbols_for_exclusion`
   **显式排除指数**（daily_klines 有 CHECK 禁止指数行，指数已自 2026-09-11 分表到 `quant.index_daily`）。
2. 指数的唯一采集通道 = launchd `com.pi-investment.index-daily-refresh`（工作日 **16:30**）→
   `tools/backfill_index_daily.py --days 30`。
3. 该脚本**没有任何新鲜度判定**：抓到什么写什么，写不进新数据也 `exit 0`。
   实测 09-11 那次采集日志（`logs/index-daily-refresh.log`，mtime 09-11 16:30）：

   ```
   [index] 000300.SH  (sh000300) 写入   22 行，最新 2026-09-10
   ...（8 个指数全部"最新 2026-09-10"）
   ```

   16:30 时新浪尚未发布当日指数 EOD（本次修复实测：09-13 采同一接口，09-11 数据已在），
   于是"跑成功 + 数据是旧的"：launchd 状态 0、无告警，表静默冻结。
4. 契约的 freshness 语义正是 `max(trade_date) ≥ market_latest(max_lag_days=0)`，
   而 09-11 / 09-12 两次 23:40 判定都发生在"下一趟 16:30 采集之前"→ 必然违约（频次 2）。

**根因类型：配置/定时错配 + 采集脚本缺少新鲜度自检（不是外部依赖故障，也不是误报）。**

## 3. 落地动作

### 3.1 立即修复数据（本次执行，幂等）

```
./venv/bin/python tools/backfill_index_daily.py --days 30 --require-fresh
[index] 000300.SH  (sh000300) 写入   21 行，最新 2026-09-11
...（9 个指数全部 2026-09-11）
[index] freshness: market_latest=2026-09-11 → OK（全部指数已追平）
EXIT=0
```

### 3.2 让"数据旧"变成可见失败（`tools/backfill_index_daily.py`）

新增 `--require-fresh`：写完后与 `quant.daily_klines` 的 `market_latest`
（行数 ≥500 的完整交易日口径，与契约判定器同源）逐键比对，未追平 **exit 3**。
新增 `--retry-until HH:MM` / `--retry-interval`：截止时刻前反复重采（upsert 幂等），
**不必猜"新浪几点发布当日指数 EOD"——发布即采到**。
新增纯函数 `select_rows` / `evaluate_freshness` / `parse_deadline` 并补 10 条单测。

### 3.3 修复定时错配（新 launchd 作业）

`deployment/launchd/com.pi-investment.index-daily-refresh-final.plist`（原件随仓库留档；`scripts/` 被 .gitignore 忽略，勿放那里。已 bootstrap 到
`~/Library/LaunchAgents`，`launchctl print` 确认 loaded、state=not running、calendar 5 档）：

- 工作日 **20:50** 启动，`--days 30 --require-fresh --retry-until 23:15 --retry-interval 900`
- 每 15 分钟重采，直到追平；**23:15 仍未追平 → exit 3**（launchctl 状态 + 日志可见）
- 23:15 早于契约判定器 23:40 → 判定时数据已就位
- 原 16:30 best-effort 作业保留（多跑无害、可兜底）

### 3.4 连带发现并修掉的第二个静默滞后键

严格模式第一版只补了 `000300.SH`，立刻报出：

```
[index] freshness: market_latest=2026-09-11 → STALE
[index]   STALE 399300.SZ: 最新=2026-09-10 < market_latest=2026-09-11
```

`399300.SZ`（深市侧沪深300，2026-09-11 分表时从 daily_klines 迁来的遗留键，
被 `utils/symbol_classifier` 当作指数码使用）**在索引表里却没有任何刷新通道**——
它拖住的正是表级契约 `quant.index_daily`（= 事件 `397def4e244c4d71`）。
已把 `399300.SZ → sz399300` 加入采集映射（实测与 sh000300 逐日收盘一致），并加回归测试。

## 4. 验证（修复后实测）

```
./venv/bin/python tools/backfill_index_daily.py --days 30 --require-fresh --retry-until 23:15
[index] freshness: market_latest=2026-09-11 → OK（全部指数已追平）        EXIT=0

./venv/bin/python tools/check_data_contracts.py --json
  ... 全量契约（含 quant.index_daily:000300.SH 与表级 quant.index_daily）
  "error_events": [],  "exit_code": 0                                  ← 违约清零

./venv/bin/python -m pytest tests/test_backfill_index_daily.py -q
  10 passed in 0.11s
```

## 5. 未决 / 建议

- **23:15 前新浪是否一定发布**：本次用 `--retry-until` 规避了"猜发布时刻"，
  但仍假设发布发生在 23:15 前。若未来该作业连续 exit 3，说明该假设不成立，
  届时应换更及时的源（腾讯 `stock_zh_index_daily_tx` / 东财）或按需放宽契约
  `max_lag_days`——**必须先有该作业的失败记录再改，不预先放宽**。
- 契约判定器（23:40）与采集收尾（23:15）之间存在 25 分钟窗口；
  若采集重试耗尽仍失败，契约会照实报违约（这是期望行为，不是重复告警）。
- `399300.SZ` 与 `000300.SH` 是同一指数的两份存储（历史遗留）；
  如需去重，应先核实谁是真实读取方（`kline_repository.get_index_daily_klines`）。
