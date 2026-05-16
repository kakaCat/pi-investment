/**
 * 弹性 Python 调用层 - 带超时优化和降级策略
 */
import { TS_FUNCTIONS } from "../../akshare-ts/index.js";
import { callPythonDaemon } from "../python-bridge.js";

// ===== 分级超时配置 =====
const TIMEOUT_FAST = 15000;      // 15秒 - 实时数据（从10秒提升到15秒，避免网络波动）
const TIMEOUT_MEDIUM = 35000;    // 35秒 - 技术指标（从30秒提升到35秒）
const TIMEOUT_SLOW = 55000;      // 55秒 - 宏观数据（从60秒降低到55秒，配合Python端50秒超时）

const TIMEOUT_CONFIG: Record<string, number> = {
  // 快速接口（10秒）
  get_stock_realtime_price: TIMEOUT_FAST,
  get_hk_stock_price: TIMEOUT_FAST,
  get_stock_news: TIMEOUT_FAST,
  get_market_overview: TIMEOUT_FAST,

  // 中速接口（30秒）
  get_north_flow: TIMEOUT_MEDIUM,
  get_sector_fund_flow: TIMEOUT_MEDIUM,
  get_stock_fund_flow: TIMEOUT_MEDIUM,
  get_market_margin: TIMEOUT_MEDIUM,
  calculate_technical_indicators: TIMEOUT_MEDIUM,
  calculate_buy_range: TIMEOUT_MEDIUM,
  analyze_candlestick: TIMEOUT_MEDIUM,
  get_lhb: TIMEOUT_MEDIUM,
  get_announcements: TIMEOUT_MEDIUM,

  // 港股接口
  get_hk_market_overview: TIMEOUT_FAST,
  get_hk_south_flow: TIMEOUT_MEDIUM,
  get_hk_technical: TIMEOUT_MEDIUM,
  get_hk_hot_rank: TIMEOUT_MEDIUM,

  // 慢速接口（60秒）- 已知慢的接口
  get_macro_data: TIMEOUT_SLOW,
  get_financial_indicators: TIMEOUT_SLOW,
  get_financial_statements: TIMEOUT_SLOW,
  test_market_sentiment: TIMEOUT_SLOW,
  get_market_news: TIMEOUT_SLOW,
};

// ===== 缓存配置 =====
const TTL_REALTIME = 5 * 60 * 1000;
const TTL_TECHNICAL = 10 * 60 * 1000;
const TTL_DAILY = 24 * 60 * 60 * 1000;

const TTL: Record<string, number> = {
  get_stock_realtime_price: TTL_REALTIME,
  get_hk_stock_price: TTL_REALTIME,
  get_market_overview: TTL_REALTIME,
  get_stock_news: TTL_REALTIME,
  get_north_flow: TTL_TECHNICAL,
  get_sector_fund_flow: TTL_TECHNICAL,
  get_stock_fund_flow: TTL_TECHNICAL,
  get_market_margin: TTL_TECHNICAL,
  calculate_technical_indicators: TTL_TECHNICAL,
  calculate_buy_range: TTL_TECHNICAL,
  analyze_candlestick: TTL_TECHNICAL,
  get_lhb: 30 * 60 * 1000,
  get_announcements: 30 * 60 * 1000,
  get_stock_info: TTL_DAILY,
  get_hk_stock_info: TTL_DAILY,
  get_financial_indicators: TTL_DAILY,
  get_stock_valuation: TTL_DAILY,
  get_pe_percentile: TTL_DAILY,
  get_financial_statements: TTL_DAILY,
  get_insider_trades: TTL_DAILY,
  get_fund_holdings: TTL_DAILY,
  get_top_holders: TTL_DAILY,
  get_holder_changes: TTL_DAILY,
  get_margin_data: TTL_DAILY,
  get_top_fund_stocks: TTL_DAILY,
  get_macro_data: TTL_DAILY,
  get_sector_list: TTL_DAILY,
  get_hk_hot_rank: TTL_TECHNICAL,
  get_hk_south_flow: TTL_TECHNICAL,
  get_hk_market_overview: TTL_REALTIME,
  get_concept_stocks: TTL_DAILY,
  get_concept_list: TTL_DAILY,
  screen_stocks_by_sector: TTL_DAILY,
  get_lhb_stock_stat: TTL_DAILY,
};
const DEFAULT_TTL = TTL_TECHNICAL;
const DEFAULT_TIMEOUT = TIMEOUT_MEDIUM;

// ===== 备选方案映射 =====
const ALTERNATIVES: Record<string, string[]> = {
  // 实时行情备选
  get_stock_realtime_price: [
    "使用 get_stock_info 获取基本信息（不含实时价格）",
    "使用 get_stock_history 获取最近的历史数据",
    "如果是港股，尝试 get_hk_stock_price"
  ],
  get_hk_stock_price: [
    "使用 get_hk_stock_info 获取基本信息",
    "使用 get_hk_stock_history 获取历史数据"
  ],

  // 资金流向备选
  get_north_flow: [
    "使用 get_market_margin 查看融资融券数据作为资金流向参考",
    "使用 get_sector_fund_flow 查看板块资金流向",
    "等待数据源恢复后重试"
  ],
  get_sector_fund_flow: [
    "使用 get_north_flow 查看北向资金流向",
    "使用 get_stock_fund_flow 查看个股资金流向",
    "等待数据源恢复后重试"
  ],
  get_stock_fund_flow: [
    "使用 get_sector_fund_flow 查看所属板块资金流向",
    "使用 calculate_technical_indicators 分析成交量变化",
    "等待数据源恢复后重试"
  ],

  // 市场情绪备选
  test_market_sentiment: [
    "分别调用 get_north_flow（北向资金）和 get_market_margin（融资融券）",
    "使用 get_lhb 查看龙虎榜数据判断市场热度",
    "使用 get_market_overview 查看大盘走势"
  ],
  get_market_news: [
    "使用 get_stock_news 获取个股新闻",
    "使用 get_announcements 获取公司公告",
    "等待数据源恢复后重试"
  ],

  // 宏观数据备选
  get_macro_data: [
    "如果只需要部分指标，可以跳过宏观数据分析",
    "使用历史经验和市场常识进行定性分析",
    "等待数据源恢复后重试（该接口响应较慢，通常需要 60 秒）"
  ],

  // 龙虎榜备选
  get_lhb: [
    "使用 get_lhb_stock_stat 查看个股龙虎榜统计",
    "使用 get_stock_fund_flow 查看资金流向",
    "等待数据源恢复后重试"
  ],

  // 财务数据备选
  get_financial_indicators: [
    "使用 get_stock_info 获取基本估值指标（PE/PB）",
    "使用 get_financial_statements 获取财务报表原始数据",
    "等待数据源恢复后重试"
  ],
  get_financial_statements: [
    "使用 get_financial_indicators 获取关键财务指标",
    "等待数据源恢复后重试"
  ],

  // 技术分析备选
  calculate_technical_indicators: [
    "使用 get_stock_history 获取历史数据后手动计算",
    "使用 analyze_candlestick 进行K线形态分析",
    "等待数据源恢复后重试"
  ],
  calculate_buy_range: [
    "使用 calculate_technical_indicators 获取技术指标后手动判断",
    "使用 get_stock_valuation 进行估值分析",
    "等待数据源恢复后重试"
  ],

  // 历史数据备选
  get_stock_history: [
    "如果是港股，使用 get_hk_stock_history",
    "使用 get_stock_realtime_price 获取当前价格",
    "等待数据源恢复后重试"
  ],
  get_hk_stock_history: [
    "使用 get_hk_stock_price 获取当前价格",
    "等待数据源恢复后重试"
  ]
};

/**
 * 获取备选方案
 */
function getAlternatives(func: string): string[] {
  return ALTERNATIVES[func] || [
    "等待数据源恢复后重试",
    "使用其他相关工具获取类似数据",
    "如果不是关键数据，可以跳过该步骤继续分析"
  ];
}

interface CacheEntry {
  data: string;
  expiry: number;
  timestamp: number; // 记录缓存时间，用于降级时显示
}

const cache = new Map<string, CacheEntry>();

// ===== 降级缓存（长期缓存，用于数据源失败时） =====
const fallbackCache = new Map<string, CacheEntry>();

/**
 * 带超时控制的 Python 调用
 */
async function callPythonWithTimeout(
  func: string,
  args: Record<string, unknown>,
  timeoutMs: number
): Promise<string> {
  return Promise.race([
    callPythonDaemon(func, args),
    new Promise<string>((_, reject) =>
      setTimeout(() => reject(new Error(`Timeout after ${timeoutMs}ms`)), timeoutMs)
    )
  ]);
}

/**
 * 判断错误是否可重试
 */
function isRetriableError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;

  const message = error.message.toLowerCase();

  // 可重试的错误类型
  const retriablePatterns = [
    'timeout',           // 超时错误
    'econnrefused',      // 连接被拒绝
    'econnreset',        // 连接重置
    'etimedout',         // 网络超时
    'enetunreach',       // 网络不可达
    'socket hang up',    // Socket 挂起
    'network',           // 通用网络错误
    'temporary',         // 临时错误
  ];

  return retriablePatterns.some(pattern => message.includes(pattern));
}

/**
 * 带重试机制的 Python 调用
 */
async function callPythonWithRetry(
  func: string,
  args: Record<string, unknown>,
  timeoutMs: number,
  maxRetries: number = 2
): Promise<string> {
  let lastError: unknown;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      if (attempt > 0) {
        // 指数退避：1秒、2秒、4秒...
        const delayMs = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
        console.log(`[python-resilient] ${func} retry ${attempt}/${maxRetries} after ${delayMs}ms`);
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }

      return await callPythonWithTimeout(func, args, timeoutMs);
    } catch (error) {
      lastError = error;

      // 如果不是可重试的错误，直接抛出
      if (!isRetriableError(error)) {
        throw error;
      }

      // 如果是最后一次尝试，抛出错误
      if (attempt === maxRetries) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        throw new Error(`${errorMsg} (failed after ${maxRetries + 1} attempts)`);
      }

      // 记录重试日志
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.warn(`[python-resilient] ${func} attempt ${attempt + 1} failed: ${errorMsg}`);
    }
  }

  throw lastError;
}

/**
 * 弹性 Python 调用 - 带超时优化和降级策略
 */
export async function callPythonResilient(
  func: string,
  args: Record<string, unknown> = {}
): Promise<string> {
  const cacheKey = `${func}:${JSON.stringify(args, Object.keys(args).sort())}`;

  // 1. 检查新鲜缓存
  const cached = cache.get(cacheKey);
  if (cached && cached.expiry > Date.now()) {
    return cached.data;
  }

  // 2. 尝试 TypeScript 原生实现
  const tsFn = TS_FUNCTIONS[func];
  if (tsFn) {
    try {
      const result = await tsFn(args);
      const shouldCache = !isErrorResult(result);
      if (shouldCache) {
        const ttl = TTL[func] ?? DEFAULT_TTL;
        const entry = { data: result, expiry: Date.now() + ttl, timestamp: Date.now() };
        cache.set(cacheKey, entry);
        // 同时更新降级缓存
        fallbackCache.set(cacheKey, { ...entry, expiry: Date.now() + 7 * 24 * 60 * 60 * 1000 }); // 7天
      }
      return result;
    } catch (e) {
      const tsErr = e instanceof Error ? e.message : String(e);
      console.warn(`[akshare-ts] ${func} failed (${tsErr}), trying Python...`);
      (args as any).__ts_fallback = tsErr;
    }
  }

  // 3. 尝试 Python 调用（带超时控制）
  const timeout = TIMEOUT_CONFIG[func] ?? DEFAULT_TIMEOUT;
  const tsFallbackErr = (args as any).__ts_fallback as string | undefined;

  if (tsFallbackErr) {
    const { __ts_fallback: _, ...cleanArgs } = args as any;
    args = cleanArgs;
  }

  try {
    const result = await callPythonWithRetry(func, args, timeout);

    // 标注降级信息
    let finalResult = result;
    if (tsFallbackErr) {
      try {
        const parsed = JSON.parse(result);
        finalResult = JSON.stringify({ ...parsed, _via_python_fallback: true });
      } catch {
        // 非 JSON 结果，保持原样
      }
    }

    // 缓存成功结果
    const shouldCache = !isErrorResult(finalResult);
    if (shouldCache) {
      const ttl = TTL[func] ?? DEFAULT_TTL;
      const entry = { data: finalResult, expiry: Date.now() + ttl, timestamp: Date.now() };
      cache.set(cacheKey, entry);
      // 同时更新降级缓存（7天有效期）
      fallbackCache.set(cacheKey, { ...entry, expiry: Date.now() + 7 * 24 * 60 * 60 * 1000 });
    }

    return finalResult;
  } catch (error: unknown) {
    // 4. Python 调用失败 - 尝试使用降级缓存
    const fallback = fallbackCache.get(cacheKey);
    if (fallback) {
      const ageMinutes = Math.floor((Date.now() - fallback.timestamp) / 60000);
      console.warn(`[python-resilient] ${func} failed, using fallback cache (${ageMinutes}min old)`);

      try {
        const parsed = JSON.parse(fallback.data);
        return JSON.stringify({
          ...parsed,
          _from_fallback_cache: true,
          _cache_age_minutes: ageMinutes,
          _warning: `数据源暂时不可用，使用 ${ageMinutes} 分钟前的缓存数据`,
          _alternatives: getAlternatives(func)
        });
      } catch {
        return fallback.data;
      }
    }

    // 5. 完全失败 - 返回错误（包含备选方案）
    const errorMsg = error instanceof Error ? error.message : String(error);
    const alternatives = getAlternatives(func);

    return JSON.stringify({
      error: `数据获取失败: ${errorMsg}`,
      ts_error: tsFallbackErr || undefined,
      _no_operation_performed: true,
      _suggestion: "数据源可能暂时不可用，请稍后重试",
      _alternatives: alternatives
    });
  }
}

/**
 * 判断结果是否为错误
 */
function isErrorResult(result: string): boolean {
  try {
    const parsed = JSON.parse(result);
    return !!parsed.error;
  } catch {
    return false;
  }
}

/**
 * 清除所有缓存（用于测试或强制刷新）
 */
export function clearAllCaches(): void {
  cache.clear();
  fallbackCache.clear();
}

/**
 * 获取缓存统计信息
 */
export function getCacheStats() {
  return {
    cache_size: cache.size,
    fallback_cache_size: fallbackCache.size,
    cache_keys: Array.from(cache.keys()),
    fallback_keys: Array.from(fallbackCache.keys())
  };
}
