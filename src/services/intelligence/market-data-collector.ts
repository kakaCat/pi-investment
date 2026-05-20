/**
 * 市场数据收集器
 *
 * 从 akshare 获取大盘指数、板块表现、市场情绪数据
 */

import { callPython } from '../../infrastructure/tools/shared/python-caller.js';
import type { MarketContext, IndexMetrics, SectorMetrics, MarketSentiment } from '../../types/market-context.js';

// ─── 配置 ────────────────────────────────────────────────────────────────

const INDICES = [
  { code: 'sh000001', name: '上证指数' },
  { code: 'sz399001', name: '深证成指' },
  { code: 'sz399006', name: '创业板指' },
];

const DEFAULT_DAYS = 90; // 默认时间窗口

// ─── 主函数 ──────────────────────────────────────────────────────────────

/**
 * 收集市场环境数据
 */
export async function collectMarketContext(
  startDate?: string,
  endDate?: string,
  days: number = DEFAULT_DAYS
): Promise<MarketContext> {
  // 计算时间窗口
  const period = calculatePeriod(startDate, endDate, days);

  console.log(`[市场数据] 收集时间窗口: ${period.start} ~ ${period.end} (${period.days}天)`);

  // 并行收集数据
  const [indices, sectorPerformance, sentiment] = await Promise.all([
    collectIndices(period.start, period.end),
    collectSectorPerformance(period.start, period.end),
    collectMarketSentiment(period.end),
  ]);

  // 评估数据质量
  const dataQuality = evaluateDataQuality(indices, sectorPerformance, sentiment);

  return {
    indices: {
      sh000001: indices.find(i => i.code === 'sh000001')!,
      sz399001: indices.find(i => i.code === 'sz399001')!,
      sz399006: indices.find(i => i.code === 'sz399006')!,
    },
    sectorPerformance,
    sentiment,
    period,
    dataQuality,
  };
}

// ─── 指数数据 ────────────────────────────────────────────────────────────

/**
 * 收集大盘指数数据
 */
async function collectIndices(startDate: string, endDate: string): Promise<IndexMetrics[]> {
  const results: IndexMetrics[] = [];

  for (const { code, name } of INDICES) {
    try {
      const data = await getIndexHistory(code, startDate, endDate);
      const metrics = calculateIndexMetrics(code, name, data);
      results.push(metrics);
    } catch (error) {
      console.warn(`[市场数据] 获取指数 ${code} 失败:`, error);
      // 使用降级数据
      results.push(createFallbackIndexMetrics(code, name));
    }
  }

  return results;
}

/**
 * 获取指数历史数据
 */
async function getIndexHistory(code: string, startDate: string, endDate: string): Promise<any[]> {
  const resultStr = await callPython('get_index_history', {
    symbol: code,
    start_date: startDate,
    end_date: endDate,
  });

  const result = JSON.parse(resultStr);

  if (!result.success || !result.data) {
    throw new Error(`获取指数 ${code} 历史数据失败`);
  }

  return result.data;
}

/**
 * 计算指数指标
 */
function calculateIndexMetrics(code: string, name: string, data: any[]): IndexMetrics {
  if (data.length === 0) {
    return createFallbackIndexMetrics(code, name);
  }

  // 按日期排序
  const sorted = data.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

  const startPrice = sorted[0].close;
  const endPrice = sorted[sorted.length - 1].close;
  const highPrice = Math.max(...sorted.map(d => d.high));
  const lowPrice = Math.min(...sorted.map(d => d.low));

  // 收益率
  const returnPct = ((endPrice - startPrice) / startPrice) * 100;

  // 波动率（日收益率的标准差）
  const dailyReturns = sorted.slice(1).map((d, i) =>
    ((d.close - sorted[i].close) / sorted[i].close) * 100
  );
  const volatility = calculateStdDev(dailyReturns);

  // 趋势判断
  const trend = determineTrend(returnPct, volatility);

  return {
    code,
    name,
    return: Math.round(returnPct * 100) / 100,
    volatility: Math.round(volatility * 100) / 100,
    trend,
    currentPrice: endPrice,
    startPrice,
    highPrice,
    lowPrice,
  };
}

/**
 * 判断趋势
 */
function determineTrend(returnPct: number, volatility: number): 'up' | 'down' | 'sideways' {
  // 如果收益率绝对值小于波动率，认为是横盘
  if (Math.abs(returnPct) < volatility) {
    return 'sideways';
  }

  return returnPct > 0 ? 'up' : 'down';
}

/**
 * 降级指数数据（数据获取失败时使用）
 */
function createFallbackIndexMetrics(code: string, name: string): IndexMetrics {
  return {
    code,
    name,
    return: 0,
    volatility: 0,
    trend: 'sideways',
    currentPrice: 0,
    startPrice: 0,
    highPrice: 0,
    lowPrice: 0,
  };
}

// ─── 板块数据 ────────────────────────────────────────────────────────────

/**
 * 收集板块表现数据
 */
async function collectSectorPerformance(startDate: string, endDate: string): Promise<SectorMetrics[]> {
  try {
    // 获取板块资金流向
    const fundFlowData = await getSectorFundFlow(endDate);

    // 获取板块涨跌幅
    const sectorReturns = await getSectorReturns(startDate, endDate);

    // 合并数据
    const sectors = mergeSectorData(fundFlowData, sectorReturns);

    // 排序并添加排名
    sectors.sort((a, b) => b.return - a.return);
    sectors.forEach((s, i) => s.rank = i + 1);

    return sectors;
  } catch (error) {
    console.warn('[市场数据] 获取板块数据失败:', error);
    return [];
  }
}

/**
 * 获取板块资金流向
 */
async function getSectorFundFlow(date: string): Promise<any[]> {
  const resultStr = await callPython('get_sector_fund_flow', {});
  const result = JSON.parse(resultStr);

  // get_sector_fund_flow 返回格式: { data: [...] } 或 { error: "..." }
  if (result.error || !result.data) {
    throw new Error('获取板块资金流向失败');
  }

  return result.data;
}

/**
 * 获取板块涨跌幅
 */
async function getSectorReturns(startDate: string, endDate: string): Promise<Map<string, number>> {
  // 这里简化处理，实际可以调用更详细的接口
  // 暂时从资金流向数据中提取涨跌幅
  return new Map();
}

/**
 * 合并板块数据
 */
function mergeSectorData(fundFlowData: any[], sectorReturns: Map<string, number>): SectorMetrics[] {
  return fundFlowData.slice(0, 20).map((item, index) => ({
    sector: item.sector || item.name,
    return: item.change_pct || sectorReturns.get(item.sector) || 0,
    rank: index + 1,
    momentum: item.change_pct || 0,
    fundFlow: item.net_inflow || 0,
    leadingStocks: item.leading_stocks || [],
  }));
}

// ─── 市场情绪 ────────────────────────────────────────────────────────────

/**
 * 收集市场情绪数据
 */
async function collectMarketSentiment(date: string): Promise<MarketSentiment> {
  try {
    // 获取涨跌家数
    const advanceDecline = await getAdvanceDeclineData(date);

    // 获取成交量数据
    const volumeData = await getVolumeData(date);

    // 计算市场广度
    const marketBreadth = advanceDecline.advance / (advanceDecline.advance + advanceDecline.decline);

    // 计算涨跌家数比
    const advanceDeclineRatio = advanceDecline.advance / advanceDecline.decline;

    // 计算成交量比
    const volumeRatio = volumeData.today / volumeData.avg5;

    // 判断市场情绪
    const sentiment = determineSentiment(marketBreadth, advanceDeclineRatio);

    return {
      advanceDeclineRatio: Math.round(advanceDeclineRatio * 100) / 100,
      volumeRatio: Math.round(volumeRatio * 100) / 100,
      marketBreadth: Math.round(marketBreadth * 100) / 100,
      volatilityIndex: 0, // TODO: 实现波动率指数
      sentiment,
    };
  } catch (error) {
    console.warn('[市场数据] 获取市场情绪失败:', error);
    return createFallbackSentiment();
  }
}

/**
 * 获取涨跌家数
 */
async function getAdvanceDeclineData(date: string): Promise<{ advance: number; decline: number }> {
  const resultStr = await callPython('get_market_overview', {});
  const result = JSON.parse(resultStr);

  // get_market_overview 返回格式: { indices: {...}, data_date: "..." }
  // 它不包含涨跌家数，所以我们需要使用默认值或从其他接口获取
  // 暂时使用估算值：根据指数涨跌推测
  if (!result.indices) {
    throw new Error('获取市场概览失败');
  }

  // 简化处理：根据主要指数涨跌估算涨跌家数比
  const shIndex = result.indices['上证指数'];
  const szIndex = result.indices['深证成指'];

  if (!shIndex || !szIndex) {
    throw new Error('获取指数数据失败');
  }

  // 估算：如果指数下跌，假设涨跌比为 0.8:1，上涨则为 1.2:1
  const avgChange = (shIndex.change_pct + szIndex.change_pct) / 2;
  let advance = 2000;
  let decline = 2000;

  if (avgChange > 0) {
    advance = 2400;
    decline = 2000;
  } else if (avgChange < 0) {
    advance = 1600;
    decline = 2000;
  }

  return { advance, decline };
}

/**
 * 获取成交量数据
 */
async function getVolumeData(date: string): Promise<{ today: number; avg5: number }> {
  // 简化处理，实际应该获取历史成交量
  return {
    today: 1,
    avg5: 1,
  };
}

/**
 * 判断市场情绪
 */
function determineSentiment(marketBreadth: number, advanceDeclineRatio: number): 'bullish' | 'bearish' | 'neutral' {
  if (marketBreadth > 0.6 && advanceDeclineRatio > 1.5) {
    return 'bullish';
  } else if (marketBreadth < 0.4 && advanceDeclineRatio < 0.67) {
    return 'bearish';
  } else {
    return 'neutral';
  }
}

/**
 * 降级情绪数据
 */
function createFallbackSentiment(): MarketSentiment {
  return {
    advanceDeclineRatio: 1,
    volumeRatio: 1,
    marketBreadth: 0.5,
    volatilityIndex: 0,
    sentiment: 'neutral',
  };
}

// ─── 工具函数 ────────────────────────────────────────────────────────────

/**
 * 计算时间窗口
 */
function calculatePeriod(
  startDate?: string,
  endDate?: string,
  days: number = DEFAULT_DAYS
): { start: string; end: string; days: number } {
  const end = endDate || new Date().toISOString().split('T')[0];

  let start: string;
  if (startDate) {
    start = startDate;
  } else {
    const startDateObj = new Date(end);
    startDateObj.setDate(startDateObj.getDate() - days);
    start = startDateObj.toISOString().split('T')[0];
  }

  // 计算实际天数
  const actualDays = Math.floor(
    (new Date(end).getTime() - new Date(start).getTime()) / (1000 * 60 * 60 * 24)
  );

  return { start, end, days: actualDays };
}

/**
 * 计算标准差
 */
function calculateStdDev(values: number[]): number {
  if (values.length === 0) return 0;

  const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
  const variance = values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length;

  return Math.sqrt(variance);
}

/**
 * 评估数据质量
 */
function evaluateDataQuality(
  indices: IndexMetrics[],
  sectors: SectorMetrics[],
  sentiment: MarketSentiment
): MarketContext['dataQuality'] {
  const indicesAvailable = indices.filter(i => i.return !== 0).length;
  const sectorsAvailable = sectors.length;
  const sentimentComplete = sentiment.advanceDeclineRatio > 0;

  let reliability: 'high' | 'medium' | 'low';
  if (indicesAvailable >= 3 && sectorsAvailable >= 10 && sentimentComplete) {
    reliability = 'high';
  } else if (indicesAvailable >= 2 && sectorsAvailable >= 5) {
    reliability = 'medium';
  } else {
    reliability = 'low';
  }

  return {
    indicesAvailable,
    sectorsAvailable,
    sentimentComplete,
    reliability,
  };
}

// ─── 导出 ────────────────────────────────────────────────────────────────

export {
  collectIndices,
  collectSectorPerformance,
  collectMarketSentiment,
};
