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
  deprecated?: boolean;
  replacement?: string;
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
  // stock.ml_predict 已移除 — 使用专用工具 model_predict
  // analysis.swing_points 已移除 — 使用专用工具 analysis_swing_points
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
  // ── 港股相关命令已移除（2026-06-02）──
  // 原因：v1 quantsys 模块已废弃，v2 数据库无港股数据，无实现计划
  // 已移除命令：hk.market_overview, hk.south_flow, hk.technical, hk.hot_rank
  // 替代方案：暂无，港股功能不在当前支持范围

  // signal.scan 已移除 — 使用专用工具 opportunity_scan
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
  // backtest.batch 已移除 — 使用专用工具 strategy_batch_validate
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
  // ml.train 已移除 — 使用专用工具 model_train
  // ml.history 已移除 — 使用专用工具 model_list
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
    example: { symbols: "600000,000001", days: 365 },
  },
  "data.update": {
    domain: "data",
    action: "update",
    description: "统一数据更新入口。source 必填：portfolio(持仓)、watchlist(自选)、hs300(沪深300)、all(全部)。可选 days(天数,默认730)、force(强制全量)、async(异步执行)。",
    params: {
      source: { required: true, type: "string" },
      days: { type: "integer", min: 1 },
      force: { type: "boolean" },
      async: { type: "boolean" },
    },
    example: { source: "all" },
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
    example: { symbol: "600000" },
  },
  // indicators.* 已移除 — 使用专用工具 indicator_list / indicator_detail / indicator_create / indicator_update / indicator_delete / indicator_backtest
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
    description: "基于历史数据优化投资组合权重，支持均值方差、最小方差、风险平价、最大夏普等方法。",
    params: {
      symbols: { required: true, type: "array" },
      start_date: { type: "string" },
      end_date: { type: "string" },
      method: { type: "string", enum: ["mean_variance", "min_variance", "risk_parity", "max_sharpe", "equal_weight"] },
      risk_free_rate: { type: "number" },
      target_return: { type: "number" },
      constraints: { type: "object" },
    },
    example: { symbols: ["600000.SH", "000001.SZ", "600519.SH"], method: "max_sharpe", risk_free_rate: 0.03 },
  },
  "portfolio.correlation": {
    domain: "portfolio",
    action: "correlation",
    description: "计算投资组合内股票的相关性矩阵，用于分散化分析。",
    params: {
      symbols: { required: true, type: "array" },
      start_date: { type: "string" },
      end_date: { type: "string" },
      method: { type: "string", enum: ["pearson", "spearman"] },
    },
    example: { symbols: ["600000.SH", "000001.SZ", "600519.SH"], method: "pearson" },
  },
  // strategy.* 命令已完全移除 — 使用独立工具: strategy_list, strategy_detail, strategy_create, strategy_write, strategy_run, strategy_status, strategy_execute, strategy_optimize, strategy_batch_validate
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
    example: { symbol: "600000", price: 105, above: 100 },
  },
  "watchlist.check": {
    domain: "watchlist",
    action: "check",
    description: "检查股票是否已加入自选股。",
    params: {
      symbol: { required: true, type: "string", symbol: true },
    },
    example: { symbol: "600000" },
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
    example: { positions_json: "[{\"symbol\":\"600000\",\"market_value\":10000}]", shock_pct: -0.2 },
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
    example: { symbol: "600000", action: "buy", price: 100, shares: 300 },
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
    example: { symbol: "600000", price: 100, signal_strength: 0.8 },
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
    example: { symbol: "600000", entry_price: 90, current_price: 100, highest_price: 110 },
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
    example: { symbols: "600000,000001" },
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
  // training.history 已移除 — 使用专用工具 model_list
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
    example: { symbols: "600000", action_type: "forecast", order: "1,1,1", forecast_steps: 10 },
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
    example: { symbols: "600000", action_type: "forecast", p: 1, q: 1, forecast_steps: 5 },
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
    example: { symbols: "600000", action_type: "local_level" },
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
    example: { symbol: "600000", start_date: "2024-01-01", end_date: "2024-12-31" },
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
    example: { symbol: "600000", start_date: "2024-01-01", end_date: "2024-12-31" },
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
    example: { symbol: "600000", start_date: "2024-01-01", end_date: "2024-12-31" },
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
    example: { symbol: "600000", start_date: "2024-01-01", end_date: "2024-12-31" },
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
    "参数格式：command 使用白名单命令名，params 传该命令参数，例如 { command: \"stock.technical\", params: { symbol: \"600000\" } }。 " +
    "常用命令：help、market.overview、market.index_history、market.sectors、market.concept_stocks、market.concepts、market.macro、market.north_flow、market.sector_flow、market.margin、market.news、market.hot_stocks、market.sentiment、stock.batch_quotes、stock.list、analysis.technical、analysis.price_action、analysis.candlestick、analysis.buy_range、analysis.quality、analysis.exit_plan、analysis.peers、indicators.list、indicators.detail、indicators.backtest、screening.sector、screening.quality、hk.market_overview、hk.south_flow、hk.technical、hk.hot_rank、sentiment.stock_fund_flow、sentiment.lhb、sentiment.insider_trades、sentiment.fund_holdings、sentiment.top_fund_stocks、sentiment.top_holders、sentiment.holder_changes、sentiment.margin_data、financial.indicators、financial.valuation、financial.pe_percentile、financial.income_statement、financial.cash_flow、financial.hk_financials、financial.hk_analysis、stock.score、stock.screen、stock.technical、factor.decay、sector.aggregate、benchmark.compare、portfolio.optimize、portfolio.correlation、watch.price_alert、stress.test、risk.trade_check、risk.position_size、risk.stop_loss、trade.verify、signal.list、signal.generate、signal.arbitrate、performance.analyze、backtest.run、backtest.results、data.status、data.full_status、data.update_klines、risk.check、report.daily、report.read_daily、tools.list、tools.describe。" +
    "不要臆造 command 或参数；不确定时先调用 help、tools.list 或 tools.describe。",
  promptSnippet:
    "量化相关能力统一使用 quant_cli。像 bash 一样先用 command=help 查使用说明书，再选择白名单 command 并把参数放进 params；不要调用旧的分散量化工具。",
  promptGuidelines: [
    // ── 元规则 ──
    "不知道量化 CLI 能做什么时，先调用 quant_cli({ command: \"help\" }) 获取命令清单。",
    "不知道某个命令参数时，调用 quant_cli({ command: \"help\", params: { name: \"stock.technical\" } }) 获取单命令说明书。",
    "不确定命令或参数时先用 help / tools.list / tools.describe，不要猜测不存在的 command。",

    // ── 场景决策树（每个场景只给一个工具，不在两个中二选一）──

    // 数据获取
    "单只股票实时行情 → data_fetch_quote（不要用 quant_cli stock.batch_quotes）",
    "批量股票实时价格（3只以上）→ quant_cli stock.batch_quotes",
    "K线历史数据 → data_fetch_kline",
    "财务报表（利润表/资产负债表/现金流）→ data_fetch_financial",
    "分红数据（历史分红/高股息筛选/分红日历）→ data_fetch_dividend",
    "财务指标/估值/PE分位 → quant_cli financial.indicators / financial.valuation / financial.pe_percentile",
    "股票列表/股票池 → quant_cli stock.list",

    // 个股分析
    "综合评分（技术+基本面+动量+质量+估值）→ quant_cli stock.score（每只标的必调入口）",
    "技术因子（RSI/MACD/布林带/均线/KDJ）→ factor_calculate（替代 quant_cli stock.technical / analysis.technical）",
    "ML模型预测信号 → model_predict",
    "质量评分 → quant_cli analysis.quality",
    "技术分析+信号判断 → quant_cli analysis.technical",
    "价格行为/支撑阻力 → quant_cli analysis.price_action",
    "K线形态 → quant_cli analysis.candlestick",
    "买入区间计算 → quant_cli analysis.buy_range",
    "止盈计划 → quant_cli analysis.exit_plan",
    "同行对比 → quant_cli analysis.peers",
    "波段买卖点(ZigZag) → analysis_swing_points",

    // 选股与扫描
    "多条件选股（PE/ROE/负债率筛选）→ quant_cli stock.screen",
    "投资机会扫描（三维评分）→ opportunity_scan",
    "行业板块筛选 → quant_cli screening.sector",
    "行业质量排序 → quant_cli screening.quality",
    "因子分析（IC/覆盖率/稳定性）→ factor_analyze",
    "因子衰减分析 → quant_cli factor.decay",

    // 市场大盘
    "市场概览/指数 → quant_cli market.overview",
    "指数历史 → quant_cli market.index_history",
    "行业资金流向 → quant_cli market.sector_flow",
    "融资融券余额 → quant_cli market.margin",
    "市场情绪/恐惧贪婪 → quant_cli market.sentiment",
    "宏观数据 → quant_cli market.macro",
    "市场新闻/热搜 → quant_cli market.news / market.hot_stocks",

    // 资金面
    "个股资金流向 → quant_cli sentiment.stock_fund_flow",
    "龙虎榜 → quant_cli sentiment.lhb",
    "高管增减持 → quant_cli sentiment.insider_trades",
    "基金持仓 → quant_cli sentiment.fund_holdings",
    "基金重仓排行 → quant_cli sentiment.top_fund_stocks",
    "股东变化 → quant_cli sentiment.holder_changes",
    "融资融券个股 → quant_cli sentiment.margin_data",

    // 策略与信号
    "策略执行（单股/批量/流水线）→ strategy_execute（独立工具）",
    "策略参数优化 → strategy_optimize",
    "批量策略验证 → strategy_batch_validate",
    "信号列表/统计/仲裁 → quant_cli signal.list / signal.statistics / signal.arbitrate",

    // ML模型
    "ML模型训练/预测/评估/监控/列表 → model_train / model_predict / model_evaluate / model_monitor / model_list",

    // 风控与交易
    "交易前风控/Kelly仓位/止损/组合风险检查 → quant_cli risk.trade_check / risk.position_size / risk.stop_loss / risk.check",
    "算法交易（TWAP/VWAP）→ trade_algo_execute",
    "压力测试 → quant_cli stress.test",
    "价格预警 → quant_cli watch.price_alert",
    "实盘回测对比 → quant_cli trade.verify",

    // 组合
    "组合权重优化/相关性/基准对比/行业聚合 → quant_cli portfolio.optimize / portfolio.correlation / benchmark.compare / sector.aggregate",

    // 港股
    "⚠️ 港股不支持。本工具仅支持A股，港股相关命令已移除（2026-06-02）。分析港股前先告知用户暂不支持。",

    // 其他
    "自选股管理 → quant_cli watchlist.*",
    "因子模型（Fama-French/Barra）→ quant_cli factor.fama_french_3 / factor.fama_french_5 / factor.carhart / factor.barra",
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
  execute: async (_toolCallId: string, rawParams: any, signal?: AbortSignal, onUpdate?: any, ctx?: any) => {
    let command = typeof rawParams?.command === "string" ? rawParams.command.trim() : "";
    const params = normalizeParams(rawParams?.params);

    if (command === "help") {
      command = typeof params.name === "string" && params.name.trim()
        ? "tools.describe"
        : "tools.list";
    }

    // ── 向后兼容：signal.generate → 提示使用独立工具 strategy_execute ──
    if (command === "signal.generate") {
      return validationError(
        "⚠️ DEPRECATED: signal.generate 命令已废弃。",
        "请使用独立工具 strategy_execute（action='batch'）替代。此命令将在 v3.0 移除。",
      );
    }

    const rule = COMMANDS[command];

    if (!rule) {
      return validationError(
        `不支持的量化命令: ${command || "(空)"}`,
        `可用命令: ${PUBLIC_COMMAND_LIST.join(", ")}。不确定时先用 help。`,
      );
    }

    // ── 废弃命令提前返回，不走后端 ──
    if (rule.deprecated) {
      return validationError(
        `⚠️ 命令 ${command} 已废弃或暂不可用。`,
        rule.replacement || "请参考 promptGuidelines 使用替代工具。",
      );
    }

    // ── 股票代码标准化：去掉 .SH / .SZ / .HK / .BJ 后缀 ──
    normalizeSymbolParams(params);

    // ── 参数映射：统一常见参数名称 ──
    applyParameterMapping(params);

    // ── 策略名称自动转换 ──
    if (command === "signal.generate" && params.strategy_names && !params.strategy_id) {
      return validationError(
        "strategy_names 参数已废弃",
        "请使用独立工具 strategy_list 查询策略列表，然后通过 strategy_id 参数指定策略。",
      );
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
 * 例如：600000.SH → 600000, 000001.SZ → 000001
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
 * 注意：strategy.* 命令已移除，使用独立工具 strategy_list
 * @returns 格式化的策略列表提示，或降级提示（查询失败时）
 */
export async function fetchStrategyListHint(): Promise<string> {
  try {
    // 直接调用 v2 API（避免使用已移除的 strategy.list 命令）
    const response = await fetch('http://127.0.0.1:5001/api/strategies');
    if (!response.ok) {
      return "提示：使用独立工具 strategy_list 查看可用策略列表。";
    }

    const data = await response.json() as any;
    const strategies = data?.strategies || [];

    if (strategies.length === 0) {
      return "提示：当前系统中没有可用策略。请先使用 strategy_create 创建策略。";
    }

    // 格式化策略列表（最多显示前 10 个）
    const displayStrategies = strategies.slice(0, 10);
    const strategyLines = displayStrategies.map((s: any) =>
      `  - ID: ${s.id}, 名称: ${s.name}`
    ).join('\n');

    const moreHint = strategies.length > 10
      ? `\n\n（共 ${strategies.length} 个策略，仅显示前 10 个）`
      : '';

    return `可用策略列表：\n${strategyLines}${moreHint}\n\n提示：使用独立工具 strategy_list 可查看完整策略详情。`;

  } catch (error) {
    // 降级：查询失败时返回通用提示
    return "提示：使用独立工具 strategy_list 查看可用策略列表。";
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
        return `不支持的参数: ${key}。提示：该命令使用 symbols（复数）参数，支持单个或多个股票。示例：{ symbols: "688008" } 或 { symbols: "688008,600000" }`;
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
      // 特殊处理：strategy_id 参数缺失时附加策略列表
      if (key === 'strategy_id') {
        const strategyListHint = await fetchStrategyListHint();
        return `缺少必填参数: ${key}。原因：该参数是命令执行的必要条件，不能为空。\n\n${strategyListHint}`;
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
      return `${key} 必须是股票代码格式，例如 600000、000001、00700 或 AAPL。原因：系统需要标准格式的股票代码才能查询数据。`;
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
    return Array.isArray(value) ? null : `${key} 必须是数组。原因：该参数需要接收多个值，请使用数组格式，例如 ["600000", "000001"]。`;
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
