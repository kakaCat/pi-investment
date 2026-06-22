/**
 * 持仓维度分析器
 * 按个股、行业、市值维度分析持仓表现
 */

import type { Holding } from './data-collector.js';
import type {
  HoldingDimensionAnalysis,
  StockHoldingAnalysis,
  SectorAnalysis,
  MarketCapAnalysis,
  HoldingIssue,
} from '../../types/holding-analysis.js';

/**
 * 分析持仓维度表现
 */
export async function analyzeHoldingDimensions(
  holdings: Holding[],
  currentPrices: Map<string, number>,
  stockInfo: Map<string, { name: string; sector?: string; marketCap?: number }>
): Promise<HoldingDimensionAnalysis> {
  // 1. 个股维度分析
  const stocks = analyzeStocks(holdings, currentPrices, stockInfo);

  // 2. 行业维度分析
  const sectors = analyzeSectors(stocks);

  // 3. 市值维度分析
  const marketCaps = analyzeMarketCaps(stocks);

  // 4. 问题诊断
  const issues = diagnoseIssues(stocks, sectors, marketCaps);

  // 5. 统计摘要
  const summary = calculateSummary(stocks, sectors);

  // 6. 排序和筛选
  const topPerformers = [...stocks]
    .sort((a, b) => b.returnRate - a.returnRate)
    .slice(0, 5);

  const bottomPerformers = [...stocks]
    .sort((a, b) => a.returnRate - b.returnRate)
    .slice(0, 5);

  const topSectors = [...sectors]
    .sort((a, b) => b.avgReturn - a.avgReturn)
    .slice(0, 3);

  const bottomSectors = [...sectors]
    .sort((a, b) => a.avgReturn - b.avgReturn)
    .slice(0, 3);

  return {
    stocks,
    topPerformers,
    bottomPerformers,
    sectors,
    topSectors,
    bottomSectors,
    marketCaps,
    issues,
    summary,
  };
}

/**
 * 分析个股表现
 */
function analyzeStocks(
  holdings: Holding[],
  currentPrices: Map<string, number>,
  stockInfo: Map<string, { name: string; sector?: string; marketCap?: number }>
): StockHoldingAnalysis[] {
  const totalValue = holdings.reduce((sum, h) => {
    const price = currentPrices.get(h.symbol) || h.avg_cost;
    return sum + price * h.quantity;
  }, 0);

  return holdings.map(h => {
    const info = stockInfo.get(h.symbol) || { name: h.symbol };
    const currentPrice = currentPrices.get(h.symbol) || h.avg_cost;
    const marketValue = currentPrice * h.quantity;
    const unrealizedPnL = (currentPrice - h.avg_cost) * h.quantity;
    const returnRate = ((currentPrice - h.avg_cost) / h.avg_cost) * 100;
    const weight = (marketValue / totalValue) * 100;

    // 计算持有天数（简化：假设从 added_date 到现在）
    const daysHeld = h.added_date
      ? Math.floor((Date.now() - new Date(h.added_date).getTime()) / (1000 * 60 * 60 * 24))
      : 0;

    // 对组合收益的贡献 = 个股收益 / 总市值
    const contribution = (unrealizedPnL / totalValue) * 100;

    return {
      symbol: h.symbol,
      name: info.name,
      quantity: h.quantity,
      avgCost: h.avg_cost,
      currentPrice,
      marketValue,
      unrealizedPnL,
      returnRate,
      weight,
      sector: info.sector,
      marketCap: info.marketCap,
      daysHeld,
      contribution,
    };
  });
}

/**
 * 分析行业维度
 */
function analyzeSectors(stocks: StockHoldingAnalysis[]): SectorAnalysis[] {
  const sectorMap = new Map<string, StockHoldingAnalysis[]>();

  // 按行业分组
  stocks.forEach(stock => {
    const sector = stock.sector || '未分类';
    if (!sectorMap.has(sector)) {
      sectorMap.set(sector, []);
    }
    sectorMap.get(sector)!.push(stock);
  });

  const totalValue = stocks.reduce((sum, s) => sum + s.marketValue, 0);

  // 计算每个行业的统计数据
  return Array.from(sectorMap.entries()).map(([sector, sectorStocks]) => {
    const totalSectorValue = sectorStocks.reduce((sum, s) => sum + s.marketValue, 0);
    const totalPnL = sectorStocks.reduce((sum, s) => sum + s.unrealizedPnL, 0);
    const avgReturn = sectorStocks.reduce((sum, s) => sum + s.returnRate, 0) / sectorStocks.length;
    const weight = (totalSectorValue / totalValue) * 100;
    const contribution = (totalPnL / totalValue) * 100;

    return {
      sector,
      stockCount: sectorStocks.length,
      totalValue: totalSectorValue,
      weight,
      avgReturn,
      totalPnL,
      contribution,
      stocks: sectorStocks.map(s => ({
        symbol: s.symbol,
        name: s.name,
        returnRate: s.returnRate,
        weight: s.weight,
      })),
    };
  });
}

/**
 * 分析市值维度
 */
function analyzeMarketCaps(stocks: StockHoldingAnalysis[]): MarketCapAnalysis[] {
  const categories: Array<{
    category: 'large' | 'mid' | 'small';
    label: string;
    filter: (marketCap: number) => boolean;
  }> = [
    { category: 'large', label: '大盘股 (>500亿)', filter: (mc) => mc > 50000000000 },
    { category: 'mid', label: '中盘股 (100-500亿)', filter: (mc) => mc >= 10000000000 && mc <= 50000000000 },
    { category: 'small', label: '小盘股 (<100亿)', filter: (mc) => mc < 10000000000 },
  ];

  const totalValue = stocks.reduce((sum, s) => sum + s.marketValue, 0);

  return categories.map(({ category, label, filter }) => {
    const categoryStocks = stocks.filter(s => s.marketCap && filter(s.marketCap));
    const totalCategoryValue = categoryStocks.reduce((sum, s) => sum + s.marketValue, 0);
    const totalPnL = categoryStocks.reduce((sum, s) => sum + s.unrealizedPnL, 0);
    const avgReturn = categoryStocks.length > 0
      ? categoryStocks.reduce((sum, s) => sum + s.returnRate, 0) / categoryStocks.length
      : 0;
    const weight = (totalCategoryValue / totalValue) * 100;
    const contribution = (totalPnL / totalValue) * 100;

    return {
      category,
      label,
      stockCount: categoryStocks.length,
      totalValue: totalCategoryValue,
      weight,
      avgReturn,
      totalPnL,
      contribution,
      stocks: categoryStocks.map(s => ({
        symbol: s.symbol,
        name: s.name,
        marketCap: s.marketCap!,
        returnRate: s.returnRate,
      })),
    };
  });
}

/**
 * 诊断持仓问题
 */
function diagnoseIssues(
  stocks: StockHoldingAnalysis[],
  sectors: SectorAnalysis[],
  marketCaps: MarketCapAnalysis[]
): HoldingIssue[] {
  const issues: HoldingIssue[] = [];

  // 1. 识别严重亏损的个股（收益率 < -20%）
  stocks.forEach(stock => {
    if (stock.returnRate < -20) {
      issues.push({
        type: 'underperformer',
        severity: stock.returnRate < -30 ? 'high' : 'medium',
        symbol: stock.symbol,
        description: `${stock.name} 亏损 ${stock.returnRate.toFixed(2)}%`,
        impact: `拖累组合收益 ${Math.abs(stock.contribution).toFixed(2)}%`,
        suggestion: stock.returnRate < -30
          ? '建议止损或减仓，避免进一步亏损'
          : '关注基本面变化，考虑是否继续持有',
      });
    }
  });

  // 2. 识别过度集中的个股（单只占比 > 15%）
  stocks.forEach(stock => {
    if (stock.weight > 15) {
      issues.push({
        type: 'overweight',
        severity: stock.weight > 20 ? 'high' : 'medium',
        symbol: stock.symbol,
        description: `${stock.name} 占比 ${stock.weight.toFixed(2)}%，过度集中`,
        impact: '单一持仓风险过高，波动性大',
        suggestion: '建议分批减仓，降低单一持仓风险',
      });
    }
  });

  // 3. 识别行业过度集中（单一行业 > 30%）
  sectors.forEach(sector => {
    if (sector.weight > 30) {
      issues.push({
        type: 'sector_concentration',
        severity: sector.weight > 40 ? 'high' : 'medium',
        sector: sector.sector,
        description: `${sector.sector} 行业占比 ${sector.weight.toFixed(2)}%，过度集中`,
        impact: '行业风险过高，受行业周期影响大',
        suggestion: '建议分散到其他行业，降低行业集中度',
      });
    }
  });

  // 4. 识别长期亏损股（持有 > 90 天且亏损 > 15%）
  stocks.forEach(stock => {
    if (stock.daysHeld > 90 && stock.returnRate < -15) {
      issues.push({
        type: 'long_term_loser',
        severity: 'medium',
        symbol: stock.symbol,
        description: `${stock.name} 持有 ${stock.daysHeld} 天，亏损 ${stock.returnRate.toFixed(2)}%`,
        impact: '长期占用资金，机会成本高',
        suggestion: '重新评估投资逻辑，考虑止损换股',
      });
    }
  });

  // 按严重程度排序
  return issues.sort((a, b) => {
    const severityOrder = { high: 0, medium: 1, low: 2 };
    return severityOrder[a.severity] - severityOrder[b.severity];
  });
}

/**
 * 计算统计摘要
 */
function calculateSummary(
  stocks: StockHoldingAnalysis[],
  sectors: SectorAnalysis[]
): HoldingDimensionAnalysis['summary'] {
  const totalValue = stocks.reduce((sum, s) => sum + s.marketValue, 0);
  const totalPnL = stocks.reduce((sum, s) => sum + s.unrealizedPnL, 0);
  const avgReturn = stocks.reduce((sum, s) => sum + s.returnRate, 0) / stocks.length;
  const winningStocks = stocks.filter(s => s.returnRate > 0).length;
  const losingStocks = stocks.filter(s => s.returnRate < 0).length;
  const winRate = (winningStocks / stocks.length) * 100;
  const maxSingleStockWeight = Math.max(...stocks.map(s => s.weight));
  const maxSectorWeight = Math.max(...sectors.map(s => s.weight));

  return {
    totalValue,
    totalPnL,
    avgReturn,
    winningStocks,
    losingStocks,
    winRate,
    maxSingleStockWeight,
    maxSectorWeight,
  };
}
