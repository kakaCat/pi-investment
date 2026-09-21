/**
 * 节点设卡矩阵（REQ-d3e61a T-17 / serve FR-12）
 *
 * 验收口径：**五个节点各构造"条款无着落"样例 → 每站均返回拒绝；存量需求 → 返回通过（不拦）**。
 *
 * 本文件是**固化验证**：五个节点的内容门禁分别在 T-3/T-4/T-6/T-7/T-9/T-13 落地，
 * 这里把它们摆成一张矩阵——每一站"有缺陷则拦、合规则过、存量则免"，
 * 防止将来某站被悄悄摘掉而无人发现（R9 的教训正是"某一站没人守"）。
 */
import { describe, expect, it } from 'vitest'
import {
  assertClauseCoverageGate,
  checkDesignServesGate,
  checkNumberChainGate,
  doneEvidenceAnchorFailure,
} from '../src/application/internal/content-gate-wiring.js'
import { missingCategoryDocs } from '../src/application/internal/category-doc-sets.js'
import { checkHowToVerify } from '../src/domain/task/Acceptability.js'

const doc = (...lines: string[]) => lines.join('\n')

const fakeDocs = (files: Record<string, string>) => ({
  exists: (p: string) => Object.prototype.hasOwnProperty.call(files, p),
  read: async (p: string) => files[p] ?? '',
  list: (dir: string) => Object.keys(files)
    .filter(k => k.startsWith(dir + '/'))
    .map(k => ({ name: k.slice(dir.length + 1), isFile: true })),
})

const REQ_OK = doc(
  '# 需求', '',
  '## 问题', '',
  '## 边界', '',
  '## 成功标准', '',
  '## 产品定义', '',
  '## 用户与角色', '',
  '## 功能点', '',
  '**FR-1 覆盖门禁**：拆分时逐条核对。', '',
  '**FR-4 三段可追溯**：需求↔任务↔证据。',
)

/** 五站的"条款无着落"样例（每站一个缺陷），与"合规样例"成对。 */
interface Station {
  node: string
  /** 该站的缺陷样例：返回非空 = 被拦 */
  broken: () => Promise<unknown>
  /** 合规样例：返回 undefined = 放行 */
  ok: () => Promise<unknown>
  /** 存量需求样例（仅对有 isLegacy 守卫的站适用） */
  legacy?: () => Promise<unknown>
}

const liveReq = { id: 'REQ-t', category: 'feature', artifacts: [{ stage: 'design', kind: 'plan', path: 'p' }] } as any
const legacyReq = { id: 'REQ-t', category: 'feature', artifacts: undefined } as any

const BASE_DOCS = {
  'docs/requirements/REQ-t/requirement.md': REQ_OK,
  'docs/requirements/REQ-t/decomposition.md': doc(
    '| 根编号 | 计划 key | 任务 id | 标题 | 状态 |', '|---|---|---|---|---|',
    '| FR-1 | T-1 | t-aaa111 | 覆盖门禁 | done |',
    '| FR-4 | T-1 | t-aaa111 | 三段可追溯 | done |',
  ),
  'docs/requirements/REQ-t/design/architecture.md': doc('# 架构', '', '## D-ARCH-1 门禁 `serves: FR-1`', '', '## D-ARCH-2 追溯 `serves: FR-4`'),
}

const stations: Station[] = [
  {
    node: '需求（分类文档集）',
    broken: async () => {
      // 缺陷：根文档缺 feature 的必填节「功能点」
      const bad = REQ_OK.replace('## 功能点', '## 别的')
      return missingCategoryDocs({ category: 'feature', rootExists: true, rootText: bad, designNames: ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md'] })[0]
    },
    ok: async () => missingCategoryDocs({ category: 'feature', rootExists: true, rootText: REQ_OK, designNames: ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md'] })[0],
  },
  {
    node: '计划（设计章节可追溯 + 编号不悬空）',
    broken: async () => {
      const docs = fakeDocs({ ...BASE_DOCS, 'docs/requirements/REQ-t/design/architecture.md': doc('# 架构', '', '## D-ARCH-1 忘了标注') })
      return checkDesignServesGate(docs as any, liveReq)
    },
    ok: async () => checkDesignServesGate(fakeDocs(BASE_DOCS) as any, liveReq),
    legacy: async () => checkDesignServesGate(fakeDocs({ ...BASE_DOCS, 'docs/requirements/REQ-t/design/architecture.md': doc('## D-ARCH-1 忘了标注') }) as any, legacyReq),
  },
  {
    node: '计划（编号悬空）',
    broken: () => checkNumberChainGate(fakeDocs({ ...BASE_DOCS, 'docs/requirements/REQ-t/design/architecture.md': doc('## D-ARCH-1 悬空 `serves: FR-99`') }) as any, liveReq).then(r => r.failure),
    ok: () => checkNumberChainGate(fakeDocs(BASE_DOCS) as any, liveReq).then(r => r.failure),
    legacy: () => checkNumberChainGate(fakeDocs({ ...BASE_DOCS, 'docs/requirements/REQ-t/design/architecture.md': doc('## D-ARCH-1 悬空 `serves: FR-99`') }) as any, legacyReq).then(r => r.failure),
  },
  {
    node: '拆分（条款覆盖门禁 —— R9 的堵口）',
    broken: async () => {
      // 缺陷：FR-4 没有任何卡接收、也没标"本轮不做"
      const bad = REQ_OK + '\n\n## 测试策略\n\n| 层级 | 数量 |\n|---|---|\n| 单元 | 3 |\n'
      return assertClauseCoverageGate(fakeDocs({ 'docs/requirements/REQ-t/requirement.md': bad }) as any, liveReq, [{ key: 'T-1', requirement_refs: ['FR-1'] }])
    },
    ok: () => assertClauseCoverageGate(fakeDocs(BASE_DOCS) as any, liveReq, [{ key: 'T-1', requirement_refs: ['FR-1', 'FR-4'] }]),
    legacy: () => assertClauseCoverageGate(fakeDocs(BASE_DOCS) as any, legacyReq, []),
  },
  {
    node: '实施（结单证据锚定）',
    broken: () => doneEvidenceAnchorFailure(fakeDocs(BASE_DOCS) as any, {
      taskId: 't-aaa111', to: 'done', tasks: [{ id: 't-aaa111', requirementId: 'REQ-t', lastReport: { completed: ['已完成'] } }], boundRequirementIds: ['REQ-t'],
    }),
    ok: () => doneEvidenceAnchorFailure(fakeDocs(BASE_DOCS) as any, {
      taskId: 't-aaa111', to: 'done', tasks: [{ id: 't-aaa111', requirementId: 'REQ-t', lastReport: { completed: ['npx vitest run tests/x.test.ts 3 passed'] } }], boundRequirementIds: ['REQ-t'],
    }),
    legacy: () => doneEvidenceAnchorFailure(fakeDocs({}) as any, {
      taskId: 't-aaa111', to: 'done', tasks: [{ id: 't-aaa111', requirementId: 'REQ-t', lastReport: { completed: ['已完成'] } }], boundRequirementIds: ['REQ-t'],
    }),
  },
  {
    node: '验收（验收项必须能照着验）',
    broken: async () => checkHowToVerify('任务一', '确认可用').ok ? undefined : '缺怎么验',
    ok: async () => checkHowToVerify('任务一', '跑 npx vitest run tests/x.test.ts 通过').ok ? undefined : '不该被拦',
  },
]

describe('五站设卡矩阵：有缺陷则拦、合规则过、存量则免', () => {
  for (const st of stations) {
    it(st.node, async () => {
      // ① 缺陷样例 → 被拦
      const broken = await st.broken()
      expect(broken, st.node + ' 的缺陷样例应当被拦').toBeDefined()
      // ② 合规样例 → 放行
      expect(await st.ok(), st.node + ' 的合规样例不应被拦').toBeUndefined()
      // ③ 存量需求 → 豁免（仅对有 isLegacy 守卫的站）
      if (st.legacy !== undefined) {
        expect(await st.legacy(), st.node + ' 的存量需求应当豁免').toBeUndefined()
      }
    })
  }

  it('**每一站都必须存在**（防止某站被摘掉而无人发现——R9 的教训）', () => {
    const nodes = stations.map(s => s.node)
    expect(nodes.some(n => n.startsWith('需求'))).toBe(true)
    expect(nodes.some(n => n.startsWith('计划'))).toBe(true)
    expect(nodes.some(n => n.startsWith('拆分'))).toBe(true)
    expect(nodes.some(n => n.startsWith('实施'))).toBe(true)
    expect(nodes.some(n => n.startsWith('验收'))).toBe(true)
  })
})
