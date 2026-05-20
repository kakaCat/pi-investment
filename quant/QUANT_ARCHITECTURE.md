# Quant System Architecture (post-refactor)

## 变更日期
2026-05-19

## 目标
消除"脚本绕过Flask API直接import quantsys"的架构冗余，让Flask API成为唯一的quantsys集成点。

## 结果

### 重构前
```
17 个脚本直接 import quantsys（绕过Flask API）
Flask API 仅被 TypeScript 前端使用
三条数据路径：Script→quantsys / Flask→quantsys / TS→Flask→quantsys
```

### 重构后
```
统一入口: Flask API → quantsys

┌──────────────┐     HTTP      ┌──────────────┐
│  Scripts      │──────────────→│  Flask API    │
│  (HTTP Client)│               │  :5001        │
└──────────────┘               └──────┬────────┘
                                      │
┌──────────────┐                      │ import
│  TypeScript   │─────HTTP───────────→│
│  Agent Tools  │                     │
└──────────────┘               ┌──────▼────────┐
                               │  quantsys      │
┌──────────────┐               │  (core lib)    │
│  ETL Scripts  │───spawn─────→│                │
│  (Flask子进程) │              └──────┬─────────┘
└──────────────┘                      │
                               ┌──────▼────────┐
                               │  SQLite DB     │
                               └───────────────┘
```

## 分类详情

### HTTP 客户端（15个，零 quantsys import）
| 脚本 | 调用端点 |
|------|---------|
| analyze_stock_factors.py | GET /api/stock/<s>/factors |
| ml_predict.py | POST /api/ml/predict-batch |
| analyze_feature_importance.py | GET /api/feature-importance |
| risk_check.py | POST /api/risk/check |
| daily_report.py | GET /api/signals + GET /api/data-status |
| generate_enhanced_report.py | GET /api/stock/<s>/factors |
| calculate_trading_days.py | GET /api/stocks/data-status |
| scheduler.py | 所有 API 端点（不再 subprocess） |

### ETL 直连（5个，Flask子进程触发）
| 脚本 | API 触发端点 |
|------|-------------|
| daily_update.py | POST /api/data/update |
| download_5year_data.py | POST /api/data/download-history |
| fetch_hs300_data.py | POST /api/data/fetch-hs300 |
| sync_portfolio_stocks.py | POST /api/data/sync-portfolio |
| sync_watchlist_stocks.py | POST /api/data/sync-watchlist |

### 计算/异步直连（5个，Flask子进程触发）
| 脚本 | API 触发端点 | 模式 |
|------|-------------|------|
| calculate_factors.py | POST /api/compute/factors | 同步 |
| calculate_historical_factors.py | POST /api/compute/historical-factors | 同步 |
| generate_signals.py | POST /api/signals/generate | 同步 |
| ml_retrain.py | POST /api/ml/retrain | 异步(job_id) |
| weekly_backtest.py | POST /api/backtest/run | 异步(job_id) |

## 新增 API 端点（14个）
```
POST /api/jobs/<job_id>          查询异步任务
POST /api/jobs                   列出任务
POST /api/risk/check             风险检查
POST /api/signals/generate       生成信号
POST /api/ml/predict-batch       批量ML预测
POST /api/ml/retrain             ML重训练(异步)
POST /api/backtest/run           回测(异步)
POST /api/data/update            数据更新
POST /api/data/download-history  历史下载
POST /api/data/fetch-hs300       HS300获取
POST /api/data/sync-portfolio    同步持仓
POST /api/data/sync-watchlist    同步自选
POST /api/compute/factors        因子计算
POST /api/compute/historical-factors 历史因子
POST /api/performance/weekly     周度绩效
```

## 启动顺序
```
1. python3 quant/api/server.py          ← Flask :5001
2. python3 quant/scripts/scheduler.py   ← 等待API就绪后注册cron
```

## 约束
- 任何新增脚本必须走 Flask API，禁止直接 import quantsys
- ETL/计算脚本通过 Flask 子进程触发，不作为独立脚本运行
- scheduler 不再使用 subprocess.run 调用业务逻辑
