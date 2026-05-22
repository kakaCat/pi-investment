# Agent 工具链接映射表

> 生成时间: 2026-05-22
> 
> 本文档展示 AI Agent 的所有工具及其实现链接

## 目录

1. [工具注册流程](#工具注册流程)
2. [Agent 元工具](#agent-元工具)
3. [投资分析工具](#投资分析工具)
4. [量化工具](#量化工具)
5. [风险管理工具](#风险管理工具)
6. [交易管理工具](#交易管理工具)
7. [数据管理工具](#数据管理工具)
8. [通知与监控工具](#通知与监控工具)
9. [Python 后端连接](#python-后端连接)

---

## 工具注册流程

```
src/core/agent/agent-loop.ts (getSession)
  ↓
src/infrastructure/tools/index.ts (allCustomTools)
  ↓
各功能模块工具定义
  ↓
执行层 (TypeScript 原生 / Python Bridge / QuantSys CLI)
```

### 核心文件

| 文件 | 职责 |
|------|------|
| [src/infrastructure/tools/index.ts](../src/infrastructure/tools/index.ts) | 工具注册中心，导出 `allCustomTools` 数组 |
| [src/core/agent/agent-loop.ts](../src/core/agent/agent-loop.ts) | Agent 主循环，初始化工具并创建 AgentSession |
| [src/infrastructure/tools/core/invest-tools.ts](../src/infrastructure/tools/core/invest-tools.ts) | 投资工具聚合器，整合所有投资相关工具 |

---

## Agent 元工具

这些工具用于 Agent 自身的工作流管理和元认知。

| 工具名 | 标签 | 实现文件 | 说明 |
|--------|------|----------|------|
| `plan` | 制定计划 | [agent/plan-tool.ts](../src/infrastructure/tools/agent/plan-tool.ts) | 生成结构化执行计划 |
| `clarify` | 澄清需求 | [agent/clarify-tool.ts](../src/infrastructure/tools/agent/clarify-tool.ts) | 向用户提问澄清模糊需求 |
| `reflect` | 反思总结 | [agent/reflect-tool.ts](../src/infrastructure/tools/agent/reflect-tool.ts) | 反思决策过程和结果 |
| `task_create` | 创建任务 | [agent/task-tools.ts](../src/infrastructure/tools/agent/task-tools.ts) | 创建结构化任务 |
| `task_update` | 更新任务 | [agent/task-tools.ts](../src/infrastructure/tools/agent/task-tools.ts) | 更新任务状态 |
| `task_execute_async` | 异步执行任务 | [agent/task-tools.ts](../src/infrastructure/tools/agent/task-tools.ts) | 并行执行多个工具调用 |
| `task_list` | 列出任务 | [agent/task-tools.ts](../src/infrastructure/tools/agent/task-tools.ts) | 查看所有任务 |
| `task_get` | 获取任务详情 | [agent/task-tools.ts](../src/infrastructure/tools/agent/task-tools.ts) | 查看单个任务 |
| `task_check_background` | 检查后台任务 | [agent/task-tools.ts](../src/infrastructure/tools/agent/task-tools.ts) | 检查后台任务状态 |
| `memory_write` | 写入记忆 | [agent/memory-tool.ts](../src/infrastructure/tools/agent/memory-tool.ts) | 保存长期记忆 |
| `memory_search` | 搜索记忆 | [agent/memory-tool.ts](../src/infrastructure/tools/agent/memory-tool.ts) | 检索历史记忆 |
| `query_experience` | 查询经验库 | [agent/query-experience-tool.ts](../src/infrastructure/tools/agent/query-experience-tool.ts) | 查询历史投资经验 |
| `compact` | 压缩上下文 | [agent/compact-tool.ts](../src/infrastructure/tools/agent/compact-tool.ts) | 压缩对话历史 |
| `browser` | 浏览器操作 | [agent/browser-tool.ts](../src/infrastructure/tools/agent/browser-tool.ts) | 控制浏览器 |
| `evolution_run` | 进化运行 | [agent/evolution-tool.ts](../src/infrastructure/tools/agent/evolution-tool.ts) | 自我优化 |
| `restart_agent` | 重启 Agent | [agent/restart-agent-tool.ts](../src/infrastructure/tools/agent/restart-agent-tool.ts) | 重启 Agent 进程 |
| `read` | 读取文件 | SDK 内置 | pi-coding-agent SDK 提供 |

---

## 投资分析工具

投资工具按功能域拆分为 7 个子模块，所有工具在 [invest-tools.ts](../src/infrastructure/tools/core/invest-tools.ts) 中聚合。

### 3.1 市场概览工具 (Market Tools)

实现文件: [invest/market-tools.ts](../src/infrastructure/tools/invest/market-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `get_market_overview` | 市场概览 | Python Bridge | 获取 A 股市场整体行情（涨跌家数、成交额、板块表现） |
| `get_sector_list` | 板块列表 | Python Bridge | 获取所有行业板块列表 |
| `get_concept_list` | 概念列表 | Python Bridge | 获取所有概念板块列表 |
| `get_concept_stocks` | 概念成分股 | Python Bridge | 获取指定概念的成分股 |
| `get_hot_stocks` | 热门股票 | Python Bridge | 获取当日热门股票（成交额、涨幅排名） |
| `get_north_flow` | 北向资金 | Python Bridge | 获取北向资金流向数据 |
| `get_sector_fund_flow` | 板块资金流 | Python Bridge | 获取板块资金流向 |
| `get_market_margin` | 市场融资融券 | Python Bridge | 获取市场整体融资融券数据 |
| `get_macro_data` | 宏观数据 | Python Bridge | 获取宏观经济数据（GDP、CPI、PMI 等） |
| `get_market_news` | 市场新闻 | Python Bridge | 获取市场新闻资讯 |

### 3.2 个股查询工具 (Stock Query Tools)

实现文件: [invest/stock-query-tools.ts](../src/infrastructure/tools/invest/stock-query-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `get_stock_info` | 股票信息 | Python Bridge | 获取股票基本信息（名称、行业、市值等） |
| `get_stock_price` | 实时价格 | Python Bridge | 获取股票实时价格和涨跌幅 |
| `get_stock_history` | 历史行情 | Python Bridge | 获取股票历史 K 线数据 |
| `get_stock_news` | 个股新闻 | Python Bridge | 获取个股相关新闻 |
| `get_announcements` | 公司公告 | Python Bridge | 获取上市公司公告 |

### 3.3 技术分析工具 (Analysis Tools)

实现文件: [invest/analysis-tools.ts](../src/infrastructure/tools/invest/analysis-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `analyze_technical` | 技术分析 | Python Bridge | 综合技术指标分析（MACD、KDJ、RSI、布林带） |
| `analyze_candlestick` | K线形态 | Python Bridge | 识别 K 线形态（锤子线、十字星、吞没等） |
| `analyze_price_action` | 价格行为 | Python Bridge | 分析价格行为（支撑位、阻力位、趋势） |
| `get_buy_range` | 买入区间 | Python Bridge | 计算建议买入价格区间（含 Kelly 仓位） |
| `get_exit_plan` | 退出计划 | Python Bridge | 生成退出策略（止损、止盈、减仓计划） |
| `get_valuation` | 估值分析 | Python Bridge | 估值分析（PE、PB、PEG、DCF） |
| `get_pe_percentile` | PE 百分位 | Python Bridge | 计算 PE 历史百分位 |
| `get_quality_score` | 质量评分 | Python Bridge | 综合质量评分（财务、成长、估值） |
| `compare_peers` | 同行对比 | Python Bridge | 同行业公司对比分析 |

### 3.4 财务数据工具 (Financial Tools)

实现文件: [invest/financial-tools.ts](../src/infrastructure/tools/invest/financial-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `get_financial_statements` | 财务报表 | Python Bridge | 获取三大财务报表（资产负债表、利润表、现金流量表） |
| `get_financial_data` | 财务指标 | Python Bridge | 获取关键财务指标（ROE、毛利率、负债率等） |
| `get_hk_financials` | 港股财务 | Python Bridge | 获取港股财务数据 |
| `get_hk_analysis` | 港股分析 | Python Bridge | 港股综合分析 |

### 3.5 选股筛选工具 (Screening Tools)

实现文件: [invest/screening-tools.ts](../src/infrastructure/tools/invest/screening-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `screen_stocks` | 股票筛选 | Python Bridge | 多维度筛选股票（市值、PE、ROE、涨跌幅等） |
| `screen_stocks_quality` | 质量筛选 | Python Bridge | 基于质量评分筛选优质股票 |

### 3.6 市场情绪工具 (Sentiment Tools)

实现文件: [invest/sentiment-tools.ts](../src/infrastructure/tools/invest/sentiment-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `get_stock_fund_flow` | 个股资金流 | Python Bridge | 获取个股资金流向（主力、散户） |
| `get_lhb` | 龙虎榜 | Python Bridge | 获取龙虎榜数据 |
| `get_lhb_web` | 龙虎榜网页 | Web Scraping | 从东方财富网抓取龙虎榜 |
| `get_margin_data` | 融资融券 | Python Bridge | 获取个股融资融券数据 |
| `get_top_holders` | 十大股东 | Python Bridge | 获取十大股东信息 |
| `get_holder_changes` | 股东变动 | Python Bridge | 获取股东持股变动 |
| `get_fund_holdings` | 基金持仓 | Python Bridge | 获取基金持仓数据 |
| `get_top_fund_stocks` | 基金重仓股 | Python Bridge | 获取基金重仓股排名 |
| `get_insider_trades` | 内部交易 | Python Bridge | 获取高管增减持数据 |

### 3.7 持仓管理工具 (Portfolio Tools)

实现文件: [invest/portfolio-tools.ts](../src/infrastructure/tools/invest/portfolio-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `manage_portfolio` | 管理持仓 | TypeScript 原生 | 管理本地持仓（增删改查、盈亏计算） |
| `get_review` | 复盘报告 | TypeScript 原生 | 生成每日复盘报告 |

**数据存储**: `.pi-invest/portfolio.json`, `.pi-invest/trades.json`

### 3.8 港股专用工具 (HK Tools)

实现文件: [invest/hk-tools.ts](../src/infrastructure/tools/invest/hk-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `get_hk_market_overview` | 港股概览 | Python Bridge | 获取港股市场概览 |
| `get_hk_hot_rank` | 港股热度 | Python Bridge | 获取港股热度排名 |
| `get_hk_south_flow` | 南向资金 | Python Bridge | 获取南向资金流向 |
| `get_hk_technical` | 港股技术分析 | Python Bridge | 港股技术指标分析 |

---

## 量化工具

### 4.1 QuantSys CLI 工具

实现文件: [core/quant-cli-tool.ts](../src/infrastructure/tools/core/quant-cli-tool.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `quant_cli` | 量化 CLI | QuantSys CLI | 统一量化工具入口，调用 Python QuantSys CLI |

**QuantSys CLI 客户端**: [quant-cli-client.ts](../src/infrastructure/quant/quant-cli-client.ts)

**支持的 domain**:
- `risk`: 风险管理查询
- `market`: 市场数据查询
- `financial`: 财务数据查询
- `analysis`: 分析查询
- 更多见 `quant/quantsys/cli/` 目录

### 4.2 量化分析工具

| 工具名 | 标签 | 实现文件 | 说明 |
|--------|------|----------|------|
| `analyze_sector_rotation` | 行业轮动 | [analysis/analyze-sector-rotation-tool.ts](../src/infrastructure/tools/analysis/analyze-sector-rotation-tool.ts) | 分析行业轮动趋势 |
| `check_stop_loss_trigger` | 止损检查 | [analysis/check-stop-loss-trigger-tool.ts](../src/infrastructure/tools/analysis/check-stop-loss-trigger-tool.ts) | 检查持仓是否触发止损 |
| `test_market_sentiment` | 市场情绪测试 | [analysis/test-market-sentiment-tool.ts](../src/infrastructure/tools/analysis/test-market-sentiment-tool.ts) | 市场情绪分析 |

---

## 风险管理工具

实现文件: [invest/risk-tools.ts](../src/infrastructure/tools/invest/risk-tools.ts)

所有风险工具通过 **QuantSys CLI** 调用 Python 后端。

| 工具名 | 标签 | CLI Action | Python 模块 | 说明 |
|--------|------|------------|-------------|------|
| `check_trade_risk` | 交易风控检查 | `risk +trade-check` | [risk_query.py](../quant/quantsys/cli/risk_query.py) | 7 项风控规则检查（黑名单、ST、仓位限制、板块集中度、最大回撤、日交易限制、流动性） |
| `calculate_position_size` | Kelly 仓位计算 | `risk +position-size` | [risk_query.py](../quant/quantsys/cli/risk_query.py) | 基于 Kelly 准则计算最优仓位 |
| `calculate_stop_loss` | 动态止损计算 | `risk +stop-loss` | [risk_query.py](../quant/quantsys/cli/risk_query.py) | 混合止损策略（固定止损 -8% / 追踪止损 -10%） |

**适配器**: [risk-query-cli-adapter.ts](../src/infrastructure/quant/risk-query-cli-adapter.ts)

**风控规则配置**: `.pi-invest/risk-rules.json`

---

## 交易管理工具

### 6.1 挂单管理

实现文件: [trading/order-tools.ts](../src/infrastructure/tools/trading/order-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `manage_orders` | 挂单管理 | TypeScript 原生 | 创建/撤销/查看/成交挂单 |
| `check_pending_orders` | 检查挂单 | TypeScript 原生 | 自动检查挂单是否触发成交 |

**数据存储**: `.pi-invest/orders.json`

### 6.2 交易日志

实现文件: [trading/trade-log-tools.ts](../src/infrastructure/tools/trading/trade-log-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `trade_log` | 交易日志 | TypeScript 原生 | 创建/更新/追加交易记录 |

**数据存储**: `.pi-invest/trades.json`

### 6.3 关注列表

实现文件: [trading/watchlist-tools.ts](../src/infrastructure/tools/trading/watchlist-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `manage_watchlist` | 关注列表 | TypeScript 原生 | 管理自选股池（增删改查） |

**数据存储**: `.pi-invest/watchlist.json`

---

## 数据管理工具

实现文件: [data/stock-db-tools.ts](../src/infrastructure/tools/data/stock-db-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `stock_db_*` | 股票数据库 | TypeScript 原生 | 本地股票数据库管理（待实现） |

---

## 通知与监控工具

### 8.1 通知工具

实现文件: [tools/notification-tools.ts](../src/tools/notification-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `send_notification` | 发送通知 | 飞书 API | 发送飞书通知 |

**飞书 API 客户端**: [api/feishu.ts](../src/api/feishu.ts)

### 8.2 监控工具

实现文件: [tools/monitor-tools.ts](../src/tools/monitor-tools.ts)

| 工具名 | 标签 | 后端 | 说明 |
|--------|------|------|------|
| `monitor_*` | 监控 | TypeScript 原生 | 实时盯盘监控（待实现） |

---

## Python 后端连接

### 9.1 调用层次

```
TypeScript 工具层
  ↓
Python Bridge / QuantSys CLI
  ↓
Python 执行层
```

### 9.2 Python Bridge

**主入口**: [shared/python-caller.ts](../src/infrastructure/tools/shared/python-caller.ts)

```typescript
export async function callPython(func: string, args: Record<string, unknown>): Promise<string>
```

**弹性适配器**: [shared/python-caller-resilient-adapter.ts](../src/infrastructure/tools/shared/python-caller-resilient-adapter.ts)

特性:
- 分级超时（10s/30s/60s）
- 缓存系统（intraday/daily/quarterly/static）
- TypeScript 原生优先降级

### 9.3 QuantSys CLI

**客户端**: [quant/quant-cli-client.ts](../src/infrastructure/quant/quant-cli-client.ts)

```typescript
export async function runQuantCli(
  domain: string,
  action: string,
  params: Record<string, unknown>
): Promise<QuantCliResponse>
```

**Python CLI 入口**: `quant/quantsys/cli/__main__.py`

**CLI 模块**:
- [risk_query.py](../quant/quantsys/cli/risk_query.py) - 风险管理查询
- [market_query.py](../quant/quantsys/cli/market_query.py) - 市场数据查询
- [financial_query.py](../quant/quantsys/cli/financial_query.py) - 财务数据查询
- [analysis_query.py](../quant/quantsys/cli/analysis_query.py) - 分析查询
- [strategy_analytics.py](../quant/quantsys/cli/strategy_analytics.py) - 策略分析
- [portfolio_analytics.py](../quant/quantsys/cli/portfolio_analytics.py) - 组合分析
- [factor_decay.py](../quant/quantsys/cli/factor_decay.py) - 因子衰减分析
- [strategy_optimizer.py](../quant/quantsys/cli/strategy_optimizer.py) - 策略优化
- [factor_sector_analytics.py](../quant/quantsys/cli/factor_sector_analytics.py) - 因子板块分析
- [risk_watch_analytics.py](../quant/quantsys/cli/risk_watch_analytics.py) - 风险监控分析

### 9.4 Python 后端模块

**AkShare 桥接**: `quant/quantsys/risk/bridge.py`

**风险管理**: `quant/quantsys/risk/`
- `risk_checker.py` - 风控检查器
- `position_sizer.py` - 仓位计算器
- `stop_loss_calculator.py` - 止损计算器

---

## 工具调用统计

| 类别 | 工具数量 |
|------|---------|
| Agent 元工具 | 16 |
| 市场概览工具 | 10 |
| 个股查询工具 | 5 |
| 技术分析工具 | 9 |
| 财务数据工具 | 4 |
| 选股筛选工具 | 2 |
| 市场情绪工具 | 9 |
| 持仓管理工具 | 2 |
| 港股专用工具 | 4 |
| 量化分析工具 | 4 |
| 风险管理工具 | 3 |
| 交易管理工具 | 4 |
| 数据管理工具 | 1 |
| 通知与监控工具 | 2 |
| **总计** | **75+** |

---

## 附录：工具执行后端分类

### TypeScript 原生实现
- 持仓管理 (`manage_portfolio`)
- 复盘报告 (`get_review`)
- 交易管理 (挂单、日志、关注列表)
- Agent 元工具 (plan, clarify, reflect, task_*, memory_*)

### Python Bridge (AkShare)
- 市场数据工具 (市场概览、板块、宏观)
- 个股查询工具 (信息、价格、历史)
- 技术分析工具 (指标、形态、估值)
- 财务数据工具 (报表、指标)
- 选股筛选工具
- 市场情绪工具 (资金流、龙虎榜、持股)
- 港股工具

### QuantSys CLI (Python)
- 风险管理工具 (风控检查、仓位计算、止损计算)
- 量化分析工具 (行业轮动、止损检查、市场情绪)
- 策略分析工具
- 组合分析工具

### Web Scraping
- 龙虎榜网页抓取 (`get_lhb_web`)

### 外部 API
- 飞书通知 (`send_notification`)

---

**文档生成时间**: 2026-05-22  
**项目**: pi-investment  
**Agent 框架**: pi-coding-agent SDK + DeepSeek Model
