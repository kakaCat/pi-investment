import { apiClient } from './client'

export interface FilterTemplate {
  /** PoolList 扫描建池传入的条件数组（后端按此筛选） */
  conditions?: any[]
  logic?: string
  min_score?: number
  max_risk_level?: string
  technical?: string[]
  fundamental?: string[]
  top_n?: number
}

export interface PoolCreateParams {
  name: string
  poolType: 'static' | 'dynamic'
  symbols?: string[]
  filterTemplate?: FilterTemplate
  refreshInterval?: 'daily' | 'weekly'
  description?: string
}

export interface PoolValidateParams {
  strategyIds?: number[]
  startDate?: string
  endDate?: string
}

export interface PoolScanCreateParams {
  name: string
  poolType: 'static' | 'dynamic'
  filter: FilterTemplate
  refreshInterval?: 'daily' | 'weekly'
  description?: string
}

export const poolApi = {
  list() {
    return apiClient.get('/api/pools')
  },

  getById(id: number) {
    return apiClient.get(`/api/pools/${id}`)
  },

  create(data: PoolCreateParams) {
    return apiClient.post('/api/pools', data)
  },

  update(id: number, data: { name?: string; description?: string; symbols?: string[] }) {
    return apiClient.put(`/api/pools/${id}`, data)
  },

  delete(id: number) {
    return apiClient.delete(`/api/pools/${id}`)
  },

  refresh(id: number) {
    return apiClient.post(`/api/pools/${id}/refresh`)
  },

  syncStockNames(id: number) {
    return apiClient.post(`/api/pools/${id}/sync-stock-names`)
  },

  validate(id: number, params?: PoolValidateParams) {
    return apiClient.post(`/api/pools/${id}/validate`, params)
  },

  scanAndCreate(data: PoolScanCreateParams) {
    return apiClient.post('/api/pools/scan-and-create', data)
  },

  updateMember(poolId: number, symbol: string, data: { description?: string; buyPoint?: string; sellPoint?: string; tags?: string[] }) {
    return apiClient.put(`/api/pools/${poolId}/members/${symbol}`, data)
  },

  toggleScan(poolId: number, enabled: boolean) {
    return apiClient.put(`/api/pools/${poolId}/scan-switch`, { enabled })
  },

  getScanStatus() {
    return apiClient.get('/api/pools/scan-status')
  },

  scanSignals(id: number, params: { strategy_id: number; lookback_days?: number }) {
    return apiClient.post(`/api/pools/${id}/scan-signals`, params)
  }
}
