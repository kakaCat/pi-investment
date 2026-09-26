/**
 * t19 · 端到端测试：完整需求流程 7 个触发点（FR-1/2/3/4/5/7/10）。
 *
 * 用一个临时需求走一遍：立项 → 提交需求 → 确认 → 提交设计 → 批准拆分 →
 * 任务状态变更 → 提交验收，逐点校验 RTM 文件、追溯链与覆盖度数字。
 */
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { readRTM } from '../../src/rtm/file-io.js'
import { RTMGenerator, runRTMTrigger } from '../../src/rtm/generator.js'
import { buildTraceabilityChain } from '../../src/rtm/traceability-builder.js'
import { assembleStageOverviewRTM } from '../../src/stage-overview/assembler.js'
import type { RTMAccepting, RTMDesign, RTMImplementing, RTMLifecycle } from '../../src/rtm/types.js'
import { DESIGN_MD, fiveTasks, makeFixture, REQUIREMENT_MD, TEST_CASES_MD } from '../rtm/fixture.js'

const RTM_FILES = [
  'rtm-lifecycle.yml',
  'rtm-brainstorming.yml',
  'rtm-design.yml',
  'rtm-decomposing.yml',
  'rtm-implementing.yml',
  'rtm-accepting.yml',
]

describe('RTM YAML 端到端', () => {
  it('完整流程：7 个触发点逐点生效，追溯链与覆盖度正确', () => {
    const f = makeFixture('REQ-e2e-0001')
    f.writeDoc('requirement.md', REQUIREMENT_MD)
    f.writeDoc('design/architecture.md', DESIGN_MD)
    f.writeDoc('design/test-cases.md', TEST_CASES_MD)
    f.setTasks(fiveTasks())
    const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger, generatedBy: 'rtm-generator' })
    const p = (name: string) => join(f.reqDir, name)

    // 1) 立项
    expect(runRTMTrigger(gen, 'create', f.reqId).ok).toBe(true)
    expect(existsSync(p('rtm-lifecycle.yml'))).toBe(true)
    expect(readRTM<RTMLifecycle>(p('rtm-lifecycle.yml'))?.lifecycle.current_stage).toBe('draft')

    // 2) 提交需求文档
    f.patchRequirement({ status: 'brainstorming' })
    expect(runRTMTrigger(gen, 'submit:requirement', f.reqId).ok).toBe(true)
    expect(existsSync(p('rtm-brainstorming.yml'))).toBe(true)

    // 3) 确认需求 → 进入设计
    f.patchRequirement({ status: 'design', artifacts: [{ kind: 'requirement', path: 'requirement.md', confirmedAt: 4000 }] })
    expect(runRTMTrigger(gen, 'confirm:artifact', f.reqId).ok).toBe(true)

    // 4) 提交设计 → 设计覆盖度 67%（3 个 FR 覆盖 2 个）
    expect(runRTMTrigger(gen, 'submit:design', f.reqId).ok).toBe(true)
    const design = readRTM<RTMDesign>(p('rtm-design.yml'))
    expect(design?.coverage.design.rate).toBe(67)
    expect(design?.coverage.design.uncovered).toEqual(['FR-3'])

    // 5) 批准拆分计划 → 拆分 + 实施骨架 + 任务详情目录
    f.patchRequirement({ status: 'implementing' })
    expect(runRTMTrigger(gen, 'confirm:plan', f.reqId).ok).toBe(true)
    expect(existsSync(p('rtm-decomposing.yml'))).toBe(true)
    expect(existsSync(p('rtm-implementing.yml'))).toBe(true)
    expect(existsSync(join(f.reqDir, 'rtm-implementing', 't-0001.yml'))).toBe(true)

    // 6) 任务状态变更：开工 → 完成
    for (const id of ['t-0001', 't-0002', 't-0003', 't-0004', 't-0005']) {
      f.task(id)!.status = 'in_progress'
      expect(runRTMTrigger(gen, 'task:status', f.reqId, { taskId: id }).ok).toBe(true)
    }
    let summary = readRTM<RTMImplementing>(p('rtm-implementing.yml'))
    expect(summary?.status.tasks_in_progress).toBe(5)
    for (const id of ['t-0001', 't-0002', 't-0003', 't-0004', 't-0005']) {
      f.task(id)!.status = 'done'
      expect(runRTMTrigger(gen, 'task:status', f.reqId, { taskId: id }).ok).toBe(true)
    }
    summary = readRTM<RTMImplementing>(p('rtm-implementing.yml'))
    expect(summary?.status).toMatchObject({ tasks_total: 5, tasks_done: 5, tasks_in_progress: 0, tasks_todo: 0 })
    expect(readRTM<RTMLifecycle>(p('rtm-lifecycle.yml'))?.lifecycle.stages.find(s => s.stage === 'implementing')?.status).toBe('in_progress')

    // 7) 提交验收材料 → 测试覆盖度 40%
    f.patchRequirement({ status: 'accepting' })
    expect(runRTMTrigger(gen, 'submit:verification', f.reqId).ok).toBe(true)
    const acc = readRTM<RTMAccepting>(p('rtm-accepting.yml'))
    expect(acc?.coverage.testing.rate).toBe(40)
    expect(existsSync(p('rtm-accepting.yml'))).toBe(true)

    // 七个 RTM 文件齐全
    for (const name of RTM_FILES) expect(existsSync(p(name))).toBe(true)

    // 完整追溯链：FR-1 → design#1.1 → t-0001 → TC-1
    const so = assembleStageOverviewRTM({ workspaceRoot: f.root, reqId: f.reqId })
    const chain = buildTraceabilityChain('FR-1', so.traceability)
    expect(chain.designs).toEqual(['design/architecture.md#1.1'])
    expect(chain.tasks).toEqual(['t-0001', 't-0004'])
    expect(chain.tests).toEqual(['TC-1'])
    expect(so.coverage.design?.rate).toBe(67)
    expect(so.coverage.implementation?.rate).toBe(100)
    expect(so.coverage.testing?.rate).toBe(40)
  })

  it('文件体积受控（FR-10）：lifecycle 与实施汇总 < 100 行', () => {
    const f = makeFixture('REQ-e2e-0002')
    f.writeDoc('requirement.md', REQUIREMENT_MD)
    f.writeDoc('design/architecture.md', DESIGN_MD)
    f.setTasks(fiveTasks())
    const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger })
    gen.generateLifecycle(f.reqId)
    gen.generateImplementing(f.reqId)
    const lines = (n: string) => readFileSync(join(f.reqDir, n), 'utf-8').split('\n').length
    expect(lines('rtm-lifecycle.yml')).toBeLessThan(100)
    expect(lines('rtm-implementing.yml')).toBeLessThan(100)
    expect(lines('rtm-implementing/t-0001.yml')).toBeLessThan(50)
  })

  it('读取性能：Dive 决策只需 2 个文件，热读 < 5ms（FR-8/FR-10）', () => {
    const f = makeFixture('REQ-e2e-0003')
    f.writeDoc('requirement.md', REQUIREMENT_MD)
    f.setTasks(fiveTasks())
    const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger })
    gen.generateLifecycle(f.reqId)
    gen.generateImplementing(f.reqId)
    const lifecyclePath = join(f.reqDir, 'rtm-lifecycle.yml')
    const implPath = join(f.reqDir, 'rtm-implementing.yml')
    // 预热（排除首次 fs 打开成本）
    readRTM(lifecyclePath)
    readRTM(implPath)
    const start = performance.now()
    const lc = readRTM<RTMLifecycle>(lifecyclePath)
    const impl = readRTM<RTMImplementing>(implPath)
    const elapsed = performance.now() - start
    expect(lc?.lifecycle.current_stage).toBeDefined()
    expect(impl?.status.tasks_total).toBe(5)
    expect(elapsed).toBeLessThan(5)
  })
})
