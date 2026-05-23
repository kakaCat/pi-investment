import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { signalApi } from '@/services/api/signal'
import type { TradingSignal, SignalFilters } from '@/types/models'
import { SignalStatus } from '@/types/enums'

export const useSignalStore = defineStore('signals', () => {
  // State
  const signals = ref<TradingSignal[]>([])
  const currentSignal = ref<TradingSignal | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  // Getters
  const pendingSignals = computed(() =>
    signals.value.filter(s => s.status === 'pending')
  )

  const approvedSignals = computed(() =>
    signals.value.filter(s => s.status === 'approved')
  )

  const executedSignals = computed(() =>
    signals.value.filter(s => s.status === 'executed')
  )

  const signalStats = computed(() => ({
    total: signals.value.length,
    pending: pendingSignals.value.length,
    approved: approvedSignals.value.length,
    executed: executedSignals.value.length,
    avgConfidence: signals.value.length > 0
      ? signals.value.reduce((sum, s) => sum + s.confidence, 0) / signals.value.length
      : 0
  }))

  // Actions
  const fetchSignals = async (filters?: SignalFilters) => {
    loading.value = true
    error.value = null
    try {
      const response = await signalApi.getSignals(filters)
      signals.value = response.items
      total.value = response.total
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const fetchSignalById = async (id: string) => {
    loading.value = true
    error.value = null
    try {
      currentSignal.value = await signalApi.getSignalById(id)
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const approveSignal = async (signalId: string) => {
    try {
      await signalApi.approveSignal(signalId)
      const signal = signals.value.find(s => s.id === signalId)
      if (signal) {
        signal.status = SignalStatus.APPROVED
      }
    } catch (e: any) {
      error.value = e.message
      throw e
    }
  }

  const rejectSignal = async (signalId: string, reason: string) => {
    try {
      await signalApi.rejectSignal(signalId, reason)
      const signal = signals.value.find(s => s.id === signalId)
      if (signal) {
        signal.status = SignalStatus.REJECTED
      }
    } catch (e: any) {
      error.value = e.message
      throw e
    }
  }

  const markError = async (signalId: string, errorType: string) => {
    try {
      await signalApi.markError(signalId, errorType)
    } catch (e: any) {
      error.value = e.message
      throw e
    }
  }

  return {
    // State
    signals,
    currentSignal,
    loading,
    error,
    total,
    // Getters
    pendingSignals,
    approvedSignals,
    executedSignals,
    signalStats,
    // Actions
    fetchSignals,
    fetchSignalById,
    approveSignal,
    rejectSignal,
    markError
  }
})
