/**
 * 宿主接线冒烟：以 stub ctx 执行 apply()，验证捕获/立项三件套真正注册：
 *   1) systemPrompt capture section（reqboard:capture / order 60 / 函数式求值）
 *   2) 五个 agent 工具（reqboard_create / reqboard_status / reqboard_move /
 *      reqboard_decompose / reqboard_task_move）
 *   3) webServer 前缀路由（/dashboard/api/reqboard）
 * 以及 dispose 清理不抛错。这是无需重启 :13080 的最强接线验证
 * （等价于启动时插件装配路径：inject → effect → section/register）。
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { apply } from '../src/index.js'

type DisposeFn = () => void

interface StubCtx {
  sections: Array<{ name: string; order: number; text: unknown }>
  tools: Array<{ name: string; execute: unknown }>
  routes: Array<{ kind: string; path: string }>
  disposeHooks: DisposeFn[]
}

/** 页面插件无静态 inject——stub 立即派发 inject，effect 立即执行并收集清理。 */
function stubCtx(): StubCtx & {
  logger: () => { debug(): void; info(): void; warn(...a: unknown[]): void; error(...a: unknown[]): void }
  inject(services: string[], cb: (c: any) => void): void
  on(ev: string, cb: DisposeFn): void
} {
  const s: StubCtx = { sections: [], tools: [], routes: [], disposeHooks: [] }
  const disposers: DisposeFn[] = []
  const mkSvc = (extra: Record<string, unknown> = {}) => ({
    effect: (fn: () => unknown) => { const d = fn(); if (typeof d === 'function') disposers.push(d as DisposeFn) },
    systemPrompt: {
      section: (sec: any) => { s.sections.push(sec); return () => {} },
    },
    tools: {
      register: (tool: any) => { s.tools.push(tool); return () => {} },
    },
    webServer: {
      register: (route: any) => { s.routes.push(route); return () => {} },
    },
    ...extra,
  })
  const svcs: Record<string, any> = {
    systemPrompt: mkSvc(),
    tools: mkSvc(),
    webServer: mkSvc(),
    agents: mkSvc({ agents: {} }),
    sessionProjections: mkSvc({ sessionProjections: {} }),
  }
  const logger = () => ({ debug() {}, info() {}, warn(..._a: unknown[]) {}, error(..._a: unknown[]) {} })
  const ctx = {
    ...s,
    logger,
    inject: (services: string[], cb: (c: any) => void) => {
      for (const name of services) cb(svcs[name])
    },
    on: (ev: string, cb: DisposeFn) => { if (ev === 'dispose') s.disposeHooks.push(cb) },
  } as any
  ctx.__disposers = disposers
  return ctx
}

let dir: string
beforeAll(() => { dir = mkdtempSync(join(tmpdir(), 'pmboard-apply-')) })
afterAll(() => rmSync(dir, { recursive: true, force: true }))

describe('dsh-pmboard apply() 宿主接线（乙流程装配冒烟）', () => {
  it('注册 capture section：reqboard:capture / order 60 / text 函数式', () => {
    const ctx = stubCtx()
    apply(ctx as never, { dshHome: dir })
    const sec = ctx.sections.find(x => x.name === 'reqboard:capture')
    expect(sec).toBeDefined()
    expect(sec!.order).toBe(60)
    expect(typeof sec!.text).toBe('function')
    // 函数式求值：unbound 窗口（空台账 + agent.id）→ 返回引导文本而非空
    const text = (sec!.text as (c: unknown) => string)({ agent: { id: 'session-unbound-1' } })
    expect(text).toContain('reqboard_create')
  })

  it('注册全部 agent 工具（REQ-47939a 收敛后 9 个 + REQ-327bdf 2 个 + REQ-e3b6a0 的 reqboard_capture）', () => {
    const ctx = stubCtx()
    apply(ctx as never, { dshHome: dir })
    const names = ctx.tools.map(t => t.name).sort()
    expect(names).toEqual([
      'reqboard_accept_sheet',
      // CONFIRM：ask_confirm + confirm_artifact 合并（evidence 路径自动分派）
      'reqboard_ask_confirm',
      // CAPTURE：立项三问 pm 专有弹框（REQ-e3b6a0 t8）
      'reqboard_capture',
      'reqboard_create',
      'reqboard_decompose',
      'reqboard_move',
      'reqboard_status',
      // SUBMIT：requirement_submit / plan_submit / verify_submit / archive_submit 合并（kind 分派）
      'reqboard_submit',
      'reqboard_task_execute',
      'reqboard_task_move',
      'reqboard_task_report',
      // REQ-4842fe t10：事件链执行入口
      'reqboard_task_run',
      'reqboard_task_status',
    ])
    expect(names).toHaveLength(13)
  })

  it('注册看板路由：/dashboard/api/reqboard 前缀', () => {
    const ctx = stubCtx()
    apply(ctx as never, { dshHome: dir })
    const route = ctx.routes.find(r => r.path === '/dashboard/api/reqboard')
    expect(route).toBeDefined()
    expect(route!.kind).toBe('prefix')
  })

  it('dispose 清理全部注册（幂等不抛错）', () => {
    const ctx = stubCtx()
    apply(ctx as never, { dshHome: dir })
    expect(ctx.disposeHooks.length).toBeGreaterThan(0)
    for (const hook of ctx.disposeHooks) expect(() => hook()).not.toThrow()
    for (const d of (ctx as any).__disposers) expect(() => d()).not.toThrow()
  })
})
