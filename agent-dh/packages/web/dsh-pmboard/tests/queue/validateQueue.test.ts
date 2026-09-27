/**
 * validateQueueFile V-1~V-6 测试（REQ-260927202051-f6df · t3 / TC-2.1~TC-2.11 / FR-5）。
 *
 * 两条贯穿全场的断言：
 * 1. **坏数据不许抛错**（TC-2.10）——校验是"报告"而不是"断言"，throw 会把三种处置
 *    （写前拒绝/读后降级/更新前保旧）退化成一种。
 * 2. **6/6 规则各有反例**（TC-2.11）——每个 V-x 至少被一条反例命中，缺哪条就说明那条
 *    规则只写在文档里、没真的实现（这类"已覆盖"的假象最难发现）。
 */

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { hasIssue, validateQueueFile } from '../../src/domain/queue/validateQueue.js'
import type { QueueFile, ValidationIssue, ValidationRule } from '../../src/domain/queue/QueueTypes.js'
import { REQ, clone, mkTask, queueOf, rawQueue } from './fixtures.js'

const ALL_RULES: readonly ValidationRule[] = ['V-1', 'V-2', 'V-3', 'V-4', 'V-5', 'V-6']

/** 一份合法队列：t1 → {t2,t3} → t4（菱形），全 todo。 */
function validQueue(): QueueFile {
  return queueOf(REQ, [
    mkTask('t-000001'),
    mkTask('t-000002', { dependsOn: ['t-000001'] }),
    mkTask('t-000003', { dependsOn: ['t-000001'] }),
    mkTask('t-000004', { dependsOn: ['t-000002', 't-000003'] }),
  ])
}

/** 各规则的反例样本（TC-2.11 的汇总依据）。 */
function badSamples(): { name: string; file: QueueFile; rule: ValidationRule }[] {
  // V-1：缺 schemaVersion + ready 类型错误
  const v1 = clone(validQueue()) as unknown as Record<string, unknown>
  delete v1.schemaVersion
  v1.ready = 't-000001'

  // V-2：两条任务同 id
  const v2 = queueOf(REQ, [mkTask('t-000001'), mkTask('t-000001')])

  // V-3a：dependsOn 引用不存在的 id
  const v3a = queueOf(REQ, [mkTask('t-000001'), mkTask('t-000002', { dependsOn: ['t-999999'] })])
  // V-3b：task.requirementId ≠ queue.requirement_id（跨需求串档）
  const v3b = queueOf(REQ, [mkTask('t-000001', { requirementId: 'REQ-260927000000-dead' })])

  // V-4a：layer 小于依赖方 layer（层号未随依赖递增）
  const v4a = clone(validQueue())
  v4a.tasks[1]!.layer = 0
  // V-4b：layer=0 却有依赖
  const v4b = clone(validQueue())
  v4b.tasks[1]!.layer = 0

  // V-5a：假就绪（依赖未 done 却进 ready）
  const v5a = clone(validQueue())
  v5a.ready = ['t-000001', 't-000002']
  // V-5b：漏就绪（依赖全 done 却不在 ready）
  const v5b = queueOf(REQ, [mkTask('t-000001', { status: 'done' }), mkTask('t-000002', { dependsOn: ['t-000001'] })], {})
  v5b.ready = []

  // V-6：三任务成环（用 rawQueue 绕过分层——环样本在 computeLayers 那一步就抛错）
  const v6 = rawQueue(REQ, [
    mkTask('t-000001', { dependsOn: ['t-000003'] }),
    mkTask('t-000002', { dependsOn: ['t-000001'] }),
    mkTask('t-000003', { dependsOn: ['t-000002'] }),
  ])

  return [
    { name: 'V-1 缺 schemaVersion + ready 类型错', file: v1 as unknown as QueueFile, rule: 'V-1' },
    { name: 'V-2 任务 id 重复', file: v2, rule: 'V-2' },
    { name: 'V-3 dependsOn 悬空引用', file: v3a, rule: 'V-3' },
    { name: 'V-3 跨需求串档', file: v3b, rule: 'V-3' },
    { name: 'V-4 层号未随依赖递增', file: v4a, rule: 'V-4' },
    { name: 'V-4 layer=0 却有依赖', file: v4b, rule: 'V-4' },
    { name: 'V-5 假就绪', file: v5a, rule: 'V-5' },
    { name: 'V-5 漏就绪', file: v5b, rule: 'V-5' },
    { name: 'V-6 三任务成环', file: v6, rule: 'V-6' },
  ]
}

describe('validateQueueFile 正例（TC-2.9）', () => {
  it('合法队列：passed=true 且 issues.length===0', () => {
    const result = validateQueueFile(validQueue())

    expect(result.issues).toEqual([])
    expect(result.passed).toBe(true)
  })

  it('合法队列（空任务列表）：passed=true（空队列可写可读）', () => {
    const result = validateQueueFile(queueOf(REQ, []))

    expect(result.passed).toBe(true)
    expect(result.issues).toEqual([])
  })

  it('合法队列（依赖已完成 → 下游进 ready）：passed=true', () => {
    const file = queueOf(REQ, [mkTask('t-000001', { status: 'done' }), mkTask('t-000002', { dependsOn: ['t-000001'] })])
    expect(file.ready).toEqual(['t-000002'])

    expect(validateQueueFile(file).passed).toBe(true)
  })
})

describe('validateQueueFile 反例逐条（TC-2.1~TC-2.8）', () => {
  it('TC-2.1 V-1 必填字段完整性', () => {
    const sample = badSamples().find((s) => s.name.startsWith('V-1'))!
    const result = validateQueueFile(sample.file)

    expect(result.passed).toBe(false)
    expect(hasIssue(result, 'V-1')).toBe(true)
    expect(result.issues.some((i) => i.path === 'schemaVersion' || i.path === 'ready')).toBe(true)
  })

  it('TC-2.1b V-1 任务级必填字段（少一个字段即报，且给出 tasks[i].字段 路径）', () => {
    const file = clone(validQueue())
    delete (file.tasks[0] as unknown as Record<string, unknown>).lastReport
    const result = validateQueueFile(file)
    // lastReport 是可选字段 → 不应报错（证明必填清单没有把可选字段当必填）
    expect(result.passed).toBe(true)

    const broken = clone(validQueue())
    delete (broken.tasks[0] as unknown as Record<string, unknown>).acceptance
    const brokenResult = validateQueueFile(broken)
    expect(brokenResult.passed).toBe(false)
    expect(brokenResult.issues.some((i) => i.rule === 'V-1' && i.path === 'tasks[0].acceptance')).toBe(true)
  })

  it('TC-2.2 V-2 标识唯一性', () => {
    const result = validateQueueFile(queueOf(REQ, [mkTask('t-000001'), mkTask('t-000001')]))

    expect(result.passed).toBe(false)
    expect(hasIssue(result, 'V-2')).toBe(true)
  })

  it('TC-2.3 V-3 dependsOn 引用不存在的 id', () => {
    const result = validateQueueFile(badSamples().find((s) => s.name === 'V-3 dependsOn 悬空引用')!.file)

    expect(result.passed).toBe(false)
    expect(hasIssue(result, 'V-3')).toBe(true)
  })

  it('TC-2.3b V-3 edges / layers / ready 也做引用检查', () => {
    const file = clone(validQueue())
    file.edges.push({ from: 't-999998', to: 't-000001' })
    file.layers[0]!.tasks.push('t-999997')
    file.ready.push('t-999996')
    const result = validateQueueFile(file)

    expect(hasIssue(result, 'V-3')).toBe(true)
    expect(result.issues.filter((i) => i.rule === 'V-3').length).toBeGreaterThanOrEqual(3)
  })

  it('TC-2.4 V-3 task.requirementId ≠ queue.requirement_id（跨需求串档）', () => {
    const result = validateQueueFile(badSamples().find((s) => s.name === 'V-3 跨需求串档')!.file)

    expect(result.passed).toBe(false)
    expect(hasIssue(result, 'V-3')).toBe(true)
  })

  it('TC-2.5 V-4 层级一致性（层号未递增 / layer=0 有依赖）', () => {
    const inverted = validateQueueFile(badSamples().find((s) => s.name === 'V-4 层号未随依赖递增')!.file)
    expect(inverted.passed).toBe(false)
    expect(hasIssue(inverted, 'V-4')).toBe(true)

    const zeroWithDep = validateQueueFile(badSamples().find((s) => s.name === 'V-4 layer=0 却有依赖')!.file)
    expect(zeroWithDep.passed).toBe(false)
    expect(hasIssue(zeroWithDep, 'V-4')).toBe(true)
  })

  it('TC-2.5b V-4 层号必须从 0 连续 + layer 不得为负', () => {
    const gapped = clone(validQueue())
    gapped.layers = [{ layer: 0, tasks: ['t-000001'] }, { layer: 2, tasks: ['t-000002', 't-000003'] }]
    expect(hasIssue(validateQueueFile(gapped), 'V-4')).toBe(true)

    const negative = clone(validQueue())
    negative.tasks[0]!.layer = -1
    expect(hasIssue(validateQueueFile(negative), 'V-4')).toBe(true)
  })

  it('TC-2.6 V-5 假就绪（依赖未 done 却进 ready）', () => {
    const result = validateQueueFile(badSamples().find((s) => s.name === 'V-5 假就绪')!.file)

    expect(result.passed).toBe(false)
    expect(hasIssue(result, 'V-5')).toBe(true)
  })

  it('TC-2.6b V-5 ready 里出现非 todo 任务也算假就绪', () => {
    const file = queueOf(REQ, [mkTask('t-000001', { status: 'done' })])
    file.ready = ['t-000001']
    expect(hasIssue(validateQueueFile(file), 'V-5')).toBe(true)
  })

  it('TC-2.7 V-5 漏就绪（依赖全 done 却不在 ready）', () => {
    const result = validateQueueFile(badSamples().find((s) => s.name === 'V-5 漏就绪')!.file)

    expect(result.passed).toBe(false)
    expect(result.issues.some((i) => i.rule === 'V-5' && i.message.includes('漏就绪'))).toBe(true)
  })

  it('TC-2.8 V-6 三任务成环', () => {
    const result = validateQueueFile(badSamples().find((s) => s.name === 'V-6 三任务成环')!.file)

    expect(result.passed).toBe(false)
    expect(hasIssue(result, 'V-6')).toBe(true)
    expect(result.issues.some((i) => i.rule === 'V-6' && i.message.includes('CIRCULAR'))).toBe(true)
  })
})

describe('validateQueueFile 契约（TC-2.10 / TC-2.11）', () => {
  it('TC-2.10 全部反例：passed=false 且**未 throw**', () => {
    for (const sample of badSamples()) {
      let result: ReturnType<typeof validateQueueFile> | undefined
      expect(() => {
        result = validateQueueFile(sample.file)
      }, `样本「${sample.name}」不得抛错`).not.toThrow()
      expect(result!.passed, `样本「${sample.name}」应判失败`).toBe(false)
      expect(result!.issues.length, `样本「${sample.name}」应至少报一条问题`).toBeGreaterThan(0)
    }
  })

  it('TC-2.10b 畸形输入（null / 数组 / 空对象 / 字段类型全错）不抛错', () => {
    const grotesque: unknown[] = [
      null,
      undefined,
      [],
      {},
      { tasks: 'not-an-array' },
      { tasks: [null, 42, 'x'] },
      { tasks: [{}], edges: {}, layers: [{ layer: 'x', tasks: 'y' }], ready: [1, null] },
    ]
    for (const input of grotesque) {
      let result: ReturnType<typeof validateQueueFile> | undefined
      expect(() => {
        result = validateQueueFile(input as QueueFile)
      }).not.toThrow()
      expect(result!.passed).toBe(false)
      expect(result!.issues.some((i) => i.rule === 'V-1')).toBe(true)
    }
  })

  it('TC-2.11 6/6 规则覆盖：6 条 rule 在反例中各自至少出现一次', () => {
    const covered = new Set<ValidationRule>()
    for (const sample of badSamples()) {
      for (const issue of validateQueueFile(sample.file).issues) covered.add(issue.rule)
    }

    const summary = ALL_RULES.map((rule) => `${rule}:${covered.has(rule) ? '✓' : '✗'}`).join(' ')
    expect(summary).toBe('V-1:✓ V-2:✓ V-3:✓ V-4:✓ V-5:✓ V-6:✓')
    expect([...covered].sort()).toEqual([...ALL_RULES].sort())
  })

  it('每条 issue 都带规则号；定位信息（path）不缺主键字段', () => {
    const issues: ValidationIssue[] = validateQueueFile(badSamples()[2]!.file).issues
    expect(issues.length).toBeGreaterThan(0)
    for (const issue of issues) {
      expect(ALL_RULES).toContain(issue.rule)
      expect(issue.message.length).toBeGreaterThan(0)
    }
    expect(issues.some((i) => i.path === 'tasks[1].dependsOn[0]')).toBe(true)
  })

  it('环检测 import 自 topology.ts，未在本文件复制算法', () => {
    const source = readFileSync(new URL('../../src/domain/queue/validateQueue.ts', import.meta.url), 'utf8')

    // 必须从 topology import
    expect(source).toMatch(/from '\.\/topology\.js'/)
    expect(source).toContain('computeLayers')
    // Kahn 的算法内部量（入度表/释放队列）只应存在于 topology.ts
    expect(source).not.toContain('inDegree')
    expect(source).not.toContain('CIRCULAR dependency detected')
  })
})
