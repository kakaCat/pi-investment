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

```bash
pip install -r requirements.txt
```

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
`adapters/inbound/fastapi_app/main.py` 提供服务（nohup 启动，日志 `logs/fastapi_5001.log`）。
Flask `adapters/inbound/api/server.py` 已停止，仅保留作紧急回滚。
新功能**只写 FastAPI 路由**，不再维护 Flask parity。
`start_all.py` 已不存在。

```bash
# 启动 FastAPI REST API (端口 5001)
python adapters/inbound/fastapi_app/main.py

# 启动 FastAPI WebSocket (端口 5003)
python adapters/inbound/fastapi_app/websocket_server.py

# （回滚/现状）启动旧 Flask REST API (端口 5001)
python adapters/inbound/api/server.py

# CLI (不受迁移影响)
python adapters/inbound/cli/main.py stock search --q 平安

# CLI - Indicator Commands
python adapters/inbound/cli/main.py indicators list [--type my|system]
python adapters/inbound/cli/main.py indicators create --name "策略名" --code "代码或文件路径"
python adapters/inbound/cli/main.py indicators update --id 1 --code "新代码"
python adapters/inbound/cli/main.py indicators run --id 1 --symbol 600000.SH
python adapters/inbound/cli/main.py indicators backtest --id 1 --symbol 600000.SH --start 2024-01-01 --end 2024-12-31

# 迁移工具
python check_migration.py        # 检查迁移完成度
python auto_migrate.py --help     # 自动生成路由模板
```

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

`scheduler_daemon.py`/`supervisor.py`/`manage_scheduler.py`/`unified_scheduler.py` 已于
2026-08-13 删除（daemon 无 launchd 守护，08-05 死讯静默 8 天致 T+1 中断、盯盘消失两起事故）。
旧 `quant.scheduler_task_configs` 表已全禁用（任务迁入 scheduler_tasks），表保留供回滚。
部署/重启：`launchctl kickstart -k gui/501/com.pi-investment.v2-api`（日志在 `~/v2-api.log`，
**不是** logs/fastapi_5001.log）。Flask 路由 `scheduler_enterprise.py` 随回滚栈保留，
其中 daemon 相关注释已标注，随 Flask 删除批次清理。

### Flask (已废弃，仅用于回滚)
```bash
# ⚠️ 以下命令已不再使用，保留仅供紧急回滚
# python adapters/inbound/api/server.py              # 旧 Flask API
# python adapters/inbound/api/server_websocket.py   # 旧 Flask-SocketIO
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
- **Brokers** (`domain/brokers/`) - Broker integration domain logic
- **Chan Theory** (`domain/chan/`) - 缠论 technical analysis
- **Quant Library** (`domain/quantlib/`) - Quantitative analysis, factors, risk models
- **Strategies** (`domain/strategies/`) - Trading strategy implementations
- **Benchmarks** (`domain/benchmarks/`) - Performance benchmarking tools

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

- Only use official entry points: `api/server.py`, `api/server_websocket.py`, `cli/main.py`
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
   - Read `DATA_ACCESS_GUIDE.md` (mandatory)
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
| Database CRUD | `Repository` classes | `infrastructure/repositories/` |

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

**Full documentation**: See `DATA_ACCESS_GUIDE.md`

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
**Status**: ✅ COMPLETE

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

4. **Job Registration** (`scripts/register_jobs_to_agent_os.py`)
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

Control scheduler mode via environment variable:

```bash
# Use Agent OS Scheduler (default)
USE_AGENT_OS_SCHEDULER=true

# Fall back to local SchedulerService
USE_AGENT_OS_SCHEDULER=false
```

The system automatically falls back to local scheduler if Agent OS is unreachable.

### Monitoring

Monitor jobs using the CLI script:

```bash
# Show all registered jobs
python scripts/monitor_scheduler.py

# Show scheduler statistics
python scripts/monitor_scheduler.py --stats

# Show recent executions
python scripts/monitor_scheduler.py --executions 20
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
python scripts/register_jobs_to_agent_os.py
```

Registration is idempotent and skips jobs that already exist.

### Rollback Plan

If Agent OS Scheduler fails:

1. **Set environment variable**: `USE_AGENT_OS_SCHEDULER=false` in `.env`
2. **Restart service**: `sudo launchctl kickstart -k system/com.pi-investment.v2-api`
3. **Verify**: Check logs show "Local SchedulerService background thread started (fallback mode)"
4. **Confirm**: Jobs run correctly with legacy scheduler

### Database Schema

Job execution history is written to local PostgreSQL for audit trail:

- **Table**: `quant.scheduler_runs`
- **Columns**: id, task_id, status, started_at, completed_at, duration_ms, result, error
- **Purpose**: Maintain detailed execution logs even when using Agent OS

For Agent OS jobs, a placeholder task is created in `quant.scheduler_tasks` to maintain schema compatibility.

### Legacy Code

**Deprecated** (will be removed 2026-09-01):
- `infrastructure/scheduler/scheduler.py` - Legacy SchedulerService
- Direct database operations in SchedulerService

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
