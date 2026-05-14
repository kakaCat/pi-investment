/**
 * 市场快速过滤器 - 硬编码规则快速判断市场状态
 */

export interface Quote {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  avg_volume?: number;
}

export interface FilterResult {
  needsAgentAnalysis: boolean;
  urgency: number;  // 0=平淡, 1=正常, 2=活跃, 3=紧急
  candidates: Quote[];
  signals: {
    high_volatility: Quote[];
    high_volume: Quote[];
  };
}

export function quickFilter(quotes: Quote[]): FilterResult {
  const high_volatility = quotes.filter(q => Math.abs(q.change_pct) > 3);
  const high_volume = quotes.filter(q =>
    q.avg_volume && q.volume > q.avg_volume * 2
  );

  const allSignals = [...new Set([...high_volatility, ...high_volume])];

  let urgency = 0;
  if (high_volatility.length > 0) urgency = Math.max(urgency, 2);
  if (high_volume.length > 0) urgency = Math.max(urgency, 1);
  if (high_volatility.length > 2) urgency = 3;

  return {
    needsAgentAnalysis: urgency > 0,
    urgency,
    candidates: allSignals,
    signals: { high_volatility, high_volume }
  };
}
