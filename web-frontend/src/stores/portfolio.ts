import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Position, PortfolioSummaryResponse } from '@/types'
import { tradingApi } from '@/services/api'

export const usePortfolioStore = defineStore('portfolio', () => {
  // State
  const positions = ref<Position[]>([])
  const summary = ref<PortfolioSummaryResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const totalValue = computed(() =>
    summary.value?.totalValue ?? 0
  )

  const totalCost = computed(() =>
    summary.value?.totalCost ?? 0
  )

  const totalPnL = computed(() =>
    summary.value?.totalPnl ?? 0
  )

  const totalPnLPercent = computed(() =>
    summary.value?.totalPnlPct ?? 0
  )

  const positionCount = computed(() =>
    summary.value?.positions ?? positions.value.length
  )

  const cash = computed(() =>
    summary.value?.cash ?? summary.value?.liquidAssets ?? 0
  )

  const dailyChange = computed(() =>
    summary.value?.dailyChange ?? 0
  )

  const allocation = computed(() => {
    const total = totalValue.value
    if (total <= 0) return []
    return positions.value.map(p => ({
      symbol: p.symbol,
      symbolName: p.symbolName,
      value: p.marketValue,
      weight: total > 0 ? (p.marketValue / total) * 100 : 0
    }))
  })

  // Actions
  const fetchSummary = async () => {
    try {
      const data = await tradingApi.getPortfolioSummary()
      summary.value = data as unknown as PortfolioSummaryResponse
    } catch (e: any) {
      console.error('获取持仓汇总失败:', e)
    }
  }

  const fetchPositions = async () => {
    loading.value = true
    error.value = null
    try {
      const data = await tradingApi.getPositions()
      const rawList: any[] = (data as any).positions ?? (data as any) ?? []

      const totalMV = rawList.reduce((sum, p) => sum + (p.currentValue || 0), 0)

      positions.value = rawList.map((p: any) => ({
        id: p.symbol,
        symbol: p.symbol,
        symbolName: p.name,
        name: p.name,
        quantity: p.quantity,
        avgCost: p.avgCost,
        currentPrice: p.currentPrice,
        marketValue: p.currentValue,
        totalCost: p.totalCost || p.avgCost * p.quantity,
        unrealizedPnL: p.profitLoss,
        unrealizedPnLPercent: p.profitLossPct,
        profit: p.profitLoss,
        profitPercent: p.profitLossPct,
        weight: totalMV > 0 ? (p.currentValue / totalMV) * 100 : 0,
        buyDate: p.updatedAt || '',
        addedDate: p.updatedAt || '',
        market: p.market || '',
        sector: p.sector || null,
        stopLoss: undefined,
        targetPrice: undefined,
        reason: ''
      })) as Position[]
    } catch (e: any) {
      error.value = e.message
      console.error('获取持仓列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  const fetchAll = async () => {
    await Promise.all([fetchSummary(), fetchPositions()])
  }

  const updatePosition = (position: Position) => {
    const index = positions.value.findIndex(p => p.id === position.id)
    if (index !== -1) {
      positions.value[index] = position
    }
  }

  const addPosition = (position: Position) => {
    positions.value.push(position)
  }

  const removePosition = (positionId: string) => {
    const index = positions.value.findIndex(p => p.id === positionId)
    if (index !== -1) {
      positions.value.splice(index, 1)
    }
  }

  return {
    // State
    positions,
    summary,
    loading,
    error,
    // Getters
    totalValue,
    totalCost,
    totalPnL,
    totalPnLPercent,
    positionCount,
    cash,
    dailyChange,
    allocation,
    // Actions
    fetchSummary,
    fetchPositions,
    fetchAll,
    updatePosition,
    addPosition,
    removePosition
  }
})
