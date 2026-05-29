# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI stock investment advisor (A-share / HK stocks) built on the `@mariozechner/pi-agent-core` SDK. Dual-component architecture:

- **`src/`** — TypeScript AI agent (primary). Interactive CLI/TUI with tool registry, Feishu bot integration, session management, and multi-layer system prompt builder.
- **`quant/`** — Python quant backend (v1). Flask REST API (port 5002) + `quantsys` package: 18+ strategies, 62 factors, XGBoost/LightGBM ML pipeline, backtesting engine, risk checks.

## Fixed IP / Port Convention

每个子项目使用固定的 127.0.0.1 地址 + 固定端口。**主分支上的 IP/端口不允许随意修改。** 如果发现主分支上的 IP 被改动，必须修复回以下固定值：

| 子项目 | 固定地址 | 配置方式 |
|--------|----------|----------|
| quant Flask API (v1) | `127.0.0.1:5002` | `QUANT_API_HOST` / `QUANT_API_PORT` 环境变量 |
| quantsys-v2 Flask API | `127.0.0.1:5001` | `QUANTSYS_API_HOST` / `QUANTSYS_API_PORT` / `QUANTSYS_API_URL` |
| quantsys-v2 WebSocket | `127.0.0.1:5003` | `QUANTSYS_API_HOST` / `QUANTSYS_WS_PORT` 环境变量 |
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

# Python quant backend (v1)
cd quant && python api/server.py          # Start Flask API on port 5002
cd quant && python -m pytest tests/       # Run Python tests
cd quant && pip install -r requirements.txt

# Python quant backend (v2)
cd quantsys-v2 && python start_all.py               # 一键启动 REST API (5001) + WebSocket (5003)
cd quantsys-v2 && python api/server.py              # 单独启动 REST API on port 5001
cd quantsys-v2 && python api/server_websocket.py    # 单独启动 WebSocket on port 5003
cd quantsys-v2 && python -m pytest tests/           # Run Python tests

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
统一的数据获取接口，支持股票基本信息、行情数据、财务数据、分红数据：
- `data_fetch_stock` — 获取股票基本信息、实时价格、新闻、公告
- `data_fetch_kline` — 获取 K 线数据（日线、周线、月线）
- `data_fetch_financial` — 获取财务数据（利润表、资产负债表、现金流量表）
- `data_fetch_dividend` — 获取分红数据（历史分红、高股息筛选、分红日历）

#### L2 因子工厂层
批量因子计算和分析：
- `factor_calculate` — 批量计算技术因子和基本面因子
- `factor_analyze` — 分析因子有效性（IC、覆盖率、稳定性）
- `invest_opportunity_scan` — 扫描投资机会（多因子评分）

#### L3 模型层
机器学习模型训练和预测：
- `model_train` — 训练机器学习模型
- `model_predict` — 模型预测和信号生成
- `model_evaluate` — 模型性能评估
- `model_monitor` — 模型监控和漂移检测
- `model_list` — 列出可用模型

#### L4 组合构建层
持仓管理和再平衡：
- `portfolio_rebalance` — 组合再平衡和持仓管理

#### L5 执行引擎层
订单管理和交易执行：
- `trade_manage_orders` — 订单管理和执行
- `trade_algo_execute` — 算法交易执行（TWAP/VWAP）

#### L6 监控运维层
实时监控和告警：
- `monitor_alert` — 告警通知和风险监控

### Agent 元工具

系统级操作工具：
- `backend_control` — 管理 quantsys-v2 后端服务生命周期（启动/停止/重启/状态查询）
  - 支持操作：`start`, `stop`, `restart`, `status`
  - 支持服务：`all` (REST API + WebSocket), `rest` (仅 REST API), `websocket` (仅 WebSocket)
  - REST API 端口：5001，WebSocket 端口：5003
  - 自动健康检查和 PID 管理

### backend_control 工具增强（2026-05-27）

**新特性：**
- **分阶段健康检查**：快速轮询（前5秒，500ms间隔）+ 慢速轮询（后10秒，1000ms间隔）
- **详细错误诊断**：
  - 进程崩溃检测 + 日志捕获
  - 端口冲突检测 + 冲突进程 PID
  - 服务日志分析 + 错误模式识别
- **日志重定向**：服务输出自动保存到 `/tmp/quantsys-v2-{service}.log`
- **启动耗时统计**：成功启动时显示实际耗时

**使用示例：**
```typescript
// 启动服务（自动等待健康检查）
backend_control({ action: "start", service: "all" })

// 如果失败，会显示详细诊断信息
```

**日志位置：**
- REST API: `/tmp/quantsys-v2-rest.log`
- WebSocket: `/tmp/quantsys-v2-websocket.log`
- 全部服务: `/tmp/quantsys-v2.log`

- `restart_agent` — 重启 agent 进程（TypeScript + Python bridge）
  - **保存并恢复对话历史**（最近 50 条消息）
  - **保存并恢复任务状态**（TaskManager + BackgroundTaskManager）
  - **自动触发 agent 循环**，无需用户手动输入
  - 重启后自动恢复未完成任务（pending + in_progress）
  - 中断的后台任务标记为失败，agent 可选择重试
  - 适用场景：新工具注册、Python bridge 异常、性能下降

- `claude_code` — 委托代码相关任务给 Claude Code CLI
  - **使用场景**：代码审查、重构、架构分析、Bug 修复、代码生成
  - **自动触发**：检测到关键词（review/审查、refactor/重构、analyze/分析、fix/修复、generate/生成）
  - **参数**：
    - `task` (必需) - 任务描述
    - `context` (可选) - 上下文信息
    - `files` (可选) - 相关文件路径
    - `timeout` (可选) - 超时时间（毫秒，默认 120000）
  - **CLI 命令**：`claude` (已安装在 `~/.local/bin/claude`)
  - **配置**：通过 `CLAUDE_CODE_*` 环境变量配置
    - `CLAUDE_CODE_CLI_PATH` - CLI 路径（默认：`claude`）
    - `CLAUDE_CODE_TIMEOUT` - 超时时间（默认：120000ms）
    - `CLAUDE_CODE_ENABLED` - 启用/禁用（默认：true）

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

**v2 迁移（2026-05-29）**：核心工具已从 v1 Python daemon 迁移到 quantsys-v2 Flask API (端口 5001)：
- `data_fetch_kline` — 使用 v2 API `/api/stock/{symbol}/history`
- `data_fetch_stock` — 使用 v2 API `/api/stocks/{symbol}`, `/api/stock/{symbol}/quote`, `/api/stock/{symbol}/news`, `/api/stock/{symbol}/announcements`
- `data_fetch_financial` — 使用 v2 API `/api/data/financials`
- `data_fetch_dividend` — 使用 v2 API `/api/stock/{symbol}/dividends`
- `factor_calculate` — 使用 v2 API `/api/factors/compute`
- `factor_analyze` — 使用 v2 API `/api/analysis/factors`
- `invest_opportunity_scan` — 使用 v2 API `/api/signals/opportunities`
- `trade_algo_execute` — 使用 v2 API `/api/orders/algo-execute`

**v1 保留工具**（已全部迁移至 v2）：
- ~~`data_fetch_stock`, `data_fetch_kline` — 基础数据获取~~ ✅ 已迁移
- `model_*` 系列 — 模型训练、预测、评估、监控（待迁移）

所有 v2 工具通过 `QuantV2Client` 统一调用，提供类型安全和错误处理。详见设计文档：`docs/superpowers/specs/2026-05-25-agent-v2-migration-design.md`

旧工具到新工具的映射：
- 股票查询相关 → `data_fetch_stock`
- K线数据相关 → `data_fetch_kline`
- 财务数据相关 → `data_fetch_financial`
- 分红数据相关 → `data_fetch_dividend`
- 因子计算相关 → `factor_calculate`
- 因子分析相关 → `factor_analyze`
- 投资机会扫描 → `invest_opportunity_scan`
- 持仓管理相关 → `portfolio_rebalance`
- 订单管理相关 → `trade_manage_orders`
- 算法交易执行 → `trade_algo_execute`
- 告警通知相关 → `monitor_alert`

工具实现位置：`src/infrastructure/tools/` 按层级组织（data/, factor/, invest/, portfolio/, trade/, monitor/）。

### 工具后端迁移（2026-05-27）

**重要变更**：`quant_cli` 工具已从 v1 CLI 迁移到 quantsys-v2 HTTP API。

- **旧架构**：spawn python -m quantsys.cli（已弃用）
- **新架构**：HTTP 调用 quantsys-v2 API (port 5001)

**新增命令**（v2 独有）：
- `strategy.run` - 实时运行策略
- `strategy.status` - 查询策略状态
- `signal.test_run` - 运行信号测试
- `signal.test_record` - 记录测试结果
- `signal.test_verify` - 验证信号准确性
- `signal.test_stats` - 信号测试统计

**要求**：使用 Agent 前必须启动 quantsys-v2 服务：
```bash
cd quantsys-v2 && python start_all.py
```

### Python Quant Backend (`quant/`)

Pipeline: resolve → data → factor → model → signal → risk → backtest → report.

- `quant/api/server.py` — Flask API with token auth and CORS (port 5002)
- `quant/api/quant_api.py` — CLI bridge for TypeScript → Python calls
- `quant/quantsys/` — Core package: strategies, factors, ml, risk, backtest, data, live

### Vue 3 Frontend (`web-frontend/`)

Vite dev server on port 3001 proxies `/api` to quantsys-v2 Flask API (port 5001). Component pages: Dashboard, Research, Model Training, Data Management, Operations.

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

**Python Environment:**
- **Required**: Python 3.13 (not 3.14 - numba incompatibility)
- Virtual environment: `.venv-py313/`
- Activation: `source activate-py313.sh`
- Dependencies: `quant/requirements.txt` (includes pandas-ta, numba, akshare, etc.)

**Node.js:**
- Node >= 22.0.0 required

## Testing

- **TypeScript**: Jest with `--experimental-vm-modules`. Test files co-located as `*.test.ts`. No jest.config file — config is in `package.json` jest section.
- **Python**: pytest, tests in `quant/tests/`. Coverage currently ~19%.
- **Frontend**: vitest, tests in `web-frontend/src/`.

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

## Dividend Data Tool (data_fetch_dividend)

### Overview
获取股票分红数据，支持三种查询模式：单股历史分红、高股息筛选、分红日历。

### Three Query Modes

#### 1. Single Mode - 单股历史分红查询
查询单只股票的历史分红记录，包含连续分红年数、平均股息率、累计派息等摘要指标。

**使用示例：**
```typescript
data_fetch_dividend({
  mode: "single",
  symbol: "600519.SH",
  years: 10
})
```

**返回内容：**
- 连续分红年数
- 平均股息率（%）
- 累计每股派息（元）
- 近期分红记录（年度、每股派息、股息率、除权日、状态）

**适用场景：**
- 分析个股分红稳定性
- 评估股息收益潜力
- 高股息策略选股

#### 2. Screen Mode - 高股息股票筛选
批量筛选符合条件的高股息股票，支持按股息率、连续分红年数等条件过滤。

**使用示例：**
```typescript
data_fetch_dividend({
  mode: "screen",
  min_yield: 3.0,        // 最低股息率 3%
  min_years: 5,          // 至少连续分红 5 年
  limit: 20              // 返回前 20 只
})
```

**筛选参数：**
- `min_yield` — 最低股息率（%）
- `min_years` — 最少连续分红年数
- `min_payout_ratio` — 最低分红率（%，预留）
- `max_payout_ratio` — 最高分红率（%，预留）
- `limit` — 返回数量限制（默认 50）

**返回内容：**
- 股票列表（按股息率降序排列）
- 每只股票的最新股息率、连续分红年数

**适用场景：**
- 构建高股息投资组合
- 寻找稳定分红标的
- 红利策略选股

**性能：**
- 股票池：沪深300 + 创业板50 + 科创50（~400只）
- 查询时间：< 30s
- 并发查询：10 workers

#### 3. Calendar Mode - 分红日历
查询指定日期范围内的分红事件（除权除息日、股权登记日、派息日）。

**使用示例：**
```typescript
data_fetch_dividend({
  mode: "calendar",
  start_date: "2026-06-01",
  end_date: "2026-06-30",
  event: "ex_dividend"    // 除权除息日
})
```

**事件类型：**
- `ex_dividend` — 除权除息日（默认）
- `record_date` — 股权登记日
- `pay_date` — 派息日

**返回内容：**
- 时间范围和事件类型
- 事件列表（按日期排序）
- 每个事件的股票名称、每股派息、股息率

**适用场景：**
- 规划分红收益时间表
- 提前布局除权除息机会
- 跟踪持仓分红日程

**性能：**
- 查询时间：< 20s

### Data Source
- **Primary**: akshare (实时查询，无数据库持久化)
- **Coverage**: A股市场
- **Update**: 实时获取最新数据

### Known Issues
- **py_mini_racer 环境问题**：部分环境下 single mode 可能遇到符号链接错误
- **Workaround**: screen 和 calendar 模式不受影响；或修复 Python 环境

### API Endpoints (quantsys-v2)
- `GET /api/stock/{symbol}/dividends?years=N` — 单股查询
- `POST /api/dividends/screen` — 批量筛选
- `GET /api/dividends/calendar?start_date=X&end_date=Y&event=Z` — 分红日历

### Files
- Backend Service: `quantsys-v2/services/dividend_service.py`
- Data Source: `quantsys-v2/services/dividend_data_source.py`
- API Routes: `quantsys-v2/api/routes/dividends.py`
- TypeScript Tool: `src/infrastructure/tools/data/fetch-dividend-tool.ts`
- Client: `src/infrastructure/quant/quant-v2-client.ts` (getDividends)
- Formatter: `src/infrastructure/quant/formatters.ts` (formatDividendData)

### Testing
- Unit Tests: `quantsys-v2/tests/services/test_dividend_service.py`
- API Tests: `quantsys-v2/tests/api/test_dividends_routes.py`
- E2E Tests: `docs/testing/dividend-tool-e2e-test.md`

## Active Conventions

- No linter/formatter configured (no ESLint, Prettier, or Biome).
- No CI/CD pipeline configured.
- git worktrees used for feature isolation (evolution branches, worktree-agent branches).
- Commit messages in Chinese are common.
- The agent uses DeepSeek which processes one tool call at a time — tool definitions should account for this.
