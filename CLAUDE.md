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
cd quantsys-v2 && python api/server.py    # Start Flask API on port 5001
cd quantsys-v2 && python -m pytest tests/ # Run Python tests

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

## Active Conventions

- No linter/formatter configured (no ESLint, Prettier, or Biome).
- No CI/CD pipeline configured.
- git worktrees used for feature isolation (evolution branches, worktree-agent branches).
- Commit messages in Chinese are common.
- The agent uses DeepSeek which processes one tool call at a time — tool definitions should account for this.
