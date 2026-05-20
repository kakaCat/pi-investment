/**
 * 市场环境上下文
 */
export interface MarketContext {
  // 大盘指数
  indices: {
    sh000001: IndexMetrics;  // 上证指数
    sz399001: IndexMetrics;  // 深证成指
    sz399006: IndexMetrics;  // 创业板指
    hsi?: IndexMetrics;      // 恒生指数（可选）
  };

  // 板块表现
  sectorPerformance: SectorMetrics[];

  // 市场情绪
  sentiment: MarketSentiment;

  // 时间窗口
  period: {
    start: string;  // ISO date
    end: string;    // ISO date
    days: number;
  };

  // 数据质量
  dataQuality: {
    indicesAvailable: number;     // 可用指数数量
    sectorsAvailable: number;     // 可用板块数量
    sentimentComplete: boolean;   // 情绪数据是否完整
    reliability: 'high' | 'medium' | 'low';
  };
}

export interface IndexMetrics {
  code: string;
  name: string;
  return: number;           // 收益率（%）
  volatility: number;       // 波动率（标准差）
  trend: 'up' | 'down' | 'sideways';
  currentPrice: number;
  startPrice: number;
  highPrice: number;
  lowPrice: number;
}

export interface SectorMetrics {
  sector: string;           // 板块名称
  return: number;           // 收益率（%）
  rank: number;             // 排名（1-N）
  momentum: number;         // 动量指标（近5日收益率）
  fundFlow: number;         // 资金流向（亿元）
  leadingStocks: string[];  // 龙头股票
}

export interface MarketSentiment {
  advanceDeclineRatio: number;  // 涨跌家数比（上涨/下跌）
  volumeRatio: number;          // 成交量比（今日/5日均）
  marketBreadth: number;        // 市场广度（上涨股票占比 0-1）
  volatilityIndex: number;      // 波动率指数
  sentiment: 'bullish' | 'bearish' | 'neutral';
}
