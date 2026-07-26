import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/services/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import { apiClient } from '@/services/api/client'
import { agentSessionApi } from '@/services/api/agentSession'

describe('agentSessionApi', () => {
  beforeEach(() => vi.clearAllMocks())

  it('list 带 channel 参数', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ sessions: [], total: 0 })
    await agentSessionApi.list({ channel: 'wake', limit: 20 })
    expect(apiClient.get).toHaveBeenCalledWith('/api/sessions', {
      params: { channel: 'wake', limit: 20 },
    })
  })

  it('getEvents 对 session_key 做 encodeURIComponent', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ events: [], total: 0 })
    await agentSessionApi.getEvents('agent:main:wake:e2e', { event_type: 'tool_call' })
    const url = vi.mocked(apiClient.get).mock.calls[0][0] as string
    expect(url).toBe('/api/sessions/agent%3Amain%3Awake%3Ae2e/events')
  })

  it('getDiagnosis 拼接正确路径', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({})
    await agentSessionApi.getDiagnosis('agent:main:wake:e2e')
    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/sessions/agent%3Amain%3Awake%3Ae2e/diagnosis'
    )
  })

  it('aiDiagnosis POST 且 refresh 走 query', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ analysis: 'a', generated_at: 't', cached: false })
    await agentSessionApi.aiDiagnosis('agent:main:wake:e2e', true)
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/sessions/agent%3Amain%3Awake%3Ae2e/ai-diagnosis?refresh=true',
      {}
    )
  })
})
