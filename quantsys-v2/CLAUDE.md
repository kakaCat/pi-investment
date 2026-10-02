# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QuantSys V2 is the **backend service system** for the PI Investment autonomous AI agent. It provides HTTP/WebSocket APIs, data persistence, and quantitative computation to support agent-driven investment decisions.

### System Role in Three-Layer Architecture

This backend serves as the **intelligence infrastructure**:

```
agent-ts → Autonomous AI Employee (decision maker)
    ↓ API calls
quantsys-v2 (this project) → Backend Service
    • HTTP/WebSocket APIs
    • Data persistence (audit trail)
    • Quant computation (backtest, factors, ML)
    • Market data integration
    ↑ Data queries
web-frontend → Monitoring Dashboard
```

### Core Mission: Enable Agent Intelligence

**Purpose**: Provide the data, computation, and intelligence infrastructure needed for the agent to:
- Make profitable trading decisions
- Identify opponent behavior (retail/institution/hot-money)
- Detect market opportunities and traps
- Learn from results and improve

**Key Principle**: Return **actionable insights**, not raw data dumps. Every API response should help the agent make better decisions.

### Architecture Philosophy

QuantSys V2 is built with hexagonal architecture, dual anti-corruption layer, and Pipeline pattern. It provides comprehensive quant pipeline for factor calculation, model prediction, backtesting, and risk assessment.

## Environment Setup

### 1. Install Dependencies

**权威声明是 `pyproject.toml`**（仓库根目录**没有** `requirements.txt`——
完整清单历史上曾被放在 `docs/misc/requirements.txt`，属归档位置，勿按它装环境）：

```bash
pip install -e .            # 或 pip install -e ".[dev]"（含 pytest/black/ruff/mypy）
```

> ⚠️ 2026-10-01 实测（REQ-261001145152-3982）：`pyproject.toml` 当时**只声明 13 个包**，
> 而代码实际硬依赖的 `pybreaker` / `pydantic-settings` / `jieba` 等**未声明也未安装**，
> 导致 119 个测试模块连 import 都失败。声明的收口由该需求的 t-504421 承担。

### 2. Database Configuration

#### Database Separation

The project uses separate databases for testing and production:

- **Production Database**: `quant_investment` - Used by API server, CLI tools, and scripts
- **Test Database**: `quant_test` - Automatically used when running pytest tests

**Automatic Switching**: The system detects when pytest is running and automatically switches to the test database. Test database names MUST end with `_test` suffix.

#### Setup Instructions

**1. Create Production Database:**
```sql
CREATE DATABASE quant_investment;
GRANT ALL PRIVILEGES ON DATABASE quant_investment TO your_user;
```

**2. Create Test Database:**
```sql
CREATE DATABASE quant_test;
GRANT ALL PRIVILEGES ON DATABASE quant_test TO your_user;
```

**3. Configure Environment Variables:**

Production (`.env`):
```bash
PGHOST=localhost
PGPORT=5432
PGDATABASE=quant_investment
PGUSER=your_username
PGPASSWORD=your_password
```

Test (`.env.test`):
```bash
PGDATABASE=quant_test
# Other variables inherited from .env
```

#### Safety Mechanism

Three-layer safety checks prevent accidental production database connections during tests:

1. **Layer 1 - conftest.py**: Validates database configuration at pytest startup
2. **Layer 2 - base_repository.py**: Runtime check for synchronous connections
3. **Layer 3 - async_base_repository.py**: Runtime check for async connections

All layers verify that the database name ends with `_test` when pytest is detected.

### 3. Run Tests

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_pipeline.py -v

# View coverage
pytest --cov=. --cov-report=html
```

## Dev Commands

### ⚠️ 重要: Flask → FastAPI 迁移（2026-08-02 更新：已切换）

**现状**：生产 5001 端口自 2026-08-02 起由 FastAPI
`adapters/inbound/fastapi_app/main.py` 提供服务。
**Flask 层已于 2026-08-19（commit `54851df0`）整体删除**（145 文件 / −32,517 行，全仓
`@app.route` 命中数为 0）——**不存在"Flask 回滚栈"**：`adapters/inbound/api/` 只剩 3 个
未被 git 跟踪的 `.bak`，且没有 `server.py`。要回滚请用 git 历史，不要在现网找 Flask 入口。
新功能**只写 FastAPI 路由**。
`start_all.py` 已不存在。

```bash
# 启动 FastAPI REST API (端口 5001)
python adapters/inbound/fastapi_app/main.py

# 启动 FastAPI WebSocket (端口 5003)
python adapters/inbound/fastapi_app/websocket_server.py

# CLI
python adapters/inbound/cli/main.py stock search --q 平安

# CLI - Indicator Commands
python adapters/inbound/cli/main.py indicators list [--type my|system]
python adapters/inbound/cli/main.py indicators create --name "策略名" --code "代码或文件路径"
python adapters/inbound/cli/main.py indicators update --id 1 --code "新代码"
python adapters/inbound/cli/main.py indicators run --id 1 --symbol 600000.SH
python adapters/inbound/cli/main.py indicators backtest --id 1 --symbol 600000.SH --start 2024-01-01 --end 2024-12-31
```

> 迁移工具 `check_migration.py` / `auto_migrate.py` 与旧 Flask 入口已于同一批次删除，
> 二者均**不存在**（2026-10-01 实测）。

### WatchEngine 实时盯盘（2026-07-22 新增；2026-08-12 迁移宿主）

WatchEngine 常驻线程**由 FastAPI `adapters/inbound/fastapi_app/main.py` 的 lifespan 唯一启动**
（经 `watch_bootstrap.start_watch_engine`，pytest 下自动跳过，句柄存 `app.state.watch_engine` 优雅停止）。
背景：08-02 部署切 FastAPI 后 daemon 未拉起，盯盘曾静默消失一周（triggers 停在 08-05）。
规则管理 API：`/api/watch/rules` CRUD（Flask + FastAPI parity）。

### 调度架构（2026-08-13 起：FastAPI lifespan 唯一宿主，scheduler_daemon 已删除）

所有周期性任务由 FastAPI 5001 进程 lifespan 内的三条后台线程承载：
- **SchedulerService**（`infrastructure/scheduler/scheduler.py` run_loop）：执行 `quant.scheduler_tasks`
  表的 cron 任务（30s 轮询，UTC cron，完整 scheduler_runs 记录 + 6h zombie reaper +
  per-task `misfire_grace_time_seconds` 宽限——NULL=唤醒必补跑，显式值=超宽限跳过记 skipped）
- **orchestrator_bootstrap**：DailyOrchestrator tick（T+1 结转/信号推送/挂单撮合）+ IntradayMonitor（止损止盈）
- **watch_bootstrap**：WatchEngine 实时盯盘

`scheduler_daemon.py`/`supervisor.py`/`manage_scheduler.py` 已于 2026-08-13 删除
（daemon 无 launchd 守护，08-05 死讯静默 8 天致 T+1 中断、盯盘消失两起事故）。
`unified_scheduler.py`（那套 YAML 配置驱动、**空转**的第四条路径）已于 2026-10-02 随
`config/scheduler_jobs.yml`、其 API 路由与专属 e2e 测试一并**删除**。

> ✅ **调度归属已定案**（2026-10-02 · 用户裁定 · [ADR-004](docs/adr/004-scheduling-ownership.md)）：
> **业务的定时任务由 v2 自己调度；agent-os 只调度 agent 自身任务**（即 `AGENT_OS_ENABLED=false`）。
> v2 侧保留两条互补路径：
> ① **`APSchedulerService`**（`infrastructure/scheduler/apscheduler_service.py`）读
>    `quant.scheduler_tasks`，跑非核心数据类任务（实时信号监控/盘前扫描/缠论/策略验证/周报等）——
>    2026-10-02 前它其实**一条都加载不了**（ORM 比库表多 `domain`/`task_type`/
>    `misfire_grace_time_seconds` 三列，查询直接报错），已由迁移
>    `infrastructure/persistence/migrations/20261002_scheduler_tasks_missing_columns.py` 修好；
> ② **DailyJobs 宿主线程**（`daily_jobs_bootstrap.py`，9 个核心数据任务，带幂等/补跑/失败告警
>    与 `quant.inprocess_job_runs` 留痕）。
> 库表启用任务已去重 **26 → 16**、撞点组 **4 → 0**；`apscheduler_jobs` 里的僵尸条目
> （11 条不在册）已清理 **27 → 16**。历史 4 路并存与重复的取证见
> `docs/requirements/REQ-261001145152-3982/design/audit-report.md` §3。
> ⚠️ 通知链路**不受影响**：`AGENT_OS_NOTIFY_ENABLED` 仍为 true（agent 优先、飞书降级）。

旧 `quant.scheduler_task_configs` 表已全禁用（任务迁入 scheduler_tasks），表保留供回滚。

**部署/重启（2026-10-02 更新：已装 launchd 守护）**：`~/Library/LaunchAgents/com.pi-investment.v2-api.plist`
**现已存在并已加载**（源自 `deployment/launchd/com.pi-investment.v2-api.plist`，
2026-10-02 · REQ-261001145152-3982 · 用户裁定"装 launchd"）。
动因：本服务先后静默死亡 3 次（08-02 盯盘消失一周 / 08-05 调度死讯静默 8 天 / 09-13 起因停摆 18 天），
共同点都是**没有守护进程**。现在 `KeepAlive` + `RunAtLoad` 保证崩溃即被拉起。

```bash
# ✅ 推荐：交给 launchd（崩溃自动拉起；实测 kill -9 后约 20 秒恢复）
launchctl kickstart -k gui/501/com.pi-investment.v2-api    # 重启（-k 先杀后起）
launchctl list | grep pi-investment                        # 看状态（第 2 列 = 上次退出码）
launchctl print gui/501/com.pi-investment.v2-api | head    # 看详情/环境变量

# 改配置后重新加载
cp deployment/launchd/com.pi-investment.v2-api.plist ~/Library/LaunchAgents/
launchctl bootout gui/501/com.pi-investment.v2-api
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.pi-investment.v2-api.plist

# 手工前台启动（排障用；现在**不需要** PYTHONPATH —— 路径引导已在 main.py 顶部）
python adapters/inbound/fastapi_app/main.py

# 只起 API、不起任何调度（排障/补数据时用）
DISABLE_APSCHEDULER=true DISABLE_DAILY_JOBS=true \
DISABLE_WATCH_ENGINE=true \
python adapters/inbound/fastapi_app/main.py
```

> ✅ **plist 里已不设任何 `DISABLE_*`**（2026-10-02 · t-2d52a7 落地后）：② APSchedulerService 与
> ③ DailyJobs 都按各自排班运行。此前四路全关是为了在滞后 18 天的数据上避免误触发补跑。
> 若要临时只起 API 停调度，见下方"调度总开关"手工启动那一段。
> 另有独立探活守护 `com.pi-investment.health-probe`（每 300 秒，与 API 进程**无关**：
> 进程死了它照样告警），plist 见 `deployment/launchd/`。

**调度总开关（2026-10-01 新增）**：`DISABLE_APSCHEDULER=true` 关掉 APScheduler 回退路径——
此前只有 `DISABLE_DAILY_JOBS` 与 `DISABLE_UNIFIED_SCHEDULER`，**关不掉回退路径**，
于是"服务一重启就补跑已过点任务"（在滞后数据上开火）。四个开关默认均为 false（行为不变）。

**日志轮转（2026-10-01 新增，`infrastructure/logging/config.py`）**：日志此前只走 stdout，
靠调用方 shell 重定向落盘 → 出现过 174M/168M 的单文件与 5.2G 的 `live_trading/logs/`。
现在设 `LOG_FILE` 即启用按大小轮转（不设则行为不变）：

```bash
LOG_FILE=logs/api.log LOG_MAX_BYTES=52428800 LOG_BACKUPS=5 python adapters/inbound/fastapi_app/main.py
```

### Flask (已于 2026-08-19 整体删除，**无回滚栈**)
```bash
# ❌ 以下入口均不存在（2026-10-01 实测）：
# python adapters/inbound/api/server.py              # 旧 Flask API（文件已删）
# python adapters/inbound/api/server_websocket.py    # 旧 Flask-SocketIO（文件已删）
# 需要旧行为请从 git 历史 commit 54851df0^ 取回，不要在现网查找 Flask 入口。
```

## Architecture

### Hexagonal Architecture (Ports & Adapters)

The codebase follows hexagonal architecture principles with clear separation of concerns.

### Design Philosophy: Intelligence Infrastructure

**Beyond Data APIs**: QuantSys V2 is not just a data warehouse — it's an **intelligence assistant** for the AI agent.

**Key Principles**:
1. **Return Insights, Not Just Numbers**
   - ❌ Bad: `{"price": 150.5, "volume": 1000000}`
   - ✅ Good: `{"price": 150.5, "volume": 1000000, "analysis": {"volume_spike": true, "vs_avg": "+250%", "interpretation": "Abnormal buying pressure"}}`

2. **Provide Decision Context**
   - Include "why" in responses (explain anomalies, trends)
   - Suggest actions with confidence scores
   - Highlight risks and opportunities

3. **Support Game-Theoretic Analysis**
   - Track opponent behavior (retail/institution/hot-money flows)
   - Identify manipulation patterns (pump-and-dump)
   - Detect competitive advantages (battlefield assessment)

4. **Enable Agent Learning**
   - Log all operations (audit trail)
   - Track decision outcomes (profit/loss)
   - Support attribution analysis (what worked, what didn't)

### Data Audit Trail System

Every agent operation is persisted for learning and accountability:

**Key Tables**:
- `agent_decisions` — Decision log (type, context, parameters, reasoning, outcome)
- `agent_knowledge` — Learned rules and patterns (domain, confidence, evidence)
- `pool_change_log` — Stock pool member changes (add/remove/refresh, reason)
- `strategy_performance` — Real trade results (entry/exit price, P&L, holding days)

**Purpose**:
- Performance attribution (which decisions led to profit/loss?)
- Strategy improvement (which parameters work best?)
- Failure analysis (why did this trade lose money?)
- Knowledge accumulation (build expertise over time)

### 筹码分布（成本分布）（2026-08-11 新增）

- `quant.chip_distribution_state` — 筹码分布滚动状态（每股票一行价位桶数组，增量计算的"内存"）
- `quant.chip_metrics` — 筹码每日摘要指标：profit_ratio（获利盘比例）/ avg_cost / 90%/70% 成本区间 / peak_price（密集峰）/ concentration（集中度）
- 每日任务：`chip_distribution_update`（cron 30 18 * * 0-4，接 kline_update 后），job `infrastructure/jobs/chip_distribution_update_job.py`
- 查询 API：`GET /api/analysis/chip-distribution/{symbol}`；agent 工具：`chip_analysis`
- 计算核心：`domain/chip_distribution/`（三角分布 + 换手率衰减模型，spec: docs/superpowers/specs/2026-08-11-chip-distribution-design.md）

### Game Theory Intelligence System (Roadmap)

**P0 - Required APIs for Competitive Intelligence**:

1. **Opponent Behavior Tracking**
   ```python
   GET /api/market/opponent-behavior
   Returns: {
     retail: { behavior: "panic_selling", net_flow: -50亿, emotion: 20 },
     institution: { behavior: "bottom_fishing", net_flow: +35亿 },
     hot_money: { behavior: "pump_and_dump", target_stocks: [...] },
     opportunity_map: {
       take_from_retail: [{ strategy: "bottom_fishing", confidence: 0.85 }]
     }
   }
   ```

2. **Pool Battlefield Assessment**
   ```python
   GET /api/pools/battlefield-assessment
   Returns: [{
     pool_id: 5,
     battlefield_score: 35,  # 0-100, competitive advantage
     game_analysis: {
       your_advantage: ["持仓成本低"],
       your_disadvantage: ["机构在出货"],
       opponent_strength: { institution: "strong", retail: "weak" }
     },
     recommendation: "exit",
     urgency: "high"
   }]
   ```

3. **Real-time Game Alerts**
   ```python
   WebSocket: /ws/game-alerts
   Pushes: {
     type: "opportunity",
     alert: "检测到散户恐慌性抛售",
     action: "create_bottom_fishing_pool",
     urgency: "high",
     expected_window: "2-4 hours"
   }
   ```

4. **Pool Risk with Game Context**
   ```python
   GET /api/pools/{id}/risk-assessment
   Returns: {
     risk_signals: [
       { type: "institution_exit", severity: "high", 
         message: "检测到5家机构席位净卖出8000万" }
     ],
     game_phase: "distribution",  # accumulation/markup/distribution/markdown
     recommendation: "机构出货，散户接盘，建议兑现利润"
   }
   ```

5. **Manipulation Detection**
   ```python
   GET /api/market/manipulation-detect
   Returns: {
     manipulated_stocks: [
       { symbol: "000XXX", type: "pump_and_dump", stage: "distribution", 
         action: "avoid" }
     ],
     post_manipulation_opportunities: [
       { symbol: "000YYY", stage: "collapse_complete", 
         fair_value: 10.2, current_price: 8.5, upside: "+20%",
         action: "bottom_fishing" }
     ]
   }
   ```

### Hexagonal Architecture (Ports & Adapters)

The codebase follows hexagonal architecture principles with clear separation of concerns:

#### Domain Layer (`domain/`)
Core business logic and domain models (no external dependencies):
- **Accounts** (`domain/accounts/`) - 账户、资金、余额
  - Models: Account, Balance
  - Services: AccountService
  - Ports: IAccountRepository
- **Trading** (`domain/trading/`) - 订单、成交
  - Models: Order, Trade
  - Services: OrderService
  - Ports: IOrderRepository, ITradeRepository
- **Portfolio** (`domain/portfolio/`) - 持仓、资产配置
  - Models: Position
  - Services: PositionService
  - Ports: IPositionRepository
- **Legacy** (`domain/legacy/`) - 旧系统适配器
  - LegacyOrderAdapter: 向后兼容旧 order_service API
- **Brokers** (`domain/brokers/`) - Broker integration domain logic
- **Chan Theory** (`domain/chan/`) - 缠论 technical analysis
- **Quant Library** (`domain/quantlib/`) - Quantitative analysis, factors, risk models
- **Strategies** (`domain/strategies/`) - Trading strategy implementations
- **Benchmarks** (`domain/benchmarks/`) - Performance benchmarking tools

**Domain Dependency Rule**: trading → accounts + portfolio; accounts and portfolio have no dependency on each other.

**Service Factory**: `domain/service_factory.py` provides singleton `DomainServiceFactory` for dependency injection.

#### Application Layer (`application/`)
Use case orchestration and application services:
- **Services** (`application/services/`) - Business logic orchestration
  - Strategy execution, data services, ML pipeline, cache services, etc.

#### Adapters Layer (`adapters/`)
External system integration (implements ports):

**Inbound Adapters** (`adapters/inbound/`) - External systems calling us:
- **API** (`adapters/inbound/api/`) - REST API endpoints (Flask)
- **CLI** (`adapters/inbound/cli/`) - Command-line interface

**Outbound Adapters** (`adapters/outbound/`) - We call external systems:
- **Repositories** (`adapters/outbound/repositories/`) - Data persistence (PostgreSQL)
- **Data Sources** (`adapters/outbound/datasources/`) - External data providers (akshare, tushare, etc.)

#### Infrastructure Layer (`infrastructure/`)
Technical infrastructure and cross-cutting concerns:
- **Persistence** (`infrastructure/persistence/`) - Database connections and migrations
- **Cache** (`infrastructure/cache/`) - Cache services (Memory/Redis)
- **Events** (`infrastructure/events/`) - Event bus and pub-sub messaging
- **Scheduler** (`infrastructure/scheduler/`) - Cron scheduling and background jobs
- **Jobs** (`infrastructure/jobs/`) - Background job implementations
- **Daemon** (`infrastructure/daemon/`) - Long-running daemon processes
- **Config** (`infrastructure/config/`) - Configuration management
- **Utils** (`infrastructure/utils/`) - Utility functions

### DI 入口分层（2026-10-02 · REQ-261001145152-3982 t-71051b）

**唯一入口 = `ServiceFactory`**（`infrastructure/services/service_factory.py`）。取服务一律走它：
具名 getter（如 `get_stock_pool_service()`）或**按端口解析** `ServiceFactory.resolve(IStockRepository)`。
下面两层是**内部实现层，调用方不该直接引用**：

| 层 | 文件 | 职责 | 现状 |
|---|---|---|---|
| **入口** | `service_factory.py` | 调用方唯一入口（72 文件在用） | ✅ 权威 |
| 内部层 | `enhanced_service_factory.py` | 端口→实现绑定与生命周期（`resolve`/`register`） | 仍有 34 个生产文件直接引用 → **待分批迁到入口** |
| 内部层 | `service_registry.py` | `create_*` 工厂函数 + `register_all_services()` 注册 | 仍有 9 个生产文件直接引用 → **同上** |
| ~~第四套~~ | ~~`infrastructure/di/`~~ | 死件（生产零引用，只有 2 个测试用） | **已删除**（连幽灵依赖 `dependency-injector` 一并移除） |

> 历史观感是"4 套 DI 并存"，实测是**1 入口 + 2 内部层 + 1 死件**：`service_factory` 内部本就在
> 调用另两层（`_ensure_enhanced_factory` / `_try_get_from_enhanced`），并非平行实现。
> 收敛动作分两批（本卡只做了安全部分）：① 死件已删；② 34+9 个直接引用者分批改走
> `ServiceFactory`（机械替换，但属运行时装配，需逐批验证）。

### Key Patterns

- **Dual Anti-Corruption Layer**: CLI/API/Scheduler → Services → Repositories
- **Pipeline Pattern**: Composable stages for factor → model → backtest flow
- **Generic Methods**: Avoid caller-specific methods; use parameters for different scenarios
- **Backward Compatibility**: Legacy import paths maintained via shim files during migration

## Financial Indicators in Strategy Code

Strategy code now has access to 18 financial indicator columns (9 indicators × quarterly/annual):

**Quarterly indicators** (_q suffix):
- `roe_q` - Return on Equity (%)
- `gross_margin_q` - Gross Profit Margin (%)
- `net_profit_margin_q` - Net Profit Margin (%)
- `debt_ratio_q` - Debt to Asset Ratio (%)
- `revenue_growth_q` - Revenue Growth YoY (%)
- `ocf_to_profit_q` - Operating Cash Flow / Net Profit
- `current_ratio_q` - Current Ratio
- `roa_q` - Return on Assets (%)
- `operating_margin_q` - Operating Profit Margin (%)

**Annual indicators** (_y suffix): Same 9 indicators with `_y` suffix

**Data source:** akshare (Sina Finance primary, East Money fallback)
**Temporal alignment:** Forward-fill based on announcement date (no future information leakage)
**Missing data:** Columns filled with NaN when data unavailable

## Technical Indicators in Strategy Code

Strategy code also has access to pre-calculated technical indicators:

**Trend Indicators:**
- `rsi` - Relative Strength Index (14-period)
- `macd` - MACD fast line
- `macd_signal` - MACD signal line
- `macd_hist` - MACD histogram

**Volatility Indicators:**
- `atr` - Average True Range (14-period, Wilder's smoothing)
- `bollinger_upper` - Bollinger Bands upper band (20-period, 2σ)
- `bollinger_middle` - Bollinger Bands middle band (SMA)
- `bollinger_lower` - Bollinger Bands lower band

**Moving Averages:**
- `ma5` - 5-day moving average
- `ma10` - 10-day moving average
- `ma20` - 20-day moving average
- `ma60` - 60-day moving average

**Usage example:**
```python
# Filter quality stocks (fundamental)
df['quality'] = (df['roe_y'] >= 15) & (df['debt_ratio_y'] < 60)

# Technical signals
df['oversold'] = df['rsi'] < 30
df['ma_cross'] = (df['ma5'] > df['ma20']) & (df['ma5'].shift(1) <= df['ma20'].shift(1))

# Volatility-based stop loss (2x ATR)
df['stop_loss_distance'] = df['atr'] * 2

# Buy signal: quality + technical oversold or MA cross
df['buy'] = df['quality'] & (df['oversold'] | df['ma_cross'])

# Sell signal: overbought or hit stop loss
df['sell'] = df['rsi'] > 70
```

**Note:** All indicators are automatically injected before strategy execution. Early rows may have NaN values due to insufficient historical data for calculation.

See `examples/strategy_with_financials.py` for a complete example.

## Indicator Endpoints

- `GET /api/indicators/sandbox-columns?symbol=600000.SH` - 沙箱列可用性探查
- `POST /api/indicators/compare` - 双策略对比回测
- `POST /api/indicators/backtest` - 回测指标（包含 summary 摘要）

## 参数搜索引擎（2026-05-29）

**P0-1 完成**：真实回测打分替代假优化器。

### 核心功能

1. **SearchSpace 参数网格生成器**：笛卡尔积生成参数组合
2. **StrategyOptimizer 并行回测引擎**：10 个 worker 并行执行真实回测
3. **POST /api/strategies/optimize**：返回按 Sharpe 排序的最优参数
4. **strategy.optimize CLI 命令**：调用 v2 API（不再使用 v1 假优化器）

### 使用示例

```bash
# CLI 调用
python cli/main.py strategy.optimize \
  --strategy_id 1 \
  --symbol 600000.SH \
  --start_date 2024-01-01 \
  --end_date 2024-12-31 \
  --param_ranges '{"fast": [5, 10, 20], "slow": [20, 50, 60]}'

# API 调用
curl -X POST http://127.0.0.1:5001/api/strategies/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "strategyId": 1,
    "symbol": "600000.SH",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31",
    "paramRanges": {"fast": [5, 10, 20], "slow": [20, 50, 60]}
  }'
```

### 性能

- 100 组参数搜索：< 60s（10x 并行加速）
- 自动处理回测失败（跳过失败组合）
- 支持所有用户自定义策略

### 相关文档

- 完成文档：`docs/superpowers/specs/2026-05-29-p0-1-parameter-search-completion.md`
- 实现计划：`docs/plans/strategy-loop-closure-plan.md`

## 策略模板类型（2026-05-29）

**P1 完成**：扩展用户策略模板，支持 5 种 code_type。

### 支持的策略类型

系统支持 5 种策略代码类型：

| code_type | 说明 | 适用场景 |
|-----------|------|---------|
| `indicator` | 指标策略 | 基于技术指标生成买卖信号（df['buy'], df['sell']） |
| `script` | 脚本策略 | 事件驱动策略（on_init, on_bar 函数） |
| `trend_following` | 趋势跟踪模板 | 均线交叉、通道突破、动量策略 |
| `mean_reversion` | 均值回归模板 | RSI/CCI 反转、布林带回归 |
| `multi_factor` | 多因子模板 | 多因子评分、因子组合策略 |

### 模板策略要求

所有模板策略（trend_following, mean_reversion, multi_factor）必须：
- 生成 `df['buy']` 买入信号列
- 生成 `df['sell']` 卖出信号列
- 使用 pandas DataFrame 操作
- 遵循代码安全规范（禁止文件操作、网络请求等）

### 使用示例

**趋势跟踪策略**：
```python
# 参数: fast=5, slow=20, atr_multiplier=2.0

# 计算均线
df['ma_fast'] = df['close'].rolling(window=5).mean()
df['ma_slow'] = df['close'].rolling(window=20).mean()

# 买入信号：快线上穿慢线
df['buy'] = (df['ma_fast'] > df['ma_slow']) & (df['ma_fast'].shift(1) <= df['ma_slow'].shift(1))

# 卖出信号：快线下穿慢线
df['sell'] = (df['ma_fast'] < df['ma_slow']) & (df['ma_fast'].shift(1) >= df['ma_slow'].shift(1))
```

**均值回归策略**：
```python
# 参数: lookback=20, oversold=30, overbought=70

# 计算 RSI
df['rsi'] = df['close'].rolling(window=20).mean()

# 买入信号：超卖
df['buy'] = df['rsi'] < 30

# 卖出信号：超买
df['sell'] = df['rsi'] > 70
```

**多因子策略**：
```python
# 参数: factors=['momentum', 'value'], weights=[0.6, 0.4], threshold=0.7

# 计算动量因子
df['momentum'] = df['close'].pct_change(20)

# 计算价值因子
df['value'] = 1 / df['close']

# 综合评分
df['score'] = df['momentum'] * 0.6 + df['value'] * 0.4

# 买入信号：评分超过阈值
df['buy'] = df['score'] > 0.7

# 卖出信号：评分低于阈值
df['sell'] = df['score'] < 0.3
```

### API 端点

- `POST /api/strategies/create` - 创建策略（支持 5 种 code_type）
- `GET /api/strategies/list?source=builtin` - 列出内置策略（18 种）
- `GET /api/strategies/list?code_type=trend_following` - 按类型筛选用户策略

### 相关文件

- 代码验证器：`quantlib/engine/code_validator.py`
- 策略服务：`services/strategy_code_service.py`
- 策略仓储：`repositories/strategy_repository.py`
- 测试：`tests/test_strategy_templates.py`

## Active Conventions

- Only use official entry points（2026-10-01 修正为真实路径）：
  `adapters/inbound/fastapi_app/main.py`（API，5001）、
  `adapters/inbound/fastapi_app/websocket_server.py`（WS，5003）、
  `adapters/inbound/cli/main.py`（CLI）。
  ⚠️ 旧写法 `api/server.py` / `api/server_websocket.py` / `cli/main.py` **均不存在**。
- No `_backup`, `_v2`, `_old`, `_new` parallel files in `api/` or `cli/`
- Delete obsolete code after references are removed; example code goes to `docs/examples/`
- Test coverage target: > 80% for core modules
- All tests must pass before committing

## ⚠️ Data Access Rules - PREVENT DUPLICATE CODE

**CRITICAL**: This project has unified data access layers. **DO NOT** create duplicate implementations!

### Mandatory Rules

1. **NEVER directly import external data libraries**
   - ❌ `import akshare`, `import tushare`, `import yfinance`
   - ❌ Custom data source switching logic
   - ❌ Scripts that bypass `DataProviderManager`

2. **ALWAYS use the unified data access layer**
   - ✅ `DataProviderManager` for external data (K-line, quotes, dividends)
   - ✅ `DataService` for business logic
   - ✅ `Repository` for database access

3. **Before writing data-related code**
   - 数据访问规范见本文件「⚠️ Data Access Rules」一节 + `docs/DATA_ACCESS_GUIDE.md`
     （⚠️ 2026-10-01 实测：根目录**没有** `DATA_ACCESS_GUIDE.md`，历史文档已失；以本文件该节为准）
   - Check if functionality already exists in `DataProviderManager`
   - Ask "Am I reinventing the wheel?"

### Quick Reference

| Need | Use | Location |
|------|-----|----------|
| K-line data | `DataProviderManager.get_klines()` | `adapters/outbound/datasources/manager.py` |
| Realtime quote | `DataProviderManager.get_quote()` | Same as above |
| Dividends | `DataProviderManager.get_dividends()` | Same as above |
| Sector constituents (板块成分) | `DataProviderManager.get_sector_stocks(sector)` | Same as above |
| Business logic | `DataService.kline.*` | `application/services/data_service.py` |
| Database CRUD | `Repository` classes | `adapters/outbound/repositories/`（73 文件；⚠️ `infrastructure/` **下没有** repositories 子目录，2026-10-01 实测） |

### 仓储双轨口径（sync / async，2026-10-01 裁定 · REQ-261001145152-3982 t-52c511）

`adapters/outbound/repositories/` 里对 8 个实体各有 **sync 与 async 两份实现**
（`x_repository.py` / `x_async_repository.py`：stock / signal / portfolio / simulation /
factor / backtest / stock_pool / signal_execution）。
另有 **async-only 模块**（`p2_async_repositories.py`：MLModel / Position / FundFlow / DataQuality
四个 Async 仓储，无 sync 对应）——它们同样遵守下面的第 1~3 条。

**实测现状（2026-10-01）**：两条轨**都在服务线上功能，谁都不能直接删**——
- sync 轨 8 文件 **5,551 行**，被 **52 个文件**引用（CLI、调度、adapters、多个服务）；
- async 轨 8 文件 **1,618 行**，只被 **2 处**仓储引用，但其中 `realtime_signals_async` 路由
  已在 `main.py` 注册、`charts_async.py` 正是 K 线图表接口的实现路径（此前 greenlet 缺失
  导致它静默返回空数组的那条链路）。

> 数字可复现（在 `quantsys-v2/` 下执行）：
> ```bash
> wc -l adapters/outbound/repositories/{stock,signal,portfolio,simulation,factor,backtest,stock_pool,signal_execution}_repository.py | tail -1
> wc -l adapters/outbound/repositories/{stock,signal,portfolio,simulation,factor,backtest,stock_pool,signal_execution}_async_repository.py | tail -1
> grep -rln "outbound.repositories\.\(stock\|signal\|portfolio\|simulation\|factor\|backtest\|stock_pool\|signal_execution\)_repository" --include='*.py' . | grep -v venv | wc -l   # 52
> grep -rln "outbound.repositories\.\(stock\|signal\|portfolio\|simulation\|factor\|backtest\|stock_pool\|signal_execution\)_async_repository" --include='*.py' . | grep -v venv | wc -l   # 2
> ```
> （口径提醒：引用数随 grep 模式变——写成 `_repository` 前缀会连 async 的一起命中，
> 故此处用**精确到实体名**的模式。2026-10-01 复核时正是这样发现初稿写的 54/1,418 不准确。）

**口径（新代码照此选）**：
1. **FastAPI 异步路由 / async 服务** → 用 `x_async_repository.py`（`AsyncBaseORMRepository`）；
2. **CLI、调度任务、其它同步上下文** → 用 `x_repository.py`；
3. **不要为同一实体再新建第三份实现**；需要新实体时按上述两条各建一份或只建实际需要的那份；
4. **已知不一致（本次不重构，仅登记）**：两侧拆分粒度不同——async 轨按实体拆类
   （如 `simulation_async_repository.py` 内 `SimulationAccount/Position/Trade` 三个 Async 仓储），
   sync 轨偏聚合（`simulation_repository.py` 单文件单仓储类 + helper）。新代码沿用**本轨既有粒度**，
   不要顺手"对齐"成另一种（会牵动调用方）；
5. 收敛成单轨属**架构级改造**（要么改写 3 个异步路由、要么迁移 52 个调用方），
   不在本需求范围；做之前先按上面第 1~2 条评估影响面。

### Example

```python
# ✅ CORRECT
from adapters.outbound.datasources.manager import get_data_provider_manager

manager = get_data_provider_manager()
result = manager.get_klines('600519', 'daily', '2026-07-01', '2026-07-17')
if result['success']:
    klines = result['data']  # Auto-fallback: database → akshare

# ❌ WRONG - Creates duplicate code!
import akshare as ak
df = ak.stock_zh_a_hist(symbol='600519', ...)  # DON'T DO THIS!
```

### Deprecated Code

| File | Status | Replace With |
|------|--------|--------------|
| `scripts/update_klines_multi_source.py` | ⚠️ DEPRECATED (2026-07-17) | `scripts/update_klines_recommended.py` |
| `scripts/batch_update_klines.py` | ⚠️ Legacy, avoid | `DataProviderManager.get_klines()` |

**Full documentation**: 见本文件「⚠️ Data Access Rules」一节；原 `DATA_ACCESS_GUIDE.md`
已不存在（2026-10-01 实测），其唯一入口 API 是
`adapters/outbound/datasources/manager.py` 的 `get_data_provider_manager()`。

## Backend Service Principles for Agent Support

When developing new features for QuantSys V2, follow these principles:

### 1. Return Insights, Not Just Data

❌ **Bad**: Return raw database rows
```python
return {"stocks": [{"symbol": "600519", "roe": 25, "pe": 45}]}
```

✅ **Good**: Return analyzed insights
```python
return {
  "stocks": [...],
  "analysis": {
    "valuation": "PE at 90th percentile (expensive)",
    "quality": "ROE excellent (top 10%)",
    "recommendation": "Good company but wait for better entry"
  }
}
```

### 2. Provide Decision Context

Every significant API response should include:
- **What**: The data/result
- **Why**: Analysis of patterns, anomalies, trends
- **Action**: Suggested next steps with confidence
- **Risk**: Potential issues to watch

### 3. Support Game-Theoretic Intelligence

Include opponent behavior analysis when relevant:
- Who's buying? (retail vs institution)
- Who's selling? (smart money vs dumb money)
- What phase? (accumulation/distribution)
- Where's the opportunity? (exploit opponent mistakes)

### 4. Enable Agent Learning

Log operations with context:
```python
# When agent makes a decision via API
log_agent_decision(
    decision_type="pool_refresh",
    context={"pool_id": 5, "trigger": "scheduled"},
    parameters={"min_roe": 15},
    reasoning="Standard quality threshold",
    timestamp=now()
)

# Later, when outcome is known
update_decision_outcome(
    decision_id=101,
    result={"stocks_added": 3, "stocks_removed": 2},
    performance={"pool_return_30d": "+5.2%"},
    learned_lesson="This ROE threshold works well"
)
```

### 5. Detect Anomalies Proactively

Don't wait for agent to ask — push alerts when:
- Pool health deteriorates
- Opponent behavior shifts
- Market regime changes
- Manipulation detected

Example:
```python
# In pool validation service
if institution_flow < -5000万 and retail_flow > +3亿:
    emit_game_alert(
        type="risk",
        message="机构出货，散户接盘",
        affected_pools=[5],
        urgency="high"
    )
```

## Stock Pool Optimization Roadmap

Based on game-theoretic intelligence requirements:

**Phase 1 - Data Foundation** (Current):
- ✅ Pool CRUD (create/read/update/delete)
- ✅ Dynamic pool refresh
- ✅ Multi-strategy validation
- ✅ Member-level annotations

**Phase 2 - Game Intelligence** (Next):
- ⏳ Opponent behavior tracking API
- ⏳ Battlefield assessment API
- ⏳ Real-time game alerts (WebSocket)
- ⏳ Manipulation detection

**Phase 3 - Learning System** (Future):
- ⏳ Decision outcome tracking
- ⏳ Attribution analysis
- ⏳ Knowledge base accumulation
- ⏳ Strategy auto-optimization

**Phase 4 - Advanced Intelligence** (Future):
- ⏳ Multi-pool portfolio optimization
- ⏳ Dynamic risk budgeting
- ⏳ Adaptive strategy selection
- ⏳ Market regime detection

---

## Scheduler Migration to Agent OS (WP-15)

**Migration Date**: 2026-08-16  
**Status**: ⚠️ 代码已实现，但**当前不生效**（2026-10-01 实测：Agent OS 8080 不可达 →
启动时注册失败 → 全部回退到本地 `APSchedulerService`）。本节描述的是**设计意图**，不是现网运行态；
现网运行态**已按 [ADR-004](docs/adr/004-scheduling-ownership.md) 定案**：业务的定时任务由 v2 自己调度
（`AGENT_OS_ENABLED=false`），本节描述的是已被取代的历史设计意图。

All scheduled jobs have been migrated from local `SchedulerService` to **Agent OS Scheduler** via webhook integration.

### Architecture

```
Agent OS Scheduler (port 8080)
    ↓ HTTP POST webhook
quantsys-v2 Webhook Receiver (/internal/scheduler/webhook)
    ↓ dispatch by job_type
Job Handler (application/services/scheduler_handlers.py)
    ↓ execute business logic
PostgreSQL (scheduler_runs table for audit trail)
    ↓ report results
Agent OS Scheduler (result tracking)
```

### Key Components

1. **Agent OS Client** (`application/services/agent_os_client.py`)
   - HTTP client for Agent OS Scheduler API
   - Methods: register_job, list_jobs, trigger_job, report_job_result
   - Async/await based using httpx

2. **Webhook Receiver** (`api/internal/scheduler_webhook.py`)
   - Endpoint: `POST /internal/scheduler/webhook`
   - Receives job execution triggers from Agent OS
   - Dispatches to registered handlers via `@register_job_handler` decorator
   - Executes in FastAPI background tasks (non-blocking)

3. **Job Handlers** (`application/services/scheduler_handlers.py`)
   - 30+ handlers for all scheduled tasks
   - Delegates to existing service methods
   - Returns structured result dictionaries

4. **Job Registration** (`tools/register_jobs_to_agent_os.py`；⚠️ 旧写法 `scripts/...` 不存在)
   - Defines all 30+ job schedules and metadata
   - Idempotent registration (skips existing jobs)
   - Auto-runs on FastAPI startup

### Registered Jobs

All jobs are registered with owner `quantsys-v2`:

**Daily Jobs** (工作日):
- `kline_update` - 17:40 - Update K-line data
- `chip_distribution_update` - 10:30 - Calculate chip distribution
- `signal_generate_buy` - 09:00 - Scan buy signals
- `signal_generate_sell` - 15:30 - Scan sell signals
- `signal_execution_daily` - 07:30 - Execute signals
- `factor_compute_daily` - 08:00 - Compute factors
- `data_quality_check_daily` - 16:00 - Check data quality
- `strategy_validate_daily` - 13:00 - Validate strategies
- `v13_daily_check` - 14:30 - V13 trading check
- `v13_risk_check` - 16:00 - V13 risk check
- `v13_verification` - 16:30 - V13 verification
- `market_style_update` - 15:30 - Detect market style
- `data_pipeline_daily` - 08:30 - Daily data pipeline
- `chan_scan_daily` - 10:10 - Chan theory scan
- `daily_equity_snapshot` - 18:00 - Equity snapshot

**Weekly Jobs**:
- `financial_statement_update` - 周六 20:00 - Financial statements
- `financial_data_update` - 周六 18:30 - Financial data
- `v13_weekly_report` - 周六 10:00 - V13 report
- `risk_check_weekly` - 周一 01:00 - Risk assessment
- `data_pipeline_weekly` - 周六 18:00 - Full rebuild
- `report_weekly` - 周五 10:00 - Weekly report
- `chan_knowledge_distill_weekly` - 周日 12:00 - Chan distillation
- `strategy_discover_weekly` - 周日 14:00 - Strategy discovery

**Other Jobs**:
- `pool_refresh_daily` - 每日 02:00 - Refresh pools
- `v14_daily_check` - 14:30 - V14 trading (disabled)

### Feature Flag

控制调度归属的环境变量（2026-10-01 修正为**真实**开关——旧文档写的
`USE_AGENT_OS_SCHEDULER` 在代码里**零引用**，是个不存在的开关）：

```bash
AGENT_OS_ENABLED=false         # 调度权归 v2（ADR-004）。代码默认仍是 true，但本仓 .env 已置 false；
                               # 置 false 后启动不再尝试注册 Agent OS 调度器
AGENT_OS_NOTIFY_ENABLED=true   # **通知**开关，与上面那个分开：仍 agent 优先、飞书降级
DISABLE_APSCHEDULER=true       # 临时关掉 ② 库表调度（只起 API 时用）
DISABLE_DAILY_JOBS=true        # 临时关掉 ③ DailyJobs 宿主线程
DISABLE_WATCH_ENGINE=true      # 临时关掉实时盯盘线程
# 注：DISABLE_UNIFIED_SCHEDULER 已随那条路径一起删除（2026-10-02）
```

The system automatically falls back to local scheduler if Agent OS is unreachable.

### Monitoring

Monitor jobs using the CLI script（⚠️ 路径修正如实测：在 `tools/`，不在 `scripts/`）:

```bash
# Show all registered jobs
python tools/monitor_scheduler.py

# Show scheduler statistics
python tools/monitor_scheduler.py --stats

# Show recent executions
python tools/monitor_scheduler.py --executions 20
```

Or query Agent OS directly:

```bash
# List all jobs
curl http://127.0.0.1:8080/api/v1/scheduler/tasks | jq

# Get job details
curl http://127.0.0.1:8080/api/v1/scheduler/tasks/{job_id} | jq

# List recent executions
curl http://127.0.0.1:8080/api/v1/scheduler/executions?limit=10 | jq

# Manually trigger a job
curl -X POST http://127.0.0.1:8080/api/v1/scheduler/tasks/{job_id}/trigger
```

### Manual Job Registration

If needed, manually register jobs:

```bash
cd quantsys-v2
python tools/register_jobs_to_agent_os.py
```

Registration is idempotent and skips jobs that already exist.

### Rollback Plan

If Agent OS Scheduler fails（2026-10-01 修正：原第 1、2 步给出的开关与 launchctl 标签**都不存在**）:

1. **什么都不用设**：Agent OS 不可达时启动会自动回退到 `APSchedulerService`（无需开关）。
   若要**显式禁用**某一路调度，用 `DISABLE_APSCHEDULER` / `DISABLE_DAILY_JOBS` /
   `DISABLE_WATCH_ENGINE`（见上文"调度总开关"）。
2. **重启服务**（2026-10-02 更新：已有 launchd 守护）：
   `launchctl kickstart -k gui/501/com.pi-investment.v2-api`
   （plist 见 `deployment/launchd/com.pi-investment.v2-api.plist`；崩溃会被 KeepAlive 自动拉起，
   实测 kill -9 后约 20 秒恢复）。若无 launchd，再退回手工 `python adapters/inbound/fastapi_app/main.py`。
3. **Verify**: 日志出现 `✅ APScheduler started (fallback mode)`。
4. **Confirm**: `select max(started_at) from quant.scheduler_runs` 随任务执行刷新。

### Database Schema

Job execution history is written to local PostgreSQL for audit trail:

- **Table**: `quant.scheduler_runs`
- **Columns**: id, task_id, status, started_at, completed_at, duration_ms, result, error
- **Purpose**: Maintain detailed execution logs even when using Agent OS

For Agent OS jobs, a placeholder task is created in `quant.scheduler_tasks` to maintain schema compatibility.

### Legacy Code

**2026-10-01 实测修正**：原文写"`infrastructure/scheduler/scheduler.py` 将于 2026-09-01 移除"——
**它并没有被移除**，至今仍被 22 个文件引用（adapters/api/application/infrastructure/scripts/tests），
但 `run_loop` 已不再由 lifespan 启动（现网由 `APSchedulerService` + DailyJobs 线程承担）。
它现在处于"文件很大、引用很多、但不驱动生产调度"的悬置状态。
**t-2d52a7 的裁定（2026-10-02）**：生产调度由 `APSchedulerService`（②，读 `quant.scheduler_tasks`）
与 DailyJobs（③）承担，`scheduler.py` 的 `run_loop` **不再被启动**；其去留（删除 or 保留作库）
不阻塞本次定案，留待后续单独评估——删除它会牵动 22 个引用方，须单独开卡。

**Preserved**:
- Job handler business logic (reused by webhook handlers)
- Database tables (used for audit trail)
- Command dispatch logic (reused by handlers)

### Benefits

✅ **Centralized scheduling** - All 3 systems (agent-ts, quantsys-v2, agent-os) use one scheduler  
✅ **Better visibility** - Unified dashboard for all scheduled tasks  
✅ **Improved reliability** - Agent OS handles cron parsing, misfires, retries  
✅ **Zero downtime** - Fallback to local scheduler if Agent OS fails  
✅ **Preserved audit trail** - All executions still logged to PostgreSQL  
✅ **Simplified deployment** - No need to manage separate scheduler processes

### Related Work

- **WP-12**: Agent OS Scheduler HTTP API (dependency, completed 2026-08-16)
- **WP-13**: agent-ts integration with Agent OS Scheduler (parallel work)
- **WP-14**: Skill Hub integration with Agent OS Scheduler (parallel work)
