import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2, V2_COMMAND_LIST } from "../../quant/quant-v2-client.js";
import { formatMaybeLargeToolOutput } from "../shared/large-tool-output.js";

type ParamRule = {
  required?: boolean;
  type?: "string" | "number" | "integer" | "boolean" | "array" | "object";
  enum?: string[];
  min?: number;
  max?: number;
  symbol?: boolean;
  positive?: boolean;
};

type CommandRule = {
  domain: string;
  action: string;
  description: string;
  params: Record<string, ParamRule>;
  example: Record<string, unknown>;
};

const COMMANDS: Record<string, CommandRule> = {
  "tools.list": {
    domain: "tools",
    action: "list",
    description: "列出 QuantSys CLI 支持的全部命令。",
    params: {},
    example: {},
  },
  "tools.describe": {
    domain: "tools",
    action: "describe",
    description: "查看单个 QuantSys CLI 命令的参数定义。",
    params: { name: { required: true, type: "string" } },
    example: { name: "stock.technical" },
  },
  "market.overview": {
    domain: "market",
    action: "overview",
    description: "查询主要 A 股指数概览。",
    params: {},
    example: {},
  },
  "market.sectors": {
    domain: "market",
    action: "sectors",
    description: "查询 A 股行业板块列表。",
    params: {},
    example: {},
  },
  "market.concept_stocks": {
    domain: "market",
    action: "concept-stocks",
    description: "查询概念/主题板块成分股。",
    params: { concept: { required: true, type: "string" } },
    example: { concept: "人工智能" },
  },
  "market.concepts": {
    domain: "market",
    action: "concepts",
    description: "查询全部概念/主题板块列表。",
    params: {},
    example: {},
  },
  "market.macro": {
    domain: "market",
    action: "macro",
    description: "查询 PMI、CPI、GDP 等宏观指标。",
    params: { indicators: { type: "array" } },
    example: { indicators: ["pmi", "cpi"] },
  },
  "market.north_flow": {
    domain: "market",
    action: "north-flow",
    description: "查询北向资金流向。",
    params: {},
    example: {},
  },
  "market.sector_flow": {
    domain: "market",
    action: "sector-flow",
    description: "查询行业资金流向排行。",
    params: {},
    example: {},
  },
  "market.margin": {
    domain: "market",
    action: "margin",
    description: "查询全市场融资融券余额趋势。",
    params: {},
    example: {},
  },
  "market.news": {
    domain: "market",
    action: "news",
    description: "查询市场综合新闻。",
    params: { num: { type: "integer", min: 1 } },
    example: { num: 20 },
  },
  "market.hot_stocks": {
    domain: "market",
    action: "hot-stocks",
    description: "查询热搜股票排行。",
    params: { market: { type: "string", enum: ["全部", "A股", "港股", "美股"] } },
    example: { market: "A股" },
  },
  "market.sentiment": {
    domain: "market",
    action: "sentiment",
    description: "分析市场情绪指标，返回综合恐惧/贪婪评分（0-100）。",
    params: {},
    example: {},
  },
  "market.index_history": {
    domain: "market",
    action: "index-history",
    description: "查询主要指数历史 OHLCV 数据。",
    params: {
      symbol: { required: true, type: "string" },
      start_date: { required: true, type: "string" },
      end_date: { required: true, type: "string" },
    },
    example: { symbol: "sh000001", start_date: "2026-01-01", end_date: "2026-05-20" },
  },
  "stock.batch_quotes": {
    domain: "stock",
    action: "batch-quotes",
    description: "通过量化后端批量查询 A 股或港股实时价格。",
    params: { symbols: { required: true, type: "array" } },
    example: { symbols: ["600519", "000001"] },
  },
  "stock.technical": {
    domain: "stock",
    action: "technical",
    description: "计算单只股票的技术指标，如 RSI、均线和 MACD。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      indicators: { type: "array" },
    },
    example: { symbol: "600519", indicators: ["RSI", "MACD"] },
  },
  "stock.list": {
    domain: "stock",
    action: "list",
    description: "列出本地量化数据库中的股票，或用 source=live 拉取实时股票池。",
    params: {
      market: { type: "string" },
      has_data: { type: "boolean" },
      source: { type: "string", enum: ["local", "live"] },
    },
    example: { market: "A", source: "live" },
  },
  "stock.ml_predict": {
    domain: "stock",
    action: "ml-predict",
    description: "对单只股票运行本地 ML 预测。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "stock.score": {
    domain: "stock",
    action: "score",
    description: "计算单只股票的技术面、基本面、动量、质量、估值综合评分。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "stock.screen": {
    domain: "stock",
    action: "screen",
    description: "按估值、质量、负债率、RSI 和综合分筛选股票并排序。",
    params: {
      limit: { type: "integer", min: 1 },
      pe_max: { type: "number", min: 0 },
      pe_min: { type: "number", min: 0 },
      pb_max: { type: "number", min: 0 },
      pb_min: { type: "number", min: 0 },
      roe_min: { type: "number" },
      debt_ratio_max: { type: "number", min: 0 },
      rsi_max: { type: "number", min: 0 },
      rsi_min: { type: "number", min: 0 },
      min_score: { type: "number", min: 0 },
      sort_by: { type: "string", enum: ["total_score", "technical_score", "fundamental_score", "momentum_score", "quality_score", "valuation_score", "pe", "pb", "roe", "debt_ratio", "rsi"] },
    },
    example: { pe_max: 20, roe_min: 0.15, debt_ratio_max: 0.5, limit: 20 },
  },
  "analysis.technical": {
    domain: "analysis",
    action: "technical",
    description: "计算 MA、MACD、RSI、布林带和技术信号。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "analysis.candlestick": {
    domain: "analysis",
    action: "candlestick",
    description: "识别K线形态、趋势线、斐波那契回调位和跳空缺口。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "analysis.quality": {
    domain: "analysis",
    action: "quality",
    description: "基于 ROE、负债率、毛利率、净利率和趋势给公司质量打分。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "analysis.peers": {
    domain: "analysis",
    action: "peers",
    description: "返回目标股关键指标和行业名称，用于后续同行对比工作流。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "screening.sector": {
    domain: "screening",
    action: "sector",
    description: "按行业板块筛选股票，可选 ROE、PE 和返回数量过滤。",
    params: {
      sector: { required: true, type: "string" },
      min_roe: { type: "number" },
      max_pe: { type: "number", min: 0 },
      limit: { type: "integer", min: 1 },
    },
    example: { sector: "白酒", max_pe: 30, limit: 20 },
  },
  "screening.quality": {
    domain: "screening",
    action: "quality",
    description: "按行业板块筛选股票并计算质量评分，返回满足分数门槛的候选股。",
    params: {
      sector: { required: true, type: "string" },
      min_score: { type: "integer", min: 0 },
      max_pe: { type: "number", min: 0 },
      limit: { type: "integer", min: 1 },
    },
    example: { sector: "白酒", min_score: 65, max_pe: 30, limit: 10 },
  },
  "hk.market_overview": {
    domain: "hk",
    action: "market-overview",
    description: "查询恒生指数、国企指数、恒生科技指数等港股主要指数概览。",
    params: {},
    example: {},
  },
  "hk.south_flow": {
    domain: "hk",
    action: "south-flow",
    description: "查询港股通南向资金最近流入流出情况。",
    params: {},
    example: {},
  },
  "hk.technical": {
    domain: "hk",
    action: "technical",
    description: "计算港股个股 MA、MACD、RSI、布林带和技术信号。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "9988" },
  },
  "hk.hot_rank": {
    domain: "hk",
    action: "hot-rank",
    description: "查询东方财富港股人气排行。",
    params: {},
    example: {},
  },
  "sentiment.stock_fund_flow": {
    domain: "sentiment",
    action: "stock-fund-flow",
    description: "查询个股资金流向，包括主力、大单、中单、小单净流入。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      days: { type: "integer", min: 1 },
    },
    example: { symbol: "600519", days: 5 },
  },
  "sentiment.lhb": {
    domain: "sentiment",
    action: "lhb",
    description: "查询龙虎榜全榜或个股近期龙虎榜记录。",
    params: {
      symbol: { type: "string", symbol: true },
      date: { type: "string" },
    },
    example: { date: "20260519" },
  },
  "sentiment.insider_trades": {
    domain: "sentiment",
    action: "insider-trades",
    description: "查询高管增减持记录。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "sentiment.fund_holdings": {
    domain: "sentiment",
    action: "fund-holdings",
    description: "查询持有指定股票的基金列表。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "sentiment.top_fund_stocks": {
    domain: "sentiment",
    action: "top-fund-stocks",
    description: "查询基金重仓股排行（若上游接口可用）。",
    params: {},
    example: {},
  },
  "sentiment.top_holders": {
    domain: "sentiment",
    action: "top-holders",
    description: "查询前十大股东。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "sentiment.holder_changes": {
    domain: "sentiment",
    action: "holder-changes",
    description: "查询股东人数变化。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "sentiment.margin_data": {
    domain: "sentiment",
    action: "margin-data",
    description: "查询个股融资融券数据。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "financial.indicators": {
    domain: "financial",
    action: "indicators",
    description: "查询最近财务指标：ROE、毛利率、净利率、负债率等。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "financial.valuation": {
    domain: "financial",
    action: "valuation",
    description: "获取股票估值数据：PE、PB、估值状态（cheap/fair/expensive）、合理价值估算。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "financial.pe_percentile": {
    domain: "financial",
    action: "pe-percentile",
    description: "获取PE历史分位数：当前PE在过去N年中所处的百分位（0=历史最低，100=历史最高）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      years: { type: "number", positive: true },
    },
    example: { symbol: "600519", years: 3 },
  },
  "financial.income_statement": {
    domain: "financial",
    action: "income-statement",
    description: "获取利润表：营业收入、营业成本、净利润、毛利率、净利率等。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      recent_n: { type: "number", positive: true },
    },
    example: { symbol: "600519", recent_n: 8 },
  },
  "financial.cash_flow": {
    domain: "financial",
    action: "cash-flow",
    description: "获取现金流量表：经营活动现金流、投资活动现金流、筹资活动现金流。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      recent_n: { type: "number", positive: true },
    },
    example: { symbol: "600519", recent_n: 8 },
  },
  "analysis.price_action": {
    domain: "analysis",
    action: "price-action",
    description: "价格行为分析：趋势、支撑阻力、成交量、突破信号、动量、波动率。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      period: { type: "number", positive: true },
    },
    example: { symbol: "600519", period: 60 },
  },
  "analysis.buy_range": {
    domain: "analysis",
    action: "buy-range",
    description: "买入区间计算：基于技术支撑位计算安全价、理想价、止损位、目标价，并给出分批建仓建议。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      current_price: { type: "number", positive: true },
    },
    example: { symbol: "600519" },
  },
  "analysis.exit_plan": {
    domain: "analysis",
    action: "exit-plan",
    description: "止盈计划：基于买入价和PE计算分批止盈目标（保守/中等/激进），给出卖出建议。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      entry_price: { required: true, type: "number", positive: true },
      position_size: { type: "number", positive: true },
    },
    example: { symbol: "600519", entry_price: 1200, position_size: 100 },
  },
  "financial.hk_financials": {
    domain: "financial",
    action: "hk-financials",
    description: "查询港股财务数据。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "9988" },
  },
  "financial.hk_analysis": {
    domain: "financial",
    action: "hk-analysis",
    description: "查询港股综合分析：价格、技术摘要和财务数据。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "9988" },
  },
  "signal.list": {
    domain: "signal",
    action: "list",
    description: "读取已生成的交易信号，可按日期、方向和置信度过滤。",
    params: {
      date: { type: "string" },
      signal_type: { type: "string", enum: ["BUY", "SELL"] },
      min_confidence: { type: "number", min: 0 },
    },
    example: { signal_type: "BUY", min_confidence: 0.7 },
  },
  "signal.generate": {
    domain: "signal",
    action: "generate",
    description: "使用指定策略对股票列表生成最新交易信号（real strategy execution）。传入 strategy_id 和 symbols，返回每只股票的 buy/sell/hold 信号和置信度。生成的信号会写入数据库（status='pending'），可通过 signal.arbitrate 进行仲裁筛选。",
    params: {
      strategy_id: { required: true, type: "string" },
      symbols: { type: "array" },
    },
    example: { strategy_id: 53, symbols: ["600519", "000425"] },
  },
  "signal.arbitrate": {
    domain: "signal",
    action: "arbitrate",
    description: "对已生成的交易信号进行仲裁：按股票聚合同日 BUY/SELL 信号，处理冲突并给出最终裁决。⚠️ 前置条件：需要先调用 signal.generate 生成信号，或确保数据库中有 pending 状态的信号记录。如果没有待仲裁的信号，将返回空结果。",
    params: {
      date: { type: "string" },
      signals_dir: { type: "string" },
      signals_json: { type: "string" },
      min_confidence_gap: { type: "number", min: 0 },
    },
    example: { date: "2026-05-20" },
  },
  "signal.scan": {
    domain: "signal",
    action: "scan",
    description: "扫描最新信号，查找新的交易机会。v2 端点。",
    params: {
      symbols: { type: "array" },
      strategies: { type: "array" },
    },
    example: {},
  },
  "signal.statistics": {
    domain: "signal",
    action: "statistics",
    description: "查询信号统计数据：各策略/方向的信号数量和置信度分布。v2 端点。",
    params: {},
    example: {},
  },
  "performance.analyze": {
    domain: "performance",
    action: "analyze",
    description: "分析策略信号表现，返回胜率、平均收益、最大回撤和夏普比率。",
    params: {
      strategy_id: { type: "string" },
      days: { type: "integer", min: 1 },
      signals_dir: { type: "string" },
    },
    example: { strategy_id: "rsi-strategy", days: 90 },
  },
  "performance.by_strategy": {
    domain: "performance",
    action: "by-strategy",
    description: "查询单个策略的性能详情：收益、回撤、夏普比率。v2 端点。",
    params: {
      strategy_id: { required: true, type: "string" },
    },
    example: { strategy_id: "rsi-strategy" },
  },
  "performance.comparison": {
    domain: "performance",
    action: "comparison",
    description: "多策略性能对比。v2 端点。",
    params: {},
    example: {},
  },
  "backtest.run": {
    domain: "backtest",
    action: "run",
    description: "运行简单移动平均交叉策略回测（内置策略）。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      strategy_name: { required: true, type: "string" },
      start_date: { required: true, type: "string" },
      end_date: { required: true, type: "string" },
      initial_capital: { required: true, type: "number", min: 10000 },
      commission: { type: "number", min: 0 },
      slippage: { type: "number", min: 0 },
      ma_short: { type: "integer", min: 1 },
      ma_long: { type: "integer", min: 1 },
    },
    example: { symbol: "600519", strategy_name: "ma_cross", start_date: "2025-11-27", end_date: "2026-05-27", initial_capital: 100000, ma_short: 5, ma_long: 20 },
  },
  "backtest.strategy": {
    domain: "backtest",
    action: "strategy",
    description: "运行自定义策略代码回测（通过 strategy_id 指定用户创建的策略）。",
    params: {
      strategy_id: { required: true, type: "string" },
      symbol: { required: true, type: "string", symbol: true },
      start_date: { required: true, type: "string" },
      end_date: { required: true, type: "string" },
      initial_cash: { type: "number", min: 10000 },
    },
    example: { strategy_id: "53", symbol: "600519.SH", start_date: "2025-11-27", end_date: "2026-05-27" },
  },
  "backtest.batch": {
    domain: "backtest",
    action: "batch",
    description: "批量回测：对多个 (策略ID, 股票) 组合依次回测并排名。传入 jobs 数组，每个 job 含 strategy_id/symbol/start_date/end_date。返回按总收益率降序的结果列表和汇总统计。",
    params: {
      jobs: { required: true, type: "array" },
      initial_capital: { type: "number", min: 10000 },
    },
    example: { jobs: [{ strategy_id: 53, symbol: "600519", start_date: "2025-01-01", end_date: "2026-01-01" }], initial_capital: 100000 },
  },
  "backtest.results": {
    domain: "backtest",
    action: "results",
    description: "读取已生成的回测结果。",
    params: {
      symbol: { type: "string", symbol: true },
      date: { type: "string" },
    },
    example: { symbol: "600519" },
  },
  "orders.list": {
    domain: "orders",
    action: "list",
    description: "查询所有订单列表。v2 端点。",
    params: {},
    example: {},
  },
  "trades.list": {
    domain: "trades",
    action: "list",
    description: "查询所有成交记录。v2 端点。",
    params: {},
    example: {},
  },
  "executions.list": {
    domain: "executions",
    action: "list",
    description: "查询信号执行记录列表。v2 端点。",
    params: {},
    example: {},
  },
  "executions.stats": {
    domain: "executions",
    action: "stats",
    description: "查询执行统计：成功率、平均延迟等。v2 端点。",
    params: {},
    example: {},
  },
  "ml.train": {
    domain: "ml",
    action: "train",
    description: "训练或重新训练量化信号模型。",
    params: {
      days: { type: "integer", min: 1 },
      future_days: { type: "integer", min: 1 },
      threshold: { type: "number", min: 0 },
      model: { type: "string" },
      tune: { type: "boolean" },
      trials: { type: "integer", min: 1 },
      cv_splits: { type: "integer", min: 2 },
      db_path: { type: "string" },
      use_feature_engineering: { type: "boolean" },
    },
    example: { days: 730, model: "xgboost" },
  },
  "ml.history": {
    domain: "ml",
    action: "history",
    description: "读取模型训练历史。",
    params: {},
    example: {},
  },
  "data.status": {
    domain: "data",
    action: "status",
    description: "查看本地量化数据库状态。",
    params: { db_path: { type: "string" } },
    example: {},
  },
  "data.full_status": {
    domain: "data",
    action: "full-status",
    description: "查看股票数据和因子覆盖完整性。",
    params: {},
    example: {},
  },
  "data.update_klines": {
    domain: "data",
    action: "update-klines",
    description: "更新日线 K 线数据。支持单个或多个股票（逗号分隔）。",
    params: {
      symbols: { type: "string" },
      days: { type: "integer", min: 1 },
    },
    example: { symbols: "600519,000001", days: 365 },
  },
  "data.update": {
    domain: "data",
    action: "update",
    description: "统一数据更新入口：K线、因子、信号等。v2 端点。",
    params: {
      source: { type: "string" },
      symbols: { type: "string" },
    },
    example: { source: "klines" },
  },
  "jobs.list": {
    domain: "jobs",
    action: "list",
    description: "查询异步任务列表和状态。v2 端点。",
    params: {},
    example: {},
  },
  "scheduler.tasks": {
    domain: "scheduler",
    action: "tasks",
    description: "查询调度器定时任务列表。v2 端点。",
    params: {},
    example: {},
  },
  "factor.list": {
    domain: "factor",
    action: "list",
    description: "列出某只股票的所有可用因子。v2 端点。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
    },
    example: { symbol: "600519" },
  },
  "indicators.list": {
    domain: "indicators",
    action: "list",
    description: "列出系统可用的所有技术指标（自定义 + 系统内置）。可选按 type='my'|'system' 过滤。v2 端点。",
    params: {
      type: { type: "string", enum: ["my", "system"] },
      page: { type: "integer", min: 1 },
      pageSize: { type: "integer", min: 1, max: 100 },
    },
    example: { type: "my" },
  },
  "indicators.detail": {
    domain: "indicators",
    action: "detail",
    description: "获取单个指标的完整详情（代码、参数、描述等）。v2 端点。",
    params: {
      indicator_id: { required: true, type: "integer", min: 1 },
    },
    example: { indicator_id: 49 },
  },
  "indicators.create": {
    domain: "indicators",
    action: "create",
    description: "创建新的自定义指标。需要 name 和 code（Python 策略代码）。v2 端点。",
    params: {
      name: { required: true, type: "string" },
      code: { required: true, type: "string" },
      params: { type: "object" },
      description: { type: "string" },
      category: { type: "string" },
      is_public: { type: "boolean" },
    },
    example: { name: "my_rsi", code: "def run(df): ...", description: "自定义RSI策略" },
  },
  "indicators.update": {
    domain: "indicators",
    action: "update",
    description: "更新已有指标（代码、参数、名称、描述等）。v2 端点。",
    params: {
      indicator_id: { required: true, type: "integer", min: 1 },
      code: { type: "string" },
      params: { type: "object" },
      name: { type: "string" },
      description: { type: "string" },
      is_public: { type: "boolean" },
      category: { type: "string" },
      is_active: { type: "boolean" },
      notebook: { type: "object" },
    },
    example: { indicator_id: 49, name: "多因子波段v10", description: "更新后的策略" },
  },
  "indicators.delete": {
    domain: "indicators",
    action: "delete",
    description: "软删除指定指标。v2 端点。",
    params: {
      indicator_id: { required: true, type: "integer", min: 1 },
    },
    example: { indicator_id: 49 },
  },
  "indicators.run": {
    domain: "indicators",
    action: "run",
    description: "在指定股票上运行自定义指标，返回信号和指标值。v2 端点。",
    params: {
      indicator_id: { required: true, type: "integer", min: 1 },
      symbol: { required: true, type: "string", symbol: true },
      limit: { type: "integer", min: 1 },
    },
    example: { indicator_id: 49, symbol: "600519", limit: 100 },
  },
  "indicators.backtest": {
    domain: "indicators",
    action: "backtest",
    description: "对指定指标进行历史回测，返回权益曲线、交易记录和摘要指标（收益率、夏普比率、最大回撤等）。v2 端点。",
    params: {
      indicator_id: { required: true, type: "integer", min: 1 },
      symbol: { required: true, type: "string", symbol: true },
      start_date: { required: true, type: "string" },
      end_date: { required: true, type: "string" },
      initial_cash: { type: "number", min: 10000 },
    },
    example: { indicator_id: 49, symbol: "600519", start_date: "2025-01-01", end_date: "2026-05-27" },
  },
  "indicators.compare": {
    domain: "indicators",
    action: "compare",
    description: "对比两个指标的回测表现（收益率、信号差异、过滤交易等）。v2 端点。",
    params: {
      indicator_id_a: { required: true, type: "integer", min: 1 },
      indicator_id_b: { required: true, type: "integer", min: 1 },
      symbol: { required: true, type: "string", symbol: true },
      start_date: { required: true, type: "string" },
      end_date: { required: true, type: "string" },
      initial_cash: { type: "number", min: 10000 },
    },
    example: { indicator_id_a: 49, indicator_id_b: 53, symbol: "600519", start_date: "2025-01-01", end_date: "2026-05-27" },
  },
  "indicators.sandbox_columns": {
    domain: "indicators",
    action: "sandbox-columns",
    description: "获取指定股票在沙箱中可用的数据列（技术指标、财务指标）及其覆盖率。用于编写指标代码前了解可用数据。v2 端点。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
    },
    example: { symbol: "600519" },
  },
  "compute.factors": {
    domain: "compute",
    action: "factors",
    description: "触发因子计算任务。v2 端点。",
    params: {
      symbols: { type: "string" },
      force: { type: "boolean" },
    },
    example: { symbols: "600519" },
  },
  "factor.compute": {
    domain: "factor",
    action: "compute",
    description: "计算因子值。",
    params: {},
    example: {},
  },
  "factor.analyze": {
    domain: "factor",
    action: "analyze",
    description: "分析因子分布、覆盖度和 IC 就绪情况。",
    params: {
      top_n: { type: "integer", min: 1 },
      min_observations: { type: "integer", min: 1 },
      sample_limit: { type: "integer", min: 0 },
    },
    example: { top_n: 20, min_observations: 30, sample_limit: 50000 },
  },
  "sector.aggregate": {
    domain: "sector",
    action: "aggregate",
    description: "按行业或板块聚合估值、质量、负债率和信号数量。",
    params: {
      sector_field: { type: "string", enum: ["sector", "industry"] },
      limit: { type: "integer", min: 1 },
    },
    example: { sector_field: "industry", limit: 20 },
  },
  "benchmark.compare": {
    domain: "benchmark",
    action: "compare",
    description: "比较策略收益与基准收益，计算 alpha 和相对表现。",
    params: {
      strategy_return: { type: "number" },
      benchmark_return: { type: "number" },
      strategy_name: { type: "string" },
      benchmark_name: { type: "string" },
      equity: { type: "string" },
      benchmark: { type: "string" },
    },
    example: { strategy_return: 0.12, benchmark_return: 0.08 },
  },
  "strategy.list": {
    domain: "strategy",
    action: "list",
    description: "列出系统所有已注册策略。v2 端点。",
    params: {},
    example: {},
  },
  "strategy.get": {
    domain: "strategy",
    action: "get",
    description: "查询单个策略详情和参数。v2 端点。",
    params: {
      strategy_id: { required: true, type: "string" },
    },
    example: { strategy_id: "rsi-strategy" },
  },
  "strategy.create": {
    domain: "strategy",
    action: "create",
    description: "创建新策略。v2 端点。",
    params: {
      name: { required: true, type: "string" },
      code: { required: true, type: "string" },
    },
    example: { name: "my_strategy", code: "..." },
  },
  "strategy.optimize": {
    domain: "strategy",
    action: "optimize",
    description: "策略参数网格搜索优化（真实回测版）。传入 strategy_id 和 param_grid，对所有参数组合运行回测，按指定指标（sharpe/return/win_rate/calmar）评分，返回最优参数和 top10。",
    params: {
      strategy_id: { required: true, type: "string" },
      symbol: { required: true, type: "string", symbol: true },
      param_grid: { required: true, type: "object" },
      start_date: { type: "string" },
      end_date: { type: "string" },
      metric: { type: "string", enum: ["sharpe", "return", "win_rate", "calmar"] },
      initial_capital: { type: "number", min: 10000 },
      max_combinations: { type: "integer", min: 1, max: 200 },
    },
    example: { strategy_id: 53, symbol: "600519", param_grid: { rsi_low: [25, 30, 35], rsi_high: [65, 70, 75] }, metric: "sharpe" },
  },
  "strategy.run": {
    domain: "strategy",
    action: "run",
    description: "实时运行策略生成信号。",
    params: {
      strategy_id: { required: true, type: "string" },
      symbols: { type: "array" },
    },
    example: { strategy_id: "rsi_strategy", symbols: ["600519.SH"] },
  },
  "strategy.status": {
    domain: "strategy",
    action: "status",
    description: "查询策略运行状态。",
    params: {},
    example: {},
  },
  "watch.price_alert": {
    domain: "watch",
    action: "price-alert",
    description: "校验单只股票价格是否触发上破、下破或涨跌幅预警。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      price: { required: true, type: "number" },
      above: { type: "number" },
      below: { type: "number" },
      change_pct: { type: "number" },
      last_price: { type: "number" },
    },
    example: { symbol: "600519", price: 105, above: 100 },
  },
  "watchlist.list": {
    domain: "watchlist",
    action: "list",
    description: "获取自选股列表，可按分组筛选。",
    params: {
      group_id: { type: "string" },
    },
    example: { group_id: "default" },
  },
  "watchlist.add": {
    domain: "watchlist",
    action: "add",
    description: "添加股票到自选股。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      group_id: { type: "string" },
      note: { type: "string" },
    },
    example: { symbol: "600519", group_id: "e379e813", note: "白酒龙头" },
  },
  "watchlist.remove": {
    domain: "watchlist",
    action: "remove",
    description: "从自选股移除股票。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
    },
    example: { symbol: "600519" },
  },
  "watchlist.check": {
    domain: "watchlist",
    action: "check",
    description: "检查股票是否已加入自选股。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
    },
    example: { symbol: "600519" },
  },
  "watchlist.groups": {
    domain: "watchlist",
    action: "groups",
    description: "获取自选股分组列表。",
    params: {},
    example: {},
  },
  "stress.test": {
    domain: "stress",
    action: "test",
    description: "按市场冲击比例模拟组合压力测试，估算损失、权益和仓位影响。",
    params: {
      positions_json: { required: true, type: "string" },
      shock_pct: { required: true, type: "number" },
      cash: { type: "number" },
    },
    example: { positions_json: "[{\"symbol\":\"600519\",\"market_value\":10000}]", shock_pct: -0.2 },
  },
  "risk.trade_check": {
    domain: "risk",
    action: "trade-check",
    description: "对单笔 A 股买卖订单执行交易前风控检查。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      action: { required: true, type: "string", enum: ["buy", "sell"] },
      price: { required: true, type: "number", min: 0 },
      shares: { required: true, type: "integer", min: 1 },
    },
    example: { symbol: "600519", action: "buy", price: 100, shares: 300 },
  },
  "risk.position_size": {
    domain: "risk",
    action: "position-size",
    description: "按 Kelly 公式和组合风控参数计算建议仓位。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      price: { required: true, type: "number", min: 0 },
      signal_strength: { type: "number", min: 0 },
    },
    example: { symbol: "600519", price: 100, signal_strength: 0.8 },
  },
  "risk.stop_loss": {
    domain: "risk",
    action: "stop-loss",
    description: "基于入场价、当前价和最高价计算固定或移动止损价。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      entry_price: { required: true, type: "number", min: 0 },
      current_price: { type: "number", min: 0 },
      highest_price: { type: "number", min: 0 },
    },
    example: { symbol: "600519", entry_price: 90, current_price: 100, highest_price: 110 },
  },
  "trade.verify": {
    domain: "trade",
    action: "verify",
    description: "对比实盘交易记录和回测交易记录，识别价格、方向和缺失差异。",
    params: {
      trades_json: { required: true, type: "string" },
      backtest_json: { required: true, type: "string" },
    },
    example: { trades_json: "[]", backtest_json: "[]" },
  },
  "factor.decay": {
    domain: "factor",
    action: "decay",
    description: "分析指定因子在多个预测周期上的 IC 衰减和时效性。",
    params: {
      factor: { required: true, type: "string" },
      horizons: { type: "string" },
    },
    example: { factor: "momentum", horizons: "5,10,20" },
  },
  "risk.check": {
    domain: "risk",
    action: "check",
    description: "运行组合风险检查。",
    params: {
      symbols: { type: "string" },
      account_value: { type: "number", min: 1 },
    },
    example: { symbols: "600519,000001" },
  },
  "report.daily": {
    domain: "report",
    action: "daily",
    description: "生成日度量化报告。",
    params: { output_dir: { type: "string" } },
    example: {},
  },
  "report.read_daily": {
    domain: "report",
    action: "read-daily",
    description: "读取最新或指定日期的日度量化报告。",
    params: { date: { type: "string" } },
    example: {},
  },
  "calibrate.run": {
    domain: "calibrate",
    action: "run",
    description: "运行置信度校准：从历史因子数据计算各技术指标的 IC 和最优阈值，生成 JSON 配置文件供信号生成器使用。",
    params: {
      forward_days: { type: "integer", min: 1 },
      return_threshold: { type: "number", min: 0 },
      lookback_days: { type: "integer", min: 30 },
      max_symbols: { type: "integer", min: 50 },
    },
    example: { forward_days: 5, lookback_days: 180 },
  },
  "training.history": {
    domain: "training",
    action: "history",
    description: "查询模型训练历史记录。v2 端点。",
    params: {},
    example: {},
  },
  "training.reports": {
    domain: "training",
    action: "reports",
    description: "查询模型训练报告列表。v2 端点。",
    params: {},
    example: {},
  },
  "timeseries.arima": {
    domain: "timeseries",
    action: "arima",
    description: "ARIMA时间序列建模：拟合、预测、自动选参。用于预测股价趋势、识别季节性模式。",
    params: {
      symbols: { required: true, type: "string" },
      action_type: { type: "string", enum: ["fit", "forecast", "auto_order"] },
      order: { type: "string" },
      forecast_steps: { type: "integer" },
      start_date: { type: "string" },
      end_date: { type: "string" },
    },
    example: { symbols: "600519", action_type: "forecast", order: "1,1,1", forecast_steps: 10 },
  },
  "timeseries.garch": {
    domain: "timeseries",
    action: "garch",
    description: "GARCH波动率建模：拟合、波动率预测、VaR计算。用于评估风险、设定止损。",
    params: {
      symbols: { required: true, type: "string" },
      action_type: { type: "string", enum: ["fit", "forecast", "var"] },
      p: { type: "integer" },
      q: { type: "integer" },
      forecast_steps: { type: "integer" },
      confidence: { type: "number" },
      start_date: { type: "string" },
      end_date: { type: "string" },
    },
    example: { symbols: "600519", action_type: "forecast", p: 1, q: 1, forecast_steps: 5 },
  },
  "timeseries.kalman": {
    domain: "timeseries",
    action: "kalman",
    description: "卡尔曼滤波：状态估计、趋势提取、平滑。用于去噪信号、估计隐藏趋势。",
    params: {
      symbols: { required: true, type: "string" },
      action_type: { type: "string", enum: ["filter", "smooth", "local_level"] },
      start_date: { type: "string" },
      end_date: { type: "string" },
    },
    example: { symbols: "600519", action_type: "local_level" },
  },
  "factor.fama_french_3": {
    domain: "factor",
    action: "fama_french_3",
    description: "Fama-French 3因子模型：市场、规模(SMB)、价值(HML)因子回归分析。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      start_date: { type: "string" },
      end_date: { type: "string" },
      mkt_rf: { type: "array" },
      smb: { type: "array" },
      hml: { type: "array" },
      risk_free_rate: { type: "number" },
    },
    example: { symbol: "600519", start_date: "2024-01-01", end_date: "2024-12-31" },
  },
  "factor.fama_french_5": {
    domain: "factor",
    action: "fama_french_5",
    description: "Fama-French 5因子模型：市场、规模、价值、盈利(RMW)、投资(CMA)因子回归。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      start_date: { type: "string" },
      end_date: { type: "string" },
      mkt_rf: { type: "array" },
      smb: { type: "array" },
      hml: { type: "array" },
      rmw: { type: "array" },
      cma: { type: "array" },
      risk_free_rate: { type: "number" },
    },
    example: { symbol: "600519", start_date: "2024-01-01", end_date: "2024-12-31" },
  },
  "factor.carhart": {
    domain: "factor",
    action: "carhart",
    description: "Carhart 4因子模型：Fama-French 3因子 + 动量(MOM)因子回归分析。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      start_date: { type: "string" },
      end_date: { type: "string" },
      mkt_rf: { type: "array" },
      smb: { type: "array" },
      hml: { type: "array" },
      mom: { type: "array" },
      risk_free_rate: { type: "number" },
    },
    example: { symbol: "600519", start_date: "2024-01-01", end_date: "2024-12-31" },
  },
  "factor.barra": {
    domain: "factor",
    action: "barra",
    description: "Barra风险模型：多因子风险分解、因子暴露分析、风险归因。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      start_date: { type: "string" },
      end_date: { type: "string" },
      factor_exposures: {},
      factor_returns: {},
      risk_free_rate: { type: "number" },
    },
    example: { symbol: "600519", start_date: "2024-01-01", end_date: "2024-12-31" },
  },

  // ── Portfolio Optimization ──
};

const COMMAND_LIST = Object.keys(COMMANDS).sort();
const PUBLIC_COMMAND_LIST = ["help", ...COMMAND_LIST];

// ── 一致性校验：确保 COMMANDS 和 V2_ROUTES 同步 ──
(function checkCommandRouteConsistency() {
  const cmdSet = new Set(COMMAND_LIST);
  const routeSet = new Set(V2_COMMAND_LIST);

  const cmdOnly = COMMAND_LIST.filter((c) => !routeSet.has(c));
  const routeOnly = V2_COMMAND_LIST.filter((c) => !cmdSet.has(c));

  if (cmdOnly.length > 0) {
    console.warn(
      `[quant_cli] COMMANDS 中有 ${cmdOnly.length} 个命令没有 V2_ROUTES 映射，将直接走旧桥接:`,
      cmdOnly,
    );
  }
  if (routeOnly.length > 0) {
    console.warn(
      `[quant_cli] V2_ROUTES 中有 ${routeOnly.length} 个映射没有 COMMANDS 定义:`,
      routeOnly,
    );
  }
})();

// ── V2 降级遥测 ──

type TelemetryEntry = {
  v2Success: number;
  v2Failure: number;   // v2 返回错误 → 降级
  v2Unavailable: number; // v2 不存活 → 直接走旧桥接
  totalFallback: number; // 最终走旧桥接的次数
  lastDowngradeAt?: number;
  lastDowngradeCmd?: string;
  lastDowngradeError?: string;
};

const _telemetry: Record<string, TelemetryEntry> = {};

function _getEntry(cmd: string): TelemetryEntry {
  if (!_telemetry[cmd]) {
    _telemetry[cmd] = { v2Success: 0, v2Failure: 0, v2Unavailable: 0, totalFallback: 0 };
  }
  return _telemetry[cmd];
}

/** Export telemetry snapshot (for debugging / health reporting). */
export function getV2Telemetry(): Record<string, TelemetryEntry> {
  return { ..._telemetry };
}

/** Export aggregate summary. */
export function getV2TelemetrySummary() {
  let totalSuccess = 0;
  let totalFailure = 0;
  let totalUnavailable = 0;
  for (const e of Object.values(_telemetry)) {
    totalSuccess += e.v2Success;
    totalFailure += e.v2Failure;
    totalUnavailable += e.v2Unavailable;
  }
  const total = totalSuccess + totalFailure + totalUnavailable;
  return {
    totalCalls: total,
    v2Success: totalSuccess,
    v2SuccessRate: total > 0 ? (totalSuccess / total * 100).toFixed(1) + '%' : 'N/A',
    v2Failure: totalFailure,
    v2Unavailable: totalUnavailable,
    commandsTracked: Object.keys(_telemetry).length,
    details: _telemetry,
  };
}

export const quantCliTool: ToolDefinition = {
  name: "quant_cli",
  label: "QuantSys CLI",
  description:
    "量化功能统一入口。这个工具只负责校验参数并调用本地 QuantSys CLI，不直接实现量化逻辑。 " +
    "它的使用方式接近 bash CLI：先用 help 获取使用说明书，再按手册执行具体 command。 " +
    "help 等价于 tools.list；help + params.name 等价于 tools.describe，可查看单个命令的参数、示例和用途。 " +
    "适用场景：查询实时行情/批量行情/股票池/基础信息/历史行情/新闻/公告、市场概览/指数历史/行业板块/概念股/宏观/资金流/市场新闻/热搜股票、港股指数/南向资金/技术分析/人气排行、资金流/龙虎榜/高管增减持/基金持仓/股东/融资融券、财务指标/财务报表/港股财务、单只股票买点/技术指标/K线、股票综合评分、多条件选股、因子分析、行业聚合、基准对比、组合优化、策略参数优化、价格预警、压力测试、实盘和回测对比、组合相关性矩阵、因子时效性、生成或读取交易信号、信号裁决、策略表现分析、运行回测、训练模型、查看数据状态和报告。 " +
    "参数格式：command 使用白名单命令名，params 传该命令参数，例如 { command: \"stock.technical\", params: { symbol: \"600519\" } }。 " +
    "常用命令：help、market.overview、market.index_history、market.sectors、market.concept_stocks、market.concepts、market.macro、market.north_flow、market.sector_flow、market.margin、market.news、market.hot_stocks、market.sentiment、stock.batch_quotes、stock.list、analysis.technical、analysis.price_action、analysis.candlestick、analysis.buy_range、analysis.quality、analysis.exit_plan、analysis.peers、indicators.list、indicators.detail、indicators.run、indicators.backtest、indicators.compare、indicators.sandbox_columns、strategy.list、strategy.get、strategy.create、strategy.run、strategy.status、screening.sector、screening.quality、hk.market_overview、hk.south_flow、hk.technical、hk.hot_rank、sentiment.stock_fund_flow、sentiment.lhb、sentiment.insider_trades、sentiment.fund_holdings、sentiment.top_fund_stocks、sentiment.top_holders、sentiment.holder_changes、sentiment.margin_data、financial.indicators、financial.valuation、financial.pe_percentile、financial.income_statement、financial.cash_flow、financial.hk_financials、financial.hk_analysis、stock.score、stock.screen、stock.technical、stock.ml_predict、factor.analyze、factor.decay、sector.aggregate、benchmark.compare、portfolio.optimize、portfolio.correlation、strategy.optimize、watch.price_alert、stress.test、risk.trade_check、risk.position_size、risk.stop_loss、trade.verify、signal.list、signal.generate、signal.arbitrate、performance.analyze、backtest.run、backtest.results、ml.train、ml.history、data.status、data.full_status、data.update_klines、risk.check、report.daily、report.read_daily、tools.list、tools.describe。 " +
    "不要臆造 command 或参数；不确定时先调用 help、tools.list 或 tools.describe。",
  promptSnippet:
    "量化相关能力统一使用 quant_cli。像 bash 一样先用 command=help 查使用说明书，再选择白名单 command 并把参数放进 params；不要调用旧的分散量化工具。",
  promptGuidelines: [
    "不知道量化 CLI 能做什么时，先调用 quant_cli({ command: \"help\" }) 获取命令清单。",
    "不知道某个命令参数时，调用 quant_cli({ command: \"help\", params: { name: \"stock.technical\" } }) 获取单命令说明书。",
    "需要实时行情、批量价格、股票池时，用 stock.batch_quotes、stock.list。对于单股数据（实时价格、基本信息、K线、新闻、公告、财务），优先使用 data_fetch_stock、data_fetch_kline、data_fetch_financial、data_fetch_dividend 等专用工具。",
    "需要市场概览、指数历史、行业板块、概念、宏观、资金流、市场新闻或热搜股票时，用 market.overview、market.index_history、market.sectors、market.concept_stocks、market.concepts、market.macro、market.north_flow、market.sector_flow、market.margin、market.news、market.hot_stocks、market.sentiment。",
    "需要技术分析、走势结构、K线形态、买入区间、质量评分、止盈计划或同行对比时，用 analysis.technical、analysis.price_action、analysis.candlestick、analysis.buy_range、analysis.quality、analysis.exit_plan、analysis.peers。",
    "需要按行业板块筛选股票时，用 screening.sector；需要行业候选股同时按基本面质量评分排序时，用 screening.quality。",
    "需要港股市场概览、南向资金、港股技术面或港股人气排行时，用 hk.market_overview、hk.south_flow、hk.technical、hk.hot_rank。",
    "需要资金流向、龙虎榜、高管增减持、基金持仓、股东变化或融资融券时，用 sentiment.stock_fund_flow、sentiment.lhb、sentiment.insider_trades、sentiment.fund_holdings、sentiment.top_fund_stocks、sentiment.top_holders、sentiment.holder_changes、sentiment.margin_data。",
    "需要财务指标或港股财务分析时，用 financial.indicators、financial.hk_financials、financial.hk_analysis。对于 A 股财务报表，优先使用 data_fetch_financial 专用工具。",
    "需要综合评价单只股票时用 stock.score；需要按 PE/ROE/负债率/RSI/综合分选股时用 stock.screen。",
    "需要看策略历史信号质量时用 performance.analyze；同一股票多信号冲突时用 signal.arbitrate。",
    "需要分析因子有效性用 factor.analyze；需要行业/板块聚合用 sector.aggregate。",
    "需要策略相对指数表现用 benchmark.compare；需要组合权重建议用 portfolio.optimize；需要搜索策略参数用 strategy.optimize。",
    "需要价格预警用 watch.price_alert；需要组合压力测试用 stress.test；需要交易前风控、Kelly仓位或止损价计算时，用 risk.trade_check、risk.position_size、risk.stop_loss；需要实盘和回测差异对比用 trade.verify。",
    "需要组合相关性矩阵用 portfolio.correlation；需要分析因子预测力随持有周期衰减用 factor.decay。",
    "查询单只股票买点或技术面时优先用 stock.technical，并结合 signal.list 或 stock.ml_predict。",
    "需要管理自选股（添加/删除/查看/分组）时，用 watchlist.add、watchlist.remove、watchlist.list、watchlist.check、watchlist.groups。",
    "不确定命令或参数时先用 help / tools.list / tools.describe，不要猜测不存在的 command。",
    "工具会先做本地参数校验，校验失败时按错误提示修正参数后再调用。",
  ],
  parameters: Type.Object({
    command: Type.String({
      description: `白名单命令名。用 help 获取使用说明书。可用值：${PUBLIC_COMMAND_LIST.join(", ")}`,
    }),
    params: Type.Optional(
      Type.Record(Type.String(), Type.Unknown(), {
        description: "命令参数对象。参数名使用下划线形式，如 start_date、signal_type、min_confidence。",
      }),
    ),
  }),
  execute: async (_toolCallId: string, rawParams: any) => {
    let command = typeof rawParams?.command === "string" ? rawParams.command.trim() : "";
    const params = normalizeParams(rawParams?.params);

    if (command === "help") {
      command = typeof params.name === "string" && params.name.trim()
        ? "tools.describe"
        : "tools.list";
    }

    const rule = COMMANDS[command];

    if (!rule) {
      return validationError(
        `不支持的量化命令: ${command || "(空)"}`,
        `可用命令: ${PUBLIC_COMMAND_LIST.join(", ")}。不确定时先用 help。`,
      );
    }

    // ── 股票代码标准化：去掉 .SH / .SZ / .HK / .BJ 后缀 ──
    normalizeSymbolParams(params);

    // ── 参数映射：统一常见参数名称 ──
    applyParameterMapping(params);

    // ── 策略名称自动转换 ──
    if (command === "signal.generate" && params.strategy_names && !params.strategy_id) {
      try {
        const strategyNames = Array.isArray(params.strategy_names)
          ? params.strategy_names
          : [params.strategy_names];

        // 查询策略列表
        const strategiesResponse = await runQuantV2("strategy.list", {});
        const strategies = (strategiesResponse as any)?.strategies || [];

        // 匹配第一个策略名称
        const targetName = strategyNames[0];
        const matched = strategies.find((s: any) =>
          s.name === targetName || s.name.toLowerCase() === targetName.toLowerCase()
        );

        if (!matched) {
          const availableNames = strategies.map((s: any) => s.name).join(", ");
          return validationError(
            `未找到策略: ${targetName}`,
            `可用策略: ${availableNames || "无"}。请使用 strategy.list 查看完整列表。`,
          );
        }

        // 转换为 strategy_id
        params.strategy_id = String(matched.id);
        delete params.strategy_names;
      } catch (error) {
        return validationError(
          `策略名称转换失败: ${error instanceof Error ? error.message : String(error)}`,
          `无法查询策略列表。请直接使用 strategy_id 参数，或确保 quantsys-v2 服务正常运行。`,
        );
      }
    }

    const validation = await validateParams(command, rule, params);
    if (validation) {
      return validationError(validation, formatCommandHelp(command, rule));
    }

    try {
      // ── V2 路由：仅使用 quantsys-v2 HTTP API ──
      const response = await runQuantV2(command, params);
      _getEntry(command).v2Success++;
      return {
        content: [{ type: "text" as const, text: formatSuccess(command, response) }],
        details: response,
      };
    } catch (error) {
      _getEntry(command).v2Failure++;
      const entry = _getEntry(command);
      entry.lastDowngradeAt = Date.now();
      entry.lastDowngradeCmd = command;
      entry.lastDowngradeError = error instanceof Error ? error.message : String(error);
      return {
        content: [
          {
            type: "text" as const,
            text: `量化 CLI 调用失败: ${error instanceof Error ? error.message : String(error)}\n${formatCommandHelp(command, rule)}`,
          },
        ],
        details: {
          command,
          params,
          error: error instanceof Error ? error.message : String(error),
        },
      };
    }
  },
};

function normalizeParams(value: unknown): Record<string, unknown> {
  if (value === undefined || value === null) {
    return {};
  }
  if (typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

/**
 * 标准化股票代码：去掉 .SH / .SZ / .HK / .BJ 等后缀
 * 例如：600519.SH → 600519, 000001.SZ → 000001
 */
function normalizeSymbol(symbol: string): string {
  return symbol.replace(/\.(SH|SZ|HK|BJ)$/i, "");
}

/**
 * 标准化参数中的所有股票代码字段
 */
function normalizeSymbolParams(params: Record<string, unknown>): void {
  // 处理单个 symbol 参数
  if (typeof params.symbol === "string") {
    params.symbol = normalizeSymbol(params.symbol);
  }

  // 处理 symbols 数组参数
  if (Array.isArray(params.symbols)) {
    params.symbols = params.symbols.map((s) =>
      typeof s === "string" ? normalizeSymbol(s) : s
    );
  }

  // 处理 symbols 字符串参数（逗号分隔）
  if (typeof params.symbols === "string") {
    params.symbols = params.symbols
      .split(",")
      .map((s) => normalizeSymbol(s.trim()))
      .join(",");
  }
}

/**
 * 参数映射：将常见的参数名称映射到后端要求的参数名称
 *
 * 映射规则：
 * - quantity/amount → shares（股数）
 * - side/direction → action（买卖方向）
 *
 * 如果目标参数已存在，则不进行映射（保留用户明确指定的参数），但仍然删除源参数以避免验证错误
 */
function applyParameterMapping(params: Record<string, unknown>): void {
  // quantity/amount → shares
  if (params.quantity !== undefined || params.amount !== undefined) {
    if (!params.shares) {
      params.shares = params.quantity ?? params.amount;
    }
    // 无论是否映射，都删除源参数
    delete params.quantity;
    delete params.amount;
  }

  // side/direction → action
  if (params.side !== undefined || params.direction !== undefined) {
    if (!params.action) {
      params.action = params.side ?? params.direction;
    }
    // 无论是否映射，都删除源参数
    delete params.side;
    delete params.direction;
  }
}

/**
 * 获取策略列表提示文本（用于 strategy_id 参数缺失时的错误消息）
 * @returns 格式化的策略列表提示，或降级提示（查询失败时）
 */
export async function fetchStrategyListHint(): Promise<string> {
  try {
    const response = await runQuantV2("strategy.list", {});
    const strategies = (response as any)?.strategies || [];

    if (strategies.length === 0) {
      return "提示：当前系统中没有可用策略。请先使用 strategy.create 创建策略。";
    }

    // 格式化策略列表（最多显示前 10 个）
    const displayStrategies = strategies.slice(0, 10);
    const strategyLines = displayStrategies.map((s: any) =>
      `  - ID: ${s.id}, 名称: ${s.name}`
    ).join('\n');

    const moreHint = strategies.length > 10
      ? `\n\n（共 ${strategies.length} 个策略，仅显示前 10 个）`
      : '';

    return `可用策略列表：\n${strategyLines}${moreHint}\n\n提示：使用 strategy.list 命令可查看完整策略详情。`;

  } catch (error) {
    // 降级：查询失败时返回通用提示
    return "提示：使用 strategy.list 命令查看可用策略列表。";
  }
}

async function validateParams(_command: string, rule: CommandRule, params: Record<string, unknown>): Promise<string | null> {
  const allowed = new Set(Object.keys(rule.params));

  // 参数建议映射：常见错误参数 → 正确参数
  const paramSuggestions: Record<string, string> = {
    'quantity': 'shares',
    'amount': 'shares',
    'side': 'action',
    'direction': 'action',
  };

  for (const key of Object.keys(params)) {
    if (!allowed.has(key)) {
      // 特殊提示：symbol → symbols 的常见错误
      if (key === "symbol" && allowed.has("symbols")) {
        return `不支持的参数: ${key}。提示：该命令使用 symbols（复数）参数，支持单个或多个股票。示例：{ symbols: "688008" } 或 { symbols: "688008,600519" }`;
      }

      // 提供参数建议
      if (paramSuggestions[key]) {
        return `不支持的参数: ${key}。提示：您可能想使用 '${paramSuggestions[key]}' 参数。`;
      }

      return `不支持的参数: ${key}。原因：该命令不接受此参数，请检查参数名称是否正确。`;
    }
  }

  for (const [key, paramRule] of Object.entries(rule.params)) {
    const value = params[key];
    if (paramRule.required && isEmpty(value)) {
      // Special handling for strategy_id: fetch and append strategy list hint
      if (key === "strategy_id") {
        const strategyHint = await fetchStrategyListHint();
        return `缺少必填参数: ${key}。原因：该参数是命令执行的必要条件，不能为空。\n\n${strategyHint}`;
      }
      return `缺少必填参数: ${key}。原因：该参数是命令执行的必要条件，不能为空。`;
    }
    if (isEmpty(value)) {
      continue;
    }

    const typeError = validateType(key, value, paramRule);
    if (typeError) {
      return typeError;
    }

    if (paramRule.symbol && typeof value === "string" && !isValidSymbol(value)) {
      return `${key} 必须是股票代码格式，例如 600519、000001、00700 或 AAPL。原因：系统需要标准格式的股票代码才能查询数据。`;
    }

    if (paramRule.enum && typeof value === "string" && !paramRule.enum.includes(value)) {
      const readable = paramRule.enum.join(" 或 ");
      return `${key} 只能是 ${readable}。原因：该参数只接受预定义的枚举值。`;
    }

    if (paramRule.min !== undefined && typeof value === "number" && value < paramRule.min) {
      const suffix = paramRule.min > 0 ? "正数" : `不小于 ${paramRule.min}`;
      return `${key} 必须是${suffix}。原因：参数值超出有效范围，可能导致计算错误或数据异常。`;
    }
  }

  return null;
}

function validateType(key: string, value: unknown, rule: ParamRule): string | null {
  if (!rule.type) {
    return null;
  }

  if (rule.type === "array") {
    return Array.isArray(value) ? null : `${key} 必须是数组。原因：该参数需要接收多个值，请使用数组格式，例如 ["600519", "000001"]。`;
  }
  if (rule.type === "integer") {
    return typeof value === "number" && Number.isInteger(value) ? null : `${key} 必须是整数。原因：该参数不接受小数或非数字值。`;
  }
  if (rule.type === "number") {
    return typeof value === "number" && Number.isFinite(value) ? null : `${key} 必须是数字。原因：该参数需要数值类型进行计算。`;
  }
  if (rule.type === "boolean") {
    return typeof value === "boolean" ? null : `${key} 必须是布尔值。原因：该参数只接受 true 或 false。`;
  }
  if (rule.type === "string") {
    return typeof value === "string" ? null : `${key} 必须是字符串。原因：该参数需要文本类型的值。`;
  }

  return null;
}

function isEmpty(value: unknown): boolean {
  return value === undefined || value === null || value === "";
}

function isValidSymbol(value: string): boolean {
  return /^[A-Za-z0-9.]{1,12}$/.test(value.trim());
}

function validationError(message: string, hint: string) {
  return {
    content: [
      {
        type: "text" as const,
        text: `${message}\n${hint}`,
      },
    ],
    details: {
      ok: false,
      error: message,
      availableCommands: COMMAND_LIST,
    },
  };
}

function formatCommandHelp(command: string, rule: CommandRule): string {
  const required = Object.entries(rule.params)
    .filter(([, param]) => param.required)
    .map(([name]) => name);
  const allowed = Object.keys(rule.params);
  return [
    `命令说明: ${command} - ${rule.description}`,
    `必填参数: ${required.length ? required.join(", ") : "无"}`,
    `支持参数: ${allowed.length ? allowed.join(", ") : "无"}`,
    `示例 params: ${JSON.stringify(rule.example)}`,
  ].join("\n");
}

function formatSuccess(command: string, response: unknown): string {
  const responseJson = JSON.stringify(response, null, 2);
  const fullText = `量化 CLI 执行完成: ${command}\n${responseJson}`;
  const largeOutput = formatMaybeLargeToolOutput(responseJson, {
    label: `量化 CLI 执行完成: ${command}`,
    filePrefix: `quant-cli-${command}`,
    extension: "json",
    metadata: { command },
  });
  return largeOutput.stored ? largeOutput.text : fullText;
}
