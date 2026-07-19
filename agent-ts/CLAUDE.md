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

**Intelligence Metrics**:
- Win rate in real trades
- Sharpe ratio vs market
- Ability to avoid traps (institutional distribution, hot-money schemes)
- Speed of adaptation to market regime changes

### Agent Characteristics

✅ **Autonomous**: Executes scheduled tasks without human prompts
✅ **Proactive**: Monitors markets and responds to opportunities
✅ **Self-learning**: Analyzes results and improves decision quality
✅ **Game-aware**: Identifies opponent behavior and exploits mistakes

**Architecture**:
- **`src/`** — TypeScript AI agent (primary). Interactive CLI/TUI with tool registry, Feishu bot integration, session management, and multi-layer system prompt builder.
- **`quantsys-v2/`** — Python quant backend (v2). Flask REST API (port 5001) + WebSocket (port 5003): strategies, factors, ML pipeline, backtesting, risk checks.

## Fixed IP / Port Convention

每个子项目使用固定的 127.0.0.1 地址 + 固定端口。**主分支上的 IP/端口不允许随意修改。** 如果发现主分支上的 IP 被改动，必须修复回以下固定值：

| 子项目 | 固定地址 | 配置方式 |
|--------|----------|----------|
| quantsys-v2 Flask API | `127.0.0.1:5001` | `QUANTSYS_API_HOST` / `QUANTSYS_API_PORT` / `QUANTSYS_API_URL` |
| quantsys-v2 WebSocket | `127.0.0.1:5003` | `QUANTSYS_API_HOST` / `QUANTSYS_WS_PORT` 环境变量 |
| web-frontend Vite | `127.0.0.1:3001` | 代理 `/api` → `127.0.0.1:5001` |
| TypeScript Agent | N/A (CLI) | 通过环境变量连接各服务 |
| PostgreSQL | `127.0.0.1:5432` | 仅用于 quantsys-v2 后端 |
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

# Python quant backend (v2)
cd quantsys-v2 && python start_all.py               # Start REST API (5001) + WebSocket (5003)
cd quantsys-v2 && python api/server.py              # Start REST API only on port 5001
cd quantsys-v2 && python api/server_websocket.py    # Start WebSocket only on port 5003
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

**调度器架构变更（2026-06-03）：**
- TypeScript Agent 使用 `InMemorySchedulerStore`（内存调度器）
- 应用重启后任务需重新注册
- 数据补充任务由 quantsys-v2 Python 后端负责

### Python Quant Backend (`quantsys-v2/`)

#### 多数据源抽象架构（2026-06-02 新增）

**背景**：统一数据访问，消除直接 `import akshare`，支持多数据源自动 failover。

**核心组件**：
- **DataSourceManager** (`data_sources/manager.py`) — 统一数据访问入口
  - 管理多个数据源（AkShare、东方财富、新浪、腾讯等）
  - 按优先级自动 failover
  - 集成熔断器防止持续调用失败源
  - 集成缓存减少重复 API 调用
  - 统计追踪（成功率、延迟、缓存命中率）

- **CircuitBreaker** (`data_sources/circuit_breaker.py`) — 熔断器
  - 三状态：CLOSED（正常）→ OPEN（熔断）→ HALF_OPEN（测试恢复）
  - 失败达到阈值后自动打开
  - 超时后尝试恢复

- **DataSourceCache** (`data_sources/cache.py`) — TTL 缓存
  - 基于方法名和参数自动生成缓存键
  - LRU 淘汰策略
  - 仅缓存成功的响应

**配置文件**：`data_sources/sources_config.yaml`
```yaml
market_data:
  sources:
    - name: akshare
      priority: 1          # 优先级（1 最高）
      enabled: true
      timeout: 10
      max_failures: 3      # 熔断器阈值
      circuit_timeout: 60  # 恢复测试超时
    - name: eastmoney
      priority: 2
      ...
  fallback_strategy: sequential  # 顺序尝试
  cache:
    enabled: true
    ttl: 60              # 缓存 60 秒
    max_size: 1000       # 最大 1000 条
```

**使用方式**：
```python
from data_sources.manager import get_data_source_manager

manager = get_data_source_manager()

# 自动尝试所有数据源，直到成功
result = manager.get_stock_info("600000.SH")
if result.success:
    print(result.data)
```

**已实现功能**：
- ✅ 多数据源管理和自动 failover
- ✅ 熔断器（防止级联失败）
- ✅ TTL 缓存（减少 API 调用）
- ✅ 统计追踪（成功率、缓存命中率）
- ✅ 方法级数据源覆盖
- ✅ 单元测试（9/9 通过）

**待实现功能**（Phase 2-5）：
- ⏳ 新增数据源：EastMoneySource、SinaSource、TencentSource
- ⏳ LLM 浏览器兜底（WebSearch/WebFetch）
- ⏳ Services 层重构（使用 DataSourceManager）
- ⏳ 扩展 BaseMarketAdapter（覆盖更多 API）

**文档位置**：
- 设计方案：`.claude/plans/multi-source-data-abstraction-plan.md`
- Phase 1 报告：`docs/features/multi-source-data-abstraction-phase1-report.md`
- 演示脚本：`data_sources/demo.py`

## Agent 工具系统

本项目实现了完整的 Agent 工具生态系统，包括：
- ✅ 统一的输出格式化系统（13个格式化函数）
- ✅ 统一的数据持久化系统（智能保存大数据，避免污染上下文）
- ✅ 统一的错误处理和性能监控系统
- ✅ 模块化的CLI工具架构（8个领域工具 + 1个核心工具）
- ✅ 因子库系统（104个技术因子，策略执行时自动注入）

### 数据持久化系统（2026-06-03 新增）

针对大数据返回工具（回测、批量查询等），实现了统一的持久化机制，避免污染 LLM 上下文。

**核心特性**：
- 智能持久化：根据数据大小自动决定是否保存到文件（默认阈值 30-100KB）
- 自动清理：过期文件（默认 24 小时）自动删除
- 统一格式化：集成现有 13 个格式化函数
- 零侵入：通过包装器模式，无需重写工具逻辑

**存储位置**：`{sessionDir}/tool-results/`（基于当前 session，文件格式：`{toolName}_YYYYMMDD_HHmmss.json`）  
**示例路径**：`.pi-invest/sessions/20260603T15183_70a27e94/tool-results/`  
**Fallback**：如果没有 session 目录，降级到 `.cache/tool-results/`

**已集成工具**：
- `indicator_backtest` — 指标回测（阈值 30KB）
- `strategy_detail` — 策略详情（阈值 40KB）
- `pool_validate` — 股票池验证（阈值 50KB）
- `strategy_batch_validate` — 策略批量验证（阈值 100KB）
- `factor_calculate` — 因子计算（阈值 40KB）

**效果**：
- 单次回测节省 ~150KB 上下文
- 批量验证节省 ~1MB 上下文
- 上下文占用减少 **99%**

**使用方式**：
```typescript
import { handleToolResponse } from '../utils/index.js';

execute: async (_toolCallId, params) => {
  const result = await apiCall(params);
  return handleToolResponse({
    toolName: 'my_tool',
    data: result,
    formatter: formatMyData,  // 可选：使用现有格式化函数
    threshold: 30 * 1024,      // 可选：自定义阈值
  });
}
```

**详细文档**：
- 使用指南：`docs/tools/unified-response-system.md`
- 集成报告：`docs/tools/tool-persistence-integration-report.md`
- 单元测试：`src/infrastructure/tools/utils/result-persister.test.ts`

### 因子库系统

策略代码可直接使用 104 个预计算因子，无需手动实现技术指标：

**6 大类因子**：
- **动量因子** (15个): rsi6/14/24, macd, roc, momentum_6m, momentum_52w_high, acceleration
- **趋势因子** (20个): adx, cci, aroon_up/down, sar, di_plus/minus, dmi
- **波动率因子** (9个): atr14/20, bollinger_upper/middle/lower, keltner_*, volatility_20
- **成交量因子** (7个): obv, mfi14, vwap, volume_ma5/10, volume_ratio, turnover_rate
- **均线因子** (10个): ma5/10/20/60/120, ema5/10/20
- **反转因子** (3个): reversal_1d/5d, overnight_return

**使用方式**：
```python
# 策略代码中直接使用（无需导入或计算）
df['buy'] = (df['momentum_6m'] > 0.1) & (df['adx'] > 25) & (df['rsi14'] < 70)
df['sell'] = df['rsi14'] > 80
```

**技术特性**：
- 策略执行时自动注入所有因子到 DataFrame
- 使用 TA-Lib C 实现，性能比 pandas 快 10 倍
- 向后兼容：保留原有 13 个常用因子名称

**完整文档**：[docs/FACTOR_LIBRARY_REFERENCE.md](docs/FACTOR_LIBRARY_REFERENCE.md) — 包含每个因子的说明、计算方法、数值范围、使用场景

**工具架构更新** (2026-06-02):
- 原 `quant_cli` 工具已拆分为多个领域CLI工具
- 每个领域工具职责单一，更易维护
- 所有工具集成了统一的错误处理和性能监控
- 文件大小减少31%（1,472行 → 1,025行）

### CLI工具系统

#### 核心CLI工具
- `quant_cli` — 核心和专用命令（46个）
  - indicators.* (8个) - 指标管理
  - portfolio.* (2个) - 组合管理  
  - risk.* (4个) - 风控命令
  - performance.* (3个) - 绩效分析
  - data.* (3个) - 数据管理
  - report.* (2个) - 报告生成
  - 其他专用命令

#### ~~领域CLI工具~~（已于 2026-07-19 移除）

`market_cli` / `stock_cli` / `sentiment_cli` / `analysis_cli` / `watchlist_cli`
从未注册进工具表（死代码），已全部删除。**禁止使用这些工具**，数据访问走：
- 行情/个股 → `data_fetch_quote`、`data_fetch_kline`
- 财务/估值 → `data_fetch_financial`
- 宏观/北向/情绪 → `data_fetch_macro`、`data_fetch_north_flow`、`data_fetch_market_sentiment`
- 技术分析 → `factor_calculate`、`analysis_swing_points`
- 选股/评分 → `opportunity_scan`、`screening`

**使用示例**:
```typescript
// 财务数据（使用增强版 data_fetch_financial）
data_fetch_financial({ symbol: "600000", dataType: "pe_percentile", years: 5 })

// 指标回测（专用工具）
indicator_backtest({ 
  indicator_id: 1, 
  symbol: "600000", 
  start_date: "2025-01-01", 
  end_date: "2025-12-31" 
})
```

**工具特性**:
- ✅ 统一的错误处理和友好提示
- ✅ 自动的性能监控和慢工具告警
- ✅ 完整的调用统计（成功率、耗时）
- ✅ 一致的输出格式

**相关文档**:
- [工具开发指南](docs/tools/tool-development-guide.md)
- [工具拆分报告](docs/reviews/2026-06-02-quant-cli-split-success.md)

### 六层量化投资架构

项目采用六层架构组织 Agent 工具，对应量化投资的完整流程（2025-05-25 重构完成，从 61 个工具精简至 30 个）：

#### L1 数据管道层
统一的数据获取接口，支持股票基本信息、行情数据、财务数据、分红数据：

**⭐ 财务数据统一工具（2026-06-03 增强）**：
- `data_fetch_financial` — **统一财务数据查询入口**
  - **数据类型**：
    - `statements` — 财务报表（利润表、资产负债表、现金流量表）
    - `indicators` — 财务指标（ROE、净利润、营收增长率等）
    - `valuation` — 估值指标（PE、PB、PS、PEG）
    - `pe_percentile` — PE 历史分位数（估值高低判断）
    - `all` — 一次性获取全部数据
  - **智能容错**：部分数据源失败不影响其他数据
  - **向后兼容**：保持原有 `reportType` 参数
  - **使用示例**：
    ```typescript
    // 获取利润表（向后兼容）
    data_fetch_financial({ symbol: "600519", reportType: "income" })
    
    // 获取 PE 分位数
    data_fetch_financial({ symbol: "600519", dataType: "pe_percentile", years: 5 })
    
    // 一站式查询全部财务数据
    data_fetch_financial({ symbol: "600519", dataType: "all" })
    ```

**其他数据工具**：
- `data_fetch_stock` — 获取股票基本信息、**实时价格**、新闻、公告
  - **多数据源支持**：5 个实时行情数据源（新浪财经、东方财富、腾讯财经、网易财经、雪球）
  - **source 参数**：
    - `realtime` (默认) — 仅尝试实时数据源，失败时返回错误
    - `db` — 仅查询数据库历史数据
    - `auto` — 实时优先，失败时自动 fallback 到数据库
  - **时间戳字段**：
    - 实时数据：包含 `timestamp` 字段（ISO 8601 格式）
    - 数据库数据：包含 `tradeDate` 字段（YYYY-MM-DD 格式），source 为 "db_fallback"
  - **延迟**：实时数据 < 3秒，数据库数据为最近交易日收盘价
- `data_fetch_kline` — 获取 K 线数据（日线、周线、月线）
- `data_fetch_financial` — 获取财务数据（利润表、资产负债表、现金流量表）
- `data_fetch_dividend` — 获取分红数据（历史分红、高股息筛选、分红日历）
- `data_fetch_macro` — 获取宏观经济数据（GDP、CPI、PMI、利率、汇率等）
- `data_fetch_north_flow` — 获取北向资金流向（沪股通+深股通）
- `data_fetch_market_sentiment` — 获取市场整体情绪分析（恐慌/贪婪指数、涨跌比）

**重要提示**：L1 层专用工具已替代 `quant_cli` 和 CLI 工具中的以下命令，请优先使用专用工具：
- ~~`stock.info`~~ → 使用 `data_fetch_stock` (fields: ["info"])
- ~~`stock.news`~~ → 使用 `data_fetch_stock` (fields: ["news"])
- ~~`stock.announcements`~~ → 使用 `data_fetch_stock` (fields: ["announcements"])
- ~~`stock.klines`~~ → 使用 `data_fetch_kline`
- ~~`financial.statements`~~ → 使用 `data_fetch_financial`
- ~~`financial.income_statement`~~ → 使用 `data_fetch_financial` (reportType: "income")
- ~~`financial.cash_flow`~~ → 使用 `data_fetch_financial` (reportType: "cashflow")
- ~~`market.macro`~~ → 使用 `data_fetch_macro`
- ~~`market.north_flow`~~ → 使用 `data_fetch_north_flow`
- ~~`market.sentiment`~~ → 使用 `data_fetch_market_sentiment`

#### L2 因子工厂层
批量因子计算和分析：
- `factor_calculate` — 批量计算技术因子和基本面因子
- `factor_analyze` — 分析因子有效性（**IC/IR/覆盖率/单调性**）
  - **✨ 2026-06-04 增强**：新增覆盖率和单调性指标
  - **IC/IR**：信息系数和信息比率，衡量预测能力
  - **覆盖率**：因子数据完整性（> 90% 优秀，< 70% 存疑）
  - **单调性**：因子分层收益是否单调递增/递减（> 80% 优秀，< 50% 失效）
  - 详细文档：`docs/features/factor-coverage-monotonicity-quick-start.md`
- `opportunity_scan` — 扫描投资机会（**支持三种权重模式**）

#### L2.5 智能选股层（2026-06-02 更新）
增强版机会雷达 - 支持固定/自定义/动态权重三种模式：
- `opportunity_scan` — **机会雷达增强版**（推荐使用）
  - **三种权重模式**：
    1. **固定权重模式**（默认）: 技术50% + 基本面30% + 资金20%
    2. **自定义权重模式**: 手动指定三维权重
    3. **动态权重模式**: 基于因子有效性（IC/IR）自动计算最优权重
  
  - **核心功能**：
    - 三维评分：技术面 + 基本面 + 资金面
    - 风险等级评估：low/medium/high
    - 筛选条件：RSI超卖、MACD金叉、PE/ROE门槛等
    - 行业轮动：自动选择强势行业
  
  - **动态权重优势**：
    - ✅ 自适应市场环境（牛市/熊市/震荡市）
    - ✅ 自动降低失效因子权重
    - ✅ 选股准确率提升 +35-40%
  
  - **使用示例**：
    ```typescript
    // 1. 固定权重（默认，快速扫描）
    opportunity_scan({
      symbols: ["600519", "000858"],
      limit: 20
    })
    
    // 2. 自定义权重（手动调整）
    opportunity_scan({
      symbols: ["600519", "000858"],
      weights: {
        technical: 0.7,
        fundamental: 0.2,
        capital: 0.1
      }
    })
    
    // 3. 动态权重（智能选股）
    opportunity_scan({
      symbols: ["600519", "000858"],
      enable_dynamic_weights: true,
      dynamic_weights_config: {
        factors: ["rsi", "macd", "roe", "pe"],
        analysis_period: {
          start_date: "2025-12-01",
          end_date: "2026-06-01"
        }
      }
    })
    ```

- ~~`smart_stock_screener`~~ — **已弃用**（请使用 opportunity_scan 的动态权重模式）
  - ⚠️ 功能已整合到 opportunity_scan
  - 📚 迁移文档：`docs/reviews/2026-06-02-tool-merge-opportunity-scan.md`

#### L2.7 股票池管理层
股票池筛选、管理和策略验证（2026-06-01 新增）：
- `pool_manage` — 股票池 CRUD（创建/列表/查看/更新/删除/刷新/筛选建池）
  - 支持静态池（手动指定stocks）和动态池（保存filter_template，可定时刷新）
  - `scan_create` 操作：执行多因子扫描后自动创建池子
- `pool_validate` — 多策略批量回测验证
  - 对池内所有股票 × 多个策略跑回测，按综合评分排名
  - 自动推荐最优策略 + 最佳股票组合（top 5）
  - 评分公式：收益率40% + 夏普20% + 回撤15% + 胜率15% + 盈亏比10%

**API 端点**：
- `POST /api/pools` — 创建池子
- `GET /api/pools` — 列出所有池子
- `GET /api/pools/:id` — 获取池子详情
- `PUT /api/pools/:id` — 更新池子
- `DELETE /api/pools/:id` — 删除池子
- `POST /api/pools/:id/refresh` — 刷新动态池
- `POST /api/pools/:id/validate` — 执行策略验证
- `POST /api/pools/scan-and-create` — 筛选+建池一步完成

#### L2.8 组合策略回测（2026-06-02 新增）
多策略组合回测，支持三种组合模式：

**工具：** `strategy_combo_backtest`

**三种模式：**
1. **Portfolio 模式**（仓位分配）
   - 多个策略按权重分配资金，独立运行
   - 适用场景：分散风险，平衡激进/保守策略
   - 权重和必须为 1.0
   - 示例：30% 趋势策略 + 70% 均值回归策略

2. **Ensemble 模式**（信号融合）
   - 多个策略信号加权融合为单一信号
   - 适用场景：提高信号质量，降低误判
   - 融合方法：weighted（加权）、majority（多数投票）、and（全部一致）、or（任一触发）
   - 示例：技术面 50% + 基本面 30% + 资金面 20%

3. **Pipeline 模式**（流程编排）
   - 策略按阶段串行执行，前一阶段输出作为后一阶段输入
   - 三个阶段：selection（选股）→ timing（择时）→ risk_control（风控）
   - 示例：多因子选股 → MACD择时 → 动态止损

**API 端点：** `POST /api/backtest/combo`

**后端实现：**
- Service: `quantsys-v2/services/combo_strategy_backtest_service.py`
- Routes: `quantsys-v2/api/routes/backtest.py`
- 复用组件：`SmartBacktestEngine`、`StrategyCombiner`

**性能指标：**
- 2策略 × 10股票：< 5秒
- 3策略 × 50股票：< 30秒
- 5策略 × 100股票：< 120秒

**相关文档：**
- 设计文档：`docs/superpowers/specs/2026-06-01-combo-strategy-backtest-design.md`
- 实现计划：`docs/superpowers/plans/2026-06-01-combo-strategy-backtest.md`

#### L2.9 策略发现（2026-06-04 新增）

自动化策略挖掘和参数优化：

**工具：** `strategy_discovery`

**功能特性**：
- 自动遍历多个策略原型
- 网格搜索最优参数组合
- 多股票池批量测试
- 按Sharpe/收益率/胜率排序
- 推荐最优策略和参数

**三种操作**：
1. **run** - 运行策略发现流水线
2. **archetypes** - 列出所有可用策略原型
3. **result** - 查询历史发现结果

**使用示例**：
```typescript
// 运行策略发现
strategy_discovery({
  action: "run",
  symbols: ["600519.SH", "000858.SZ", "000001.SZ"],
  start_date: "2023-01-01",
  end_date: "2025-12-31",
  metric: "sharpe",           // 优化目标：sharpe/return/win_rate
  max_combinations: 30,       // 每个原型最多测试30个参数组合
  archetype_filter: ["RSI均值回归", "MACD趋势跟踪"]  // 可选：只测试特定原型
})

// 输出：
// - 发现的最优策略列表（Top 10）
// - 每个策略的参数配置
// - 完整绩效指标（Sharpe、收益率、回撤、胜率）
// - 策略评估和建议

// 列出可用策略原型
strategy_discovery({
  action: "archetypes"
})
```

**API 端点**：
- `POST /api/discovery/run` - 运行策略发现
- `GET /api/discovery/archetypes` - 列出策略原型
- `GET /api/discovery/result/:run_id` - 查询历史结果

**应用场景**：
- 策略开发：快速找到有效策略
- 参数优化：自动搜索最优参数
- 策略评估：对比多个策略效果
- 因子挖掘：发现有效的因子组合

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

#### L7 绩效分析层（2026-06-04 新增）
因子模型归因和风险分解：
- `factor_model_attribution` — 因子模型归因分析
  - 支持模型：Fama-French 三因子/五因子、Carhart 四因子、Barra 风险模型
  - Alpha/Beta 分解：识别超额收益来源
  - 因子暴露分析：市场、规模、价值、盈利、投资、动量
  - 风格分析：量化投资风格偏好
  - 应用场景：绩效归因、策略评估、风险预算
  
- `risk_barra_decomposition` — Barra 风险分解
  - 总风险分解：因子风险（系统性）+ 特质风险（个股）
  - 行业因子暴露：识别行业集中度风险
  - 风格因子暴露：规模、价值、成长、动量、波动率等
  - 边际风险贡献（Marginal VaR）：每只股票的风险贡献
  - 应用场景：风险管理、组合优化、压力测试

**使用示例**：
```typescript
// Fama-French 五因子归因
factor_model_attribution({
  model: "fama_french_5",
  portfolio: ["600519.SH", "000858.SZ"],
  weights: [0.6, 0.4],
  start_date: "2025-01-01",
  end_date: "2026-06-04"
})
// 输出：Alpha、市场Beta、规模因子、价值因子、盈利因子、投资因子、R²

// Barra 风险分解
risk_barra_decomposition({
  portfolio: ["600519.SH", "000858.SZ", "000001.SZ"],
  weights: [0.4, 0.3, 0.3]
})
// 输出：总风险、因子风险、特质风险、行业暴露、风格暴露、边际VaR
```

#### 市场分析工具（2026-06-04 新增）

市场风格检测和自适应策略：
- `market_style_detect` — 市场风格检测
  - 自动识别牛市/熊市/震荡市
  - 基于多维度指标：趋势斜率、波动率、动量、成交量
  - 提供投资建议和策略推荐
  - 应用场景：策略自适应、风险控制、择时交易、风格轮动

**使用示例**：
```typescript
// 检测当前市场风格
market_style_detect({
  lookback_days: 60  // 回溯60天分析趋势
})
// 输出：
// - 市场风格：牛市/熊市/震荡市（置信度）
// - 市场指标：趋势斜率、波动率、动量评分
// - 投资建议：针对当前市场风格的操作建议
// - 策略推荐：适合当前市场的策略类型
// - 风格历史：最近的风格变化记录
```

### Agent 元工具

系统级操作工具：
- `backend_control` — 管理 quantsys-v2 后端服务生命周期（启动/停止/重启/状态查询）
  - 支持操作：`start`, `stop`, `restart`, `status`
  - 支持服务：`all` (REST API + WebSocket), `rest` (仅 REST API), `websocket` (仅 WebSocket)
  - REST API 端口：5001，WebSocket 端口：5003
  - 自动健康检查和 PID 管理

- `scheduler_manage` — 调度器管理（2026-06-04 新增）
  - 完整的定时任务管理（任务CRUD、启用/禁用、手动触发）
  - 支持Cron表达式定义执行时间
  - 查询执行历史和失败任务
  - 支持补偿执行
  - 应用场景：数据自动更新、组合再平衡、策略执行、风险监控

**调度器使用示例**：
```typescript
// 创建定时任务
scheduler_manage({
  action: "create",
  name: "daily_portfolio_rebalance",
  cron: "0 9 * * 1-5",  // 工作日每天9点
  command: "portfolio.rebalance",
  params: { strategy_id: 123 },
  enabled: true
})

// 列出所有任务
scheduler_manage({ action: "list" })

// 手动触发任务
scheduler_manage({
  action: "trigger",
  task_id: "1"
})

// 查询执行历史
scheduler_manage({
  action: "runs",
  task_id: "1",
  limit: 20
})
```

### CLI工具系统（2026-06-02 新增）

本项目已将原 `quant_cli` 工具拆分为模块化的CLI工具系统，提供更清晰的职责划分和更好的可维护性。

#### 核心CLI工具
- `quant_cli` — 核心和专用命令（46个）
  - indicators.* (8个) - 指标管理
  - portfolio.* (2个) - 组合管理
  - risk.* (4个) - 风控命令
  - performance.* (3个) - 绩效分析
  - data.* (3个) - 数据管理
  - report.* (2个) - 报告生成
  - 其他专用命令

#### ~~领域CLI工具~~（已于 2026-07-19 移除）
- `market_cli` / `stock_cli` / `sentiment_cli` / `analysis_cli` / `watchlist_cli`
  从未注册进工具表（死代码），已全部删除。**禁止使用**，数据访问走
  `data_fetch_*` / `factor_*` / `opportunity_scan` 路径。

**使用示例**:
```typescript
// 财务数据（使用增强版 data_fetch_financial）
data_fetch_financial({ symbol: "600000", dataType: "pe_percentile", years: 5 })

// 指标回测（专用工具）
indicator_backtest({ 
  indicator_id: 1, 
  symbol: "600000", 
  start_date: "2025-01-01", 
  end_date: "2025-12-31" 
})
```

**工具特性**:
- ✅ 统一的错误处理和友好提示
- ✅ 自动的性能监控和慢工具告警
- ✅ 完整的调用统计（成功率、耗时）
- ✅ 一致的输出格式

**相关文档**:
- [工具开发指南](docs/tools/tool-development-guide.md)
- [quant_cli拆分报告](docs/reviews/2026-06-02-quant-cli-split-success.md)

### Agent 元工具（系统级）

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

### 策略工具统一（2026-06-02 更新）

**重要变更**：策略管理已完全迁移到独立工具，`quant_cli` 不再支持 `strategy.*` 命令。

**独立策略工具**（推荐使用）：
| 工具名 | 功能 | 示例 |
|--------|------|------|
| `strategy_list` | 列出所有策略 | `strategy_list()` |
| `strategy_detail` | 查看策略详情 | `strategy_detail({ strategy_id: "53" })` |
| `strategy_write` | 编写/更新策略代码（创建+更新） | `strategy_write({ name: "my_strategy", code: "..." })` 不传indicator_id即创建新策略 |
| `strategy_execute` | 统一策略执行（single/batch/pipeline） | `strategy_execute({ action: "single", symbol: "600000", strategy: "53" })` |
| `strategy_status` | 查询策略运行状态 | `strategy_status()` |
| `strategy_optimize` | 策略参数优化 | `strategy_optimize({ strategy_id: "53", ... })` |
| `strategy_batch_validate` | 批量验证策略 | `strategy_batch_validate({ strategy_ids: ["53", "54"], ... })` |

**strategy_write 双重功能**（创建+更新）：
- **不传 indicator_id** → 创建新策略
- **传 indicator_id** → 更新已有策略
- 典型工作流：`strategy_write` → `indicator_backtest` → 调整参数 → `strategy_write` → ...

**strategy_execute 三种执行模式**：
1. **single** — 单股票执行，返回详细信号和风险参数
2. **batch** — 批量执行多股票，返回汇总统计
3. **pipeline** — 完整流水线（信号生成 → 风控筛选 → 订单创建）
4. 自动集成市场风格检测

**已移除**（2026-06-02）：
- ❌ `quant_cli` 的 `strategy.list` / `strategy.get` / `strategy.create` / `strategy.run` / `strategy.status` / `strategy.execute` 命令
- ❌ `signal_cli` 工具（后端未实现 signal.arbitrate，其他功能已被更好的 API 替代）

**迁移指南**：
```typescript
// ❌ 旧方式（已不支持）
quant_cli({ command: "strategy.list" })
quant_cli({ command: "strategy.execute", params: { action: "single", symbol: "600000", strategy: "53" } })

// ✅ 新方式（推荐）
strategy_list()
strategy_execute({ action: "single", symbol: "600000", strategy: "53" })
```

**详细文档**：`docs/reviews/2026-06-02-quant-cli-strategy-cleanup.md`

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

**v2 已迁移工具**：
- ~~`data_fetch_stock`, `data_fetch_kline` — 基础数据获取~~ ✅ 已迁移
- `model_list`, `model_predict`, `model_train`, `model_evaluate`, `model_monitor` ✅ 已迁移 (2026-05-29)

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

### 策略循环闭合（2026-05-29）

**P2 完成**：实现"信号 → 执行 → 盈亏 → 统计 → 经验"完整闭环。

#### 核心功能

1. **信号追踪**：订单关联 `signal_id`，全程可追踪
2. **盈亏计算**：卖出成交时自动计算并记录到 `strategy_performance` 表
3. **统一统计**：`GET /api/signal-test/performance` 返回纸面+实盘综合数据
4. **经验积累**：`ExperienceAccumulator` 自动从统计生成经验条目

#### 数据流

```
策略信号 → signal_test_log (pending)
    ↓
创建订单 (signal_id)
    ↓
买入成交 → 更新 entry_price
    ↓
卖出成交 → 计算 pnl_pct → 写入 strategy_performance (source='live')
    ↓
统计 API → 纸面+实盘加权合并
    ↓
经验积累 → 生成推荐等级 (aggressive/moderate/cautious/avoid)
    ↓
Agent 查询经验 → 决策时参考历史表现
```

#### 关键组件

- **strategy_performance 表**：存储实盘交易记录（entry_price, exit_price, pnl_pct, holding_days, source）
- **StrategyPerformanceRepository**：CRUD + 统计查询
- **_update_signal_tracking()**：订单成交时自动更新信号状态和盈亏
- **ExperienceAccumulator**：样本 ≥ 10 时自动生成经验条目

#### 推荐等级规则

| 胜率 | 平均收益 | 推荐等级 |
|------|---------|---------|
| ≥ 70% | ≥ 3% | aggressive |
| ≥ 60% | ≥ 2% | moderate |
| ≥ 50% | ≥ 1% | cautious |
| < 50% | < 1% | avoid |

#### 相关文档

- 完成文档：`docs/superpowers/specs/2026-05-29-strategy-loop-p2-completion.md`
- 端到端测试：`docs/testing/strategy-loop-p2-e2e-test.md`
- 实现计划：`docs/plans/strategy-loop-closure-plan.md`

### 工具后端迁移（2026-05-27）

**重要变更**：`quant_cli` 工具已从 v1 CLI 迁移到 quantsys-v2 HTTP API。

- **旧架构**：spawn python -m quantsys.cli（已弃用）
- **新架构**：HTTP 调用 quantsys-v2 API (port 5001)

**新增命令**（v2 独有）：
- `signal.test_run` - 运行信号测试
- `signal.test_record` - 记录测试结果
- `signal.test_verify` - 验证信号准确性
- `signal.test_stats` - 信号测试统计

**注意**：策略管理命令（`strategy.*`）已从 quant_cli 移除，请使用独立的 strategy 工具。

**要求**：使用 Agent 前必须启动 quantsys-v2 服务：
```bash
cd quantsys-v2 && python start_all.py
```

### quant_cli 工具增强（2026-05-29）

**智能错误提示**：当缺少 `strategy_id` 必填参数时，错误消息会自动附加可用策略列表，减少工具调用次数。

适用命令：
- `performance.by_strategy`
- `backtest.strategy`

示例错误输出：
```
缺少必填参数: strategy_id。原因：该参数是命令执行的必要条件，不能为空。

可用策略列表：
  - ID: 53, 名称: 多因子波段策略v9
  - ID: 54, 名称: RSI超买超卖策略

提示：使用独立工具 strategy_list 可查看完整策略详情。
```

容错处理：如果 quantsys-v2 服务不可用，降级为通用提示。

### Python Quant Backend (`quantsys-v2/`)

Pipeline: resolve → data → factor → model → signal → risk → backtest → report.

- `quantsys-v2/api/server.py` — Flask REST API (port 5001)
- `quantsys-v2/api/server_websocket.py` — WebSocket server (port 5003)
- `quantsys-v2/services/` — Business logic: strategies, factors, ML, risk, backtest
- `quantsys-v2/repositories/` — Data access layer
- `quantsys-v2/daemon/` — JSON-RPC daemon server for legacy compatibility

### Vue 3 Frontend (`web-frontend/`)

Vite dev server on port 3001 proxies `/api` to quantsys-v2 Flask API (port 5001). Component pages: Dashboard, Research, Model Training, Data Management, Operations.

## Environment Setup

Required env vars (see `.env.example`):

```bash
# LLM provider: deepseek (默认) 或 kimi
LLM_PROVIDER=deepseek

# DeepSeek API (OpenAI-compatible)
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=...          # SDK reads this key; must match DEEPSEEK_API_KEY
MODEL_ID=deepseek-chat

# Kimi / Moonshot API (LLM_PROVIDER=kimi 时生效)
# KIMI_API_KEY=sk-...
# KIMI_BASE_URL=https://api.moonshot.cn/v1
# MODEL_ID=kimi-k3          # 可覆盖为具体版本，如 kimi-k3-xxxx-preview
# 通用覆盖: LLM_API_KEY / LLM_BASE_URL / LLM_REASONING / LLM_CONTEXT_WINDOW / LLM_MAX_TOKENS

# quantsys-v2 backend
QUANTSYS_V2_API_URL=http://127.0.0.1:5001
QUANTSYS_V2_TIMEOUT=30000

# Database (PostgreSQL - 仅用于 Python 后端 quantsys-v2)
QUANT_DB_PROVIDER=postgres
PGDATABASE=quant_investment

# 注意：TypeScript Agent 不再直接连接 PostgreSQL
# 数据库连接由 quantsys-v2 后端管理

# Optional
FEISHU_APP_ID=...           # Feishu/Lark bot
TAVILY_API_KEY=...          # Web search
```

**Python Environment:**
- **Required**: Python 3.13 (not 3.14 - numba incompatibility)
- Virtual environment: `.venv-py313/`
- Activation: `source activate-py313.sh`
- Dependencies: `quantsys-v2/requirements.txt` (includes pandas-ta, numba, akshare, etc.)

**Node.js:**
- Node >= 22.0.0 required

## Testing

- **TypeScript**: Jest with `--experimental-vm-modules`. Test files co-located as `*.test.ts`. No jest.config file — config is in `package.json` jest section.
- **Python**: pytest, tests in `quantsys-v2/tests/`. Coverage tracked via pytest-cov.
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

## Agent Autonomy & Scheduled Tasks

### Autonomous Operation Model

The agent operates on **scheduled tasks** and **event triggers**, not just user requests:

**Daily Schedule Example**:
- **02:00** - Refresh dynamic stock pools, validate strategies
- **09:00** - Scan buy signals before market open
- **15:30** - Analyze day's performance, adjust positions
- **Weekly** - Review all pools, optimize parameters

**Event-driven Triggers**:
- Abnormal volatility → Risk assessment
- Pool health deterioration → Auto-refresh
- Signal quality decline → Strategy adjustment

**Implementation**: Uses in-memory scheduler (`InMemorySchedulerStore`) for task scheduling. Critical data refresh tasks are handled by quantsys-v2 backend.

### Game Theory in Stock Pools

Stock pools are **battlefield selection** tools for competitive advantage:

**Strategic Patterns**:
1. **Harvest Retail Panic** — Buy quality during fear-driven selloffs
2. **Avoid Institutional Traps** — Exit when institutions distribute
3. **Snipe Hot-Money Aftermath** — Bottom-fish after pump-and-dump
4. **Sector Rotation** — Switch to winning sectors

**Required Intelligence**:
- Opponent flow tracking (retail/institution/hot-money)
- Risk signal detection (abnormal volume, insider action)
- Opportunity windows (oversold quality stocks)
- Fast battlefield switching

**Tool Enhancement Needed** (see quantsys-v2 roadmap):
- `GET /api/market/opponent-behavior` — Track opponent flows
- `GET /api/pools/{id}/battlefield-assessment` — Competitive advantage score
- `WebSocket /ws/game-alerts` — Real-time opportunity/risk alerts

## Agent Decision Framework

### Decision Context (Not Just Data)

When calling backend APIs, the agent should receive:
- **What**: The data/result
- **Why**: Analysis of anomalies, trends, patterns
- **Suggested Action**: Recommendations with confidence scores
- **Game Context**: Who's winning, who's losing, who's making mistakes

### Audit Trail for Learning

Every significant decision is logged to quantsys-v2:
```typescript
{
  decision_id: 101,
  timestamp: "2026-06-25T02:00:00",
  type: "pool_refresh",
  context: { pool_id: 5, reason: "Scheduled maintenance" },
  parameters: { min_roe: 15 },
  reasoning: "Standard ROE threshold for quality stocks",
  result: { stocks_added: 3, stocks_removed: 2 },
  outcome: "pending"  // Later updated with performance data
}
```

This enables:
- Performance attribution (which decisions led to profit/loss?)
- Strategy improvement (which parameters work best?)
- Failure analysis (why did this trade lose money?)

## Active Conventions

- No linter/formatter configured (no ESLint, Prettier, or Biome).
- No CI/CD pipeline configured.
- git worktrees used for feature isolation (evolution branches, worktree-agent branches).
- Commit messages in Chinese are common.
- The agent uses DeepSeek which processes one tool call at a time — tool definitions should account for this.
- **Agent is autonomous**: Design features around scheduled tasks, not just user prompts.
- **Game-theoretic mindset**: Tools should help identify opponent mistakes, not just "good stocks".
