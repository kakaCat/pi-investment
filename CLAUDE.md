# CLAUDE.md - PI Investment System

This file provides guidance to Claude Code when working with this multi-project repository.

> **项目认知入口**：动手前先读 [项目说明书](docs/architecture/project-manual.md)（文档金字塔 L1：项目是什么 /
> 三层架构 / 关键概念 / 怎么跑 / 去哪儿找细节）。细节在 [docs/](docs/README.md) 的领域篇（L2），
> 追溯历史才下沉到需求档案与工作日志（L3）。

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
│   agent-dh       │      │  web-frontend   │
│  (AI Employee)   │──────│  (Monitoring)   │
│  DSH Profile     │ Data │                 │
│                  │ Trail│ 📊 Visualize:   │
│ 🤖 Autonomous:   │      │ • Agent logs    │
│ • Scheduled tasks│      │ • Pool changes  │
│ • Active monitor │      │ • Signal history│
│ • Auto decision  │      │ • Decisions     │
│ • Smart response │      │ • Requirements  │
└────────┬─────────┘      └────────┬────────┘
         ↓ API Calls               ↓ Query
         
┌─────────────────────────────────────────────────┐
│       quantsys-v2 (Backend Service)             │
│  • HTTP/WebSocket APIs                          │
│  • Data persistence (operation audit trail)     │
│  • Support agent autonomous decisions           │
└─────────────────────────────────────────────────┘
```

### 1. agent-dh (AI Employee - DSH Profile)

**Location**: `./agent-dh/`

**Role**: Autonomous AI agent (DeepSeek Harness Profile) that:
- Executes scheduled investment tasks
- Makes trading decisions independently
- Monitors markets and responds to opportunities
- Learns from results (self-improvement via genome evolution)
- Manages requirements and development tasks

**Key Features**:
- Built on DeepSeek Harness framework
- Plugin-based architecture (60+ investment tools)
- Genome system (constitution/principles/rules/lessons)
- Scheduled task system (Agent OS integration)
- Requirement board (REQ pipeline)
- Multi-channel integration (Web UI, CLI, Feishu bot)

**See**: [agent-dh/CLAUDE.md](agent-dh/CLAUDE.md) for detailed documentation.

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
- Provider framework with fault tolerance

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

**Note**: Agent-DH also provides web UI via DSH framework (port 13080) with page plugins.

## System Intelligence Design

### Agent Autonomy

The agent operates on **scheduled tasks** and **event-driven triggers**, not just user requests:

**Examples**:
- **Daily 02:00**: Refresh dynamic stock pools, validate strategies
- **Daily 09:00**: Scan buy signals before market opens (session-briefing)
- **Daily 15:30**: Analyze day's performance, adjust positions
- **Weekly**: Review all pools, optimize parameters

### Genome Evolution System

The agent's decision-making is governed by a **genome system** (constitution/principles/rules/lessons):

**Four Layers**:
1. **Constitution** (不可修改) - Trading constraints (时段/制度/仓位/止损/数据驱动)
2. **Principles** (可进化) - Core principles (博弈思维/风险控制/透明记录/链式扫描)
3. **Rules** (可进化) - Operational rules (R-001 ~ R-020+, 买入确认/卖出确认/信号分级等)
4. **Lessons** (可进化) - Experience learned from results

**Evolution Process**:
- Candidate versions go through validation gate
- Observational period with A/B testing
- Promote to active or rollback based on performance
- Version history tracked with git integration

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

## Key Concepts (术语表)

| 术语 | 一句话解释 | 细节在哪 |
|---|---|---|
| **DSH Profile** | DeepSeek Harness 的装载单元；agent-dh 是本项目的 profile | [agent-dh/CLAUDE.md](agent-dh/CLAUDE.md) |
| **插件 (Plugin)** | DSH 的功能单元；用 `defineTool` 注册工具 | [agent-dh/docs/](agent-dh/docs/README.md) |
| **基因组 (Genome)** | Agent 的宪法/原则/规则/教训四段提示词，可进化、有版本与验证门 | [RFC 006-008](docs/rfcs/) |
| **需求看板 (reqboard)** | 需求 → 任务两级流水线：立项 → 需求分析 → 技术设计 → 拆分 → 实施 → 验收 → 归档（7 态） | [RFC 014](agent-dh/docs/rfcs/014-requirement-board.md) |
| **任务队列 (queue.json)** | 任务卡的唯一存储：按需求分片的 `docs/requirements/<REQ>/queue.json` | [project-manual.md](docs/architecture/project-manual.md) |
| **文档金字塔** | L1 说明书 / L2 领域篇 / L3 证据档案；归档让认知自下而上生长 | [DOCUMENT-MANAGEMENT-PLAN.md](docs/DOCUMENT-MANAGEMENT-PLAN.md) |
| **多源 provider 框架** | quantsys-v2 取数的唯一入口，提供故障转移/熔断/健康排序 | quantsys-v2 adapters/outbound/datasources/manager.py |
| **诚实降级** | 无数据→显式 empty:true；上游损坏→拒绝返回；传输故障→None（进熔断） | [work-logs](docs/work-logs/) |

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

## Development Guidelines

### Agent Tool Development

When creating tools for the agent:
1. **Return decision context**, not just data
2. **Include opponent analysis** when relevant
3. **Suggest actions** with confidence scores
4. **Provide audit trails** for learning
5. **Follow schema rules** - every `type: 'object'` must have `additionalProperties: true|false`

### Quantsys-v2 API Design

When adding APIs:
1. **Return actionable insights**, not raw data dumps
2. **Include "why"** in responses (explain anomalies, trends)
3. **Support time-series queries** for pattern recognition
4. **Log all operations** for agent learning
5. **Use provider framework** for data sources (fault tolerance)

### Web Frontend Visualization

When building dashboards:
1. **Show agent's reasoning**, not just results
2. **Visualize game dynamics** (who's winning, who's losing)
3. **Highlight anomalies** that need human attention
4. **Track decision quality** over time

### Architecture Rules (Mandatory)

#### Notification Architecture

**All notifications MUST go through `NotificationFacade`. Direct calls to Feishu SDK or agent_service are FORBIDDEN.**

**Rules:**
1. Application layer can only import `application.notification.notification_facade.NotificationFacade`
2. NEVER import `infrastructure.notification.channels.*` in application layer
3. NEVER call `requests.post(feishu_webhook_url)` directly
4. New notification types MUST extend `NotificationFacade` first, then use it

**Correct Example:**
```python
from application.notification import NotificationFacade

facade = NotificationFacade(...)
result = facade.send_watch_triggered(
    symbol='600219',
    name='南山铝业',
    price=5.15,
    condition={...},
    message='突破5.13',
    trigger_level='L2',
    action_hint={...}
)
```

**Wrong Example:**
```python
from infrastructure.notification.channels import FeishuChannel
channel = FeishuChannel(...)
channel.send(...)  # FORBIDDEN
```

**Reference:**
- Notification dev guide: `docs/guides/notification-development-guide.md`
- WatchEngine tiered design: `docs/rfcs/011-watch-engine-tiered-notification.md`

## Project Structure

```
pi-investment/
├── agent-dh/              # AI agent (DeepSeek Harness Profile)
│   ├── packages/          # Plugin packages (tools/pages/runtime/client)
│   │   ├── tools/         # Investment tools (17 plugins, 60+ tools)
│   │   ├── pages/         # Web page plugins (7 plugins)
│   │   ├── runtime/       # Runtime management
│   │   └── bundle/        # Business domain bundles
│   ├── apps/web/          # Web application shell
│   ├── .dsh-data/         # DSH_HOME (data directory)
│   └── CLAUDE.md          # Agent-DH specific docs
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
│   ├── architecture/     # Architecture documentation
│   ├── rfcs/             # Design proposals
│   ├── adr/              # Architecture decision records
│   ├── guides/           # User guides
│   ├── strategy-research/ # Strategy research
│   └── work-logs/        # Work progress logs
│
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

## 多会话并行工作规则（Worktree 隔离）

本仓库常有多个 Claude 会话与人工并行工作。**修改代码必须创建 worktree，完成并合并后再提交 GitHub。**

1. **每个独立工作线必须在独立 worktree 中开发**：`git worktree add .claude/worktrees/<name> -b feat/<name>`，不在共享主工作区直接做 feature 提交
2. **会话开始先确认分支**：`git branch --show-current` 与预期不符时停手确认，不要在被切换的分支上继续提交
3. **合并与推送**：工作线在 worktree 内完成并验证后，合并回 main（临时 worktree 或 PR），再推送 GitHub
4. **禁止在脏工作区批量覆盖**：不执行 `git checkout <ref> -- .`、`git restore --source=<ref> .` 等命令；提交前 `git status` 出现不属于自己的改动 = 停手信号，只 add 自己任务的文件
5. **IP/端口约定**：worktree 中因测试改 IP/端口的，合并前必须改回固定值（见 agent-dh/CLAUDE.md 固定端口表）

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

# 3. Start agent-dh (DSH Profile)
cd agent-dh
./scripts/start.sh  # Default port 13080
```

### Environment Variables

Create `.env` in `agent-dh/` directory:

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
✅ **This system**: Agent learns from results and adapts (genome evolution)

### Data Dump vs Intelligence

❌ **Traditional APIs**: Return raw data
✅ **This system**: Return insights, recommendations, and decision context

### Win vs Learn

❌ **Traditional focus**: High backtest returns
✅ **This system**: Sustained profitability against real opponents

## Related Documentation

- [Agent Architecture](agent-dh/CLAUDE.md) - Agent-DH DSH Profile
- [Backend API Reference](quantsys-v2/CLAUDE.md) - Quantsys-v2 backend
- [Web Frontend Guide](web-frontend/CLAUDE.md) - Monitoring dashboard
- [Project Manual](docs/architecture/project-manual.md) - 项目说明书（L1）
- [Documentation Index](docs/README.md) - 文档中心与索引
- [RFC Index](docs/rfcs/) - Design proposals
- [ADR Index](docs/adr/) - Architecture decisions

## Version History

- 2026-09-27: 任务队列改为按需求分片的 queue.json；确认门改为真正阻塞；拆分→实施段不再静默
- 2026-09-24: 盯盘通知改版上线（10 个频道专用群，降级机制，聚合回执）
- 2026-09-22: 插件 bundle 化（三个业务域 bundle）；立项链路五处收口；看板产物用词收敛
- 2026-09-20: Profile 布局更新（项目内 profile，DSH_HOME=.dsh-data）
- 2026-09-18: 盯盘引擎重构为待办化闭环
- 2026-09-17: 阶段提示词按节点×难度×类型路由注入；项目看板流程节点统一定义
- 2026-09-14: 多源 provider 框架上线；文档金字塔与需求归档规范确立
- 2026-09-13: Updated to agent-dh (DeepSeek Harness Profile)
- 2026-08-21: Added agent identity system and multi-instance lifecycle rules
- 2026-08-20: Added autonomy system (learning/evolution/genome)
- 2026-08-18: Added 文档放置规范 - document placement rules
- 2026-06-29: Documentation consolidation - created game theory framework docs
- 2026-06-25: Added system philosophy, game theory framework, autonomous agent design
- 2026-06-03: Initial three-layer architecture documentation
