/**
 * topology 纯函数测试（REQ-260927202051-f6df · t2 / TC-1.1~TC-1.7 / FR-1）。
 *
 * 覆盖七种形状：线性 / 菱形 / 多层 / 环 / 空 / 多 ready / 依赖已 done。
 *
 * ⚠️ 路径口径说明（对验收锚点的一处**显式偏离**，非静默降级）：
 * 验收锚点写的是 `npx vitest run src/domain/queue/topology.test.ts`，但本仓
 * `vitest.config.ts` 的 `include` 是 `tests/**\/*.test.ts`——实测把测试文件放 src/
 * 下会被 vitest 判"filter 之后无测试文件"（exit 1，`No test files found`）。
 * 因此测试落在 `tests/queue/topology.test.ts`，验收命令相应为
 * `npx vitest run tests/queue/topology.test.ts`。**未改 vitest.config.ts**（不在本卡写域）。
 */

import { describe, expect, it } from 'vitest'
import { CIRCULAR_DEPENDENCY, computeEdges, computeLayers, computeReady } from '../../src/domain/queue/topology.js'
import type { QueueTask } from '../../src/domain/queue/QueueTypes.js'
import type { TaskRecord } from '../../src/shared/protocol.js'

/** 构造一份字段齐全的 QueueTask；只用 id / dependsOn / status 三个维度做形状。 */
function mk(id: string, opts: { dependsOn?: string[]; status?: TaskRecord['status'] } = {}): QueueTask {
  const actor = { kind: 'agent' as const, sessionId: 'session-topology-test' }
  const base: TaskRecord = {
    id,
    requirementId: 'REQ-260927202051-f6df',
    title: `任务 ${id}`,
    description: '拓扑测试样本',
    phase: 'implement',
    side: 'backend',
    scope: { apis: [], tables: [], files: [] },
    acceptance: '样本验收',
    context: '样本背景',
    dependsOn: opts.dependsOn ?? [],
    status: opts.status ?? 'todo',
    blocked: false,
    executions: [],
    comments: [],
    version: 1,
    createdAt: 1759000000000,
    updatedAt: 1759000000000,
    createdBy: actor,
    updatedBy: actor,
  }
  return { ...base, layer: 0 }
}

const layerIds = (tasks: QueueTask[]) => computeLayers(tasks).map((l) => l.tasks)

describe('topology.computeLayers（TC-1.1~TC-1.4）', () => {
  it('TC-1.1 线性链 t1→t2→t3：逐层单任务，ready 只有源头', () => {
    const tasks = [mk('t-000001'), mk('t-000002', { dependsOn: ['t-000001'] }), mk('t-000003', { dependsOn: ['t-000002'] })]

    expect(computeLayers(tasks)).toEqual([
      { layer: 0, tasks: ['t-000001'] },
      { layer: 1, tasks: ['t-000002'] },
      { layer: 2, tasks: ['t-000003'] },
    ])
    expect(computeReady(tasks)).toEqual(['t-000001'])
  })

  it('TC-1.2 菱形 t1→{t2,t3}→t4：中间层两个任务，ready=[t1]', () => {
    const tasks = [
      mk('t-000001'),
      mk('t-000002', { dependsOn: ['t-000001'] }),
      mk('t-000003', { dependsOn: ['t-000001'] }),
      mk('t-000004', { dependsOn: ['t-000002', 't-000003'] }),
    ]

    expect(computeLayers(tasks)).toEqual([
      { layer: 0, tasks: ['t-000001'] },
      { layer: 1, tasks: ['t-000002', 't-000003'] },
      { layer: 2, tasks: ['t-000004'] },
    ])
    expect(computeReady(tasks)).toEqual(['t-000001'])
  })

  it('TC-1.3 环 t1→t2→t3→t1：抛错且 message 含 CIRCULAR（不是静默返回空 ready）', () => {
    const tasks = [
      mk('t-000001', { dependsOn: ['t-000003'] }),
      mk('t-000002', { dependsOn: ['t-000001'] }),
      mk('t-000003', { dependsOn: ['t-000002'] }),
    ]

    expect(() => computeLayers(tasks)).toThrowError(/CIRCULAR/)
    try {
      computeLayers(tasks)
      expect.unreachable('环输入必须抛错')
    } catch (error) {
      expect((error as Error).message).toContain('CIRCULAR')
      expect((error as Error & { code?: string }).code).toBe(CIRCULAR_DEPENDENCY)
    }
  })

  it('TC-1.3b 自依赖也算环（t1 dependsOn t1）', () => {
    expect(() => computeLayers([mk('t-000001', { dependsOn: ['t-000001'] })])).toThrowError(/CIRCULAR/)
  })

  it('TC-1.4 空输入：空三件套且不抛错', () => {
    expect(computeLayers([])).toEqual([])
    expect(computeEdges([])).toEqual([])
    expect(computeReady([])).toEqual([])
  })

  it('多层（长链 + 旁支）：层号连续、旁支与其前置同层之后', () => {
    const tasks = [
      mk('t-000001'),
      mk('t-000002', { dependsOn: ['t-000001'] }),
      mk('t-000003', { dependsOn: ['t-000002'] }),
      mk('t-000004', { dependsOn: ['t-000003'] }),
      // 旁支：也依赖 t-000002 → 与 t-000003 同层
      mk('t-000005', { dependsOn: ['t-000002'] }),
      // 汇聚：依赖最深支路
      mk('t-000006', { dependsOn: ['t-000004', 't-000005'] }),
    ]

    expect(layerIds(tasks)).toEqual([
      ['t-000001'],
      ['t-000002'],
      ['t-000003', 't-000005'],
      ['t-000004'],
      ['t-000006'],
    ])
    expect(computeLayers(tasks).map((l) => l.layer)).toEqual([0, 1, 2, 3, 4])
  })

  it('悬空 dependsOn 不误报环，按"忽略该依赖"分层（引用合法性由 V-3 负责）', () => {
    const tasks = [mk('t-000001', { dependsOn: ['t-999999'] })]
    expect(computeLayers(tasks)).toEqual([{ layer: 0, tasks: ['t-000001'] }])
  })

  it('畸形条目（null / 数字 / 字符串）只跳过不抛错 —— 回归：曾抛 Cannot read properties of null', () => {
    const junk = [null, 42, 'x'] as unknown as QueueTask[]

    expect(() => computeLayers(junk)).not.toThrow()
    expect(computeLayers(junk)).toEqual([])
    expect(computeReady(junk)).toEqual([])
    expect(computeEdges(junk)).toEqual([])

    // 混在合法任务里也不影响正常分层（校验路径的 V-1 负责报"任务必须是对象"）
    const mixed = [mk('t-000001'), null, mk('t-000002', { dependsOn: ['t-000001'] })] as unknown as QueueTask[]
    expect(computeLayers(mixed)).toEqual([
      { layer: 0, tasks: ['t-000001'] },
      { layer: 1, tasks: ['t-000002'] },
    ])
  })

  it('dependsOn 非数组（畸形 JSON）不影响推导，不抛错', () => {
    const broken = [{ ...mk('t-000001'), dependsOn: 't-xxx' } as unknown as QueueTask]

    expect(() => computeLayers(broken)).not.toThrow()
    expect(computeEdges(broken)).toEqual([])
  })
})

describe('topology.computeEdges', () => {
  it('由 dependsOn 展开边集，from 是 to 的前置', () => {
    const tasks = [
      mk('t-000001'),
      mk('t-000002', { dependsOn: ['t-000001'] }),
      mk('t-000003', { dependsOn: ['t-000001', 't-000002'] }),
    ]

    expect(computeEdges(tasks)).toEqual([
      { from: 't-000001', to: 't-000002' },
      { from: 't-000001', to: 't-000003' },
      { from: 't-000002', to: 't-000003' },
    ])
  })

  it('重复 dependsOn 项去重；悬空依赖仍旧展开成边（交给 V-3 检出）', () => {
    const tasks = [mk('t-000001'), mk('t-000002', { dependsOn: ['t-000001', 't-000001'] }), mk('t-000003', { dependsOn: ['t-999999'] })]

    expect(computeEdges(tasks)).toEqual([
      { from: 't-000001', to: 't-000002' },
      { from: 't-999999', to: 't-000003' },
    ])
  })
})

describe('topology.computeReady（TC-1.5~TC-1.6）', () => {
  it('TC-1.5 多 ready：两个无依赖源头都在，被阻塞者不在', () => {
    const tasks = [mk('t-000001'), mk('t-000002'), mk('t-000003', { dependsOn: ['t-000001'] })]

    expect(computeReady(tasks)).toEqual(['t-000001', 't-000002'])
  })

  it('TC-1.6 依赖已 done：下游被解锁进入 ready', () => {
    const tasks = [
      mk('t-000001', { status: 'done' }),
      mk('t-000002', { dependsOn: ['t-000001'] }),
      mk('t-000003', { dependsOn: ['t-000002'] }),
    ]

    expect(computeReady(tasks)).toEqual(['t-000002'])
  })

  it('假就绪：依赖未 done 却已成 ready 的集合，与本函数结果可比对（V-5 的判据来源）', () => {
    const tasks = [mk('t-000001', { status: 'in_progress' }), mk('t-000002', { dependsOn: ['t-000001'] }), mk('t-000003', { status: 'done' })]

    const ready = computeReady(tasks)
    // t-000003 已完成、不参与 ready；t-000002 的前置未 done → 不放行
    expect(ready).toEqual([])
    expect(ready).not.toContain('t-000002')
  })

  it('非 todo 状态一律不进 ready（in_progress / testing / in_review / done / canceled）', () => {
    const statuses: TaskRecord['status'][] = ['in_progress', 'integrating', 'testing', 'in_review', 'done', 'canceled']
    const tasks = statuses.map((status, i) => mk(`t-10000${i}`, { status }))

    expect(computeReady(tasks)).toEqual([])
  })

  it('悬空依赖保守不放行（视为未满足）', () => {
    expect(computeReady([mk('t-000001', { dependsOn: ['t-999999'] })])).toEqual([])
  })
})

describe('topology 纯函数约束（TC-1.7）', () => {
  it('不改动入参（派生视图可安全重算）', () => {
    const tasks = [mk('t-000001'), mk('t-000002', { dependsOn: ['t-000001'] })]
    const before = JSON.stringify(tasks)

    computeLayers(tasks)
    computeEdges(tasks)
    computeReady(tasks)

    expect(JSON.stringify(tasks)).toBe(before)
  })
})
