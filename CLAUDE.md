# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI stock investment advisor (A-share / HK stocks) built on the `@mariozechner/pi-agent-core` SDK. Tri-component architecture:

- **`src/`** — TypeScript AI agent (primary). Interactive CLI/TUI with tool registry, Feishu bot integration, session management, and multi-layer system prompt builder.
- **`quant/`** — Python quant backend. Flask REST API (port 5002) + `quantsys` package: 18+ strategies, 62 factors, XGBoost/LightGBM ML pipeline, backtesting engine, risk checks.
- **`quant-web/`** — React dashboard (Vite + Ant Design + Recharts). Proxies `/api` to Flask backend on port 5002.

## Fixed IP / Port Convention

每个子项目使用固定的 127.0.0.1 地址 + 固定端口。**主分支上的 IP/端口不允许随意修改。** 如果发现主分支上的 IP 被改动，必须修复回以下固定值：

| 子项目 | 固定地址 | 配置方式 |
|--------|----------|----------|
| quant Flask API (v1) | `127.0.0.1:5002` | `QUANT_API_HOST` / `QUANT_API_PORT` 环境变量 |
| quantsys-v2 Flask API | `127.0.0.1:5001` | `QUANTSYS_API_HOST` / `QUANTSYS_API_PORT` / `QUANTSYS_API_URL` |
| quantsys-v2 WebSocket | `127.0.0.1:5003` | `QUANTSYS_API_HOST` / `QUANTSYS_WS_PORT` 环境变量 |
| quant-web Vite | `127.0.0.1:3000` | 代理 `/api` → `127.0.0.1:5002` |
| web-frontend Vite | `127.0.0.1:3001` | 代理 `/api` → `127.0.0.1:5001` |
| TypeScript Agent | N/A (CLI) | 通过环境变量连接各服务 |
| PostgreSQL | `127.0.0.1:5432` | `PGHOST` / `PGPORT` 环境变量 |
| Redis | `127.0.0.1:6379` | `REDIS_HOST` / `REDIS_PORT` 环境变量 |
| Kafka brokers | `127.0.0.1:19092-19094` | `docker/kafka-cluster.yaml` |

> **注意：** `quantsys-v2/` 和 `web-frontend/` 是各自独立的 git 仓库。`quantsys-v2` 是量化系统 v2（后继版本），`web-frontend` 是 Vue 3 + Element Plus 前端，直连 quantsys-v2 后端。

**Worktree 隔离规则：** 如果在 worktree 中做测试需要改 IP，必须在合并回主分支前改回固定值。不能在主分支上出现非固定 IP 的改动。

## Dev Commands

```bash
# TypeScript agent (primary app)
npm run dev              # Start TUI agent (tsx src/index.ts)
npm run feishu           # Start Feishu bot only

# Build & production
npm run build            # tsc -p tsconfig.build.json → dist/
npm start                # node dist/index.js

# Testing
npm test                 # Jest (ESM via --experimental-vm-modules)
npm run test:watch       # Jest watch mode
npm run test:coverage    # Jest with coverage
npm run test:quant-web   # vitest tests in quant-web/

# Python quant backend (v1)
cd quant && python api/server.py          # Start Flask API on port 5002
cd quant && python -m pytest tests/       # Run Python tests
cd quant && pip install -r requirements.txt

# Python quant backend (v2)
cd quantsys-v2 && python start_all.py               # 一键启动 REST API (5001) + WebSocket (5003)
cd quantsys-v2 && python api/server.py              # 单独启动 REST API on port 5001
cd quantsys-v2 && python api/server_websocket.py    # 单独启动 WebSocket on port 5003
cd quantsys-v2 && python -m pytest tests/           # Run Python tests

# React dashboard (quant-web)
cd quant-web && npm run dev    # Vite dev server on port 3000
cd quant-web && npm run build  # Production build

# Vue 3 dashboard (web-frontend)
cd web-frontend && npm run dev     # Vite dev server on port 3001
cd web-frontend && npm run build   # Production build
```

## Architecture

### TypeScript Agent (`src/`)

Layered architecture:

| Layer | Directory | Purpose |
|-------|-----------|---------|
| API | `src/api/` | Feishu bot, session manager, agent bootstrap |
| Config | `src/config/` | Model config (DeepSeek), paths, bootstrap |
| Core | `src/core/` | Agent loop, session, task management, system prompt |
| Domain | `src/domain/` | Cache system (namespaces: daily, intraday, quarterly, static) |
| Infrastructure | `src/infrastructure/` | Adapters (CLI, data sources), logging, monitoring, TUI |
| Services | `src/services/` | Business logic: quant, portfolio, compaction, scheduler, notification, intelligence |
| Tools | `src/tools/` | Agent tool definitions (core, invest, data, analysis) |
| Types | `src/types/` | TypeScript type definitions |

**Key patterns:**
- **CLI Adapter pattern**: `src/infrastructure/adapters/cli/` — data access wrapped as shell commands (BaseCliAdapter, PositionCliAdapter, TradeCliAdapter, AccountCliAdapter, WatchlistCliAdapter). Active migration is moving tools from direct service calls to CLI adapters.
- **Tool Registry**: Tools registered in `src/infrastructure/tools/`, categorized by domain.
- **8-layer system prompt**: Built in `src/services/intelligence/system-prompt-builder.ts` — Identity → Soul → Tools → Skills → Memory → Bootstrap → Runtime → Channel.
- **Data sources**: `src/infrastructure/data-sources/` — eastmoney, sina, sina-fx, stooq, technical indicators; falls back to Python/akshare bridge.

## Agent 工具系统

### 六层量化投资架构

项目采用六层架构组织 Agent 工具，对应量化投资的完整流程（2025-05-25 重构完成，从 61 个工具精简至 30 个）：

#### L1 数据管道层
统一的数据获取接口，支持股票基本信息、行情数据、财务数据：
- `data_fetch_stock` — 获取股票基本信息、实时价格、新闻、公告
- `data_fetch_kline` — 获取 K 线数据（日线、周线、月线）
- `data_fetch_financial` — 获取财务数据（利润表、资产负债表、现金流量表）

#### L2 因子工厂层
批量因子计算和分析：
- `factor_calculate` — 批量计算技术因子和基本面因子

#### L3 模型层（待实现）
机器学习模型训练和预测：
- 特征工程
- 模型训练
- 预测服务

#### L4 组合构建层
持仓管理和再平衡：
- `portfolio_rebalance` — 组合再平衡和持仓管理

#### L5 执行引擎层
订单管理和交易执行：
- `trade_manage_orders` — 订单管理和执行

#### L6 监控运维层
实时监控和告警：
- `monitor_alert` — 告警通知和风险监控

### 工具使用指南

新工具采用统一的命名规范：
- 数据管道：`data_*`
- 因子工厂：`factor_*`
- 模型层：`model_*`（待实现）
- 组合构建：`portfolio_*`
- 执行引擎：`trade_*`
- 监控运维：`monitor_*`

### 迁移说明

**重大变更（2025-05-25）**：旧工具系统已完全移除，请使用新的六层架构工具。

旧工具到新工具的映射：
- 股票查询相关 → `data_fetch_stock`
- K线数据相关 → `data_fetch_kline`
- 财务数据相关 → `data_fetch_financial`
- 因子计算相关 → `factor_calculate`
- 持仓管理相关 → `portfolio_rebalance`
- 订单管理相关 → `trade_manage_orders`
- 告警通知相关 → `monitor_alert`

工具实现位置：`src/infrastructure/tools/` 按层级组织（data/, factor/, portfolio/, trade/, monitor/）。

### Python Quant Backend (`quant/`)

Pipeline: resolve → data → factor → model → signal → risk → backtest → report.

- `quant/api/server.py` — Flask API with token auth and CORS (port 5002)
- `quant/api/quant_api.py` — CLI bridge for TypeScript → Python calls
- `quant/quantsys/` — Core package: strategies, factors, ml, risk, backtest, data, live

### React Frontend (`quant-web/`)

Vite dev server on port 3000 proxies `/api` to Flask (port 5002, configurable via `VITE_API_TARGET`). Component pages: Dashboard, Research, Model Training, Data Management, Operations.

## Environment Setup

Required env vars (see `.env.example`):

```bash
# DeepSeek API (OpenAI-compatible)
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=...          # SDK reads this key; must match DEEPSEEK_API_KEY
MODEL_ID=deepseek-chat

# Fixed IP — Flask quant backend
QUANT_API_HOST=127.0.0.1
QUANT_API_PORT=5002
PYTHON_BACKEND_URL=http://127.0.0.1:5002
PYTHON_BACKEND_TIMEOUT=30000

# Database (PostgreSQL required; SQLite removed)
QUANT_DB_PROVIDER=postgres
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=quant_investment

# Optional
FEISHU_APP_ID=...           # Feishu/Lark bot
TAVILY_API_KEY=...          # Web search
```

Node >= 22.0.0 required. Python >= 3.9 with packages from `quant/requirements.txt`.

## Testing

- **TypeScript**: Jest with `--experimental-vm-modules`. Test files co-located as `*.test.ts`. No jest.config file — config is in `package.json` jest section.
- **Python**: pytest, tests in `quant/tests/`. Coverage currently ~19%.
- **Frontend**: vitest, tests in `quant-web/src/`.

## Kafka (Optional)

Docker Compose cluster for event streaming: `docker compose -f docker/kafka-cluster.yaml up -d`. Topics: market.klines, market.ticks, signals.generated, orders.submitted, orders.filled, risk.alerts, events.store. Kafka UI on port 8080.

## Opportunity Radar Feature

### Overview
Real-time stock opportunity scanning with multi-dimensional scoring (technical, fundamental, capital).

### Architecture
- **StockPoolService**: Manages hot stock pool (沪深300 + 创业板50 + 科创50, ~400 stocks)
- **OpportunityScoringService**: Parallel scoring engine with ThreadPoolExecutor (10 workers)
- **Batch Queries**: Optimized database access (no N+1 queries)

### API Endpoint
`POST /api/signals/scan`

**Request:**
```json
{
  "stocks": ["600519.SH"],  // Optional: specific stocks to scan
  "minScore": 60,            // Optional: minimum score (0-100)
  "maxRiskLevel": "medium",  // Optional: low/medium/high
  "technical": ["rsi_oversold", "macd_golden_cross"],  // Optional filters
  "fundamental": ["low_pe", "high_roe"]                // Optional filters
}
```

**Response:**
```json
{
  "success": true,
  "opportunities": [
    {
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "score": 85,
      "technical_score": 90,
      "fundamental_score": 80,
      "capital_score": 75,
      "confidence": 0.85,
      "risk_level": "low",
      "signal_type": "buy",
      "timestamp": "2026-05-24T12:00:00"
    }
  ],
  "total": 1,
  "scanned": 400
}
```

### Scoring Algorithm
- **Technical Score (50%)**: RSI, MACD, Bollinger Bands, Volume
- **Fundamental Score (30%)**: PE, ROE, Gross Margin, Debt Ratio
- **Capital Score (20%)**: Volume growth, consecutive increases, volume ratio

**Formula**: `comprehensive_score = technical × 0.5 + fundamental × 0.3 + capital × 0.2`

### Performance
- 400 stocks: ~0.2 seconds
- Batch queries: 3-5 total queries
- Parallel processing: 10 workers
- Memory: 50-100 MB

### Files
- `quantsys-v2/services/stock_pool_service.py` - Hot stock pool management
- `quantsys-v2/services/opportunity_scoring_service.py` - Scoring engine
- `quantsys-v2/repositories/kline_repository.py` - Batch K-line queries
- `quantsys-v2/repositories/stock_repository.py` - Batch fundamental queries
- `quantsys-v2/api/server.py` - `/api/signals/scan` endpoint

## Active Conventions

- No linter/formatter configured (no ESLint, Prettier, or Biome).
- No CI/CD pipeline configured.
- git worktrees used for feature isolation (evolution branches, worktree-agent branches).
- Commit messages in Chinese are common.
- The agent uses DeepSeek which processes one tool call at a time — tool definitions should account for this.
