# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Autonomous AI Investment Agent** — A self-directed AI employee that makes investment decisions and executes trades with minimal human intervention.

### System Role in Three-Layer Architecture

This agent is the **intelligent core** of the PI Investment system:

```
Human User → Monitor & Configure
      ↓
   agent-ts (this project) → Autonomous AI Employee
      ↓ Tool calls
   quantsys-v2 → Backend Service (data, computation, persistence)
      ↑ Query
   web-frontend → Monitoring Dashboard (visualize agent work)
```

### Core Mission: Profitability Through Intelligence

**Goal**: Sustained profitability in financial markets by outperforming opponents:
- Retail investors (emotional, reactive)
- Hot money traders (pump-and-dump)
- Institutions (information/capital advantages)
- Other AI trading systems

**Intelligence Metrics**: win rate in real trades, Sharpe ratio vs market, ability to avoid traps (institutional distribution, hot-money schemes), speed of adaptation to market regime changes.

### Agent Characteristics

- **Autonomous**: Executes scheduled tasks without human prompts
- **Proactive**: Monitors markets and responds to opportunities
- **Self-learning**: Analyzes results and improves decision quality
- **Game-aware**: Identifies opponent behavior and exploits mistakes

## Fixed IP / Port Convention

每个子项目使用固定的 127.0.0.1 地址 + 固定端口。**主分支上的 IP/端口不允许随意修改。** 如果发现主分支上的 IP 被改动，必须修复回以下固定值：

| 子项目 | 固定地址 | 配置方式 |
|--------|----------|----------|
| quantsys-v2 REST API | `127.0.0.1:5001` | `QUANTSYS_API_HOST` / `QUANTSYS_API_PORT` / `QUANTSYS_API_URL` |
| quantsys-v2 WebSocket | `127.0.0.1:5003` | `QUANTSYS_API_HOST` / `QUANTSYS_WS_PORT` 环境变量 |
| web-frontend Vite | `127.0.0.1:3001` | 代理 `/api` → `127.0.0.1:5001` |
| agent-ts Wake Channel | `127.0.0.1:3002` | `WAKE_CHANNEL_PORT` / `WAKE_TOKEN`；v2 侧对应 `AGENT_API_URL=http://127.0.0.1:3002` / `AGENT_API_TOKEN` |
| TypeScript Agent | N/A (CLI) | 通过环境变量连接各服务 |
| PostgreSQL | `127.0.0.1:5432` | 仅用于 quantsys-v2 后端 |
| Redis | `127.0.0.1:6379` | `REDIS_HOST` / `REDIS_PORT` 环境变量 |

> **注意：** `quantsys-v2/` 和 `web-frontend/` 已并入本 monorepo（不再是独立 git 仓库）。

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
npm test                 # Jest (ESM via --experimental-vm-modules；必须走 npm test)
npm run test:watch       # Jest watch mode
npm run test:coverage    # Jest with coverage
npm run check:tool-refs  # 工具引用 sanity check（见「工具系统」）

# Python quant backend (v2) — 启动细节以 quantsys-v2/CLAUDE.md 为准
cd quantsys-v2 && source venv/bin/activate               # venv 目录为 quantsys-v2/venv（也可用 activate-py313.sh）
python adapters/inbound/api/server.py                    # 生产 5001 目前仍由 Flask 提供（start_all.py 已不存在）
python adapters/inbound/fastapi_app/websocket_server.py  # WebSocket 5003
python -m pytest tests/                                  # Python tests（自动切 quant_test 库）

# Vue 3 dashboard (web-frontend)
cd web-frontend && npm run dev     # Vite dev server on port 3001
cd web-frontend && npm run build   # Production build
```

## Architecture

### TypeScript Agent (`src/`)

| Layer | Directory | Purpose |
|-------|-----------|---------|
| API | `src/api/` | Feishu bot、gateway（通道适配器/session 事件流）、wake channel (3002) |
| Config | `src/config/` | Model/provider config（DeepSeek/Kimi + compat）、paths、bootstrap |
| Core | `src/core/` | Agent loop、session、task management、system prompt |
| Domain | `src/domain/` | Cache system（namespaces: daily, intraday, quarterly, static） |
| Infrastructure | `src/infrastructure/` | Adapters、providers（行情数据源）、logging、monitoring、TUI、**tools/**（工具注册表） |
| Services | `src/services/` | Business logic: quant, portfolio, compaction, scheduler, notification, intelligence |
| Types | `src/types/` | TypeScript type definitions |

**Key patterns:**
- **Tool Registry**：约 110 个工具统一注册在 `src/infrastructure/tools/index.ts` 的 `allCustomTools` 数组（数组顺序 = 系统提示词中的工具顺序）。新增工具 = 写工具文件 + import + 加入数组。
- **8-layer system prompt**：`src/services/intelligence/system-prompt-builder.ts` — Identity → Soul → Tools → Skills → Memory → Bootstrap → Runtime → Channel。
- **Data providers**：`src/infrastructure/providers/market/` — eastmoney、sina、sina-fx、stooq、技术指标；复杂计算和持久化走 quantsys-v2 API（`QuantV2Client`）。
- **CLI adapters**：`src/infrastructure/adapters/cli/` — 部分数据访问封装为 shell 命令。

### Python Quant Backend (`quantsys-v2/`)

REST API (5001) + WebSocket (5003)：策略、因子、ML pipeline、回测、风控、数据持久化。架构与启动细节见 [quantsys-v2/CLAUDE.md](../quantsys-v2/CLAUDE.md)。

数据访问经 DataSourceManager 统一入口：多数据源（baostock/akshare/东财/新浪/腾讯）按优先级 failover + 熔断器 + TTL 缓存。细节见 [quantsys-v2/DATA_ACCESS_GUIDE.md](../quantsys-v2/DATA_ACCESS_GUIDE.md)。

### Vue 3 Frontend (`web-frontend/`)

Vite dev server (3001) 代理 `/api` → quantsys-v2 (5001)。页面：Dashboard、Research、Model Training、Data Management、Operations。

## 工具系统

### 现状概述

约 **110 个注册工具**，注册表：`src/infrastructure/tools/index.ts`（`allCustomTools`），按域组织在 `src/infrastructure/tools/<domain>/`：

- `data_*` — 行情/财务/分红/宏观/北向/情绪数据（quote、kline、financial、dividend、macro、north_flow、market_sentiment）
- `factor_*` / `indicator_*` — 因子计算与有效性分析（IC/IR/覆盖率/单调性）、技术指标 CRUD 与回测
- `strategy_*` — 策略 CRUD/执行（single/batch/pipeline）/优化/批量验证/发现；组合回测（portfolio/ensemble/pipeline 三模式）
- `pool_*` — 股票池 CRUD/动态刷新/成员管理/多策略批量回测验证/战场评估
- `portfolio_*` / `trade_*` — 虚拟仓交易/状态/对账/账户、订单监控、算法执行（TWAP/VWAP）
- `model_*` — ML 模型训练/预测/评估/监控/列表（均已注册）
- `monitor_*` / `watch_*` / `risk_*` — 告警、盯盘规则、风控、Barra 风险分解
- 分析与选股 — 因子归因、行业分析、基准对比、回测统计、`screening`、`opportunity_scan`、`rotation_*`
- 元工具 — `backend_control`（v2 服务启停/健康诊断）、`scheduler_manage`、`restart_agent`（保留对话与任务状态重启）、`claude_code`（委托代码任务给 Claude Code CLI）、`model_switch`、记忆/任务/计划工具

**关键警示：**
- 领域 CLI 工具（`market_cli`/`stock_cli`/`sentiment_cli`/`analysis_cli`/`watchlist_cli`）与旧的核心 CLI 聚合工具**已全部移除**，禁止使用；数据访问走 `data_fetch_*` / `factor_*` / `opportunity_scan` 等工具 → quantsys-v2 API。
- `smart_stock_screener` 已并入 `opportunity_scan`（固定/自定义/动态权重三种模式）。

**工具引用 sanity check**：`npm run check:tool-refs` — 扫描 `skills/*.md`、调度任务 prompt、事件唤醒 prompt 中引用的工具名是否已注册，退出码 1 表示有漂移；agent 启动时也会自动 warn。改 skills 或任务模板后应跑一次。

### 大结果持久化（节省上下文）

大数据返回工具（回测、批量查询等）经 `handleToolResponse`（`src/infrastructure/tools/utils/tool-response-handler.ts`）包装：超过阈值（按工具 30-100KB）的结果落盘到 `{sessionDir}/tool-results/{toolName}_YYYYMMDD_HHmmss.json`（无 session 时降级 `.cache/tool-results/`），上下文只保留摘要 + 文件路径；过期文件（默认 24h）自动清理。**新工具若返回大数据，必须走此包装器**（可选配 formatter 与自定义阈值）。

### 策略沙箱因子注入

策略代码执行时自动预注入技术/财务/因子列到 DataFrame（TA-Lib 实现，无需手动 import 或计算），可直接写 `df['buy'] = (df['rsi14'] < 30) & (df['adx'] > 25)`。因子清单与财务指标口径详见 quantsys-v2/CLAUDE.md。

## 调度器架构

- TypeScript Agent 使用 `InMemorySchedulerStore`（内存调度器，`src/services/scheduler/`）——**重启后任务需重新注册**；数据补充任务由 quantsys-v2 调度器（scheduler_daemon）负责。
- Agent AI 决策任务类型为 `agent_turn`（唤醒 Agent 自主决策），启动时由 `src/services/scheduler/init-agent-tasks.ts` 注册：

| 任务 | 调度 | 用途 |
|------|------|------|
| `morning_ai_analysis` | `0 9 * * 1-5`（工作日 9:00） | 盘前分析 |
| `realtime_quick_check` | `*/30 9-14 * * 1-5`（盘中每 30 分钟） | 盘中快检 |
| `daily_ai_review` | `0 18 * * *`（每天 18:00） | 盘后复盘 |
| `weekly_evolution` | `0 20 * * 0`（每周日 20:00） | 周度进化 |

- 运行时管理：`scheduler_manage` 工具（任务 CRUD/启停/手动触发/执行历史/补偿执行）。

## Environment Setup

Required env vars (see `.env.example`):

```bash
# LLM provider: deepseek (默认) 或 kimi
LLM_PROVIDER=deepseek

# DeepSeek API (OpenAI-compatible)
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=...          # SDK reads this key; must match DEEPSEEK_API_KEY
MODEL_ID=deepseek-v4-flash  # 或 deepseek-v4-pro

# Kimi / Moonshot API (LLM_PROVIDER=kimi 时生效)
# KIMI_API_KEY=sk-...
# KIMI_BASE_URL=https://api.moonshot.cn/v1
# MODEL_ID=kimi-k3          # 可覆盖为具体版本
# 通用覆盖: LLM_API_KEY / LLM_BASE_URL / LLM_REASONING / LLM_CONTEXT_WINDOW / LLM_MAX_TOKENS

# quantsys-v2 backend
QUANTSYS_V2_API_URL=http://127.0.0.1:5001
QUANTSYS_V2_TIMEOUT=30000

# Database (PostgreSQL - 仅 quantsys-v2 使用；TypeScript Agent 不直连 PG)
QUANT_DB_PROVIDER=postgres
PGDATABASE=quant_investment

# Optional
FEISHU_APP_ID=...           # Feishu/Lark bot
TAVILY_API_KEY=...          # Web search
```

**运行时热切换 provider**（不重启进程）：
- 人工：TUI 中 `/provider` 查看状态，`/provider kimi` / `/provider deepseek` 切换（当前会话立即生效）
- Agent：`model_switch` 工具（仅新会话生效，1 小时内限 3 次）
- 仅内存生效，重启后回到 `LLM_PROVIDER`；切换审计日志在 `.pi-invest/model-switch.log`

**Python Environment:**
- Required: Python 3.13（3.14 与 numba 不兼容）
- Virtual environment: `quantsys-v2/venv/`（`source venv/bin/activate` 或 `source activate-py313.sh`）
- Dependencies: `quantsys-v2/requirements.txt`

**Node.js:** >= 22.0.0

## Testing

- **TypeScript**: Jest with `--experimental-vm-modules` — 必须 `npm test`（裸 `npx jest` 会误报 TS1378）。Test files co-located as `*.test.ts`。Config in `package.json` jest section（无独立 jest.config）。
- **Python**: pytest, tests in `quantsys-v2/tests/`，测试自动切换到 `quant_test` 库。
- **Frontend**: vitest, tests in `web-frontend/src/`。

## Agent Autonomy & Scheduled Tasks

The agent operates on **scheduled tasks** and **event triggers**, not just user requests. 日常节奏：盘前分析（9:00）→ 盘中快检（每 30 分钟）→ 盘后复盘（18:00）→ 周度进化（周日 20:00），见「调度器架构」。

**Event-driven triggers**: abnormal volatility → risk assessment; pool health deterioration → auto-refresh; signal quality decline → strategy adjustment; watch rules 命中 → WatchEngine 唤醒 Agent。

## Game Theory in Stock Pools

Stock pools are **battlefield selection** tools for competitive advantage:

**Strategic patterns**:
1. **Harvest Retail Panic** — Buy quality during fear-driven selloffs
2. **Avoid Institutional Traps** — Exit when institutions distribute
3. **Snipe Hot-Money Aftermath** — Bottom-fish after pump-and-dump
4. **Sector Rotation** — Switch to winning sectors

**Required intelligence**: opponent flow tracking (retail/institution/hot-money)、risk signal detection (abnormal volume, insider action)、opportunity windows、fast battlefield switching。相关工具：`opponent_behavior`、`pool_battlefield`、`manipulation_detect`、`market_style_detect`。

## Agent Decision Framework

### Decision Context (Not Just Data)

When calling backend APIs, the agent should receive:
- **What**: The data/result
- **Why**: Analysis of anomalies, trends, patterns
- **Suggested Action**: Recommendations with confidence scores
- **Game Context**: Who's winning, who's losing, who's making mistakes

### Audit Trail for Learning

Every significant decision is logged to quantsys-v2（context、reasoning、result、outcome），支持 performance attribution、strategy improvement、failure analysis。策略闭环已打通：信号 → 订单（关联 signal_id）→ 成交 → 盈亏（`strategy_performance` 表）→ 纸面+实盘统一统计 → 经验积累（`ExperienceAccumulator`，样本 ≥ 10 自动生成推荐等级 aggressive/moderate/cautious/avoid）。

## Active Conventions

- No linter/formatter configured (no ESLint, Prettier, or Biome). No CI/CD pipeline.
- **修改代码必须创建 worktree，完成并合并后再提交 GitHub**——见根 CLAUDE.md「多会话并行工作规则（Worktree 隔离）」。
- Commit messages in Chinese are common.
- The agent uses DeepSeek which processes one tool call at a time — tool definitions should account for this.
- **Agent is autonomous**: Design features around scheduled tasks, not just user prompts.
- **Game-theoretic mindset**: Tools should help identify opponent mistakes, not just "good stocks".
