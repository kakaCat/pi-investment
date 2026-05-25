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
  OpportunityScanParams,
  Opportunity,
  AlgoExecuteParams,
  AlgoOrder,
  QuantV2Error as QuantV2ErrorType,
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
  { path: string; method: "GET" | "POST" }
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
  "backtest.run":     { path: "/api/backtest/run",     method: "POST" },
  "backtest.results": { path: "/api/backtest/results", method: "GET" },

  // ── strategy ──
  "strategy.list":   { path: "/api/strategies/list",           method: "GET" },
  "strategy.get":    { path: "/api/strategies/detail/{strategy_id}", method: "GET" },
  "strategy.create": { path: "/api/strategies/create",        method: "POST" },

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
  "indicators.list": { path: "/api/indicators/list", method: "GET" },
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
    throw new Error(`QUANT_V2_NO_ROUTE: 命令 ${command} 没有 v2 端点映射`);
  }

  const { url, body } = buildRequest(route, params);

  const response = await fetch(url, {
    method: route.method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal: opts.signal ?? AbortSignal.timeout(V2_TIMEOUT_MS),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(
      `QUANT_V2_HTTP_${response.status}: ${text || response.statusText}`,
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
}

// ─── 内部辅助 ────────────────────────────────────────────

function buildRequest(
  route: { path: string; method: "GET" | "POST" },
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
    if (pathParams.has(k) && typeof v === "string") {
      path = path.replace(`{${k}}`, encodeURIComponent(v));
    } else if (v !== undefined && v !== null) {
      remaining[k] = v;
    }
  }

  if (route.method === "GET") {
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
  try {
    const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/financials?type=${statementType}&periods=${periods}`;
    const response = await fetch(url, {
      signal: AbortSignal.timeout(V2_TIMEOUT_MS),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new QuantV2Error(
        `获取财务数据失败: ${text || response.statusText}`,
        response.status,
        url,
      );
    }

    const data = await response.json() as FinancialData;
    return data;
  } catch (error) {
    if (error instanceof QuantV2Error) throw error;
    throw new QuantV2Error(
      `获取财务数据异常: ${error instanceof Error ? error.message : String(error)}`,
      undefined,
      `/api/stock/${symbol}/financials`,
    );
  }
}

/**
 * 批量计算因子
 * @param params 因子计算参数
 */
export async function computeFactors(
  params: FactorComputeParams,
): Promise<FactorResult> {
  try {
    const url = `${V2_API_BASE}/api/compute/factors`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal: AbortSignal.timeout(V2_TIMEOUT_MS),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new QuantV2Error(
        `计算因子失败: ${text || response.statusText}`,
        response.status,
        url,
      );
    }

    const data = await response.json() as FactorResult;
    return data;
  } catch (error) {
    if (error instanceof QuantV2Error) throw error;
    throw new QuantV2Error(
      `计算因子异常: ${error instanceof Error ? error.message : String(error)}`,
      undefined,
      '/api/compute/factors',
    );
  }
}

/**
 * 因子分析
 * @param params 因子分析参数
 */
export async function analyzeFactors(
  params: FactorAnalyzeParams,
): Promise<FactorAnalysis> {
  try {
    const url = `${V2_API_BASE}/api/portfolio/factor-analyze`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal: AbortSignal.timeout(V2_TIMEOUT_MS),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new QuantV2Error(
        `因子分析失败: ${text || response.statusText}`,
        response.status,
        url,
      );
    }

    const data = await response.json() as FactorAnalysis;
    return data;
  } catch (error) {
    if (error instanceof QuantV2Error) throw error;
    throw new QuantV2Error(
      `因子分析异常: ${error instanceof Error ? error.message : String(error)}`,
      undefined,
      '/api/portfolio/factor-analyze',
    );
  }
}

/**
 * 扫描投资机会
 * @param params 扫描参数
 */
export async function scanOpportunities(
  params: OpportunityScanParams = {},
): Promise<Opportunity[]> {
  try {
    const url = `${V2_API_BASE}/api/signals/scan`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal: AbortSignal.timeout(V2_TIMEOUT_MS),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new QuantV2Error(
        `扫描机会失败: ${text || response.statusText}`,
        response.status,
        url,
      );
    }

    const result = await response.json() as { success: boolean; opportunities: Opportunity[] };
    return result.opportunities || [];
  } catch (error) {
    if (error instanceof QuantV2Error) throw error;
    throw new QuantV2Error(
      `扫描机会异常: ${error instanceof Error ? error.message : String(error)}`,
      undefined,
      '/api/signals/scan',
    );
  }
}

/**
 * 执行算法交易订单
 * @param params 算法交易参数
 */
export async function algoExecute(
  params: AlgoExecuteParams,
): Promise<AlgoOrder> {
  try {
    const url = `${V2_API_BASE}/api/algo/execute`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal: AbortSignal.timeout(V2_TIMEOUT_MS),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new QuantV2Error(
        `执行算法订单失败: ${text || response.statusText}`,
        response.status,
        url,
      );
    }

    const data = await response.json() as AlgoOrder;
    return data;
  } catch (error) {
    if (error instanceof QuantV2Error) throw error;
    throw new QuantV2Error(
      `执行算法订单异常: ${error instanceof Error ? error.message : String(error)}`,
      undefined,
      '/api/algo/execute',
    );
  }
}
