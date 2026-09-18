/**
 * 全链路映射门禁单测（REQ-d3e61a T-7 / serve TC-011）
 *
 * 验收口径：设计章节缺映射 → 提交计划被拒；测试文件缺映射 → 验收面出现"孤儿用例"项。
 */
import { describe, expect, it } from 'vitest'
import {
  checkDesignServesGate, testFileHasServesHeader, testFilesFromDesign, collectOrphanTestFiles,
} from '../src/application/internal/content-gate-wiring.js'
import { parseDocument } from '../src/application/internal/content-gates.js'
import { buildSheet } from '../src/domain/workflow/AcceptanceSheetSpec.js'

const doc = (...lines: string[]) => lines.join('\n')

const DES_OK = doc(
  '# 架构设计', '',
  '## D-ARCH-1 三级门禁 `serves: FR-12`', '正文。', '',
  '## D-ARCH-2 编号模型 `serves: FR-2`', '正文。',
)
const DES_ORPHAN = doc(
  '# 架构设计', '',
  '## D-ARCH-1 三级门禁 `serves: FR-12`', '正文。', '',
  '## D-ARCH-2 忘了标注', '正文。',
)

const fakeDocs = (files: Record<string, string>) => ({
  exists: (p: string) => Object.prototype.hasOwnProperty.call(files, p),
  read: async (p: string) => files[p] ?? '',
  list: (dir: string) => Object.keys(files)
    .filter(k => k.startsWith(dir + '/'))
    .map(k => ({ name: k.slice(dir.length + 1), isFile: true })),
})

const live = { id: 'REQ-t', artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: 'x' }] } as any
const D = 'docs/requirements/REQ-t/design'

describe('checkDesignServesGate（设计章节缺映射 → 被拒）', () => {
  it('有章节缺 serves → design_orphan，且点出「文件 → 章节」', async () => {
    const r = await checkDesignServesGate(fakeDocs({ [D + '/architecture.md']: DES_ORPHAN }), live)
    expect(r).toBeDefined()
    expect(r?.code).toBe('design_orphan')
    expect((r?.gaps ?? []).join(' ')).toContain('architecture.md')
    expect((r?.gaps ?? []).join(' ')).toContain('D-ARCH-2')
  })

  it('每节都有 serves → 不拦', async () => {
    expect(await checkDesignServesGate(fakeDocs({ [D + '/architecture.md']: DES_OK }), live)).toBeUndefined()
  })

  it('存量需求 / 无设计目录 → 不拦（避免误拦）', async () => {
    const docs = fakeDocs({ [D + '/architecture.md']: DES_ORPHAN })
    expect(await checkDesignServesGate(docs, { id: 'REQ-t', artifacts: undefined } as any)).toBeUndefined()
    expect(await checkDesignServesGate(fakeDocs({}), live)).toBeUndefined()
  })
})

describe('testFileHasServesHeader（只看头部 20 行）', () => {
  it('头部有 serves → true', () => {
    expect(testFileHasServesHeader('// serve TC-011\n// serves: FR-5\n\nimport x')).toBe(true)
  })
  it('没有 serves → false', () => {
    expect(testFileHasServesHeader('// 这个文件没声明覆盖\nimport x')).toBe(false)
  })
  it('serves 出现在第 20 行之后 → 不算（约定是顶部注释块）', () => {
    const body = Array.from({ length: 25 }, () => '// filler').join('\n') + '\n// serves: FR-5'
    expect(testFileHasServesHeader(body)).toBe(false)
  })
})

describe('testFilesFromDesign', () => {
  it('从「实际文件」列取路径', () => {
    const md = doc(
      '| 用例ID | 实际文件 | serves |',
      '|--------|---------|--------|',
      '| TC-001 | tests/a.test.ts | FR-5 |',
      '| TC-002 | tests/b.test.ts | FR-5 |',
    )
    expect(testFilesFromDesign(parseDocument(md))).toEqual(['tests/a.test.ts', 'tests/b.test.ts'])
  })
  it('没有该列 → 空数组（不猜）', () => {
    expect(testFilesFromDesign(parseDocument(doc('| A | B |', '|---|---|', '| 1 | 2 |')))).toEqual([])
  })
})

describe('collectOrphanTestFiles（缺映射的用例 = 孤儿）', () => {
  const design = doc(
    '| 用例ID | 实际文件 | serves |',
    '|--------|---------|--------|',
    '| TC-001 | tests/ok.test.ts | FR-5 |',
    '| TC-002 | tests/orphan.test.ts | FR-5 |',
  )

  it('点名了但头部没声明 → 计入孤儿', async () => {
    const orphans = await collectOrphanTestFiles(fakeDocs({
      [D + '/test-cases.md']: design,
      'tests/ok.test.ts': '// serves: FR-5\nimport x',
      'tests/orphan.test.ts': '// 没声明\nimport x',
    }), live)
    expect(orphans).toEqual(['tests/orphan.test.ts'])
  })

  it('全部声明 → 无孤儿', async () => {
    const orphans = await collectOrphanTestFiles(fakeDocs({
      [D + '/test-cases.md']: design,
      'tests/ok.test.ts': '// serves: FR-5',
      'tests/orphan.test.ts': '// serves: FR-5',
    }), live)
    expect(orphans).toEqual([])
  })

  it('设计文件不存在 → 空（不猜、不误报）', async () => {
    expect(await collectOrphanTestFiles(fakeDocs({}), live)).toEqual([])
  })
})

describe('验收单可见性：缺映射必须成为一项（不靠人记得）', () => {
  const base = {
    sheetHistoryLength: 0,
    tasks: [{ id: 't-1', title: 'A', acceptance: '验收标准' }],
    evidence: ['ev'],
    generatedAt: 1,
    generatedBy: { kind: 'agent', sessionId: 'w' },
  } as any

  it('有孤儿 → 追加一条需求级项，criterion 点名文件，状态 pending', () => {
    const r = buildSheet({ ...base, orphanTestFiles: ['tests/a.test.ts'] })
    const item = r.sheet.items.find(i => i.criterion.includes('孤儿用例'))
    expect(item).toBeDefined()
    expect(item?.criterion).toContain('tests/a.test.ts')
    expect(item?.status).toBe('pending')
  })

  it('无孤儿 → 不追加（不制造噪声）', () => {
    const r = buildSheet(base)
    expect(r.sheet.items.some(i => i.criterion.includes('孤儿用例'))).toBe(false)
  })
})
