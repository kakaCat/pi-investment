/**
 * 持仓维度分析类型定义
 */

// 个股持仓分析
export interface StockHoldingAnalysis {
  symbol: string;
  name: string;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  unrealizedPnL: number;
  returnRate: number;
  weight: number; // 占组合比例
  sector?: string;
  marketCap?: number;
  daysHeld: number;
  contribution: number; // 对组合收益的贡献
}

// 行业维度分析
export interface SectorAnalysis {
  sector: string;
  stockCount: number;
  totalValue: number;
  weight: number;
  avgReturn: number;
  totalPnL: number;
  contribution: number;
  stocks: Array<{
    symbol: string;
    name: string;
    returnRate: number;
    weight: number;
  }>;
}

// 市值维度分析
export interface MarketCapAnalysis {
  category: 'large' | 'mid' | 'small'; // 大盘、中盘、小盘
  label: string;
  stockCount: number;
  totalValue: number;
  weight: number;
  avgReturn: number;
  totalPnL: number;
  contribution: number;
  stocks: Array<{
    symbol: string;
    name: string;
    marketCap: number;
    returnRate: number;
  }>;
}

// 持仓问题诊断
export interface HoldingIssue {
  type: 'underperformer' | 'overweight' | 'sector_concentration' | 'long_term_loser';
  severity: 'high' | 'medium' | 'low';
  symbol?: string;
  sector?: string;
  description: string;
  impact: string;
  suggestion: string;
}

// 持仓维度分析结果
export interface HoldingDimensionAnalysis {
  // 个股维度
  stocks: StockHoldingAnalysis[];
  topPerformers: StockHoldingAnalysis[]; // 表现最好的 5 只
  bottomPerformers: StockHoldingAnalysis[]; // 表现最差的 5 只

  // 行业维度
  sectors: SectorAnalysis[];
  topSectors: SectorAnalysis[]; // 表现最好的行业
  bottomSectors: SectorAnalysis[]; // 表现最差的行业

  // 市值维度
  marketCaps: MarketCapAnalysis[];

  // 问题诊断
  issues: HoldingIssue[];

  // 统计摘要
  summary: {
    totalValue: number;
    totalPnL: number;
    avgReturn: number;
    winningStocks: number;
    losingStocks: number;
    winRate: number;
    maxSingleStockWeight: number;
    maxSectorWeight: number;
  };
}
