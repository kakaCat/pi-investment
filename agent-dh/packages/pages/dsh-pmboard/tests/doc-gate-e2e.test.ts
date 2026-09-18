/**
 * 文档门禁端到端验证（REQ-d3e61a T-18 / serve 全链路）
 *
 * 验收口径：两条 E2E 全绿，**存量需求零误伤**。
 *   E2E①  需求 → 拆分（缺条款）→ **被拦** → 补卡 → 通过
 *   E2E②  交付 → 三方一致性验收单（需求有编号、无设计/无实施 → 单上出现缺口项）
 *
 * 走**真实入口**（executeDecompose / submitVerification）+ harness 的假 docs/仓，
 * 断言**可观察终态**（拒绝与否、验收单里有没有那一项），而不是"函数被调用过"。
 */
import { describe, expect, it } from 'vitest'
import { makeHarness, req, task } from './application/harness.js'
import { executeDecompose } from '../src/application/use-cases/Decompose.js'
import { submitVerification } from '../src/application/use-cases/SubmitVerification.js'

const EXEC = { agent: { id: 'session-w-001' } }
const doc = (...lines: string[]) => lines.join('\n')

const REQ_MD = doc(
  '# 需求', '',
  '## 边界', '',
  '## 问题', '',
  '## 成功标准', '',
  '## 产品定义', '',
  '## 用户与角色', '',
  '## 功能点', '',
  '**FR-1 覆盖门禁**：拆分时逐条核对。', '',
  '**FR-4 三段可追溯**：需求↔任务↔证据。', '',
  '## 10. 测试策略', '',
  '| 层级 | 数量 | 说明 |', '|---|---|---|', '| 单元 | 3 | 纯函数 |', '| E2E | 1 | 全链路 |',
)

const planTask = (key: string, title: string) => ({
  key, title, phase: 'implement', side: 'backend', dependsOn: [],
  acceptance: 'npx vitest run tests/x.test.ts 通过', implementation: '改 src/x.ts',
})

const seededReq = (over: Record<string, unknown> = {}, keys: [string, string][] = [['T-1', '覆盖门禁'], ['T-2', '三段可追溯']]) => req({
  status: 'decomposing',
  artifacts: [{ stage: 'planning', kind: 'plan', path: 'docs/requirements/REQ-000001/plan.md' }],
  plan: {
    path: 'docs/requirements/REQ-000001/plan.md', summary: '技术设计', submittedAt: 1,
    submittedBy: { kind: 'agent', sessionId: 'session-w-001' },
    tasks: keys.map(([k, title]) => planTask(k, title)),
    approvedAt: 2, approvedBy: { kind: 'human' },
  },
  ...over,
} as any)

describe('E2E① 需求 → 拆分 → 缺条款 → 被拦 → 补卡 → 通过', () => {
  const h = () => {
    const hh = makeHarness({ requirements: [seededReq()], tasks: [] })
    hh.docs.put('docs/requirements/REQ-000001/requirement.md', REQ_MD)
    return hh
  }

  it('违规：只覆盖 FR-1、漏 FR-4 → **拆分被拦**且点出 FR-4', async () => {
    const hh = h()
    await expect(executeDecompose(hh.deps, {
      tasks: [
        { key: 'T-1', title: '覆盖门禁', acceptance: 'npx vitest run a 通过', implementation: '改 a.ts', requirement_refs: ['FR-1'] },
        { key: 'T-2', title: '三段可追溯', acceptance: 'npx vitest run b 通过', implementation: '改 b.ts', requirement_refs: [] },
      ],
    }, EXEC)).rejects.toThrow(/FR-4/)
    // 终态：台账里没有落库任务（拒绝不留副作用）
    expect(hh.repo.ledger.tasks).toHaveLength(0)
  })

  it('补卡：给 T-2 补上 FR-4 → **拆分通过**并落库', async () => {
    const hh = h()
    const out: any = await executeDecompose(hh.deps, {
      tasks: [
        { key: 'T-1', title: '覆盖门禁', acceptance: 'npx vitest run a 通过', implementation: '改 a.ts', requirement_refs: ['FR-1'] },
        { key: 'T-2', title: '三段可追溯', acceptance: 'npx vitest run b 通过', implementation: '改 b.ts', requirement_refs: ['FR-4'] },
      ],
    }, EXEC)
    expect(out.success).toBe(true)
    expect(hh.repo.ledger.tasks).toHaveLength(2)
    // 终态②：RTM 覆盖表随拆分一起生成（任务↔条款绑定从此可查）
    const decomp = hh.docs.files.get('docs/requirements/REQ-000001/decomposition.md')?.content ?? ''
    expect(decomp, decomp).toContain('RTM 覆盖对照表')
    expect(decomp, decomp).toContain('| FR-4 | T-2 |')
  })

  it('等效合法路径：显式标「本轮不做」→ 同样通过（拦的是无记录，不是少做）', async () => {
    const hh = makeHarness({ requirements: [seededReq({}, [['T-1', '覆盖门禁']])], tasks: [] })
    hh.docs.put('docs/requirements/REQ-000001/requirement.md', REQ_MD.replace('**FR-4 三段可追溯**：需求↔任务↔证据。', '**FR-4 三段可追溯**：本轮不做（原因：依赖的证据链尚未就绪）。'))
    const out: any = await executeDecompose(hh.deps, {
      tasks: [{ key: 'T-1', title: '覆盖门禁', acceptance: 'npx vitest run a 通过', implementation: '改 a.ts', requirement_refs: ['FR-1'] }],
    }, EXEC)
    expect(out.success).toBe(true)
  })

  it('**存量需求零误伤**：artifacts 为空 → 同样的漏条款样例不被拦', async () => {
    const hh = makeHarness({ requirements: [seededReq({ artifacts: undefined }, [['T-1', '覆盖门禁']])], tasks: [] })
    hh.docs.put('docs/requirements/REQ-000001/requirement.md', REQ_MD)
    const out: any = await executeDecompose(hh.deps, {
      tasks: [{ key: 'T-1', title: '覆盖门禁', acceptance: 'npx vitest run a 通过', implementation: '改 a.ts' }],
    }, EXEC)
    expect(out.success).toBe(true)
  })
})

describe('E2E② 交付 → 三方一致性验收单', () => {
  const verifyingReq = () => seededReq({
    status: 'implementing',
    artifacts: [
      { stage: 'planning', kind: 'plan', path: 'docs/requirements/REQ-000001/plan.md' },
      { stage: 'decomposing', kind: 'decomposition', path: 'docs/requirements/REQ-000001/decomposition.md' },
    ],
  })

  const seedTasks = (hh: any) => {
    hh.repo.ledger.tasks.push(
      task({ id: 't-aaa111', status: 'done', acceptance: 'npx vitest run tests/a.test.ts 通过', lastReport: { at: 1, reportIndex: 1, filesChanged: [], completed: ['npx vitest run tests/a.test.ts 3 passed'] } }),
      task({ id: 't-bbb222', status: 'done', acceptance: 'npx vitest run tests/b.test.ts 通过', lastReport: { at: 1, reportIndex: 1, filesChanged: [], completed: ['npx vitest run tests/b.test.ts 2 passed'] } }),
    )
  }
  /** RTM：只有 T-1 接了 FR-1；FR-4 无人接 → 三方比对必报"实施缺失" */
  const RTM_GAP = doc(
    '## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）', '',
    '| 根编号 | 计划 key | 任务 id | 标题 | 状态 |', '|---|---|---|---|---|',
    '| FR-1 | T-1 | t-aaa111 | 覆盖门禁 | done |',
  )
  const RTM_OK = doc(
    '## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）', '',
    '| 根编号 | 计划 key | 任务 id | 标题 | 状态 |', '|---|---|---|---|---|',
    '| FR-1 | T-1 | t-aaa111 | 覆盖门禁 | done |',
    '| FR-4 | T-2 | t-bbb222 | 三段可追溯 | done |',
  )
  const DESIGN = doc('# 架构', '', '## D-ARCH-1 覆盖 `serves: FR-1`', '', '## D-ARCH-2 追溯 `serves: FR-4`')

  it('需求有编号、**无设计**（FR-4 无设计章节）、**无实施**（RTM 里 FR-4 无卡）→ 验收单出现「三方一致性」缺口项', async () => {
    const hh = makeHarness({ requirements: [verifyingReq()], tasks: [] })
    seedTasks(hh)
    hh.docs.put('docs/requirements/REQ-000001/requirement.md', REQ_MD)
    hh.docs.put('docs/requirements/REQ-000001/decomposition.md', RTM_GAP)
    hh.docs.put('docs/requirements/REQ-000001/design/architecture.md', DESIGN)
    const out: any = await submitVerification(hh.deps, { summary: '交付完成', evidence: ['npx vitest run 全绿'] }, EXEC)
    expect(out.success).toBe(true)
    const sheet = hh.repo.ledger.requirements[0].verification?.sheet
    const item = sheet?.items.find((i: any) => i.criterion.includes('三方一致性'))
    expect(item, '验收单应当出现三方一致性缺口项').toBeDefined()
    expect(item?.criterion).toContain('FR-4')
    expect(item?.criterion).toContain('实施缺失')
  })

  it('补齐后（设计+实施都到位）→ 验收单**不再**出现缺口项（证明该项是活的，不是常驻噪声）', async () => {
    const hh = makeHarness({ requirements: [verifyingReq()], tasks: [] })
    seedTasks(hh)
    hh.docs.put('docs/requirements/REQ-000001/requirement.md', REQ_MD)
    hh.docs.put('docs/requirements/REQ-000001/decomposition.md', RTM_OK)
    hh.docs.put('docs/requirements/REQ-000001/design/architecture.md', DESIGN)
    const out: any = await submitVerification(hh.deps, { summary: '交付完成', evidence: ['npx vitest run 全绿'] }, EXEC)
    expect(out.success).toBe(true)
    const sheet = hh.repo.ledger.requirements[0].verification?.sheet
    expect(sheet?.items.some((i: any) => i.criterion.includes('三方一致性'))).toBe(false)
  })
})
