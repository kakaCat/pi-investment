import type { PaginatedResponse, StockInfo } from '@/types'

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
  const page = Number(data.page ?? 1)
  const pageSize = Number(data.pageSize ?? data.page_size ?? items.length ?? 0)
  const total = Number(data.total ?? data.count ?? items.length ?? 0)

  return {
    items,
    total,
    page,
    pageSize,
    totalPages: pageSize > 0 ? Math.ceil(total / pageSize) : 0
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
    changePercent: Number(raw.changePercent ?? raw.change_percent ?? 0)
  }
}

export function adaptStockList(response: any): PaginatedResponse<StockInfo> {
  const page = toPaginatedResponse<any>(response, 'stocks')
  return {
    ...page,
    items: page.items.map(adaptStock)
  }
}
