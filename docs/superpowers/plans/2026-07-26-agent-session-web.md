# Agent Session Web 可视化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 web-frontend 新增"Agent 会话"可视化（列表+详情钻取：回放/智能诊断），v2 新增 AI 诊断端点。

**Architecture:** 纯前端只读消费现有 `/api/sessions` API（apiClient + usePolling + el-timeline + useChart）；回放加工为前端纯函数；AI 诊断为 v2 新端点（DeepSeek + 结果缓存）。设计：`docs/superpowers/specs/2026-07-25-agent-session-web-design.md`

**Tech Stack:** Vue 3 `<script setup>` + Element Plus + Pinia（本 feature 不需要 store）+ vitest/happy-dom；v2: Flask + pytest。

**分支**：`feature/agent-session-web`（已从 feature/agent-gateway 切出，含 spec commit `a3d6f5e`）。

**关键模式（必须遵循）**：
- API 层：`apiClient.get<T>(url, { params })` / `apiClient.post<T>(url, data)`，拦截器已自动解包 `{success, data}` → 直接返回 data
- 测试只收 `tests/**/*.test.ts`；组件测试用 `mount` + `global.stubs` + `vi.mock('@/services/api/...')`
- 图表：`useChart()` 返回 `{ chartRef, setOption }`；轮询：`usePolling(callback, interval)`

---

### Task 1: 类型定义 + agentSession API 服务

**Files:**
- Modify: `web-frontend/src/types/models.ts`（尾部追加类型）
- Create: `web-frontend/src/services/api/agentSession.ts`
- Modify: `web-frontend/src/services/api/index.ts`（加一行导出）
- Test: `web-frontend/tests/services/agentSession.test.ts`

- [ ] **Step 1: models.ts 尾部追加**

```typescript
// ===== Agent Session 可视化（2026-07-26）=====

export interface AgentSession {
  session_key: string
  channel: 'wake' | 'feishu' | 'cli' | string
  peer_id: string
  agent_id: string
  started_at: string
  last_active_at: string
  status: 'active' | 'idle' | string
  message_count: number
  tool_call_count: number
  error_count: number
}

export interface SessionEvent {
  seq: number
  event_type: 'session_start' | 'user_message' | 'tool_call' | 'assistant_reply' | 'error' | 'session_idle' | 'legacy_note' | string
  payload: Record<string, any>
  created_at: string
}

export interface SessionDiagnosis {
  session_key: string
  tool_success_rate: number | null
  tool_call_count: number
  avg_tool_duration_ms: number
  max_tool_duration_ms: number
  error_count: number
  top_errors: Array<{ message: string; cnt: number }>
  decisions: Array<{
    decision_id: string
    decision_type: string
    reasoning: string | null
    evaluation_status: string
    success: boolean | null
  }>
  insight: string
}

export interface AiDiagnosis {
  analysis: string
  generated_at: string
  cached: boolean
}
```

- [ ] **Step 2: 写失败测试**

```typescript
// web-frontend/tests/services/agentSession.test.ts
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
```

- [ ] **Step 3: 运行确认失败**

Run: `cd web-frontend && npx vitest run tests/services/agentSession.test.ts 2>&1 | tail -3`
Expected: FAIL — 找不到模块 `@/services/api/agentSession`

- [ ] **Step 4: 实现**

```typescript
// web-frontend/src/services/api/agentSession.ts
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
```

`src/services/api/index.ts` 追加一行：

```typescript
export { agentSessionApi } from './agentSession'
```

（同时确认 `@/types` 的 barrel `src/types/index.ts` 已 re-export models.ts——现有 `AgentLog` 可从 `@/types` 导入说明已通；若没有则加 `export * from './models'`。）

- [ ] **Step 5: 运行确认通过并 commit**

Run: `cd web-frontend && npx vitest run tests/services/agentSession.test.ts 2>&1 | tail -3`
Expected: 4 passed

```bash
cd web-frontend && git add src/types/models.ts src/services/api/agentSession.ts src/services/api/index.ts src/types/index.ts tests/services/agentSession.test.ts
git commit -m "feat(session-web): 类型与 agentSession API 服务"
```

---

### Task 2: 回放加工纯函数 groupEventsToTurns

**Files:**
- Create: `web-frontend/src/services/agentSession/replay.ts`
- Test: `web-frontend/tests/unit/replay.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// web-frontend/tests/unit/replay.test.ts
import { describe, it, expect } from 'vitest'
import { groupEventsToTurns, type Turn } from '@/services/agentSession/replay'
import type { SessionEvent } from '@/types'

const ev = (seq: number, event_type: string, payload: any = {}): SessionEvent => ({
  seq, event_type, payload, created_at: `2026-07-26T10:00:0${seq}Z`,
})

describe('groupEventsToTurns', () => {
  it('按 user_message 切分回合，工具与错误挂进回合，assistant_reply 收尾', () => {
    const events = [
      ev(1, 'session_start', { channel: 'wake', peerId: 'e2e' }),
      ev(2, 'user_message', { text: '分析一下', messageId: 'm1' }),
      ev(3, 'tool_call', { toolName: 'a', durationMs: 100, success: true }),
      ev(4, 'tool_call', { toolName: 'b', durationMs: 300, success: false, error: 'timeout' }),
      ev(5, 'assistant_reply', { text: '结论', replyLength: 2 }),
      ev(6, 'user_message', { text: '再来一次', messageId: 'm2' }),
      ev(7, 'error', { stage: 'prompt', message: 'boom' }),
    ]
    const turns = groupEventsToTurns(events)
    expect(turns).toHaveLength(2)
    expect(turns[0].userText).toBe('分析一下')
    expect(turns[0].toolCalls).toHaveLength(2)
    expect(turns[0].reply).toBe('结论')
    expect(turns[1].userText).toBe('再来一次')
    expect(turns[1].errors).toHaveLength(1)
    expect(turns[1].reply).toBeNull()
  })

  it('session_start 作为独立头部信息返回', () => {
    const turns = groupEventsToTurns([ev(1, 'session_start', { channel: 'wake' })])
    expect(turns).toHaveLength(0)
  })

  it('空事件流返回空数组', () => {
    expect(groupEventsToTurns([])).toEqual([])
  })

  it('乱序 seq 先排序再分组', () => {
    const events = [
      ev(5, 'assistant_reply', { text: 'r', replyLength: 1 }),
      ev(2, 'user_message', { text: 'q', messageId: 'm' }),
      ev(3, 'tool_call', { toolName: 'a', durationMs: 1, success: true }),
    ]
    const turns = groupEventsToTurns(events)
    expect(turns[0].userText).toBe('q')
    expect(turns[0].toolCalls).toHaveLength(1)
    expect(turns[0].reply).toBe('r')
  })

  it('没有 user_message 的孤儿工具调用归入 turn 0（userText 为空）', () => {
    const turns = groupEventsToTurns([
      ev(1, 'tool_call', { toolName: 'a', durationMs: 1, success: true }),
    ])
    expect(turns).toHaveLength(1)
    expect(turns[0].userText).toBeNull()
    expect(turns[0].toolCalls).toHaveLength(1)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd web-frontend && npx vitest run tests/unit/replay.test.ts 2>&1 | tail -3`
Expected: FAIL — 找不到模块

- [ ] **Step 3: 实现**

```typescript
// web-frontend/src/services/agentSession/replay.ts
/**
 * 会话回放加工：事件流 → 回合结构（纯函数）
 * 按 user_message 切分回合；回合内挂 tool_call/error；assistant_reply 收尾
 */
import type { SessionEvent } from '@/types'

export interface ToolCallItem {
  toolName: string
  durationMs: number
  success: boolean
  error?: string
  seq: number
}

export interface Turn {
  userText: string | null
  userTime: string | null
  toolCalls: ToolCallItem[]
  errors: Array<{ stage: string; message: string; time: string }>
  reply: string | null
  replyTime: string | null
}

export function groupEventsToTurns(events: SessionEvent[]): Turn[] {
  const sorted = [...events].sort((a, b) => a.seq - b.seq)
  const turns: Turn[] = []
  let current: Turn | null = null

  const ensureTurn = (): Turn => {
    if (!current) {
      current = { userText: null, userTime: null, toolCalls: [], errors: [], reply: null, replyTime: null }
      turns.push(current)
    }
    return current
  }

  for (const e of sorted) {
    switch (e.event_type) {
      case 'user_message':
        current = {
          userText: e.payload.text ?? '',
          userTime: e.created_at,
          toolCalls: [], errors: [], reply: null, replyTime: null,
        }
        turns.push(current)
        break
      case 'tool_call':
        ensureTurn().toolCalls.push({
          toolName: e.payload.toolName ?? 'unknown',
          durationMs: e.payload.durationMs ?? 0,
          success: !!e.payload.success,
          error: e.payload.error,
          seq: e.seq,
        })
        break
      case 'assistant_reply':
        ensureTurn().reply = e.payload.text ?? ''
        ensureTurn().replyTime = e.created_at
        break
      case 'error':
        ensureTurn().errors.push({
          stage: e.payload.stage ?? '',
          message: e.payload.message ?? '',
          time: e.created_at,
        })
        break
      default:
        // session_start / session_idle / legacy_note 不进回合
        break
    }
  }
  return turns
}
```

- [ ] **Step 4: 运行确认通过并 commit**

Run: `cd web-frontend && npx vitest run tests/unit/replay.test.ts 2>&1 | tail -3`
Expected: 5 passed

```bash
cd web-frontend && git add src/services/agentSession/replay.ts tests/unit/replay.test.ts
git commit -m "feat(session-web): 回放加工纯函数 groupEventsToTurns"
```

---

### Task 3: SessionList.vue 会话列表页

**Files:**
- Create: `web-frontend/src/views/AgentSession/SessionList.vue`
- Test: `web-frontend/tests/unit/SessionList.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// web-frontend/tests/unit/SessionList.test.ts
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd web-frontend && npx vitest run tests/unit/SessionList.test.ts 2>&1 | tail -3`
Expected: FAIL — 找不到组件

- [ ] **Step 3: 实现**

```vue
<!-- web-frontend/src/views/AgentSession/SessionList.vue -->
<template>
  <div class="session-list-page">
    <el-card>
      <template #header>
        <div class="header-row">
          <span class="title">Agent 会话</span>
          <div class="actions">
            <el-select v-model="channelFilter" placeholder="全部通道" clearable style="width: 140px" @change="loadSessions">
              <el-option label="全部" value="" />
              <el-option label="Wake" value="wake" />
              <el-option label="飞书" value="feishu" />
              <el-option label="CLI" value="cli" />
            </el-select>
            <el-button :loading="loading" @click="loadSessions">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="sessions" v-loading="loading" @row-click="goDetail" style="cursor: pointer">
        <el-table-column label="会话" min-width="280">
          <template #default="{ row }">
            <span :title="row.session_key">{{ shortenKey(row.session_key) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="通道" width="100">
          <template #default="{ row }">
            <el-tag :type="channelTagType(row.channel)" size="small">{{ channelLabel(row.channel) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message_count" label="消息" width="80" align="center" />
        <el-table-column prop="tool_call_count" label="工具" width="80" align="center" />
        <el-table-column label="错误" width="80" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.error_count > 0 ? '#f56c6c' : 'inherit', fontWeight: row.error_count > 0 ? 600 : 400 }">
              {{ row.error_count }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最后活跃" width="160">
          <template #default="{ row }">{{ formatTime(row.last_active_at) }}</template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && sessions.length === 0" description="暂无会话记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { agentSessionApi } from '@/services/api/agentSession'
import { usePolling } from '@/composables/usePolling'
import type { AgentSession } from '@/types'

const router = useRouter()
const sessions = ref<AgentSession[]>([])
const loading = ref(false)
const channelFilter = ref('')

async function loadSessions() {
  loading.value = true
  try {
    const params: { channel?: string; limit: number } = { limit: 50 }
    if (channelFilter.value) params.channel = channelFilter.value
    const data = await agentSessionApi.list(params)
    sessions.value = data.sessions
  } finally {
    loading.value = false
  }
}

usePolling(loadSessions, 30000)

function goDetail(row: AgentSession) {
  router.push(`/agent-session/${encodeURIComponent(row.session_key)}`)
}

function shortenKey(key: string): string {
  return key.length > 40 ? key.slice(0, 24) + '…' + key.slice(-12) : key
}

const channelLabel = (c: string) => ({ wake: 'Wake', feishu: '飞书', cli: 'CLI' }[c] ?? c)
const channelTagType = (c: string) => (({ wake: 'primary', feishu: 'success', cli: 'info' } as Record<string, any>)[c] ?? 'info')

function formatTime(iso: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  const diffMin = Math.floor((Date.now() - d.getTime()) / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)} 小时前`
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 600; }
.actions { display: flex; gap: 8px; }
</style>
```

- [ ] **Step 4: 运行确认通过并 commit**

Run: `cd web-frontend && npx vitest run tests/unit/SessionList.test.ts 2>&1 | tail -3`
Expected: 3 passed

```bash
cd web-frontend && git add src/views/AgentSession/SessionList.vue tests/unit/SessionList.test.ts
git commit -m "feat(session-web): 会话列表页"
```

---

### Task 4: SessionDetail.vue 详情页（回放 + 诊断两个 tab）

**Files:**
- Create: `web-frontend/src/views/AgentSession/SessionDetail.vue`
- Test: `web-frontend/tests/unit/SessionDetail.test.ts`

说明：单文件两个 tab。回放 tab 用 groupEventsToTurns + el-timeline；诊断 tab 用指标卡 + useChart 慢工具 TOP5 + 错误/决策表 + AI 诊断按钮。

- [ ] **Step 1: 写失败测试**

```typescript
// web-frontend/tests/unit/SessionDetail.test.ts
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd web-frontend && npx vitest run tests/unit/SessionDetail.test.ts 2>&1 | tail -3`
Expected: FAIL — 找不到组件

- [ ] **Step 3: 实现**

```vue
<!-- web-frontend/src/views/AgentSession/SessionDetail.vue -->
<template>
  <div class="session-detail-page">
    <el-card>
      <template #header>
        <div class="header-row">
          <span class="title" :title="sessionKey">{{ sessionKey }}</span>
          <el-button size="small" :loading="loading" @click="loadAll">刷新</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- ============ Tab 1: 会话回放 ============ -->
        <el-tab-pane label="会话回放" name="replay">
          <div class="filter-row">
            <el-select v-model="eventFilter" size="small" style="width: 130px">
              <el-option label="全部" value="" />
              <el-option label="仅对话" value="dialog" />
              <el-option label="仅工具" value="tool" />
              <el-option label="仅错误" value="error" />
            </el-select>
          </div>

          <el-empty v-if="!loading && filteredTurns.length === 0" description="该会话暂无事件" />

          <el-timeline v-else>
            <template v-for="(turn, i) in filteredTurns" :key="i">
              <el-timeline-item v-if="turn.userText !== null && showDialog" type="primary" :timestamp="formatTime(turn.userTime)">
                <div class="user-msg">👤 {{ turn.userText }}</div>
              </el-timeline-item>

              <el-timeline-item
                v-for="tc in (showTool ? turn.toolCalls : [])"
                :key="`tc-${tc.seq}`"
                :type="tc.success ? 'success' : 'danger'"
                size="small"
              >
                🔧 {{ tc.toolName }}
                <el-tag size="small" :type="tc.success ? 'success' : 'danger'">
                  {{ tc.success ? '✓' : '✗' }} {{ tc.durationMs }}ms
                </el-tag>
                <span v-if="tc.error" class="err-text">{{ tc.error }}</span>
              </el-timeline-item>

              <el-timeline-item v-if="turn.reply && showDialog" type="success" :timestamp="formatTime(turn.replyTime)">
                <div class="reply" :class="{ collapsed: isCollapsed(i) }">🤖 {{ turn.reply }}</div>
                <el-button v-if="turn.reply.length > 200" link type="primary" size="small" @click="toggleCollapse(i)">
                  {{ isCollapsed(i) ? '展开全文' : '收起' }}
                </el-button>
              </el-timeline-item>

              <el-timeline-item
                v-for="(err, j) in (showError ? turn.errors : [])"
                :key="`err-${j}`"
                type="danger"
                :timestamp="formatTime(err.time)"
              >
                ⚠️ [{{ err.stage }}] {{ err.message }}
              </el-timeline-item>
            </template>
          </el-timeline>
        </el-tab-pane>

        <!-- ============ Tab 2: 智能诊断 ============ -->
        <el-tab-pane label="智能诊断" name="diagnosis">
          <div v-if="diagnosis" class="diagnosis-body">
            <div class="metric-cards">
              <el-card class="metric"><div class="metric-value">{{ rateText }}</div><div class="metric-label">工具成功率</div></el-card>
              <el-card class="metric"><div class="metric-value">{{ diagnosis.tool_call_count }}</div><div class="metric-label">工具调用</div></el-card>
              <el-card class="metric"><div class="metric-value">{{ diagnosis.avg_tool_duration_ms }}ms</div><div class="metric-label">平均耗时</div></el-card>
              <el-card class="metric"><div class="metric-value" :style="{ color: diagnosis.error_count > 0 ? '#f56c6c' : 'inherit' }">{{ diagnosis.error_count }}</div><div class="metric-label">错误</div></el-card>
            </div>

            <el-alert v-if="diagnosis.insight" :title="diagnosis.insight" type="info" :closable="false" class="mt-12" />

            <!-- AI 诊断 -->
            <div class="ai-section mt-12">
              <el-button type="primary" :loading="aiLoading" @click="runAiDiagnosis">
                {{ aiResult ? '重新生成 AI 诊断' : 'AI 诊断' }}
              </el-button>
              <span v-if="aiResult" class="ai-time">{{ aiResult.cached ? '缓存于' : '生成于' }} {{ formatTime(aiResult.generated_at) }}</span>
              <el-alert v-if="aiError" :title="aiError" type="error" :closable="false" class="mt-12" />
              <div v-if="aiResult" class="ai-result mt-12">{{ aiResult.analysis }}</div>
            </div>

            <div class="panels mt-20">
              <div class="panel">
                <h4>慢工具 TOP5</h4>
                <div ref="chartRef" class="chart"></div>
              </div>
              <div class="panel">
                <h4>错误聚类</h4>
                <el-table :data="diagnosis.top_errors" size="small">
                  <el-table-column prop="message" label="错误" min-width="200" />
                  <el-table-column prop="cnt" label="次数" width="80" align="center" />
                </el-table>
                <el-empty v-if="diagnosis.top_errors.length === 0" description="无错误" :image-size="60" />
              </div>
            </div>

            <h4 class="mt-20">关联决策</h4>
            <el-table :data="diagnosis.decisions" size="small">
              <el-table-column prop="decision_type" label="类型" width="140" />
              <el-table-column prop="reasoning" label="理由" min-width="240" show-overflow-tooltip />
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="statusTagType(row)">{{ statusLabel(row) }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="diagnosis.decisions.length === 0" description="无关联决策" :image-size="60" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { agentSessionApi } from '@/services/api/agentSession'
import { groupEventsToTurns, type Turn } from '@/services/agentSession/replay'
import { useChart } from '@/composables/useChart'
import type { SessionDiagnosis, AiDiagnosis, SessionEvent } from '@/types'

const route = useRoute()
const sessionKey = decodeURIComponent(route.params.key as string)

const activeTab = ref('replay')
const loading = ref(false)
const events = ref<SessionEvent[]>([])
const turns = ref<Turn[]>([])
const diagnosis = ref<SessionDiagnosis | null>(null)
const eventFilter = ref('')

const aiLoading = ref(false)
const aiResult = ref<AiDiagnosis | null>(null)
const aiError = ref('')

const collapsedSet = ref<Set<number>>(new Set())
const isCollapsed = (i: number) => !collapsedSet.value.has(i)
const toggleCollapse = (i: number) => {
  isCollapsed(i) ? collapsedSet.value.add(i) : collapsedSet.value.delete(i)
}

const showDialog = computed(() => eventFilter.value === '' || eventFilter.value === 'dialog')
const showTool = computed(() => eventFilter.value === '' || eventFilter.value === 'tool')
const showError = computed(() => eventFilter.value === '' || eventFilter.value === 'error')

const filteredTurns = computed(() => {
  if (eventFilter.value === 'error') return turns.value.filter(t => t.errors.length > 0)
  if (eventFilter.value === 'tool') return turns.value.filter(t => t.toolCalls.length > 0)
  return turns.value
})

const rateText = computed(() =>
  diagnosis.value?.tool_success_rate == null ? '-' : `${(diagnosis.value.tool_success_rate * 100).toFixed(0)}%`
)

const { chartRef, setOption } = useChart()

async function loadAll() {
  loading.value = true
  try {
    const [eventsData, diagData] = await Promise.all([
      agentSessionApi.getEvents(sessionKey, { limit: 1000 }),
      agentSessionApi.getDiagnosis(sessionKey),
    ])
    events.value = eventsData.events
    turns.value = groupEventsToTurns(eventsData.events)
    diagnosis.value = diagData
    await nextTick()
    renderSlowToolChart()
  } finally {
    loading.value = false
  }
}

function renderSlowToolChart() {
  const toolMax = new Map<string, number>()
  for (const e of events.value) {
    if (e.event_type !== 'tool_call') continue
    const name = e.payload.toolName ?? 'unknown'
    const ms = e.payload.durationMs ?? 0
    toolMax.set(name, Math.max(toolMax.get(name) ?? 0, ms))
  }
  const top5 = [...toolMax.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5)
  if (top5.length === 0) return
  setOption({
    grid: { left: 120, right: 30, top: 10, bottom: 20 },
    xAxis: { type: 'value', name: 'ms' },
    yAxis: { type: 'category', data: top5.map(([n]) => n).reverse() },
    series: [{ type: 'bar', data: top5.map(([, v]) => v).reverse(), itemStyle: { color: '#5470c6' } }],
  })
}

async function runAiDiagnosis() {
  aiLoading.value = true
  aiError.value = ''
  try {
    aiResult.value = await agentSessionApi.aiDiagnosis(sessionKey, !!aiResult.value)
  } catch (e: any) {
    aiError.value = e?.message ?? 'AI 诊断失败，请稍后重试'
  } finally {
    aiLoading.value = false
  }
}

function statusLabel(row: { evaluation_status: string; success: boolean | null }): string {
  if (row.evaluation_status === 'evaluated') return row.success ? '成功' : '失败'
  return '待评估'
}
function statusTagType(row: { evaluation_status: string; success: boolean | null }): any {
  if (row.evaluation_status === 'evaluated') return row.success ? 'success' : 'danger'
  return 'info'
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return isNaN(d.getTime()) ? String(iso) : d.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

onMounted(loadAll)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 600; font-size: 13px; word-break: break-all; }
.filter-row { margin-bottom: 12px; }
.user-msg { font-weight: 600; }
.reply.collapsed { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.err-text { color: #f56c6c; margin-left: 8px; }
.metric-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.metric { text-align: center; }
.metric-value { font-size: 24px; font-weight: 700; }
.metric-label { color: #909399; font-size: 12px; margin-top: 4px; }
.mt-12 { margin-top: 12px; }
.mt-20 { margin-top: 20px; }
.panels { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.chart { height: 200px; }
.ai-section .ai-time { margin-left: 12px; color: #909399; font-size: 12px; }
.ai-result { white-space: pre-wrap; background: #f5f7fa; padding: 16px; border-radius: 4px; line-height: 1.8; }
</style>
```

- [ ] **Step 4: 运行确认通过并 commit**

Run: `cd web-frontend && npx vitest run tests/unit/SessionDetail.test.ts 2>&1 | tail -3`
Expected: 4 passed

```bash
cd web-frontend && git add src/views/AgentSession/SessionDetail.vue tests/unit/SessionDetail.test.ts
git commit -m "feat(session-web): 会话详情页（回放 + 智能诊断）"
```

---

### Task 5: 路由与菜单注册

**Files:**
- Modify: `web-frontend/src/router/index.ts`（GameIntelligence 分组后追加）
- Modify: `web-frontend/src/components/layout/MainLayout.vue`（"博弈智能"组末尾加菜单项）
- Test: `web-frontend/tests/unit/router.test.ts`（追加一条正则断言）

- [ ] **Step 1: router/index.ts 追加分组**（放在 GameIntelligence 分组的 `]` 之后）

```typescript
      // Agent Session 可视化
      {
        path: '/agent-session',
        name: 'AgentSession',
        redirect: '/agent-session/list',
        meta: { title: 'Agent 会话' },
        children: [
          {
            path: 'list',
            name: 'AgentSessionList',
            component: () => import(/* webpackChunkName: "agent-session" */ '@/views/AgentSession/SessionList.vue'),
            meta: { title: 'Agent 会话 - 列表' }
          },
          {
            path: ':key',
            name: 'AgentSessionDetail',
            component: () => import(/* webpackChunkName: "agent-session" */ '@/views/AgentSession/SessionDetail.vue'),
            meta: { title: 'Agent 会话 - 详情' }
          }
        ]
      }
```

- [ ] **Step 2: MainLayout.vue 菜单**（`自动化配置` el-menu-item 之后、`系统运维` group-title 之前）

```html
          <el-menu-item index="/agent-session/list">
            <el-icon><ChatDotRound /></el-icon>
            <span>Agent 会话</span>
          </el-menu-item>
```

（`ChatDotRound` 来自 @element-plus/icons-vue，已在 main.ts 全局注册，无需 import。）

- [ ] **Step 3: 追加路由断言测试**

在 `tests/unit/router.test.ts` 末尾追加（先读该文件确认现有写法，保持同风格）：

```typescript
it('注册 Agent Session 路由', () => {
  const src = fs.readFileSync(routerPath, 'utf-8')
  expect(src).toContain("path: '/agent-session'")
  expect(src).toContain("redirect: '/agent-session/list'")
  expect(src).toContain("name: 'AgentSessionDetail'")
})
```

- [ ] **Step 4: 运行测试并 commit**

Run: `cd web-frontend && npx vitest run tests/unit/router.test.ts 2>&1 | tail -3`
Expected: passed

```bash
cd web-frontend && git add src/router/index.ts src/components/layout/MainLayout.vue tests/unit/router.test.ts
git commit -m "feat(session-web): 路由与菜单注册"
```

---

### Task 6: v2 AI 诊断（llm_service + 端点 + 缓存迁移）

**Files:**
- Create: `quantsys-v2/application/services/llm_service.py`
- Create: `quantsys-v2/infrastructure/persistence/migrations/add_session_ai_diagnosis.sql`
- Modify: `quantsys-v2/application/services/session_service.py`（追加 ai_diagnosis 方法）
- Modify: `quantsys-v2/adapters/inbound/api/routes/agent_sessions.py`（追加端点）
- Test: `quantsys-v2/tests/services/test_ai_diagnosis.py`

- [ ] **Step 1: 应用缓存列迁移**

```sql
-- quantsys-v2/infrastructure/persistence/migrations/add_session_ai_diagnosis.sql
-- Agent Session AI 诊断缓存（2026-07-26）
ALTER TABLE quant.agent_sessions ADD COLUMN IF NOT EXISTS ai_diagnosis JSONB;
ALTER TABLE quant.agent_sessions ADD COLUMN IF NOT EXISTS ai_diagnosis_at TIMESTAMPTZ;
```

```bash
cd quantsys-v2
psql -d quant_investment -f infrastructure/persistence/migrations/add_session_ai_diagnosis.sql
psql -d quant_test -f infrastructure/persistence/migrations/add_session_ai_diagnosis.sql
```

- [ ] **Step 2: 写失败测试**

```python
# quantsys-v2/tests/services/test_ai_diagnosis.py
"""AI 诊断端点测试：成功/超时/未配置 key/缓存命中"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from infrastructure.persistence.database.base_repository import BaseRepository
from application.services.session_service import SessionService
from tests.services.test_session_service import DDL


@pytest.fixture
def service():
    repo = BaseRepository()
    cursor = repo._get_cursor()
    cursor.execute(DDL)
    cursor.execute("ALTER TABLE quant.agent_sessions ADD COLUMN IF NOT EXISTS ai_diagnosis JSONB")
    cursor.execute("ALTER TABLE quant.agent_sessions ADD COLUMN IF NOT EXISTS ai_diagnosis_at TIMESTAMPTZ")
    cursor.execute("DELETE FROM quant.agent_session_events")
    cursor.execute("DELETE FROM quant.agent_sessions")
    repo.db.commit()
    s = SessionService()
    s.ingest_events([{
        "session_key": "agent:main:wake:e2e", "seq": 1, "event_type": "session_start",
        "payload": {"channel": "wake", "peerId": "e2e", "agentId": "main"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, {
        "session_key": "agent:main:wake:e2e", "seq": 2, "event_type": "tool_call",
        "payload": {"toolName": "pool_manage", "durationMs": 100, "success": True},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }])
    yield s


def test_ai_diagnosis_success(service, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sk-test')
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {'choices': [{'message': {'content': '做得好：X\n问题：Y\n建议：Z'}}]}

    with patch('application.services.llm_service.requests.post', return_value=fake_resp):
        result = service.ai_diagnosis('agent:main:wake:e2e')

    assert '做得好' in result['analysis']
    assert result['cached'] is False


def test_ai_diagnosis_cached_no_second_call(service, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sk-test')
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {'choices': [{'message': {'content': '分析内容'}}]}

    with patch('application.services.llm_service.requests.post', return_value=fake_resp) as mock_post:
        service.ai_diagnosis('agent:main:wake:e2e')
        second = service.ai_diagnosis('agent:main:wake:e2e')

    assert mock_post.call_count == 1  # 第二次走缓存
    assert second['cached'] is True


def test_ai_diagnosis_no_api_key(service, monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    with pytest.raises(RuntimeError, match='DEEPSEEK_API_KEY'):
        service.ai_diagnosis('agent:main:wake:e2e')


def test_ai_diagnosis_refresh_forces_regenerate(service, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sk-test')
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {'choices': [{'message': {'content': '新分析'}}]}

    with patch('application.services.llm_service.requests.post', return_value=fake_resp) as mock_post:
        service.ai_diagnosis('agent:main:wake:e2e')
        service.ai_diagnosis('agent:main:wake:e2e', refresh=True)

    assert mock_post.call_count == 2
```

- [ ] **Step 3: 运行确认失败**

Run: `cd quantsys-v2 && ./venv/bin/python -m pytest tests/services/test_ai_diagnosis.py -x -q 2>&1 | tail -3`
Expected: FAIL — no attribute 'ai_diagnosis' / ModuleNotFoundError: llm_service

- [ ] **Step 4: 实现 llm_service.py**

```python
# quantsys-v2/application/services/llm_service.py
"""
LLM 服务薄封装（DeepSeek，OpenAI 兼容接口）
"""
import os
import requests
import structlog

logger = structlog.get_logger(__name__)

DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'


def chat_completion(prompt: str, model: str = 'deepseek-chat', timeout: int = 60) -> str:
    """调用 DeepSeek 返回文本内容

    Raises:
        RuntimeError: 未配置 key / 超时 / API 错误
    """
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        raise RuntimeError('未配置 DEEPSEEK_API_KEY，无法使用 AI 诊断')

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
            },
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        raise RuntimeError('AI 诊断超时（60s），请稍后重试')
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f'AI 诊断请求失败: {e}')

    if resp.status_code != 200:
        raise RuntimeError(f'DeepSeek API 错误 {resp.status_code}: {resp.text[:200]}')

    return resp.json()['choices'][0]['message']['content']
```

- [ ] **Step 5: session_service.py 追加 ai_diagnosis 方法**

在 SessionService 类内追加：

```python
    def ai_diagnosis(self, session_key: str, refresh: bool = False) -> Dict[str, Any]:
        """AI 诊断：压缩事件流 → DeepSeek 三段分析 → 缓存到 agent_sessions

        Returns:
            {analysis, generated_at, cached}
        """
        import json as _json
        repo = BaseRepository()
        cursor = repo._get_cursor()

        # 缓存命中
        if not refresh:
            cursor.execute(
                "SELECT ai_diagnosis, ai_diagnosis_at FROM quant.agent_sessions WHERE session_key = %s",
                (session_key,),
            )
            row = cursor.fetchone()
            if row and row['ai_diagnosis']:
                return {
                    'analysis': row['ai_diagnosis'].get('analysis', ''),
                    'generated_at': row['ai_diagnosis_at'].isoformat() if row['ai_diagnosis_at'] else None,
                    'cached': True,
                }

        events = self.get_events(session_key, limit=500)
        prompt = self._build_diagnosis_prompt(session_key, events)

        from application.services.llm_service import chat_completion
        analysis = chat_completion(prompt)

        now = datetime.now(timezone.utc)
        cursor.execute(
            """UPDATE quant.agent_sessions
               SET ai_diagnosis = %s::jsonb, ai_diagnosis_at = %s
               WHERE session_key = %s""",
            (_json.dumps({'analysis': analysis}), now, session_key),
        )
        repo.db.commit()

        return {'analysis': analysis, 'generated_at': now.isoformat(), 'cached': False}

    @staticmethod
    def _build_diagnosis_prompt(session_key: str, events: List[Dict[str, Any]]) -> str:
        """压缩事件流为 ≤4K token 的诊断 prompt"""
        lines = [f"请诊断以下 AI 投资助手的工作会话（{session_key}）：\n"]
        tool_stats: Dict[str, Dict[str, int]] = {}

        for e in events:
            etype = e['event_type']
            p = e['payload'] or {}
            if etype == 'user_message':
                lines.append(f"用户: {str(p.get('text', ''))[:200]}")
            elif etype == 'assistant_reply':
                lines.append(f"助手回复: {str(p.get('text', ''))[:200]}")
            elif etype == 'tool_call':
                name = p.get('toolName', 'unknown')
                stat = tool_stats.setdefault(name, {'ok': 0, 'fail': 0, 'max_ms': 0})
                stat['ok' if p.get('success') else 'fail'] += 1
                stat['max_ms'] = max(stat['max_ms'], int(p.get('durationMs') or 0))
            elif etype == 'error':
                lines.append(f"错误[{p.get('stage', '')}]: {p.get('message', '')}")

        if tool_stats:
            lines.append("\n工具调用统计:")
            for name, s in tool_stats.items():
                lines.append(f"  {name}: 成功{s['ok']} 失败{s['fail']} 最慢{s['max_ms']}ms")

        lines.append(
            "\n请用中文输出三段分析（每段不超过100字）：\n"
            "1. 做得好的地方\n2. 问题与根因\n3. 下次改进建议"
        )
        return '\n'.join(lines)[:6000]
```

（文件顶部 import 区需有 `from datetime import datetime, timezone`。）

- [ ] **Step 6: routes/agent_sessions.py 追加端点**

```python
@agent_sessions_bp.route('/<path:session_key>/ai-diagnosis', methods=['POST'])
@handle_errors
def ai_diagnosis(session_key):
    """AI 诊断（DeepSeek，缓存）；?refresh=true 强制重新生成"""
    refresh = request.args.get('refresh', '').lower() == 'true'
    try:
        result = SessionService().ai_diagnosis(session_key, refresh=refresh)
    except RuntimeError as e:
        return jsonify({'success': False, 'error': str(e)}), 503
    return jsonify({'success': True, 'data': result})
```

- [ ] **Step 7: 运行测试确认通过并 commit**

Run: `cd quantsys-v2 && ./venv/bin/python -m pytest tests/services/test_ai_diagnosis.py -q 2>&1 | tail -3`
Expected: 4 passed

```bash
cd quantsys-v2 && git add application/services/llm_service.py application/services/session_service.py adapters/inbound/api/routes/agent_sessions.py infrastructure/persistence/migrations/add_session_ai_diagnosis.sql tests/services/test_ai_diagnosis.py
git commit -m "feat(session-web): AI 诊断端点（DeepSeek + 缓存）"
```

---

### Task 7: 端到端验证

- [ ] **Step 1: 启动 v2（含新端点）并造测试数据**

```bash
cd quantsys-v2 && ./venv/bin/python -c "
from adapters.inbound.api.server import create_app
create_app().run(host='127.0.0.1', port=5002, debug=False)" &
sleep 5
# 注入一条测试会话
curl -s -X POST http://127.0.0.1:5002/api/sessions/events -H 'Content-Type: application/json' -d '{
  "events": [
    {"session_key":"agent:main:wake:demo","seq":1,"event_type":"session_start","payload":{"channel":"wake","peerId":"demo","agentId":"main"},"created_at":"2026-07-26T10:00:00Z"},
    {"session_key":"agent:main:wake:demo","seq":2,"event_type":"user_message","payload":{"messageId":"m1","text":"分析茅台"},"created_at":"2026-07-26T10:00:01Z"},
    {"session_key":"agent:main:wake:demo","seq":3,"event_type":"tool_call","payload":{"toolName":"data_fetch_quote","durationMs":800,"success":true},"created_at":"2026-07-26T10:00:02Z"},
    {"session_key":"agent:main:wake:demo","seq":4,"event_type":"assistant_reply","payload":{"text":"茅台当前PE处于高位…","replyLength":100},"created_at":"2026-07-26T10:00:05Z"}
  ]}'
```

- [ ] **Step 2: 启动前端并人工验证**

```bash
cd web-frontend && VITE_API_BASE_URL=http://127.0.0.1:5002 npm run dev
# 浏览器打开 http://127.0.0.1:3001/agent-session/list
# 验证：列表显示 demo 会话 → 点击钻取 → 回放时间线正确分组 → 诊断 tab 指标卡/慢工具图
# AI 诊断按钮：需 v2 环境有 DEEPSEEK_API_KEY（无 key 时验证 503 文案）
```

- [ ] **Step 3: 全量测试**

```bash
cd web-frontend && npx vitest run 2>&1 | tail -3
cd quantsys-v2 && ./venv/bin/python -m pytest tests/services/test_session_service.py tests/services/test_ai_diagnosis.py tests/api/test_agent_session_routes.py -q 2>&1 | tail -2
```

---

## Self-Review 记录

- **Spec 覆盖**：§2 路由/菜单（Task 5）✓；§3 API 层（Task 1）✓；§4.1 列表（Task 3）✓；§4.2 回放（Task 2, 4）✓；§4.3 诊断（Task 4）✓；§5 AI 诊断（Task 1, 4, 6）✓；§6 错误处理（融入各 Task；503/超时路径 Task 6 测试）✓；§7 测试（每 Task TDD）✓
- **类型一致**：`AiDiagnosis{analysis,generated_at,cached}` 在 Task 1 类型/测试、Task 4 组件、Task 6 v2 返回一致；`agentSessionApi` 方法签名四处一致；`Turn` 结构 Task 2/4 一致
- **已知坑已注明**：barrel 导出需确认（Task 1 Step 4）；router.test.ts 需先读现有风格（Task 5 Step 3）；session_service.py 顶部需补 datetime import（Task 6 Step 5）
