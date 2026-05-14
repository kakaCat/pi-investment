/**
 * AkShare-TS — TypeScript-native market data
 *
 * Unified export layer for all akshare-ts modules
 */

// Re-export data layer
export {
  get_stock_realtime_price,
  get_stock_history,
  get_stock_info,
  get_market_overview,
  get_sector_list,
  get_hk_stock_price,
  get_hk_stock_info,
  get_hk_stock_history,
  cleanSymbol,
} from './data/market.js';

export {
  get_quality_score,
  get_stock_valuation,
  get_pe_percentile,
  get_stock_fund_flow,
  get_holder_changes,
} from './data/financial.js';

// Re-export indicators layer
export {
  calculate_technical_indicators,
} from './indicators/technical.js';

export {
  analyze_candlestick,
} from './indicators/chart-patterns.js';

// Re-export services layer
export {
  calculate_buy_range,
} from './services/buy-range.js';

export {
  analyze_price_action,
} from './services/price-action.js';

export {
  get_exit_plan,
} from './services/exit-plan.js';

export {
  compare_peers,
} from './services/peer-comparison.js';

// Re-export portfolio
export {
  manage_portfolio,
} from './portfolio.js';

// Re-export shared utilities
export {
  callPython,
  getQualityRating,
} from './shared.js';

// Function registry for tool routing
import type { TsFn } from './shared.js';
import {
  get_stock_realtime_price,
  get_stock_history,
  get_stock_info,
  get_market_overview,
  get_sector_list,
  get_hk_stock_price,
  get_hk_stock_info,
  get_hk_stock_history,
} from './data/market.js';
import {
  get_quality_score,
  get_stock_valuation,
  get_pe_percentile,
  get_stock_fund_flow,
  get_holder_changes,
} from './data/financial.js';
import { calculate_technical_indicators } from './indicators/technical.js';
import { analyze_candlestick } from './indicators/chart-patterns.js';
import { calculate_buy_range } from './services/buy-range.js';
import { analyze_price_action } from './services/price-action.js';
import { get_exit_plan } from './services/exit-plan.js';
import { compare_peers } from './services/peer-comparison.js';
import { manage_portfolio } from './portfolio.js';

export const TS_FUNCTIONS: Record<string, TsFn> = {
  get_stock_realtime_price: (a) => get_stock_realtime_price(a.symbol as string),
  get_stock_history: (a) => get_stock_history(
    a.symbol as string,
    a.period as string | undefined,
    a.start_date as string | undefined,
    a.end_date as string | undefined,
    undefined,
    a._skip_cache as boolean | undefined
  ),
  get_stock_info: (a) => get_stock_info(a.symbol as string),
  get_market_overview: () => get_market_overview(),
  get_sector_list: () => get_sector_list(),
  get_hk_stock_price: (a) => get_hk_stock_price(a.symbol as string),
  get_hk_stock_info: (a) => get_hk_stock_info(a.symbol as string),
  get_hk_stock_history: (a) => get_hk_stock_history(a.symbol as string, a.period as string | undefined),
  calculate_technical_indicators: (a) => calculate_technical_indicators(a.symbol as string),
  calculate_buy_range: (a) => calculate_buy_range(a.symbol as string, a.current_price as number | undefined),
  get_stock_valuation: (a) => get_stock_valuation(a.symbol as string),
  get_pe_percentile: (a) => get_pe_percentile(a.symbol as string, a.years as number | undefined),
  get_quality_score: (a) => get_quality_score(a.symbol as string),
  get_stock_fund_flow: (a) => get_stock_fund_flow(a.symbol as string, a.days as number | undefined),
  get_holder_changes: (a) => get_holder_changes(a.symbol as string),
  get_exit_plan: (a) => get_exit_plan(a.symbol as string, a.buy_price as number, a.shares as number | undefined),
  analyze_price_action: (a) => analyze_price_action(a.symbol as string, a.period as number | undefined),
  analyze_candlestick: (a) => analyze_candlestick(a.symbol as string),
  compare_peers: (a) => compare_peers(a.symbol as string),
  manage_portfolio: (a) => manage_portfolio(
    a.action as string,
    a.symbol as string | undefined,
    a.quantity as number | undefined,
    a.avg_cost as number | undefined,
    a.notes as string | undefined,
  ),
};
