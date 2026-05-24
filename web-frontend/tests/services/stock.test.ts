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

describe('stockApi.getMyStocks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch positions and watchlist successfully', async () => {
    const mockResponse = {
      positions: [
        { symbol: '000001.SZ', name: '平安银行' },
        { symbol: '600000.SH', name: '浦发银行' }
      ],
      watchlist: [
        { symbol: '000002.SZ', name: '万科A' },
        { symbol: '600036.SH', name: '招商银行' }
      ]
    }

    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

    const result = await stockApi.getMyStocks()

    expect(apiClient.get).toHaveBeenCalledWith('/api/stocks/my-stocks')
    expect(result).toEqual(mockResponse)
    expect(result.positions).toHaveLength(2)
    expect(result.watchlist).toHaveLength(2)
  })

  it('should handle empty positions and watchlist', async () => {
    const mockResponse = {
      positions: [],
      watchlist: []
    }

    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

    const result = await stockApi.getMyStocks()

    expect(result.positions).toHaveLength(0)
    expect(result.watchlist).toHaveLength(0)
  })

  it('should propagate API errors', async () => {
    const mockError = new Error('Network error')
    vi.mocked(apiClient.get).mockRejectedValue(mockError)

    await expect(stockApi.getMyStocks()).rejects.toThrow('Network error')
  })
})
