/**
 * 卡面产物 chips + 五门确认入口 + 派生展示 单测（REQ-31e11f t7）。
 * 覆盖：chip 三态渲染（已确认/待确认/缺失）、确认按钮卡面外置（不在抽屉）、
 * 分类差异化（bug 少门）、confirm-artifact 动作属性。
 */
import { describe, it, expect } from 'vitest'
import { buildBoard } from '../src/client/view.ts'
import type { BoardState, RequirementRecord, StageArtifact } from '../src/client/types.ts'

// -- 测试数据构造 ---------------------------------------------------------

let seq = 0
const rid = (p: string) => `${p}-${String(++seq).padStart(6, '0')}`

function makeReq(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: rid('REQ'), title: '需求', description: '', status: 'draft',
    blocked: false, comments: [], version: 1,
    createdAt: 1700000000000, updatedAt: 1700000000000,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...over,
  }
}

function makeArtifact(over: Partial<StageArtifact> = {}): StageArtifact {
  return {
    stage: 'brainstorming',
    kind: 'requirement',
    path: 'docs/requirements/REQ-001/requirement.md',
    registeredAt: 1700000000000,
    registeredBy: { kind: 'agent' },
    ...over,
  }
}

function makeState(over: Partial<BoardState> = {}): BoardState {
  return { revision: 1, requirements: [], tasks: [], ready: {}, ...over }
}

// -- 产物 chip 三态 --------------------------------------------------------

describe('产物 chips（四道人工确认门）', () => {
  it('已确认产物渲染绿✓ chip', () => {
    const req = makeReq({
      id: 'REQ-chip-confirmed',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [makeArtifact({ kind: 'requirement', confirmedAt: 1700000100000, confirmedBy: { kind: 'human' } })],
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).toContain('dsh-pm-artifact-chip confirmed')
    expect(html).toContain('✓ 需求文档')
  })

  it('待确认产物渲染橙⏳ chip（可点击确认）', () => {
    const req = makeReq({
      id: 'REQ-chip-pending',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [makeArtifact({ kind: 'requirement' })], // 无 confirmedAt
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).toContain('dsh-pm-artifact-chip pending')
    expect(html).toContain('⏳ 需求文档')
    // 待确认 chip 带 confirm-artifact 动作
    expect(html).toContain('data-action="confirm-artifact"')
    expect(html).toContain('data-kind="requirement"')
  })

  it('缺失产物渲染红✗ chip', () => {
    const req = makeReq({
      id: 'REQ-chip-missing',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [], // 无产物
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).toContain('dsh-pm-artifact-chip missing')
    expect(html).toContain('✗ 需求文档')
  })

  it('feature 分类显示全部五类产物 chip（REQ-9f4a44 后门为四道、产物仍五类）', () => {
    const req = makeReq({
      id: 'REQ-chip-five',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [
        makeArtifact({ kind: 'requirement', stage: 'brainstorming' }),
        makeArtifact({ kind: 'plan', stage: 'design' }),
        makeArtifact({ kind: 'decomposition', stage: 'decomposing' }),
        makeArtifact({ kind: 'verification', stage: 'accepting' }),
        // REQ-9f4a44：archive 产物挂在 archived 阶段（done 已移除）
        makeArtifact({ kind: 'archive', stage: 'archived' }),
      ],
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    // REQ-9f4a44：chip 按"门"生成 → 四道门对应四个产物 chip
    expect(html).toContain('需求文档')
    expect(html).toContain('设计文档')
    expect(html).toContain('拆分计划')
    expect(html).toContain('验收材料')
    // 归档材料不再是门（验收通过即归档），其状态由 archived 泳道的「归档材料待补」标记表达
    expect(html).not.toContain('✗ 归档材料')
  })
})

// -- 确认入口卡面外置 ------------------------------------------------------

describe('确认入口卡面外置', () => {
  it('当前门产物待确认时，卡片正面有「确认产物」按钮', () => {
    const req = makeReq({
      id: 'REQ-confirm-btn',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [makeArtifact({ kind: 'requirement' })], // 待确认
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    // 卡面正面有确认按钮（不是抽屉里）
    expect(html).toContain('确认产物')
    expect(html).toContain('data-action="confirm-artifact"')
    expect(html).toContain('data-id="REQ-confirm-btn"')
    expect(html).toContain('data-kind="requirement"')
    // 按钮在卡片正面：确认 HTML 包含确认按钮且不在详情抽屉里
    expect(html).toContain('确认产物')
    // 详情抽屉不应包含确认按钮（卡面外置，不在抽屉）
    expect(html).not.toContain('dsh-pm-detail')
  })

  it('当前门产物已确认时，不显示「确认产物」按钮', () => {
    const req = makeReq({
      id: 'REQ-no-confirm-btn',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [makeArtifact({ kind: 'requirement', confirmedAt: 1700000100000, confirmedBy: { kind: 'human' } })],
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    // 不应有确认按钮
    expect(html).not.toContain('确认产物')
  })

  it('当前门产物缺失时，不显示「确认产物」按钮（须先登记产物）', () => {
    const req = makeReq({
      id: 'REQ-missing-no-btn',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [],
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).not.toContain('确认产物')
  })

  it('无门状态（draft）不显示确认按钮', () => {
    const req = makeReq({
      id: 'REQ-draft-no-btn',
      status: 'draft',
      category: 'feature',
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).not.toContain('确认产物')
  })
})

// -- 分类差异化 ------------------------------------------------------------

describe('分类差异化：bug 少门', () => {
  it('bug 分类无需求分析门（brainstorming>design 门被跳过）', () => {
    const req = makeReq({
      id: 'REQ-bug-gates',
      status: 'design',
      category: 'bug',
      artifacts: [makeArtifact({ kind: 'design', stage: 'design' })],
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    // bug 分类不应显示需求文档 chip（该门被跳过）
    expect(html).not.toContain('需求文档')
    // 但应显示设计文档 chip（2026-09-21：design>decomposing 门锚定设计文档）
    expect(html).toContain('设计文档')
  })

  it('spike 分类只有验收归档一门', () => {
    const req = makeReq({
      id: 'REQ-spike-gates',
      status: 'implementing',
      category: 'spike',
      artifacts: [],
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    // spike 不应显示需求文档/拆分计划/拆分方案 chip
    expect(html).not.toContain('需求文档')
    expect(html).not.toContain('拆分计划')
    expect(html).not.toContain('拆分方案')
  })
})

// -- 派生展示 --------------------------------------------------------------

describe('派生展示', () => {
  it('显示产物完成度 n/m', () => {
    const req = makeReq({
      id: 'REQ-derived-nm',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [makeArtifact({ kind: 'requirement' })],
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    // 应有产物完成度显示（feature 全流水线 6 类产物，当前 1 个就位）
    expect(html).toContain('产物 1/6')
  })

  it('显示待确认门数', () => {
    const req = makeReq({
      id: 'REQ-derived-pending',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [makeArtifact({ kind: 'requirement' })], // 1 个待确认
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).toContain('1 门待确认')
  })

  it('全部确认后无待确认门数显示', () => {
    const req = makeReq({
      id: 'REQ-derived-all-confirmed',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [
        makeArtifact({ kind: 'requirement', confirmedAt: 1700000100000, confirmedBy: { kind: 'human' } }),
        makeArtifact({ kind: 'plan', confirmedAt: 1700000200000, confirmedBy: { kind: 'human' } }),
        makeArtifact({ kind: 'decomposition', confirmedAt: 1700000300000, confirmedBy: { kind: 'human' } }),
        makeArtifact({ kind: 'verification', confirmedAt: 1700000400000, confirmedBy: { kind: 'human' } }),
        makeArtifact({ kind: 'archive', confirmedAt: 1700000500000, confirmedBy: { kind: 'human' } }),
      ],
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).not.toContain('门待确认')
  })
})

// -- confirm-artifact 动作属性 ----------------------------------------------

describe('confirm-artifact 动作', () => {
  it('待确认 chip 带 confirm-artifact data-action', () => {
    const req = makeReq({
      id: 'REQ-action-confirm',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [makeArtifact({ kind: 'requirement' })],
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).toContain('data-action="confirm-artifact"')
    expect(html).toContain('data-id="REQ-action-confirm"')
    expect(html).toContain('data-kind="requirement"')
  })

  it('确认按钮带 confirm-artifact data-action', () => {
    const req = makeReq({
      id: 'REQ-action-btn',
      status: 'brainstorming',
      category: 'feature',
      artifacts: [makeArtifact({ kind: 'requirement' })],
    })
    const html = buildBoard(makeState({ requirements: [req] }))
    // 主确认按钮也带 confirm-artifact
    const btnMatch = html.match(/<button[^>]*data-action="confirm-artifact"[^>]*>/g)
    expect(btnMatch).not.toBeNull()
    expect(btnMatch!.length).toBeGreaterThanOrEqual(2) // chip + 主按钮
  })
})