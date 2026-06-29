import type { FinancialDataSource } from "./types.js";
/**
 * QuantSys V2 HTTP 客户端
 *
 * 直连 quantsys-v2 Flask API (默认 127.0.0.1:5001)，
 * 替代旧的 spawn python -m quantsys.cli 桥接方式。
 */
import type { QuantCliResponse } from "./types.js";
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
  RiskMetrics,
  RiskMetricsParams,
  PortfolioOptimizationParams,
  PortfolioOptimizationResult,
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
  { path: string; method: "GET" | "POST" | "PUT" | "DELETE"; paramMap?: Record<string, string> }
> = {
  // ── stock ──
  "stock.list":      { path: "/api/stocks/list",          method: "GET" },
  // stock.info 已移除 — 使用专用工具 data_fetch_quote
  // stock.quote 已移除 — 使用专用工具 data_fetch_quote
  // stock.klines 已移除 — 使用专用工具 data_fetch_kline
  // stock.history 已移除 — 使用专用工具 data_fetch_kline
  "stock.technical": { path: "/api/stock/{symbol}/technical", method: "GET" },

  // ── analysis (复用 stock 端点) ──
  "analysis.technical":    { path: "/api/stock/{symbol}/technical",    method: "GET" },
  "analysis.valuation":    { path: "/api/stock/{symbol}/valuation",    method: "GET" },
  "analysis.price_action": { path: "/api/stock/{symbol}/price-action", method: "GET" },
  "analysis.buy_range":    { path: "/api/stock/{symbol}/buy-range",    method: "GET" },
  "analysis.exit_plan":    { path: "/api/stock/{symbol}/exit-plan",    method: "GET", paramMap: { entry_price: "buy_price" } },
  "analysis.pe_percentile":{ path: "/api/stock/{symbol}/pe-percentile",method: "GET" },
  "analysis.candlestick":  { path: "/api/stock/{symbol}/candlestick",  method: "GET" },
  "analysis.quality":      { path: "/api/stock/{symbol}/quality",     method: "GET" },
  "indicator.technical":   { path: "/api/stock/{symbol}/technical",    method: "GET" },
  "indicator.candlestick": { path: "/api/stock/{symbol}/candlestick",  method: "GET" },

  // ── market ──
  "market.overview":      { path: "/api/stocks/market/overview",          method: "GET" },
  "market.sectors":       { path: "/api/market/sectors",                 method: "GET" },
  "market.sentiment":     { path: "/api/sentiment/market",               method: "GET" },  // ✅ v2 原生实现完成 (FastAPI路径)
  "market.macro":         { path: "/api/market/macro",                   method: "GET" },
  "market.style":         { path: "/api/market/style",                   method: "GET" },  // ✅ 市场风格检测
  "market.news":          { path: "/api/market/news",                    method: "GET" },
  "market.margin":        { path: "/api/market/margin",                  method: "GET" },
  "market.hot_stocks":    { path: "/api/market/hot-stocks",              method: "GET" },
  "market.sector_flow":   { path: "/api/market/sector-flow",             method: "GET" },
  "market.concepts":      { path: "/api/market/concepts",                method: "GET" },
  "market.concept_stocks":{ path: "/api/market/concept/{concept}/stocks",method: "GET" },
  "market.opponent_behavior": { path: "/api/game/market/opponent-behavior", method: "GET" },  // ✅ 对手行为分析

  // ── financial ──
  "financial.indicators":   { path: "/api/stock/{symbol}/indicators",    method: "GET" },
  // financial.statements 已移除 — 使用专用工具 data_fetch_financial
  "financial.valuation":    { path: "/api/stock/{symbol}/valuation",     method: "GET" },
  "financial.pe_percentile":{ path: "/api/stock/{symbol}/pe-percentile", method: "GET" },  // ✅ v2 原生实现完成

  // ── screening ──
  "screening.sector":  { path: "/api/market/sector/{sector}",  method: "GET" },
  "screening.quality": { path: "/api/screening/quality",        method: "GET" },

  // ── sentiment ──
  "sentiment.stock_fund_flow": { path: "/api/stock/{symbol}/fund-flow",     method: "GET" },  // ✅ v2 原生实现完成
  "sentiment.margin_data":     { path: "/api/stock/{symbol}/margin",         method: "GET" },  // ✅ v2 原生实现完成
  "sentiment.lhb":             { path: "/api/stock/{symbol}/lhb",            method: "GET" },
  "sentiment.fund_holdings":   { path: "/api/stock/{symbol}/fund-holdings",  method: "GET" },  // ✅ v2 原生实现完成
  "sentiment.top_fund_stocks": { path: "/api/sentiment/top-fund-stocks",     method: "GET" },  // ✅ v2 原生实现完成
  "sentiment.top_holders":     { path: "/api/stock/{symbol}/top-holders",    method: "GET" },  // ✅ v2 原生实现完成
  "sentiment.holder_changes":  { path: "/api/stock/{symbol}/holder-changes", method: "GET" },  // ✅ v2 原生实现完成

  // ── stock analytics ──
  "stock.score":  { path: "/api/stock/{symbol}/score", method: "GET" },  // ✅ v2 原生实现完成
  "stock.screen": { path: "/api/stocks/screen",        method: "GET" },  // ✅ v2 原生实现完成

  // ── stock queries ──
  "stock.batch_quotes":  { path: "/api/stocks/batch-quotes",         method: "POST" },
  // stock.announcements 已移除 — 功能已整合到 stock_cli
  // stock.news 已移除 — 功能已整合到 stock_cli

  // ── sentiment extra ──
  "sentiment.insider_trades":  { path: "/api/stock/{symbol}/insider-trades", method: "GET" },  // ✅ v2 原生实现完成

  // ── analysis ──
  "analysis.peers":      { path: "/api/stock/{symbol}/peers",          method: "GET" },
  "analysis.peer_comparison": { path: "/api/stock/{symbol}/peers",          method: "GET" },  // alias
  "analysis.swing_points": { path: "/api/analysis/swing-points",       method: "POST" },
  // "analysis.candlestick": 未实现 - 依赖 v1 quantsys 模块
  // "analysis.quality": 未实现 - 依赖 v1 quantsys 模块

  // ── HK market ──
  "hk.market_overview":   { path: "/api/hk/overview",              method: "GET" },
  "hk.south_flow":        { path: "/api/hk/south-flow",            method: "GET" },
  "hk.hot_rank":          { path: "/api/hk/hot-rank",              method: "GET" },
  "hk.technical":         { path: "/api/hk/{symbol}/technical",   method: "GET" },

  // ── HK financials ──
  "financial.hk_financials": { path: "/api/hk/{symbol}/financials",  method: "GET" },
  "financial.hk_analysis":   { path: "/api/hk/{symbol}/analysis",    method: "GET" },

  // ── financial detail (已移除) ──
  // financial.cash_flow 已移除 — 使用专用工具 data_fetch_financial (reportType: "cashflow")
  // financial.income_statement 已移除 — 使用专用工具 data_fetch_financial (reportType: "income")

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

  // factor.analyze 已移除 — 使用专用工具 factor_analyze
  "factor.decay":        { path: "/api/portfolio/factor-decay",        method: "POST" },
  "sector.aggregate":    { path: "/api/portfolio/sector-aggregate",    method: "POST" },
  // strategy.optimize 已移除 — 使用专用工具 strategy_optimize
  "performance.analyze": { path: "/api/portfolio/performance-analyze", method: "POST" },
  "signal.arbitrate":    { path: "/api/portfolio/signal-arbitrate",    method: "POST" },
  // stock.ml_predict 已移除 — 使用专用工具 model_predict
  // ml.history 已移除 — 使用专用工具 model_list
  "calibrate.run":      { path: "/api/cli/calibrate",       method: "POST" },
  // factor.compute 已移除 — 使用专用工具 factor_calculate
  // ml.train 已移除 — 使用专用工具 model_train
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
  // signal.scan 已移除 — 使用专用工具 opportunity_scan
  "signal.statistics": { path: "/api/signals/statistics",   method: "GET" },

  // ── backtest ──
  "backtest.run":     { path: "/api/backtest/run",      method: "POST" },
  "backtest.strategy": { path: "/api/backtest/strategy", method: "POST" },
  // backtest.batch 已移除 — 使用专用工具 strategy_batch_validate
  "backtest.results": { path: "/api/backtest/results",  method: "GET" },

  // ── strategy ──
  "strategy.list":   { path: "/api/strategies/list",           method: "GET" },
  "strategy.get":    { path: "/api/strategies/detail/{strategy_id}", method: "GET" },
  "strategy.create": { path: "/api/strategies",               method: "POST" },
  "strategy.run":    { path: "/api/strategy/run",             method: "POST" },
  "strategy.status": { path: "/api/strategy/status",          method: "GET" },
  "strategy.execute": { path: "/api/strategies/execute",      method: "POST", paramMap: { strategy: "strategyName" } },

  // ── discovery ──
  "discovery.run": { path: "/api/discovery/run", method: "POST" },
  "discovery.archetypes": { path: "/api/discovery/archetypes", method: "GET" },
  "discovery.result": { path: "/api/discovery/result/{run_id}", method: "GET" },

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
  "data.quality-report": { path: "/api/data/quality-report", method: "GET" },
  "data.quality-stats": { path: "/api/data/quality-stats", method: "GET" },
  "data.quality-summary": { path: "/api/data/quality-summary", method: "GET" },
  "data.quality-trend": { path: "/api/data/quality-trend", method: "GET" },

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
  "scheduler.tasks.list": { path: "/api/scheduler/tasks", method: "GET" },
  "scheduler.tasks.create": { path: "/api/scheduler/tasks", method: "POST" },
  "scheduler.tasks.update": { path: "/api/scheduler/tasks/{task_id}", method: "PUT" },
  "scheduler.tasks.enable": { path: "/api/scheduler/tasks/{task_id}/enable", method: "POST" },
  "scheduler.tasks.disable": { path: "/api/scheduler/tasks/{task_id}/disable", method: "POST" },
  "scheduler.tasks.delete": { path: "/api/scheduler/tasks/{task_id}", method: "DELETE" },
  "scheduler.tasks.trigger": { path: "/api/scheduler/tasks/{task_id}/trigger", method: "POST" },
  "scheduler.tasks.runs": { path: "/api/scheduler/tasks/{task_id}/runs", method: "GET" },
  "scheduler.runs.failed": { path: "/api/scheduler/runs/failed", method: "GET" },

  // ── compute ──
  // compute.factors 已移除 — 使用专用工具 factor_calculate

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
 *
 * 支持两种调用签名：
 * - 新签名: runQuantV2(command, params?, opts?)
 * - 旧签名: runQuantV2(module, action, params?, opts?) — 自动拼接为 "module.action"
 */
export async function runQuantV2<T = unknown>(
  command: string,
  params?: Record<string, unknown>,
  opts?: V2ClientOptions,
): Promise<QuantCliResponse<T>>;
export async function runQuantV2<T = unknown>(
  module: string,
  action: string,
  params?: Record<string, unknown>,
  opts?: V2ClientOptions,
): Promise<QuantCliResponse<T>>;
export async function runQuantV2<T = unknown>(
  commandOrModule: string,
  actionOrParams?: string | Record<string, unknown>,
  paramsOrOpts?: Record<string, unknown> | V2ClientOptions,
  opts?: V2ClientOptions,
): Promise<QuantCliResponse<T>> {
  // 兼容旧签名: runQuantV2(module, action, params, opts)
  let command: string;
  let params: Record<string, unknown>;
  if (typeof actionOrParams === 'string') {
    // 旧签名: module + action → 拼接为 "module.action"
    command = `${commandOrModule}.${actionOrParams}`;
    params = (paramsOrOpts as Record<string, unknown>) || {};
    opts = (opts as V2ClientOptions | undefined) || {};
  } else {
    // 新签名: command + params
    command = commandOrModule;
    params = actionOrParams || {};
    opts = (paramsOrOpts as V2ClientOptions | undefined) || {};
  }

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
      signal: opts?.signal ?? AbortSignal.timeout(V2_TIMEOUT_MS),
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
      data: ((raw as any).data ?? raw) as T | undefined,
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
          `  cd quantsys-v2 && python adapters/inbound/api/server.py\n` +
          `(新架构: Spring Boot 风格单进程,自动启动 Scheduler)\n` +
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
  route: { path: string; method: "GET" | "POST" | "PUT" | "DELETE"; paramMap?: Record<string, string> },
  params: Record<string, unknown>,
): { url: string; body: Record<string, unknown> | null } {
  let path = route.path;

  // 参数重映射 → 将客户端键名转换为服务器端名
  if (route.paramMap) {
    for (const [from, to] of Object.entries(route.paramMap)) {
      if (from in params && !(to in params)) {
        params[to] = params[from];
        delete params[from];
      }
    }
  }

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
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
    body?: unknown;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  try {
    const response = await fetch(url, {
      method: options.method ?? 'GET',
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: options.signal ?? AbortSignal.timeout(V2_TIMEOUT_MS),
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
          `  cd quantsys-v2 && python adapters/inbound/api/server.py\n` +
          `(新架构: Spring Boot 风格单进程,自动启动 Scheduler)\n` +
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
 * 获取财务数据（使用多数据源 V2 端点）
 * @param symbol 股票代码
 * @param statementType 报表类型: 'income' | 'balance' | 'cash_flow' | 'all'
 * @param periods 期数，默认 4
 * @param source 数据源策略: 'auto' | 'fresh' | 'cache_only'
 */
export async function getFinancials(
  symbol: string,
  statementType: 'income' | 'balance' | 'cash_flow' | 'all' = 'all',
  periods = 4,
  source: 'auto' | 'fresh' | 'cache_only' = 'auto',
): Promise<FinancialData> {
  if (!symbol || symbol.trim() === '') {
    throw new QuantV2Error('股票代码不能为空', 400);
  }

  // 使用 V2 多数据源端点
  const url = `${V2_API_BASE}/api/v2/stock/${encodeURIComponent(symbol)}/financials?statement_type=${statementType}&periods=${periods}&source=${source}`;

  // V2 API 返回格式（兼容两种结构）:
  //   Flat (current): { success, data: { income_statement: [...], balance_sheet: [...], cash_flow: [...], source, cached } }
  //   Nested (legacy): { success, data: { data: { incomeStatement: [...], ... }, source, cached } }
  const response = await fetchV2<{
    success: boolean;
    data: {
      cached?: boolean;
      source?: string;
      data?: {
        balanceSheet?: Array<Record<string, any>>;
        incomeStatement?: Array<Record<string, any>>;
        cashFlow?: Array<Record<string, any>>;
      };
      // flat fields (current backend format)
      income_statement?: Array<Record<string, any>>;
      balance_sheet?: Array<Record<string, any>>;
      cash_flow?: Array<Record<string, any>>;
    };
  }>(url);

  if (!response.success || !(response as any).data) {
    throw new QuantV2Error('财务数据获取失败', 500);
  }

  const raw = (response as any).data;

  // Accept both nested { data: { data: {...} } } and flat { data: {...} } formats
  const inner = raw?.data || raw;
  const incomeStatement: Array<Record<string, any>> =
    inner?.incomeStatement || inner?.income_statement || [];
  const balanceSheet: Array<Record<string, any>> =
    inner?.balanceSheet || inner?.balance_sheet || [];
  const cashFlow: Array<Record<string, any>> =
    inner?.cashFlow || inner?.cash_flow || [];
  const dataSource: string = raw?.source || '';
  const _dataCached: boolean = raw?.cached || false;

  // 辅助：从记录中提取字段值（兼容中文名和英文名）
  const getField = (record: Record<string, any>, ...names: string[]): number => {
    for (const n of names) {
      const v = record[n];
      if (v !== undefined && v !== null) return Number(v);
    }
    return 0;
  };

  // 辅助：提取日期
  const getDate = (record: Record<string, any>, ...names: string[]): string => {
    for (const n of names) {
      const v = record[n];
      if (v) {
        // 截取日期部分 (YYYY-MM-DD)
        const d = String(v).split(' ')[0]?.split('T')[0] || '';
        if (d) return d;
      }
    }
    return '';
  };

  // 转换为 FinancialData 格式（取最新一期数据）
  const result: FinancialData = {
    success: true,
    symbol: symbol,
    name: '',
    report_date: '',
  };

  // 转换利润表
  if (incomeStatement.length > 0) {
    const income = incomeStatement[0];
    result.report_date = result.report_date || getDate(income,
      '报告期', '公告日期', 'report_date', 'REPORTDATE', 'REPORT_DATE');

    // 字段名按优先级排列：provider 转换后的英文名 → 原始API英文字段 → 中文字段
    const revenue = getField(income, 'total_revenue', 'revenue', '营业总收入', '营业收入', 'TOTAL_OPERATE_INCOME');
    const operatingCost = getField(income, 'total_cost', 'operating_cost', '营业总成本', '营业成本', 'TOTAL_OPERATE_COST');
    const netProfit = getField(income, 'net_profit', '净利润', 'NETPROFIT');
    const netProfitAttrParent = getField(income, 'parent_net_profit', '归母净利润', '归属于母公司所有者的净利润', 'PARENT_NETPROFIT') || netProfit;
    const grossProfit = revenue - getField(income, 'operating_cost', '营业成本', 'OPERATE_COST');

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
  if (balanceSheet.length > 0) {
    const balance = balanceSheet[0];
    result.report_date = result.report_date || getDate(balance,
      '报告期', '公告日期', 'report_date', 'REPORTDATE', 'REPORT_DATE');

    const totalAssets = getField(balance, 'total_assets', '资产总计', '总资产', 'TOTAL_ASSETS');
    const currentAssets = getField(balance, 'current_assets', '流动资产合计', '流动资产', 'CURRENT_ASSETS');
    const totalLiabilities = getField(balance, 'total_liabilities', '负债合计', '总负债', 'TOTAL_LIABILITIES');
    const currentLiabilities = getField(balance, 'current_liabilities', '流动负债合计', '流动负债', 'CURRENT_LIABILITIES');
    const totalEquity = getField(balance, 'total_equity', '股东权益合计', '所有者权益(或股东权益)合计', 'TOTAL_EQUITY');

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
  if (cashFlow.length > 0) {
    const cf = cashFlow[0];
    result.report_date = result.report_date || getDate(cf,
      '报告期', '公告日期', 'report_date', 'REPORTDATE', 'REPORT_DATE');

    result.cash_flow = {
      operating_cashflow: getField(cf,
        'operating_cash_flow', '经营现金流', '经营活动产生的现金流量净额', 'OPERATE_CASH_FLOW_NET', 'NETCASH_OPERATE'),
      investing_cashflow: getField(cf,
        'investing_cash_flow', '投资现金流', '投资活动产生的现金流量净额', 'INVEST_CASH_FLOW_NET', 'NETCASH_INVEST'),
      financing_cashflow: getField(cf,
        'financing_cash_flow', '筹资现金流', '筹资活动产生的现金流量净额', 'FINANCE_CASH_FLOW_NET', 'NETCASH_FINANCE'),
      net_cashflow: getField(cf,
        'cash_increase', '现金及现金等价物净增加额', 'CCE_ADD', 'NETCASH_CHANGE'),
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
 * 因子分析（v2 增强版 - alphalens）
 * @param params 因子分析参数
 */
export async function analyzeFactors(
  params: FactorAnalyzeParams,
): Promise<FactorAnalysis> {
  if (!params.factors || params.factors.length === 0) {
    throw new QuantV2Error('因子列表不能为空', 400);
  }
  if (!params.start_date! || !params.end_date!) {
    throw new QuantV2Error('开始日期和结束日期不能为空', 400);
  }

  const url = `${V2_API_BASE}/api/portfolio/factor-analyze`;

  // API 返回格式（增强版）
  const response = await fetchV2<{
    success: boolean;
    data: {
      success: boolean;
      factors: Array<any>;
      method?: 'alphalens' | 'fallback';
      period?: {
        start: string;
        end: string;
      };
      universe_size?: number | string;
      count?: number;
      note?: string;
      warning?: string;
    };
  }>(url, { method: 'POST', body: params });

  // 转换因子数据（支持 alphalens 和 fallback 两种格式）
  const factors: FactorMetrics[] = ((response as any).data.factors || []).map((f: any) => {
    // 基础字段
    const factor: FactorMetrics = {
      name: f.name,
      coverage: f.coverage,
      data_points: f.data_points || f.dataPoints,
    };

    // alphalens 增强字段
    if (f.ic_analysis || f.icAnalysis) {
      const ic = f.ic_analysis || f.icAnalysis;
      factor.ic_analysis = {
        ic_mean: ic.ic_mean || ic.icMean,
        ic_std: ic.ic_std || ic.icStd,
        ic_ir: ic.ic_ir || ic.icIr,
        t_stat: ic.t_stat || ic.tStat,
        p_value: ic.p_value || ic.pValue,
        ic_by_period: ic.ic_by_period || ic.icByPeriod || {},
      };
    }

    if (f.returns_analysis || f.returnsAnalysis) {
      const returns = f.returns_analysis || f.returnsAnalysis;
      factor.returns_analysis = {
        mean_return_by_quantile: returns.mean_return_by_quantile || returns.meanReturnByQuantile || {},
        mean_return_spread: returns.mean_return_spread || returns.meanReturnSpread || {},
      };
    }

    if (f.turnover_analysis || f.turnoverAnalysis) {
      const turnover = f.turnover_analysis || f.turnoverAnalysis;
      factor.turnover_analysis = {
        mean_turnover: turnover.mean_turnover || turnover.meanTurnover,
        autocorrelation: turnover.autocorrelation || {},
      };
    }

    // 向后兼容字段（fallback 模式）
    if (f.ic_daily !== undefined || f.icDaily !== undefined) {
      factor.ic_daily = f.ic_daily || f.icDaily;
      factor.ic_weekly = f.ic_weekly || f.icWeekly;
      factor.ic_monthly = f.ic_monthly || f.icMonthly;
      factor.stability = f.stability;
      factor.decay_curve = f.decay_curve || f.decayCurve || [];
    }

    return factor;
  });

  return { success:  (response as any).data.success,
    factors,
    method: (response as any).data.method,
    period: (response as any).data.period,
    universe_size: (response as any).data.universe_size,
    note: (response as any).data.note,
    warning: (response as any).data.warning,
  };
}

/**
 * 生成因子分析 HTML 报告
 * @param params 报告生成参数
 */
export async function generateFactorReport(params: {
  factors: string[];
  start_date: string;
  end_date: string;
  universe?: string[];
  output_dir?: string;
}): Promise<{
  success: boolean;
  reports?: Array<{
    factor: string;
    success: boolean;
    report_path?: string;
    file_size?: number;
    url?: string;
    error?: string;
  }>;
  total?: number;
  success_count?: number;
  failed_count?: number;
  method?: string;
  period?: { start: string; end: string };
  universe_size?: number;
  error?: string;
}> {
  const url = `${V2_API_BASE}/api/analysis/factor-report`;

  const response = await fetchV2<{
    success: boolean;
    data?: {
      reports: Array<{
        factor: string;
        success: boolean;
        report_path?: string;
        reportPath?: string;
        file_size?: number;
        fileSize?: number;
        url?: string;
        error?: string;
      }>;
      total: number;
      success_count?: number;
      successCount?: number;
      failed_count?: number;
      failedCount?: number;
      method: string;
      period: { start: string; end: string };
      universe_size?: number;
      universeSize?: number;
    };
    error?: string;
  }>(url, {
    method: 'POST',
    body: {
      factors: params.factors,
      start_date: params.start_date!,
      end_date: params.end_date!,
      universe: params.universe,
      output_dir: params.output_dir,
    },
  });

  if (!response.success || !(response as any).data) {
    return { success:  false,
      error: response.error || '生成报告失败',
    };
  }

  // 转换响应（支持 camelCase 和 snake_case）
  const reports = (response as any).data.reports.map((r: any) => ({
    factor: r.factor,
    success: r.success,
    report_path: r.report_path || r.reportPath,
    file_size: r.file_size || r.fileSize,
    url: r.url,
    error: r.error,
  }));

  return { success:  true,
    reports,
    total: (response as any).data.total,
    success_count: (response as any).data.success_count || (response as any).data.successCount,
    failed_count: (response as any).data.failed_count || (response as any).data.failedCount,
    method: (response as any).data.method,
    period: (response as any).data.period,
    universe_size: (response as any).data.universe_size || (response as any).data.universeSize,
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
  if (!params.symbol! || params.symbol!.trim() === '') {
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
 * 获取K线历史数据（带自动验证、清洗和质量日志）
 * @param symbol 股票代码
 * @param period 周期 (daily/weekly/monthly)
 * @param startDate 开始日期 YYYYMMDD 或 YYYY-MM-DD
 * @param endDate 结束日期 YYYYMMDD 或 YYYY-MM-DD
 * @param limit 最大返回条数 (默认60)
 * @param options 可选配置
 */
export async function getKlineHistory(
  symbol: string,
  period: 'daily' | 'weekly' | 'monthly' = 'daily',
  startDate?: string,
  endDate?: string,
  limit: number = 60,
  options: {
    enableValidation?: boolean;    // 启用验证（默认true）
    enableCleaning?: boolean;       // 启用清洗（默认true）
    enableQualityLog?: boolean;     // 启用质量日志（默认true）
  } = {},
): Promise<KlineData> {
  const startTime = Date.now();

  // 默认启用所有质量控制功能
  const {
    enableValidation = true,
    enableCleaning = true,
    enableQualityLog = true,
  } = options;

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
    params.start_date! = convertDate(startDate, 'start_date');
  }

  if (endDate) {
    params.end_date! = convertDate(endDate, 'end_date');
  }

  const queryString = buildQueryString(params);
  const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/history${queryString ? '?' + queryString : ''}`;

  try {
    const response = await fetchV2<any>(url);

    // 后端返回格式: { data: { count: number, data: Array<...> } }
    // 需要解包嵌套结构
    const rawData = (response as any).data;
    const klineData: KlineData = {
      success: response.success ?? true,
      symbol,
      period,
      data: rawData?.data ?? [],
      count: rawData?.count ?? 0,
    };

    // 如果没有数据或请求失败，直接返回
    if (
      !klineData.success ||
      !(klineData as any).data ||
      (klineData as any).data.length === 0
    ) {
      return klineData;
    }

    // ─── 数据质量控制流程 ───

    const originalData = (klineData as any).data;
    const originalCount = originalData.length;

    // 1. 数据验证
    let validationResult;
    if (enableValidation) {
      const { validateKlineData } = await import('./kline-data-quality.js');
      validationResult = validateKlineData(originalData);
    } else {
      validationResult = {
        isValid: true,
        errors: [],
        warnings: [],
      };
    }

    // 2. 数据清洗
    let cleaningResult;
    if (enableCleaning && validationResult.errors.length > 0) {
      const { cleanKlineData } = await import('./kline-data-quality.js');
      cleaningResult = cleanKlineData(originalData, validationResult);

      // 使用清洗后的数据
      (klineData as any).data = cleaningResult.cleaned;
      klineData.count = cleaningResult.cleaned.length;

      // 在响应中添加清洗信息
      (klineData as any).quality = {
        original_count: originalCount,
        cleaned_count: cleaningResult.cleaned.length,
        removed: cleaningResult.removed,
        fixed: cleaningResult.fixed,
        has_issues: validationResult.errors.length > 0 || validationResult.warnings.length > 0,
      };
    } else {
      cleaningResult = {
        cleaned: originalData,
        removed: 0,
        fixed: 0,
        operations: [],
      };
    }

    // 3. 计算质量指标
    const { calculateQualityMetrics, getQualityGrade } = await import('./kline-data-quality.js');
    const metrics = calculateQualityMetrics(
      originalCount,
      validationResult,
      cleaningResult
    );

    // 4. 记录质量日志
    if (enableQualityLog) {
      const { logDataQuality } = await import('./kline-data-quality.js');
      const durationMs = Date.now() - startTime;

      logDataQuality({
        timestamp: new Date().toISOString(),
        symbol,
        period,
        requestedRange: {
          startDate: params.start_date! as string,
          endDate: params.end_date! as string,
          limit: params.limit as number,
        },
        validation: validationResult,
        cleaning: cleaningResult,
        metrics,
        durationMs,
      });
    }

    // 5. 在响应中添加质量信息（用于调试）
    if (validationResult.errors.length > 0 || validationResult.warnings.length > 0) {
      (klineData as any).quality = {
        ...(klineData as any).quality,
        grade: getQualityGrade(metrics.overall),
        score: Math.round(metrics.overall * 100),
        errors: validationResult.errors.length,
        warnings: validationResult.warnings.length,
        metrics: {
          completeness: Math.round(metrics.completeness * 100),
          consistency: Math.round(metrics.consistency * 100),
          accuracy: Math.round(metrics.accuracy * 100),
        },
      };
    }

    return klineData;
  } catch (error) {
    if (error instanceof QuantV2Error) {
      return { success:  false,
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
          // API wraps response as {success, data}, unwrap the data field
          result.price = (data as any).data || data;
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

// ── 策略写入（从 quant_cli 提取为独立工具） ─

/**
 * 创建新策略/指标
 */
export async function createIndicator(params: {
  name: string;
  code: string;
  description?: string;
  category?: string;
  params?: Record<string, unknown>;
}): Promise<{
  success: boolean;
  data?: {
    strategy_id: number;
    name: string;
    code_type: string;
    validation: {
      valid: boolean;
      error?: string;
      syntax_ok: boolean;
      has_buy_signal: boolean;
      has_sell_signal: boolean;
      params: Array<{ name: string; default: unknown; type: string }>;
      risk_config: Record<string, unknown>;
      metadata: Record<string, unknown>;
    };
  };
  message?: string;
  error?: string;
}> {
  if (!params.name || !params.code) {
    throw new QuantV2Error('name 和 code 不能为空', 400);
  }

  const url = `${V2_API_BASE}/api/indicators/create`;
  return fetchV2(url, { method: 'POST', body: params });
}

/**
 * 更新已有策略/指标
 */
export async function updateIndicator(
  indicatorId: number,
  params: {
    code?: string;
    name?: string;
    description?: string;
    category?: string;
    is_active?: boolean;
    is_public?: boolean;
    notebook?: Record<string, unknown>;
    strategy_profile?: Record<string, unknown>;
    params?: Record<string, unknown>;
  }
): Promise<{
  success: boolean;
  data?: Record<string, unknown>;
  message?: string;
  error?: string;
}> {
  const url = `${V2_API_BASE}/api/indicators/update/${indicatorId}`;
  return fetchV2(url, { method: 'POST', body: params });
}

// backtestIndicator 已移除 — 使用专用工具 indicator_backtest (通过 runQuantV2 调用)

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
 * ML训练是长耗时操作（数据拉取+特征工程+训练），使用 5 分钟超时
 */
const ML_TRAIN_TIMEOUT_MS = 300_000; // 5 minutes

export async function trainModel(params: {
  model_type?: string;
  start_date?: string;
  end_date?: string;
  test_size?: number;
  symbols?: string[];
  params?: Record<string, any>;
}): Promise<any> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ML_TRAIN_TIMEOUT_MS);
  try {
    return await fetchV2(`${V2_API_BASE}/api/ml/train`, {
      method: "POST",
      body: params,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }
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

  return (result as any).data;
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
        signals.push((item as any).data);
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

  return (result as any).data;
}

// ── Stock Pool Management ──

export interface PoolCreateParams {
  name: string;
  pool_type: "static" | "dynamic";
  symbols?: string[];
  filter_template?: Record<string, unknown>;
  refresh_interval?: "daily" | "weekly";
  description?: string;
}

export interface PoolValidateParams {
  strategy_ids?: number[];
  start_date?: string;
  end_date?: string;
}

export interface PoolScanCreateParams {
  name: string;
  pool_type: "static" | "dynamic";
  filter: Record<string, unknown>;
  refresh_interval?: "daily" | "weekly";
  description?: string;
}

export async function createPool(params: PoolCreateParams): Promise<any> {
  const url = `${V2_API_BASE}/api/pools`;
  return fetchV2(url, { method: "POST", body: params });
}

export async function listPools(): Promise<any> {
  const url = `${V2_API_BASE}/api/pools`;
  return fetchV2(url, { method: "GET" });
}

export async function getPool(poolId: number): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}`;
  return fetchV2(url, { method: "GET" });
}

export async function updatePool(
  poolId: number,
  data: Partial<PoolCreateParams>,
): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}`;
  return fetchV2(url, { method: "PUT", body: data });
}

export async function deletePool(poolId: number): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}`;
  return fetchV2(url, { method: "DELETE" });
}

export async function refreshPool(poolId: number): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}/refresh`;
  return fetchV2(url, { method: "POST" });
}

export async function validatePool(
  poolId: number,
  params?: PoolValidateParams,
): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}/validate`;
  return fetchV2(url, { method: "POST", body: params ?? {} });
}

export async function scanAndCreatePool(
  params: PoolScanCreateParams,
): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/scan-and-create`;
  return fetchV2(url, { method: "POST", body: params });
}

export interface PoolMemberUpdateParams {
  description?: string;
  buy_point?: string;
  sell_point?: string;
  tags?: string[];
}

export async function updatePoolMember(
  poolId: number,
  symbol: string,
  data: PoolMemberUpdateParams,
): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}/members/${symbol}`;
  return fetchV2(url, { method: "PUT", body: data });
}

export interface PoolSignalScanParams {
  strategy_id: number;
  lookback_days?: number;
  max_buy_signals?: number;
  max_sell_signals?: number;
}

export interface PoolSignalScanResult {
  strategy_id: number;
  strategy_name: string;
  total_symbols: number;
  buy_signals: Array<{
    symbol: string;
    signal: string;
    current_price: number;
    reasons: string[];
    indicators: Record<string, number>;
    trade_params: {
      stop_loss: number;
      take_profit: number;
      suggested_position: number;
    };
    trade_date: string;
  }>;
  sell_signals: Array<{
    symbol: string;
    signal: string;
    current_price: number;
    reasons: string[];
    indicators: Record<string, number>;
    trade_params: Record<string, any>;
    trade_date: string;
  }>;
  hold_signals: Array<{
    symbol: string;
    signal: string;
    current_price: number;
    reasons: string[];
    indicators: Record<string, number>;
    trade_params: Record<string, any>;
    trade_date: string;
  }>;
  errors: Array<{
    symbol: string;
    error: string;
  }>;
  scanned_at: string;
  summary: {
    buy: number;
    sell: number;
    hold: number;
    error: number;
  };
}

export async function scanPoolSignals(
  poolId: number,
  params: PoolSignalScanParams,
): Promise<{ success: boolean; data?: PoolSignalScanResult; error?: string }> {
  const url = `${V2_API_BASE}/api/pools/${poolId}/scan-signals`;
  return fetchV2(url, { method: "POST", body: params });
}

// ─── Combo Backtest ───────────────────────────────────────

export interface ComboBacktestRequest {
  mode: 'portfolio' | 'ensemble' | 'pipeline';
  strategies: Array<{
    strategy_id: number;
    weight?: number;
    signal_weight?: number;
    stage?: string;
  }>;
  symbols: string[];
  start_date?: string;
  end_date?: string;
  initial_capital?: number;
  ensemble_method?: 'weighted' | 'majority' | 'and' | 'or';
  pipeline_config?: {
    stages?: string[];
  };
}

export interface ComboBacktestResult {
  mode: string;
  period: { start: string; end: string };
  overall_metrics: {
    total_return: number;
    annual_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    profit_loss_ratio: number;
  };
  strategy_breakdown: Array<{
    strategy_id: number;
    strategy_name: string;
    weight?: number;
    signal_weight?: number;
    return: number;
    sharpe: number;
    contribution: number;
  }>;
  equity_curve: Array<{ date: string; value: number }>;
  ensemble_method?: string;
  pipeline_stats?: {
    initial_symbols: number;
    stages: Array<{
      stage: string;
      input_count?: number;
      output_count?: number;
      signals_generated?: number;
    }>;
  };
}

export async function comboBacktest(
  request: ComboBacktestRequest
): Promise<ComboBacktestResult> {
  const response = await fetch(`${V2_API_BASE}/api/backtest/combo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(V2_TIMEOUT_MS),
  });

  if (!response.ok) {
    const error: any = await response.json().catch(() => ({}));
    throw new Error(
      error.error || `HTTP ${response.status}: ${response.statusText}`
    );
  }

  const data: any = await response.json();
  if (!data.success) {
    throw new Error(data.error || 'Combo backtest failed');
  }

  return (data as any).data;
}

/**
 * 计算风险指标
 * @param params 风险指标参数
 */
export async function calculateRiskMetrics(
  params: RiskMetricsParams
): Promise<RiskMetrics> {
  if (!params.returns || params.returns.length === 0) {
    throw new QuantV2Error('收益率序列不能为空', 400);
  }

  const url = `${V2_API_BASE}/api/risk/metrics`;

  const response = await fetchV2<{
    success: boolean;
    data?: RiskMetrics;
    error?: string;
  }>(url, {
    method: 'POST',
    body: {
      returns: params.returns,
      benchmark_returns: params.benchmark_returns,
      risk_free_rate: params.risk_free_rate,
    },
  });

  if (!response.success || !(response as any).data) {
    throw new QuantV2Error(
      response.error || '风险指标计算失败',
      500
    );
  }

  return (response as any).data;
}


/**
 * 组合优化
 * @param params 组合优化参数
 */
export async function optimizePortfolio(
  params: PortfolioOptimizationParams
): Promise<PortfolioOptimizationResult> {
  if (!params.symbols || params.symbols.length === 0) {
    throw new QuantV2Error('股票列表不能为空', 400);
  }

  const url = `${V2_API_BASE}/api/portfolio/optimize`;

  const response = await fetchV2<{
    success: boolean;
    data?: PortfolioOptimizationResult;
    error?: string;
  }>(url, {
    method: 'POST',
    body: {
      symbols: params.symbols,
      expected_returns: params.expected_returns,
      cov_matrix: params.cov_matrix,
      method: params.method,
      risk_aversion: params.risk_aversion,
      risk_free_rate: params.risk_free_rate,
      constraints: params.constraints,
      start_date: params.start_date!,
      end_date: params.end_date!,
    },
  });

  if (!response.success || !(response as any).data) {
    throw new QuantV2Error(
      response.error || '组合优化失败',
      500
    );
  }

  return (response as any).data;
}

// ========================================
// 数据质量管理 API (2026-06-04)
// ========================================

/**
 * 检查数据质量
 */
export async function checkDataQuality(params: {
  symbols?: string[];
  start_date?: string;
  end_date?: string;
  include_report?: boolean;
}): Promise<{
  success: boolean;
  summary?: {
    total_stocks: number;
    stocks_with_issues: number;
    total_missing_days: number;
    avg_coverage_rate: number;
    data_quality_score: number;
  };
  stocks_with_issues?: Array<{
    symbol: string;
    missing_days_count: number;
    coverage_rate: number;
    quality_score: number;
    has_duplicates: boolean;
    duplicate_count: number;
    has_anomalies: boolean;
    anomaly_count: number;
  }>;
  report_url?: string;
  timestamp?: string;
  error?: string;
}> {
  const queryParams = new URLSearchParams();
  if (params.symbols) queryParams.append('symbols', params.symbols.join(','));
  if (params.start_date!) queryParams.append('start_date', params.start_date!);
  if (params.end_date!) queryParams.append('end_date', params.end_date!);
  if (params.include_report) queryParams.append('include_report', 'true');

  const url = `${V2_API_BASE}/api/data/check?${queryParams.toString()}`;

  const response = await fetchV2<any>(url, { method: 'GET' });
  return response;
}

/**
 * 检测缺失数据
 */
export async function detectMissingData(params: {
  symbols?: string[];
  start_date?: string;
  end_date?: string;
}): Promise<{
  success: boolean;
  summary?: {
    total_stocks: number;
    stocks_with_gaps: number;
    total_missing_days: number;
    avg_coverage_rate: number;
    worst_stocks: Array<{
      symbol: string;
      coverage_rate: number;
      missing_days: number;
    }>;
  };
  gaps?: Record<string, {
    symbol: string;
    total_trading_days: number;
    actual_days: number;
    missing_days_count: number;
    missing_days: string[];
    missing_segments: Array<{
      start: string;
      end: string;
      days: number;
    }>;
    coverage_rate: number;
  }>;
  timestamp?: string;
  error?: string;
}> {
  const url = `${V2_API_BASE}/api/data/detect-gaps`;

  const response = await fetchV2<any>(url, {
    method: 'POST',
    body: {
      symbols: params.symbols,
      start_date: params.start_date!,
      end_date: params.end_date!,
    },
  });

  return response;
}

/**
 * 补充缺失数据
 */
export async function backfillMissingData(params: {
  symbols?: string[];
  start_date?: string;
  end_date?: string;
  mode?: 'auto' | 'force';
  max_workers?: number;
}): Promise<{
  success: boolean;
  summary?: {
    total_stocks: number;
    success_count: number;
    failed_count: number;
    total_days_filled: number;
    elapsed_time: number;
  };
  failed_symbols?: string[];
  timestamp?: string;
  error?: string;
}> {
  const url = `${V2_API_BASE}/api/data/backfill`;

  const response = await fetchV2<any>(url, {
    method: 'POST',
    body: {
      symbols: params.symbols,
      start_date: params.start_date!,
      end_date: params.end_date!,
      mode: params.mode || 'auto',
      max_workers: params.max_workers || 8,
    },
  });

  return response;
}

/**
 * 验证数据质量
 */
export async function validateDataQuality(params: {
  symbols?: string[];
  start_date?: string;
  end_date?: string;
}): Promise<{
  success: boolean;
  summary?: {
    total_stocks: number;
    stocks_with_issues: number;
  };
  validation_results?: Array<{
    symbol: string;
    valid: boolean;
    total_records: number;
    invalid_records: number;
    validation_errors: Array<{
      index: number;
      date: string;
      symbol: string;
      errors: string[];
    }>;
    has_duplicates: boolean;
    duplicate_count: number;
    has_anomalies: boolean;
    anomaly_count: number;
  }>;
  timestamp?: string;
  error?: string;
}> {
  const url = `${V2_API_BASE}/api/data/validate`;

  const response = await fetchV2<any>(url, {
    method: 'POST',
    body: {
      symbols: params.symbols,
      start_date: params.start_date!,
      end_date: params.end_date!,
    },
  });

  return response;
}

/**
 * QuantV2Client - 统一的客户端对象，包装所有 API 函数
 */
export const QuantV2Client = {
  // 基础功能
  ping: pingV2,
  run: runQuantV2,

  // 通用 HTTP 方法
  get: async <T = any>(path: string, params?: Record<string, unknown>): Promise<T> => {
    const url = new URL(path, V2_API_BASE);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }
    return fetchV2<T>(url.toString(), { method: 'GET' });
  },

  post: async <T = any>(path: string, body?: unknown): Promise<T> => {
    const url = `${V2_API_BASE}${path}`;
    return fetchV2<T>(url, { method: 'POST', body });
  },

  // 数据获取
  getFinancials,
  getDividends,
  getKlineHistory,
  getStockData,

  // 因子相关
  computeFactors,
  analyzeFactors,
  generateFactorReport,

  // 投资机会
  scanOpportunities,

  // 策略相关
  batchValidateStrategies,

  // 指标相关
  createIndicator,
  updateIndicator,

  // 模型相关
  listModels,
  evaluateModel,
  monitorModel,
  trainModel,

  // 算法交易
  algoExecute,

  // 数据质量
  checkDataQuality,
  detectMissingData,
  backfillMissingData,
  validateDataQuality,
};

/**
 * 默认客户端实例（向后兼容）
 */
export const quantV2Client = QuantV2Client;
