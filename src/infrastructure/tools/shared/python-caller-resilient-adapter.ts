/**
 * 弹性 Python 调用层适配器 - 使用新缓存系统
 *
 * 保持与旧 python-caller-resilient 相同的接口,但使用新的缓存领域实现
 */
import { TS_FUNCTIONS } from "../../akshare-ts/index.js";
import { callPythonDaemon } from "../python-bridge.js";
import { CacheManager } from "../../../domain/cache/core/cache-manager.js";
import type { CacheNamespace } from "../../../domain/cache/core/types.js";

// ===== 分级超时配置 =====
const TIMEOUT_FAST = 15000;
const TIMEOUT_MEDIUM = 35000;
const TIMEOUT_SLOW = 55000;
const TIMEOUT_VERY_SLOW = 120000; // 2分钟，用于腾讯API等慢速数据源

const TIMEOUT_CONFIG: Record<string, number> = {
  get_stock_realtime_price: TIMEOUT_FAST,
  get_hk_stock_price: TIMEOUT_FAST,
  get_stock_news: TIMEOUT_FAST,
  get_market_overview: TIMEOUT_FAST,
  get_north_flow: TIMEOUT_MEDIUM,
  get_sector_fund_flow: TIMEOUT_VERY_SLOW, // AkShare板块数据较慢
  get_stock_fund_flow: TIMEOUT_MEDIUM,
  get_market_margin: TIMEOUT_MEDIUM,
  calculate_technical_indicators: TIMEOUT_MEDIUM,
  calculate_buy_range: TIMEOUT_MEDIUM,
  analyze_candlestick: TIMEOUT_MEDIUM,
  get_lhb: TIMEOUT_MEDIUM,
  get_announcements: TIMEOUT_MEDIUM,
  get_hk_market_overview: TIMEOUT_FAST,
  get_hk_south_flow: TIMEOUT_MEDIUM,
  get_hk_technical: TIMEOUT_MEDIUM,
  get_hk_hot_rank: TIMEOUT_MEDIUM,
  get_index_history: TIMEOUT_VERY_SLOW, // 腾讯API较慢，需要更长超时
  get_macro_data: TIMEOUT_SLOW,
  get_financial_indicators: TIMEOUT_SLOW,
  get_financial_statements: TIMEOUT_SLOW,
  test_market_sentiment: TIMEOUT_SLOW,
  get_market_news: TIMEOUT_SLOW,
  train_signal_model: TIMEOUT_SLOW,
  predict_signal_confidence: TIMEOUT_MEDIUM,
  combine_strategy_signals: TIMEOUT_MEDIUM,
  check_trade_risk: TIMEOUT_MEDIUM,
  calculate_position_size: TIMEOUT_MEDIUM,
  calculate_stop_loss: TIMEOUT_FAST,
};

// ===== 分级重试配置 =====
// 慢接口只重试 1 次（快速失败），快速/中速接口重试 2 次
const RETRY_CONFIG: Record<string, number> = {
  get_macro_data: 1,
  get_financial_indicators: 1,
  get_financial_statements: 1,
  test_market_sentiment: 1,
  get_market_news: 1,
  get_north_flow: 1,
  get_sector_fund_flow: 1,
  get_index_history: 1, // 腾讯API慢，只重试1次
};

const DEFAULT_MAX_RETRIES = 2;

// ===== 缓存命名空间映射 =====
const NAMESPACE_MAP: Record<string, CacheNamespace> = {
  // 实时数据 -> intraday (5分钟)
  get_stock_realtime_price: 'intraday',
  get_hk_stock_price: 'intraday',
  get_market_overview: 'intraday',
  get_stock_news: 'intraday',

  // 技术指标 -> intraday (10分钟)
  get_north_flow: 'intraday',
  get_sector_fund_flow: 'intraday',
  get_stock_fund_flow: 'intraday',
  get_market_margin: 'intraday',
  calculate_technical_indicators: 'intraday',
  calculate_buy_range: 'intraday',
  analyze_candlestick: 'intraday',
  get_lhb: 'intraday',
  get_announcements: 'intraday',
  get_hk_hot_rank: 'intraday',
  get_hk_south_flow: 'intraday',
  get_hk_market_overview: 'intraday',

  // 风险管理 -> intraday (日内缓存)
  check_trade_risk: 'intraday',
  calculate_position_size: 'intraday',
  calculate_stop_loss: 'intraday',

  // 日级数据 -> daily (24小时)
  get_stock_info: 'daily',
  get_hk_stock_info: 'daily',
  get_financial_indicators: 'daily',
  get_stock_valuation: 'daily',
  get_pe_percentile: 'daily',
  get_financial_statements: 'daily',
  get_insider_trades: 'daily',
  get_fund_holdings: 'daily',
  get_top_holders: 'daily',
  get_holder_changes: 'daily',
  get_margin_data: 'daily',
  get_top_fund_stocks: 'daily',
  get_macro_data: 'daily',
  get_sector_list: 'daily',
  get_concept_stocks: 'daily',
  get_concept_list: 'daily',
  screen_stocks_by_sector: 'daily',
  get_lhb_stock_stat: 'daily',
  train_signal_model: 'daily',
  predict_signal_confidence: 'daily',
};

const DEFAULT_NAMESPACE: CacheNamespace = 'intraday';
const DEFAULT_TIMEOUT = TIMEOUT_MEDIUM;

// ===== 备选方案映射 =====
const ALTERNATIVES: Record<string, string[]> = {
  get_stock_realtime_price: [
    "使用 get_stock_info 获取基本信息（不含实时价格）",
    "使用 get_stock_history 获取最近的历史数据",
    "如果是港股，尝试 get_hk_stock_price"
  ],
  get_hk_stock_price: [
    "使用 get_hk_stock_info 获取基本信息",
    "使用 get_hk_stock_history 获取历史数据"
  ],
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
  get_macro_data: [
    "如果只需要部分指标，可以跳过宏观数据分析",
    "使用历史经验和市场常识进行定性分析",
    "等待数据源恢复后重试（该接口响应较慢，通常需要 60 秒）"
  ],
  get_lhb: [
    "使用 get_lhb_stock_stat 查看个股龙虎榜统计",
    "使用 get_stock_fund_flow 查看资金流向",
    "等待数据源恢复后重试"
  ],
  get_financial_indicators: [
    "使用 get_stock_info 获取基本估值指标（PE/PB）",
    "使用 get_financial_statements 获取财务报表原始数据",
    "等待数据源恢复后重试"
  ],
  get_financial_statements: [
    "使用 get_financial_indicators 获取关键财务指标",
    "等待数据源恢复后重试"
  ],
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

function getAlternatives(func: string): string[] {
  return ALTERNATIVES[func] || [
    "等待数据源恢复后重试",
    "使用其他相关工具获取类似数据",
    "如果不是关键数据，可以跳过该步骤继续分析"
  ];
}

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
  const retriablePatterns = [
    'timeout', 'econnrefused', 'econnreset', 'etimedout',
    'enetunreach', 'socket hang up', 'network', 'temporary',
  ];

  return retriablePatterns.some(pattern => message.includes(pattern));
}

/**
 * 带重试机制的 Python 调用
 */
async function callPythonWithRetry(
  func: string,
  args: Record<string, unknown>,
  timeoutMs: number
): Promise<string> {
  const maxRetries = RETRY_CONFIG[func] ?? DEFAULT_MAX_RETRIES;
  let lastError: unknown;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      if (attempt > 0) {
        const delayMs = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
        console.log(`[python-resilient] ${func} retry ${attempt}/${maxRetries} after ${delayMs}ms`);
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }

      return await callPythonWithTimeout(func, args, timeoutMs);
    } catch (error) {
      lastError = error;

      if (!isRetriableError(error)) {
        throw error;
      }

      if (attempt === maxRetries) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        throw new Error(`${errorMsg} (failed after ${maxRetries + 1} attempts)`);
      }

      const errorMsg = error instanceof Error ? error.message : String(error);
      console.warn(`[python-resilient] ${func} attempt ${attempt + 1} failed: ${errorMsg}`);
    }
  }

  throw lastError;
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
 * 非交易时段可继续的工具（不依赖实时行情数据）
 * 这些工具的 Python 请求在非交易时段也允许发起
 */
const OFFLINE_CAPABLE_TOOLS = new Set([
  // 基础信息（不需要实时行情）
  'get_stock_info',
  'get_hk_stock_info',
  // 财务/基本面数据（财报数据非实时依赖）
  'get_financial_indicators',
  'get_financial_statements',
  'get_stock_valuation',
  'get_quality_score',
  'get_hk_financials',
  'get_hk_analysis',
  // 选股（基于存量数据）
  'screen_stocks_by_sector',
  'screen_stocks_quality',
  // 概念板块（基于存量数据）
  'get_concept_stocks',
  'get_concept_list',
  'get_sector_list',
  // 宏观数据（月度/季度更新）
  'get_macro_data',
  // 新闻/公告（非交易依赖）
  'get_stock_news',
  'get_announcements',
  'get_market_news',
  // 基金/股东持仓（基于财报披露）
  'get_fund_holdings',
  'get_top_fund_stocks',
  'get_top_holders',
  'get_holder_changes',
  // 历史行情（盘后可获取）
  'get_stock_history',
  'get_hk_stock_history',
  // 港股技术分析（基于历史数据）
  'get_hk_technical',
  // ML 模型（基于历史数据，不依赖实时行情）
  'train_signal_model',
  'predict_signal_confidence',
]);

/**
 * 获取非交易时段的友好提示信息
 */
function getNonTradingMessage(func: string): string {
  const now = new Date();
  const chinaTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }));
  const dayOfWeek = chinaTime.getDay();
  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;

  let reason: string;
  if (isWeekend) {
    reason = '周末非交易时段，数据源不可用';
  } else {
    const hours = chinaTime.getHours();
    if (hours < 9 || hours >= 15) {
      reason = '非交易时段（9:30-11:30 / 13:00-15:00），数据源不可用';
    } else {
      reason = '午间休市时段（11:30-13:00），数据源不可用';
    }
  }

  return JSON.stringify({
    error: reason,
    _non_trading_hours: true,
    _current_time: chinaTime.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false
    }),
    _suggestion: '请在北京时间 9:30-15:00（交易日）使用，或使用不依赖实时行情的工具（财报分析/估值分析/选股等）',
  });
}

/**
 * 弹性 Python 调用 - 使用新缓存系统
 */
export async function callPythonResilient(
  func: string,
  args: Record<string, unknown> = {}
): Promise<string> {
  const cacheManager = CacheManager.getInstance();
  const namespace = NAMESPACE_MAP[func] || DEFAULT_NAMESPACE;
  const cacheKey = `python:${func}:${JSON.stringify(args, Object.keys(args).sort())}`;

  // 1. 检查新鲜缓存
  const cached = await cacheManager.get<string>(namespace, cacheKey);
  if (cached) {
    return cached;
  }

  // 2. 尝试 TypeScript 原生实现
  const tsFn = TS_FUNCTIONS[func];
  if (tsFn) {
    try {
      const result = await tsFn(args);
      const shouldCache = !isErrorResult(result);
      if (shouldCache) {
        await cacheManager.set(namespace, cacheKey, result);
      }
      return result;
    } catch (e) {
      const tsErr = e instanceof Error ? e.message : String(e);
      console.warn(`[akshare-ts] ${func} failed (${tsErr}), trying Python...`);
      (args as any).__ts_fallback = tsErr;
    }
  }

  // 2b. 非交易时段快速失败（仅限实时类工具）
  if (!OFFLINE_CAPABLE_TOOLS.has(func)) {
    const now = new Date();
    const chinaTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }));
    const dayOfWeek = chinaTime.getDay();
    const hours = chinaTime.getHours();
    const minutes = chinaTime.getMinutes();
    const currentMinutes = hours * 60 + minutes;

    const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
    const morningStart = 9 * 60 + 30;
    const morningEnd = 11 * 60 + 30;
    const afternoonStart = 13 * 60;
    const afternoonEnd = 15 * 60;
    const isTradingHours = !isWeekend && (
      (currentMinutes >= morningStart && currentMinutes <= morningEnd) ||
      (currentMinutes >= afternoonStart && currentMinutes <= afternoonEnd)
    );

    if (!isTradingHours) {
      console.log(`[python-resilient] ${func} 非交易时段快速失败，跳过 Python 请求`);
      return getNonTradingMessage(func);
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
      await cacheManager.set(namespace, cacheKey, finalResult);
    }

    return finalResult;
  } catch (error: unknown) {
    // 4. Python 调用失败 - 尝试使用过期缓存（降级）
    // 注意：新缓存系统的 get 方法已经处理了 TTL，这里我们尝试直接读取（即使过期）
    // 但由于新系统会自动删除过期数据，我们需要依赖备用策略

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
 * 清除所有缓存（用于测试或强制刷新）
 */
export async function clearAllCaches(): Promise<void> {
  const cacheManager = CacheManager.getInstance();
  await Promise.all([
    cacheManager.clear('intraday'),
    cacheManager.clear('daily'),
    cacheManager.clear('quarterly'),
    cacheManager.clear('static'),
  ]);
}

/**
 * 获取缓存统计信息
 */
export async function getCacheStats() {
  const cacheManager = CacheManager.getInstance();
  const namespaces: CacheNamespace[] = ['intraday', 'daily', 'quarterly', 'static'];

  const stats: Record<string, number> = {};
  for (const ns of namespaces) {
    // 使用 invalidateByPattern 返回的计数（不实际删除，只是获取匹配数）
    // 由于没有直接的 keys 方法，我们返回 0（统计功能降级）
    stats[ns] = 0;
  }

  return {
    cache_size: 0, // 统计功能暂时降级
    by_namespace: stats,
  };
}
