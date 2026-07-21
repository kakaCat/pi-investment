/**
 * Data Collector - 数据采集器
 *
 * 从 PostgreSQL（通过 CLI Adapters）和 reviews/ 提取数据用于经验库构建
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join } from 'path';

// 2026-07-19 修复：v1 quant CLI（.venv/bin/quant）已删除，
// PositionCliAdapter/TradeCliAdapter 全部失败（spawn quant ENOENT），
// 数据源迁移到 quantsys-v2 HTTP API（模拟交易账户）。
const V2_API_BASE = process.env.QUANTSYS_V2_API_URL ?? 'http://127.0.0.1:5001';

const DEFAULT_BASE_DIR = join(process.cwd(), '.pi-invest');

// ============ 类型定义 ============

export interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;
  market: 'A' | 'HK' | 'US';
  notes: string;
  added_date: string;
  original_cost: number;
  total_invested: number;
  stop_loss: number | null;
  target_price: number | null;
  batch_plan: string | null;
  sector: string;
  buy_reason: string | null;
}

export interface Portfolio {
  holdings: Holding[];
  last_updated: string;
}

export interface Trade {
  date: string;
  action: 'buy' | 'sell';
  symbol: string;
  name: string;
  quantity: number;
  price: number;
  amount: number;
  market: 'A' | 'HK' | 'US';
  notes: string;
  time: string;
}

export interface TradeHistory {
  trades: Trade[];
  last_updated: string;
}

export interface HoldingWithReturn extends Holding {
  current_return?: number;
  realized_return?: number;
  total_return?: number;
}

export interface TradeWithOutcome extends Trade {
  outcome?: 'profit' | 'loss' | 'breakeven';
  return_rate?: number;
  holding_days?: number;
}

export interface ReviewData {
  date: string;
  content: string;
  holdings_count: number;
  suggestions: string[];
}

// ============ Portfolio 解析器 ============

/**
 * 加载持仓数据（通过 CLI → PostgreSQL）
 */
export async function loadPortfolio(baseDir?: string): Promise<Portfolio> {
  const resp = await fetch(`${V2_API_BASE}/api/simulation/accounts/default`);
  const json = (await resp.json()) as any;
  if (!json.success) {
    throw new Error(json.error || '获取模拟账户持仓失败');
  }
  const positions: any[] = json.data?.positions ?? [];

  const holdings: Holding[] = positions.map(p => {
    const quantity = p.shares ?? p.quantity ?? 0;
    const avgCost = p.avg_price ?? p.cost_basis ?? 0;
    return {
      symbol: p.symbol,
      name: p.name || p.symbol,
      quantity,
      avg_cost: avgCost,
      market: 'A' as 'A' | 'HK',
      notes: p.notes || '',
      added_date: p.entry_date || '',
      original_cost: avgCost,
      total_invested: avgCost * quantity,
      stop_loss: p.stop_loss ?? null,
      target_price: null,
      batch_plan: null,
      sector: p.sector || '',
      buy_reason: p.entry_reason || null,
    };
  });

  return {
    holdings,
    last_updated: new Date().toISOString(),
  };
}

/**
 * 解析持仓数据，计算收益率
 */
export function parsePortfolio(
  portfolio: Portfolio,
  currentPrices?: Map<string, number>
): HoldingWithReturn[] {
  return portfolio.holdings.map(holding => {
    const result: HoldingWithReturn = { ...holding };

    // 如果提供了当前价格，计算浮动收益
    if (currentPrices && currentPrices.has(holding.symbol)) {
      const currentPrice = currentPrices.get(holding.symbol)!;
      const currentValue = currentPrice * holding.quantity;
      const costValue = holding.avg_cost * holding.quantity;
      result.current_return = ((currentValue - costValue) / costValue) * 100;
    }

    // 从 notes 中提取已实现收益信息
    const profitMatch = holding.notes.match(/卖.*?@[¥￥]?([\d.]+)/);
    if (profitMatch && holding.original_cost) {
      const sellPrice = parseFloat(profitMatch[1]);
      result.realized_return = ((sellPrice - holding.original_cost) / holding.original_cost) * 100;
    }

    return result;
  });
}

// ============ Trades 解析器 ============

/**
 * 加载交易记录（quantsys-v2 模拟交易账户）
 */
export async function loadTrades(baseDir?: string): Promise<TradeHistory> {
  const resp = await fetch(`${V2_API_BASE}/api/simulation/trades?limit=10000`);
  const json = (await resp.json()) as any;
  if (!json.success) {
    throw new Error(json.error || '获取模拟交易记录失败');
  }
  const trades: any[] = json.data ?? [];

  const mappedTrades: Trade[] = trades.map(t => {
    const quantity = t.shares ?? t.quantity ?? 0;
    const price = t.price ?? t.filled_price ?? 0;
    return {
      date: t.trade_date || t.timestamp || '',
      action: String(t.action || '').toLowerCase() as 'buy' | 'sell',
      symbol: t.symbol,
      name: t.name,
      quantity,
      price,
      amount: t.amount ?? price * quantity,
      market: 'A' as 'A' | 'HK',
      notes: t.notes || '',
      time: t.timestamp || t.trade_date || '',
    };
  });

  return {
    trades: mappedTrades,
    last_updated: new Date().toISOString(),
  };
}

/**
 * 解析交易记录，关联买卖配对计算收益
 */
export function parseTrades(trades: Trade[]): TradeWithOutcome[] {
  const results: TradeWithOutcome[] = [];
  const buyMap = new Map<string, Trade[]>(); // symbol -> buy trades

  // 按时间排序
  const sortedTrades = [...trades].sort((a, b) =>
    new Date(a.time).getTime() - new Date(b.time).getTime()
  );

  for (const trade of sortedTrades) {
    const result: TradeWithOutcome = { ...trade };

    if (trade.action === 'buy') {
      // 记录买入
      if (!buyMap.has(trade.symbol)) {
        buyMap.set(trade.symbol, []);
      }
      buyMap.get(trade.symbol)!.push(trade);
    } else if (trade.action === 'sell') {
      // 尝试匹配买入记录
      const buyTrades = buyMap.get(trade.symbol);
      if (buyTrades && buyTrades.length > 0) {
        // FIFO: 使用最早的买入记录
        const buyTrade = buyTrades[0];

        // 计算收益率
        result.return_rate = ((trade.price - buyTrade.price) / buyTrade.price) * 100;
        result.outcome = result.return_rate > 0.5 ? 'profit'
                       : result.return_rate < -0.5 ? 'loss'
                       : 'breakeven';

        // 计算持有天数
        const buyDate = new Date(buyTrade.time);
        const sellDate = new Date(trade.time);
        result.holding_days = Math.floor((sellDate.getTime() - buyDate.getTime()) / (1000 * 60 * 60 * 24));

        // 如果卖出数量 >= 买入数量，移除这条买入记录
        if (trade.quantity >= buyTrade.quantity) {
          buyTrades.shift();
        }
      }
    }

    results.push(result);
  }

  return results;
}

/**
 * 按股票分组交易记录
 */
export function groupTradesBySymbol(trades: TradeWithOutcome[]): Map<string, TradeWithOutcome[]> {
  const grouped = new Map<string, TradeWithOutcome[]>();

  for (const trade of trades) {
    if (!grouped.has(trade.symbol)) {
      grouped.set(trade.symbol, []);
    }
    grouped.get(trade.symbol)!.push(trade);
  }

  return grouped;
}

/**
 * 计算交易统计
 */
export interface TradeStats {
  total_trades: number;
  buy_count: number;
  sell_count: number;
  profit_count: number;
  loss_count: number;
  win_rate: number;
  avg_return: number;
  avg_holding_days: number;
  total_profit: number;
  total_loss: number;
}

export function calculateTradeStats(trades: TradeWithOutcome[]): TradeStats {
  const sellTrades = trades.filter(t => t.action === 'sell' && t.return_rate !== undefined);

  const profitTrades = sellTrades.filter(t => t.outcome === 'profit');
  const lossTrades = sellTrades.filter(t => t.outcome === 'loss');

  const totalReturn = sellTrades.reduce((sum, t) => sum + (t.return_rate || 0), 0);
  const totalHoldingDays = sellTrades
    .filter(t => t.holding_days !== undefined)
    .reduce((sum, t) => sum + (t.holding_days || 0), 0);

  return {
    total_trades: trades.length,
    buy_count: trades.filter(t => t.action === 'buy').length,
    sell_count: trades.filter(t => t.action === 'sell').length,
    profit_count: profitTrades.length,
    loss_count: lossTrades.length,
    win_rate: sellTrades.length > 0 ? (profitTrades.length / sellTrades.length) * 100 : 0,
    avg_return: sellTrades.length > 0 ? totalReturn / sellTrades.length : 0,
    avg_holding_days: sellTrades.length > 0 ? totalHoldingDays / sellTrades.length : 0,
    total_profit: profitTrades.reduce((sum, t) => sum + (t.return_rate || 0), 0),
    total_loss: lossTrades.reduce((sum, t) => sum + (t.return_rate || 0), 0),
  };
}

// ============ Reviews 解析器 ============

/**
 * 加载复盘数据
 */
export function loadReviews(baseDir: string = DEFAULT_BASE_DIR): ReviewData[] {
  const reviewsDir = join(baseDir, 'reviews');

  if (!existsSync(reviewsDir)) {
    return [];
  }

  const files = readdirSync(reviewsDir)
    .filter(f => f.endsWith('.md'))
    .sort();

  return files.map(file => parseReviewFile(join(reviewsDir, file)));
}

/**
 * 解析单个复盘文件
 */
function parseReviewFile(filePath: string): ReviewData {
  const content = readFileSync(filePath, 'utf-8');
  const filename = filePath.split('/').pop()!;
  const date = filename.replace('.md', '');

  // 提取持仓数量
  const holdingsMatch = content.match(/持仓复盘（(\d+)只）/);
  const holdings_count = holdingsMatch ? parseInt(holdingsMatch[1]) : 0;

  // 提取操作建议
  const suggestions: string[] = [];
  const suggestionRegex = /💡 \*\*操作建议\*\*：(.+)/g;
  let match;
  while ((match = suggestionRegex.exec(content)) !== null) {
    suggestions.push(match[1].trim());
  }

  return {
    date,
    content,
    holdings_count,
    suggestions,
  };
}

/**
 * 从复盘中提取经验模式
 */
export interface ExperiencePattern {
  date: string;
  symbol: string;
  condition: string;
  suggestion: string;
}

export function extractPatternsFromReviews(reviews: ReviewData[]): ExperiencePattern[] {
  const patterns: ExperiencePattern[] = [];

  for (const review of reviews) {
    const lines = review.content.split('\n');
    let currentSymbol = '';

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // 提取股票代码和名称
      const symbolMatch = line.match(/###\s+(.+?)（(\d+|[A-Z0-9]+)）/);
      if (symbolMatch) {
        currentSymbol = symbolMatch[2];
      }

      // 提取操作建议
      const suggestionMatch = line.match(/💡 \*\*操作建议\*\*：(.+)/);
      if (suggestionMatch && currentSymbol) {
        const suggestion = suggestionMatch[1].trim();

        // 向上查找技术指标
        let condition = '';
        for (let j = i - 1; j >= 0 && j > i - 10; j--) {
          if (lines[j].includes('趋势：') || lines[j].includes('MACD：') || lines[j].includes('RSI：')) {
            condition += lines[j].trim() + '; ';
          }
          if (lines[j].includes('###')) break;
        }

        patterns.push({
          date: review.date,
          symbol: currentSymbol,
          condition: condition.trim(),
          suggestion,
        });
      }
    }
  }

  return patterns;
}

// ============ 综合数据采集 ============

export interface CollectedData {
  portfolio: HoldingWithReturn[];
  trades: TradeWithOutcome[];
  tradeStats: TradeStats;
  reviews: ReviewData[];
  patterns: ExperiencePattern[];
  collectedAt: string;
}

/**
 * 采集所有数据
 */
export async function collectAllData(baseDir?: string): Promise<CollectedData> {
  try {
    const portfolio = await loadPortfolio(baseDir);
    const tradeHistory = await loadTrades(baseDir);
    const reviews = loadReviews(baseDir);

    const parsedPortfolio = parsePortfolio(portfolio);
    const parsedTrades = parseTrades(tradeHistory.trades);
    const tradeStats = calculateTradeStats(parsedTrades);
    const patterns = extractPatternsFromReviews(reviews);

    return {
      portfolio: parsedPortfolio,
      trades: parsedTrades,
      tradeStats,
      reviews,
      patterns,
      collectedAt: new Date().toISOString(),
    };
  } catch (error) {
    if (error instanceof Error) {
      throw new Error(`Data collection failed: ${error.message}`);
    }
    throw error;
  }
}
