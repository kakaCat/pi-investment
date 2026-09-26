/**
 * t12-t16 · 7 个触发点集成测试（FR-2 / FR-9）。
 * 触发点 = 业务动作 → 该动哪几个 RTM 文件；失败必须结构化返回而不打断主流程。
 */
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { readRTM } from '../../src/rtm/file-io.js'
import { RTMGenerator, runRTMTrigger, type RTMTrigger } from '../../src/rtm/generator.js'
import type { RTMAccepting, RTMBrainstorming, RTMDecomposing, RTMDesign, RTMImplementing, RTMLifecycle, RTMTaskDetail } from '../../src/rtm/types.js'
import { DESIGN_MD, fiveTasks, makeFixture, REQUIREMENT_MD, TEST_CASES_MD } from './fixture.js'

function setup() {
  const f = makeFixture()
  f.writeDoc('requirement.md', REQUIREMENT_MD)
  f.writeDoc('design/architecture.md', DESIGN_MD)
  f.writeDoc('design/test-cases.md', TEST_CASES_MD)
  f.setTasks(fiveTasks())
  const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger, generatedBy: 'test' })
  return { f, gen }
}

function run(gen: RTMGenerator, trigger: RTMTrigger, reqId: string, payload?: { taskId?: string }) {
  return runRTMTrigger(gen, trigger, reqId, payload)
}

describe('触发点 1 · 立项 (t12)', () => {
  it('create → 生成 rtm-lifecycle.yml（current_stage=draft）', () => {
    const { f, gen } = setup()
    const res = run(gen, 'create', f.reqId)
    expect(res.ok).toBe(true)
    expect(res.files).toEqual(['rtm-lifecycle.yml'])
    expect(existsSync(join(f.reqDir, 'rtm-lifecycle.yml'))).toBe(true)
    expect(readRTM<RTMLifecycle>(join(f.reqDir, 'rtm-lifecycle.yml'))?.lifecycle.current_stage).toBe('draft')
  })
})

describe('触发点 2/3 · 提交需求 + 确认需求 (t13/t14)', () => {
  it('submit:requirement → rtm-brainstorming.yml（3 个 FR）', () => {
    const { f, gen } = setup()
    expect(run(gen, 'submit:requirement', f.reqId).ok).toBe(true)
    expect(readRTM<RTMBrainstorming>(join(f.reqDir, 'rtm-brainstorming.yml'))?.outputs.requirements).toHaveLength(3)
  })

  it('confirm:artifact → brainstorming 确认态落章 + 设计 RTM 生成 + lifecycle 推进', () => {
    const { f, gen } = setup()
    run(gen, 'submit:requirement', f.reqId)
    f.patchRequirement({ status: 'design', artifacts: [{ kind: 'requirement', path: 'requirement.md', confirmedAt: 3000 }] })
    expect(run(gen, 'confirm:artifact', f.reqId).ok).toBe(true)
    const brain = readRTM<RTMBrainstorming>(join(f.reqDir, 'rtm-brainstorming.yml'))
    expect(brain?.status?.artifacts[0]?.confirmed).toBe(true)
    expect(brain?.metadata.version).toBe(2)
    expect(existsSync(join(f.reqDir, 'rtm-design.yml'))).toBe(true)
    expect(readRTM<RTMLifecycle>(join(f.reqDir, 'rtm-lifecycle.yml'))?.lifecycle.current_stage).toBe('design')
  })
})

describe('触发点 4 · 提交设计 (t13)', () => {
  it('submit:design → rtm-design.yml，设计覆盖度 67%', () => {
    const { f, gen } = setup()
    run(gen, 'submit:requirement', f.reqId)
    run(gen, 'submit:design', f.reqId)
    const design = readRTM<RTMDesign>(join(f.reqDir, 'rtm-design.yml'))
    expect(design?.coverage.design.rate).toBe(67)
    expect(design?.coverage.design.uncovered).toEqual(['FR-3'])
  })
})

describe('触发点 5 · 批准拆分计划 (t13/t15)', () => {
  it('confirm:plan → rtm-decomposing.yml + rtm-implementing.yml + 任务详情目录', () => {
    const { f, gen } = setup()
    run(gen, 'submit:requirement', f.reqId)
    run(gen, 'submit:design', f.reqId)
    const res = run(gen, 'confirm:plan', f.reqId)
    expect(res.ok).toBe(true)
    expect(existsSync(join(f.reqDir, 'rtm-decomposing.yml'))).toBe(true)
    expect(existsSync(join(f.reqDir, 'rtm-implementing.yml'))).toBe(true)
    expect(existsSync(join(f.reqDir, 'rtm-implementing', 't-0001.yml'))).toBe(true)
    expect(readRTM<RTMDecomposing>(join(f.reqDir, 'rtm-decomposing.yml'))?.coverage.implementation.rate).toBe(100)
    expect(readRTM<RTMImplementing>(join(f.reqDir, 'rtm-implementing.yml'))?.status.tasks_todo).toBe(5)
  })
})

describe('触发点 6 · 任务状态 / 子阶段汇报 (t15/t16)', () => {
  it('task:status → 任务详情与汇总同步', () => {
    const { f, gen } = setup()
    run(gen, 'confirm:plan', f.reqId)
    f.task('t-0001')!.status = 'in_progress'
    expect(run(gen, 'task:status', f.reqId, { taskId: 't-0001' }).ok).toBe(true)
    expect(readRTM<RTMTaskDetail>(join(f.reqDir, 'rtm-implementing', 't-0001.yml'))?.task.status).toBe('in_progress')
    expect(readRTM<RTMImplementing>(join(f.reqDir, 'rtm-implementing.yml'))?.status.tasks_in_progress).toBe(1)
  })

  it('task:report → workflow 子阶段推进（done 数变化）', () => {
    const { f, gen } = setup()
    run(gen, 'confirm:plan', f.reqId)
    const res = runRTMTrigger(gen, 'task:report', f.reqId, {
      taskId: 't-0002',
      updates: { workflow: [{ phase: 'doc', status: 'done' }] },
    })
    expect(res.ok).toBe(true)
    const detail = readRTM<RTMTaskDetail>(join(f.reqDir, 'rtm-implementing', 't-0002.yml'))
    expect(detail?.task.workflow_done).toBe(1)
    expect(detail?.task.workflow[0]?.phase).toBe('doc')
    expect(detail?.task.workflow[0]?.completed_at).toBeTruthy()
  })

  it('缺 taskId → 结构化失败，不抛异常', () => {
    const { f, gen } = setup()
    const res = run(gen, 'task:status', f.reqId)
    expect(res.ok).toBe(false)
    expect(res.error).toContain('taskId')
  })
})

describe('触发点 7 · 提交验收材料 (t13)', () => {
  it('submit:verification → rtm-accepting.yml，测试覆盖度 40%', () => {
    const { f, gen } = setup()
    run(gen, 'confirm:plan', f.reqId)
    expect(run(gen, 'submit:verification', f.reqId).ok).toBe(true)
    const acc = readRTM<RTMAccepting>(join(f.reqDir, 'rtm-accepting.yml'))
    expect(acc?.coverage.testing.rate).toBe(40)
    expect(acc?.traceability.task_to_tests['t-0001']).toEqual(['TC-1'])
  })
})

describe('FR-9 · RTM 失败不打断主流程', () => {
  it('落盘失败（工作区不可写）→ 结构化 ok:false + error 原文', () => {
    const f = makeFixture()
    const gen = new RTMGenerator({ workspaceRoot: '/dev/null/not-a-dir', ledger: f.ledger })
    const res = run(gen, 'create', f.reqId)
    expect(res.ok).toBe(false)
    expect(typeof res.error).toBe('string')
    expect(res.error?.length).toBeGreaterThan(0)
  })
})
