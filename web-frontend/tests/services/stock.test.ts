import { describe, it, expect, vi, beforeEach } from 'vitest'
import { stockApi } from '@/services/api/stock'
import { apiClient } from '@/services/api/client'

vi.mock('@/services/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

describe('stockApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('repairStockData', () => {
    it('should trigger kline data update for the current stock only', async () => {
      const mockResponse = {
        success: true,
        run_id: '#D-12345678',
        symbols: ['600726'],
        days: 730
      }

      vi.mocked(apiClient.post).mockResolvedValue(mockResponse)

      const result = await stockApi.repairStockData('600726.SH')

      expect(apiClient.post).toHaveBeenCalledWith('/api/stocks/data-update-klines', {
        symbols: ['600726'],
        days: 730
      })
      expect(result).toEqual(mockResponse)
    })

    it('should allow a custom repair window', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ success: true })

      await stockApi.repairStockData('600726', 120)

      expect(apiClient.post).toHaveBeenCalledWith('/api/stocks/data-update-klines', {
        symbols: ['600726'],
        days: 120
      })
    })
  })

  describe('getMyStocks', () => {
    it('should fetch positions and watchlist successfully', async () => {
      const mockResponse = {
        positions: [
          { symbol: '600519', name: '贵州茅台' },
          { symbol: '000001', name: '平安银行' }
        ],
        watchlist: [
          { symbol: '600036', name: '招商银行' }
        ]
      }

      vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

      const result = await stockApi.getMyStocks()

      expect(apiClient.get).toHaveBeenCalledWith('/api/stocks/my-stocks')
      expect(result).toEqual(mockResponse)
      expect(result.positions).toHaveLength(2)
      expect(result.watchlist).toHaveLength(1)
    })

    it('should handle empty positions and watchlist', async () => {
      const mockResponse = {
        positions: [],
        watchlist: []
      }

      vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

      const result = await stockApi.getMyStocks()

      expect(result.positions).toEqual([])
      expect(result.watchlist).toEqual([])
    })

    it('should handle API errors', async () => {
      const mockError = new Error('Network error')
      vi.mocked(apiClient.get).mockRejectedValue(mockError)

      await expect(stockApi.getMyStocks()).rejects.toThrow('Network error')
    })
  })
})
