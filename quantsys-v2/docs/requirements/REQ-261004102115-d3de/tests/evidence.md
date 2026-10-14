# 测试证据 · REQ-261004102115-d3de

**日期**：2026-10-04 ｜ **Python**：`venv/bin/python`（3.13.14）｜ **pytest**：9.1.1 ｜ **机器**：同一台

---

## 1. 改前基线：告警确实在响（可复现）

```bash
./venv/bin/python tools/health_probe.py --dry-run
# → {"healthy": false, …, {"name": "kline_freshness", "ok": false,
#      "expected": "2026-10-02", "kline_latest": "2026-09-30", "lag_days": 2, "max_lag_days": 1}}
#    告警正文：K线最新 2026-09-30 / 应有 2026-10-02，滞后 2 天
```

数据侧事实（同一时刻）：`SELECT max(trade_date) FROM quant.daily_klines` → `2026-09-30`，
当日覆盖 5276 只（与 09-24/28/29 相同）——**数据是完好的，判据是错的**。

## 2. 改后逐条验收命令与输出

```bash
# FR-1 + FR-2：误报消除
./venv/bin/python tools/health_probe.py --dry-run
# → {"healthy": true, "checks": [ …, {"name": "kline_freshness", "ok": true,
#      "expected": "2026-09-30", "expected_source": "calendar", "expected_degraded": false,
#      "kline_latest": "2026-09-30", "factor_latest": "2026-09-30", "lag_days": 0}]}
#   EXIT=0

# 负向：判据没被改空
./venv/bin/python tools/health_probe.py --dry-run --max-lag-days -1 ; echo EXIT=$?
# → EXIT=2

# FR-1 语义（七组日期，真实数据源）
./venv/bin/python -c "…last_closed_trading_day(ref)…"
# 2026-10-04 10:18 -> 2026-09-30 calendar_table False
# 2026-10-02 16:00 -> 2026-09-30 calendar_table False
# 2026-10-08 15:29 -> 2026-09-30 calendar_table False
# 2026-10-08 15:30 -> 2026-10-08 calendar_table False
# 2026-09-25 20:00 -> 2026-09-24   ｜ 2026-09-26 10:00 -> 2026-09-24
# 2026-09-29 10:00 -> 2026-09-28

# FR-3 进程内同源出口
./venv/bin/python -c "…_last_trading_day(datetime(2026,10,2,17,20))…"
# → 2026-09-30（修复前为 2026-10-01）

# 回归集合（含既有守卫用例与新回归锁）
pytest tests/ -q -k "freshness or trading_day or health_probe"
# → 92 passed, 6269 deselected（notify-guard 汇总 intercepted=0 egress=0 offenders=[]）
```

## 3. 数据侧回填证据

```bash
./venv/bin/python tools/refresh_trading_calendar.py --dry-run
# [calendar] 官方日历（AKShare）: 1272 个交易日（2021-10-08 ~ 2026-12-31）
# [calendar] 真源 daily_klines: 7730 个交易日（1994-03-01 ~ 2026-09-30）
# [calendar] --dry-run：K 线源将为 [SSE, SZSE, ALL] 各写入 7730 行；官方日历将补写最多 61 个未来交易日 × 3

./venv/bin/python tools/refresh_trading_calendar.py
# [calendar] PK 状态: altered   ← (trade_date) → (trade_date, exchange)
# [calendar] 官方日历并集补写 183 行（含未来交易日 61 天）
# [calendar] 表内总行数: 23373

psql -h 127.0.0.1 -U mac -d quant_investment -At \
  -c "SELECT count(*), min(trade_date), max(trade_date) FROM quant.trading_calendar;" \
  -c "SELECT trade_date FROM quant.trading_calendar WHERE exchange='SSE' AND trade_date BETWEEN '2026-09-28' AND '2026-10-12' ORDER BY 1;"
# 23373|1994-03-01|2026-12-31
# 2026-09-28 / 09-29 / 09-30 / 10-08 / 10-09 / 10-12     ← 国庆 10-01~10-07 与中秋 09-25 均不在
```

## 4. 反向验证（回归锁必须真能抓）

```bash
# 把解析器改成"永远走回退"（模拟修复前的口径）
./venv/bin/python -m pytest tests/test_trading_day_resolver.py -q
# → 10 failed, 3 passed

# 还原后（shasum 与改动前逐字节一致）
459886bb…  application/services/trading_day_resolver.py
./venv/bin/python -m pytest tests/test_trading_day_resolver.py -q
# → 13 passed
```

## 5. 迁移与兼容实测

```bash
./venv/bin/python -c "…load_trading_calendar_from_db('SSE')…"
# 7791 个交易日，max=2026-12-31；日志中 trading_calendar_empty_fallback_to_klines 出现 0 次

./venv/bin/python -c "import application.services.scheduler_tasks_data, adapters.inbound.fastapi_app.daily_jobs, adapters.inbound.fastapi_app.daily_jobs_bootstrap"
# 三个生产导入方均 ok（_last_trading_day 签名未变）

git diff --name-only | grep -E 'deployment/launchd|pyproject.toml'
# NONE
```

## 6. 覆盖标注（covers）

本需求量级：6 张父卡 + t1 名下 3 张子卡。逐张对应到本文档中的证据：

- covers: t-dc66e2 — 解析器实现（§2 七组日期、§4 反向验证）
- covers: t-8e4de7 — 同上（研发段）
- covers: t-2aae82 — §1 改前基线 + §2 语义对照（复核段）
- covers: t-598ad3 — §4 反向验证（测试段）
- covers: t-b952d0 — §2 回归集合 92 passed + §4 反向验证 10 failed
- covers: t-f062d4 — §2 探针 --dry-run（exit 0）与负向（exit 2）
- covers: t-1d780d — §2 `_last_trading_day(datetime(2026,10,2,17,20))` → 2026-09-30
- covers: t-ed8425 — §3 回填 23373 行 / 覆盖至 2026-12-31
- covers: t-4caf2a — §5 迁移与兼容实测（管道读表、导入方、diff 面）

汇总一行（便于机器读取）：

covers: t-dc66e2, t-8e4de7, t-2aae82, t-598ad3, t-b952d0, t-f062d4, t-1d780d, t-ed8425, t-4caf2a
## 7. 端到端证据（验收返工 v1-8）

```bash
# 与 launchd 同一条命令（独立进程 + 仓库为工作目录 + dry-run 不外发）
pytest tests/e2e/test_health_probe_e2e.py -q
# → 2 passed, 1 warning in 9.06s
#    notify-guard intercepted=0 egress=0 offenders=[]

# 场景一断言（跨进程核对）：脚本给出的应有交易日 == 进程内唯一口径
# 场景二断言（负向控制）：--max-lag-days <lag-1> → 退出码 2 + "[--dry-run] 以下告警**未发送**"
```

初版写法的一处自查纠正：第一版负向控制用固定 `--max-lag-days -1`，
在 pytest 子进程（`PGDATABASE=quant_test`，测试库行情是合成的、lag 可能为负）下会得 exit 0 而误判。
现改为**按实测 lag 现算容差**（lag-1），与"库里数据新不新鲜"无关，永远必然不及格。

覆盖标注补充：

- covers: t-391941 — 本文件 §7（端到端两场景）
