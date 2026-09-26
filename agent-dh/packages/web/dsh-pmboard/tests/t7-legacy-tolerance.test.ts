import { describe, it, expect } from 'vitest'
import { isDrivableRequirement, roundLimitFor } from '../src/application/dive/round-state.js'
const legacy = { id: 'REQ-old', dive: { phase: 'implementing', activation: 'armed', roundsInStage: 2 } } as never
const noDive = { id: 'REQ-none' } as never
describe('T-7 legacy tolerance', () => {
  it('阶段名相位（旧数据）不被驱动', () => { expect(isDrivableRequirement(legacy)).toBe(false) })
  it('无 dive 字段不被驱动', () => { expect(isDrivableRequirement(noDive)).toBe(false) })
  it('未知阶段上限回落 10', () => { expect(roundLimitFor('nope')).toBe(10) })
})
