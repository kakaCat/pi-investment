/**
 * 市场快速过滤器 - 硬编码规则快速判断市场状态
 */

export interface MonitorQuote {
  symbol: string;
  name?: string;
  price?: number;
  current_price?: number;
  current?: number;
  change_pct?: number;
  pct_chg?: number;
  volume?: number;
  avg_volume?: number;
  support?: number;
  resistance?: number;
}

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
    near_support: MonitorQuote[];
    breakout: MonitorQuote[];
  };
}

export function quickFilter(quotes: MonitorQuote[], _context?: { holdings: any[] }): FilterResult {
  // Normalize quotes
  const normalized = quotes.map(q => ({
    symbol: q.symbol,
    name: q.name || '',
    price: q.price || q.current_price || q.current || 0,
    change_pct: q.change_pct || q.pct_chg || 0,
    volume: q.volume || 0,
    avg_volume: q.avg_volume,
    support: q.support,
    resistance: q.resistance,
  }));

  const high_volatility = normalized.filter(q => Math.abs(q.change_pct) > 3);
  const high_volume = normalized.filter(q =>
    q.avg_volume && q.volume > q.avg_volume * 2
  );
  const near_support = normalized.filter(q =>
    q.support && q.price > 0 && q.price <= q.support * 1.02
  );
  const breakout = normalized.filter(q =>
    q.resistance && q.price > 0 && q.price >= q.resistance
  );

  const allSignals = [...new Set([...high_volatility, ...high_volume, ...near_support, ...breakout])];

  let urgency = 0;
  if (high_volatility.length > 0) urgency = Math.max(urgency, 2);
  if (high_volume.length > 0) urgency = Math.max(urgency, 1);
  if (high_volatility.length > 2) urgency = 3;

  return {
    needsAgentAnalysis: urgency > 0,
    urgency,
    candidates: allSignals,
    signals: { high_volatility, high_volume, near_support, breakout }
  };
}
