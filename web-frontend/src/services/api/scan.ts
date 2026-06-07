import { apiClient } from './client'

export const scanApi = {
  // 扫描所有股票池
  scanAllPools(params?: { strategy_ids?: number[]; min_score?: number }) {
    return apiClient.post('/api/pools/scan-all', params)
  },

  // 扫描指定股票池
  scanPool(poolId: number, params?: { strategy_ids?: number[]; min_score?: number }) {
    return apiClient.post(`/api/pools/${poolId}/scan`, params)
  },

  // 启动/停止定时扫描
  controlSchedule(action: 'start' | 'stop' | 'trigger') {
    return apiClient.post('/api/pools/scan/schedule', { action })
  },

  // 获取扫描历史
  getScanHistory(params?: { pool_id?: number; limit?: number }) {
    return apiClient.get('/api/pools/scan-results', { params })
  },

  // 获取扫描状态
  getScanStatus() {
    return apiClient.get('/api/pools/scan-status')
  }
}
