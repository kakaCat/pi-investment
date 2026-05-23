import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantCli } from "../../quant/quant-cli-client.js";

type ParamRule = {
  required?: boolean;
  type?: "string" | "number" | "integer" | "boolean" | "array";
  enum?: string[];
  min?: number;
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
  "stock.klines": {
    domain: "stock",
    action: "klines",
    description: "查询本地量化库中的股票 K 线数据。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      start_date: { type: "string" },
      end_date: { type: "string" },
      limit: { type: "integer", min: 1 },
    },
    example: { symbol: "600519", limit: 100 },
  },
  "stock.quote": {
    domain: "stock",
    action: "quote",
    description: "通过量化后端查询 A 股或港股实时行情。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "stock.batch_quotes": {
    domain: "stock",
    action: "batch-quotes",
    description: "通过量化后端批量查询 A 股或港股实时价格。",
    params: { symbols: { required: true, type: "array" } },
    example: { symbols: ["600519", "000001"] },
  },
  "stock.info": {
    domain: "stock",
    action: "info",
    description: "通过量化后端查询 A 股或港股基础信息。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "stock.history": {
    domain: "stock",
    action: "history",
    description: "通过量化后端查询 A 股或港股历史行情。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      period: { type: "string", enum: ["daily", "weekly", "monthly"] },
      start_date: { type: "string" },
      end_date: { type: "string" },
      limit: { type: "integer", min: 1 },
    },
    example: { symbol: "600519", period: "daily", limit: 60 },
  },
  "stock.news": {
    domain: "stock",
    action: "news",
    description: "通过量化后端查询个股新闻。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      num: { type: "integer", min: 1 },
    },
    example: { symbol: "600519", num: 10 },
  },
  "stock.announcements": {
    domain: "stock",
    action: "announcements",
    description: "通过量化后端查询个股公告。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
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
  "analysis.valuation": {
    domain: "analysis",
    action: "valuation",
    description: "基于 PE、PB 和格雷厄姆估值公式分析绝对估值。",
    params: { symbol: { required: true, type: "string", symbol: true } },
    example: { symbol: "600519" },
  },
  "analysis.pe_percentile": {
    domain: "analysis",
    action: "pe-percentile",
    description: "估算当前 PE 在自身历史中的分位数。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      years: { type: "integer", min: 1 },
    },
    example: { symbol: "600519", years: 3 },
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
  "financial.statements": {
    domain: "financial",
    action: "statements",
    description: "查询利润表、资产负债表、现金流量表或三表合集。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      statement: { type: "string", enum: ["income", "balance", "cashflow", "all"] },
      recent_n: { type: "integer", min: 1 },
    },
    example: { symbol: "600519", statement: "income", recent_n: 4 },
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
  "indicator.technical": {
    domain: "indicator",
    action: "technical",
    description: "计算技术指标：MA（移动平均线）、MACD、RSI、布林带，并生成交易信号。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      indicators: { type: "string" },
    },
    example: { symbol: "600519" },
  },
  "indicator.candlestick": {
    domain: "indicator",
    action: "candlestick",
    description: "K线形态识别：识别看涨/看跌形态、跳空缺口、趋势线突破等。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
      lookback: { type: "number", positive: true },
    },
    example: { symbol: "600519", lookback: 120 },
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
  "analysis.peer_comparison": {
    domain: "analysis",
    action: "peer-comparison",
    description: "同行对比：获取目标股票基础数据（PE、PB、ROE、市值）和行业信息，提示如何获取同行数据。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
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
    description: "基于最新因子数据生成交易信号。",
    params: {},
    example: {},
  },
  "signal.arbitrate": {
    domain: "signal",
    action: "arbitrate",
    description: "按股票聚合同日 BUY/SELL 信号，处理冲突并给出最终裁决。",
    params: {
      date: { type: "string" },
      signals_dir: { type: "string" },
      signals_json: { type: "string" },
      min_confidence_gap: { type: "number", min: 0 },
    },
    example: { date: "2026-05-20" },
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
  "backtest.run": {
    domain: "backtest",
    action: "run",
    description: "运行策略回测。",
    params: {
      symbol: { type: "string", symbol: true },
      symbols: { type: "string" },
      days: { type: "integer", min: 1 },
      start: { type: "string" },
      end: { type: "string" },
      capital: { type: "number", min: 1 },
      commission: { type: "number", min: 0 },
      slippage: { type: "number", min: 0 },
    },
    example: { symbol: "600519", days: 365 },
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
    description: "更新日线 K 线数据。",
    params: {
      symbols: { type: "string" },
      days: { type: "integer", min: 1 },
    },
    example: { symbols: "600519,000001", days: 365 },
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
  "portfolio.optimize": {
    domain: "portfolio",
    action: "optimize",
    description: "用等权、风险平价或简化最大夏普方法优化组合权重。",
    params: {
      symbols: { required: true, type: "string" },
      method: { type: "string", enum: ["equal_weight", "risk_parity", "max_sharpe"] },
      expected_returns: { type: "string" },
      volatilities: { type: "string" },
    },
    example: { symbols: "600519,000001", method: "risk_parity" },
  },
  "strategy.optimize": {
    domain: "strategy",
    action: "optimize",
    description: "搜索 RSI、均线交叉、布林带策略参数。",
    params: {
      strategy: { required: true, type: "string", enum: ["rsi", "ma_cross", "bollinger"] },
      metric: { type: "string", enum: ["sharpe", "return", "win_rate"] },
      trials: { type: "integer", min: 1 },
      param_grid_json: { type: "string" },
    },
    example: { strategy: "rsi", metric: "sharpe", trials: 9 },
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
  "portfolio.correlation": {
    domain: "portfolio",
    action: "correlation",
    description: "基于价格序列计算组合相关性矩阵，并标出高相关股票对。",
    params: {
      prices_json: { required: true, type: "string" },
      threshold: { type: "number", min: 0 },
    },
    example: { prices_json: "{\"600519\":[1,2,3],\"000001\":[1,2,4]}", threshold: 0.7 },
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
};

const COMMAND_LIST = Object.keys(COMMANDS).sort();
const PUBLIC_COMMAND_LIST = ["help", ...COMMAND_LIST];

export const quantCliTool: ToolDefinition = {
  name: "quant_cli",
  label: "QuantSys CLI",
  description:
    "量化功能统一入口。这个工具只负责校验参数并调用本地 QuantSys CLI，不直接实现量化逻辑。 " +
    "它的使用方式接近 bash CLI：先用 help 获取使用说明书，再按手册执行具体 command。 " +
    "help 等价于 tools.list；help + params.name 等价于 tools.describe，可查看单个命令的参数、示例和用途。 " +
    "适用场景：查询实时行情/批量行情/股票池/基础信息/历史行情/新闻/公告、市场概览/指数历史/行业板块/概念股/宏观/资金流/市场新闻/热搜股票、港股指数/南向资金/技术分析/人气排行、资金流/龙虎榜/高管增减持/基金持仓/股东/融资融券、财务指标/财务报表/港股财务、单只股票买点/技术指标/K线、股票综合评分、多条件选股、因子分析、行业聚合、基准对比、组合优化、策略参数优化、价格预警、压力测试、实盘和回测对比、组合相关性矩阵、因子时效性、生成或读取交易信号、信号裁决、策略表现分析、运行回测、训练模型、查看数据状态和报告。 " +
    "参数格式：command 使用白名单命令名，params 传该命令参数，例如 { command: \"stock.technical\", params: { symbol: \"600519\" } }。 " +
    "常用命令：help、market.overview、market.index_history、market.sectors、market.concept_stocks、market.concepts、market.macro、market.north_flow、market.sector_flow、market.margin、market.news、market.hot_stocks、market.sentiment、stock.quote、stock.batch_quotes、stock.list、stock.info、stock.history、stock.news、stock.announcements、analysis.technical、analysis.price_action、analysis.candlestick、analysis.buy_range、analysis.valuation、analysis.pe_percentile、analysis.quality、analysis.exit_plan、analysis.peers、screening.sector、screening.quality、hk.market_overview、hk.south_flow、hk.technical、hk.hot_rank、sentiment.stock_fund_flow、sentiment.lhb、sentiment.insider_trades、sentiment.fund_holdings、sentiment.top_fund_stocks、sentiment.top_holders、sentiment.holder_changes、sentiment.margin_data、financial.indicators、financial.statements、financial.valuation、financial.pe_percentile、financial.income_statement、financial.cash_flow、financial.hk_financials、financial.hk_analysis、indicator.technical、indicator.candlestick、stock.score、stock.screen、stock.technical、stock.klines、stock.ml_predict、factor.analyze、factor.decay、sector.aggregate、benchmark.compare、portfolio.optimize、portfolio.correlation、strategy.optimize、watch.price_alert、stress.test、risk.trade_check、risk.position_size、risk.stop_loss、trade.verify、signal.list、signal.generate、signal.arbitrate、performance.analyze、backtest.run、backtest.results、ml.train、ml.history、data.status、data.full_status、data.update_klines、risk.check、report.daily、report.read_daily、tools.list、tools.describe。 " +
    "不要臆造 command 或参数；不确定时先调用 help、tools.list 或 tools.describe。",
  promptSnippet:
    "量化相关能力统一使用 quant_cli。像 bash 一样先用 command=help 查使用说明书，再选择白名单 command 并把参数放进 params；不要调用旧的分散量化工具。",
  promptGuidelines: [
    "不知道量化 CLI 能做什么时，先调用 quant_cli({ command: \"help\" }) 获取命令清单。",
    "不知道某个命令参数时，调用 quant_cli({ command: \"help\", params: { name: \"stock.technical\" } }) 获取单命令说明书。",
    "需要实时行情、批量价格、股票池、股票基础信息、历史行情、新闻或公告时，优先用 stock.quote、stock.batch_quotes、stock.list、stock.info、stock.history、stock.news、stock.announcements。",
    "需要市场概览、指数历史、行业板块、概念、宏观、资金流、市场新闻或热搜股票时，用 market.overview、market.index_history、market.sectors、market.concept_stocks、market.concepts、market.macro、market.north_flow、market.sector_flow、market.margin、market.news、market.hot_stocks、market.sentiment。",
    "需要技术分析、走势结构、K线形态、买入区间、估值、PE分位数、质量评分、止盈计划或同行对比时，用 analysis.technical、analysis.price_action、analysis.candlestick、analysis.buy_range、analysis.valuation、analysis.pe_percentile、analysis.quality、analysis.exit_plan、analysis.peers。",
    "需要按行业板块筛选股票时，用 screening.sector；需要行业候选股同时按基本面质量评分排序时，用 screening.quality。",
    "需要港股市场概览、南向资金、港股技术面或港股人气排行时，用 hk.market_overview、hk.south_flow、hk.technical、hk.hot_rank。",
    "需要资金流向、龙虎榜、高管增减持、基金持仓、股东变化或融资融券时，用 sentiment.stock_fund_flow、sentiment.lhb、sentiment.insider_trades、sentiment.fund_holdings、sentiment.top_fund_stocks、sentiment.top_holders、sentiment.holder_changes、sentiment.margin_data。",
    "需要财务指标、财务报表或港股财务分析时，用 financial.indicators、financial.statements、financial.hk_financials、financial.hk_analysis。",
    "需要综合评价单只股票时用 stock.score；需要按 PE/ROE/负债率/RSI/综合分选股时用 stock.screen。",
    "需要看策略历史信号质量时用 performance.analyze；同一股票多信号冲突时用 signal.arbitrate。",
    "需要分析因子有效性用 factor.analyze；需要行业/板块聚合用 sector.aggregate。",
    "需要策略相对指数表现用 benchmark.compare；需要组合权重建议用 portfolio.optimize；需要搜索策略参数用 strategy.optimize。",
    "需要价格预警用 watch.price_alert；需要组合压力测试用 stress.test；需要交易前风控、Kelly仓位或止损价计算时，用 risk.trade_check、risk.position_size、risk.stop_loss；需要实盘和回测差异对比用 trade.verify。",
    "需要组合相关性矩阵用 portfolio.correlation；需要分析因子预测力随持有周期衰减用 factor.decay。",
    "查询单只股票买点或技术面时优先用 stock.technical，并结合 signal.list 或 stock.ml_predict。",
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

    const validation = validateParams(command, rule, params);
    if (validation) {
      return validationError(validation, formatCommandHelp(command, rule));
    }

    try {
      // Special handling: calibrate.run calls Python bridge directly
      if (command === 'calibrate.run') {
        const response = await runCalibrationBridge(params);
        return {
          content: [{ type: "text" as const, text: formatSuccess(command, response) }],
          details: response,
        };
      }

      const response = await runQuantCli(rule.domain, rule.action, params);
      return {
        content: [
          {
            type: "text" as const,
            text: formatSuccess(command, response),
          },
        ],
        details: response,
      };
    } catch (error) {
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

function validateParams(command: string, rule: CommandRule, params: Record<string, unknown>): string | null {
  const allowed = new Set(Object.keys(rule.params));

  for (const key of Object.keys(params)) {
    if (!allowed.has(key)) {
      return `不支持的参数: ${key}`;
    }
  }

  for (const [key, paramRule] of Object.entries(rule.params)) {
    const value = params[key];
    if (paramRule.required && isEmpty(value)) {
      return `缺少必填参数: ${key}`;
    }
    if (isEmpty(value)) {
      continue;
    }

    const typeError = validateType(key, value, paramRule);
    if (typeError) {
      return typeError;
    }

    if (paramRule.symbol && typeof value === "string" && !isValidSymbol(value)) {
      return `${key} 必须是股票代码格式，例如 600519、000001、00700 或 AAPL`;
    }

    if (paramRule.enum && typeof value === "string" && !paramRule.enum.includes(value)) {
      const readable = paramRule.enum.join(" 或 ");
      return `${key} 只能是 ${readable}`;
    }

    if (paramRule.min !== undefined && typeof value === "number" && value < paramRule.min) {
      const suffix = paramRule.min > 0 ? "正数" : `不小于 ${paramRule.min}`;
      return `${key} 必须是${suffix}`;
    }
  }

  if (command === "backtest.run" && !params.symbol && !params.symbols) {
    return "backtest.run 至少需要 symbol 或 symbols";
  }

  return null;
}

function validateType(key: string, value: unknown, rule: ParamRule): string | null {
  if (!rule.type) {
    return null;
  }

  if (rule.type === "array") {
    return Array.isArray(value) ? null : `${key} 必须是数组`;
  }
  if (rule.type === "integer") {
    return typeof value === "number" && Number.isInteger(value) ? null : `${key} 必须是整数`;
  }
  if (rule.type === "number") {
    return typeof value === "number" && Number.isFinite(value) ? null : `${key} 必须是数字`;
  }
  if (rule.type === "boolean") {
    return typeof value === "boolean" ? null : `${key} 必须是布尔值`;
  }
  if (rule.type === "string") {
    return typeof value === "string" ? null : `${key} 必须是字符串`;
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
  return `量化 CLI 执行完成: ${command}\n${JSON.stringify(response, null, 2)}`;
}

/**
 * Run confidence calibration via QuantSys daemon.
 * Calls the run_confidence_calibration handler registered in ml_query.py.
 */
async function runCalibrationBridge(params: Record<string, unknown>) {
  const { callPythonResilient } = await import('../shared/python-caller-resilient-adapter.js');
  const resultJson = await callPythonResilient('run_confidence_calibration', {
    forward_days: params.forward_days ?? 5,
    return_threshold: params.return_threshold ?? 0.02,
    max_symbols: params.max_symbols ?? 500,
    lookback_days: params.lookback_days ?? 180,
  });
  return JSON.parse(resultJson);
}
