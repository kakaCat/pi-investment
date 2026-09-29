/**
 * 会话跳转语义单测（父卡：跳转语义归位 selectPanel(null)）。
 *
 * 可证伪点：
 * ① 跳转 = **先** layout.selectPanel(null)（收看板面板、回当前对话）**再**
 *    uiWorkspace.openSession(sid)（切会话）——两者顺序落进同一条时间线，顺序错即失败；
 * ② 目标即当前会话：只收面板，不重复 openSession；
 * ③ layout 未注入/已 clear → 返回 'unavailable'，且**不 openSession**（不静默跳过收口，
 *    否则「会话切了、画面仍停在看板」的故障会复现）；
 * ④ uiWorkspace 不可用 → 'unavailable'；
 * ⑤ archived / missing 判定与既有返回语义保留（不因收口改造而丢失）。
 *
 * 另设有回归守卫：旧收口机制（closeHostPanel + dsh-pmboard:open-board 派发）已删除。
 *
 * node 环境即可跑：本模块不依赖真实 DOM（location 读取在 try/catch 内，测试显式传 access 投影）。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as sessionJumpModule from '../src/client/session-jump.ts'
import { jumpToSession, type SessionServiceAccess, type UiWorkspaceFace } from '../src/client/session-jump.ts'
import { setPageLayout, clearPageLayout } from '../src/client/page/page-runtime.ts'

interface FakeAccessOptions {
  byId?: Record<string, unknown>
  archived?: readonly string[]
  currentSessionId?: string
  withUiWorkspace?: boolean
}

interface FakeAccess {
  access: SessionServiceAccess
  /** 跳转过程动作时间线（selectPanel / openSession / refresh 的顺序证据）。 */
  timeline: string[]
}

/** 构造假服务投影：layout 的 selectPanel 与 uiWorkspace.openSession 都写同一条时间线。 */
function fakeAccess(opts: FakeAccessOptions = {}): FakeAccess {
  const timeline: string[] = []
  const workspaces: {
    list: { getSnapshot: () => { archivedSessionIds: readonly string[] } }
    currentSessionId?: string
  } = {
    list: { getSnapshot: () => ({ archivedSessionIds: opts.archived ?? [] }) },
  }
  if (opts.currentSessionId !== undefined) workspaces.currentSessionId = opts.currentSessionId
  const sessions = {
    refresh: async (): Promise<void> => { timeline.push('refresh') },
    list: { getSnapshot: () => ({ byId: opts.byId ?? {} }) },
  }
  const uiWorkspace: UiWorkspaceFace = {
    openSession: (target: string): void => { timeline.push('openSession:' + target) },
  }
  const access: SessionServiceAccess = {
    getUiWorkspace: () => (opts.withUiWorkspace === false ? undefined : uiWorkspace),
    getSessions: () => sessions,
    getWorkspaces: () => workspaces,
  }
  return { access, timeline }
}

/** 安装假 layout：selectPanel 调用写时间线，使「先收面板再切会话」可断言。 */
function installLayout(timeline: string[]): void {
  setPageLayout({
    selectPanel: (id: string | null): void => { timeline.push('selectPanel:' + String(id)) },
  })
}

/** node 环境无 window；注入最小 location.pathname（模块只读这一个浏览器全局）。 */
function setWindowPathname(pathname: string): void {
  (globalThis as unknown as Record<string, unknown>).window = { location: { pathname } }
}

beforeEach(() => { clearPageLayout() })
afterEach(() => {
  clearPageLayout()
  delete (globalThis as unknown as Record<string, unknown>).window
})

describe('jumpToSession 跳转语义（layout.selectPanel(null) 归位）', () => {
  it('跳转 = 先 selectPanel(null) 再 openSession(sid)（顺序可证伪）', async () => {
    const { access, timeline } = fakeAccess({ byId: { 's-target': {} } })
    installLayout(timeline)

    await expect(jumpToSession(access, 's-target')).resolves.toBe('opened')
    expect(timeline).toEqual(['selectPanel:null', 'openSession:s-target'])
  })

  it('目标即当前会话（URL 命中）：只收面板，不重复 openSession', async () => {
    const { access, timeline } = fakeAccess({ byId: { 's-here': {} } })
    setWindowPathname('/session/s-here')
    installLayout(timeline)

    await expect(jumpToSession(access, 's-here')).resolves.toBe('opened')
    expect(timeline).toEqual(['selectPanel:null'])
  })

  it('当前会话回退取 workspaces.currentSessionId 时同样只收面板', async () => {
    const { access, timeline } = fakeAccess({ byId: { 's-here': {} }, currentSessionId: 's-here' })
    setWindowPathname('/')
    installLayout(timeline)

    await expect(jumpToSession(access, 's-here')).resolves.toBe('opened')
    expect(timeline).toEqual(['selectPanel:null'])
  })

  it('layout 未注入 → unavailable，且不 openSession（不静默跳过收口）', async () => {
    const { access, timeline } = fakeAccess({ byId: { 's-target': {} } })
    clearPageLayout()

    await expect(jumpToSession(access, 's-target')).resolves.toBe('unavailable')
    expect(timeline).toEqual([])
  })

  it('uiWorkspace 不可用 → unavailable', async () => {
    const { access, timeline } = fakeAccess({ byId: { 's-target': {} }, withUiWorkspace: false })
    installLayout(timeline)

    await expect(jumpToSession(access, 's-target')).resolves.toBe('unavailable')
    expect(timeline).toEqual([])
  })

  it('archived 判定保留：不点面板、不切会话', async () => {
    const { access, timeline } = fakeAccess({ byId: { 's-arch': {} }, archived: ['s-arch'] })
    installLayout(timeline)

    await expect(jumpToSession(access, 's-arch')).resolves.toBe('archived')
    expect(timeline).toEqual([])
  })

  it('missing 判定保留：列表未命中先 refresh 一次，仍无 → missing', async () => {
    const { access, timeline } = fakeAccess({ byId: {} })
    installLayout(timeline)

    await expect(jumpToSession(access, 's-gone')).resolves.toBe('missing')
    expect(timeline).toEqual(['refresh'])
  })
})

describe('旧收口机制已删除（不再经 dsh-pmboard:open-board 派发）', () => {
  it('session-jump 不再导出 closeHostPanel', () => {
    expect('closeHostPanel' in sessionJumpModule).toBe(false)
  })
})
