import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Position } from '@/types'

export const usePortfolioStore = defineStore('portfolio', () => {
  // State
  const positions = ref<Position[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const totalValue = computed(() =>
    positions.value.reduce((sum, p) => sum + p.marketValue, 0)
  )

  const totalCost = computed(() =>
    positions.value.reduce((sum, p) => sum + p.avgCost * p.quantity, 0)
  )

  const totalPnL = computed(() => totalValue.value - totalCost.value)

  const totalPnLPercent = computed(() =>
    totalCost.value > 0 ? (totalPnL.value / totalCost.value) * 100 : 0
  )

  const positionCount = computed(() => positions.value.length)

  const allocation = computed(() => {
    const total = totalValue.value
    return positions.value.map(p => ({
      symbol: p.symbol,
      symbolName: p.symbolName,
      value: p.marketValue,
      weight: total > 0 ? (p.marketValue / total) * 100 : 0
    }))
  })

  // Actions
  const fetchPositions = async () => {
    loading.value = true
    error.value = null
    try {
      // TODO: 调用API
      // const response = await portfolioApi.getPositions()
      // positions.value = response
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
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
    loading,
    error,
    // Getters
    totalValue,
    totalCost,
    totalPnL,
    totalPnLPercent,
    positionCount,
    allocation,
    // Actions
    fetchPositions,
    updatePosition,
    addPosition,
    removePosition
  }
})
