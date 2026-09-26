/**
 * t6-t11 · 六个节点 RTM 生成器 + 任务详情增量更新（FR-1 / FR-2 / FR-6 / FR-10 / FR-11）。
 */
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { readRTM } from '../../src/rtm/file-io.js'
import { generateAcceptingRTM } from '../../src/rtm/accepting-generator.js'
import { generateBrainstormingRTM } from '../../src/rtm/brainstorming-generator.js'
import { generateDecomposingRTM } from '../../src/rtm/decomposing-generator.js'
import { generateDesignRTM } from '../../src/rtm/design-generator.js'
import { generateImplementingRTM, initialWorkflow, updateTaskDetail, workflowPhasesFor } from '../../src/rtm/implementing-generator.js'
import { generateLifecycleRTM, stageOfStatus } from '../../src/rtm/lifecycle-generator.js'
import { RTMGenerator } from '../../src/rtm/generator.js'
import { RTMContext } from '../../src/rtm/context.js'
import type { RTMAccepting, RTMBrainstorming, RTMDecomposing, RTMDesign, RTMImplementing, RTMLifecycle, RTMTaskDetail } from '../../src/rtm/types.js'
import { DESIGN_MD, fiveTasks, makeFixture, REQUIREMENT_MD, TEST_CASES_MD } from './fixture.js'

function setup() {
  const f = makeFixture()
  f.writeDoc('requirement.md', REQUIREMENT_MD)
  f.writeDoc('design/architecture.md', DESIGN_MD)
  f.writeDoc('design/test-cases.md', TEST_CASES_MD)
  f.setTasks(fiveTasks())
  return f
}

describe('lifecycle-generator (t6)', () => {
  it('立项生成骨架：七个阶段、当前 draft', () => {
    const f = makeFixture()
    const rtm = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger, generatedBy: 'test' }).generateLifecycle(f.reqId)
    expect(rtm.lifecycle.current_stage).toBe('draft')
    expect(rtm.lifecycle.stages.map(s => s.stage)).toEqual(['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'done'])
    expect(rtm.lifecycle.stages[0]?.status).toBe('in_progress')
    expect(rtm.lifecycle.stages[1]?.status).toBe('pending')
    expect(rtm.metadata.version).toBe(1)
    expect(existsSync(join(f.reqDir, 'rtm-lifecycle.yml'))).toBe(true)
    // 绑定窗口进快照（Dive 唤醒要按它投递）
    expect(rtm.requirement.source_session).toBe('session-fixture-1')
    // 绝对路径自定位：需求目录 + 本文件
    expect(rtm.requirement.dir).toBe(f.reqDir)
    expect(rtm.metadata.file_path).toBe(join(f.reqDir, 'rtm-lifecycle.yml'))
    // 节点清单 + 计数（缺省全流水线 = 7 个节点，全部启用）
    expect(rtm.lifecycle.stage_count).toBe(7)
    expect(rtm.lifecycle.stage_list).toEqual(['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'done'])
    expect(rtm.lifecycle.stages.every(s => s.enabled === true)).toBe(true)
  })

  it('节点清单按分类档案：跳过的节点不在 stage_list 里，且 stages[] 标 enabled=false', () => {
    const f = makeFixture()
    // spike 档案（shared/protocol CATEGORY_FLOW_PROFILES）= draft + implementing + accepting + archived
    const gen = new RTMGenerator({
      workspaceRoot: f.root,
      ledger: f.ledger,
      enabledStagesOf: () => ['draft', 'implementing', 'accepting', 'done'],
    })
    const rtm = gen.generateLifecycle(f.reqId)
    expect(rtm.lifecycle.stage_count).toBe(4)
    expect(rtm.lifecycle.stage_list).toEqual(['draft', 'implementing', 'accepting', 'done'])
    const byStage = Object.fromEntries(rtm.lifecycle.stages.map(s => [s.stage, s.enabled]))
    expect(byStage.brainstorming).toBe(false)
    expect(byStage.design).toBe(false)
    expect(byStage.implementing).toBe(true)
  })

  it('未绑定窗口 → 不写 source_session（缺省即未绑定，不伪造空串）', () => {
    const f = makeFixture()
    f.patchRequirement({ sourceSessionId: undefined })
    const rtm = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger }).generateLifecycle(f.reqId)
    expect(rtm.requirement.source_session).toBeUndefined()
  })

  it('阶段派生：archived → done，已过阶段 completed', () => {
    expect(stageOfStatus('archived')).toBe('done')
    expect(stageOfStatus('weird')).toBe('draft')
    const f = makeFixture()
    f.patchRequirement({ status: 'implementing' })
    const rtm = generateLifecycleRTM(new RTMContext({ workspaceRoot: f.root, ledger: f.ledger }), f.reqId)
    const byStage = Object.fromEntries(rtm.lifecycle.stages.map(s => [s.stage, s.status]))
    expect(byStage['draft']).toBe('completed')
    expect(byStage['implementing']).toBe('in_progress')
    expect(byStage['accepting']).toBe('pending')
  })

  it('确认产物落到对应阶段', () => {
    const f = makeFixture()
    f.patchRequirement({
      status: 'design',
      artifacts: [{ kind: 'requirement', path: 'requirement.md', confirmedAt: 1000 }],
    })
    const rtm = generateLifecycleRTM(new RTMContext({ workspaceRoot: f.root, ledger: f.ledger }), f.reqId)
    const brain = rtm.lifecycle.stages.find(s => s.stage === 'brainstorming')
    expect(brain?.artifacts?.[0]?.kind).toBe('requirement')
  })
})

describe('brainstorming-generator (t7)', () => {
  it('提取 3 个 FR，产物确认态落章', () => {
    const f = setup()
    f.patchRequirement({ status: 'brainstorming', artifacts: [{ kind: 'requirement', path: 'requirement.md', confirmedAt: 2000 }] })
    const rtm = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger }).generateBrainstorming(f.reqId)
    expect(rtm.outputs.requirements.map(r => r.id)).toEqual(['FR-1', 'FR-2', 'FR-3'])
    expect(rtm.status?.artifacts[0]?.confirmed).toBe(true)
    expect(readRTM<RTMBrainstorming>(join(f.reqDir, 'rtm-brainstorming.yml'))?.outputs.requirements).toHaveLength(3)
  })
})

describe('design-generator (t8)', () => {
  it('两个章节、FR-1/FR-2 有设计，覆盖度 67%', () => {
    const f = setup()
    new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger }).generateBrainstorming(f.reqId)
    const rtm = generateDesignRTM(new RTMContext({ workspaceRoot: f.root, ledger: f.ledger }), f.reqId)
    expect(rtm.outputs.design_sections).toHaveLength(2)
    expect(rtm.traceability.fr_to_design['FR-1']).toEqual(['design/architecture.md#1.1'])
    expect(rtm.coverage.design.total_frs).toBe(3)
    expect(rtm.coverage.design.covered_frs).toBe(2)
    expect(rtm.coverage.design.rate).toBe(67)
    expect(rtm.coverage.design.uncovered).toEqual(['FR-3'])
  })
})

describe('decomposing-generator (t9)', () => {
  it('五个任务、设计 → 任务映射、实施覆盖度 100%', () => {
    const f = setup()
    const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger })
    gen.generateBrainstorming(f.reqId)
    gen.generateDesign(f.reqId)
    const rtm = gen.generateDecomposing(f.reqId)
    expect(rtm.outputs.tasks).toHaveLength(5)
    expect(rtm.traceability.design_to_tasks['design/architecture.md#1.1']).toContain('t-0001')
    expect(rtm.traceability.fr_to_tasks['FR-1']).toEqual(['t-0001', 't-0004'])
    expect(rtm.coverage.implementation.total_designs).toBe(2)
    expect(rtm.coverage.implementation.rate).toBe(100)
  })

  it('无任务的设计章节暴露为 uncovered', () => {
    const f = setup()
    f.setTasks([{ id: 't-0009', title: '只做 FR-1', status: 'todo', serves: ['FR-1'] }])
    const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger })
    gen.generateBrainstorming(f.reqId)
    gen.generateDesign(f.reqId)
    const rtm = gen.generateDecomposing(f.reqId)
    expect(rtm.coverage.implementation.uncovered).toEqual(['design/architecture.md#1.2'])
    expect(rtm.coverage.implementation.rate).toBe(50)
  })
})

describe('implementing-generator (t10/t11)', () => {
  it('汇总统计 + 每任务一个详情文件，workflow 按 phase 初始化', () => {
    const f = setup()
    const rtm: RTMImplementing = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger }).generateImplementing(f.reqId)
    expect(rtm.status).toEqual({ tasks_total: 5, tasks_done: 0, tasks_in_progress: 0, tasks_todo: 5 })
    for (const t of ['t-0001', 't-0002', 't-0003', 't-0004', 't-0005']) {
      expect(existsSync(join(f.reqDir, 'rtm-implementing', t + '.yml'))).toBe(true)
    }
    const ui = readRTM<RTMTaskDetail>(join(f.reqDir, 'rtm-implementing', 't-0004.yml'))
    expect(ui?.task.workflow.map(w => w.phase)).toEqual(['ui', 'implement', 'test', 'commit'])
    const impl = readRTM<RTMTaskDetail>(join(f.reqDir, 'rtm-implementing', 't-0001.yml'))
    expect(impl?.task.workflow).toHaveLength(1)
    expect(impl?.task.workflow_params['TASK_ID']).toBe('t-0001')
  })

  it('phase/side → 子阶段映射（backend 跳过 ui）', () => {
    expect(workflowPhasesFor('implement')).toEqual(['implement'])
    expect(workflowPhasesFor('doc')).toEqual(['doc', 'implement', 'test', 'commit'])
    expect(workflowPhasesFor(undefined)).toHaveLength(7)
    expect(initialWorkflow(['ui', 'implement'], 'backend')[0]).toEqual({ phase: 'ui', status: 'skipped', skip_reason: 'backend task, no UI needed' })
  })

  it('任务状态变更：详情与汇总同步（以台账为事实源）', () => {
    const f = setup()
    const ctx = new RTMContext({ workspaceRoot: f.root, ledger: f.ledger })
    generateImplementingRTM(ctx, f.reqId)
    const t1 = f.task('t-0001')!
    t1.status = 'in_progress'
    const detail = updateTaskDetail(ctx, f.reqId, 't-0001', { status: 'in_progress' })
    expect(detail?.task.status).toBe('in_progress')
    expect(detail?.task.workflow[0]?.status).toBe('in_progress')
    expect(detail?.task.workflow[0]?.started_at).toBeTruthy()
    const summary = readRTM<RTMImplementing>(join(f.reqDir, 'rtm-implementing.yml'))
    expect(summary?.status).toMatchObject({ tasks_in_progress: 1, tasks_todo: 4, tasks_done: 0 })

    t1.status = 'done'
    updateTaskDetail(ctx, f.reqId, 't-0001', { status: 'done', workflow: [{ phase: 'implement', status: 'done' }] })
    const summary2 = readRTM<RTMImplementing>(join(f.reqDir, 'rtm-implementing.yml'))
    expect(summary2?.status).toMatchObject({ tasks_done: 1, tasks_in_progress: 0 })
    const detail2 = readRTM<RTMTaskDetail>(join(f.reqDir, 'rtm-implementing', 't-0001.yml'))
    expect(detail2?.task.workflow[0]?.completed_at).toBeTruthy()
    expect(detail2?.task.workflow_done).toBe(1)
  })

  it('未知任务不会凭空造文件', () => {
    const f = setup()
    const ctx = new RTMContext({ workspaceRoot: f.root, ledger: f.ledger })
    expect(updateTaskDetail(ctx, f.reqId, 't-nope', { status: 'done' })).toBeNull()
  })

  it('版本号每次更新 +1（FR-6）', () => {
    const f = setup()
    const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger })
    gen.generateLifecycle(f.reqId)
    gen.generateLifecycle(f.reqId)
    gen.generateLifecycle(f.reqId)
    expect(readRTM<RTMLifecycle>(join(f.reqDir, 'rtm-lifecycle.yml'))?.metadata.version).toBe(3)
  })
})

describe('accepting-generator (t11)', () => {
  it('两个测试用例、任务 → 测试映射、测试覆盖度 40%', () => {
    const f = setup()
    const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger })
    gen.generateBrainstorming(f.reqId)
    gen.generateDesign(f.reqId)
    gen.generateDecomposing(f.reqId)
    const rtm: RTMAccepting = gen.generateAccepting(f.reqId)
    expect(rtm.outputs.test_cases.map(t => t.id)).toEqual(['TC-1', 'TC-2'])
    expect(rtm.traceability.task_to_tests['t-0001']).toEqual(['TC-1'])
    expect(rtm.coverage.testing.total_tasks).toBe(5)
    expect(rtm.coverage.testing.tested_tasks).toBe(2)
    expect(rtm.coverage.testing.rate).toBe(40)
  })
})

describe('生成器规模约束 (t10 / FR-10)', () => {
  it('汇总文件保持轻量（不内联任务详情）', () => {
    const f = setup()
    new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger }).generateImplementing(f.reqId)
    const text = readRTM<RTMImplementing>(join(f.reqDir, 'rtm-implementing.yml'))
    expect(text?.tasks.every(t => !('workflow' in t))).toBe(true)
  })
})
