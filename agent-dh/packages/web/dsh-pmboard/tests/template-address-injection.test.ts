/**
 * 注入点地址段一致性（REQ-260922213356-4a45 T-3 / TC-9）。
 *
 * 系统提示词段与 H3 后置链必须由**同一个纯函数**折入**逐字相同**的地址段——
 * 否则「纪律到了、地址没到」或「两处口径不一致」这类漂移会静默发生。
 * （节点输入包一侧在 T-5 的压缩两路径用例里补齐。）
 *
 * @module dsh-pmboard/tests/template-address-injection
 */
import { describe, it, expect } from 'vitest'
import { fileURLToPath } from 'node:url'
import { makeHarness, req } from './application/harness.js'
import { boundSectionText } from '../src/application/internal/capture-section.js'
import { createH3InjectHandler } from '../src/application/gate/handlers/h3-inject.js'
import { createH4ResumeHandler } from '../src/application/gate/handlers/h4-resume.js'
import { buildNodeInputPackage } from '../src/application/internal/node-input-package.js'
import type { ConfirmContext } from '../src/domain/gate/GateSpec.js'
import type { ChainScratch } from '../src/application/gate/GatePostChain.js'
import type { InjectionLogInput } from '../src/application/internal/injection-log.js'

const WINDOW = 'session-w-001'
const REQ_ID = 'REQ-000001'
const REAL_ROOT = fileURLToPath(new URL('../templates', import.meta.url))

function seeded(status: string, category = 'feature') {
  return makeHarness({
    requirements: [req({
      id: REQ_ID, status: status as never, category: category as never, sourceSessionId: WINDOW,
      artifacts: [
        { stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-000001/requirement.md', registeredAt: 1, registeredBy: { kind: 'agent' } },
        { stage: 'design', kind: 'design', path: 'docs/requirements/REQ-000001/design/architecture.md', registeredAt: 1, registeredBy: { kind: 'agent' } },
      ],
    })],
  })
}

function ctx(to: string, verdict: 'affirmative' | 'negative' | undefined = 'affirmative', answers: ConfirmContext['answers'] = []): ConfirmContext {
  return { windowKey: WINDOW, gate: 'G1', from: 'brainstorming', to: to as never, requirementId: REQ_ID, ...(verdict === undefined ? {} : { verdict }), answers, decidedAt: 1000 }
}

function deliverSink() {
  const msgs: string[] = []
  return { msgs, port: { deliver: (_wk: string, m: { text: string }) => { msgs.push(m.text); return { delivered: true } } } }
}

/** 从整段注入文本里抽出地址段（到「流水线（状态就是阶段」为止；输入的 H3 文本无此串则到末尾）。 */
function sectionOf(text: string): string {
  const i = text.indexOf('## 本节点文档')
  if (i < 0) return ''
  const rest = text.slice(i)
  const j = rest.indexOf('\n流水线（状态就是阶段')
  return (j < 0 ? rest : rest.slice(0, j)).trimEnd()
}

function logSink() {
  const entries: InjectionLogInput[] = []
  return { entries, port: { record: (e: InjectionLogInput) => { entries.push(e) } } }
}

describe('TC-9 地址段在三处注入点逐字一致', () => {
  it('design/feature：系统段与 H3 的地址段相同，且含同一组绝对地址', async () => {
    const h = seeded('design')
    const sink = logSink()
    const section = boundSectionText(h.repo.snapshot() as never, { agent: { id: WINDOW } }, sink.port, { templateRoot: REAL_ROOT, enabled: true })
    const systemSection = sectionOf(section)

    const h3Sink = logSink()
    const handler = createH3InjectHandler({ repo: h.repo, injectionLog: h3Sink.port, templateRoot: REAL_ROOT, addressSectionEnabled: true } as never)
    const scratch: ChainScratch = {}
    const outcome = await handler.run({ ctx: ctx('design'), scratch })
    expect(outcome).toEqual({ kind: 'continue' })
    const h3Section = sectionOf(scratch.promptText ?? '')

    expect(systemSection.length).toBeGreaterThan(0)
    expect(h3Section).toBe(systemSection)
    expect(systemSection).toContain(REAL_ROOT + '/design/architecture.md')
    expect(systemSection).toContain('docs/requirements/REQ-000001/requirement.md')
    // 留痕 charCount 含地址段（FR-8 记账）：H3 的 charCount = 增强后文本长度
    expect(h3Sink.entries[0]?.charCount).toBe((scratch.promptText ?? '').length)
    expect(sink.entries[0]?.charCount ?? 0).toBeGreaterThan(0)
  })

  it('空集（bug 的 design 且无已登记上游）：两处都不出现地址段标题', async () => {
    // 空集 = 无模板（bug design）且无上游（artifacts 为空）——只有此时渲染返空串
    const h = makeHarness({
      requirements: [req({ id: REQ_ID, status: 'design' as never, category: 'bug' as never, sourceSessionId: WINDOW })],
    })
    const section = boundSectionText(h.repo.snapshot() as never, { agent: { id: WINDOW } }, undefined, { templateRoot: REAL_ROOT, enabled: true })
    expect(section).not.toContain('## 本节点文档')

    const handler = createH3InjectHandler({ repo: h.repo, templateRoot: REAL_ROOT, addressSectionEnabled: true } as never)
    const scratch: ChainScratch = {}
    await handler.run({ ctx: ctx('design'), scratch })
    expect(scratch.promptText ?? '').not.toContain('## 本节点文档')
  })

  it('开关关闭 / 未给模板根：行为与改造前逐字一致（无地址段）', async () => {
    const h = seeded('design')
    const off = boundSectionText(h.repo.snapshot() as never, { agent: { id: WINDOW } }, undefined, { templateRoot: REAL_ROOT, enabled: false })
    const none = boundSectionText(h.repo.snapshot() as never, { agent: { id: WINDOW } }, undefined, undefined)
    expect(off).toBe(none)
    expect(off).not.toContain('## 本节点文档')
  })
})

describe('TC-10 非肯定项不注入下一节点纪律（FR-10）', () => {
  it('negative：H3 skip(negative_verdict)，不写 scratch、不留痕', async () => {
    const h = seeded('design')
    const sink = logSink()
    const handler = createH3InjectHandler({ repo: h.repo, injectionLog: sink.port, templateRoot: REAL_ROOT, addressSectionEnabled: true } as never)
    const scratch: ChainScratch = {}
    const out = await handler.run({ ctx: ctx('design', 'negative'), scratch })
    expect(out).toEqual({ kind: 'skip', code: 'negative_verdict', reason: expect.any(String) })
    expect(scratch.promptText).toBeUndefined()
    expect(sink.entries).toHaveLength(0)
  })

  it('verdict 缺省（H1 未跑到）→ 保守按 negative 处理', async () => {
    const h = seeded('design')
    const handler = createH3InjectHandler({ repo: h.repo, templateRoot: REAL_ROOT, addressSectionEnabled: true } as never)
    const scratch: ChainScratch = {}
    const noVerdict = ctx('design')
    delete (noVerdict as { verdict?: unknown }).verdict
    const out = await handler.run({ ctx: noVerdict, scratch })
    expect(out).toMatchObject({ kind: 'skip', code: 'negative_verdict' })
    expect(scratch.promptText).toBeUndefined()
  })

  it('H4 negative：只发作答摘要 + 用户意见，不含任何纪律块', async () => {
    const d = deliverSink()
    const handler = createH4ResumeHandler({ delivery: d.port as never })
    await handler.run({ ctx: ctx('design', 'negative', [{ id: 'confirm', selected: ['需修改'], custom: '第三节缺端侧条件' }]), scratch: {} })
    const text = d.msgs[0] ?? ''
    expect(text).not.toContain('按以下阶段纪律继续')
    expect(text).not.toContain('阶段纪律已随节点输入包')
    expect(text).toContain('需修改')
    expect(text).toContain('第三节缺端侧条件')
  })

  it('H4 affirmative：仍附纪律全文（防"修反"）', async () => {
    const d = deliverSink()
    const handler = createH4ResumeHandler({ delivery: d.port as never })
    await handler.run({ ctx: ctx('design', 'affirmative'), scratch: { promptText: 'DISCIPLINE-X' } })
    expect(d.msgs[0] ?? '').toContain('DISCIPLINE-X')
  })
})

describe('TC-11 压缩路径（节点输入包）与未压缩路径地址段一致', () => {
  it('输入包含「本节点文档」且与系统段逐字一致，位于「需求文档」之后', () => {
    const h = seeded('design')
    const requirement = h.repo.snapshot().requirements[0]
    const pkg = buildNodeInputPackage({
      stage: 'design' as never,
      category: 'feature' as never,
      requirement,
      requirementDoc: 'X',
      requirementDocPath: 'docs/requirements/REQ-000001/requirement.md',
      templateRoot: REAL_ROOT,
    })
    const pkgSection = sectionOf(pkg.text)
    const systemSection = sectionOf(boundSectionText(h.repo.snapshot() as never, { agent: { id: WINDOW } }, undefined, { templateRoot: REAL_ROOT, enabled: true }))
    expect(pkgSection.length).toBeGreaterThan(0)
    expect(pkgSection).toBe(systemSection)
    expect(pkg.text.indexOf('## 本节点文档')).toBeGreaterThan(pkg.text.indexOf('## 需求文档'))
  })

  it('系统段不可得时，输入包仍带地址段（双落点互为兜底）', () => {
    const h = seeded('design')
    const noWindow = boundSectionText(h.repo.snapshot() as never, {} as never, undefined, { templateRoot: REAL_ROOT, enabled: true })
    expect(noWindow).toBe('')
    const pkg = buildNodeInputPackage({
      stage: 'design' as never, category: 'feature' as never,
      requirement: h.repo.snapshot().requirements[0],
      requirementDoc: 'X', requirementDocPath: 'docs/requirements/REQ-000001/requirement.md',
      templateRoot: REAL_ROOT,
    })
    expect(sectionOf(pkg.text).length).toBeGreaterThan(0)
  })

  it('空集（无模板无上游）：输入包不追加地址小节', () => {
    const h = makeHarness({ requirements: [req({ id: REQ_ID, status: 'design' as never, category: 'bug' as never, sourceSessionId: WINDOW })] })
    const pkg = buildNodeInputPackage({
      stage: 'design' as never, category: 'bug' as never,
      requirement: h.repo.snapshot().requirements[0],
      requirementDoc: 'X', requirementDocPath: 'docs/requirements/REQ-000001/requirement.md',
      templateRoot: REAL_ROOT,
    })
    expect(pkg.text).not.toContain('## 本节点文档')
  })
})


