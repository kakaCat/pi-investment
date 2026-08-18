# CLAUDE.md - PI Investment System

This file provides guidance to Claude Code when working with this multi-project repository.

## Project Overview

**PI Investment** is an intelligent autonomous investment system powered by AI agents. The system operates with minimal human intervention, executing investment strategies and making trading decisions independently.

### Core Philosophy

**Intelligence = Profitability in Financial Competition**

The system's intelligence is measured by one metric: **sustained profitability** in zero-sum financial markets. The AI agent competes against:
- Retail investors (emotional, reactive)
- Hot money traders (pump-and-dump schemes)
- Institutions (information/capital advantages)
- Other quant teams and AI agents

**Goal**: Outperform opponents by identifying their mistakes and exploiting market inefficiencies.

## Three-Layer Architecture

```
┌─────────────────────────────────────────────────┐
│  Human User                                      │
│  • Initial setup (goals, preferences, rules)    │
│  • Occasional intervention                       │
│  • Monitor via web dashboard                     │
└─────────────────────────────────────────────────┘
       ↓ Configure            ↑ Monitor
       
┌──────────────────┐      ┌─────────────────┐
│   agent-ts       │      │  web-frontend   │
│  (AI Employee)   │──────│  (Monitoring)   │
│                  │ Data │                 │
│ 🤖 Autonomous:   │ Trail│ 📊 Visualize:   │
│ • Scheduled tasks│      │ • Agent logs    │
│ • Active monitor │      │ • Pool changes  │
│ • Auto decision  │      │ • Signal history│
│ • Smart response │      │ • Decisions     │
└────────┬─────────┘      └────────┬────────┘
         ↓ API Calls               ↓ Query
         
┌─────────────────────────────────────────────────┐
│       quantsys-v2 (Backend Service)             │
│  • HTTP/WebSocket APIs                          │
│  • Data persistence (operation audit trail)     │
│  • Support agent autonomous decisions           │
└─────────────────────────────────────────────────┘
```

### 1. agent-ts (AI Employee)

**Location**: `./agent-ts/`

**Role**: Autonomous AI agent that:
- Executes scheduled investment tasks
- Makes trading decisions independently
- Monitors markets and responds to opportunities
- Learns from results (self-improvement)

**Key Features**:
- Built on DeepSeek model
- Tool-based architecture (60+ investment tools)
- Scheduled task system (cron-like)
- Session management with conversation history
- Multi-channel integration (CLI, TUI, Feishu bot)

**See**: [agent-ts/CLAUDE.md](agent-ts/CLAUDE.md) for detailed documentation.

### 2. quantsys-v2 (Backend Service)

**Location**: `./quantsys-v2/`

**Role**: Quantitative backend that:
- Provides HTTP/WebSocket APIs for agent
- Persists all operations (data audit trail)
- Handles complex calculations (backtest, factor analysis, ML)
- Manages data sources (stocks, financials, macroeconomic)

**Key Features**:
- Flask REST API (port 5001)
- WebSocket server (port 5003)
- PostgreSQL database
- Multi-data-source abstraction (akshare, eastmoney, sina, etc.)
- Circuit breaker and cache system

**See**: [quantsys-v2/CLAUDE.md](quantsys-v2/CLAUDE.md) for detailed documentation.

### 3. web-frontend (Monitoring Dashboard)

**Location**: `./web-frontend/`

**Role**: Visualization frontend that:
- Displays agent's work and decisions
- Shows stock pool status and changes
- Tracks signal history and performance
- Provides human oversight interface

**Key Features**:
- Vue 3 + Element Plus
- Vite dev server (port 3001)
- Real-time updates via WebSocket
- Historical data visualization

## System Intelligence Design

### Agent Autonomy

The agent operates on **scheduled tasks** and **event-driven triggers**, not just user requests:

**Examples**:
- **Daily 02:00**: Refresh dynamic stock pools, validate strategies
- **Daily 09:00**: Scan buy signals before market opens
- **Daily 15:30**: Analyze day's performance, adjust positions
- **Weekly**: Review all pools, optimize parameters

### Game Theory in Stock Pools

Stock pools are not just "finding good stocks" — they are **battlefield selection** in financial warfare:

**Strategic Use**:
1. **Harvest retail panic** — Buy quality stocks during fear-driven selloffs
2. **Avoid institutional traps** — Exit when institutions start distributing
3. **Snipe hot-money schemes** — Bottom-fish after pump-and-dump crashes
4. **Sector rotation** — Switch to winning battlefields

**Required Intelligence**:
- Opponent behavior tracking (retail/institution/hot-money flows)
- Risk signal detection (abnormal volume, insider selling)
- Opportunity identification (oversold quality stocks)
- Fast battlefield switching (exit losing sectors, enter winning ones)

### Data Trail for Learning

Every agent operation is logged to quantsys-v2 database:
- Decision context (why this action?)
- Execution results (profit/loss)
- Performance metrics (win rate, Sharpe ratio)
- Lessons learned (what worked, what didn't)

This enables the agent to improve decision quality over time.

## Key Workflow Example

### Autonomous Daily Stock Pool Maintenance

```
⏰ 02:00 AM - Scheduled Task Triggers
  ↓
Agent wakes up autonomously:
  1. Call pool_manage (list all dynamic pools)
  2. For each pool:
     - Call pool_manage (refresh)
     - Detect changes: +3 stocks added, -2 removed
     - Log reason: "600519 ROE dropped to 12%, below 15% threshold"
  3. Call pool_validate (strategy validation)
  4. Write audit trail to quantsys-v2 database
  5. If major changes: Send notification (Feishu/email)
  ↓
Human user checks web dashboard in the morning:
  - See pool changes and reasons
  - Review agent's decisions
  - Intervene only if needed
```

## Stock Pool Game Theory Optimization

Based on our discussion, stock pools need enhancements to support game-theoretic intelligence:

### P0 - Required for Competitive Intelligence

1. **Opponent Behavior Tracking**
   - API: `GET /api/market/opponent-behavior`
   - Returns: retail sentiment, institution flows, hot-money activity
   - Use: Agent identifies when opponents are making mistakes

2. **Pool Risk Assessment with Game Analysis**
   - API: `GET /api/pools/{id}/risk-assessment`
   - Returns: risk signals (institution exit, retail chase, volume spike)
   - Use: Agent exits before traps, enters during panic

3. **Battlefield Assessment**
   - API: `GET /api/pools/battlefield-assessment`
   - Returns: competitive advantage score for each pool
   - Use: Agent prioritizes high-advantage battlefields

4. **Real-time Game Alerts**
   - WebSocket: `/ws/game-alerts`
   - Pushes: opportunity alerts (panic selloff) and risk alerts (distribution phase)
   - Use: Agent responds to fleeting opportunities

### P1 - Enhanced Decision Support

5. **Pool Health Time Series**
   - Track pool quality trends over time
   - Detect deterioration early

6. **Attribution Analysis**
   - Identify profit sources (stock selection vs timing vs sector allocation)
   - Learn which screening criteria work

7. **Manipulation Detection**
   - Flag pump-and-dump schemes
   - Identify post-manipulation bottom-fishing opportunities

## 多会话并行工作规则（Worktree 隔离）

本仓库常有多个 Claude 会话与人工并行工作。**修改代码必须创建 worktree，完成并合并后再提交 GitHub。**

1. **每个独立工作线必须在独立 worktree 中开发**：`git worktree add .claude/worktrees/<name> -b feat/<name>`，不在共享主工作区直接做 feature 提交
2. **会话开始先确认分支**：`git branch --show-current` 与预期不符时停手确认，不要在被切换的分支上继续提交
3. **合并与推送**：工作线在 worktree 内完成并验证后，合并回 main（临时 worktree 或 PR），再推送 GitHub
4. **禁止在脏工作区批量覆盖**：不执行 `git checkout <ref> -- .`、`git restore --source=<ref> .` 等命令；提交前 `git status` 出现不属于自己的改动 = 停手信号，只 add 自己任务的文件
5. **IP/端口约定**：worktree 中因测试改 IP/端口的，合并前必须改回固定值（见 agent-ts/CLAUDE.md 固定端口表）

## Development Guidelines

### Agent Tool Development

When creating tools for the agent:
1. **Return decision context**, not just data
2. **Include opponent analysis** when relevant
3. **Suggest actions** with confidence scores
4. **Provide audit trails** for learning

### Quantsys-v2 API Design

When adding APIs:
1. **Return actionable insights**, not raw data dumps
2. **Include "why"** in responses (explain anomalies, trends)
3. **Support time-series queries** for pattern recognition
4. **Log all operations** for agent learning

### Web Frontend Visualization

When building dashboards:
1. **Show agent's reasoning**, not just results
2. **Visualize game dynamics** (who's winning, who's losing)
3. **Highlight anomalies** that need human attention
4. **Track decision quality** over time

## Project Structure

```
pi-investment/
├── agent-ts/              # AI agent (TypeScript)
│   ├── src/
│   │   ├── core/         # Agent loop, session management
│   │   ├── infrastructure/
│   │   │   ├── tools/    # 60+ investment tools
│   │   │   └── adapters/ # Data source adapters
│   │   └── services/     # Business logic
│   └── CLAUDE.md         # Agent-specific docs
│
├── quantsys-v2/          # Backend service (Python)
│   ├── api/              # Flask REST + WebSocket
│   ├── services/         # Business services
│   ├── repositories/     # Data access
│   └── CLAUDE.md         # Backend-specific docs
│
├── web-frontend/         # Monitoring UI (Vue 3)
│   └── src/
│       └── views/        # Dashboard pages
│
├── docs/                 # Shared documentation
└── CLAUDE.md            # This file
```

## 文档放置规范（Document Placement Rules）

**根目录只保留两个 MD 文件**：`README.md` 和 `CLAUDE.md`。其余所有文档必须按类型放入 `docs/` 对应子目录，禁止直接写到仓库根目录或散落在各子项目根目录。

创建任何 `.md` 前先走决策树：

```
这是技术决策（选型/架构变更）？
├─ 是 → docs/adr/NNN-title.md
└─ 否 ↓
这是新特性设计提案（实施前）？
├─ 是 → docs/rfcs/NNN-title.md
└─ 否 ↓
这是架构说明（长期有效）？
├─ 是 → docs/architecture/topic.md
└─ 否 ↓
这是使用指南（部署/迁移/排障）？
├─ 是 → docs/guides/topic.md
└─ 否 ↓
这是工作记录（WP/Phase/Batch 完成报告、总结）？
└─ 是 → docs/work-logs/YYYY-MM/title.md
```

要点：

- **工作包/阶段完成报告**（`*-REPORT.md`、`*-SUMMARY.md`、`*-COMPLETE.md`、`PHASE-*`、`WP-*`、`BATCH-*` 等）一律写 `docs/work-logs/YYYY-MM/`，按完成月份归档，不写入根目录。
- **子项目专属文档**放各自 `docs/` 目录（如 `agent-os/docs/`、`agent-dh/docs/`），不要放子项目根目录。
- 命名规范：kebab-case；ADR/RFC 用 `NNN-title.md` 数字编号；work-logs 用 `<project>-<type>.md`。
- 完整规范与模板见 [docs/DOCUMENT-MANAGEMENT-PLAN.md](docs/DOCUMENT-MANAGEMENT-PLAN.md) 和 [docs/README.md](docs/README.md)。

## Getting Started

### Start All Services

```bash
# 1. Start backend
cd quantsys-v2
source activate-py313.sh
python start_all.py

# 2. Start frontend (optional, for monitoring)
cd web-frontend
npm run dev

# 3. Start agent
cd agent-ts
npm run dev
```

### Environment Variables

Create `.env` in `agent-ts/` directory:

```bash
# AI Model
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...  # Same as DEEPSEEK_API_KEY
MODEL_ID=deepseek-v4-flash  # 或 deepseek-v4-pro

# Backend
QUANTSYS_V2_API_URL=http://127.0.0.1:5001

# Database (for quantsys-v2 only)
PGDATABASE=quant_investment

# Optional
FEISHU_APP_ID=...
TAVILY_API_KEY=...
```

## Key Concepts

### Autonomous vs Reactive

❌ **Traditional systems**: Wait for user commands
✅ **This system**: Agent executes scheduled tasks autonomously

### Learning vs Rule-Based

❌ **Traditional quant**: Fixed rules and parameters
✅ **This system**: Agent learns from results and adapts

### Data Dump vs Intelligence

❌ **Traditional APIs**: Return raw data
✅ **This system**: Return insights, recommendations, and decision context

### Win vs Learn

❌ **Traditional focus**: High backtest returns
✅ **This system**: Sustained profitability against real opponents

## Related Documentation

- [Agent Architecture](agent-ts/CLAUDE.md)
- [Backend API Reference](quantsys-v2/CLAUDE.md)
- [Web Frontend Guide](web-frontend/CLAUDE.md)
- [Stock Pool Game Theory](docs/stock-pool-game-theory.md) - Battlefield selection and opponent exploitation
- [Agent Autonomy Guide](docs/agent-autonomy.md) - Autonomous operation and decision-making
- [Game Theory Framework](docs/game-theory-framework.md) - Theoretical foundation and competitive intelligence
- [文档中心](docs/README.md) - 文档索引与放置规范（[管理规范](docs/DOCUMENT-MANAGEMENT-PLAN.md)）

## Version History

- 2026-08-18: Added 文档放置规范 - document placement rules (root keeps only README.md + CLAUDE.md)
- 2026-06-29: Documentation consolidation - created game theory framework docs
- 2026-06-25: Added system philosophy, game theory framework, autonomous agent design
- 2026-06-03: Initial three-layer architecture documentation
