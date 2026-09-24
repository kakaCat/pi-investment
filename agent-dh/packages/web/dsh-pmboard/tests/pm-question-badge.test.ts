/**
 * pm 弹框统一来源标志（REQ-260924213231-b1c4 T-11 / FR-8 · I-7 / TC-14）。
 *
 * 口径（design/interfaces.md I-7、use-cases.md UC-5）：
 *   ① pm 侧构造的**每个** AskQuestion.header 以固定前缀 `📋 PM · ` 开头——
 *      ask_confirm / accept_sheet（逐项 + 最终）/ 立项四问 / 失败处置四处构造点；
 *   ② 标志是**代码注入**（domain/text/pm-badge.ts 唯一字面量处），不靠 agent 在正文写 emoji：
 *      正文（question）保持原文、不加前缀；宿主原生 `ask_user_question` 不经本函数、不带前缀。
 *
 * @module dsh-pmboard/tests/pm-question-badge
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { pmHeader, PM_BADGE_PREFIX } from '../src/domain/text/pm-badge.js'
import { buildCaptureQuestions, buildCaptureIntentQuestions, buildCaptureDetailQuestions } from '../src/application/internal/capture-mapping.js'
import { askConfirm } from '../src/application/use-cases/AskConfirm.js'
import { acceptSheet } from '../src/application/use-cases/AcceptSheet.js'
import { openFailurePopup } from '../src/application/use-cases/HandleFailure.js'
import { DEFAULT_CONFIRM_OPTIONS, ACCEPT_ITEM_OPTIONS, FINAL_PASS_LABEL } from '../src/domain/text/labels.js'
import { makeHarness, req } from './application/harness.js'

const W = 'session-w-001'
const REQ_ID = 'REQ-000001'
const exec = { agent: { id: W } }

/** 记录每次 ask 下发的全部 header（FakeQuestions.asked 只留最后一批）。 */
function recordingQuestions(onAsk?: (headers: readonly string[]) => void) {
  const seen: string[] = []
  return {
    seen,
    wrap(inner: { available(): boolean; ask: (q: readonly { header?: string }[]) => Promise<readonly unknown[]> }) {
      return {
        available: () => inner.available(),
        ask: async (q: readonly { header?: string }[], _opts?: unknown) => {
          const headers = q.map(x => x.header ?? '')
          seen.push(...headers)
          onAsk?.(headers)
          return inner.ask(q) as Promise<readonly never[]>
        },
      }
    },
  }
}

describe('pmHeader：来源标志唯一注入点', () => {
  it('固定前缀 + 原文', () => {
    expect(PM_BADGE_PREFIX).toBe('📋 PM · ')
    expect(pmHeader('确认')).toBe('📋 PM · 确认')
    expect(pmHeader('需求名称')).toBe('📋 PM · 需求名称')
  })
})

describe('TC-14 四处 pm 弹框 header 均带标志', () => {
  it('立项四问（两段合计 4 问）header 全部带前缀，题干不变', () => {
    const intent = buildCaptureIntentQuestions(['候选 A'])
    const detail = buildCaptureDetailQuestions()
    const all = buildCaptureQuestions(['候选 A'])
    expect(all).toHaveLength(4)
    expect([...intent, ...detail]).toHaveLength(4)
    expect(all.map(q => q.header)).toEqual([
      pmHeader('需求名称'),
      pmHeader('需求类型'),
      pmHeader('提示词难度'),
      pmHeader('需求文档位置'),
    ])
    for (const q of all) expect(q.header!.startsWith(PM_BADGE_PREFIX)).toBe(true)
    // 正文不注入标志（标志在 header，不在 question）
    for (const q of all) expect(q.question.startsWith(PM_BADGE_PREFIX)).toBe(false)
  })

  it('ask_confirm（artifact 确认）header 带前缀，宿主可见的 question 正文不带', async () => {
    const h = makeHarness({
      requirements: [req({
        id: REQ_ID, status: 'brainstorming', sourceSessionId: W,
        artifacts: [{
          stage: 'brainstorming', kind: 'requirement',
          path: 'docs/requirements/REQ-000001/requirement.md',
          registeredAt: 1, registeredBy: { kind: 'agent', sessionId: W },
        }],
      })],
    })
    h.questions.answers = [{ id: 'confirm', selected: [DEFAULT_CONFIRM_OPTIONS[0]] }]
    const rec = recordingQuestions()
    h.deps.questions = rec.wrap(h.deps.questions as never) as never

    await askConfirm(h.deps, { target: 'artifact', kind: 'requirement', question: '确认需求文档？', advance: false }, exec)

    expect(rec.seen).toEqual([pmHeader('确认')])
    expect(h.questions.asked[0]!.header).toBe(pmHeader('确认'))
    expect(h.questions.asked[0]!.question).not.toContain(PM_BADGE_PREFIX)
  })

  it('accept_sheet（逐项 + 最终归档）header 带前缀', async () => {
    const sheet = {
      version: 1, generatedAt: 1, generatedBy: { kind: 'agent' as const, sessionId: W },
      items: [
        { id: 'v1-1', source: { kind: 'requirement' } as const, criterion: '判据一', evidence: ['e'], status: 'pending' as const },
        { id: 'v1-2', source: { kind: 'task', taskId: 't-000001' } as const, criterion: '判据二', evidence: [], status: 'pending' as const },
      ],
    }
    const h = makeHarness({
      requirements: [req({ id: REQ_ID, status: 'accepting', sourceSessionId: W, verification: { sheet } as never })],
    })
    h.questions.answers = [
      { id: 'v1-1', selected: [ACCEPT_ITEM_OPTIONS.pass] },
      { id: 'v1-2', selected: [ACCEPT_ITEM_OPTIONS.pass] },
      { id: 'final-pass', selected: [FINAL_PASS_LABEL] },
    ]
    const rec = recordingQuestions()
    h.deps.questions = rec.wrap(h.deps.questions as never) as never

    await acceptSheet(h.deps, {}, exec)

    expect(rec.seen).toEqual([
      pmHeader('需求级验收'),
      pmHeader('验收项 t-000001'),
      pmHeader('验收通过'),
    ])
    for (const header of rec.seen) expect(header.startsWith(PM_BADGE_PREFIX)).toBe(true)
  })

  it('失败处置弹框 header 带前缀', async () => {
    const h = makeHarness()
    h.questions.answers = [{ selected: ['重跑该卡'] }]
    const rec = recordingQuestions()
    h.deps.questions = rec.wrap(h.deps.questions as never) as never

    const choice = await openFailurePopup(h.deps, REQ_ID, exec)

    expect(choice).toBe('rerun')
    expect(rec.seen).toEqual([pmHeader('实施链已暂停')])
  })
})

describe('TC-14 标志由代码注入，宿主原生提问不带前缀', () => {
  const SRC = fileURLToPath(new URL('../src', import.meta.url))
  const rel = (p: string) => p.slice(SRC.length + 1).replace(/\\/g, '/')

  function tsFiles(dir: string): string[] {
    const out: string[] = []
    for (const name of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, name.name)
      if (name.isDirectory()) out.push(...tsFiles(full))
      else if (name.name.endsWith('.ts')) out.push(full)
    }
    return out
  }

  it('前缀字面量只出现在 pm-badge.ts（别处硬写 = 漂移）', () => {
    const holders = tsFiles(SRC).filter(f => readFileSync(f, 'utf8').includes(PM_BADGE_PREFIX))
    expect(holders.map(rel)).toEqual(['domain/text/pm-badge.ts'])
  })

  it('四处构造点都经 pmHeader（而不是手写前缀）', () => {
    const points = [
      'application/use-cases/AskConfirm.ts',
      'application/use-cases/AcceptSheet.ts',
      'application/internal/capture-mapping.ts',
      'application/use-cases/HandleFailure.ts',
    ]
    for (const p of points) {
      const src = readFileSync(join(SRC, p), 'utf8')
      expect(src, p).toContain("from '../../domain/text/pm-badge.js'")
      expect(src, p).toContain('pmHeader(')
      expect(src, p).not.toContain(PM_BADGE_PREFIX)
    }
  })
})
