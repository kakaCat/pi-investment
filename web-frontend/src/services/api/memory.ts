import { apiClient } from './client'

/**
 * 统一记忆服务 API（W1.6 web 记忆面板）
 *
 * 契约说明（已实测生产 5001，2026-08-13）：
 * - /api/memory/* 返回**裸 JSON**（无 {success,data} 信封），拦截器原样透传
 * - /api/scheduler/runs 返回 { success, runs }（有 success 无 data，同样原样透传）
 * - 条目字段为 snake_case，勿 camelize（拦截器不做 key 转换）
 */

export type MemoryKind = 'rule' | 'episode' | 'experience' | 'stock_note'
export type MemoryStatus = 'testing' | 'active' | 'deprecated' | 'archived'

export interface MemoryEntry {
  id: number
  kind: MemoryKind
  scope: string
  title: string
  content: string
  payload: Record<string, any> | null
  evidence: Record<string, any> | null
  status: MemoryStatus
  confidence: number
  validation_count: number
  success_count: number
  provenance: {
    session_kind?: string
    channel?: string
    session_id?: string
  } | null
  last_recalled_at: string | null
  source: string | null
  supersedes: number | null
  /** 检索命中时带：bm25 | vector | both */
  match_source?: string
  score?: number
  created_at: string
  updated_at: string
}

export interface MemorySearchResponse {
  items: MemoryEntry[]
  total: number
  /** true = ollama 不可达，已降级为纯 BM25 */
  degraded: boolean
  strategy: 'hybrid' | 'bm25' | 'vector' | 'filter' | 'none'
}

export interface SchedulerRun {
  id: number
  taskId: number
  taskName: string
  status: string
  triggeredAt: string | null
  startedAt: string | null
  finishedAt: string | null
  durationMs: number | null
  error: string | null
  payload?: Record<string, any> | null
}

export const memoryApi = {
  /** 检索记忆（带 q 走混合检索；不带 q 为过滤列举） */
  search(params: {
    q?: string
    kind?: string
    status?: string
    scope?: string
    limit?: number
  }) {
    return apiClient.get<MemorySearchResponse>('/api/memory/search', { params })
  },

  /** 单条详情 */
  get(id: number) {
    return apiClient.get<MemoryEntry>(`/api/memory/${id}`)
  },

  /** 确认生效：验证成功 + 提升 testing → active */
  promote(id: number) {
    return apiClient.post<MemoryEntry>(`/api/memory/${id}/validate`, {
      success: true,
      promote: true,
    })
  },

  /** 废弃（无替代品场景；status → deprecated，不再参与召回） */
  deprecate(id: number) {
    return apiClient.post<MemoryEntry>(`/api/memory/${id}/deprecate`, {})
  },
}

export const schedulerRunApi = {
  /** 调度运行记录（近 N 条，用于 T4.4 观测简表） */
  listRuns(limit = 50) {
    return apiClient.get<{ success: boolean; runs: SchedulerRun[] }>(
      '/api/scheduler/runs',
      { params: { limit }, silent: true }
    )
  },
}

/** 决策详情（证据链下钻用，/api/decisions/{id}） */
export function fetchDecision(decisionId: number | string) {
  return apiClient.get<Record<string, any>>(`/api/decisions/${encodeURIComponent(String(decisionId))}`, {
    silent: true,
  })
}
