import { apiClient } from './client'
import type { AgentSession, SessionEvent, SessionDiagnosis, AiDiagnosis } from '@/types'

const enc = encodeURIComponent

export const agentSessionApi = {
  /** 会话列表（活跃时间倒序） */
  list(params?: { channel?: string; limit?: number }) {
    return apiClient.get<{ sessions: AgentSession[]; total: number }>('/api/sessions', { params })
  },

  /** 会话详情 */
  get(key: string) {
    return apiClient.get<AgentSession>(`/api/sessions/${enc(key)}`)
  },

  /** 会话事件流（回放数据源） */
  getEvents(key: string, params?: { event_type?: string; limit?: number; offset?: number }) {
    return apiClient.get<{ events: SessionEvent[]; total: number }>(
      `/api/sessions/${enc(key)}/events`,
      { params }
    )
  },

  /** 规则化诊断指标 */
  getDiagnosis(key: string) {
    return apiClient.get<SessionDiagnosis>(`/api/sessions/${enc(key)}/diagnosis`)
  },

  /** AI 诊断（DeepSeek，约 30s；refresh=true 强制重新生成） */
  aiDiagnosis(key: string, refresh = false) {
    const qs = refresh ? '?refresh=true' : ''
    return apiClient.post<AiDiagnosis>(`/api/sessions/${enc(key)}/ai-diagnosis${qs}`, {})
  },
}
