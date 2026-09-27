/**
 * 追溯 handler 的覆盖度形状归一测试（REQ-260926140539-457b FR-6）。
 *
 * 为什么专门测这两个纯函数：装配器按节点只挂"自己那一段"覆盖度（扁平对象），
 * 而视图要 { design?, implementation?, testing? } 容器。此前直接透传导致
 * 三个分支全不命中、覆盖度卡片永不显示——这是本条集成最容易再次回归的地方。
 */
import { describe, it, expect } from 'vitest'
import { coverageKeyOf, toCoverageContainer } from '../src/client/traceability-handler.js'

const DESIGN_COV = { total: 0, covered: 0, uncovered: [], rate: 100, total_frs: 0, covered_frs: 0 }
const IMPL_COV = { total: 40, covered: 0, uncovered: ['a'], rate: 0, total_designs: 40, covered_designs: 0 }
const TEST_COV = { rate: 100, total: 0, covered: 0, uncovered: [], total_tasks: 0, tested_tasks: 0, untested: [] }

describe('coverageKeyOf', () => {
  it('按节点判定（契约：设计→design / 拆分·实施→implementation / 验收→testing）', () => {
    expect(coverageKeyOf('design', DESIGN_COV)).toBe('design')
    expect(coverageKeyOf('brainstorming', DESIGN_COV)).toBe('design')
    expect(coverageKeyOf('decomposing', IMPL_COV)).toBe('implementation')
    expect(coverageKeyOf('implementing', IMPL_COV)).toBe('implementation')
    expect(coverageKeyOf('accepting', TEST_COV)).toBe('testing')
  })

  it('节点缺失时按字段签名兜底', () => {
    expect(coverageKeyOf(undefined, IMPL_COV)).toBe('implementation')
    expect(coverageKeyOf(undefined, TEST_COV)).toBe('testing')
    expect(coverageKeyOf(undefined, DESIGN_COV)).toBe('design')
  })

  it('无法判定时返回 undefined（不硬塞错误分类）', () => {
    expect(coverageKeyOf(undefined, { foo: 1 })).toBeUndefined()
  })
})

describe('toCoverageContainer', () => {
  it('把扁平覆盖度包成视图要的容器（核心回归点）', () => {
    expect(toCoverageContainer(DESIGN_COV, 'design')).toEqual({ design: DESIGN_COV })
    expect(toCoverageContainer(IMPL_COV, 'implementing')).toEqual({ implementation: IMPL_COV })
    expect(toCoverageContainer(TEST_COV, 'accepting')).toEqual({ testing: TEST_COV })
  })

  it('已是容器形式时原样返回', () => {
    const container = { design: DESIGN_COV, testing: TEST_COV }
    expect(toCoverageContainer(container, 'design')).toBe(container)
  })

  it('空/非法输入返回 undefined（FR-9 降级，不抛）', () => {
    expect(toCoverageContainer(undefined, 'design')).toBeUndefined()
    expect(toCoverageContainer(null, 'design')).toBeUndefined()
    expect(toCoverageContainer('x', 'design')).toBeUndefined()
    expect(toCoverageContainer([], 'design')).toBeUndefined()
    expect(toCoverageContainer({ foo: 1 }, undefined)).toBeUndefined()
  })

  it('归一后的容器能被视图 renderCoverageSummary 的取值路径命中', () => {
    const c = toCoverageContainer(DESIGN_COV, 'design')
    expect(c?.design).toBeDefined()
    expect(c?.design?.rate).toBe(100)
    expect(c?.design?.uncovered.length).toBe(0)
    const t = toCoverageContainer(TEST_COV, 'accepting')
    expect(t?.testing?.tested_tasks).toBe(0)
    expect(t?.testing?.untested.length).toBe(0)
  })
})
