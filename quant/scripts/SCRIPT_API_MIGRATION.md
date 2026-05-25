# 脚本→API 迁移映射表

## 策略分类

| 策略 | 适用场景 |
|------|---------|
| **HTTP Client** | 脚本改为 `requests` 调 Flask，零 quantsys import |
| **API Trigger (sync)** | Flask 端点直接执行（<30s），脚本 fork 调用 |
| **API Trigger (async)** | Flask 端点 `subprocess.Popen`，返回 `job_id`，轮询状态 |
| **Keep Direct** | ETL 写 DB 必须直连，但加 API 触发端点 |

---

## 完整映射

### 1. ETL / 数据摄取（Keep Direct + API Trigger）

| 脚本 | 行数 | quantsys imports | 策略 | Flask 端点 |
|------|------|-----------------|------|-----------|
| `daily_update.py` | ~90 | `Database`, `KlineFetcher` | Keep Direct | `POST /api/data/update` (new) |
| `download_5year_data.py` | ~100 | `Database`, `KlineFetcher` | Keep Direct | `POST /api/data/download-history` (new) |
| `fetch_hs300_data.py` | ~120 | `Database`, `StockListFetcher`, `KlineFetcher` | Keep Direct | `POST /api/data/fetch-hs300` (new) |
| `sync_portfolio_stocks.py` | ~250 | `Database`, `KlineFetcher` | Keep Direct | `POST /api/data/sync-portfolio` (new) |
| `sync_watchlist_stocks.py` | ~260 | `Database`, `KlineFetcher` | Keep Direct | `POST /api/data/sync-watchlist` (new) |

> ETL 脚本必须直接操作 DB（数据还没入库），不能走 API。但 Flask 会新增触发端点，让 scheduler 用 HTTP 触发。

### 2. 计算/处理

| 脚本 | 行数 | quantsys imports | 策略 | Flask 端点 |
|------|------|-----------------|------|-----------|
| `calculate_factors.py` | 262 | `Database`, `factors.*` | API Trigger (sync) | `POST /api/compute/factors` (new) |
| `calculate_historical_factors.py` | 306 | `Database`, `factors.*` | API Trigger (sync) | `POST /api/compute/historical-factors` (new) |
| `calculate_trading_days.py` | 145 | `Database` | HTTP Client | 内联到 `/api/compute/factors` |
| `generate_signals.py` | 402 | `Database`, `confidence_calibration.*` | HTTP Client (refactor) | `POST /api/signals/generate` (new) → 计算后写 signals.json，`GET /api/signals` 读取 |
| `ml_retrain.py` | 590 | `Database`, `ModelTrainer`, `TimeSeriesCV`, `HyperparameterTuner`, `FeatureEngineer` | API Trigger (async) | `POST /api/ml/retrain` (new) → 异步，`GET /api/jobs/<id>` 查状态 |
| `weekly_backtest.py` | 662 | `BacktestEngine`, `RSIReversal`, `MACross`, `BollingerBreakout` | API Trigger (async) | `POST /api/backtest/run` (new) → 异步，`GET /api/jobs/<id>` |

### 3. 分析（→ HTTP Client）

| 脚本 | 行数 | quantsys imports | 策略 | Flask 端点 |
|------|------|-----------------|------|-----------|
| `analyze_stock_factors.py` | 308 | `Database` | **HTTP Client** | `GET /api/stock/<s>/factors` ✅ 已有 |
| `ml_predict.py` | 440 | `Database` | **HTTP Client** | `GET /api/stock/<s>/ml-predict` ✅ 已有 |
| `analyze_feature_importance.py` | 179 | 无（被 Flask import 用） | **HTTP Client** | `GET /api/feature-importance` ✅ 已有 |

### 4. 报告/风控

| 脚本 | 行数 | quantsys imports | 策略 | Flask 端点 |
|------|------|-----------------|------|-----------|
| `daily_report.py` | 438 | `Database` | **HTTP Client** | `GET /api/signals` + `GET /api/report/daily` ✅ |
| `generate_enhanced_report.py` | 281 | `Database` | **HTTP Client** | 复用 `/api/signals` + `/api/stock/<s>/factors` |
| `risk_check.py` | 355 | `Database`, `StopLossManager`, `PositionManager` | **HTTP Client** | `POST /api/risk/check` (new) |
| `weekly_performance.py` | 576 | 无（独立） | **HTTP Client** | `POST /api/performance/weekly` (new) |

### 5. 基础设施

| 脚本 | 行数 | 策略 |
|------|------|------|
| `scheduler.py` | 380 | 所有 `subprocess.run(['python3', script])` → `requests.post(endpoint)`。启动时先 `GET /api/health`。 |
| `test_*.py` | N/A | 测试脚本，改为调 API |

---

## 新增端点汇总（Phase 1）

```
POST /api/jobs/status           → 查询异步任务状态 {job_id}
POST /api/data/update           → 触发每日数据更新
POST /api/data/download-history → 触发5年历史下载
POST /api/data/fetch-hs300      → 触发HS300数据获取
POST /api/data/sync-portfolio   → 同步持仓
POST /api/data/sync-watchlist   → 同步自选
POST /api/compute/factors       → 触发因子计算
POST /api/compute/historical-factors → 触发历史因子计算
POST /api/signals/generate      → 生成交易信号（写 signals.json）
POST /api/ml/retrain            → 触发ML重训练（异步）
POST /api/backtest/run          → 触发回测（异步）
POST /api/risk/check            → 风险检查
POST /api/performance/weekly    → 周度绩效
```

---

## 启动顺序（最终态）

```
1. python3 quant/api/server.py          ← Flask :5001 启动
2. python3 quant/scripts/scheduler.py   ← 启动时 GET /api/health，等待200后注册cron
3. scheduler cron触发 → POST /api/xxx   ← 所有任务走HTTP
```

## 重构后约束

- `quant/scripts/` 中零个 `from quantsys`（除 Flask server.py 本身）
- ETL 脚本保留 quantsys import（写DB需求），但通过 scheduler HTTP 触发
- scheduler 不再有 `subprocess.run(['python3', ...])`
