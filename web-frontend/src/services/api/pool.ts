import { apiClient } from './client'

export interface FilterTemplate {
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

  validate(id: number, params?: PoolValidateParams) {
    return apiClient.post(`/api/pools/${id}/validate`, params)
  },

  scanAndCreate(data: PoolScanCreateParams) {
    return apiClient.post('/api/pools/scan-and-create', data)
  }
}
