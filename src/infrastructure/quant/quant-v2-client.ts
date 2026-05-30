/**
 * QuantSys V2 HTTP 客户端
 *
 * 直连 quantsys-v2 Flask API (默认 127.0.0.1:5001)，
 * 替代旧的 spawn python -m quantsys.cli 桥接方式。
 */
import type { QuantCliResponse } from "./quant-cli-client.js";
import type {
  FinancialData,
  FactorComputeParams,
  FactorResult,
  FactorAnalyzeParams,
  FactorAnalysis,
  FactorMetrics,
  OpportunityScanParams,
  Opportunity,
  AlgoExecuteParams,
  AlgoOrder,
  StrategyExecuteParams,
  StrategyBatchValidateParams,
  StrategyBatchValidateResponse,
  DividendResponse,
  KlineData,
  StockData,
  StockInfo,
  StockPrice,
  StockNews,
  StockAnnouncement,
  ListModelsResponse,
  EvaluateModelResponse,
  MonitorModelResponse,
  StrategyExecutionSignal,
  StrategyBatchExecuteParams,
  StrategyPipelineExecuteParams,
  BatchExecutionResult,
  PipelineExecutionResult,
} from "./types.js";
import { QuantV2Error } from "./types.js";

// ─── 配置 ────────────────────────────────────────────────

const V2_API_BASE =
  process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001";

const V2_TIMEOUT_MS = parseInt(
  process.env.QUANTSYS_V2_TIMEOUT ?? "30000",
  10
);

// ─── 命令 → 端点映射表 ──────────────────────────────────

/**
 * 将 quant_cli 的 domain.action 命令映射到 v2 API 端点。
 * 没在这张表里的命令 → 走旧桥接 fallback。
 *
 * URL 模板支持 {symbol} / {strategy_id} / {job_id} 等占位符，
 * 会从 params 中提取对应字段填充。
 */
const V2_ROUTES: Record<
  string,
  { path: string; method: "GET" | "POST" | "DELETE" }
> = {
  // ── stock ──
  "stock.list":      { path: "/api/stocks/list",          method: "GET" },
  "stock.info":      { path: "/api/stocks/{symbol}",       method: "GET" },
  "stock.quote":     { path: "/api/stock/{symbol}/quote",  method: "GET" },
  "stock.klines":    { path: "/api/stock/{symbol}/klines", method: "GET" },
  "stock.history":   { path: "/api/stock/{symbol}/history", method: "GET" },
  "stock.technical": { path: "/api/stock/{symbol}/technical", method: "GET" },

  // ── analysis (复用 stock 端点) ──
  "analysis.technical":    { path: "/api/stock/{symbol}/technical",    method: "GET" },
  "analysis.valuation":    { path: "/api/stock/{symbol}/valuation",    method: "GET" },
  "analysis.price_action": { path: "/api/stock/{symbol}/price-action", method: "GET" },
  "analysis.buy_range":    { path: "/api/stock/{symbol}/buy-range",    method: "GET" },
  "analysis.exit_plan":    { path: "/api/stock/{symbol}/exit-plan",    method: "GET" },
  "analysis.pe_percentile":{ path: "/api/stock/{symbol}/pe-percentile",method: "GET" },
  "analysis.candlestick":  { path: "/api/stock/{symbol}/candlestick",  method: "GET" },
  "analysis.quality":      { path: "/api/stock/{symbol}/quality",     method: "GET" },
  "indicator.technical":   { path: "/api/stock/{symbol}/technical",    method: "GET" },
  "indicator.candlestick": { path: "/api/stock/{symbol}/candlestick",  method: "GET" },

  // ── market ──
  "market.overview":      { path: "/api/stocks/market/overview",          method: "GET" },
  "market.sectors":       { path: "/api/market/sectors",                 method: "GET" },
  "market.sentiment":     { path: "/api/market/sentiment",               method: "GET" },
  "market.macro":         { path: "/api/market/macro",                   method: "GET" },
  "market.news":          { path: "/api/market/news",                    method: "GET" },
  "market.margin":        { path: "/api/market/margin",                  method: "GET" },
  "market.hot_stocks":    { path: "/api/market/hot-stocks",              method: "GET" },
  "market.sector_flow":   { path: "/api/market/sector-flow",             method: "GET" },
  "market.concepts":      { path: "/api/market/concepts",                method: "GET" },
  "market.concept_stocks":{ path: "/api/market/concept/{concept}/stocks",method: "GET" },

  // ── financial ──
  "financial.indicators":   { path: "/api/stock/{symbol}/indicators",    method: "GET" },
  "financial.statements":   { path: "/api/stock/{symbol}/financials",    method: "GET" },
  "financial.valuation":    { path: "/api/stock/{symbol}/valuation",     method: "GET" },
  "financial.pe_percentile":{ path: "/api/stock/{symbol}/pe-percentile", method: "GET" },

  // ── screening ──
  "screening.sector":  { path: "/api/market/sector/{sector}",  method: "GET" },
  "screening.quality": { path: "/api/screening/quality",        method: "GET" },

  // ── sentiment ──
  "sentiment.stock_fund_flow": { path: "/api/stock/{symbol}/fund-flow",     method: "GET" },
  "sentiment.margin_data":     { path: "/api/stock/{symbol}/margin",         method: "GET" },
  "sentiment.lhb":             { path: "/api/stock/{symbol}/lhb",            method: "GET" },
  "sentiment.fund_holdings":   { path: "/api/stock/{symbol}/fund-holdings", method: "GET" },
  "sentiment.top_fund_stocks": { path: "/api/funds/top-stocks",              method: "GET" },
  "sentiment.top_holders":     { path: "/api/stock/{symbol}/top-holders",   method: "GET" },
  "sentiment.holder_changes":  { path: "/api/stock/{symbol}/holder-changes",method: "GET" },

  // ── stock analytics ──
  "stock.score":  { path: "/api/stock/{symbol}/score", method: "GET" },
  "stock.screen": { path: "/api/stocks/screen",        method: "GET" },

  // ── stock queries ──
  "stock.batch_quotes":  { path: "/api/stocks/batch-quotes",         method: "POST" },
  "stock.announcements": { path: "/api/stock/{symbol}/announcements", method: "GET" },
  "stock.news":          { path: "/api/stock/{symbol}/news",         method: "GET" },

  // ── sentiment extra ──
  "sentiment.insider_trades": { path: "/api/stock/{symbol}/insider-trades", method: "GET" },

  // ── analysis ──
  "analysis.peers":      { path: "/api/stock/{symbol}/peers",          method: "GET" },
  "analysis.peer_comparison": { path: "/api/stock/{symbol}/peers",          method: "GET" },  // alias

  // ── HK market ──
  "hk.market_overview":   { path: "/api/hk/overview",              method: "GET" },
  "hk.south_flow":        { path: "/api/hk/south-flow",            method: "GET" },
  "hk.hot_rank":          { path: "/api/hk/hot-rank",              method: "GET" },
  "hk.technical":         { path: "/api/hk/{symbol}/technical",   method: "GET" },

  // ── HK financials ──
  "financial.hk_financials": { path: "/api/hk/{symbol}/financials",  method: "GET" },
  "financial.hk_analysis":   { path: "/api/hk/{symbol}/analysis",    method: "GET" },

  // ── financial detail ──
  "financial.cash_flow":       { path: "/api/stock/{symbol}/cash-flow",        method: "GET" },
  "financial.income_statement": { path: "/api/stock/{symbol}/income-statement", method: "GET" },

  // ── risk wrappers ──
  "risk.trade_check":   { path: "/api/stock/{symbol}/risk/trade-check",   method: "POST" },
  "risk.position_size": { path: "/api/stock/{symbol}/risk/position-size", method: "POST" },
  "risk.stop_loss":     { path: "/api/stock/{symbol}/risk/stop-loss",     method: "POST" },

  "stress.test":     { path: "/api/risk/stress-test",   method: "POST" },
  "watch.price_alert": { path: "/api/risk/price-alert",  method: "POST" },
  "trade.verify":    { path: "/api/risk/trade-verify",  method: "POST" },

  "benchmark.compare":     { path: "/api/portfolio/benchmark",   method: "POST" },
  "portfolio.optimize":    { path: "/api/portfolio/optimize",    method: "POST" },
  "portfolio.correlation": { path: "/api/portfolio/correlation", method: "POST" },

  "factor.analyze":      { path: "/api/portfolio/factor-analyze",      method: "POST" },
  "factor.decay":        { path: "/api/portfolio/factor-decay",        method: "POST" },
  "sector.aggregate":    { path: "/api/portfolio/sector-aggregate",    method: "POST" },
  "strategy.optimize":   { path: "/api/portfolio/strategy-optimize",   method: "POST" },
  "performance.analyze": { path: "/api/portfolio/performance-analyze", method: "POST" },
  "signal.arbitrate":    { path: "/api/portfolio/signal-arbitrate",    method: "POST" },
  "stock.ml_predict":   { path: "/api/cli/ml-predict",  method: "POST" },
  "ml.history":         { path: "/api/ml/history",   method: "GET"  },
  "calibrate.run":      { path: "/api/cli/calibrate",       method: "POST" },
  "factor.compute":     { path: "/api/cli/factor-compute",  method: "POST" },
  "ml.train":           { path: "/api/cli/ml-train",        method: "POST" },
  "signal.generate":    { path: "/api/cli/signal-generate", method: "POST" },

  // ── market north flow ──
  "market.north_flow": { path: "/api/market/north-flow", method: "GET" },
  "market.index_history": { path: "/api/market/index-history", method: "GET" },

  // ── tools meta ──
  "tools.list":     { path: "/api/tools/list",     method: "GET" },
  "tools.describe": { path: "/api/tools/describe", method: "GET" },

  // ── data management ──
  "data.full_status":  { path: "/api/stocks/data-full-status",  method: "GET" },
  "data.update_klines": { path: "/api/stocks/data-update-klines", method: "POST" },

  // ── factor ──
  "factor.list":     { path: "/api/stock/{symbol}/factors", method: "GET" },

  // ── signal ──
  "signal.list":       { path: "/api/signals",              method: "GET" },
  "signal.scan":       { path: "/api/signals/scan",         method: "POST" },
  "signal.statistics": { path: "/api/signals/statistics",   method: "GET" },

  // ── backtest ──
  "backtest.run":     { path: "/api/backtest/run",      method: "POST" },
  "backtest.strategy": { path: "/api/backtest/strategy", method: "POST" },
  "backtest.batch":   { path: "/api/backtest/batch",    method: "POST" },
  "backtest.results": { path: "/api/backtest/results",  method: "GET" },

  // ── strategy ──
  "strategy.list":   { path: "/api/strategies/list",           method: "GET" },
  "strategy.get":    { path: "/api/strategies/detail/{strategy_id}", method: "GET" },
  "strategy.create": { path: "/api/strategies/create",        method: "POST" },
  "strategy.run":    { path: "/api/strategy/run",             method: "POST" },
  "strategy.status": { path: "/api/strategy/status",          method: "GET" },

  // ── portfolio ──
  "portfolio.summary":  { path: "/api/portfolio/summary",    method: "GET" },
  "portfolio.positions":{ path: "/api/portfolio/positions",  method: "GET" },
  "portfolio.history":  { path: "/api/portfolio/history",    method: "GET" },
  "portfolio.allocation":{ path: "/api/portfolio/allocation",method: "GET" },
  "portfolio.equity_curve": { path: "/api/portfolio/equity-curve", method: "GET" },

  // ── risk ──
  "risk.check": { path: "/api/risk/check", method: "POST" },

  // ── report ──
  "report.daily":      { path: "/api/report/daily",   method: "GET" },
  "report.read_daily": { path: "/api/report/daily",   method: "GET" },

  // ── training ──
  "training.history": { path: "/api/training/history", method: "GET" },
  "training.reports": { path: "/api/training/reports", method: "GET" },

  // ── data ──
  "data.status": { path: "/api/stocks/data-status", method: "GET" },

  // ── performance ──
  "performance.by_strategy":  { path: "/api/performance/strategy/{strategy_id}", method: "GET" },
  "performance.comparison":   { path: "/api/performance/comparison",            method: "GET" },

  // ── executions ──
  "executions.list":  { path: "/api/executions",       method: "GET" },
  "executions.stats": { path: "/api/executions/stats", method: "GET" },

  // ── orders / trades ──
  "orders.list": { path: "/api/orders/list", method: "GET" },
  "trades.list": { path: "/api/trades/list", method: "GET" },

  // ── scheduler ──
  "scheduler.tasks": { path: "/api/scheduler/tasks", method: "GET" },

  // ── compute ──
  "compute.factors": { path: "/api/compute/factors", method: "POST" },

  // ── charts ──
  "charts.accuracy":    { path: "/api/charts/accuracy",    method: "GET" },
  "charts.equity":      { path: "/api/charts/equity",      method: "GET" },
  "charts.comparison":  { path: "/api/charts/comparison",  method: "GET" },
  "charts.importance":  { path: "/api/charts/importance",  method: "GET" },

  // ── data update ──
  "data.update": { path: "/api/data/update", method: "POST" },

  // ── jobs ──
  "jobs.list": { path: "/api/jobs", method: "GET" },

  // ── indicators ──
  "indicators.list":   { path: "/api/indicators/list",                   method: "GET" },
  "indicators.detail": { path: "/api/indicators/detail/{indicator_id}",  method: "GET" },
  "indicators.create": { path: "/api/indicators/create",                method: "POST" },
  "indicators.update": { path: "/api/indicators/update/{indicator_id}",  method: "POST" },
  "indicators.delete": { path: "/api/indicators/delete/{indicator_id}",  method: "POST" },
  "indicators.run":    { path: "/api/indicators/run/{indicator_id}",     method: "POST" },
  "indicators.backtest": { path: "/api/indicators/backtest",             method: "POST" },
  "indicators.compare":  { path: "/api/indicators/compare",              method: "POST" },
  "indicators.sandbox_columns": { path: "/api/indicators/sandbox-columns", method: "GET" },

  // ── timeseries ──
  "timeseries.arima": { path: "/api/timeseries/arima/{action_type}", method: "POST" },
  "timeseries.garch": { path: "/api/timeseries/garch/{action_type}", method: "POST" },
  "timeseries.kalman": { path: "/api/timeseries/kalman/{action_type}", method: "POST" },

  // ── factor models ──
  "factor.fama_french_3": { path: "/api/factor-models/fama-french-3/calculate", method: "POST" },
  "factor.fama_french_5": { path: "/api/factor-models/fama-french-5/calculate", method: "POST" },
  "factor.carhart": { path: "/api/factor-models/carhart/calculate", method: "POST" },
  "factor.barra": { path: "/api/factor-models/barra/calculate", method: "POST" },

  // ── portfolio optimization ──
  "portfolio.markowitz": { path: "/api/portfolio/markowitz/optimize", method: "POST" },
  "portfolio.black_litterman": { path: "/api/portfolio/black-litterman/optimize", method: "POST" },
  "portfolio.risk_parity": { path: "/api/portfolio/risk-parity/optimize", method: "POST" },
  "portfolio.risk_decomposition": { path: "/api/portfolio/risk-parity/risk-decomposition", method: "POST" },

  // ── signal test ──
  "signal.test_run":     { path: "/api/signal-test/run-strategy",  method: "POST" },
  "signal.test_record":  { path: "/api/signal-test/record",         method: "POST" },
  "signal.test_verify":  { path: "/api/signal-test/verify",         method: "POST" },
  "signal.test_stats":   { path: "/api/signal-test/stats",          method: "GET" },

  // ── watchlist ──
  "watchlist.list":      { path: "/api/stocks/watchlist",          method: "GET" },
  "watchlist.add":       { path: "/api/stocks/watchlist",          method: "POST" },
  "watchlist.remove":    { path: "/api/stocks/watchlist/{symbol}", method: "DELETE" },
  "watchlist.check":     { path: "/api/stocks/watchlist/{symbol}/check", method: "GET" },
  "watchlist.groups":    { path: "/api/stocks/watchlist/groups",   method: "GET" },
};

/** v2 不支持但可用的命令名列表（用于调试） */
export const V2_COMMAND_LIST = Object.keys(V2_ROUTES).sort();

// ─── 健康检查 ────────────────────────────────────────────

interface PingCacheEntry {
  ok: boolean;
  at: number;
}

let _pingCache: PingCacheEntry | null = null;
const PING_TTL_MS = 60_000;

/**
 * 检查 quantsys-v2 API 是否可达。
 * 结果缓存 60s，避免每次命令都触发 HTTP 请求。
 */
export async function pingV2(): Promise<boolean> {
  const now = Date.now();
  if (_pingCache && now - _pingCache.at < PING_TTL_MS) {
    return _pingCache.ok;
  }

  try {
    const resp = await fetch(`${V2_API_BASE}/api/health`, {
      signal: AbortSignal.timeout(5_000),
    });
    const ok = resp.ok;
    _pingCache = { ok, at: now };
    return ok;
  } catch {
    _pingCache = { ok: false, at: now };
    return false;
  }
}

// ─── 核心执行函数 ────────────────────────────────────────

interface V2ApiResponse {
  success?: boolean;
  data?: unknown;
  warnings?: string[];
  error?: string | object;
}

export interface V2ClientOptions {
  signal?: AbortSignal;
}

/**
 * 通过 HTTP 调用 quantsys-v2 API 执行量化命令。
 *
 * 返回格式与旧 `runQuantCli` 兼容（QuantCliResponse<T>）。
 */
export async function runQuantV2<T = unknown>(
  command: string,
  params: Record<string, unknown> = {},
  opts: V2ClientOptions = {},
): Promise<QuantCliResponse<T>> {
  const route = V2_ROUTES[command];
  if (!route) {
    throw new QuantV2Error(
      `命令 ${command} 没有 v2 端点映射`,
      404,
      command,
    );
  }

  const { url, body } = buildRequest(route, params);

  try {
    const response = await fetch(url, {
      method: route.method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: opts.signal ?? AbortSignal.timeout(V2_TIMEOUT_MS),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new QuantV2Error(
        `HTTP ${response.status}: ${text || response.statusText}`,
        response.status,
        url,
      );
    }

    const raw = (await response.json()) as V2ApiResponse;

    // 规范化响应格式：v2 用 { success, data } → 统一为 { ok, data }
    return {
      ok: raw.success !== false,
      command,
      params,
      data: (raw.data ?? raw) as T | undefined,
      warnings: raw.warnings ?? [],
      error: raw.error
        ? { message: typeof raw.error === "string" ? raw.error : JSON.stringify(raw.error) }
        : null,
    };
  } catch (error) {
    if (error instanceof QuantV2Error) throw error;

    // 检查是否是连接失败（服务未启动）
    const errorMsg = error instanceof Error ? error.message : String(error);
    if (errorMsg.includes('fetch failed') || errorMsg.includes('ECONNREFUSED')) {
      // 检查服务状态
      const isHealthy = await pingV2();
      if (!isHealthy) {
        throw new QuantV2Error(
          `quantsys-v2 后端未启动。请先启动后端服务：\n` +
          `  cd quantsys-v2 && python start_all.py\n` +
          `或单独启动 REST API：\n` +
          `  cd quantsys-v2 && python api/server.py\n` +
          `预期端口：${V2_API_BASE}`,
          503,
          url,
        );
      }
    }

    throw new QuantV2Error(
      `请求异常: ${errorMsg}`,
      undefined,
      url,
    );
  }
}

// ─── 内部辅助 ────────────────────────────────────────────

function buildRequest(
  route: { path: string; method: "GET" | "POST" | "DELETE" },
  params: Record<string, unknown>,
): { url: string; body: Record<string, unknown> | null } {
  let path = route.path;

  // 提取 URL 路径占位符
  const pathParams = new Set<string>();
  const pathRe = /\{(\w+)\}/g;
  let m: RegExpExecArray | null;
  while ((m = pathRe.exec(path)) !== null) {
    pathParams.add(m[1]!);
  }

  // 从 params 中提取路径参数填充 URL，剩下的作为 query/body
  const remaining: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(params)) {
    if (k === "command") continue;
    if (pathParams.has(k) && (typeof v === "string" || typeof v === "number")) {
      path = path.replace(`{${k}}`, encodeURIComponent(String(v)));
    } else if (v !== undefined && v !== null) {
      remaining[k] = v;
    }
  }

  if (route.method === "GET" || route.method === "DELETE") {
    const qs = buildQueryString(remaining);
    return { url: `${V2_API_BASE}${path}${qs ? "?" + qs : ""}`, body: null };
  }

  return { url: `${V2_API_BASE}${path}`, body: remaining };
}

function buildQueryString(params: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) {
      for (const item of v) {
        parts.push(
          `${encodeURIComponent(k)}=${encodeURIComponent(String(item))}`,
        );
      }
    } else {
      parts.push(
        `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`,
      );
    }
  }
  return parts.join("&");
}

// ─── 高级 API 方法 ────────────────────────────────────────

/**
 * 通用 HTTP 请求包装器，统一错误处理
 */
async function fetchV2<T>(
  url: string,
  options: {
    method?: 'GET' | 'POST';
    body?: unknown;
  } = {},
): Promise<T> {
  try {
    const response = await fetch(url, {
      method: options.method ?? 'GET',
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: AbortSignal.timeout(V2_TIMEOUT_MS),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new QuantV2Error(
        `HTTP ${response.status}: ${text || response.statusText}`,
        response.status,
        url,
      );
    }

    return await response.json() as T;
  } catch (error) {
    if (error instanceof QuantV2Error) throw error;

    // 检查是否是连接失败（服务未启动）
    const errorMsg = error instanceof Error ? error.message : String(error);
    if (errorMsg.includes('fetch failed') || errorMsg.includes('ECONNREFUSED')) {
      // 检查服务状态
      const isHealthy = await pingV2();
      if (!isHealthy) {
        throw new QuantV2Error(
          `quantsys-v2 后端未启动。请先启动后端服务：\n` +
          `  cd quantsys-v2 && python start_all.py\n` +
          `或单独启动 REST API：\n` +
          `  cd quantsys-v2 && python api/server.py\n` +
          `预期端口：${V2_API_BASE}`,
          503,
          url,
        );
      }
    }

    throw new QuantV2Error(
      `请求异常: ${errorMsg}`,
      undefined,
      url,
    );
  }
}

/**
 * 获取财务数据
 * @param symbol 股票代码
 * @param statementType 报表类型: 'income' | 'balance' | 'cash_flow' | 'all'
 * @param periods 期数，默认 4
 */
export async function getFinancials(
  symbol: string,
  statementType: 'income' | 'balance' | 'cash_flow' | 'all' = 'all',
  periods = 4,
): Promise<FinancialData> {
  if (!symbol || symbol.trim() === '') {
    throw new QuantV2Error('股票代码不能为空', 400);
  }

  const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/financials?type=${statementType}&periods=${periods}`;

  // API 返回格式: { success: true, data: { symbol, name, incomeStatement: [...], balanceSheet: [...], cashFlow: [...] } }
  const response = await fetchV2<{
    success: boolean;
    data: {
      symbol: string;
      name: string;
      statementType: string;
      periods: number;
      incomeStatement?: Array<Record<string, any>>;
      balanceSheet?: Array<Record<string, any>>;
      cashFlow?: Array<Record<string, any>>;
    };
  }>(url);

  if (!response.success || !response.data) {
    throw new QuantV2Error('财务数据获取失败', 500);
  }

  const { data } = response;

  // 转换为 FinancialData 格式（取最新一期数据）
  const result: FinancialData = {
    success: true,
    symbol: data.symbol,
    name: data.name,
    report_date: '', // 将从报表数据中提取
  };

  // 转换利润表
  if (data.incomeStatement && data.incomeStatement.length > 0) {
    const income = data.incomeStatement[0];
    result.report_date = income['报告期'] || income['公告日期'] || '';

    const revenue = income['营业总收入'] || income['营业收入'] || 0;
    const operatingCost = income['营业总成本'] || income['营业成本'] || 0;
    const netProfit = income['净利润'] || 0;
    const netProfitAttrParent = income['归属于母公司所有者的净利润'] || netProfit;
    const grossProfit = revenue - (income['营业成本'] || 0);

    result.income_statement = {
      revenue,
      operating_cost: operatingCost,
      gross_profit: grossProfit,
      net_profit: netProfit,
      net_profit_attr_parent: netProfitAttrParent,
      gross_margin: revenue > 0 ? (grossProfit / revenue) * 100 : 0,
      net_margin: revenue > 0 ? (netProfit / revenue) * 100 : 0,
    };
  }

  // 转换资产负债表
  if (data.balanceSheet && data.balanceSheet.length > 0) {
    const balance = data.balanceSheet[0];
    if (!result.report_date) {
      result.report_date = balance['报告期'] || balance['公告日期'] || '';
    }

    const totalAssets = balance['资产总计'] || 0;
    const currentAssets = balance['流动资产合计'] || 0;
    const totalLiabilities = balance['负债合计'] || 0;
    const currentLiabilities = balance['流动负债合计'] || 0;
    const totalEquity = balance['股东权益合计'] || balance['所有者权益(或股东权益)合计'] || 0;

    result.balance_sheet = {
      total_assets: totalAssets,
      current_assets: currentAssets,
      total_liabilities: totalLiabilities,
      current_liabilities: currentLiabilities,
      total_equity: totalEquity,
      debt_ratio: totalAssets > 0 ? (totalLiabilities / totalAssets) * 100 : 0,
      current_ratio: currentLiabilities > 0 ? currentAssets / currentLiabilities : 0,
    };
  }

  // 转换现金流量表
  if (data.cashFlow && data.cashFlow.length > 0) {
    const cashflow = data.cashFlow[0];
    if (!result.report_date) {
      result.report_date = cashflow['报告期'] || cashflow['公告日期'] || '';
    }

    result.cash_flow = {
      operating_cashflow: cashflow['经营活动产生的现金流量净额'] || 0,
      investing_cashflow: cashflow['投资活动产生的现金流量净额'] || 0,
      financing_cashflow: cashflow['筹资活动产生的现金流量净额'] || 0,
      net_cashflow: cashflow['现金及现金等价物净增加额'] || 0,
    };
  }

  return result;
}

/**
 * 批量计算因子
 * @param params 因子计算参数
 */
export async function computeFactors(
  params: FactorComputeParams,
): Promise<FactorResult> {
  if (!params.symbols || params.symbols.length === 0) {
    throw new QuantV2Error('股票列表不能为空', 400);
  }

  const url = `${V2_API_BASE}/api/compute/factors`;
  return fetchV2<FactorResult>(url, { method: 'POST', body: params });
}

/**
 * 因子分析
 * @param params 因子分析参数
 */
export async function analyzeFactors(
  params: FactorAnalyzeParams,
): Promise<FactorAnalysis> {
  if (!params.factors || params.factors.length === 0) {
    throw new QuantV2Error('因子列表不能为空', 400);
  }
  if (!params.start_date || !params.end_date) {
    throw new QuantV2Error('开始日期和结束日期不能为空', 400);
  }

  const url = `${V2_API_BASE}/api/portfolio/factor-analyze`;

  // API 返回格式: { success: true, data: { success: true, factors: [...] } }
  // 需要解包 data 字段并转换 camelCase → snake_case
  const response = await fetchV2<{
    success: boolean;
    data: {
      success: boolean;
      factors: Array<{
        name: string;
        icDaily: number;
        icWeekly: number;
        icMonthly: number;
        coverage: number;
        stability: number;
        decayCurve: number[];
      }>;
      count?: number;
      note?: string;
      warning?: string;
    };
  }>(url, { method: 'POST', body: params });

  // 转换字段名：camelCase → snake_case
  const factors: FactorMetrics[] = (response.data.factors || []).map(f => ({
    name: f.name,
    ic_daily: f.icDaily,
    ic_weekly: f.icWeekly,
    ic_monthly: f.icMonthly,
    coverage: f.coverage,
    stability: f.stability,
    decay_curve: f.decayCurve,
  }));

  return {
    success: response.data.success,
    factors,
  };
}

/**
 * 扫描投资机会
 * @param params 扫描参数
 */
export async function scanOpportunities(
  params: OpportunityScanParams = {},
): Promise<Opportunity[]> {
  const url = `${V2_API_BASE}/api/signals/scan`;
  const result = await fetchV2<{ success: boolean; opportunities: Opportunity[] }>(
    url,
    { method: 'POST', body: params },
  );
  return result.opportunities || [];
}

/**
 * 执行算法交易订单
 * @param params 算法交易参数
 */
export async function algoExecute(
  params: AlgoExecuteParams,
): Promise<AlgoOrder> {
  if (!params.symbol || params.symbol.trim() === '') {
    throw new QuantV2Error('股票代码不能为空', 400);
  }
  if (!params.side || !['buy', 'sell'].includes(params.side)) {
    throw new QuantV2Error('交易方向必须是 buy 或 sell', 400);
  }
  if (!params.quantity || params.quantity <= 0) {
    throw new QuantV2Error('交易数量必须大于 0', 400);
  }
  if (!params.algo || !['TWAP', 'VWAP'].includes(params.algo)) {
    throw new QuantV2Error('算法类型必须是 TWAP 或 VWAP', 400);
  }

  const url = `${V2_API_BASE}/api/orders/algo-execute`;
  return fetchV2<AlgoOrder>(url, { method: 'POST', body: params });
}

/**
 * 批量验证策略有效性
 * @param params 验证参数
 */
export async function batchValidateStrategies(
  params: StrategyBatchValidateParams,
): Promise<StrategyBatchValidateResponse> {
  if (!params.startDate || !params.endDate) {
    throw new QuantV2Error('开始日期和结束日期不能为空', 400, '/api/strategies/validate');
  }

  const url = `${V2_API_BASE}/api/strategies/validate`;
  return fetchV2<StrategyBatchValidateResponse>(url, { method: 'POST', body: params });
}

/**
 * 获取分红数据
 * @param params 分红查询参数
 */
export async function getDividends(
  params: {
    mode: 'single' | 'screen' | 'calendar';
    symbol?: string;
    years?: number;
    min_yield?: number;
    min_years?: number;
    min_payout_ratio?: number;
    max_payout_ratio?: number;
    limit?: number;
    start_date?: string;
    end_date?: string;
    event?: string;
  }
): Promise<DividendResponse> {
  const { mode, symbol, years, ...rest } = params;

  try {
    if (mode === 'single') {
      if (!symbol) {
        throw new QuantV2Error('single 模式必须提供 symbol 参数');
      }

      const url = `${V2_API_BASE}/api/stock/${symbol}/dividends?years=${years || 10}`;
      const response = await fetch(url, {
        signal: AbortSignal.timeout(V2_TIMEOUT_MS)
      });

      if (!response.ok) {
        throw new QuantV2Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json() as DividendResponse;
    }

    if (mode === 'screen') {
      const url = `${V2_API_BASE}/api/dividends/screen`;
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rest),
        signal: AbortSignal.timeout(V2_TIMEOUT_MS)
      });

      if (!response.ok) {
        throw new QuantV2Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json() as DividendResponse;
    }

    if (mode === 'calendar') {
      const { start_date, end_date, event = 'ex_dividend' } = rest;

      if (!start_date || !end_date) {
        throw new QuantV2Error('calendar 模式必须提供 start_date 和 end_date 参数');
      }

      const url = `${V2_API_BASE}/api/dividends/calendar?start_date=${start_date}&end_date=${end_date}&event=${event}`;
      const response = await fetch(url, {
        signal: AbortSignal.timeout(V2_TIMEOUT_MS)
      });

      if (!response.ok) {
        throw new QuantV2Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json() as DividendResponse;
    }

    throw new QuantV2Error(`未知查询模式: ${mode}`);

  } catch (error) {
    if (error instanceof QuantV2Error) {
      throw error;
    }
    throw new QuantV2Error(
      `分红数据查询失败: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

/**
 * 获取K线历史数据
 * @param symbol 股票代码
 * @param period 周期 (daily/weekly/monthly)
 * @param startDate 开始日期 YYYYMMDD 或 YYYY-MM-DD
 * @param endDate 结束日期 YYYYMMDD 或 YYYY-MM-DD
 * @param limit 最大返回条数 (默认60)
 */
export async function getKlineHistory(
  symbol: string,
  period: 'daily' | 'weekly' | 'monthly' = 'daily',
  startDate?: string,
  endDate?: string,
  limit: number = 60,
): Promise<KlineData> {
  if (!symbol || symbol.trim() === '') {
    throw new QuantV2Error('股票代码不能为空', 400);
  }

  const params: Record<string, string | number> = {
    period,
    limit: Math.min(limit, 200),
  };

  // Helper function to validate and convert date format
  const convertDate = (date: string, fieldName: string): string => {
    // Already in YYYY-MM-DD format
    if (/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return date;
    }
    // YYYYMMDD format - convert to YYYY-MM-DD
    if (/^\d{8}$/.test(date)) {
      return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
    }
    // Invalid format
    throw new QuantV2Error(
      `${fieldName} 格式无效: "${date}"。请使用 YYYYMMDD 或 YYYY-MM-DD 格式`,
      400
    );
  };

  if (startDate) {
    params.start_date = convertDate(startDate, 'start_date');
  }

  if (endDate) {
    params.end_date = convertDate(endDate, 'end_date');
  }

  const queryString = buildQueryString(params);
  const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/history${queryString ? '?' + queryString : ''}`;

  try {
    const response = await fetchV2<KlineData>(url);
    return {
      ...response,
      success: response.success ?? true,
    };
  } catch (error) {
    if (error instanceof QuantV2Error) {
      return {
        success: false,
        symbol,
        period,
        count: 0,
        data: [],
        error: error.message,
      };
    }
    throw error;
  }
}

/**
 * 获取股票基础数据（info/price/news/announcements）
 * @param symbol 股票代码
 * @param fields 要获取的字段列表
 * @param newsNum 新闻条数（仅当fields包含news时有效）
 * @param source 数据源选择（realtime=实时数据，db=数据库，auto=自动选择，默认realtime）
 */
export async function getStockData(
  symbol: string,
  fields: Array<'info' | 'price' | 'news' | 'announcements'> = ['info', 'price'],
  newsNum: number = 10,
  source: 'realtime' | 'db' | 'auto' = 'realtime',
): Promise<StockData> {
  if (!symbol || symbol.trim() === '') {
    throw new QuantV2Error('股票代码不能为空', 400);
  }

  const result: StockData = { success: true };
  const fetchPromises: Promise<void>[] = [];

  // Fetch info
  if (fields.includes('info')) {
    fetchPromises.push(
      (async () => {
        try {
          const url = `${V2_API_BASE}/api/stocks/${encodeURIComponent(symbol)}`;
          const data = await fetchV2<StockInfo>(url);
          result.info = data;
        } catch (error) {
          result.info = null;
          result.info_error = error instanceof Error ? error.message : String(error);
        }
      })()
    );
  }

  // Fetch price
  if (fields.includes('price')) {
    fetchPromises.push(
      (async () => {
        try {
          const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/quote?source=${source}`;
          const data = await fetchV2<StockPrice>(url);
          result.price = data;
        } catch (error) {
          result.price = null;
          result.price_error = error instanceof Error ? error.message : String(error);
        }
      })()
    );
  }

  // Fetch news
  if (fields.includes('news')) {
    fetchPromises.push(
      (async () => {
        try {
          const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/news?num=${newsNum}`;
          const data = await fetchV2<{ news: StockNews[] }>(url);
          result.news = data.news || [];
        } catch (error) {
          result.news = null;
          result.news_error = error instanceof Error ? error.message : String(error);
        }
      })()
    );
  }

  // Fetch announcements
  if (fields.includes('announcements')) {
    fetchPromises.push(
      (async () => {
        try {
          const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/announcements`;
          const data = await fetchV2<{ announcements: StockAnnouncement[] }>(url);
          result.announcements = data.announcements || [];
        } catch (error) {
          result.announcements = null;
          result.announcements_error = error instanceof Error ? error.message : String(error);
        }
      })()
    );
  }

  // Wait for all fetches to complete
  await Promise.all(fetchPromises);

  // Check if all fields failed
  const hasAnySuccess = fields.some(field => {
    if (field === 'info') return result.info !== null;
    if (field === 'price') return result.price !== null;
    if (field === 'news') return result.news !== null;
    if (field === 'announcements') return result.announcements !== null;
    return false;
  });

  if (!hasAnySuccess) {
    result.success = false;
    const firstError = result.info_error || result.price_error || result.news_error || result.announcements_error;
    result.error = firstError || '所有数据获取失败';
  }

  return result;
}

/**
 * 列出模型
 */
export async function listModels(
  modelType?: string,
  status?: string,
  limit?: number
): Promise<ListModelsResponse> {
  const params = new URLSearchParams();
  if (modelType) params.append("model_type", modelType);
  if (status) params.append("status", status);
  if (limit) params.append("limit", limit.toString());

  const url = `${V2_API_BASE}/api/ml/models${params.toString() ? `?${params.toString()}` : ""}`;
  return fetchV2<ListModelsResponse>(url, { method: "GET" });
}

/**
 * 评估模型
 */
export async function evaluateModel(
  modelType: string = "xgboost",
  version: string = "latest"
): Promise<EvaluateModelResponse> {
  const params = new URLSearchParams({ model_type: modelType, version });

  return fetchV2<EvaluateModelResponse>(
    `${V2_API_BASE}/api/ml/model/evaluate?${params.toString()}`,
    { method: "GET" }
  );
}

/**
 * 监控模型漂移
 */
export async function monitorModel(
  modelType: string = "xgboost",
  version: string = "latest",
  days: number = 30
): Promise<MonitorModelResponse> {
  const params = new URLSearchParams({
    model_type: modelType,
    version,
    days: days.toString()
  });

  return fetchV2<MonitorModelResponse>(
    `${V2_API_BASE}/api/ml/model/monitor?${params.toString()}`,
    { method: "GET" }
  );
}

/**
 * 训练模型（复用现有端点）
 */
export async function trainModel(params: {
  model_type?: string;
  start_date?: string;
  end_date?: string;
  test_size?: number;
  symbols?: string[];
  params?: Record<string, any>;
}): Promise<any> {
  return fetchV2(`${V2_API_BASE}/api/ml/train`, {
    method: "POST",
    body: params
  });
}

/**
 * 模型预测（复用现有端点）
 */
export async function predictModel(params: {
  model_type?: string;
  version?: string;
  symbols: string[];
  date?: string;
}): Promise<any> {
  return fetchV2(`${V2_API_BASE}/api/ml/predict`, {
    method: "POST",
    body: params
  });
}

// ─── 策略执行方法 (Strategy System Unification - Phase 2) ────

/**
 * 执行单个策略并返回信号
 * @param params 策略执行参数
 */
export async function executeStrategy(
  params: StrategyExecuteParams
): Promise<StrategyExecutionSignal> {
  const response = await fetch(`${V2_API_BASE}/api/strategies/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal: AbortSignal.timeout(V2_TIMEOUT_MS)
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new QuantV2Error(
      `HTTP ${response.status}: ${text || response.statusText}`,
      response.status,
      '/api/strategies/execute'
    );
  }

  const result = await response.json() as { success: boolean; data: StrategyExecutionSignal; error?: string };

  if (!result.success) {
    throw new QuantV2Error(
      result.error || 'Unknown error',
      undefined,
      '/api/strategies/execute'
    );
  }

  return result.data;
}

/**
 * 批量执行策略并返回信号（NDJSON 流式响应）
 * @param params 批量执行参数
 */
export async function batchExecuteStrategy(
  params: StrategyBatchExecuteParams
): Promise<BatchExecutionResult> {
  const response = await fetch(`${V2_API_BASE}/api/strategies/batch-execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal: AbortSignal.timeout(V2_TIMEOUT_MS)
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new QuantV2Error(
      `HTTP ${response.status}: ${text || response.statusText}`,
      response.status,
      '/api/strategies/batch-execute'
    );
  }

  // Parse NDJSON response
  const text = await response.text();
  const lines = text.split('\n').filter(line => line.trim());

  const signals: StrategyExecutionSignal[] = [];
  const errors: Array<{ symbol: string; error: string }> = [];
  let summary = {
    total: 0,
    success: 0,
    failed: 0,
    buy: 0,
    sell: 0,
    hold: 0,
    duration_ms: 0,
  };

  for (const line of lines) {
    try {
      const item = JSON.parse(line);

      if (item.type === 'signal') {
        signals.push(item.data);
      } else if (item.type === 'error') {
        errors.push({
          symbol: item.symbol,
          error: item.error,
        });
      } else if (item.type === 'summary') {
        summary = {
          total: item.total,
          success: item.success,
          failed: item.failed,
          buy: item.buy,
          sell: item.sell,
          hold: item.hold,
          duration_ms: item.duration_ms,
        };
      }
    } catch (parseError) {
      // Skip malformed lines
      continue;
    }
  }

  return {
    signals,
    summary,
    errors,
  };
}

/**
 * 执行策略管道（信号生成 → 风险检查 → 订单创建）
 * @param params 管道执行参数
 */
export async function pipelineExecuteStrategy(
  params: StrategyPipelineExecuteParams
): Promise<PipelineExecutionResult> {
  const response = await fetch(`${V2_API_BASE}/api/strategies/pipeline-execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal: AbortSignal.timeout(V2_TIMEOUT_MS)
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new QuantV2Error(
      `HTTP ${response.status}: ${text || response.statusText}`,
      response.status,
      '/api/strategies/pipeline-execute'
    );
  }

  const result = await response.json() as { success: boolean; data: PipelineExecutionResult; error?: string };

  if (!result.success) {
    throw new QuantV2Error(
      result.error || 'Unknown error',
      undefined,
      '/api/strategies/pipeline-execute'
    );
  }

  return result.data;
}

