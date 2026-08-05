import type { HeatmapResponse, KLineData, PaginatedResponse, StockInfo } from '@/types'

export function asData<T = any>(response: any): T {
  if (response && typeof response === 'object' && 'data' in response && response.success !== false) {
    return response.data as T
  }
  return response as T
}

export function toPaginatedResponse<T>(
  response: any,
  itemKey: 'items' | 'stocks' | 'signals' | 'runs' = 'items'
): PaginatedResponse<T> {
  const data = asData<any>(response) || {}
  const items = data.items ?? data[itemKey] ?? []
  const pagination = data.pagination ?? {}
  const page = Number(data.page ?? pagination.page ?? 1)
  const pageSize = Number(data.pageSize ?? data.page_size ?? pagination.pageSize ?? pagination.page_size ?? items.length ?? 0)
  const total = Number(data.total ?? data.count ?? pagination.total ?? pagination.count ?? items.length ?? 0)
  const totalPages = Number(data.totalPages ?? data.total_pages ?? pagination.totalPages ?? pagination.total_pages ?? 0)

  return {
    items,
    total,
    page,
    pageSize,
    totalPages: totalPages || (pageSize > 0 ? Math.ceil(total / pageSize) : 0)
  }
}

export function adaptKLine(raw: any): KLineData {
  return {
    date: raw.tradeDate ?? raw.trade_date ?? raw.date ?? '',
    open: Number(raw.open ?? raw.openPrice ?? raw.open_price ?? 0),
    close: Number(raw.close ?? raw.closePrice ?? raw.close_price ?? 0),
    high: Number(raw.high ?? raw.highPrice ?? raw.high_price ?? 0),
    low: Number(raw.low ?? raw.lowPrice ?? raw.low_price ?? 0),
    volume: Number(raw.volume ?? 0),
    amount: Number(raw.amount ?? 0)
  }
}

export function adaptStock(raw: any): StockInfo {
  return {
    symbol: raw.symbol ?? raw.code ?? '',
    code: raw.code ?? raw.symbol ?? '',
    name: raw.name ?? raw.symbolName ?? '',
    industry: raw.industry ?? '',
    sector: raw.sector ?? raw.market ?? '',
    market: raw.market ?? raw.exchange ?? '',
    marketCap: Number(raw.marketCap ?? raw.market_cap ?? 0),
    pe: Number(raw.pe ?? 0),
    pb: Number(raw.pb ?? 0),
    roe: Number(raw.roe ?? 0),
    currentPrice: Number(raw.currentPrice ?? raw.current_price ?? raw.close ?? raw.price ?? 0),
    price: Number(raw.price ?? raw.currentPrice ?? raw.current_price ?? raw.close ?? 0),
    change: Number(raw.change ?? 0),
    changePercent: Number(raw.changePercent ?? raw.change_percent ?? 0),
    klineDays: Number(raw.klineDays ?? raw.kline_days ?? 0),
    factorCount: Number(raw.factorCount ?? raw.factor_count ?? 0),
    dataStatus: raw.dataStatus ?? raw.data_status ?? 'unknown'
  }
}

export function adaptStockList(response: any): PaginatedResponse<StockInfo> {
  const page = toPaginatedResponse<any>(response, 'stocks')
  return {
    ...page,
    items: page.items.map(adaptStock)
  }
}

export function adaptHeatmap(response: any): HeatmapResponse {
  const raw = asData<any>(response) ?? {}
  const industries = Array.isArray(raw.industries) ? raw.industries : []
  return {
    date: raw.date ?? '',
    window: Number(raw.window ?? 5),
    actualEndDate: raw.actualEndDate ?? raw.actual_end_date ?? null,
    partial: Boolean(raw.partial),
    scopeDegraded: Boolean(raw.scopeDegraded ?? raw.scope_degraded),
    excludedCount: Number(raw.excludedCount ?? raw.excluded_count ?? 0),
    message: raw.message,
    industries: industries.map((ind: any) => ({
      name: ind.name ?? '',
      changePct: Number(ind.changePct ?? ind.change_pct ?? 0),
      agentStance: ind.agentStance ?? ind.agent_stance ?? 'neutral',
      stocks: (Array.isArray(ind.stocks) ? ind.stocks : []).map((s: any) => ({
        symbol: s.symbol ?? '',
        name: s.name ?? '',
        changePct: Number(s.changePct ?? s.change_pct ?? 0),
        marketCap: Number(s.marketCap ?? s.market_cap ?? 0),
        inScope: Boolean(s.inScope ?? s.in_scope),
        startDate: s.startDate ?? s.start_date,
        endDate: s.endDate ?? s.end_date,
        signals: s.signals,
        poolEvents: s.poolEvents ?? s.pool_events,
      })),
    })),
  }
}
