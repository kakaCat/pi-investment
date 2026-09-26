/**
 * t17/t18 · StageOverview RTM 读取与装配测试（FR-7 / FR-9）。
 */
import { rmSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { RTMGenerator } from '../../src/rtm/generator.js'
import {
  readAcceptingRTM,
  readDecomposingRTM,
  readDesignRTM,
  readLifecycleRTM,
  readStageRTM,
} from '../../src/stage-overview/rtm-reader.js'
import { assembleStageOverviewRTM } from '../../src/stage-overview/assembler.js'
import { DESIGN_MD, fiveTasks, makeFixture, REQUIREMENT_MD, TEST_CASES_MD } from './fixture.js'

function full() {
  const f = makeFixture()
  f.writeDoc('requirement.md', REQUIREMENT_MD)
  f.writeDoc('design/architecture.md', DESIGN_MD)
  f.writeDoc('design/test-cases.md', TEST_CASES_MD)
  f.setTasks(fiveTasks())
  const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger })
  gen.generateLifecycle(f.reqId)
  gen.generateBrainstorming(f.reqId)
  gen.generateDesign(f.reqId)
  gen.generateDecomposing(f.reqId)
  gen.generateImplementing(f.reqId)
  gen.generateAccepting(f.reqId)
  return { f, gen }
}

describe('rtm-reader (t17)', () => {
  it('读取各节点 RTM', () => {
    const { f } = full()
    expect(readLifecycleRTM(f.root, f.reqId)?.lifecycle.current_stage).toBe('draft')
    expect(readDesignRTM(f.root, f.reqId)?.outputs.design_sections).toHaveLength(2)
    expect(readDecomposingRTM(f.root, f.reqId)?.outputs.tasks).toHaveLength(5)
    expect(readAcceptingRTM(f.root, f.reqId)?.outputs.test_cases).toHaveLength(2)
    expect(readStageRTM(f.root, f.reqId, 'design')).not.toBeNull()
  })

  it('缺失返回 null（降级模式入口）', () => {
    const f = makeFixture()
    expect(readLifecycleRTM(f.root, f.reqId)).toBeNull()
    expect(readStageRTM(f.root, f.reqId, 'design')).toBeNull()
  })
})

describe('assembleStageOverviewRTM (t18)', () => {
  it('合并追溯映射与三层覆盖度', () => {
    const { f } = full()
    const out = assembleStageOverviewRTM({ workspaceRoot: f.root, reqId: f.reqId })
    expect(out.traceability.fr_to_design?.['FR-1']).toEqual(['design/architecture.md#1.1'])
    expect(out.traceability.design_to_tasks?.['design/architecture.md#1.2']).toEqual(['t-0002', 't-0005'])
    expect(out.traceability.task_to_tests?.['t-0001']).toEqual(['TC-1'])
    expect(out.coverage.design?.rate).toBe(67)
    expect(out.coverage.implementation?.rate).toBe(100)
    expect(out.coverage.testing?.rate).toBe(40)
  })

  it('RTM 缺失时用 regenerator 实时重建（FR-9 降级）', () => {
    const { f, gen } = full()
    rmSync(join(f.reqDir, 'rtm-design.yml'))
    rmSync(join(f.reqDir, 'rtm-decomposing.yml'))
    rmSync(join(f.reqDir, 'rtm-accepting.yml'))
    const out = assembleStageOverviewRTM({ workspaceRoot: f.root, reqId: f.reqId, regenerator: gen })
    expect(out.coverage.design?.rate).toBe(67)
    expect(out.traceability.fr_to_design?.['FR-2']).toEqual(['design/architecture.md#1.2'])
    expect(readDesignRTM(f.root, f.reqId)).not.toBeNull()
  })

  it('无 regenerator 且文件缺失 → 返回空块，不抛异常', () => {
    const f = makeFixture()
    const out = assembleStageOverviewRTM({ workspaceRoot: f.root, reqId: f.reqId })
    expect(out.traceability).toEqual({
      fr_to_design: {},
      design_to_tasks: {},
      fr_to_tasks: {},
      task_to_tests: {},
      fr_to_tests: {},
    })
    expect(out.coverage).toEqual({})
  })
})
