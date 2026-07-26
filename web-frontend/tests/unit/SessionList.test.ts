import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockList, mockPush } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockPush: vi.fn(),
}))

vi.mock('@/services/api/agentSession', () => ({
  agentSessionApi: { list: mockList },
}))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ path: '/agent-session/list' }),
}))

import SessionList from '@/views/AgentSession/SessionList.vue'

const sessions = [
  {
    session_key: 'agent:main:wake:e2e', channel: 'wake', peer_id: 'e2e', agent_id: 'main',
    started_at: '2026-07-26T10:00:00Z', last_active_at: '2026-07-26T11:00:00Z',
    status: 'active', message_count: 3, tool_call_count: 5, error_count: 0,
  },
  {
    session_key: 'agent:main:feishu:oc_x', channel: 'feishu', peer_id: 'oc_x', agent_id: 'main',
    started_at: '2026-07-26T09:00:00Z', last_active_at: '2026-07-26T09:30:00Z',
    status: 'idle', message_count: 12, tool_call_count: 34, error_count: 2,
  },
]

const globalStubs = {
  stubs: {
    'el-table': { template: '<div><slot /></div>' },
    'el-table-column': true,
    'el-tag': { template: '<span><slot /></span>' },
    'el-select': true,
    'el-option': true,
    'el-button': { template: '<button><slot /></button>' },
    'el-empty': { template: '<div class="empty">暂无数据</div>' },
    'el-icon': true,
  },
}

describe('SessionList', () => {
  beforeEach(() => vi.clearAllMocks())

  it('加载并渲染会话列表', async () => {
    mockList.mockResolvedValue({ sessions, total: 2 })
    const wrapper = mount(SessionList, { global: globalStubs })
    await flushPromises()

    expect(mockList).toHaveBeenCalled()
    const vm = wrapper.vm as any
    expect(vm.sessions).toHaveLength(2)
    expect(vm.sessions[0].session_key).toBe('agent:main:wake:e2e')
  })

  it('点击行跳转到详情页（encodeURIComponent）', async () => {
    mockList.mockResolvedValue({ sessions, total: 2 })
    const wrapper = mount(SessionList, { global: globalStubs })
    await flushPromises()

    ;(wrapper.vm as any).goDetail(sessions[0])
    expect(mockPush).toHaveBeenCalledWith('/agent-session/agent%3Amain%3Awake%3Ae2e')
  })

  it('通道筛选传给 API', async () => {
    mockList.mockResolvedValue({ sessions: [], total: 0 })
    const wrapper = mount(SessionList, { global: globalStubs })
    await flushPromises()
    mockList.mockClear()

    const vm = wrapper.vm as any
    vm.channelFilter = 'wake'
    await vm.loadSessions()
    expect(mockList).toHaveBeenCalledWith(
      expect.objectContaining({ channel: 'wake' })
    )
  })
})
