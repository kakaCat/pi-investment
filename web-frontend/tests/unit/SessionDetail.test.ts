import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockGetEvents, mockGetDiagnosis, mockAiDiagnosis } = vi.hoisted(() => ({
  mockGetEvents: vi.fn(),
  mockGetDiagnosis: vi.fn(),
  mockAiDiagnosis: vi.fn(),
}))

vi.mock('@/services/api/agentSession', () => ({
  agentSessionApi: {
    getEvents: mockGetEvents,
    getDiagnosis: mockGetDiagnosis,
    aiDiagnosis: mockAiDiagnosis,
  },
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { key: 'agent%3Amain%3Awake%3Ae2e' }, path: '/agent-session/x' }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@/composables/useChart', () => ({
  useChart: () => ({ chartRef: { value: null }, setOption: vi.fn() }),
}))

import SessionDetail from '@/views/AgentSession/SessionDetail.vue'

const eventsResp = {
  events: [
    { seq: 1, event_type: 'session_start', payload: { channel: 'wake', peerId: 'e2e' }, created_at: 't1' },
    { seq: 2, event_type: 'user_message', payload: { text: '分析一下', messageId: 'm1' }, created_at: 't2' },
    { seq: 3, event_type: 'tool_call', payload: { toolName: 'pool_manage', durationMs: 100, success: true }, created_at: 't3' },
    { seq: 4, event_type: 'assistant_reply', payload: { text: '结论', replyLength: 2 }, created_at: 't4' },
  ],
  total: 4,
}

const diagnosisResp = {
  session_key: 'agent:main:wake:e2e',
  tool_success_rate: 0.9, tool_call_count: 10, avg_tool_duration_ms: 800, max_tool_duration_ms: 3000,
  error_count: 1, top_errors: [{ message: 'timeout', cnt: 1 }],
  decisions: [{ decision_id: 'd1', decision_type: 'create_pool', reasoning: 'r', evaluation_status: 'pending', success: null }],
  insight: '会话健康',
}

const globalStubs = {
  stubs: {
    'el-card': { template: '<div><slot name="header" /><slot /></div>' },
    'el-tabs': { template: '<div><slot /></div>' },
    'el-tab-pane': { template: '<div><slot /></div>' },
    'el-timeline': { template: '<div><slot /></div>' },
    'el-timeline-item': { template: '<div><slot /></div>' },
    'el-tag': { template: '<span><slot /></span>' },
    'el-alert': { template: '<div><slot /></div>' },
    'el-table': { template: '<div><slot /></div>' },
    'el-table-column': true,
    'el-empty': true,
    'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
    'el-select': true,
    'el-option': true,
    'el-icon': true,
  },
}

describe('SessionDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetEvents.mockResolvedValue(eventsResp)
    mockGetDiagnosis.mockResolvedValue(diagnosisResp)
  })

  it('加载事件流并分组为回合', async () => {
    const wrapper = mount(SessionDetail, { global: globalStubs })
    await flushPromises()

    expect(mockGetEvents).toHaveBeenCalledWith('agent:main:wake:e2e', expect.anything())
    const vm = wrapper.vm as any
    expect(vm.turns).toHaveLength(1)
    expect(vm.turns[0].userText).toBe('分析一下')
    expect(vm.turns[0].toolCalls).toHaveLength(1)
    expect(vm.turns[0].reply).toBe('结论')
  })

  it('加载诊断数据', async () => {
    const wrapper = mount(SessionDetail, { global: globalStubs })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.diagnosis.tool_success_rate).toBe(0.9)
    expect(vm.diagnosis.insight).toBe('会话健康')
  })

  it('AI 诊断按钮调用接口并展示结果', async () => {
    mockAiDiagnosis.mockResolvedValue({ analysis: '做得好：…\n问题：…\n建议：…', generated_at: 't', cached: false })
    const wrapper = mount(SessionDetail, { global: globalStubs })
    await flushPromises()

    const vm = wrapper.vm as any
    await vm.runAiDiagnosis()
    expect(mockAiDiagnosis).toHaveBeenCalledWith('agent:main:wake:e2e', false)
    expect(vm.aiResult.analysis).toContain('做得好')
  })

  it('session_key 从路由参数 decode', async () => {
    const wrapper = mount(SessionDetail, { global: globalStubs })
    await flushPromises()
    expect((wrapper.vm as any).sessionKey).toBe('agent:main:wake:e2e')
  })
})
