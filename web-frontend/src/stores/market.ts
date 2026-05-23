import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { StockInfo, KLineData, RealtimeQuote } from '@/types'

export const useMarketStore = defineStore('market', () => {
  // State
  const stocks = ref<StockInfo[]>([])
  const currentStock = ref<StockInfo | null>(null)
  const klineData = ref<KLineData[]>([])
  const realtimeQuotes = ref<Map<string, RealtimeQuote>>(new Map())
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const getQuote = computed(() => (symbol: string) => {
    return realtimeQuotes.value.get(symbol)
  })

  // Actions
  const fetchStocks = async (_params?: any) => {
    loading.value = true
    error.value = null
    try {
      // TODO: 调用API
      // const response = await marketApi.getStocks(_params)
      // stocks.value = response.items
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const fetchStockDetail = async (_symbol: string) => {
    loading.value = true
    error.value = null
    try {
      // TODO: 调用API
      // currentStock.value = await marketApi.getStockDetail(_symbol)
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const fetchKLineData = async (_symbol: string, _timeFrame: string, _startDate?: string, _endDate?: string) => {
    loading.value = true
    error.value = null
    try {
      // TODO: 调用API
      // klineData.value = await marketApi.getKLineData({ symbol: _symbol, timeFrame: _timeFrame, startDate: _startDate, endDate: _endDate })
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const updateRealtimeQuote = (quote: RealtimeQuote) => {
    realtimeQuotes.value.set(quote.symbol, quote)
  }

  const subscribeSymbol = (symbol: string) => {
    // TODO: WebSocket订阅
    console.log('Subscribe to', symbol)
  }

  const unsubscribeSymbol = (symbol: string) => {
    // TODO: WebSocket取消订阅
    console.log('Unsubscribe from', symbol)
  }

  return {
    // State
    stocks,
    currentStock,
    klineData,
    realtimeQuotes,
    loading,
    error,
    // Getters
    getQuote,
    // Actions
    fetchStocks,
    fetchStockDetail,
    fetchKLineData,
    updateRealtimeQuote,
    subscribeSymbol,
    unsubscribeSymbol
  }
})
